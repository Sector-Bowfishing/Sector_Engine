# Sector Brain Orchestrator — design v1 (foundation)

**Owner:** Sector Engine / Brain Platform. **Status:** DESIGN + planning core on `main`; **not deployed**
(deploying it would create new recurring cloud work — needs Michael's approval). Consolidation Phase 11.

## The question it answers
"Which Brain needs to run next, after what, and why?" — and nothing else. Brains keep knowing what makes
them stale (`stalenessModel`, `staleAfterHours`, `plan()`), what they depend on (`dependsOn`), and when
they would look again (`schedule.nextCheckAt`). The Orchestrator turns those self-descriptions into one
ordered, de-duplicated plan and (later) executes it. Page views never trigger recomputation.

## Inputs (what every Brain must publish — contract §9/§11)
| Field | Where | Meaning |
|---|---|---|
| `schedule{cadence, jobId?, nextCheckAt?, running?, lockedUntil?}` | `/brains/{id}` | cadence hint, single-flight state |
| `stalenessModel` `TIME|VERSION|FINGERPRINT` + `staleAfterHours` (TIME) | `/brains/{id}` | how the published state goes stale |
| `dependsOn[]` | `/brains/{id}` | upstream brains that should run first |
| `lastSuccessfulRun`, `lastError` | `/brains/{id}` | |
| `descriptor{components{status, inputs, staleness, recomputeWhen}}` (or legacy `orchestration`) | `/brains/{id}` | human-readable source cadence and recompute reasons |
| `/health/brains/{id}{status, errorCount, lastRun}` | | retry input |
| the brain's own `plan()` verdict (`--plan` CLI on each job) | | VERSION/FINGERPRINT brains only know this themselves |

`sector_brain_platform.descriptor_gaps(registries)` lists what a registry still lacks. Gap fill for the
six Brains is part of Phase 11 (schedule, stalenessModel, dependsOn on every registry).

## Planning core — `sector_brain_platform/orchestrator.py` (pure, tested)
`plan(brains, health, now, brain_plans, targets)` →
```jsonc
{ "generatedAt": "…", "order": ["lake-brain", "…", "sector-intelligence"],
  "runs": [ {"brainId": "lake-brain", "action": "RUN", "reasons": ["published state 5.1 h old >= staleAfterHours 3"], "after": [], "priority": 1, "lakes": ["Guntersville|AL"]?} ],
  "waiting": [ {"brainId": "wind", "action": "WAIT", "reasons": ["already running (single-flight)"]} ],
  "skipped": [ {"brainId": "biological-state", "action": "SKIP", "reasons": ["brain plan: nothing to do"]} ] }
```
Guarantees:
- **Dependency order:** topological over `dependsOn` (cycle → error). `after[]` names the runs a run waits for.
- **Deduplication:** one entry per brain per plan.
- **Single-flight:** `schedule.running` or `lockedUntil > now` → WAIT; never started twice.
- **Conditional refresh:** TIME brains run when `now − lastSuccessfulRun ≥ staleAfterHours`, never run, or
  `nextCheckAt` reached; VERSION/FINGERPRINT brains run only when their own `plan()` says PUBLISH.
- **Retries:** after `health FAILED`, backoff 5 / 15 / 45 min by `errorCount`; after 3 failures SKIP with
  "needs attention" (a human, not a loop).
- **Failure isolation:** a FAILED upstream never blocks a downstream run; the run is flagged
  `degradedUpstream` so the brain publishes degraded inputs honestly (Intelligence already does).
- **Lake targeting:** `targets[]` passes through to every run (a brain may refresh a subset).

## Executor — `jobs/brain-orchestrator` (built 2026-10-13, cost-efficient scheduling work)
A single scale-to-zero Cloud Run job `brain-orchestrator` (1 vCPU / 512 Mi, single task, usually < 1 min) on an
**hourly** Cloud Scheduler wake-up (`50 * * * *` UTC — after `wind-hourly` at :05 and the TVA archive at :20).
Each cycle (`orchestrate.py`):

1. **Sync `/jobs`** from Cloud Scheduler + Cloud Run (`docs/brains/JOBS_CONTRACT.md`); only changed records are written.
2. **Plan** with `orchestrator.plan()`. TIME brains (Lake, Water Temp) from their published `staleAfterHours` /
   `lastSuccessfulRun`; VERSION / FINGERPRINT brains (Biological, Intelligence) from their own `run.py --plan`.
   Single-flight comes from the real world: a running Cloud Run execution of the brain's job, or the lock this job
   wrote when it started one (`/control/orchestrator/locks`, 15 min).
3. **Execute** only `runs`: `lake-brain` / `water-temp-brain` through the Jobs API (`jobs.run` with arg overrides —
   pilot scope for Lake, fleet for Water Temp); `biological-brain` / `sector-intelligence-brain` **in-process**
   (`run.py --write`, their plan() decides). A run whose `after[]` upstream was *started asynchronously this cycle*
   waits for the next wake-up (Intelligence re-evaluates after Lake / Water Temp have published). **Wind** keeps its
   own cron and **Water Clarity** stays manual: both are planned for visibility and never started here.
4. **Scores / control** (`score_brains.py --write --if-changed`) only when a Brain's `lastSuccessfulRun` changed
   since the last cycle, something published this cycle, or a job record changed — never on a blind timer.
5. **Record** `/control/orchestrator` (plan, executed, deferred, locks, lastSeen).

Identity: service account `brain-writer` (shared with the two Brain jobs): `firebasedatabase.admin`,
`run.viewer`, `cloudscheduler.viewer`, `run.invoker` on `lake-brain` and `water-temp-brain` only,
`storage.objectViewer` on the biology bundle bucket. Per-brain crons for Lake / Water Temp were never created;
`wind-hourly` stays until the executor has proven itself across a few days (then it is the next candidate).
