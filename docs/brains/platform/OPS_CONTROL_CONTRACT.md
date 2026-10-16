# Ops Control Contract (Model v1 layer)

Extends `docs/brains/OPS_CONTROL_PLANE_CONTRACT.md` (`control-plane-v1`, which remains authoritative for what is published today). This document defines the **compact common Brain control summary** (`brain-control-v1`) that all Brains would share, and the rules around it. Implementation (pure, not wired to publish): `control_contract.py`.

## 1. Shape
```jsonc
// control.brains[brainId]  (v1 names; every field except brainId + lifecycle is OPTIONAL — omit what you cannot honestly fill)
{ "brainId": "wind", "controlModel": "brain-control-v1",
  "lifecycle": "CALIBRATION", "legacyLifecycle": "CALIBRATION",
  "health": "HEALTHY",
  "canonicalScore": 3.3, "underlyingScore": 3.27, "displayedScore": 3.3, "scoreStatus": "COMPUTED",
  "claimMaturity": {"NOT_VALIDATED": 3, "VALIDATED": 1},
  "criticalGates": [{"gate":"fieldValidation","why":"…","cap":6.0}],
  "coverage": {…}, "validation": {"status":"NOT_VALIDATED","ref":"/validation/wind"},
  "freshness": {"stale": false, "evidenceStale": false},
  "stateVersion": "…", "lastMeaningfulUpdate": "…", "executionType": "PROVIDER_INGESTION",
  "blockers": [], "nextExpectedUpdate": "…", "customerReadiness": "INTERNAL",
  "dependencies": [{"id":"lake-brain","status":"SATISFIED"}] }
```
Rules enforced by `validate_control`: required `brainId` + v1 `lifecycle`; **no bare `score`**; `displayedScore ≤ canonicalScore` (gates cap, never inflate); closed `scoreStatus`/`customerReadiness`.

## 2. Mapping from today's control summary (`from_control_summary`)
| Today | v1 |
|---|---|
| `status` | `lifecycle` (mapped) + `legacyLifecycle` (+ `lifecycleMappingAmbiguous` when lossy) |
| `score.value` | `canonicalScore` and `displayedScore` |
| `score.uncapped` | `underlyingScore` |
| `score.basis` | `scoreStatus` (COMPUTED/FROZEN) |
| `lastSuccessfulRun` | `lastMeaningfulUpdate` (see §4) |
| `version` | `stateVersion`, `coverage/validation/blockers/health` | same names, copied only when non-empty |
Nothing is defaulted: an unscored Brain (Depth, Vegetation today) simply has no score fields.

## 3. Rollout (additive, Ops-safe)
1. Engine publishes the v1 fields **beside** the current ones under `control.brains[id]` (new keys only) — requires a shared-orchestrator deploy (DECISION D-1).
2. Ops adopts the v1 names behind its existing "unknown renders as unknown" rule, falling back to the old fields.
3. Only after Ops no longer reads the old fields is anything retired — a later, separate decision.
Until step 1, nothing Ops sees changes.

## 4. `lastMeaningfulUpdate` vs `lastSuccessfulRun`
`lastSuccessfulRun` moves every run, including no-ops. `lastMeaningfulUpdate` moves only when the published **content** changed (fingerprint/`_content` differs). Ops should show the latter for "last changed" and the former for "last checked". Not published yet; needs each Brain to expose a content fingerprint (`EXECUTION_MODEL.md` §4).

## 5. Publication is content-aware (preserved)
Scores: `plan_writes` rewrites a node only when content differs (timestamps and RTDB-dropped empties ignored); `score.changed` events only when displayed value/version/basis change. Control: `--if-changed` + `_stable` ignore volatile timestamps; the overview is rewritten when any sibling changes. Model v1 adds the stale guard in front of both.

## 6. Hot-path rules for Ops
Ops reads `/control/*`, `/brains/*`, `/scores/*`. It computes no score, staleness, readiness or fleet count. Load, reload, navigation, multiple tabs, focus and reconnect cause RTDB reads only — no function call, job start or Engine API call for Brain state. Ops has no credential or UI path that starts a Brain. (Verification of Engine-API-calls-on-load = 0 needs an authenticated Ops session — `DECISION_QUEUE` D-6.)

## 7. Held scores are visible
When the publisher holds a stale proposal, the run report carries `held[]`. Publishing that into `control/orchestrator.scores` (so Ops can show "Wind score held: stale artifact") is a small additive change bundled with D-1; until then it is in the job log and the dry-run report.
