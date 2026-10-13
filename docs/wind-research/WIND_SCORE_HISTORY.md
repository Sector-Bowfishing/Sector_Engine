# Wind Brain — score history

Rubric is **not** altered by this campaign. All numbers below are from the iOS `WIND_SCORE_CHANGE_LOG.jsonl`, `WIND_BOWFISHING_*` reports and Engine `frozen-scores.json`.

## Wind Certification Score (frozen rubric v1, candidate pipeline)
| When (UTC) | Score | What changed |
|---|---:|---|
| 2026-10-07 00:00 | 3.4 | Stage 2 baseline, computed by hand. Dimensions 8 (reliability, 0.4) and 9 (coverage, 0.5) were **judgment** credits. Dims 1 and 3 scored 0 because the 14-day calm window had **zero** ≥15 mph night hours (strict rule: unmeasured = 0). Sensitivity (not official): 5.0 if sample-limited events were unscorable. |
| 2026-10-07 19:10 | 3.3 | Stage 3A: scoreboard derived by code; judgment credits replaced; dim 9 earned by 50 directory lakes passing national QA. |
| 2026-10-07 23:36 | **3.1** | Stage 3C: dims 1–4 re-measured on the pre-registered NBM v5.0 corpus (3,696 cycles, 5 months): ≥15 mph events now observed (13 at night) and NBM forecast none; direction within 22.5° 0.758. |
| 2026-10-12 | 3.1 | Frozen in `SCORING.md`/`frozen-scores.json` with failed gate "fieldValidation". Stages 3D.1, 3D.2, score-acceleration, 3E, BWIS: **no score change**. |
| 2026-10-13 | 3.1 | This campaign: **no change** (research only; no rubric item can be earned without field/over-water truth or live days). |

Current point table (raw 31.3): dim2 4.3, dim4 5.0, dim5 10.0, dim9 4.0, dim10 8.0; all others 0.

## Bowfishing Wind Intelligence Score (BWIS v1, frozen 2026-10-12)
5.4 / 10 (54.1 pts): A input 17.9/25, B exposure geometry 18.0/25, C surface 12.4/25, D decision 3.3/20, E ops 2.4/5.

## Production wind
Unscored. The Stage 2 report carries "3/10, unchanged" as a descriptive production note, with listed defects (hidden model identity, fallback host with a different product, provider-terms review, single lake-wide reading).

## Observations about the history
- The only movement was a drift **down** (3.4 → 3.1) as better evidence replaced judgment credits and a calm window. Nothing yet has earned points from new capability: the Brain's build-out (profiles, publishing, bank rank engine) shows up in BWIS, not in certification.
- Both scores are capped by the same missing evidence class: physical truth at the bank and over water.
