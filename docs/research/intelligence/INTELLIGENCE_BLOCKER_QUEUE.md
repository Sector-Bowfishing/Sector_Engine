# Blocker queue

Ordered by how much each blocks a trustworthy WHERE / WHEN / WHAT / WHY / HOW SURE. **Owner** says whose work it is; items owned elsewhere are listed so they are visible, not so Intelligence does them.

## Intelligence-owned (can be worked now)
| # | Blocker | Evidence | Next action | Needs approval |
|---|---|---|---|---|
| I1 | No combination rule for Brain states: the Brain that reads all specialists judges nothing | audit §1, §3 | Implement the ordinal synthesis as a pilot module that emits `rating/confidence/explanation` into the pilot evaluation, still `consumesThisEvaluation: false` | review of this design |
| I2 | Missing data raises the score; cliffs of 15–46 points; confidence blind to most inputs | probe E1–E5 | Adopt rules R1–R9 in the pilot; keep production Conditions Score unchanged | none for the pilot; production change = customer approval |
| I3 | No validation of any kind | validation doc | Stage 2: blind expert ranking on Guntersville/Wheeler (days of work); pilot 20 pairs | Michael + testers |
| I4 | Published rubric rewards plumbing | audit A1 | Propose `r2` (synthesisQuality 0 once evaluations exist; add `answersABowfisher`) | platform owner |
| I5 | Persistence in `nights[]` unlabelled; tonight/headline cache skew | audit §5.3 | write the `HELD` labelling spec; add a parity test across caches | customer-visible if shipped |
| I6 | Intelligence owns weather/sky/fog/warnings with no Brain | tonight §5 | document the adapter provenance and version the gate thresholds | none |
| I7 | Duplicate thresholds across Engine/FishIntel/Wind | audit §5.1 | produce a single threshold inventory; replace by Brain-published bands as they arrive | none |

## Upstream-owned (Intelligence is blocked)
| # | Blocker | Owner | Effect on Intelligence |
|---|---|---|---|
| U1 | No per-species response bands (only common carp rules); knowledge median ≈1.0; 3 conflicting spawn tables | Biological | species-first impossible for all but one species; **largest single blocker** |
| U2 | Lake Brain and Water Temp unscheduled, STALE on 5/5 pilots; orchestrator planning-only | Platform | every pilot answer degraded; beta readiness 5 × NOT_READY |
| U3 | Depth Brain does not exist (one binary contour, one lake) | Depth research | no shallow/effective-depth answers; zone ranking impossible |
| U4 | Vegetation Brain does not exist | Vegetation research | no cover/obstruction answers |
| U5 | Wind: per-bank exposure only on 4 lakes, not field-validated; windy-hour POD 0.0; H2 sealed to 2027-01-01 | Wind | bank choice unavailable elsewhere; cannot assert "wind will build" |
| U6 | Water Temp is lake-wide, un-confidence-labelled, protected truth short, no shallow product | Water Temp | cannot tell shallow-flat from main-lake temperature |
| U7 | Clarity R3.1 undeployed; lake-level only | Clarity/Michael | usable but not zone-specific |
| U8 | Brains publish no calibrated confidence | all | confidence stays an ordinal evidence label |
| U9 | Lake Brain presence only for 5 lakes | Lake Brain | no fleet species list |
| U10 | Policy/legal gate undecided (D5); TVA midnight rows (D8) | Michael | gate source missing; Lake and Intelligence disagree on timing |

## Decisions needed from Michael
1. Is `intelligence-decision-readiness-r1` accepted as the working research score (the published 4.8 stays)?
2. Approve building the synthesis as a pilot module (no customer change) after review of the prototype?
3. Approve a blind expert-ranking exercise on the pilot lakes, and a trusted-tester roster for the paired study (spring 2027 season)?
4. Decide whether on-device FishIntel stays unreleased until its tables are reconciled with Biological (private-repo risk: no entitlement gate).
5. D5 (policy gate) and D8 (TVA timing) remain open and affect gate and timing inputs.

## Suggested first three (by value / effort)
1. I1+I2 as a pilot module with parity tests (days; no customer change).
2. U1 request to Biological: bands for 3 targets, one table.
3. I3 blind expert ranking (no software; produces the first outcome-related data point).
