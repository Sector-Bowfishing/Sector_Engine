# Sector Engine — centralized Brain scheduling and cloud cost shutdown — Session Record

```text
Standards: Rehtac Cortex 2.7.0 @ ebc7fb9 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · main @ e6ed2388 (start) · Branch: cortex/central-scheduling-2026-10-23 · Date: 2026-10-23
```

**Owner directive (2026-10-23).** Pause all recurring Brain execution now and keep it paused until the owner explicitly authorizes reactivation. Consolidate automatic execution into the existing `brain-orchestrator`, and make it permanent in Cortex.

## 1. Cloud shutdown (02:35Z, before any code change)

Discovery covered:
- Cloud Scheduler (all locations)
- Eventarc
- Pub/Sub subscriptions
- Cloud Functions
- Cloud Run services and jobs
- Workflows and Cloud Tasks (their APIs are not enabled in the project, so none exist)

| Trigger | Before | After |
|---|---|---|
| `wind-hourly` (5 * * * *) | ENABLED (last fire 02:05Z) | **PAUSED** 02:35:59Z |
| `brain-orchestrator` (50 * * * *) | ENABLED (last fire 01:50Z) | **PAUSED** |
| `lake-brain-ledger-daily` (0 12 * * *) | ENABLED (last fire 2026-10-22 12:00Z) | **PAUSED** |
| `lake-surface-dispatch`, `lake-surface-daily`, `clarity-current-hourly`, `hydrology-hourly`, `water-temp-tva-archive`, `clarity-candidate-shadow` | PAUSED | PAUSED |

**Not Brain execution, left untouched:**
- Eventarc triggers for `playNotifications`/`playNotificationsDev` (Play RTDN Pub/Sub) and `subscriptionLedgerDev` (RTDB write);
- the RTDB-event Cloud Functions: social activity, notifications, purchases;
- the HTTP functions;
- Cloud Run services `sector-engine`, `conditions`, `wind-candidate-read` and the purchase/notification services. These are customer-serving or on-demand, with no recurring trigger.

**After the pause:**
- No Brain Cloud Run execution started at the 02:50Z orchestrator slot (last `brain-orchestrator-cz5tt` 01:50Z).
- No running executions remain.

## 2. Changes

- **`sector_brain_platform/execution_control.py`:** the fail-closed global and per-Brain control (`brain-execution-control-v1`):
  - the gate covers global state, per-Brain enablement, `maxStartsPerCycle` (no catch-up burst), `maxRunsPerDay` and `maxCostPerDay`;
  - admin runs need `requestedBy` and a reason;
  - the owner CLI is `tools/ops/execution_control.py`, and the owner-only resume path is `tools/ops/resume-orchestrator.sh`.
- **The orchestrator:**
  - It reads the control first; unreadable means PAUSED.
  - While paused it starts no worker, runs no Brain plan check and no shadow lane.
  - It has an overlap guard (no concurrent cycles) and a gate before every start.
  - `--admin-reason` makes an explicit, recorded admin run.
  - Wind is an executor (the `wind-hourly` job); `NOT_STARTED_HERE` is empty.
- **Execution manifest:**
  - Wind and Lake are ORCHESTRATOR_OWNED, with `deprecatedScheduler` PAUSED.
  - `lake-brain` is scoped (pilots).
  - The jobs map has exactly one scheduler, `brain-orchestrator`.
- **`schedule-policy.json`:**
  - The only allowed scheduler is `brain-orchestrator`, which requires the execution control to be ENABLED; it is "NOT APPROVED" until the owner resumes it.
  - Deprecated: `wind-hourly`, `lake-brain-ledger-daily`.
  - `check_preproduction_schedules.py` audits deprecated schedulers and the control (live: it reads the RTDB node).
- **Deploy scripts:**
  - None creates, updates or resumes a scheduler, except that the orchestrator's script maintains its own trigger definition, then always pauses it and fails if it is not PAUSED.
  - `SCHEDULE_STATE` was removed.
  - The orchestrator is granted `run.invoker` on `wind-hourly`.
- **`brain.json` `operations.execution`** (BR-21) in all 8; `ops-check --repo`: 0 findings.
- **Status:**
  - `engineering-status-ops-v1` 1.3.0 (additive) adds a top-level `executionControl` and `internalOperation.executionControl`.
  - A Brain is reported PAUSED while the control is not ENABLED (FAILED stays FAILED). The evidence (last execution, runtime readiness) is kept.
- **Docs and records:**
  - `docs/brains/platform/CENTRAL_SCHEDULING_V1.md`: design, activation procedure, costs.
  - `path_families.json`: `/control/executionControlV1`.
  - Cortex pin 2.7.0 @ ebc7fb9; compliance PL-15..18, BR-21.

## 3. Verification before merge

- **New tests:** `tests/test_central_scheduling.py` (20) covers mission checks 1–13; check 14 is live. A mutation check of five safeguards caught every one.
- **Existing scenario tests** now run under an explicit ENABLED control fixture.
- **All suites pass;** certification was recollected.

## 4. Merges and deployments

| Step | Result |
|---|---|
| Cortex 2.7.0 | `ebc7fb9` (Cortex maintenance session), validate 0 problems, pushed |
| `/control/executionControlV1` | written PAUSED by the owner CLI, 03:08:22Z; all 8 Brains disabled |
| PR #56 | CI 9/9, `gh pr checks` rc=0 → merged `fa0f40ad`; orchestrator deployed `fa0f40ad558e`, its trigger left PAUSED by the new deploy script; `brain-writer` granted `run.invoker` on `wind-hourly` |
| Live defect | the first bounded paused status cycle `brain-orchestrator-z9s6r` (03:17Z) failed in the new overlap guard: `gcp.running_executions` returns names. It failed before any action: no worker, no write. The tests had mocked the helper. |
| PR #57 (fix) | CI rc=0 → merged `c7b54484`; orchestrator deployed `c7b544844298`; trigger PAUSED |

## 5. Production verification (2026-10-23 ~03:31–03:45Z)

**Bounded paused status cycle `brain-orchestrator-h4qb2`:**
- It found the execution control PAUSED.
- Water Temp was due and was HELD by the global control.
- 0 executed; the shadow lane did not run.
- The status published operations {PAUSED: 8}.

**`/control/engineeringStatusV1` (1.3.0 @ `c7b544844298`, Cortex 2.7.0 @ ebc7fb9):**
- `executionControl.state` PAUSED.
- All 8 Brains: runtime READY, internal operation **PAUSED**, with their last-execution evidence kept.
- Science shown independently.
- Converted for `ops-check --status`: **0 findings**.

**Execution history since the pause (02:36Z):**
- Cloud Scheduler fires: **0**.
- Brain worker executions: **0** (`wind-hourly`, `lake-brain`, `water-temp-brain`, `water-clarity-brain` and the six pipeline jobs).
- Orchestrator executions: only the two manual bounded cycles above.

**Live state:**

| Check | Result |
|---|---|
| Schedulers | all 9 PAUSED; `check_preproduction_schedules.py` passes |
| Scores | Brain score values unchanged; Engine 7.2 |
| Rules | sha256 `72f321bd…`, unchanged |
| Sector Ops and customer applications | unchanged |

## 6. Cloud costs while paused (list prices, approximate)

**Stopped:** all Brain execution charges. Before the pause:
- `wind-hourly` ran hourly (about $4/month);
- `brain-orchestrator` ran hourly (about $1/month), plus the pilot jobs it started;
- the Lake ledger ran daily.

**Remaining:**

| Item | ≈ USD / month |
|---|---|
| Artifact Registry (~5.7 GB) | ~0.5 |
| Cloud Storage (~38 GB, mostly the 29 GB Clarity research archive and the 7 GB research backup) | ~0.8 |
| Cloud Scheduler (9 paused jobs, beyond the free allowance) | ~0.6 |

Not estimated here: Cloud Logging retention and RTDB storage/bandwidth. Customer-serving Cloud Run services and Functions are unrelated to Brain execution and unchanged.

## 7. Closeout

- The worktree `Worktrees/Sector_Engine/central-scheduling` is registered COMPLETED and removed after merge.
- No research data was touched.
- Merged branches remain on the remote (deletion is gated).
