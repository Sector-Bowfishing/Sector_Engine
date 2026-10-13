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

## Executor (not built)
A single Cloud Run job `brain-orchestrator` on a coarse cron (e.g. every 15 min) that: reads
`/brains`, `/health/brains`; asks each Python brain's `--plan` (or reads the published `fingerprint`);
calls `plan()`; executes `runs` in `priority` order honoring `after[]` by invoking the existing per-brain
jobs (Cloud Run Jobs API) with `schedule.running=true` / `lockedUntil` written first and cleared after;
records the plan under `/control/orchestrator/lastPlan` and runs under `/health/jobs/brain-orchestrator`.
Per-brain crons (`wind-hourly` etc.) stay until the executor proves itself; then only the Orchestrator
schedules Brains and the per-brain cron architecture is retired.

**Stop condition:** creating the orchestrator job/scheduler is new recurring cloud work — Michael approves.
