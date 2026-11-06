# Runner lease and artifact uploader, V1 (DRAFT; Sector_Ops #46, #47, #50)

**Status:** draft code, off by default. Nothing is deployed, no IAM is granted and no lease exists anywhere.

**Purpose.** The owner wants Sector Pulse, the runner on the owner's Mac mini, to run the Brains, with the cloud jobs as a fallback that stays **OFF** until the owner turns it on. These two pieces let a second runner exist without breaking the single-scheduler rule (Cortex PL-15) or making a double publish possible.

## 1. The lease (`jobs/brain_platform/sector_brain_platform/runner_lease.py`)
- **Storage.** There is one object per Brain, `exports/runners/leases/{brainId}.json` (`sector-runner-lease-v1`), in the private artifact store. It is written by compare-and-swap (generation match), the same mechanism as the Publisher's apply lock.
- **Granting.** Only the **Orchestrator** grants or hands over a lease (`grant`), wherever the Orchestrator runs.
  - A fresh lease of another runner is never taken.
  - An expired lease goes to a different runner only when **failover is enabled** for that Brain in the reviewed `runner-policy.json`.
- **Renewing.** Only the **holder** renews, as a heartbeat (`renew`), and only while the lease is unexpired. An expired lease must be granted again, so a runner that lost its lease stops before it seals.
- **Policy.** `runner-policy.json` is reviewed in git: `defaultPrimary: cloud`, **failover off**. Since 2026-11-06 one per-Brain primary: `water-clarity` = `pulse` (owner, Sector_Ops #51 O4; `approvals` records the approvalRef). Every other Brain stays on the cloud. Making Pulse primary for a Brain, or enabling failover, is an owner decision with an `approvalRef`.
- **Orchestrator gate** (`--runner-leases` or `RUNNER_LEASES=on`, default off). Before starting a Brain's Cloud Run job, `cloud_may_start`:
  - refuses while another runner holds a fresh lease;
  - refuses whenever the policy primary is not the cloud and failover is off.

  A missing store or policy fails closed, so it never means a surprise cloud run.
- **Runs outside Cloud Run** leave a create-only `exports/runners/{holder}/executions/{brainId}/{executionId}.json`. With the flag on, the publication stage reconciles those runs exactly like Cloud Run executions.

## 2. The uploader (`tools/runner/runner.py upload`)
Pulse calls it through its Engine bridge, from a commit-pinned Engine snapshot. For a locally sealed artifact (for example `run.py --dry-run --out DIR` → `DIR/artifact.json`), it does the following:
1. checks that the lineage is present (Brain, execution, schema, generation time);
2. requires this runner to hold a fresh lease for the Brain (exit 3 otherwise);
3. stores the artifact create-only under `artifacts/{brainId}/` with the Brain's own `ArtifactWriter`, the call Cloud Run jobs make. An identical re-upload is a no-op, and a different artifact under the same id is an error;
4. reads it back by digest and canonical form (exit 5 on mismatch);
5. creates the runner execution record.

It never writes a database and never starts anything. `runner.py renew` is the heartbeat; `show` and `grant` (Orchestrator only) are for operations.

## 3. What this does not do yet
- **Identity.** The access split (Pulse may create only `artifacts/{brainId}/` and its own execution records, and renew leases) is enforced in code (`runner_view`), not yet by IAM. A per-holder IAM condition is part of the Pulse activation plan.
- **Lease history.** The Orchestrator does not yet record its grants in its publication ledger, so `held_for_cycle` has no production caller. That wiring comes with Pulse activation.
- **Pulse side.** Calling `renew` / `upload` from Pulse's pipeline is the matching Sector-Pulse PR.

## Runner executor, local runner mode and grant ledger (Sector_Ops #51 C1, C2)
- **Grant instead of start.** With `--runner-leases`, a Brain whose `runner-policy.json` primary is not the cloud is granted that runner's lease for the cycle (`grant_to_primary`). The Orchestrator starts nothing; the runner runs the Brain while it holds the lease and records its execution. A fresh lease of the same holder is not granted again (the cycle is in progress). A dry run grants nothing.
- **Local runner mode.** `--runner-mode local` (or `RUNNER_MODE=local`) is for an Orchestrator cycle that runs outside Cloud Run. It makes **no Cloud Run or Cloud Scheduler API call**: `gcp.disable_cloud_calls` refuses every call, `/jobs` is not synced, a cloud-primary Brain waits, and the overlap guard is a local lock file. The Publisher pass runs as a local process (`run_publisher_locally`); it is a dry run unless `PUBLISHER_LOCAL_LIVE=on`, which needs its own approval.
- **Grant ledger.** Every grant is also written create-only to `exports/runners/grants/{brainId}/{cycleId}.json`. The publication stage reconciles a runner execution only for a cycle that was granted to that runner (`reconcilable_executions`).
- Nothing changes until the policy names a non-cloud primary (owner step O4).
- **Review hardening (2026-11-03):**
  - **The grant ledger is the only proof of a grant.** A runner's credential may rewrite the live lease object (renew), so a lease object alone never counts. The ledger record is written before the lease.
  - **No grant every hour.** A primary gets a new cycle at most once per the Brain's staleness window, and never more often than the lease TTL. Today's grants count against the execution control's `maxRunsPerDay`.
  - **The local Publisher pass runs only with the Publisher identity:** `PUBLISHER_ACCESS_TOKEN`, mapped to the child's `BRAIN_ACCESS_TOKEN`. It never uses the orchestrator's token or a gcloud fallback.
  - **A local cycle refuses to start without an explicit `BRAIN_ACCESS_TOKEN`.**
  - **The shadow lane never runs in local mode.**

## Hybrid deploy switches (Sector_Ops #51 O5.1; O3 decision (b))
In the hybrid path, Pulse runs the Brain job and the Orchestrator and Publisher stay in Cloud Run. `jobs/brain-orchestrator/deploy-job.sh` takes three switches, all off by default:

- **`RUNNER_LEASES=on`:** the cloud cycle honours `runner-policy.json`.
  - **Every** cloud Brain's start reads the lease store first.
  - So `brain-writer` needs its `exports/runners/` grants (O5.2) before this is on; otherwise every Brain fails closed and holds.
- **`PUBLICATION_HANDOFF=on`** (requires `PUBLICATION_COORDINATION=on`): publication requests for CENTRAL Brains, and the `brain-publisher` start.
- **`ORCH_ARGS`:** the job's arguments, `;`-separated, from an allowlist (`--publish-engineering-status`, `--publish-health`, `--run-shadow-lane`).
  - Unset leaves the deployed arguments as they are. An empty string resets them.
  - The hybrid deploy uses `ORCH_ARGS="--publish-engineering-status;--publish-health"`, so the shadow lane is off (owner choice (ii), 2026-11-06).
- **Every deploy replaces the job's whole environment** (`--set-env-vars`), and every script default is `off`. So the hybrid deploy must restate the live switches:
  `WIND_MEASUREMENTS=on PUBLICATION_COORDINATION=on PUBLICATION_HANDOFF=on RUNNER_LEASES=on ORCH_ARGS="--publish-engineering-status;--publish-health"`.
  - Leaving out `WIND_MEASUREMENTS=on` silently turns the Wind measurements off.
- **Before `RUNNER_LEASES=on` or `PUBLICATION_HANDOFF=on`,** `brain-writer` needs `roles/run.invoker` on `brain-publisher` and its `exports/runners/` grants (O5.2). Without them:
  - every Publisher start fails with START_FAILED (requests stay pending);
  - every Brain holds.
