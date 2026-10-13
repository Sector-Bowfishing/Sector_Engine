# Wind validation + shadow readiness — summary (2026-10-13)

Branch `feat/wind-brain-adoption` (additional commits on the existing remote branch; still based on the unmerged `feat/cost-efficient-scheduling`). Canonical Wind Certification **3.1 / 10**, unchanged; no rubric edit. H2 completely sealed: no row read, summarised or copied; the live-reliability audit used operational metadata only. Customer wind unchanged (Open-Meteo). Nothing deployed, merged or rebased.

## What this phase established
| Workstream | Result | Doc |
|---|---|---|
| 1 Live reliability clock | **5 valid live days** (10-08…10-12); 10-07 invalid (clock started 04:59Z, RTMA 92.7%). 164 executions, 0 failed; 24 partial NBM cycles all completed by catch-up. Archive 30-day gate ≈ **2026-11-07 03:00Z** (holds only if no day is invalid); Brain-publish gate ≈ **2026-11-12 03:00Z** | `WIND_LIVE_RELIABILITY.md` |
| 2 NBM vs Open-Meteo (HRRR proxy), CAL+H1 tonight rows | NBM better on calm/light, direction (0.78 vs 0.70), category (0.79 vs 0.64), easing (0.65 vs 0.57), MAE 2.05 vs 3.03. **But on observed ≥ 10 mph nights the current provider's point value is less biased (−3.6 vs −5.7 mph) and detects more (43% vs 15%).** NBM + P90 flag reaches parity (49%). Live-period comparison not made (sealed); future logging design only | `WIND_PROVIDER_SHADOW_COMPARISON.md` |
| 3 Strong wind | Flag: flagged nights breezy 33% vs 3.4% unflagged (~10×), POD 0.51 night-level; **51% of ≥ 10 mph hours unflagged (silent), 70% of ≥ 15 mph**; P90 covers observed on only 32% of ≥ 10 mph hours. Useful as a caution, not as reassurance or ceiling; wording fixed; no numeric correction | `WIND_STRONG_WIND_RISK_VALIDATION.md` |
| 4 Matched per-bank validation | M1 (same NHD polygon) **PASS**. M2 (engine polygon) **FAIL as registered** on lake dominant direction (58% vs 80%) while every bank-level line passes. Pre-registered test exposed a vocabulary defect (false-PROTECTED 10.6%) — fixed (PROTECTED needs chop ≤ 2; estimated margin) → ≈ 1%. With the estimator's own facing, DIRECT/CROSS split is poor (78% agreement) ⇒ ESTIMATED surfaces say **EXPOSED/PROTECTED** only | `WIND_MATCHED_BANK_EXPOSURE_VALIDATION.md` |
| 5–6 Field pairs + protocol | 99 candidate pairs on 9 lakes (4 Tennessee reaches = one environment; Hartwell and Toledo Bend test the ESTIMATED tier; Mille Lacs, McConaughy, Maurepas for independence); one-minute record (calm/light/choppy/rough · easy/noticeable/difficult · DIRECT/CROSS/PROTECTED/UNSURE) validated in code | `WIND_BANK_PAIR_FIELD_PACK.md`, `WIND_FIELD_OBSERVATION_PROTOCOL.md` |
| 7 Anemometer | Portable ≥ 30 sessions on 2–3 lakes is the minimum useful over-water truth; permanent station optional (26a, ≈ $5–8k) and earns no points alone at 3.1 | `WIND_ANEMOMETER_VALIDATION_RECOMMENDATION.md` |
| 8 Fleet readiness (recomputed) | AUDITED 65 + ESTIMATED_HIGH 296 + ESTIMATED_MEDIUM 167 + LOW 45 + POINT_ONLY 10 + NO_GEOMETRY 21 + **BLOCKED 17** (six audited lakes have a lake-identity risk; AK/HI untested). **528 lakes may carry bank words** | `WIND_FLEET_EXPOSURE_READINESS.md` |
| 9 Fleet NBM sampling | Matches production interpolation on 600 real lake points (0.005 m/s, 0.5°); 0 extra reads/calls; 36 leads in 0.23 s; 24 objects/day vs 14,904; calm-cell defect found and fixed | `WIND_FLEET_SAMPLING_VALIDATION.md` |
| 10–11 Tonight contract + scenarios | `simple()` customer words; fixtures A–K pass; no lay-down/rising/gust/wave wording; weak-wind direction and bank words suppressed < 5 mph | `WIND_TONIGHT_SCENARIO_TESTS.md` |
| 12 Intelligence | Final contract proposal, fixtures pinned by tests | `WIND_INTELLIGENCE_CONTRACT_FINAL_PROPOSAL.md` |
| 13 Rubric | Proposed v2 (not applied); cap logic keeps the score ≤ 6 without bank-pair truth | `WIND_CERTIFICATION_RUBRIC_V2.md` |
| 14 Readiness matrix | PASS 2 · PARTIAL 14 · WAITING 6 · NOT_REQUIRED 1 · FAIL 0 | `WIND_PRODUCTION_READINESS_MATRIX.md` |

## Corrections to earlier statements (honesty log)
1. Earlier provider paper said "neither source" for windy nights; the shadow comparison shows the current provider's point value is *better* on windy hours — added gate 7 (risk-aware gauge input).
2. "AUDITED = trustworthy" is wrong for six lakes with a lake-identity flag.
3. Earlier tonight text implied `ifItBlows` bounds the wind; it does not (exceeded on 68% of ≥ 10 mph hours). Wording fixed.
4. Vocabulary v1 allowed PROTECTED on lee-facing banks with 3–6 in modelled chop; fixed after the matched test (post-hoc, same data).
5. Fleet sampler differed from the archive in calm cells; fixed.

## Tests
`jobs/wind-hourly`: **104 passed** (58 original + 46 new; network tests deselected).

## Blocked / waiting
Time (30 live days; H2 on 2027-01-01) · humans (bank pairs, over-water sessions) · Michael (customer provider, ESTIMATED visibility, anemometer, rubric review) · merge of `feat/cost-efficient-scheduling` (wiring/deploy/orchestration). See `WIND_NEXT_ACTIONS.md`.
