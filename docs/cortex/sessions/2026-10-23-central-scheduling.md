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

## 4. Deployment and production verification

Appended after merge.
