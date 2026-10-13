# Wind Certification rubric v2 — PROPOSAL ONLY (not applied; canonical score stays 3.1 / 10)

Question asked of every dimension: **does it make Wind better for bowfishing?** Mature Wind should be rewarded for reliable direction, reliable useful speed, a good tonight forecast, bank exposure, fleet coverage, honest confidence, real validation and operational reliability — not for extreme-weather science. Nothing here changes the frozen v1 rubric, the scorer, the caps or the stored score; adoption needs a separate rubric decision, a pre-registered scorer, and no H2 look.

## Dimension review (v1 → v2)
| v1 dimension (pts) | Problem | Bowfishing value | v2 recommendation | Effect on rigor |
|---|---|---|---|---|
| 1 Speed (12): night MAE/bias **and** ≥ 15 mph event POD ≥ 0.5, FAR ≤ 0.5 | ≥ 15 mph nights ≈ 0.1% of hours; no source meets it; scores 0 for a forecast right where bank choice flips | MAE/bias and calm-vs-light yes; 15 mph event no | **Useful tonight speed (12):** category exact + within-one vs always-modal baseline; calm/light recall; windy-tail bias reported | Stricter on baseline skill (v1 never compared to climatology) |
| 2 Direction (8): within 22.5° over all hours (≥ 2.6 m/s) | Includes daytime and 6–8 mph drift; hides that direction is good at night ≥ 5 mph | Direction drives the bank answer | **Direction when it matters (12):** night, forecast ≥ 5 mph within 22.5°; plus **suppression correctness** (direction not shown < 5 mph) | Same data, sharper target; adds "do not claim" scoring |
| 3 Gust (5): bias and ≥ 20 kt POD ≥ 0.6 | No source forecasts gust events; irrelevant to a nightly decision | "gusty tonight?" is useful as a risk | **Strong-wind risk (8):** probabilistic flag — lift ≥ 3×, POD ≥ 0.4 at 10 mph (night level also), plus honesty of absent-flag wording; gust claims score only if a measured-gust source earns them | Scores calibrated risk instead of an impossible deterministic event |
| 4 Lead (5) | Fine | tonight leads matter | **Tonight trend (4):** easing precision ≥ 0.55; rising/lay-down earn points **only** if they pass their own guard tests | Rewards withholding unsupported claims |
| 5 Fetch method (10) | Method QA only; blind to geometry identity | bank answer rests on it | **Geometry & tier discipline (8):** audited method QA + matched tier validation + identity checks + blockers | Adds matched-geometry and identity gates |
| 6 Exposure field-validated (20) | Correct and essential | the product question | **Bank exposure field-validated (20):** paired-bank concordance, ≥ 40 holdout pairs, ≥ 2 independent lakes, ≥ 3 quadrants (Addendum v1 volumes) | Unchanged weight and rigor |
| 7 Surface field-validated (20) | Wave-height-class science heavy for the use | practical roughness yes | **Practical roughness (8):** tester water-surface (calm/light/choppy/rough) and boat-control agreement; no wave-height claims | Less science, same need for field data |
| — | No over-water term except a cap | biggest unknown | **Over-water reference (5):** ≥ 30 sessions, ≥ 2 lakes, ratio measured | New measured item |
| — | No confidence term | users need "how sure" | **Confidence calibration (5):** HIGH vs not-HIGH direction error ordering (H2-C1/C2) | New, uses frozen rule |
| 8 Reliability (8) | Operations, not knowledge | needed | **Reliability & freshness (5):** 30 valid live days (same rule as the audit) | Same rule, less weight |
| 9 Coverage (4): lakes with tables | Counts audited only | fleet matters | **Fleet coverage (5):** share of fleet with label-eligible exposure, **capped by validation tier** (ESTIMATED ≤ 50% credit until field-validated; blocked lakes 0) | Prevents coverage inflation |
| 10 Provenance/Unknown (8) | Good | honesty | **Honesty & provenance (8):** Unknown preserved, withheld-claims list intact, forecast ≠ observation, no fabricated calm | Kept |
Total 100 = 12 + 12 + 8 + 4 + 8 + 20 + 8 + 5 + 5 + 5 + 5 + 8.

## Caps (unchanged in spirit)
- Cap 6 until bank-pair field truth meets the volume above; cap 7 until an over-water reference exists; cap 8 requires the field items at ≥ 70% and 30 valid live days. Without field truth the maximum raw is 100 − 20 − 8 − 5 = **67 ⇒ capped at 6.0**, i.e. **v2 cannot raise the score without physical truth** (same as v1). Desk work alone still cannot certify Wind.

## What v2 changes in practice
- Rewards the capabilities that already exist (direction at night, tonight category, risk flag, easing, tiered bank exposure, honest withholding) — but each is scored on **held-out data against a baseline**, so a pass means something.
- Removes ≥ 15 mph / ≥ 20 kt gates and wave-height-class science.
- Adds items v1 lacked: baselines, calibration of confidence, identity/blocker gates, tier-capped coverage, over-water ratio.

## Process needed before adoption
Independent review (Michael + reviewer); pre-register the v2 scorer; keep v1 in parallel for continuity; do not evaluate v2 on H2 before the holdout opens; log any change in `WIND_SCORE_CHANGE_LOG.jsonl` as a new rubric version, never as an in-place edit.

## Review pass 2026-10-13 (still a proposal; nothing adopted)
Test applied to every v2 dimension: *does it make Wind better for bowfishing, and could Wind score well on it without extreme-weather science?*
| v2 dimension | Better for bowfishing? | Needs obscure science? | Finding from this cycle | Change to the proposal |
|---|---|---|---|---|
| Useful tonight speed (12) | yes — calm vs light decides the night | no | provider shadow: NBM 0.79 vs 0.64 category; skill is calm-vs-light | add **windy-night handling** (the point forecast under-calls: require the risk-aware value to be what is scored when wind ≥ 10 mph), so a score cannot be earned by being right only on calm nights |
| Direction when it matters (12) | yes | no | night ≥ 5 mph 0.81–0.97; 3 stations weak | score per-lake (min-station gate) so one good lake cannot hide a poor one; keep suppression correctness |
| Strong-wind risk (8) | yes | no (percentiles already published) | ladder 1.9% / 27.6% / 52.7%; half of breezy hours unflagged | require both lift and an **absent-flag statement test** (no "low risk" text); POD floor stays modest (0.4) |
| Tonight trend (4) | yes | no | easing 0.65; lay-down none | unchanged |
| Geometry & tier discipline (8) | yes | no | identity risk found in 6 audited lakes; vocabulary defect found by the matched test | add **identity/blocker gate** (a lake with an unresolved identity flag earns nothing) and require the validated rule-set version to match the shipped fingerprint |
| Bank exposure field-validated (20) | yes — the product question | no | field plan: 40 pairs, 2 independent lakes, 3 quadrants; afternoons are the practical volume | state explicitly whether daytime pairs count (Addendum owner), since evenings ≥ 8 mph are ~4 a month |
| Practical roughness (8) | yes | no | one-minute record exists | unchanged |
| Over-water reference (5) | yes — largest unknown | no | portable plan ≥ 30 sessions | unchanged |
| Confidence calibration (5) | yes | no | label orders direction reliability, not strong-wind risk | **split**: score `forecastConfidence` on direction ordering and `windRisk` on lift; do not score one blended "confidence" |
| Reliability & freshness (5) | operations | no | scorer already earns 1.33/8 at 5 days | unchanged rule |
| Fleet coverage (5, tier-capped) | yes | no | 522 label-eligible IDs (517 distinct waters), 0 validated | cap by validation tier (ESTIMATED ≤ 50% until field-validated), blocked lakes count 0 |
| Honesty & provenance (8) | yes | no | withheld-claims list, forecast ≠ observation | keep |
Not rewarded by v2 by design: gust-event POD, ≥ 15 mph event skill, wave-height science, extra atmospheric variables. Cap logic unchanged (no field truth ⇒ ≤ 6.0). **Do not adopt during this phase**; the canonical score stays on frozen rubric v1.
