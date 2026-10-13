# Current maturity vs future potential (kept strictly separate)

**Rule from the brief:** Depth and Vegetation are under parallel research and are not production Brains. They count **zero** toward current capability. Future potential is a ceiling conditional on named upstream work; it is not a forecast and is never added to the current score.

## 1. Side by side
| | CURRENT INPUT INTELLIGENCE | FUTURE POTENTIAL |
|---|---|---|
| Published score | 4.8 (plumbing rubric) | n/a |
| Research score | **3.2** (3.0 ± 1; 2.7 if unreleased FishIntel is ignored) | 7.8 uncapped, **7.0 displayed** (validation <8 cap) |
| Inputs actually used | customer path: weather, nearest gauges, MRMS rain, astronomy, spawn table; pilot: 5 Brain states for 5 lakes, no judgment | + Depth, + Vegetation, + Biological response bands, + scheduled Lake/Temp, + per-bank Wind everywhere, + arm clarity |
| Species | spawn headline (Engine); 5 species on one lake (unreleased, local tables) | species-first from Biological bands |
| Where | one query point; Guntersville segments (unreleased) | zones on pilot lakes with measured/modeled depth and vegetation |
| When | tonight + 6 nights, persistence unlabelled | strip inside each Brain's horizon with trend and driver |
| Confidence | 100 − fixed deductions; ignores staleness of most inputs | weakest-link, calibrated once paired data exists |
| Validation | none | PARTIAL (≥30 blind pairs per stratum) |

## 2. Current-input design ceiling (what the design can earn *without* any upstream improvement)
Design adopted on today's inputs: **4.5** (hypothetical). It stays under the 5.0 validation cap and is limited by: coverage 2 (Wind pilots 4 lakes, Biological rules for 1 species), where 4 (bank exposure on 4 lakes, everything else lake-level), validation 1. So even a perfect implementation of the synthesis, with no new upstream science, cannot make Intelligence a *validated, fleet-wide, area-level* system. What it *can* do immediately: stop the missing-data optimism, expose unknowns, make confidence honest, and make species/time/why structure available for the 4 wind pilot lakes.

## 3. What the future potential assumes (each is someone else's deliverable)
| Assumption | Owner | Evidence of progress today |
|---|---|---|
| Depth zone state with effective depth | Depth Brain (does not exist) | audit + IENC overlap for 34 lakes; one binary contour for one lake |
| Vegetation zone state | Vegetation Brain (does not exist; research folder empty) | only lake-level indirect indicators |
| Biological response bands for principal targets | Biological | knowledge median ≈1.0; rules for one species |
| Lake and Water Temp scheduled and fresher | Platform / Orchestrator | both STALE on 5/5 pilots; orchestrator is planning-only |
| Wind per-bank exposure validated and extended | Wind | 4 lakes; field validation absent; H2 sealed to 2027-01-01 |
| Clarity R3.1 approved/deployed | Michael | certified candidate, undeployed |
| Paired blind-area study | Intelligence + testers | design and power done; no data |

If **none** of these arrive, future potential = current. If **only** Biological bands + scheduling arrive, the realistic reach is ≈5.0 (validation-capped).

## 4. Interfaces so future inputs slot in without redesign
Depth and Vegetation enter through the same `Factor` record (`UPSTREAM_CONTRACTS` §0, §6, §7). The synthesis already treats a missing Depth/Vegetation as UNKNOWN: today every depth/vegetation-using species is capped at `WORTH_A_LOOK` and printed "depth not published". When the Brain arrives, the cap lifts by itself and no Intelligence code changes. That is the test of a good interface and it is covered by the prototype (a zone missing `vegetation` cannot be `START_HERE`; add the factor and it can).

## 5. Example of mixed-maturity inputs (the brief's scenario)
Depth modeled/low-confidence; Vegetation stale; Clarity excellent; Temp observed; Wind reliable. Prototype result: **WORTH_A_LOOK, confidence LOW**, weakest deciding factor depth, vegetation flagged STALE, "temperature is lake-level" caveat. The system neither inflates ("five good signals, so HIGH") nor discards the strong evidence: BEST lists all five.

## 6. What must never be done
Count Depth/Vegetation in the current score; infer depth from the mean-depth proxy and call it a zone; use satellite `grassPct` as a zone vegetation state; raise a dimension because a document describes it.
