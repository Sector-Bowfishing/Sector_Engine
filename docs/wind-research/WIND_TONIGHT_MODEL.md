# Wind Brain — the "tonight" model

**Goal:** answer what a bowfisher asks before dusk: how windy is it tonight, from where, is it building or easing, how sure are we, which banks. Built only from evidence in `WIND_FORECAST_VALIDATION.md`; **nothing here is implemented or promoted.**

## Window
Tonight = valid 00Z–06Z (7 pm–1 am CDT; shift by time zone) from the newest NBM cycle (hourly leads 1–24 are already in `hourly[≤24]`). Use the cycle issued the same afternoon (leads 6–12 h) for the headline; later cycles refresh it.

## Outputs, and the evidence behind each
| Output | Rule | Evidence | Wording to customers |
|---|---|---|---|
| **Wind from** | NBM u/v-blended direction, shown only if forecast mean ≥ 5 mph, else "variable/light" | within 22.5°: 0.81 (5–10 mph), 0.92–0.97 (≥ 10) at night; 0.65 at 3–5 | "From the SW" with a 16-point compass; never degrees |
| **Strength class** | calm < 5 · light 5–10 · breezy 10–15 · windy ≥ 15 mph on the mean forecast speed 8 pm–1 am | exact 0.79, within-1 0.99 (V3); calm recall 93%, light 36%, breezy 16%, windy 0 | State the class; **do not** state "windy" from the point forecast alone |
| **Breezy-risk flag** | NBM P90 sustained ≥ 10 mph at any tonight hour | P(≥ 10 mph \| flag) 36% vs 1.9%; POD 0.49 (V7) | "Could turn breezy" — a risk, not a forecast |
| **Trend** | speed at 1 am vs 7 pm: easing ≤ −2, rising ≥ +2, else steady | accuracy 0.55 vs 0.42 steady (V4); "easing" precision 65%; "rising" almost never issued | Offer "easing overnight" / "steady"; suppress "rising" and "lays down" |
| **Direction shift** | none | V5 insufficient (63 pairs) | Do not claim |
| **Gust** | none beyond showing the raw NBM gust as "gusts possible" | conditional gust bias −4.3 mph; ≥ 20 kt POD 0 | Do not claim |
| **Confidence** | HIGH when forecast ≥ 5 mph and no breezy-risk flag; MEDIUM when forecast 3–5 mph or breezy-risk flag; LOW when forecast < 3 mph (direction meaningless) or observation/analysis disagree by > 5 mph | derived from V1/V3/V7; no calibration of the label itself yet | Plain words, not percentages |
| **Bank view** | exposure per bank at the tonight *mean* speed and again at P90 ("if it blows") | CEM + fetch; classes in `WIND_FETCH_RESEARCH.md` | "Protected tonight" vs "protected unless it breezes up" |

## "Now vs tonight" guardrail
Use RTMA-RU analysis for "right now"; it did not improve +1 h/+3 h forecasts (fit chose no correction), so do not blend it into tonight. If a nearby METAR shows ≥ 3 mph more than the forecast hour, raise the confidence to MEDIUM and say "running windier than forecast" — a rule-based flag from the observed underforecast tail; **not yet validated** (candidate for pre-registration).

## What this model deliberately does not do
No wave-height claim, no tonight "quality", no species, no clarity. It supplies the **wind/exposure state** that Intelligence combines.

## Open items
1. Re-run V1–V7 on the sealed H2 holdout after 2027-01-01 before any customer wording ships.
2. 8A1-style stations with poor direction (0.44) suggest local terrain effects; check per-lake before promising direction on a new lake.
3. Pre-register a "running windier than forecast" nowcast rule on the 2026 corpus using hour-of-day persistence of the NBM error.
