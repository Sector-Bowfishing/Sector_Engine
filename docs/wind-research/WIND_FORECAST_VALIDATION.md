# Wind Brain — forecast validation (bowfishing framing)

Pre-registered in `WIND_RESEARCH_PREREG.md` (committed before results). Data: NBM v5.0 historical corpus, inits 2026-05-06 → 2026-10-06, leads 1/3/6/12/18, 8 METAR stations at 4 lakes (141,730 matched rows). H2 not read. These are **descriptive restratifications of already-consumed data**: nothing tuned, nothing changes the Candidate. Code: `research/wind-brain/bowfishing_validation.py`, `confidence_flag.py`. Results: `data/bowfishing_validation.json`, `data/confidence_flag.json`.

## Plain answers
| Question | Answer |
|---|---|
| Is direction usually right? | **Yes when it matters.** At night, forecast ≥ 5 mph, lead ≤ 12 h: within 22.5° **0.81** (5–10 mph, n=2,305) and **0.97** (≥ 10 mph, n=224). Weak under 5 mph (0.65) — direction is nearly meaningless there anyway. |
| Is speed biased? | Calm-to-light nights: small (−0.2 to +1.2 mph). **Windy nights are badly under-forecast:** when observed wind is 10–15 mph the forecast is **4.6 (+1 h) to 6.0 mph (+12 h) too low**; at ≥ 15 mph, 10–17 mph too low (n = 7–13 hours). |
| How accurate is tonight's forecast? | Category (calm <5 / light 5–10 / breezy 10–15 / windy ≥15) exact **0.79**, within one category **0.99** — but the modal "calm" baseline already scores 0.77. **Skill is concentrated in telling calm from light; it almost never calls breezy/windy** (forecast breezy+ 0.7% of rows vs 3.5% observed). |
| Over-water vs land | **Not testable.** All 8 stations are land (none over water). The only prior over-water evidence is satellite/buoy-derived wave physics. See `WIND_FETCH_RESEARCH.md`. |

## V1 — direction by speed band (pre-registered pass: ≥ 0.75 within 22.5° for forecast ≥ 5 mph at night, lead ≤ 12 h) → **PASS**
Within 22.5° / circular MAE:
| Scope | Forecast 3–5 mph | Forecast 5–10 | Forecast ≥ 10 |
|---|---|---|---|
| Night, lead ≤ 6 h | 0.65 / 23.9° (n 3,007) | **0.81** / 16.1° (n 2,305) | **0.97** / 8.5° (n 224) |
| Night, lead 12–18 h | 0.58 / 27.3° | **0.77** / 17.5° | **0.92** / 9.5° (n 102) |
| All hours, lead ≤ 6 h | 0.54 | 0.69 | 0.83 |
| All hours, lead 12–18 h | 0.50 | 0.67 | 0.80 |

Keyed by *observed* speed the numbers are lower (night ≤ 6 h: 0.56 / 0.73 / 0.76), because conditioning on the observation selects hours the forecast missed. **The customer sees the forecast, so the forecast-keyed table is the one that describes product behaviour.** Stations: night/forecast ≥ 5 mph/lead ≤ 12 h within 22.5°: SNH 0.91, 9A4 0.88, HSV 0.81, DCU 0.80, MSL 0.79, 15M 0.79, 4A6 0.75 (n 28), **8A1 0.44 (n 50, circular MAE 35°)** — one station is poor; likely local terrain at that AWOS (not diagnosed).
Implication: the rubric's all-hours 0.758 understates direction quality for the hours and speeds bowfishing uses (see `WIND_SCORE_LADDER.md`).

## V2 — speed bias / MAE at night (mph)
By **forecast** band (what the user is told), +6 h: <5 mph: bias −0.2, MAE 1.8 (n 8,480); 5–10: **+1.0**, MAE 2.4 (n 930); 10–15: +1.3, MAE 3.4 (n 62). By **observed** band, +6 h: <5: +0.4; 5–10: **−2.7**; 10–15: **−5.3**; ≥ 15: **−11.9** (n 11).
Reading both: the forecast is regressed toward the middle (over-calls modest wind when it says 5–10, under-calls when it actually blows). Do not present a forecast of "8 mph" as a ceiling: real wind that night was as likely to be 4 or 12. Pre-registered expectation "biased low in the windy band" **confirmed**.

## V3 — tonight categories (init 12Z/18Z, valid 00Z/06Z; n = 4,724) → **PASS the stated line, weakly**
Exact 0.792 (≥ 0.65 ✔), within-1 0.986 (≥ 0.95 ✔). Baseline always-"calm": 0.774. Confusion (rows observed, cols forecast; calm/light/breezy/windy):
`calm 3392/262/4/0` · `light 569/328/3/0` · `breezy 42/81/23/0` · `windy 9/9/2/0`.
Recall: calm 93%, **light 36%**, **breezy 16%**, windy 0 of 20.

## V4 — trend, valid 00Z → 06Z (n = 2,324) → **PASS the stated line**
Three-class (easing / steady / rising at ±2 mph) accuracy **0.554** vs always-steady 0.417 (+0.137 ≥ +0.05 ✔). Forecast "easing": precision 65%, recall 50%. Forecast "rising" essentially never issued (14 times; 9 right) while 250 were observed. **Lay-down event (obs ≥ 8 mph at 00Z and ≤ 5 mph at 06Z, 226 events): POD 0.066, FAR 0.63 — FAIL / no skill**, because the forecast rarely has ≥ 8 mph at 00Z to begin with.

## V5 — direction shift ≥ 45° tonight → **INSUFFICIENT** (63 pairs with both ≥ 5 mph; 10 observed events; POD 0.40, FAR 0.56). No claim.

## V7 — breezy-risk confidence flag from NBM P90 (n = 4,716) → **PASS**
Flag when P90 sustained ≥ 10 mph (4.8% of rows). Observed ≥ 10 mph: P(event | flag) **0.358** vs **0.019** unflagged (19× lift ≥ 3× ✔); POD **0.49** (≥ 0.4 ✔); FAR 0.64. Same events found by the P50 forecast alone: POD 0.15. At 8 mph: lift 8×, POD 0.56, FAR 0.63. Caveats: 166 events across 8 stations from clustered weather days (effective n smaller); land stations; it is a *risk flag*, not a prediction ("one in three flagged nights is breezy"); needs the sealed H2 re-test before any claim.

## What this does and does not support saying to a customer
- ✔ "Wind from the SW tonight" when forecast ≥ 5 mph — right within ~22° about 4 times in 5, 9 times in 10 when ≥ 10 mph.
- ✔ Calm vs light vs not-calm at ~80% category agreement.
- ✔ "Breezy possible tonight" as a risk flag (1 in 3 hit rate, 19× the base rate).
- ✔ "Easing overnight" (precision 65%).
- ✘ "Lays down after dark" as a prediction (POD 0.07).
- ✘ Any gust claim from the sustained forecast (prior evidence: conditional gust bias −4.3 mph; ≥ 20 kt POD 0).
- ✘ Any over-water speed claim.

## Failures reported honestly
Windy-tail bias (V2), breezy/windy recall (V3), lay-down POD (V4), shift sample size (V5), and the 8A1 station direction. The flag in V7 is the only fix found that needs no new source.
