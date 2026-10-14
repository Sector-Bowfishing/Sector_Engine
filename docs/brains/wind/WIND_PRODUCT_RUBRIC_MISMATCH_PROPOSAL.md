# Wind — product intelligence reset: output classification and rubric mismatch PROPOSAL (nothing changed)

Canonical scorer re-run 2026-10-14 00:28Z (frozen `wind-certification-rubric-v1`, metadata mirror only, H2 sealed): **displayed 3.3, raw 3.29** (3.27 earlier; the only mover is reliability, 5 -> 6 of 30 valid days). Rubric, thresholds, evidence, H2: untouched. No score published from this lane.

## 1. Two score numbers in circulation are POINTS, not 0-10 values
Several "low" dimensions are already maxed. Dimension value (0-10) x weight/10 = points:
| Dim | Value | Weight | Points | Reading |
|---|---:|---:|---:|---|
| Wind speed | 0.0 | 12 | 0.00 | gated (see 3) |
| Direction | 5.4 | 8 | 4.32 | partial |
| Gust | 0.0 | 5 | 0.00 | gated (see 3) |
| Lead / tonight | **10.0** | 5 | 5.0 | **maxed** ("5.0" is full marks) |
| Fetch method | **10.0** | 10 | 10.0 | maxed |
| Exposure (field) | 0.0 | 20 | 0 | needs bank-pair truth |
| Surface (field) | 0.0 | 20 | 0 | needs bank-pair truth |
| Reliability | 2.0 | 8 | 1.6 | TIME (6/30 days; completeness credit 0.2) |
| Coverage | **10.0** | 4 | 4.0 | **maxed** ("4.0" is full marks; 4/4 dev lakes, 50 directory lakes pass QA) |
| Provenance/Unknown | **10.0** | 8 | 8.0 | maxed |
So tonight, coverage and provenance need no desk work. Hundreds of fleet geometry candidates are not counted by this dimension and do not need to be: it counts QA-passing directory lakes, which is already full.

## 2. Classification of every Wind output
| Output | Level | Validation owed |
|---|---|---|
| Wind speed (NBM / Open-Meteo) | 1 provider | source, freshness, units, sanity |
| Wind direction | 1 provider | same |
| Forecast gust | 1 provider | same (display only) |
| Forecast trend (easing / steady / rising) | 1 / simple 2 | arithmetic on provider hourly values; edge cases |
| Direction relative to bank | 2 deterministic | formula + sign convention (FROM-wind looks INTO the wind; tested) |
| Effective fetch (9-ray CEM) | 2 deterministic | agrees with independent exact geometry (median diff 0.05): mature |
| Breezy-risk flag (NBM P90 >= 10 mph) | 2 (provider percentile threshold) | descriptive restratification passed; sealed H2 before any stronger claim |
| Exposed / protected bank | **3 Sector-derived** | prospective bank-pair truth (v2 rules were set after the original failure: NOT independently validated) |
| Chop / rough-water interpretation | **3** | field truth |
| Tonight bowfishing usefulness | **3** | field + prospective |

## 3. Why Wind speed = 0 and Gust = 0 (RUBRIC MISMATCH)
Each dimension's credit is the **minimum** over its conditions (`scoreboard.dims_1_to_4`).
- **Wind speed** conditions: night MAE 0.837 (credit **1.0**); |bias| 0.04 <= 0.3 (**1.0**); >= 15 mph event POD >= 0.5 and FAR <= 0.5 (**0.0**: POD 0.0 on 49 observed events). min = **0** -> 12 of 100 points.
- **Gust** conditions: |conditional bias| 1.91 m/s (**0.544**); >= 20 kt event POD >= 0.6 (**0.0**: POD 0.02-0.07, FAR 0.84+). min = **0** -> 5 points.
One dimension therefore mixes (a) provider availability/accuracy, (b) strong-event detection skill on LAND stations, and (c) by implication over-water impact. The first is excellent, the second is a real forecast limitation, the third is not measured at all. A strong-wind detection failure zeroes the whole "speed" capability even though speed itself is accurate.

Hypothetical only (NOT applied, NOT publishable): if the event gates were scored as a separate item rather than min'd, speed would carry full 12 points (MAE and bias pass) and gust ~2.7 of 5, giving raw ~47.6/100 (4.8), still under the 6.0 field-validation cap. This quantifies the mismatch; it does not authorise a change. The rubric changes only on Michael's approval (see also `WIND_CRITICAL_DIMENSIONS_PROPOSAL.md`, `WIND_CERTIFICATION_RUBRIC_V2.md`).

### Gust: what Sector can truthfully say today
1. Open-Meteo exposes hourly `wind_gusts_10m`; NBM exposes a GUST field (already ingested and archived by the Brain); the Engine already applies a provider-gust penalty in `/conditions`. Units (m/s -> mph), freshness and time alignment are in the existing ingest/evidence path (`evidence.py` matches gust as `gustMS`).
2. Product capability that exists: **"Gusts up to N mph tonight" (provider forecast)** can be displayed as provider truth, labelled as forecast.
3. What is NOT supported: strong gusts are under-forecast by both providers (NBM >= 20 kt POD 0.04, HRRR 0.19, FAR 0.88-0.93; conditional bias -1.9 / -1.6 m/s; see `WIND_PROVIDER_DECISION.md`). So do not say "no strong gusts expected" or "these gusts will make this bank rough". The right customer text is "forecast gust N mph; gust forecasts run low in strong wind".
4. The score of 0 measures **(b) independent strong-event validation**, not availability (a) and not impact on water (c). Three maturity levels to keep separate: DATA EXISTS (yes) / TRUSTWORTHY ENOUGH TO DISPLAY (yes with the under-forecast caveat) / SECTOR-DERIVED IMPACT VALIDATED (no).
No new gust campaign is warranted: the desk answer is documented here.

### Wind speed
Same structure: provider speed exists and is accurate (MAE 0.84 mph at night, bias -0.04). The zero is entirely the >= 15 mph event gate (NBM rarely forecasts >= 15 mph even when it happens; V3 in `WIND_FORECAST_VALIDATION.md` on the research branch: breezy recall 16%, windy 0 of 20). Remedy that needs no new source is already shipped as the breezy-risk flag (P90 >= 10 mph, lift 19x). No further desk research on speed.

### Direction (4.32 / 8)
Credit 0.54 on "within 22.5 degrees" for ALL hours when both speeds >= 2.6 m/s (0.758; target 0.85). The product-relevant slice (night, forecast >= 5 mph, lead <= 12 h) is 0.81 (0.97 at >= 10 mph). Provider direction needs no new validation; the all-hours metric understates the hours bowfishers use. No desk work moves it; the proposal is to score the product slice (rubric change, Michael). The Sector-derived part (direction -> bank exposure) is item Exposure below.

### Coverage and tonight
Both maxed (section 1). Nothing to do.

### Exposure and surface (40 points, both 0)
Genuine Sector-derived claims with no field truth. The v2 rules post-date the original failure and stay "unvalidated". The smallest legitimate fresh validation is already prepared and frozen: `WIND_BANK_VALIDATION_V2_PREREG.md` + field pack (>= 40 bank pairs, >= 2 independent lakes, >= 3 quadrants; Guntersville and Hartwell first) and the one-minute field record. Blocker category: **FIELD**. No national campaign, no desk substitute.
Minimum useful surface claim (internal until field-validated): per bank **LIKELY CALM / LIKELY MODERATE / LIKELY ROUGH / UNKNOWN**, mapped from the frozen chop classes (Protected + Ripple = calm; Light + Moderate chop = moderate; >= 12 in = rough), UNKNOWN whenever geometry tier is POINT_ONLY, the bank is below resolution, or the forecast sits on a class boundary. No wave model.

### Reliability (1.6 / 8)
TIME. Clock running (5 of 30 valid days; projected gate 2026-11-08). Nothing to build.

## 4. Runtime compactness check
Wind runtime image = `main.py`, `lakes.json`, `sector_wind` package (644 KB incl. 208 KB geometry tiers + 8 KB validation evidence) and the shared platform package. No research archives, GRIBs or pickles are baked in or read at customer time. Customer reads hit cached RTDB state. Wind state is already the compact set: speed, direction, gust, trend, exposure, surface class, confidence, timestamps, provenance. One residual simplification (Wind deployment lane, not done here): `validation_evidence.json` is baked and republished as `scores` in the registry, which is how the 3.1 duplicate arose (see `docs/brains/scoring/SCORE_ARTIFACT_DURABILITY.md` section 6 on the shared branch).

## 5. Proposed approvals (Michael)
1. Split event-detection gates out of dimensions 1 and 3 (or weight them as a separate "strong-wind detection" item) so provider speed/gust accuracy is not erased by a land-station event gate.
2. Score direction on the night, forecast >= 5 mph slice (or report both).
3. Keep Exposure/Surface as the 40-point Sector-derived dimensions requiring field truth.
Until approved, rubric v1 stands and the displayed score stays 3.3.
