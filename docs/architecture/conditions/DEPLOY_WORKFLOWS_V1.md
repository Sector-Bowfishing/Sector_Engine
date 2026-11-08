# Deploy workflows V1: Engine, Orchestrator, conditions tile flags (GitHub Actions + WIF)

Status: **draft, not runnable yet**. The workflows cannot run until the owner applies the IAM: the WIF pool and provider, the three
deployer service accounts and their grants, and the repository settings (Sector_Ops #55, `docs/deploy/WIF_DEPLOY_IAM_V1.md`).
Context: Sector_Ops #53 (conditions consolidation). The owner approves each production use separately, on their own dates.

Three manually started workflows (`workflow_dispatch` only) authenticate to Google Cloud with Workload Identity Federation. They use no
key file and run nothing on a personal machine. Shared rules:

| Rule | How |
|---|---|
| Only from `main` | `if: github.ref == 'refs/heads/main'` on every job. The WIF provider also accepts only this repository, `refs/heads/main`, event `workflow_dispatch` and these named workflow files (`job_workflow_ref`). |
| Deliberate start | A `confirm` input: `DEPLOY` for the two deploys, `SET` for the flag. One concurrency group per workflow, never cancelled in progress. |
| Token only where needed | Each workflow has two jobs. The **build/validate** job has `contents: read` only and runs every build, smoke test, test and `pip install`. The **deploy/apply** job has `id-token: write` and runs only the checkout, auth, `gcloud`, the checks and the rollback. No dependency install runs in a job that can mint a Google token. |
| Pinned actions | Every action is pinned to a full commit SHA, with its tag in a comment: `actions/checkout` v4.4.0, `google-github-actions/auth` v2.1.13, `actions/upload-artifact` v4.6.2, `actions/download-artifact` v4.3.0. `gcloud` is the one preinstalled on `ubuntu-latest`; `auth` points it at the federated credentials. |
| No identifiers in the repository | The provider and service accounts come from repository settings: `GCP_WIF_PROVIDER`, `GCP_SA_ENGINE_DEPLOY`, `GCP_SA_ORCHESTRATOR_DEPLOY`, `GCP_SA_CONDITIONS_FLAGS`, and `GCP_AR_REPO` (the registry prefix `<region>-docker.pkg.dev/<project>`, with no repository name). The workflows never echo them. Each name may be a repository **secret** instead of a variable, and a secret wins. This repository's run logs are public, and GitHub masks secrets in logs but not variables. |
| Images by digest | Images are built on the runner (no Cloud Build) and handed from the build job to the deploy job as a 1-day artifact. The deploy job checks that the image ID is unchanged, then pushes the image to Artifact Registry with the commit as its tag and deploys it **by digest**. The logs show the digest, not the registry path. |
| Commit | `sha` is a full 40-character commit. It must be HEAD of `main` or an ancestor, and it is checked out exactly (`git rev-parse HEAD == sha`). A commit older than the scripts' new switches is refused. |

## 1. `deploy-engine.yml`: the `sector-engine` Cloud Run service

Inputs: `sha` and `confirm=DEPLOY`.

1. **build** (no token): validates the commit, builds the root `Dockerfile` and runs `scripts/linux-smoke.sh` against **that** image with
   `SMOKE_SKIP_BUILD=1` (new: it tests a prebuilt image without rebuilding it). The image is then saved as an artifact.
2. **deploy** (WIF, `GCP_SA_ENGINE_DEPLOY`):
   1. Loads the image, checks the image ID, and pushes it to `<GCP_AR_REPO>/sector-engine/sector-engine:<sha>`.
   2. Records the revision serving now. This is the rollback target.
   3. Runs `IMAGE=<digest ref> SKIP_LINUX_SMOKE=1 ./deploy.sh`. The new `IMAGE=` mode of `deploy.sh` follows the same flow:
      - a no-traffic `candidate` tag labeled with the commit;
      - the smoke test of the candidate (health, a real render, validation);
      - promotion to 100 %;
      - the prod re-check, which rolls back automatically if it fails;
      - `--update-secrets USGS_API_KEY=usgs-api-key:latest`;
      - the existing env is kept, and the sizing and probes are identical.
   4. Checks that the serving revision is labeled with this commit, then runs
      `python3 tools/conditions_golden/capture.py --base <service url> check --live`, the phone contract at all 17 probe points.
   5. **Rollback:** on any failure or cancellation after the rollback target was recorded, it runs `./deploy.sh --rollback <previous revision>`
      (only if traffic is not already there) and fails the job.
   6. The step summary shows the image digest, the revision serving before and after, and each check's outcome.

`IMAGE=` mode differs from the default `--source` path (still the Cloud Shell path, unchanged) in these ways:

| Difference | Why |
|---|---|
| `--image <digest>` replaces `--source .` | No Cloud Build. The deployed image is exactly the tested one: a non-digest `IMAGE` is refused. |
| The Linux smoke runs on `IMAGE` without rebuilding it | The workflow runs it in the build job and passes `SKIP_LINUX_SMOKE=1`. |
| `--allow-unauthenticated` is not passed | That flag sets the service IAM policy, which `run.developer` cannot do. The service is already public, and the candidate and prod smoke tests are unauthenticated, so they prove it is still public. |
| A detached HEAD is accepted when it is on `origin/main` | `actions/checkout` of an exact sha is detached. A commit not on main is still refused unless `ALLOW_BRANCH_DEPLOY=1`. |

## 2. `deploy-orchestrator.yml`: the `brain-orchestrator` Cloud Run job

Inputs: `sha` (a commit, or `current` to keep the job's current image), `projection` (`0` or `1`) and `confirm=DEPLOY`.

1. **build** (no token): runs `deploy-job.sh`'s own staging block, extracted exactly as `image-build-verification.yml` does it (it contains no
   `gcloud`), builds the staged context, smoke-imports the packaged knowledge, and saves the image. With `current` it builds nothing.
2. **deploy** (WIF, `GCP_SA_ORCHESTRATOR_DEPLOY`):
   1. **Preflight.** It reads the scheduler state. If the scheduler is **not PAUSED** (for example ENABLED), the run **stops before any
      change** and reports this. `deploy-job.sh` always leaves the scheduler PAUSED and resuming it is owner-only, so a running scheduler is
      never paused silently. The preflight then records the job's current image, env, `commit` label and arguments (`tools/deploy/job_env.py snapshot`).
      A job whose env holds a secret reference is refused, because an env-vars file cannot carry it.
   2. For a commit, it pushes `<GCP_AR_REPO>/brain-orchestrator/brain-orchestrator:<sha>`.
   3. It runs `SKIP_IAM=1 SKIP_SCHEDULER_DEFINITION=1 CARRY_ENV=1 CONDITIONS_SOURCES_PROJECTION=<0|1> deploy-job.sh` with
      `IMAGE=<digest ref>`, or `CARRY_IMAGE=1` for `current`. `ORCH_ARGS` is unset, so the job's arguments stay unchanged. The lineage
      preflight and the stale-score guard still run.
   4. **Verify.** The job must now have exactly the carried env (everything as before, except `CONDITIONS_SOURCES_PROJECTION`, and
      `DEPLOYMENT_VERSION=brain-orchestrator@<sha12>` when a new image was deployed), the intended image and unchanged arguments.
   5. **Dry cycle.** It runs `gcloud run jobs execute brain-orchestrator --args=--dry-run --wait` and requires `succeededCount >= 1` with no
      failed or cancelled task. A dry cycle writes nothing and starts nothing.
   6. **Rollback:** on any failure or cancellation after the preflight record, it runs `gcloud run jobs update` with the previous image, the
      previous env (`--env-vars-file`, the whole env) and the previous `commit` label, then re-checks it, and fails the job.
   7. **The projection node is a MANUAL check** (it is in the step summary). The deployer has no database role, and a dry cycle writes
      nothing. `/control/conditionsSourcesV1` appears only after the owner resumes the scheduler and a real cycle runs. Read it the way the
      repository's owner tools read `/control/*` (an authenticated RTDB REST GET, as in `tools/ops/execution_control.py`). Expect
      `schema: sector-conditions-sources-v1`, a recent `generatedAt` and `contractOk: true`.

New `deploy-job.sh` switches. Each is off unless set, and the default path is unchanged (`jobs/brain-orchestrator/tests/test_deploy_switches_wif.py`):

| Switch | Effect |
|---|---|
| `SKIP_IAM=1` | No service-account creation and no `add-iam-policy-binding` (project, bucket, Brain jobs, own job). The bindings must already exist. |
| `SKIP_SCHEDULER_DEFINITION=1` | The scheduler is not created, updated or paused; its state is only read. The existing end check still fails unless it is PAUSED. |
| `CARRY_ENV=1` | Reads the job's current env with `describe` and writes it back through `--env-vars-file`, changing only `CONDITIONS_SOURCES_PROJECTION` (and `DEPLOYMENT_VERSION` for a new image, because it names the deployed commit). Without it, `--set-env-vars` resets `RUNNER_LEASES`, `PUBLICATION_HANDOFF` and the rest to the script defaults, which would break the live hybrid Water Clarity setup. It refuses the other switch variables when set (they would be ignored), and it refuses an unset projection. |
| `IMAGE=<ref>@sha256:<digest>` | Deploys a prebuilt image. `IMAGE=<ref>:<tag>` builds the staged context with local Docker, pushes it and deploys it by digest (for a Cloud Shell use without Cloud Build). |
| `CARRY_IMAGE=1` | Together with `CARRY_ENV=1`, redeploys the job's current image and keeps its `commit` label: an env-only change. |

## 3. `set-conditions-tiles.yml`: Remote Config `conditions_tiles_v1`

Inputs: `preset` (`off` or `weather-shadow`) and `confirm=SET`. The tool is `tools/deploy/conditions_tiles_flag.py` (stdlib), tested in
`tools/deploy/tests/test_conditions_tiles_flag.py`.

- `weather-shadow` writes exactly
  `{"version":1,"tiles":{"humidity":{"mode":"shadow"},"pressure":{"mode":"shadow"},"temperature":{"mode":"shadow"},"sky":{"mode":"shadow"},"wind":{"mode":"shadow"}}}`
  as a top-level JSON parameter. `off` deletes the parameter, which TileFlags reads as every tile off.
- **Validate** (no token): `pip install pytest`, the tool's tests, and `plan`.
  - The value is checked with **TileFlags semantics**: a Python mirror of `TileFlags.parse` / `mode(for:lakeId:)`. A test pins its keys and
    modes to the Swift enums. The check is stricter than the parser: unknown keys, `lakes` restrictions or a version other than 1 fail it.
  - **Anything containing `serve` is refused.** That flip is customer-visible and the owner approves it separately. `weather-shadow` is also
    refused when the *current* value contains `serve`. `off`, the rollback, is always allowed.
- **Apply** (WIF, `GCP_SA_CONDITIONS_FLAGS`, a 10-minute access token):
  1. It GETs the template and its **ETag**, and prints the template version **before**.
  2. It refuses a `conditions_tiles_v1` inside a parameter group or one with conditional values, because the Engine reads only the top-level
     default (`RemoteConfigREST.defaults`).
  3. It changes ONLY that parameter: `PUT ?validate_only=true`, then `PUT` with `If-Match: <etag>`, so a concurrent edit fails instead of
     being lost.
  4. It reads the template back, requires every other parameter, group and condition to be identical, and re-validates the value. It prints
     the version **after**.
- **Rollback:** run the workflow again with `off`, or roll Remote Config back to the printed "before" version. The Engine picks up a change
  within its 10-minute cache.

## 4. GCP permissions per job (role names and resource types only)

These are the grants of the reviewed IAM package (Sector_Ops #55). The owner applies them from Cloud Shell. The workflows are designed to
need nothing more; the items marked *unverified* are listed on Sector_Ops #53.

| Job | Grant | On | Used for |
|---|---|---|---|
| all | `roles/iam.workloadIdentityUser` for the provider's principal set (this repository, `refs/heads/main`, `workflow_dispatch`, the named workflow file) | the job's deployer service account | federation; minting the deployer's tokens |
| **E** deploy-engine | `roles/run.developer` | the `sector-engine` Cloud Run **service** | describe, deploy a revision (no traffic, tag), update traffic, read revisions (`deploy.sh`, `ops/check_warm_tags.sh`) |
| E | `roles/iam.serviceAccountUser` | the Engine **runtime** service account | deploying a revision that runs as it |
| E | `roles/artifactregistry.writer` | the Artifact Registry **repository** `sector-engine` | pushing the image |
| E | no Secret Manager role | n/a | `--update-secrets` only references the secret; the runtime account reads it |
| **O** deploy-orchestrator | `roles/run.developer` | the `brain-orchestrator` Cloud Run **job** | describe, deploy/update, execute with `--args` overrides (dry cycle), rollback |
| O | `roles/iam.serviceAccountUser` | the `brain-writer` service account | the job runs as it |
| O | `roles/artifactregistry.writer` | the Artifact Registry **repository** `brain-orchestrator` | pushing the image |
| O | `roles/cloudscheduler.viewer` | project | reading the scheduler state (never changing it) |
| O | no IAM-admin and no scheduler-admin role | n/a | hence `SKIP_IAM=1` and `SKIP_SCHEDULER_DEFINITION=1` |
| **F** set-conditions-tiles | `roles/firebaseremoteconfig.admin` | project | reading and publishing the Remote Config template |

*Unverified until a first run:*
- whether service-level `run.developer` covers `gcloud run revisions describe` for that service's revisions;
- whether job-level `run.developer` covers `run jobs execute --args` (`runWithOverrides`) and reading the execution `--wait` polls;
- whether `gcloud run jobs execute --wait --format=json` prints the finished execution with `succeededCount`;
- whether the orchestrator's current image is stored by digest. If it is stored by tag, `current` and the rollback redeploy that tag.

## 5. Tests

| Suite | Covers |
|---|---|
| `tools/deploy/tests/test_conditions_tiles_flag.py` | the exact preset string; TileFlags parse mirror (fail-safe cases) and the Swift enum pin; serve refusals; strict validation; single-parameter edit; read-back detection; ETag/If-Match and `validate_only` against a fake Remote Config; idempotence; dry run |
| `tools/deploy/tests/test_job_env.py` | snapshot, carry-forward (only the projection changes), env-file round trip, secret refusal, restore and compare |
| `tools/deploy/tests/test_deploy_sh_image_mode.py` | `deploy.sh` `IMAGE=` flags against a fake `gcloud` in a throwaway repository: same flow, digest only, commit must be on main, default and rollback paths unchanged |
| `jobs/brain-orchestrator/tests/test_deploy_switches_wif.py` | the whole `deploy-job.sh` against a fake `gcloud`/`docker`: no IAM or scheduler writes, the env carried exactly, prebuilt, build and carried image, refusals, a non-PAUSED scheduler fails, the default path unchanged |

All run in `python-jobs-tests.yml` (`tools/deploy` added to the platform loop). None of them touches Google Cloud.
