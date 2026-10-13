# Vegetation Brain — Production readiness matrix (2026-10-14)

Policy: **overall ≥ 8.0 and every required/critical dimension ≥ 7.5.** Research maturity today **2.70** (not an official score). **Not production-ready; not close.** State: shadow foundation, `NOT_VALIDATED`.

## 1. Critical dimensions
| Dimension | Now | Required | Gap closes when |
|---|---:|---:|---|
| Source authority | 4.0 | 7.5 | ≥ 3 independent authoritative families *in use per region*, licences cleared (TVA/TPWD/WI/FWC answers) |
| Spatial accuracy | 2.5 | 7.5 | Lake geometry fixed (Okeechobee littoral, Toho duplicate); measured cell registration; shore-band policy validated |
| Presence accuracy | 2.5 | 7.5 | PARTIAL gate passed in ≥ 3 regions on fresh truth |
| Validation | 4.0 | 7.5 | ladder state PARTIAL (breadth documented) or VALIDATED |
| Confidence & provenance | 5.0 | 7.5 | confidence reliability measured |
Conditionally critical when exposed: density (1.0), seasonality (2.5).

## 2. Validation ladder (pre-registration §5)
| State | Status |
|---|---|
| NOT_VALIDATED | **current** |
| RESEARCH | entry condition met in the technical sense (production code scored on ≥ 2 independent sets) but the published state stays `NOT_VALIDATED` until the pre-registered owner review |
| CALIBRATION | not met: dev set cannot discriminate (1 effective positive lake) |
| PARTIAL | not met: (a) NOT_TESTABLE, (b) literal PASS only, (c) FAIL, (d) FAIL, (e) NOT_TESTABLE |
| VALIDATED | not met |

## 3. Pre-registered gates (v0.2, one-shot TEST)
| Gate | Verdict | Numbers |
|---|---|---|
| (a) cell P/R in ≥ 3 truth lakes with ≥ 30 positives | **NOT_TESTABLE** | TEST Snohomish lakes hold 0 interior positives; dev has 1 lake with 23 |
| (b) open-water FPR ≤ 2 % | PASS (literal, weak) | 0 of 203 known open-water cells; 55 % of cells UNKNOWN in V1 |
| (c) NLA AUC ≥ 0.80 and Spearman ≥ 0.50 | **FAIL** | AUC 0.72 (0.37–1.00), Spearman 0.22–0.24; 22 lakes, 9 regions |
| (d) negative controls ≤ 2 % | **FAIL** | Keystone Lake OK 11.3 %; Lake Buchanan unscored (all scenes bloom-ambiguous) |
| (e) F1 lower bound ≥ 0.65 | **NOT_TESTABLE** | no interior positive in TEST |
| Density gate / Seasonal gate | not passed | density not evaluated; seasonal beats calendar +38 but only +6 over most-common-state |

## 4. Rubric vs product — documented mismatches (proposal; not applied)
1. **Gate (c) measures the wrong thing for the V1 claim.** NLA stations are shoreline plots (191 of 467 within 10 m of the edge, 162 in 10–90 m); V1 claims are interior-only. A belt statistic over offshore cells compared with shoreline-plot cover is not co-located. Proposal: replace with a station-level, co-located comparison, or accept agency/FWC/TVA vegetation observations as **Level-1 provider truth** for pilot lakes.
2. **Presence accuracy asks for dense polygon truth that does not exist for reservoirs.** The product question is "where to look". Proposal: for lakes where an agency publishes vegetation (FWC, SFWMD littoral, TVA when obtained), **display the agency observation as-is** (Level 1: verify source/date/units) and use the satellite observer only as "Likely surface vegetation" evidence.
3. **Seasonal *state labels* may be unnecessary.** A bowfisher needs "last seen N days ago, typically present in this month". Proposal: publish observation age + lake-history frequency, and drop the five-state label until it earns a gate.
4. **Coverage counts observed lakes, not useful lakes.** Proposal: coverage = pilot/priority lakes with a current agency or accepted-pass observation.
5. **The 8.0/7.5 policy fits a continuously-observing Brain; V1 is an evidence layer.** Michael decides whether an "evidence-only" tier (SHADOW → CALIBRATION with no score) is acceptable for internal Ops visibility.
Rubric is unchanged pending Michael's approval.

## 5. Infrastructure readiness
| Item | Status |
|---|---|
| Platform contract (slot, schema, ownership) | dry-run conformant; no live writer by design |
| Orchestrator / `/jobs` | not registered (correct) |
| Scoring (`ALL_BRAINS`) | excluded; no scorer |
| Ops | `future:true`, copy overpromises (see Ops visibility gap) |
| Cost | event/fingerprint-driven design; per-scene read cost measured (≈7.6 MB for a 5 km window); share Clarity's reads before any schedule |
| Customer layer | none; none permitted |

## 6. Recommended product slice (needs Michael)
1. **Level 1 first:** agency vegetation observations for pilot lakes (FWC LTM/PAC-PVI, SFWMD littoral, TVA when received) displayed with source/date.
2. **Level 3, labelled:** satellite "Likely surface vegetation" with age and confidence, shadow-only until fresh-truth validation.
3. **Never:** submerged-observed, species, density percentages.
