# `depth-brain-score-v1` - PROPOSAL ONLY (Depth has no official score; none is published)

Implementation of the proposal (not wired, tested): `jobs/depth-brain/depth_brain/score_v1_proposal.py`, `tests/test_score_proposal.py`. It reuses the platform scorer primitives (`dim`, `finish`, `ladder`: weights sum to 100, UNKNOWN excluded, gates cap and never add). **It is not imported by the publisher, not registered with the scorer, and cannot write `/scores/depth`.** Ratifying it, naming critical dimensions and adding `depth` to the platform scorer are Michael's decisions.

## Principle

Reward what helps a bowfisher know how the water they care about has moved and what that does to known shallow water, with honest confidence. **Do not reward** deep-basin bathymetry, academic completeness, GLOBathy coverage, or false precision. There is deliberately no dimension for any of them (a test fails if one appears, and extra "GLOBathy"/"deep basin" facts are ignored by the function).

## Dimensions (weight; denominator = the addressable fleet: directory lakes with `poolBasis = fullPool`, 414 today)

| Dimension | W | Value | Rationale |
|---|---|---|---|
| referencePool | 8 | coverage ladder of addressable lakes with a high/medium pool figure | the shift is only as good as the reference |
| datumCorrectness | 17 | ladder of (verified + 0.5 x inferred operator-system) over addressable | the dominant failure mode; inferred counts half; any datum conflict triggers a gate |
| effectiveDepthCorrectness | 15 | UNKNOWN until preregistered field/event validation exists; then 8.0 (pass) / 3.0 (fail) | cannot be scored from arithmetic alone |
| contourQuality | 10 | ladder of tier A/B contour lakes licensed for customer-derived numbers | measured contours where they exist, only if usable |
| shallowZoneSupport | 10 | ladder of tier A/B lakes with a verified survey reference pool (effective zones eligible) | whether "known flat now shallower/dry" can be answered with real contours |
| fleetCoverage | 15 | ladder of addressable lakes with a LIVE Depth state | defensible but un-served lakes earn nothing |
| validation | 10 | NOT_VALIDATED 1 / PARTIAL 5 / VALIDATED 9 | |
| provenance | 5 | tier, datum assessment, sources, fingerprint, limitations carried on every state | tested in code |
| freshness | 5 | share of live states not evidence-stale | |
| operationalReliability | 5 | orchestration registered + healthy runs | 0 until a job exists |

## Gates (cap, never add)

| Gate | Cap | Fires when |
|---|---|---|
| coverage | 3.0 | live Depth states < 10% of the addressable fleet |
| validation | 5.0 | validation != VALIDATED |
| fieldTruth | 6.0 | field validation != PASSED |
| orchestration | 6.0 | no scheduled/orchestrated job |
| datumConflict | 2.0 | any lake with conflicting datum evidence |
| health | 2.0 | brain health FAILED / UNKNOWN |

## What it would say today (not published)

Facts: 414 addressable, 5 live states, 92 defensible shifts (76 verified datum + 16 inferred), 103 tier A/B (59 licensed), 0 verified survey reference pools, NOT_VALIDATED, no field validation, no orchestration. Result: **uncapped 3.2, displayed 3.0** (coverage gate), `effectiveDepthCorrectness` UNKNOWN (not faked). If all 92 defensible lakes were live: 3.5 - still capped by validation/fieldTruth/orchestration. The score would only move materially with live coverage, validation and datum - exactly the work that matters.

## Proposed critical dimensions (for the 8.0 / 7.5 policy; Michael ratifies)

`datumCorrectness`, `effectiveDepthCorrectness`, `fleetCoverage`, `validation`. Not critical: `contourQuality` / `shallowZoneSupport` (shift-only Depth is useful on reservoirs without contours; contours are an enhancement), referencePool (a gate on datum in practice), provenance, freshness (hygiene), operationalReliability (required for Production by the lifecycle, enforced by the orchestration gate rather than a 7.5 floor).

## Relationship to the research rubric

The research rubric (`docs/depth-brain-research`, currently 4.5) judged evidence quality for a decision; v1 would score the **running Brain**. Both stay separate: research maturity is reported as `research.maturity` with `official:false`; v1 (if approved) would publish at `/scores/depth` through the platform scorer.

## Open decisions for Michael

1. Denominator: addressable (pool-basis) lakes vs all 621 vs demand-weighted lakes.
2. Whether inferred operator-system datum (TVA) counts 0.5 (proposed), 0.75 or 0.
3. Whether `shallowZoneSupport` should be critical once contour licensing is resolved.
4. Whether to register Depth as a shadow Brain in the platform scorer before any live write.
