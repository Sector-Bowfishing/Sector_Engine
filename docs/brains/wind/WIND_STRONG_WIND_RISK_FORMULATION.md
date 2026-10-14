# Strong-wind risk — a safe customer formulation, and what "confidence" should mean

**Exploratory.** All numbers are CAL+H1 (consumed data, land stations, tonight rows, n = 4,716 station-hours, 166 hours ≥ 10 mph, 1,200 station-nights with 75 breezy). Code `jobs/wind-hourly/research/strong_wind_formulation.py`, data `data/strong_wind_formulation.json`. **Nothing here changes a product rule**: the shipped flag (NBM P90 ≥ 10 mph) is frozen by the H2 pre-registration; any candidate below would need its own pre-registration and fresh data. No numeric speed correction was tried.

## Question 1 — which formulation behaves best?
| Rule (hour level; night level in brackets) | Flagged hours | POD | Precision | Notes |
|---|---|---|---|---|
| **Shipped: P90 ≥ 10** | 4.8% (114 of 1,200 nights) | 0.49 (0.51) | 0.36 (0.33) | P(breezy \| unflagged night) 3.4% |
| P90 ≥ 9 | 8.2% (192) | 0.59 (0.61) | 0.26 (0.24) | more recall, 2× false alarms |
| P90 ≥ 12 | 1.6% (37) | 0.24 (0.25) | **0.53 (0.51)** | rare, about even odds |
| Mean ≥ 8 | 2.8% (66) | 0.37 (0.39) | 0.46 (0.44) | the point forecast alone |
| P50 ≥ 8 | 2.2% (51) | 0.35 (0.36) | 0.56 (0.53) | |
| P90 − P10 ≥ 6 and P90 ≥ 8 (spread) | 6.1% (181) | 0.31 (0.43) | 0.18 (0.18) | spread adds noise, not skill |
| P90 ≥ 10 **or** mean ≥ 8 | 5.0% (118) | 0.51 (0.53) | 0.36 (0.34) | barely beyond shipped |
| P90 ≥ 10 **or** HRRR point ≥ 10 | 7.4% (213) | 0.57 (**0.65**) | 0.27 (0.23) | needs a second provider; 18% of nights flagged |
| P90 ≥ 10 and HRRR ≥ 8 | 3.2% (87) | 0.42 (0.48) | 0.45 (0.41) | |
Findings: (1) the P90 flag carries the signal; the spread and the median add little. (2) There is a clean **gradient**: P(observed ≥ 10 mph) is **1.9%** with no flag, **27.6%** with P90 10–12 (n = 152 h), **52.7%** with P90 ≥ 12 (n = 74 h). (3) The only rule that finds clearly more breezy nights is one that adds a second provider; that is exactly the evidence the future dual-wind logging should collect on fresh data.

## Question 2 — is that enough for a useful warning?
Yes as a *warning ladder*, not as a speed: 
- **Expected: LIGHT · Risk: COULD TURN BREEZY** (P90 10–12; ≈ 1 in 4 hours, 1 in 3 nights breezy)
- **Expected: LIGHT · Risk: GOOD CHANCE OF BREEZY** (P90 ≥ 12; ≈ 1 in 2) — *candidate wording, not shipped*
- no flag ⇒ **say nothing** (3.4% of unflagged nights are breezy and ≈ half of breezy nights are unflagged).
Never "wind will be 12 mph". Absolute strong wind (≥ 15 mph) stays unclaimed: 70% of those hours carry no flag.
Candidate for a future pre-registered test (fresh data only): the two-tier ladder above (thresholds 10 and 12 mph on P90) with pass lines such as tier-2 precision ≥ 0.4 and tier-1 lift ≥ 3×, evaluated on the dual-logged live data after the H2 window has been scored.

## Question 3 — does `confidence` answer the right question?
It answers a different one. Measured:
| | HIGH | MEDIUM | LOW |
|---|---|---|---|
| Direction within 22.5° (obs ≥ 2.6 m/s) | **0.77** (n 184) | 0.71 (n 343) | **0.53** (n 137) |
| P(observed ≥ 10 mph), no flag | **7.2%** (HIGH is the group whose mean forecast is already ≥ 5 mph) | 2.1% | 0.9% |
| P(observed ≥ 10 mph), flag | — | 35.7% | (n = 2) |
So the label is ordered as a **direction / forecast reliability** label (good), and is **not** a strong-wind risk label: HIGH nights are 3× more likely to hit 10 mph than MEDIUM-without-flag nights. Overloading one word invites "HIGH confidence ⇒ won't blow".

### Proposal (do not alter the contract yet)
Keep two separate fields with two vocabularies:
1. `forecastConfidence` (today's `tonight.confidence`): HIGH/MEDIUM/LOW = how much to trust *direction and the light/calm category*. Frozen rule (H2 pre-reg); rename deferred to a contract-v2 decision to avoid disturbing H2.
2. `windRisk`: `null` (no statement) · `ELEVATED` ("could turn breezy") · `HIGH` (candidate). Independent of the first; derived only from NBM P90; never rendered as "low" when absent.
Customer copy should present them on different lines ("Direction: SW — confidence medium" / "Risk: could turn breezy"), never as one blended "confidence".

## Safe-by-construction rules (already in code and tests)
Absent flag = `None`; `ifItBlows` is labelled "not a maximum"; category is a floor; no gust/wave wording; strong-wind copy derives from the flag only.
