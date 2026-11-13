# Session record: GitHub Actions + WIF deploy workflows (Sector_Ops #53)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-08. Branch: `ci/wif-deploy-workflows-2026-11-07` (named by the owner's task).

## Scope
The owner's task: three `workflow_dispatch` workflows that deploy with Workload Identity Federation, the script switches they need, the doc
`docs/architecture/conditions/DEPLOY_WORKFLOWS_V1.md` and tests. Mid-session, a peer session (conditions consolidation design) aligned the
work with the reviewed IAM package (Sector_Ops #55): a build/deploy job split, action pins, the `GCP_AR_REPO` prefix convention and the
granted roles. That alignment was applied. Nothing was deployed, no `gcloud` / `firebase` / production call was made, and no IAM was changed.

## Done
- `.github/workflows/deploy-engine.yml`, `deploy-orchestrator.yml`, `set-conditions-tiles.yml` (see the doc).
- `deploy.sh`: `IMAGE=<digest>` mode. `scripts/linux-smoke.sh`: `SMOKE_SKIP_BUILD=1`. Default paths unchanged and tested.
- `jobs/brain-orchestrator/deploy-job.sh`: `SKIP_IAM`, `SKIP_SCHEDULER_DEFINITION`, `CARRY_ENV`, `IMAGE`, `CARRY_IMAGE`. The default path is unchanged and
  tested, and the staging block is untouched (image-build-verification extracts it).
- `tools/deploy/` (stdlib): `conditions_tiles_flag.py` (Remote Config read-modify-write with an ETag, TileFlags-semantics validation, serve
  refusal) and `job_env.py` (job env snapshot / carry / restore / compare). Tests are added to the `python-jobs-tests` platform loop.
- `.gitignore`: `gha-creds-*.json` (the auth action's credentials file must not make `deploy.sh`'s clean-tree gate fail).
- Fixed while there: `image-build-verification.yml` guarded the staging block with `! grep -q gcloud`, which does not trip `errexit`
  (shellcheck SC2251), so that guard never failed. It now fails explicitly.

## Decisions recorded for the owner (not taken here)
- Repository **variables** appear in public run logs, for example the provider resource name in the auth step's inputs. The workflows accept a
  repository **secret** of the same name, and a secret wins. Recommendation: store `GCP_WIF_PROVIDER` as a secret.
- `DEPLOYMENT_VERSION` changes with a new image under `CARRY_ENV` (it names the deployed commit, and the engineering-status gate compares it).
  Every other env value is carried unchanged.
- The `/control/conditionsSourcesV1` check is manual. The orchestrator deployer has no database role, and the node appears only after the
  owner resumes the scheduler.

## Verification
- `tools/deploy` 36 passed; `jobs/brain-orchestrator` 256 passed (incl. 12 new); `actionlint` + `shellcheck` clean on the new workflows
  (informational SC2016 only, intentional).
- Certification digests re-recorded (separate commit).

## Independent review (round 1) and fixes
- Fixed:
  - The engine rollback decided from the served traffic, which can lag a promotion still in flight. It now always re-pins to the previous
    revision once deploy.sh has started.
  - The orchestrator rollback skipped itself when `describe` failed. An unreadable state now counts as changed.
  - The dry cycle's gcloud output carried a console link with the project number. That output is now filtered before it is printed.
  - deploy-job.sh echoed the runtime service account's email. It now prints the account name only, and the test checks this.
  - Remote Config error bodies were printed (they can name the project number). Now only the HTTP code and Google's error status are printed.
  - A failed Remote Config read-back now restores the parameter, but only when nothing else in the template changed.
  - The `pytest` install in set-conditions-tiles now runs in a venv (PEP 668).
  - The orchestrator verify step now also checks the commit label and the service account.
  - The new `IMAGE` check in deploy.sh no longer blocks `--rollback` / `--check-warm-tags`.
- Owner decision, not changed: the reviewer flagged as blocking that repository **variables** print the WIF provider (project number) and
  the service-account emails in the public run logs. The design shared across sessions fixed variables. The workflows read
  `secrets.X || vars.X`, so storing them as secrets removes the leak without a code change.
- Known, documented: the build job's staged engineering status reports branch `HEAD` (detached checkout); deploy.sh prints its
  "local main differs" warning when an older main commit is deployed; deploy-job.sh resets CPU, memory and timeout to its fixed values, as
  on the Cloud Shell path.
