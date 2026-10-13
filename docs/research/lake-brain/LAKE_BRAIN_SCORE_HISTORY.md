# Lake Brain — score history (research re-scoring, 2026-10-13)

**The published Lake Brain score is still 3.0 / 10 and was not touched.** Every number below after S0 is a *research score*: the **unmodified** rubric
(`lake-brain-score-v1`, `jobs/brain_platform/sector_brain_platform/scoring.py::score_lake`, via `research/lake-brain/tools/research_score.py`) run over the
facts the research produced. A research score is **conditional**: it holds only if (a) the machine-verified bindings are accepted as REVIEWED (the rubric
`cannotCount` unreviewed candidates), (b) the Engine can read each binding's provider (today it reads TVA, CWMS and USGS), and (c) the history and plan/flood
evidence is adopted into the profiles. Nothing was written to production.

## Score by step (NOT_VALIDATED, the status today)

| Step | Evidence added | Profiled | Σ uncapped | Displayed (gates applied) | Notes |
|---|---|---|---|---|---|
| **S0 published baseline** | – | 5 (0.8 %) | 4.3 | **3.0** | coverage gate (< 10 %) caps at 3.0; validation gate caps at 5.0 |
| **S1 deep TVA history** | NWS RVDHUN 2005–21 + NWS/TVA HADS 2022-10→ + CWMS LRD: 16–18 complete years for the 4 TVA pilots (recounted: ≥ 329 days/yr; HADS = TVA archive to 0.00 ft) | 5 | **6.3** | 3.0 | +2.0 uncapped; invisible while the coverage gate holds |
| **S2 machine-verified fleet bindings** | binding-review-v1 R1–R9 on 621 lakes: 258 core | 258 (41.5 %) | 5.9 | **5.0** | coverage ladder 1 → 5 points lifts the gate; **uncapped falls** versus S1 because the new lakes dilute operator-plan, history and flood shares |
| **S3 history extension + verified plan/flood** | IEM HADS archive recovers 34 NWS-relay lakes (5–15 y), 14 more lakes from USGS/CWMS/TWDB/CO-OPS; CWMS levels + Access2Water + TVA guide joined with verified matches | 258 | 6.7 | 5.0 | history share 0.80 → 0.94; plan 0.19 → 0.46; flood 0.32 → 0.61 (independently recounted) |
| **S4 wave-2 gap closing, strict v1 only (FINAL, primary)** | +15 lakes bound under *unchanged* binding-review-v1 after fixing a wave-1 probe bug (14 lakes had been mis-classified stage-only) and adding sources (USGS scan, regional scouts); new lakes get **no** plan/flood credit. Excluded from the primary figure: Clinton Lake (its row relies on a v1.1 rule) and 5 lakes whose only source is an undocumented operator web endpoint (NIPSCO, NJ Water Supply, Duke, Wisconsin Public Service, Alliant; terms unreviewed) | **273 (44.0 %)** | **6.6** | **5.0** | 50 % ladder step (7 pts) **not** reached on strict rules |

### Sensitivities (all NOT_VALIDATED → displayed 5.0)
| Variant | Profiled | Σ uncapped |
|---|---|---|
| T2: + labelled v1.1 rules (written after seeing failures) | 299 (48.1 %) | 6.5 |
| T3: + `R7h` history-envelope promotion of 90 flagged lakes (post-hoc; error rate unmeasured) | 389 (62.6 %) | 6.8 (coverage 7 pts, but quality shares dilute) |
| Strict + 57 wave-1 flagged lakes accepted (wave 1) | 315 (50.7 %) | 7.0 (S3 evidence) |
| Strict S4 with a 10-year history rule instead of 5 | 273 | 6.1 |
| S4 if every unbound-lake gain were ignored (S3) | 258 | 6.7 |

The post-hoc rules add 110 lakes of coverage for **+0.2** uncapped; they are not worth their unmeasured error. Primary = T1.

## Dimension by dimension (0–10; weight in brackets)

| Dimension | S0 published | S1 | S2 | S3 | **S4 final** | Why it moved |
|---|---|---|---|---|---|---|
| sourceAuthority [15] | 10.0 | 10.0 | 10.0 | 10.0 | **10.0** | Every bound lake is an operator pool or its own gauge by construction; no change |
| operatorPlan [10] | 10.0 | 10.0 | 1.9 | 4.6 | **4.4** | Fell when the fleet grew: pilots all have a TVA/CWMS plan; only 44 % of the 273 do (guide curve, or conservation zone with a top **and** a bottom). Denominator effect, `LAKE_BRAIN_AUDIT.md` §4 |
| historyQuality [15] | 2.0 | 10.0 | 8.0 | 9.4 | **9.3** | 93 % of bound lakes have ≥ 5 complete years |
| seasonalBaseline [10] | 2.0 | 10.0 | 8.8 | 10.0 | **9.9** | ≥ 2 complete years |
| trendQuality [10] | 10.0 | 10.0 | 10.0 | 10.0 | **10.0** | Every bound lake publishes an observed level (live series fresh at probe time) |
| floodDroughtContext [5] | 2.0 | 2.0 | 3.2 | 6.1 | **5.8** | An operator flood-pool bottom exists for 57.5 % of bound lakes; the rest are run-of-river/natural or publish none and stay `UNKNOWN` by design |
| validation [15] | 0.0 | 0.0 | 0.0 | 0.0 | **0.0** | Pre-registered hold-out **failed** the per-lake bar (`LAKE_BRAIN_VALIDATION_STRATEGY.md` §5); no PARTIAL claimed. Source-binding agreement evidence is strong but is one family |
| coverage [20] | 1.0 | 1.0 | 5.0 | 5.0 | **5.0** | 44.0 % ⇒ 25 % ladder step (5 points); 50 % (7 points) not reached on strict rules |

## What the status would do (same S4 evidence)
| Validation status | Displayed | Meaning |
|---|---|---|
| NOT_VALIDATED (today) | **5.0** (uncapped 6.6) | gate cap |
| PARTIAL | **7.4** | needs the PARTIAL definition in `LAKE_BRAIN_VALIDATION_STRATEGY.md` §6 accepted and earned |
| VALIDATED | **8.1** | needs a prospective result (12 months) |

## What would raise it one more point
From the research state: **validation leaving NOT_VALIDATED** (+2.4 displayed). From the *published* state: adopting the reviewed bindings with provider adapters (3.0 → 5.0).
Beyond that, `data/score_marginals_final.json`: plan share 0.44 → 0.70 (+0.2 at PARTIAL), history 1.0 (+0.1), coverage 50 % (+0.4), coverage 75 % (+0.8).

## What reaching 8.0 requires (rubric score only; the production policy additionally needs every critical condition ≥ 7.5 and is Michael's gate)
Cheapest paths (unmodified rubric): **VALIDATED + the current 273-lake evidence = 8.1**; or **PARTIAL + plan ≥ 0.8, flood ≥ 0.85, history 1.0 on 273 lakes**; or PARTIAL + coverage 75 % (466 lakes) at today's quality (8.2). No path reaches 8.0 while validation is NOT_VALIDATED (hard cap 5.0).

## Not counted, by design
`NO_SOURCE` reviews (would lift the coverage ladder without knowledge), 33 stage-only gauges, NEARBY_GAUGE_PROXY candidates, the 57 flagged lakes (single-origin, deep drawdown), satellite/altimetry levels, any lake whose provider the Engine cannot read.
