# Wind Brain deep-research campaign — pre-registration (2026-10-13)

Written and committed BEFORE any result below was computed. Research only; no production, rubric, lifecycle or Brain change.

## Data rules
- Forecast/obs rows: the pre-registered NBM v5.0 historical corpus, inits 2026-05-06 → 2026-10-06 (CAL + H1), leads 1/3/6/12/18, the 8 frozen METAR stations, same rows for every comparison. These are DESCRIPTIVE restratifications of data already consumed by earlier pre-registrations; nothing is tuned and no number here changes the Candidate.
- H2 (inits >= 2026-10-07) is NOT read. Live archive is not used for skill.
- Night = valid 01-08 UTC (existing definition). "Tonight" = valid 00-06 UTC (7 pm - 1 am CDT) forecast issued the same day (init 12Z or 18Z).
- Calm direction: METAR direction is not used when observed speed < 2.6 m/s (5.8 mph) in headline direction numbers; lower bands reported only as "direction is not meaningful".

## Tests (pass/fail stated now)
- V1 Direction by band. Fraction within 22.5 deg and circular MAE, stratified by (a) observed speed band 3-5 / 5-10 / >=10 mph and (b) FORECAST speed band (what the customer sees) 5-10 / >=10 mph, all hours and night. PASS (customer-useful) if within-22.5 >= 0.75 for forecast >= 5 mph at night, leads <= 12 h. Report failures.
- V2 Speed bias/MAE by forecast band (<5, 5-10, 10-15, >=15 mph) and lead group, night. Report signed bias; no pass line (descriptive), but "biased low in the windy band" is pre-registered as the expected failure from Stage 3D.2.
- V3 Tonight categories: calm <5, light 5-10, breezy 10-15, windy >=15 mph. Forecast category vs observed category for tonight rows. PASS if exact >= 0.65 and within one category >= 0.95; also compare to persistence-of-climatology (always forecasting the modal category).
- V4 Trend/lay-down: for same-day inits 12Z and 18Z, forecast change in speed between valid 00Z and 06Z (+-2 mph = steady) vs observed change. PASS if 3-class accuracy beats the always-"steady" baseline by >= 0.05 absolute. Lay-down event (obs 00Z >= 8 mph and obs 06Z <= 5 mph): report POD/FAR of forecast.
- V5 Direction shift tonight: forecast vs observed 00Z->06Z wind turning >= 45 deg when both >= 5 mph; POD/FAR.
- G1 Convention unit tests (synthetic lakes): wind FROM theta -> fetch measured upwind (toward theta) from the bank point; the bank receiving longest fetch is the one on the DOWNWIND end. Must pass 100%.
- G2 Independent geometry: a polygon ray-cast fetch computed from the engine lake polygons (599) vs the frozen NHD raster fetch tables on lakes in both sets. PASS if median per-lake Spearman rank correlation of 16-direction median bank fetch >= 0.85 and dominant-exposure-direction within 45 deg on >= 80% of lakes.
- G3 Fleet: count of the 621 directory lakes with (i) polygon, (ii) fetch exposure computable, (iii) bank-class computable, (iv) live forecast available (grid-based, all CONUS = yes), by rule stated in the fleet doc.
- G4 Simple exposure class monotonicity: for the reference winds 8/12/18 mph, class from fetch is monotone in fetch and speed (Low/Moderate/High); report share of lake-direction cells per class.

## Addendum (written before any G5 result was computed)
- G5 Bank-impact vocabulary. For each bank of the frozen fetch tables (4 development lakes + 70 national), facing bearing = bearing anchor -> standoff (toward the water). For wind FROM theta at 12 mph, alpha = angular difference(theta, facing). DIRECT: alpha <= 45; CROSS: 45 < alpha <= 90; LEE: alpha > 90. "HIGH" exposure = frozen CEM chop >= 6 in (6 h steady, effective 9-ray fetch). PASS if on >= 80% of lakes: HIGH share among LEE banks <= 5% AND median effective fetch DIRECT / LEE >= 5. Also report AUC of "DIRECT vs not" for predicting HIGH (informational; >= 0.75 means the simple angle concept carries real information beyond nothing).
- G6 Fetch-class thresholds in plain terms: the 3-class LOW/MODERATE/HIGH map (CEM chop < 1 in, 1-6 in, >= 6 in; 6 h steady) is reported as fetch-vs-speed table. No pass line.

## Addendum 2 (written before any V7 result was computed)
- V7 Confidence flag for tonight. Tonight rows as in V3 (init 12Z/18Z, valid 00Z or 06Z, qmd percentiles exist at those inits). Flag "BREEZY RISK" when NBM P90 sustained speed (bilinear to station) >= 10 mph. Evaluate against observed >= 10 mph (POD, FAR, and the observed-breezy rate when the flag is on vs off). PASS if P(obs >= 10 mph | flag on) >= 3x P(obs >= 10 mph | flag off) and POD >= 0.4. Same test at 8 mph threshold reported as sensitivity (not a pass line). Descriptive only; no fitting.
