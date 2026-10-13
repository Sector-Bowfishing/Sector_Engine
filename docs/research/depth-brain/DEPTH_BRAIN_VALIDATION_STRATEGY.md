# Depth Brain Validation Strategy

Principle: never validate a model against another model. Truth = agency/instrument surveys, TWDB/CWMS hypsometry, and (future) field observations.

## 1. Truth sets in hand (this campaign)

| Set | n | Used for | Notes |
|---|---|---|---|
| Contour-derived shares (tier A) | 76-77 lakes | shallow share, shore-to-6-ft distance, flats, GLOBathy and proxy tests | 65 % reservoirs, not random; contour gaps bias shallow; datum doubts flagged |
| TWDB area-capacity tables | 63 (18 rebuilt to 15 m rasters) | exact shallow shares, method check | one regional family |
| MN DNR contours | 9-10 | independent method check (5/10 ft interval) | can judge <=10 ft only |
| USACE CWMS stage-area slope | 33 | acres per foot, lake-level response | no TVA/Duke/Santee |
| Max-depth anchors | 232 records, 188 with max depth, 116 high/medium | Dmax tests | uneven quality |
| EPA NLA 2007 max depth | 109 fleet lakes | anchor for contour completeness | single year |
| IENC 9 ft | 34 footprints | binary check (not yet used as truth) | interior coverage unverified |

## 2. Metrics and thresholds (proposed, for a production gate)

| Capability | Metrics | Gate to ship |
|---|---|---|
| Max/mean depth (absolute) | MAE, bias, RMSE, within x1.25/x1.5, Spearman | only A/B; sigma <= 1.5 ft for any foot-level claim |
| Shallow share per zone | MAE vs leave-one-state-out constant, Spearman, bootstrap CI | must beat a constant with CI excluding zero |
| Class (very shallow/shallow/transition/deep) | accuracy, balanced accuracy, confusion; compare to majority class | balanced accuracy >= 0.7 |
| Broad-shallow lake ranking | AUC, top-third precision | AUC >= 0.75, lower CI > 0.6 |
| Spatial flats | IoU, cell-level AUC for <=6 ft, flat100/flat200 recall | AUC >= 0.85, IoU >= 0.6 (only tier A/B ever reach this) |
| Channel/drop-off | distance error to true 6 ft/10 ft contour | median error < 1 contour interval |
| Effective depth | predicted vs measured shift (pool delta), contour re-binning vs TWDB area-capacity at lower pool | shift error <= 0.5 ft p90 where pool confidence high |
| Calibration | reliability of reported sigma | 68 % of truths within 1 sigma |

## 3. Anti-leakage rules

* Leave-one-state-out and leave-one-lake-out; report both.
* Collapse river chains (Tennessee, Savannah, Santee, Cumberland) to one point.
* Separate "supplied-observed Dmax" GLOBathy rows (59 lakes; literature pass-through) from modeled rows.
* No tuning on the lake used to report accuracy; fix thresholds in a pre-registration note before any prospective test.

## 4. Results to date (see the detailed docs)

* GLOBathy: Dmax Spearman 0.42 (n=75) and 0.18 (n=73 vs contour max); shallow-share MAE 0.135 vs constant 0.128, AUC for broad-shallow 0.53. Fails every gate.
* 3DEP shoreline slope: lake-level response Spearman 0.77 on CWMS (n=33), 0.44 on TWDB (n=63); shallow shares do not beat a constant (MAE 0.039 vs 0.041 within 3 ft); per-segment slope in lakes adds 0.004 AUC beyond distance to shore. Passes only the coarse "acres per foot" prior.
* Distance to shore alone: cell-level AUC 0.82-0.90 for <=6 ft / <=3 ft; it is the strongest cheap predictor within a lake.
* Landsat drawdown exposure (5 TX lakes): Spearman 0.87-0.93 with true depth; promising for lakes whose level moves 8-25 ft; lake-wide shares biased low.
* Contour-to-share method: MAE 0.010-0.013 with 1-2 ft contours, 0.015-0.026 with 5 ft, 0.020-0.070 with 10 ft (overstates shallow).
* Effective depth: shift sigma 0.27 ft (high pool confidence) to 1.0 ft (medium); absolute depth 0.4-0.45 ft for 1-2 ft contours with reconciled datum, 1.35 ft at 5 ft interval, 1.8-3.2 ft if datum unreconciled.

## 5. Missing validation (the real gap)

1. **Bowfisher ground truth.** Nobody has checked that "0-6 ft flat" maps to shootable water with fish. Needs sonar/hand-measured depths and catch/sighting points on 5-10 lakes; Sector's own user observation data could do this if tied to depth.
2. **Prospective test.** Pre-register thresholds, predict a held-out set of states (e.g. hold out all of Ohio/Nebraska), then score.
3. **Effective-depth realism.** Compare predicted newly dry/flooded acres to satellite masks on the day of an extreme level (Landsat/Sentinel), for TVA and Duke lakes where no contour truth exists.
4. **Datum audit.** Verify TVA/Santee/Duke datum statements against the operator documents (not done).
5. **Southeast truth.** Obtain at least 5 hydroacoustic surveys from GA/SC/AL/TN reservoirs (blocker).
