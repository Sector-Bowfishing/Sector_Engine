# Execution Model

Answers: **why does a Brain run, and what makes a run unnecessary?** A Brain does not get a cron merely because it exists.

## 1. Execution types (`executionType`, closed)
| Type | Meaning | Trigger |
|---|---|---|
| `PROVIDER_INGESTION` | the provider's data changes on a cadence the Brain must follow | cadence of the provider (Wind: hourly model cycle; TVA archive hourly) |
| `DEPENDENCY_DRIVEN` | output is a function of other Brains/state | upstream `stateVersion`/fingerprint changed (Depth ← Lake; Intelligence ← specialists) |
| `PROSPECTIVE_VALIDATION` | timed snapshots *are* the evidence | the schedule is the experiment (Lake prediction ledger) |
| `MAINTENANCE` | cheap health/housekeeping | infrequent, bounded-cost |
| `MANUAL_SHADOW` | owner-run research/shadow | human |

Do not confuse with `/jobs/{id}.executionMode` (`SCHEDULED | MANUAL | EVENT_DRIVEN | DISABLED`) — that describes *how a job record is triggered*; `executionType` describes *why the Brain runs*. A `DEPENDENCY_DRIVEN` Brain typically has `executionMode: EVENT_DRIVEN`.

## 2. Staleness vs execution
The existing `stalenessModel` (`TIME | VERSION | FINGERPRINT`) stays: it says how the *published state* goes stale. `executionType` says why a *run* happens. TIME → usually PROVIDER_INGESTION or a documented time-invalidation; VERSION/FINGERPRINT → DEPENDENCY_DRIVEN.

## 3. When a recurring schedule survives
Only if at least one is true and written in the Brain Spec (`SCHEDULE_REASONS` in code):
- **A.** the provider changes on cadence;
- **B.** prospective evidence needs timed snapshots;
- **C.** state becomes invalid purely from elapsed time;
- **D.** cheap maintenance / health requires it.
Otherwise the Brain is fingerprint/dependency driven and the orchestrator decides.

## 4. Input fingerprint standard
`fingerprint.fingerprint(material) → 16-hex`. **Material** inputs (a Brain picks its own ingredients; mechanics are shared): provider observation timestamp, upstream `stateVersion`, `rulesVersion`, `modelVersion`, `geometryVersion`, reference-data version, evidence-bundle version. **Excluded (volatile, non-semantic):** `generatedAt, ageHours, inputAgeHours, requestedAt, evaluatedAt, updatedAt, scoreUpdatedAt, rolledUpAt, summarizedAt, syncedAt, fetchedAt, lastRun, nextCheckAt, freshUntil, refreshReason, durationMs, runId, executionId` (at any depth). Key order and float noise (<1e-9) do not matter; `0` ≠ absent ≠ `null`.
`fingerprint.decide(material, previous)` → `RUN` (first run or material change) or `SKIP` ("no material input changed"). A Brain stores the **planned** fingerprint (the one computed *before* any upgrade of its own view), never a recomputation after (the Intelligence republish-every-cycle bug, fixed in `7a563c18`).

## 5. The orchestrator's role
Coordinates: freshness checks, dependency changes, safe publication, recovery, stale detection, control-plane updates. It does not run a Brain because an hour passed. Today (deployed, gen 8, `5fd727ef`): hourly `50 * * * *` UTC wake-up → sync `/jobs` → plan (TIME Brains from `staleAfterHours`, VERSION/FINGERPRINT Brains from their own `--plan`) → start only what the plan says → publish scores/control only if a Brain's `lastSuccessfulRun` changed → record `/control/orchestrator`. That backstop is kept. Wind (`wind-hourly` :05) and Clarity (manual) are reported, not started.

## 6. Customer hot-path rule (hard)
A customer page view must not trigger heavy Brain compute. Runtime = *read compact canonical state → synthesise → return*. A customer request must never require: large research datasets, raw satellite imagery, national CSV archives, fleet recomputation, provider fan-out, a validation experiment, or a full Brain re-run. Enforced by `tests/test_architecture.py::test_customer_api_never_references_brain_compute_or_research_data` (static scan of `Sources/SectorEngine/API` for job-start URLs, score/orchestrator scripts, research paths, CSV, research buckets, subprocesses). It is a tripwire, not a proof; code review still applies.

## 7. Ops hot-path rule
Opening Sector Ops is not an Engine event: it consumes cached control state, registry state and durable scores. Load/reload/navigation/multi-tab/focus/reconnect → RTDB reads only. Ops has no credentials that can start a job (rules deny client writes; `run.invoker` is held only by the `brain-writer` service account).

## 8. Cost model (reviewed 2026-10-14, live state)
| Surface | Today | Assessment |
|---|---|---|
| Cloud Run | `brain-orchestrator` 1 vCPU/512 Mi, ≤30 min cap, ~8 s typical, scale-to-zero | ok |
| Scheduler | 4 enabled jobs (lake-surface-dispatch daily, tva-archive hourly, wind-hourly hourly, orchestrator hourly); 4 paused | ok; each remaining recurring job maps to reason A or D |
| RTDB writes | score publish skips identical content (`_content`, RTDB-empty-container fix); `--if-changed` control publish | **Observation:** the 03:51Z cycle rewrote 627 of 628 control paths because Wind updates every lake's `lastUpdatedAt` hourly; ~620 small writes/hour. Candidate saving: stop rewriting fleet rollups for `lastUpdatedAt`-only drift. Needs Ops freshness decision → `DECISION_QUEUE` D-4 |
| Artifact storage | frozen artifacts in git; research archives in GCS buckets | no per-request reads |
| Egress | no customer-path reads of research data (tripwire test) | ok |
No recurring work is added by Model v1: nothing here registers a scheduler job or a Cloud Run job.

## 9. Zero-concurrency lesson (shared design guidance)
A Lake runner once crashed because a worker count was computed to **0** (`ThreadPoolExecutor(max_workers=0)` raises). Any runner that derives parallelism from config, data size or an empty work list must clamp: `model_v1.bounded_workers(requested, n_items, cap)` → `1 ≤ w ≤ cap`, and never more workers than items. Water Temperature may contain the same pattern; the platform lane **did not edit Water Temp code** — see `BRAIN_MIGRATION_CHECKLIST.md` §4 for the audit request. Also: an empty work list must be a successful no-op, not an error and not a "0 changed = healthy" claim without checking `attempted > 0`.
