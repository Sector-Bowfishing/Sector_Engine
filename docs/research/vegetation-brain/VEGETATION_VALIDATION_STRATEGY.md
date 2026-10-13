# Vegetation Brain — Validation Strategy

**RESEARCH ONLY. Proposed Brain.** Principle: **never validate a satellite classification against another satellite classification.** Ground truth = dated field survey, point-intercept, agency habitat map, or sonar biovolume.

## 1. Ground-truth inventory and what each can validate

| Truth | In hand? | Validates | Weakness |
|---|---|---|---|
| Snohomish County WA dated polygons (5 lakes, 2021–2023) | **Yes** (used) | floating-leaf presence/density, precision/recall/IoU | small clear lakes, absence assumed, one region |
| FL FWC LTM point intercepts (96k pts, 7 lakes tested; 10 fleet lakes named) | **Yes** (used) | recall, class mix (presence-only) | no absences → precision unusable |
| EPA NLA 2017 station cover codes (47 fleet lakes with cover rows) | **Yes, not yet scored vs S2** | class + density bins nationwide | shoreline plots only; one 2017 summer date |
| FWC sonar BioVolume rasters 2015–2023 | Services listed but **hang** (no pixel data); lake-level sonar PAC/PVI served and **used** | submerged proxy at lake level | pixel × depth truth unobtainable today; FL only |
| USGS UMR LTRM CSV (1998–2019 presence) | Yes | species presence in Mississippi pools | few fleet lakes, turbid |
| UMN Minnesota dataset (372k points, 1,520 lakes) | No (browser download) | MN clear natural lakes, abundance subset | unverified layout |
| WI DNR point-intercept, TVA annual surveys, TPWD, SFWMD Okeechobee | Request-only | large reservoirs (the bowfishing core) | access, PDFs |
| NWI | Yes (REST) | prior only | not dated; **not used as truth** |

## 2. What has been validated so far (campaign results)

| Metric | Result | Status |
|---|---|---|
| Presence AUC, floating-leaf, PNW, shore-matched | 0.98–0.995 | measured (5 lakes) |
| Presence recall, Sector rule, PNW | 0.993 (FPR 9.9 %) | measured |
| Presence recall, Sector rule, FL surface | 0.60 single / 0.74 composite | measured, presence-only |
| IoU / F1 floating-leaf best threshold | 0.92–0.95 / 0.96–0.97 | measured (in-sample); LOLO F1 0.94–0.97 |
| Submerged AUC | 0.57–0.77 PNW, 0.57–0.69 FL | measured: not usable |
| Density-class accuracy | **not measured** | open |
| Seasonal change accuracy | **not measured** | open |
| Cell-level rule vs Snohomish polygons | precision 0.54 closest date, **0.92 with pass acceptance**, 1.00 with median persistence (60 positive cells) | measured, tiny sample |
| Cell recall vs FL surface points | 0.32 single date; 0.43–0.54 with persistence | measured, presence-only |
| Lake-level vs FWC sonar (130 lake-years) | Spearman 0.43 (PVI), 0.35 (PAC); AUC 0.79–0.84 for high vs low volume | measured, lake-clustered |

## 3. Metric set (pre-register before scoring any lake)

For each class × region × clarity stratum:
- **Presence:** precision, recall, F1, IoU, AUC (shore-matched), false-positive rate on verified open water, balanced accuracy.
- **Density:** weighted-kappa on 4 classes, within-one-class agreement, MAE of cover fraction vs NLA/FWC/polygons.
- **Seasonal change:** onset/peak/dieback date error (days) vs repeated surveys (FWC LTM repeats 2015–2023; WI/MN repeats), and week-class agreement for the seasonal prior vs naive climatology.
- **Submerged:** recall/precision vs sonar biovolume by canopy-height/depth ratio and clarity; the point of first detectability.
- **Calibration:** reliability curve of confidence vs correctness; Brier score.
- **Refusal quality:** share refused, and accuracy of what was *not* refused (refusals must not hide errors).

## 4. Protocol rules (learned the hard way in this campaign)
1. **Shore-distance match** negatives to positives; otherwise NIR alone scores AUC 0.998.
2. **Survey–image gap ≤ 7 days** for headline scoring; report 8–30 d separately.
3. **Presence-only truth** (FWC points, NAS, EDDMapS) supports **recall only**; never report precision/FPR from it.
4. **Leave-one-lake-out** (and leave-one-region-out) for any learned or threshold-tuned component; report per-lake, not only pooled.
5. **Spatial autocorrelation:** bootstrap by polygon/lake (blocks), not by pixel, for confidence intervals.
6. **Check processing baseline per collection** (the reflectance offset trap).
7. **Freeze thresholds before scoring a new region**; tune only on a disjoint calibration set.
8. **No self-validation:** a second satellite product (Dynamic World, NLCD, a Sentinel-1 classification) is never truth.
9. **Negative controls:** include known vegetation-free lakes (17 fleet lakes with NLA submergent cover ≈0) to measure false positives.

## 5. Staged validation plan

| Stage | Data | Goal | Gate |
|---|---|---|---|
| V0 (done) | Snohomish + FWC | first honest measurement | report `notes/04…` |
| V1 (partly done) | Sector rule cell-level (done) + lake-level sonar (done) + **pixel BioVolume (blocked)** | submerged detectability envelope; cell-level FPR | envelope "beds with canopy ≳40 % of water column" documented; pixel-level confirmation pending |
| V2 | NLA 2017 × S2 summer 2017 on 47 fleet lakes + 17 negative controls | class + density calibration across regions | density kappa and false-positive rate reported per region |
| V3 | UMN MN + UMR LTRM + WI | turbid and northern lakes; clarity transfer | per-regime thresholds |
| V4 | TVA/TPWD/SFWMD/WI requests | large reservoirs, dense hydrilla | agreement with agency acreage by lake-year |
| V5 | Seasonal back-test on 2017–2025 S2 history for ~60 lakes | seasonal prior vs naive climatology | beats naive by pre-registered margin per regime |
| V6 | Field/user feedback + sonar crowd | density→bowfishing "too dense" threshold; deep SAV | agreement with user labels |

## 6. Honest known unknowns
No clarity stratification; no turbid-reservoir truth; no winter/dormant truth; the density ladder cutoffs are estimates; every large-reservoir number in this research is from outside the validated set.
