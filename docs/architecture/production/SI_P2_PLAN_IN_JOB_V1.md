# SI-P2: where Sector Intelligence's skip decision runs (DRAFT, for owner decision)

Status: DRAFT. It was written under the standing approval of 2026-11-05 ("SI-A5/SI-P2 as drafts", Sector_Ops #50). Nothing here is decided or switched on. It checks against Engine `main`, with #123 (SI-A2) merged.

## Today
- With `SI_ARTIFACT_JOB=1` (SI-A2, default off), the Orchestrator still runs `run.py --plan` **in its own process** to decide PUBLISH or SKIP (`planInProcess`). Only then does it lease the cycle to Pulse.
- `run.py --artifact` **already makes the same decision itself:**
  - `orch.plan(...)` runs before sealing.
  - On SKIP it seals nothing, prints `"published": false`, and exits 0 (unless `--force` is given).

## Options
- **(a) Keep the plan in the Orchestrator** (the shipped default). The Orchestrator keeps running Brain code, Intelligence's `--plan` with its reads, every cycle.
- **(b) Move it into the job** (recommended in SECTOR_INTELLIGENCE_JOB_PLAN_V1). The Orchestrator leases Intelligence on its schedule without asking, and the job's own plan decides. The Orchestrator then runs no Brain code.

## What (b) needs (found while drafting)
1. **Engine:** `planInProcess: False` under a second default-off switch. A test must pin that the decision inputs are the same, because the job computes the same `orch.plan` from the same reads.
2. **Pulse:** `central.after_run` treats a lease run with no `artifact.json` as `PUBLICATION_FAILED` / `NO_ARTIFACT`.
   - Under (b), a normal SKIP would raise a critical event every cycle.
   - Pulse needs a SKIPPED outcome: the job prints `"published": false` with a SKIP decision and no artifact. That should end the lease cleanly with no hand-off, and record the decision.
   - This already matters for (a): the Orchestrator's plan and the job's plan run minutes apart and can disagree.
3. **Ops:** a SKIP has to be visible as a normal cycle outcome, not a gap.

## Recommendation
- (b), in two steps: first the Pulse SKIPPED outcome (useful under (a) too), then the Engine switch.
- Both are drafts until the owner decides SI-P2. The Pulse half is on the `sector-intelligence-central` draft (SI-A5).
