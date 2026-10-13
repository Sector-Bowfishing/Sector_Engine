# Depth field validation - preregistration (FROZEN 2026-10-14, before any field data)

Frozen file: `jobs/depth-brain/depth_brain/data/field_validation_prereg.json`
SHA-256: `b73f528ceb01a8df834ef0e2c1db8c0745095899acdb7e39e8ca682476ff0fa0` (pinned in `depth_brain/field_validation.py`; `analyze()` refuses to run if the file changes; test `test_prereg_is_frozen_and_hash_pinned`).

Criteria (unchanged from the plan in `DEPTH_FIELD_VALIDATION_PLAN.md`; they may not be lowered after results are seen):

| Criterion | Threshold | Minimum sample |
|---|---|---|
| shift-vs-observed MAE | <= 0.5 ft | >= 20 pairs, >= 5 lakes |
| class accuracy (DRY / TOO_SHALLOW / SHOOTABLE / GOOD / DEEP) | >= 80% | >= 60 observations |
| DRY observed but predicted SHOOTABLE or GOOD | 0 occurrences | any |
| observations within 1 sigma | 68% +/- 15% (0.53 - 0.83) | any |

Class bins are measurement bins only (DRY <= 0 ft; TOO_SHALLOW < 1; SHOOTABLE 1 - <3; GOOD 3 - 5; DEEP > 5); they are not fish preference. Any criterion failing means effective depth is not field-validated. Excluded rows need a reason fixed before looking at errors and are reported.

## Observation CSV (one row per visit per flat)
`lake,flat,obsAt,observedDepthFt,poolFt,predictedDepthFt,sigmaFt[,excluded,excludeReason]` - `predictedDepthFt` and `sigmaFt` are taken from the Depth state generated at the time of the visit (record its `provenance.inputFingerprint`), using `d_pred = d0 + (P1 - P0)` from the reference visit.

## Status
Tooling and thresholds ready; **no field data collected**. Execution needs Michael / beta testers and sonar (blocker: FIELD VALIDATION).
