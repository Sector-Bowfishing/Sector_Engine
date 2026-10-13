# Depth Brain: shallow-zone inference without bathymetry (draft)

Research only. Date 2026-10-13. Thread: terrain. Scripts: `research/depth-brain/terrain_*.py`. Data: `docs/research/depth-brain/data/` (`shallow_proxy_validation.json`, `shallow_proxy_lake_table.csv`, `shallow_spatial_validation.json`, `sat_hypso_validation.json`, `mn_dnr_truth.json`, `contour_interval_error.json`). Ledger: `ledger/terrain.jsonl`. Raw downloads (not in git): `~/Desktop/Development/Sector_Research_Data/depth-brain/terrain/`. Builds on `docs/research/lake-brain/LAKE_BRAIN_CONTEXT_RESEARCH.md` section 4.

## 1. Executive summary

Question: with no bathymetry, what scalable evidence says where shallow water and flats are? Every candidate was scored against real depth data: 33 USACE storage curves (CWMS), 63 Texas hydrographic surveys (TWDB area-capacity tables, 18 of them with 1-ft or 2-ft contours rebuilt as depth rasters), and 9 Minnesota DNR contour sets (5-ft or 10-ft interval). No result below was tuned on its own truth set except where marked "LOO" (leave-one-out).

| # | Finding | Numbers |
|---|---|---|
| 1 | **The 3DEP shoreline-slope proxy ranks lakes well on USACE storage lakes and only moderately on Texas surveys.** The prior CWMS result reproduces (Spearman 0.77, n = 33). On 63 independent TWDB lakes it falls to 0.44 for area change per foot, and for "share of the surface within 3 ft of the surface" (S3) to 0.41. | CWMS n=33: Spearman 0.77, 85 % within a factor 2. TWDB n=63: 0.44, 65 % within a factor 2 (a constant gets 87 %). Pooled n=96: 0.65. |
| 2 | **For the share of a lake that is shallow, the proxy adds nothing to a constant.** Calibrated by leave-one-out on 63 Texas lakes, S3 MAE is 0.039 versus 0.041 for the median (S6: 0.074 vs 0.079; S10: 0.114 vs 0.127). Raw (uncalibrated) 3x P_dem overshoots by +0.11 of the surface. | `shallow_proxy_validation.json` |
| 3 | **Classifying a lake as "broad shallow" (top third of S3) is weak outside the CWMS set.** AUC 0.69 on TWDB (accuracy 68 %, where answering "no" for every lake scores 67 %); AUC 0.85 and accuracy 82 % on CWMS rel-per-foot. Perimeter-to-area alone scores AUC 0.68 on Texas, so the DEM adds little there. | table 5.3 |
| 4 | **The proxy fails where the land beside the polygon is a flat floodplain but the basin is a flooded valley.** Livingston (predicted 0.27 per ft, true 0.029), Houston, Jim Chapman, Conroe, Bryan, plus Enid and Caddo in the prior set. Failure mode: 3DEP shows the river bottomland, not the drowned channel. | section 5.2 |
| 5 | **Per-segment slope predicts WHERE shallow water is only weakly.** Across 27 lakes with real contours (18 Texas, 9 Minnesota) the Spearman of segment slope (10-60 m) against the share of the 0-100 m band that is within 3 ft is -0.29 mean in Texas (16 of 18 lakes the right sign) and -0.16 in Minnesota (7 of 9). Top-third AUC 0.69 (TX) and 0.62 (MN). | section 5.4 |
| 6 | **Distance to shore from the polygon is the dominant spatial predictor, and slope adds a little.** Cell-level AUC for "3 ft or shallower" (leave-one-lake-out logistic) is 0.896 with distance alone and 0.914 with distance + slope in Texas (slope helps in 13 of 18 lakes); in Minnesota 0.869 and 0.861 (helps in 4 of 9). Cove / narrow-arm flag alone: AUC 0.72 (TX), adds zero after distance. | section 5.4 |
| 7 | **A "flat-segment" mask is not a better flats map than the plain shore band.** Water within 100 m of shore on segments flatter than 2 degrees: precision 0.41, recall 0.51, IoU 0.28 for depth <= 3 ft. The whole 100 m band regardless of slope: precision 0.32, recall 0.81, IoU 0.29. | section 5.4 |
| 8 | **Longer slope profiles (30-100 m, 60-200 m, bank rise at 200 m) do not help.** Ranks lakes about as well (0.70-0.71 on CWMS) but calibrate worse (x2 high), and within a lake the 60-200 m slope has the wrong sign (+0.10). The 10-60 m slope is the only informative window. | tables 5.1, 5.4 |
| 9 | **JRC occurrence / seasonality is misleading as a shallow-flats score.** The share of a lake in the 5-95 % occurrence band has Spearman -0.70 against CWMS area change per foot (n = 11, SE tile). | section 5.5 |
| 10 | **Drawdown-exposed terrain from Landsat water masks is the best scalable within-lake evidence found, but only where the level moves.** For 5 Texas lakes with level series spanning 8-25 ft, per-pixel inundation-threshold elevation versus TWDB contour depth: Spearman 0.87-0.93 on four lakes (0.58 on Fork, flooded timber), MAE 0.4-1.4 ft; distance to shore alone gives 0.22-0.54. It recovers 24-75 % of the cells inside the observed level range and about half of the cells at 3 ft or less (three lakes). Lake-wide shallow shares are biased low (S3 0.035-0.042 vs 0.059-0.101 true on four lakes). | table 5.5 |
| 11 | **A real contour map is only as good as its interval.** Rebuilding the shallow bottom from every 5th or 10th 1-ft contour of 10 TWDB lakes gives depth RMSE 1.3 ft (5-ft interval) and 2.8 ft (10-ft interval, bias -1.6 ft), against 0.28 ft for 2-ft. State lake maps at 5-10 ft cannot locate a 0-3 ft flat. | section 5.6 |
| 12 | **Recommendation.** Treat shoreline slope as a lake-level coarse prior and as a minor within-lake tiebreaker, never as a flats map. Use real contours where they exist (TWDB, state DNR at 2 ft or finer), Landsat drawdown-exposure where the level swings 8 ft or more and a level series exists, and distance-to-shore and cove geometry from the polygon as the free spatial baseline. Do not build a per-segment "flats" layer from slope. | section 7 |

## 2. Data used (truth and predictors)

| Data | What | Coverage | Access |
|---|---|---|---|
| USACE CWMS storage vs pool (prior thread) | measured area change per foot near full pool, `rel_per_ft` | 33 lakes after the R2 / unit gate | CWMS Data API |
| TWDB hydrographic surveys | elevation-area-capacity tables (0.1 ft), conservation-pool polygon, 1-ft or 2-ft contours | 91 surveys listed; 68 usable (pool polygon matched to table area), 63 of 250 acres or larger and S3 < 0.9; 3 directory-lake gaps (Buchanan, Travis, Possum Kingdom: no usable polygon) | twdb.texas.gov survey zips fetched by HTTP range (the 0.4-1.9 GB zips were not downloaded whole) |
| TWDB contours rebuilt as depth rasters | depth-below-pool at 15 m by linear TIN on contour vertices | 18 lakes | `terrain_contour_depth.py`; reproduces the table S3 within 0.005 on 15 of 18 lakes (misses: Diversion 0.175 vs 0.204, Houston 0.143 vs 0.130, Jim Chapman 0.085 vs 0.094) |
| Minnesota DNR lake bathymetry | contour lines (5 or 10 ft interval) and outline polygon | 9 of the 14 Minnesota directory lakes matched (Gull, Bemidji, Minnetonka, Winnibigoshish, Leech, Mille Lacs, Otter Tail, White Bear, Pepin); Vermilion not found by name | enterprise.gisdata.mn.gov MapServer `water_lake_bathymetry` (layers 0 and 1) |
| USGS 3DEP DEM | elevation at 5-200 m outside the polygon edge | 33 + 63 + 9 lakes, 600 points each (150 m spacing, 7 offsets for the 27 spatial lakes) | ImageServer `getSamples`, 1 m lidar where available |
| Landsat 5/7/8/9 Collection 2 L2 | green, SWIR1 (MNDWI > 0 = water), QA | 5 TX lakes, 2000-2026, 224-430 usable scenes each | Microsoft Planetary Computer STAC, COG windows |
| TWDB daily lake level | `waterdatafortexas.org/reservoirs/individual/<lake>.csv` | pairs Landsat scenes with level | public CSV |
| JRC GSW v1.4 (prior) | occurrence / seasonality shares in `gsw_features.json` | 11 CWMS lakes in the SE tile | prior thread |

Truth definitions. From an area-capacity table with pool elevation P (found where the table area equals the mapped pool-polygon area): `S_d = (A(P) - A(P - d)) / A(P)` is the share of the pool surface whose bottom is within d feet of the surface; `rel_per_ft` is the share of the surface gained per foot of rise near the top. The raster depth truth is checked against S3 and S6 of the table for each lake (section 2 table).

## 3. Methods

**Lake-level predictors.** `P_dem = perimeter x median(run per vertical foot) / area`, where run = 1 / tan(slope from 10 m to 60 m outside the shoreline) (the prior proxy). Extended variants use the 30-100 m slope (`P_dem_30_100`) and the rise from 5 to 200 m (`P_dem_200`). Polygon-only predictors: perimeter / area, share of surface within 50 / 100 / 200 m of shore, share removed by a 150 m morphological opening ("narrow water", arms narrower than 300 m).

**Calibration.** Raw: `S3 = min(1, 3 x P_dem)`. Calibrated: log10 S = a + b log10 P fitted on the other lakes (leave-one-out). Reported with MAE and bias in share-of-surface units.

**Segments.** Shoreline cut into 500 m arc segments (about 3 DEM points of 150 m spacing at least). Truth per segment: share of water cells within 100 m of shore, assigned to the nearest shore point (within 400 m), with depth <= 3 ft (<= 6, <= 10 also computed). Tests: segment Spearman, top-third AUC, mask precision / recall / IoU, and a cell-level leave-one-lake-out logistic ranking of "depth <= d".

**Satellite hypsometry.** One Landsat path/row per lake (modal grid), scenes with <= 3 % cloud/shadow/fill inside the pool polygon + 150 m, water = MNDWI > 0. Each scene is paired with the daily level. Lake-wide: monotone fit of wet area against level gives dA/dz and S_d. Per pixel: the threshold elevation (wet iff level > e) minimising misclassification over the scenes; pixels with >= 40 valid scenes, <= 10 % misfit and >= 5 scenes on each side count as informative; satellite depth = pool - e.

**Contour-interval error.** Rebuild the depth grid from every 2nd, 5th or 10th contour (counted down from pool) and compare with the 1-ft grid over cells shallower than 10 ft.

## 4. What was not done

* Sentinel-2 (10 m): same method, but 2015+ only and shorter drawdown history; not run.
* JRC monthly water history (Earth Engine only) was not available; Landsat QA/MNDWI masks stand in for it.
* Tributary-mouth flats: the NHD mouth count was already shown not to discriminate (context research 4.1); not repeated. The polygon narrow-arm flag is the stand-in.
* No TVA, Duke or Santee lake has contour truth in this study.

## 5. Results

### 5.1 Lake level: area change per foot (`rel_per_ft`)

| Predictor | CWMS n=33 Spearman | CWMS log10 RMSE | CWMS within x2 | TWDB n=63 Spearman | TWDB within x2 | Pooled n=96 Spearman |
|---|---|---|---|---|---|---|
| P_dem (10-60 m slope) | **0.77** | 0.22 | 85 % | 0.44 | 65 % | 0.65 |
| P_dem_30_100 | 0.71 | 0.35 | 61 % | 0.46 | 38 % | 0.65 |
| P_dem_200 (rise at 200 m) | 0.70 | 0.40 | 52 % | 0.44 | 32 % | 0.62 |
| slope alone (10-60 m median, sign flipped) | 0.74 | n/a | n/a | 0.31 | n/a | 0.53 (n=105) |
| perimeter / area | -0.16 | n/a | n/a | 0.41 | n/a | 0.31 |
| share of surface within 100 m of shore | -0.23 | n/a | n/a | 0.36 | n/a | 0.17 |
| constant (median truth) | n/a | 0.33 | 76 % | n/a | 87 % | 76 % |

Sign of perimeter / area flips between sets: on CWMS lakes (large plains and mountain reservoirs) it carries no information, in Texas it is as good as the DEM. The DEM adds information in the first set and little in the second.

### 5.2 Lake level: share of surface within 3, 6, 10 ft (Texas, n = 63, truth from area-capacity tables)

Truth spread (10th / 50th / 90th percentile): S3 0.061 / 0.095 / 0.199, S6 0.132 / 0.196 / 0.369, S10 0.223 / 0.329 / 0.570. Texas reservoirs are a narrow population, so a constant is a hard baseline.

| Target | Predictor | Spearman | MAE | bias | log10 RMSE | within x2 |
|---|---|---|---|---|---|---|
| S3 | 3 x P_dem, raw | 0.41 | 0.124 | +0.110 | 0.395 | 65 % |
| S3 | P_dem, LOO log-linear | 0.36 | 0.039 | -0.011 | 0.212 | 89 % |
| S3 | P_dem_30_100, LOO | 0.42 | 0.038 | -0.011 | 0.203 | 87 % |
| S3 | perimeter / area, LOO | 0.27 | 0.041 | -0.011 | 0.209 | 86 % |
| S3 | constant median | n/a | 0.041 | -0.015 | 0.216 | 86 % |
| S6 | P_dem, LOO | 0.39 | 0.074 | -0.019 | 0.198 | 95 % |
| S6 | constant median | n/a | 0.079 | -0.030 | 0.205 | 87 % |
| S10 | P_dem, LOO | 0.43 | 0.114 | -0.023 | 0.162 | 95 % |
| S10 | constant median | n/a | 0.127 | -0.051 | 0.184 | 89 % |

Largest P_dem misses (predicted 3 x P_dem vs true S3): Livingston 0.82 vs 0.094, Jim Chapman 0.70 vs 0.094, Big Creek 0.71 vs 0.284, Bryan 0.65 vs 0.077, Houston 0.63 vs 0.130, GCWA 0.63 vs 0.017. The big ones (Livingston, Jim Chapman, Houston, Conroe) sit in flat East Texas / Gulf-plain terrain where the DEM beside the shore is bottomland; the small ones (GCWA, Bryan, Big Creek, under 4 km2) have so few shore points beside the polygon edge that one flat reach dominates. These are the pattern, not a diagnosis: no check of canopy or lidar-water artefacts was run.

Transfer to Minnesota (calibrated on Texas, n = 9 lakes, truth S10): P_dem Spearman 0.30, 30-100 m variant 0.68, log10 RMSE 0.19-0.20, within x2 89 %, against a Texas-median constant at 0.23 / 89 %. Share of surface within 100 m of shore alone: Spearman 0.73. n is too small to rank the predictors; none is better than a constant in absolute error.

### 5.3 Classification: "broad shallow" lake (top third of the truth)

| Set (truth) | n (positives) | AUC P_dem | accuracy top-third P_dem | AUC perimeter / area | AUC share within 100 m | baseline accuracy (all "no") |
|---|---|---|---|---|---|---|
| CWMS rel-per-foot >= 0.0267 | 33 (11) | **0.85** | **82 %** | 0.39 | 0.35 | 67 % |
| TWDB S3 >= 0.117 | 63 (21) | 0.69 | 68 % | 0.68 | 0.68 | 67 % |
| TWDB S6 >= 0.241 | 63 (21) | 0.71 | 68 % | 0.67 | 0.65 | 67 % |

### 5.4 Within a lake: does per-segment slope say where the shallows are?

27 lakes, no exclusions: 18 Texas (Bardwell, Bob Sandlin, Brownwood, Bryan, Cedar Creek, Cherokee, Coleman, Conroe, Diversion, Eagle Mountain, Fork, Granbury, Houston, Hubbard Creek, Jim Chapman, Lavon, Striker, Tawakoni) and 9 Minnesota. Depth truth in Texas is 1 ft or 2 ft contours; Minnesota is 5 or 10 ft, so its <= 3 and <= 6 ft shares are linear interpolation inside the first contour interval (an assumption) and the <= 10 ft columns are the reliable ones.

| Test | Texas (18) | Minnesota (9) |
|---|---|---|
| Spearman, segment slope 10-60 m vs share <= 3 ft in the 0-100 m band: mean (lakes with negative sign) | -0.29 (16) | -0.16 (7) |
| ... vs share <= 10 ft | -0.21 (15) | -0.16 (6 of 8) |
| Spearman, 30-100 m slope vs share <= 3 ft | -0.09 (15) | -0.10 (6) |
| Spearman, 60-200 m slope vs share <= 3 ft | +0.10 (4 negative) | -0.05 (6) |
| Spearman, bank rise to 200 m vs share <= 3 ft | -0.06 (13) | -0.12 (7) |
| top-third AUC of 10-60 m slope, share <= 3 ft | 0.69 | 0.62 |
| Mask depth <= 3 ft, water <= 100 m from shore, slope < 1 deg: precision / recall / IoU | 0.45 / 0.36 / 0.24 | 0.71 / 0.28 / 0.26 |
| ... slope < 2 deg | 0.41 / 0.51 / 0.28 | 0.70 / 0.39 / 0.34 |
| ... slope < 4 deg | 0.36 / 0.70 / 0.30 | 0.68 / 0.48 / 0.39 |
| ... whole 100 m band, any slope (baseline) | 0.32 / 0.81 / 0.29 | 0.66 / 0.61 / 0.45 |
| Cell-level AUC depth <= 3 ft, leave-one-lake-out: distance only | 0.896 | 0.869 |
| ... distance + slope | 0.914 | 0.861 |
| ... distance + slope + narrow-arm flag | 0.912 | 0.861 |
| ... slope only | 0.62 | 0.56 |
| ... narrow-arm flag only | 0.72 | 0.54 |
| Lakes where slope improves the distance-only AUC | 13 of 18 | 4 of 9 |
| Cell-level AUC depth <= 10 ft, distance only / distance + slope | 0.803 / 0.815 | 0.793 / 0.786 |

Reading. Steeper nearby banks do go with less shallow water in most lakes (the sign is right in 23 of 27), and a slope gate raises precision, but with a weak effect size. The polygon alone (distance to shore) already separates shallow from deep with AUC near 0.9 in the first 300 m; slope lifts that by 0.02 in Texas and by nothing in Minnesota. A slope-defined flats mask trades recall for precision without beating the plain shore band on IoU. Minnesota's glacial lakes have steep drop-offs behind many flat-looking banks; Texas reservoirs flood valleys whose bank slope is a weaker guide to basin slope.

### 5.5 Satellite hypsometry from drawdown (Landsat water masks vs known level)

| Lake (level range seen, ft; usable scenes) | Spearman sat depth vs TWDB contour depth | same for distance to shore | partial Spearman given distance | MAE ft (distance-only isotonic MAE) | cells in observed range recovered | <= 3 ft cells recovered / precision | dA/dz sat vs table, ac/ft | S3 sat vs table |
|---|---|---|---|---|---|---|---|---|
| Lavon (24.2; 224) | 0.93 | 0.32 | 0.93 | 0.94 (2.45) | 67 % | 47 % / 0.57 | 373 / 491 | 0.038 / 0.059 |
| Tawakoni (15.1; 252) | 0.93 | 0.31 | 0.93 | 0.83 (2.00) | 63 % | 46 % / 0.71 | 507 / 885 | 0.035 / 0.078 |
| Brownwood (18.2; 430) | 0.93 | 0.54 | 0.90 | 1.39 (3.16) | 75 % | 53 % / 0.61 | 180 / 206 | 0.090 / 0.089 |
| Cedar Creek (7.9; 238) | 0.87 | 0.23 | 0.86 | 0.44 (0.99) | 40 % | 22 % / 0.82 | 509 / 1,006 | 0.035 / 0.077 |
| Fork (8.4; 330) | 0.58 | 0.22 | 0.56 | 1.07 (1.39) | 24 % | 6 % / 0.64 | 449 / 722 | 0.042 / 0.101 |

Reading. When the level has moved through the zone, the threshold elevation of each pixel is a real bathymetric measurement, far better than distance to shore (0.87-0.93 vs 0.22-0.54), with MAE about 1 ft over the 1-15 ft range it covers. It only speaks for cells between the lowest and highest level seen, so it says nothing about the deep end, and it needs dozens of clear scenes at low pool (usable scenes with the level at least 3 ft below pool: Lavon 113, Tawakoni 49, Brownwood 263, Cedar Creek 58, Fork 85; at least 6 ft below: 40, 21, 173, 4, 28). The lake-wide area-change slope and the S3 share are biased low in four of five lakes (dA/dz by 12-50 %, median about 40 %; S3 about half of truth in four lakes; Brownwood matches), consistent with 30 m pixels missing vegetated and mixed shallows. Fork, the lake with flooded timber and a smaller range, is the weak case. Fixed bias, not noise, so a lake-wide correction would be needed before quoting acres.

### 5.6 How coarse can the contour source be? (10 TWDB lakes, 1-ft truth, shallower than 10 ft)

| Contour interval used | depth RMSE | MAE | bias | P90 abs error | S3 estimated (true 0.112) | IoU of the <= 3 ft mask |
|---|---|---|---|---|---|---|
| 2 ft | 0.28 ft | 0.16 | -0.07 | 0.5 ft | 0.122 | 0.93 |
| 5 ft | 1.30 ft | 0.86 | -0.51 | 2.3 ft | 0.140 | 0.78 |
| 10 ft | 2.81 ft | 2.04 | -1.63 | 4.9 ft | 0.218 | 0.52 |

Linear interpolation between sparse contours pulls the shallows toward the contour depth, so shallow areas are overstated and depth is biased shallow. A Minnesota map with a 10-ft first contour cannot say which cells are 4 ft deep. This number feeds the uncertainty budget in the effective-depth document.

### 5.7 JRC Global Surface Water, static layers

Against CWMS area change per foot on the 11 lakes inside the one downloaded tile: Spearman of the fluctuating-water share is -0.70, of the 150 m ring-to-polygon ratio +0.02, while the DEM proxy on the same 11 lakes scores +0.67. A wide fluctuating zone in the mask reflects long drawdowns of a lake that is steep (Hartwell), not wide flats. Keep JRC only as a source of water masks (section 5.5), not as an occurrence score.

## 6. Limits

* Sample sizes: 33, 63, 27 (spatial), 9 (Minnesota), 5 (Landsat). Texas is one physiographic family of lakes; the 63 lakes have a narrow truth range, which makes the constant baseline hard and the rank correlation noisy. Minnesota truth is coarse. No TVA, Duke or Santee lake is in the truth set.
* The truth depth is relative to pool at survey time; the DEM predictor describes the bank above the water line. The two coincide only if the bank and the bed share a slope, which the data say holds weakly.
* Landsat is scene-limited by clouds and 30 m pixels, and only for lakes with a level series (417 bound lakes, 175 of the delta-eligible ones with 10 years of history).
* All cell-level truth comes from interpolated contours (linear TIN), validated against table shares to within 0.005 on most lakes, but never against sonar points.
* 57 of the 63 lakes are outside the 621-lake directory; transfer to directory lakes is by inference. Directory lakes among the 63: Texoma, Livingston, Tawakoni, Cedar Creek, Fork, Conroe (the last four also have contour rasters in the spatial test; Texoma has only 5-ft contours and Livingston's 639 MB contour layer was not rebuilt).

## 7. Recommendation

1. **Ship, if anything, a lake-level "shoreline gradient" class** (steep / mixed / flat from the 10-60 m slope), tagged low confidence and described as a ranking aid. It is useful on USACE-type reservoirs (AUC 0.85, n = 33) and weak on Texas plains reservoirs (0.69, n = 63). Do not publish predicted acres of shallows or a shallow-water percentage from it; for the Texas set it does no better than a constant.
2. **Do not build a per-segment flats layer from slope.** Segment slope carries a faint signal (mean Spearman -0.29, AUC 0.69 in Texas) that polygon distance-to-shore already dominates. If a spatial "likely shallow" hint is wanted at all, use the free polygon baseline: cells within about 100 m of shore (AUC 0.80-0.90 for 3-10 ft), with cove / narrow-arm geometry as a label, not slope.
3. **Spend effort on real contours.** TWDB (91 surveys, 63 matched here; Buchanan, Travis, Possum Kingdom need a manual polygon) and any state or agency data at 2 ft or finer give shallow-zone truth at 0.3-1 ft. Use 5-10 ft maps only for "shallower than first contour" and say so (RMSE 1.3 to 2.8 ft).
4. **Pilot Landsat drawdown-exposure on lakes that move.** It is the only bathymetry-free signal found that locates flats inside a lake (Spearman 0.87-0.93 on four of five lakes). Candidates are the 134 bound lakes whose 5-95 % level range is at least 4 ft (effective-depth document, section 5). Output should be a per-lake low-water bottom-elevation map with an explicit coverage mask and the low bias in area noted. Cost seen: 750-1,000 scenes per lake, three window reads per scene; about 20-30 minutes per lake with 8 reader threads on a home connection, so ~134 lakes is a day or two of fetching, not a pipeline decision.
5. **Retire JRC occurrence and long-profile slope variants** from the candidate list; keep 3DEP 10-60 m only.
6. **Pre-registered next tests** (cheap): (a) repeat the 10-60 m proxy on the 74 NWDM CWMS storage locations the prior thread listed, (b) add Sentinel-2 drawdown masks for the 2015+ record on three of the five lakes and compare with Landsat, (c) add 5 more states with 2-ft-or-finer contours (Ohio, Indiana, Oklahoma OWRB, Kansas KDWP, Arkansas) to test whether the poorer Texas result is regional.

## 8. Files

Scripts: `terrain_dem_profile.py` (3DEP profile sampler), `terrain_features.py`, `terrain_twdb_fetch.py`, `terrain_twdb_truth.py`, `terrain_contour_depth.py`, `terrain_mn_dnr.py`, `terrain_proxy_validation.py`, `terrain_spatial_test.py`, `terrain_sat_hypso.py` (fetch / analyze / summary), `terrain_contour_interval_error.py`, `terrain_stats.py`. Run order: fetch TWDB, truth, DEM profile, contour depth, validation; the venv Python (`lake-brain/context/venv`) has no scikit-learn, so `terrain_stats.py` supplies the logistic and isotonic fits. Re-running needs about 35 minutes of 3DEP sampling for 100 lakes (the service is latency-bound at about 7 s per request) and 20-30 minutes per Landsat lake.
