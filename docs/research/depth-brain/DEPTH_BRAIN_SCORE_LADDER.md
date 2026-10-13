# Depth Brain Proposed Maturity and Score Ladder (RESEARCH ONLY)

Rubric: `DEPTH_BRAIN_RUBRIC_PROPOSAL.md`. Scores are judgments tied to cited evidence. Weighted sum uses the rubric weights.

## Current proposed maturity: **4.3 / 10**

| Dimension (weight) | Score | Evidence |
|---|---|---|
| Source authority (15, critical) | 5 | 103 lakes (17 %) with instrument-survey contours/tables at A/B; 35 partial; 0 TVA lakes |
| Coverage (15, critical) | 4 | zones for 103 (17 %); level shift possible for 265 (43 %); union 322 (52 %), 56 explicitly unknown; no SE reservoir with contours |
| Absolute depth accuracy (10) | 3 | method error 0.010-0.026 share with fine contours; sigma 0.4-1.35 ft on A with reconciled datum; datum audit incomplete; nothing validated outside the surveyed lakes |
| Relative morphology accuracy (15, critical) | 3 | zones measurable on A lakes; every scalable proxy fails to beat a constant (GLOBathy AUC 0.53, polygon/slope 0.5-0.62); only distance-to-shore (AUC 0.82-0.9) and Landsat drawdown (5 lakes) work |
| Effective-depth capability (15, critical) | 5 | shift defined, sigma propagated (0.27/1.0 ft), operating range for 187 lakes, worked real examples; no event-level validation, datum unaudited for TVA/Santee |
| Validation (15, critical) | 5 | truth on 76 contour lakes, 63 TWDB, 33 CWMS, 232 anchor records; honest negative results; no prospective or field check |
| Confidence / provenance (10) | 5 | tiers, ledgers, licence flags, schema proposed; nothing implemented |
| Scalability (5) | 4 | ingest/normalize/match scripts for 20 sources; 23 states without a source; manual verification still needed |
| **Weighted overall** | **4.3** | 0.15x5 + 0.15x4 + 0.10x3 + 0.15x3 + 0.15x5 + 0.15x5 + 0.10x5 + 0.05x4 |

Gate status: overall < 8.0; critical dimensions < 7.5 on all five. **Not production-ready.** A shift-only slice (265 lakes, mostly federal reservoirs) is closer: about 6 on effective depth, but it is not a Depth Brain on its own.

## History this campaign

| Step | Evidence added | Overall |
|---|---|---|
| 0 | No Depth Brain | 0.0 |
| 1 Asset audit | one IENC 9 ft contour (Guntersville), modeled mean depths, shoreline-slope proxy | 1.0 |
| 2 GLOBathy evaluation | negative: Spearman 0.42/0.18, shallow share no better than constant; fallback prior only | 1.6 |
| 3 Source scout | 40 sources; 136 candidate lakes; 4.6 GB measured contours | 2.6 |
| 4 Terrain and effective depth | shift, datum, operating range, Landsat drawdown test; slope limits quantified | 3.4 |
| 5 Contour truth | 140 verified lakes, 103 A/B truth, method checked against TWDB, proxies re-tested | 4.3 |

## Projected ladder (estimates; each step requires the named evidence)

| Next step | Needs | Projected overall |
|---|---|---|
| Publish shift-only, shadow, with datum audit for TVA/Duke/Santee/USACE | datum documents, ops review | 5.0 |
| Add tier A/B zone shares in shadow for 103 lakes + verify 24 name-only USGS matches | licence review, shadow pipeline | 5.6 |
| Southeast hydroacoustic data (GA/SC/AL/NC/TN/AR/MO) for >= 25 reservoirs | partner data (blocker B-depth-001) | 6.6 |
| Field validation on 5-10 lakes against bowfishing observations | field data / Sector user reports | 7.2 |
| Landsat drawdown pilot extended to lakes with moving level, validated vs contours | scene pipeline | 7.6 |
| Prospective held-out test, monitoring, operator-reviewed datums | time | 8.0+ |
