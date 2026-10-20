# Brain Operational Truth V1

Status: implemented on `feat/brain-operational-truth-v1` (2026-10-20). Answers the six Engine follow-ups raised by Sector Ops *Brain Dashboard Accuracy V2* (Ops PR #8).
Code: `jobs/brain_platform/sector_brain_platform/operational_truth.py` (pure). Callers: `control.brain_summary` / `control.overview` (scorer → `/control/overview`) and `control_state.build_control_state` (orchestrator → `/control/orchestratorV1`). Tests: `tests/test_operational_truth.py`, `tests/test_fish_capability_activation.py`, `Tests/SectorEngineTests/LakeBrainTests.swift`.

All fields below are **additive**. Existing fields keep their names and meaning, except where noted: `stale` was previously wrong (computed under a different limit, or `false` without any evidence).

## 1. One freshness policy, one verdict per Brain
- **Effective policy** = the Orchestrator manifest's `brains.{id}.freshness`. That is the operating cadence the Orchestrator schedules against.
  - The Brain's own registry rule (`staleAfterHours`, `stalenessModel`) is reported beside it as `declaredModel` / `declaredStaleAfterHours` whenever it differs. It is never dropped silently.
  - The manifest `note` explains the difference. For example, Lake Brain runs under a 26 h pre-production maintenance cadence, while its registry declares 3 h.
  - When the manifest has no entry, the registry rule applies (`policySource: BRAIN_REGISTRY`).
- This is **run freshness** of the Brain as a whole, which belongs to the control plane. Per-state evidence freshness stays with the owning Brain (`FRESHNESS_MODEL.md`), and the authority rule there is unchanged.

| model | verdict | evidence |
|---|---|---|
| TIME | FRESH / STALE by `lastSuccessfulRun` age vs `staleAfterHours`; UNKNOWN with no successful run | registry `lastSuccessfulRun` |
| VERSION | FRESH when the Brain's own `--plan` says SKIP (published version = newest canonical); STALE on PUBLISH; UNKNOWN with no plan this cycle | in-process Brain plan (orchestrator) |
| FINGERPRINT | FRESH when the current input fingerprint equals the one the Brain last processed; STALE when it differs; UNKNOWN when either is missing (manual runs record no processed fingerprint) | orchestrator decision context `last_in_fps` |

Missing evidence is **UNKNOWN, never FRESH**. `stale` is `true` / `false` / absent (UNKNOWN).

- **Both planes, same answer.** TIME is computed identically on both planes. VERSION and FINGERPRINT need the plan and the fingerprints, which only the orchestrator has. So `/control/overview` mirrors `/control/orchestratorV1/brains/{id}/freshness.{verdict,stale,reason}` (`mirroredFrom`), and is otherwise UNKNOWN.
- **Schedule state is separate.** A PAUSED scheduler stays `summary.scheduler.state: PAUSED`, and `scheduleClass` / `executionMode` are untouched. A STALE verdict stays STALE. Neither is used to soften the other.

`/control/orchestratorV1/brains/{id}.freshness` = `{staleAfterHours?, ageHours?, stale?, verdict, reason, model, policySource, declaredModel?, declaredStaleAfterHours?}`.

`/control/overview/brains/{id}`: `stale`, `staleReason`, `staleAfterHours` and `stalenessModel` now follow the effective policy. Added: `freshness` = `{verdict, stale, reason, model, policySource, ageHours, staleAfterHours?, mirroredFrom?, declared…?, note?}`.

## 2. Why a Brain is not HEALTHY: `healthReasons`
`{basis, reasons[]}` is present only when health is WARNING, DEGRADED or FAILED. Basis, in order:
1. **`BRAIN_REPORTED`**: the Brain's own `health/brains/{id}.reasons`. Lake Brain now writes them (Swift `LakeBrainRunner.healthReasons`), one per lake that is unavailable, stale, or on a fallback source, plus "publish failed" / "no lakes evaluated".
2. **`DERIVED_FROM_PUBLISHED_FACTS`**: built from that same Brain's own sources (`/sources` filtered by `ownerBrainId`, health from `/health/sources`) with bad health, plus its `staleLakeCount` and `latestError`.
3. **`UNEXPLAINED`**: says so explicitly. It never invents a cause.

The health word itself is never changed.

## 3. Lifecycle: `status` vs `legacyStatus`
In `/control/overview`, `status` = the canonical lifecycle from the manifest. The Brain's own registry word is kept as `legacyStatus` when it differs (Water Clarity: `CALIBRATION` with `legacyStatus: BETA`). `/control/orchestratorV1` already published `lifecycle` + `legacyStatus`, and is unchanged. Without a manifest entry, `status` remains the registry word.

## 4. Four timestamps, four questions
| field | meaning | source |
|---|---|---|
| `lastExecution {at, status, executionId?}` | the last attempt, any outcome | execution ledger (orchestrator) / `health/brains.lastRun` |
| `lastSuccessfulRun` (`lastRun` kept as an alias on orchestratorV1) | the last run that finished successfully | registry |
| `lastDataUpdate {at, basis}` | the newest data the Brain actually published | `NEWEST_LAKE_STATE`: newest `lastUpdatedAt`/`generatedAt` in that Brain's `/lakeFleet` slot. `VERSION_PUBLISH_RUN`: the run that published the current version, with `version` |
| `lastScoreEvaluation` | when the scorer last evaluated the score | `/scores/{id}.scoreUpdatedAt` |

The orchestrator plane does not read `/lakeFleet` or `/sources`. It copies `lastDataUpdate` and `healthReasons` from `/control/overview/brains`, read in `load_world`. Without that read it falls back to health-only reasons and omits `lastDataUpdate`.

## 5. Lake coverage by meaning (`coverage` on `/control/overview`)
- `internalPilotLakes`: the length of `responsibilities.biologicalState.pilotLakes`. Internal evaluation only; nothing is published for these lakes.
- `publishedLakes`: `supportedLakeCount`.
- `customerEnabledLakes`: 0 when Sector Intelligence declares `consumedByCustomerPath: false` for the Brain; equal to `publishedLakes` when it is `true`; absent otherwise.

Counts only. No lake ids or species presence are added to the control plane.

## 6. Fish capability activation prerequisites
See `../scoring/FISH_CAPABILITY_ACTIVATION.md`.

## Ownership
- Unchanged:
  - The scorer writes `/control/overview` and `/scores`.
  - The orchestrator writes `/control/orchestratorV1`.
  - Brains write `/health/brains/{id}` and their own registry.
  - The Publisher's paths are untouched.
- No schedule is created or changed. Lake Brain's `reasons` field is additive in `BrainHealthRecord` (an optional key; old readers ignore it).
