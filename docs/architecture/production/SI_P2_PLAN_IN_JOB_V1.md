# SI-P2: where Sector Intelligence's skip decision runs

Status: **DECIDED, option (b)**. The owner approved it on 2026-11-05 (Sector_Ops #50): the plan moves into the job, with Pulse's SKIPPED outcome built first. Everything ships **off**. Nothing is deployed and no runner is enabled.

## Before
- With `SI_ARTIFACT_JOB=1` (SI-A2, default off), the Orchestrator ran `run.py --plan` **in its own process** to decide PUBLISH or SKIP (`planInProcess`), and only then leased the cycle to Pulse.
- `run.py --artifact` already computes the same `orch.plan` from the same reads before it seals anything.

## Option (b), as built
1. **Engine, the Orchestrator** (`orchestrate.intelligence_executor`):
   - With `SI_JOB_PLAN=1` as well as `SI_ARTIFACT_JOB=1`, `planInProcess` is False. Both switches are default off.
   - The Orchestrator then runs no Intelligence code. It leases the cycle on the schedule and dependency triggers alone.
   - `SI_JOB_PLAN` alone changes nothing.
   - Test: `test_with_si_job_plan_the_orchestrator_never_asks_for_the_plan_and_still_leases`.
2. **Engine, the job** (`run.py`):
   - `--emit-decision FILE`, with `--artifact` only, writes the job's verdict to a local, create-only `sector-job-decision-v1` file: `{action, reasons, artifactId, forced}`.
   - A SKIP seals nothing and names no artifact.
   - Test `test_job_plan.py` pins two things: `--artifact` asks `orch.plan` with the same published state, fingerprint and version as `--plan`; and the decision file is right for both SKIP and PUBLISH.
3. **Engine, the runner tool** (`tools/runner/runner.py skip`):
   - Pulse records a SKIP for the cycle it holds. The tool refuses if there is no fresh lease, or if the lease is for another cycle.
   - It writes a create-only `SKIPPED` runner execution record (`{cycle}-skip`): no artifact, with the decision instead.
   - `runner_lease.record_execution` accepts `SKIPPED` only with a decision, no artifact and a cycle. Existing SUCCEEDED and FAILED records keep their exact bytes.
4. **Engine, the publication stage** (`PublicationCoordinator.reconcile`):
   - A SKIPPED run is listed under `skippedRuns`. It is never a missing artifact or a failed run, and it is never matched to an artifact by time window.
   - The Orchestrator prints `skipped runs N` beside failed runs.
   - This also fixes today's in-process SKIP records, which the stage had counted as failed runs.
5. **Pulse** (Sector-Pulse, `central.after_run`):
   - The fix applies only to a lease job that declares `skipDecision` (a decision file name) in the catalog.
   - When such a job leaves no artifact but a decision file that says SKIP, Pulse calls `runner.py skip` and records `CENTRAL_SKIPPED` (severity info) instead of `PUBLICATION_FAILED`.
   - A job that declares nothing behaves exactly as before.

## Still to do (not in this change)
- **SI-A5** (held by the owner): the `sector-intelligence-central` catalog entry (Pulse #6) and `run.py --emit` (#130). The entry would add `--emit-decision {out}/decision.json` and `"skipDecision": "decision.json"`.
- **Ops:** show `skippedRuns` as a normal cycle outcome. Today it appears in the cycle log only.
- **Daily cap:** the execution-control `runs today` count includes SKIPPED runs and leases granted. With the plan in the job, every scheduled cycle is a lease. Before `SI_JOB_PLAN` is turned on, check Intelligence's runs-per-day cap and its re-grant cooldown.
- **The lease after a skip:** it is not released early. It expires on its TTL (20 minutes), and the re-grant cooldown applies as before.
