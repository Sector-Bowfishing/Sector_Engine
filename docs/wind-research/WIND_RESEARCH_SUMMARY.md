# Wind Brain deep-research campaign — summary (2026-10-13)

Research only. Branch `docs/wind-brain-research`, worktree `Sector_Engine-wind-research`. No deploy, no rubric/lifecycle/score change, no other Brain touched, H2 not read.

## Scores
| | Start | Research-supported |
|---|---:|---:|
| Wind Certification (rubric v1) | **3.1 / 10** | **3.1** — nothing in this campaign is rubric-earnable without field/over-water truth or live days |
| BWIS v1 | **5.4 / 10** | **5.4** (shadow: ≈ 5.6 if direction were scored on night/forecast ≥ 5 mph — not official) |
| Production wind | unscored | unscored |

## What we learned (bowfishing terms)
1. **Where from — good.** At night with forecast ≥ 5 mph, direction is within 22.5° 81% (5–10 mph) and 92–97% (≥ 10 mph). Poor under 5 mph, where it hardly matters. One station (8A1) is poor.
2. **How strong — fine when calm, wrong when it blows.** Night observed 10–15 mph is under-forecast by 4.6–6 mph; ≥ 15 mph by 10–17 mph. Tonight category agreement 79% (baseline 77%): skill is calm-vs-light, breezy recall 16%, windy 0/20.
3. **Tonight trend — partly.** Easing/steady/rising 55% vs 42% baseline; "easing" precision 65%; "lays down after dark" has **no skill** (POD 0.07).
4. **Confidence — one cheap lever found.** NBM **P90 ≥ 10 mph** flags nights that become breezy 36% of the time vs 1.9% otherwise (19× lift, POD 0.49; the median forecast catches 0.15). A risk flag, not a prediction; needs the sealed H2 re-test.
5. **What bank is the wind hitting — geometry is solid.** Convention verified (G1 7/7; shipped tables use the same one). Wind FROM SW hits the **NE shore** (faces SW); the SW shore is protected. Fetch × speed gives LOW/MODERATE/HIGH exposure; simple DIRECT/CROSS/PROTECTED labels pass G5 (64/71 lakes) but orientation alone is a weak predictor (AUC 0.70): **fetch carries the signal, orientation adds "which way to look" and lee protection.**
6. **Fleet.** Polygon fetch computed for 595 of 599 polygons in under an hour; **544 lakes** with HIGH/MEDIUM geometry confidence (479 beyond the 74 audited tables). It matches audited fetch in magnitude (−6%) but **failed** the registered direction-rank test (G2), so it is an *estimate tier*, not audited.
7. **Source.** Keep NBM; stop provider shopping. The real gap is production still serving HRRR/GFS Best Match.
8. **Rubric concern.** Dims 1/3 (≥ 15 mph, ≥ 20 kt events ≈ 0.1% of hours) and all-hours direction reward things bowfishing mostly doesn't use; dims 6/7 (40 pts) need physical truth, so desk research cannot move certification.

## Pre-registered results
| Test | Result |
|---|---|
| V1 direction (forecast ≥ 5 mph, night, ≤ 12 h) | PASS 0.81 / 0.77 / 0.97 / 0.92 |
| V2 speed bias | windy-tail under-forecast CONFIRMED |
| V3 tonight categories | PASS (0.79 exact, 0.99 ±1) — barely above 0.77 baseline |
| V4 trend | PASS (+0.14 vs baseline); lay-down event FAIL (POD 0.07) |
| V5 direction shift | INSUFFICIENT (10 events) |
| V7 breezy-risk flag | PASS (19× lift, POD 0.49) |
| G1 convention unit tests | PASS 7/7 |
| G2 polygon vs frozen rank agreement | **FAIL** (ρ 0.56; dominant dir 51%) — magnitude agrees, no convention error |
| G3 fleet counts | 595 computed / 544 usable / 479 new |
| G4 monotonic class vs speed | PASS 595/595 |
| G5 DIRECT/CROSS/LEE vs CEM | PASS 64/71 lakes (AUC 0.70 informational) |

## Files
`WIND_CURRENT_STATE_AUDIT` · `WIND_SCORE_HISTORY` · `WIND_SCORE_LADDER` · `WIND_SOURCE_RESEARCH` · `WIND_FORECAST_VALIDATION` · `WIND_BANK_EXPOSURE_RESEARCH` · `WIND_FETCH_RESEARCH` · `WIND_TONIGHT_MODEL` · `WIND_FLEET_SCALING` · `WIND_CROSS_BRAIN_OPPORTUNITIES` · `WIND_BLOCKER_QUEUE` · `WIND_SOURCE_LEDGER` · `WIND_NEXT_IMPLEMENTATION_PLAN` · `WIND_RESEARCH_PREREG` · `data/*.json` · scripts in `research/wind-brain/`.

## Stopped paths
Provider shopping (no source beats NBM), WindNinja, chop/wave-height refinement, any additional atmospheric variables. Nothing was added that customers would not use.
