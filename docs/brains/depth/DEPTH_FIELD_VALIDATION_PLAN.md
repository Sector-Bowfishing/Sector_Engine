# Depth Field Validation Plan (bowfishing ground truth; 5-10 lakes)

Goal: test the practical question, not deep-basin accuracy. **Does the model correctly say when a known flat becomes too shallow, ideal shallow, too deep, or dry/exposed?** No customer exposure; no Michael travel for hundreds of lakes.

## 1. Lake selection (5-10; all with a live direct Lake Brain level and a high-confidence pool)

| Lake | Why | Shift regime |
|---|---|---|
| Hartwell (SC/GA) | large drawdowns (research: p05 -9.1 ft; dry-flat days ~31%) | wide range, USACE CWMS, SAME_SOURCE datum |
| Guntersville (AL) | big shallow flats, small designed range, IENC 9 ft partial contour | narrow range, strong flats |
| Wheeler / Wilson / Pickwick (TVA) | the other pilots; TVA winter drawdown | moderate |
| One or two Texas reservoirs with TWDB 1-2 ft contours (e.g. Fork, Texoma) | tier A contours; level moves 8-25 ft; Landsat drawdown tested | validates zone shares and effective zones |
| One Minnesota lake (DNR contours) | natural lake, tier A/B, tiny range | negative control (no shift expected) |

## 2. Design

1. **Known flats**: ask 2-3 trusted bowfishers/beta testers per lake to name 3-5 flats (GPS point + typical depth class + typical pool/season). Prefer flats they fish at different pool levels.
2. **Depth truth**: portable sonar/handheld depth reading at those points on 2-4 dates spanning at least 2 ft of pool change (a depth reading per visit with the Depth Brain's pool shift recorded at the time). 20-40 paired readings per lake is enough to see the error.
3. **Practical class truth** per visit: dry/exposed, too shallow to shoot (< ~1 ft), shootable shallow (~1-3 ft), good (~3-5 ft), deeper (> ~5-6 ft). Record the shooter's own judgement.
4. **Prediction (pre-registered before reading)**: from the Depth shift and the flat's reference depth (taken at a reference visit near pool), predict effective depth `d_ref + shift` and class.

## 3. Metrics

* Depth error: MAE, bias, within 0.5 ft / 1 ft, calibration of reported `uncertaintyFt` (68% within 1 sigma).
* Class accuracy and the cost-weighted confusion (a dry flat called ideal is the worst error).
* Shift check: predicted shift vs (observed depth change at a fixed flat between visits). Tests the shift directly, independent of any reference depth.
* Contour lakes: error of `referenceZones` shares vs sonar transects.

## 4. Pass criteria (proposed, to be frozen before data)

* shift-vs-observed-change MAE <= 0.5 ft on >= 5 lakes;
* class accuracy >= 80% with no dry-called-ideal error;
* 68% +/- 15% of observations within 1 sigma;
* at least one lake where a true datum fault is caught (the engine returns UNKNOWN, not a wrong number).

## 5. Data capture packet

Per observation: lake, UTC time, GPS, measured depth (ft), method, pool elevation from the operator at that hour, shooter class, photo. A simple CSV/form schema is sufficient; nothing is written to production. Existing beta-tester channel is enough; no new app feature.

## 6. Dependencies / blockers

Needs willing bowfishers and 5-10 site visits over a season; depends on a live direct level (Lake Brain pilots cover Hartwell and the TVA four). Texas/Minnesota controls depend on the Lake Brain fleet binding adoption (research-verified bindings exist, not live).
