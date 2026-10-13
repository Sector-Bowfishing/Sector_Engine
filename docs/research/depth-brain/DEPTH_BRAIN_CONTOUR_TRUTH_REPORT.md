# Depth Brain: real-contour bathymetry truth for the fleet, and a re-test of GLOBathy and the cheap proxies

Research only. Date 2026-10-13. Thread: contour truth. Scripts `research/depth-brain/contour_*.py`; data `docs/research/depth-brain/data/contour_*`; ledger `ledger/contour.jsonl`. Raw downloads, rasters and the merged segment table live outside git in `~/Desktop/Development/Sector_Research_Data/depth-brain/contour/`.

## 1. Executive summary

| # | Finding | Numbers |
|---|---|---|
| 1 | **140 of 621 fleet lakes are now matched to REAL measured contours or hypsometry by geometry, not by name.** Every contour group in 20 sources was tested against every one of the 599 fleet polygons (contours inside the polygon, name as a secondary flag). Scout name candidates were mostly confirmed (3 rejected for polygon extent mismatch: Buckeye Lake OH polygon is 0.003 km2, Marion Reservoir KS 0.565 km2, Crescent Lake FL). 59 pairs stay `name_only_unverified` (USGS index/catalog, not downloaded). | 134 lakes from contours + 6 TWDB lakes verified by pool-polygon overlap; 182 verified pairs, 33 rejected, 59 name-only |
| 2 | **102 lakes carry usable shallow-zone truth** (data-quality tiers A 76, B 26; 35 lakes are tier C and excluded). A = whole lake, contour steps of 3 ft or less (or 5 ft on a lake at least 25 ft deep). B = 10-ft steps on a lake at least 40 ft deep, or 65-85 % coverage. C = partial lakes (e.g. Rainy Lake covered 2.6 %, Michigan band files), steps over 10 ft (Chelan 100 ft, NH 20 ft), datum or top-of-survey doubts. | by source (A+B): WV 12, OH 10, NE 10, MN 10, KS 8, MA 8, CT 7, FL 7, TWDB 6, NH 6, MT 5, OK 4, ND 3, plus six single-lake sources (PA, MI, WA, IL, IN, NJ). Lake type (A+B): reservoir 66, regulated natural 26, natural 10 |
| 3 | **The contour-to-shares method is accurate enough.** On 18 real TWDB lakes the shares match exact area-capacity tables to MAE 0.010-0.013 (1-2 ft ladder), 0.015-0.026 (5-ft ladder). A 10-ft ladder overstates the share shallower than 6 ft by +0.05 (MAE 0.053). Independent MN extraction by the terrain thread agrees (9 lakes, MAE 0.024 on share < 6 ft; one outlier because that thread used the DNR pool outline, 66.7 km2, against the fleet polygon, 55.6 km2). | section 4 |
| 4 | **What a bowfishing lake looks like in real data (tier A, n = 76):** median 9 % of area is 0-3 ft, 9 % is 3-6 ft, 11 % is 6-10 ft, 69 % is deeper than 10 ft. Share shallower than 6 ft: median 18 %, 10th to 90th percentile 8.5-41 %. Median shore-to-6-ft distance is only 38 m (10th to 90th percentile 10-220 m); on 43 % of the shoreline (median lake) the 6 ft contour is within 30 m. Flats at least 200 m wide: median lake 55 ha in 3 patches; 23 of 96 lakes have none. | section 5 |
| 5 | **GLOBathy fails again with a larger, independent truth.** Dmax vs contour maximum depth (73 lakes, modeled Dmax only): Spearman 0.18 (95 % CI -0.08 to 0.41), within 2x 66 % against 62 % for a constant guess. Share of area shallower than 1.8 m (5.9 ft), n = 55 tier-A lakes: MAE 0.14 vs 0.13 for a constant, Spearman 0.09 (-0.20 to 0.37), AUC for the broad-shallow third 0.53 (0.35 to 0.69). All three thresholds fail the same way. | section 6.1 |
| 6 | **No available proxy picks out broad-shallow lakes.** Top third of share < 6 ft (cut at 21 %), tier A: HydroLAKES/NID mean depth AUC 0.62 (0.48-0.76), GLOBathy Dmax 0.59 (0.42-0.75), log area 0.56, frac_within_100m 0.54, frac_narrow_300m 0.55, GLOBathy shallow share 0.53; every interval includes 0.5. Leave-one-STATE-out ridge models (17 states) do not beat the constant (MAE 0.13): polygon-only 0.16, GLOBathy 0.14, polygon plus mean depth 0.15. **Best single predictor: HydroLAKES/NID storage-over-area mean depth (AUC 0.62, Spearman 0.18).** | section 6.2 |
| 7 | **The lever is mean depth.** The same lakes ranked by their true contour mean depth give AUC 0.91 (0.83-0.97), Spearman 0.76; by true maximum depth AUC 0.79. Dmax-based modelling cannot reach mean depth (GLOBathy mean depth Spearman 0.20 against contour mean depth, n = 17). | section 6.3 |
| 8 | **Polygon geometry does predict WHERE-in-the-lake width, not share.** frac_within_100m and frac_narrow_300m correlate with the 0-3 ft share (Spearman 0.35 and 0.39, CIs excluding 0) but not with the < 6 ft share. They correlate strongly NEGATIVELY with the median shore-to-6-ft distance (-0.66, -0.60): they are mostly size proxies (small lakes are steeper and have a larger shoreline fraction). Treat them as "small and steep", not "broad and shallow". | section 6.2 |
| 9 | **Within a lake, 3DEP shoreline slope is a modest but real signal; distance from shore does most of the work.** 46 fleet lakes with contours and 3DEP: per-lake Spearman of 10-60 m slope against the share of the near-shore band that is <= 6 ft is -0.24 on average (CI -0.32 to -0.16; 33 of 44 lakes negative). A slope-aware shallow-zone mask beats a constant-width mask by +0.036 IoU (CI 0.005 to 0.073; 26 of 44 lakes), but cell-level AUC rises only 0.818 to 0.822 (CI of the lake-level change -0.015 to 0.022). | section 7 |
| 10 | **Recommendation.** Use the real contours as lake-specific truth for the 102 tier-A/B lakes (publish only derived metrics; never raw FL FWC data). For the other ~520 fleet lakes do not model "flats"; return "unknown" until a mean-depth source exists. Ranking the unknown lakes: HydroLAKES/NID mean depth is the only cheap input with any signal, and it is weak. The best acquisitions are more state and USACE contour sources, not another model. | section 9 |

## 2. Data and matching

**Sources used (20 contour sources, all downloaded by the scout thread)**: MN DNR, WV DNR, OH DOW, NE NGPC, KS KBS, MA MassWildlife, CT DEEP, FL FWC, NH GRANIT, MT FWP, OK OWRB, ND G&F, WA Ecology, MI DNR/IFR, IN DNR, NJDEP, IL IDNR, plus PA Harveys Lake, UT Utah Lake, WI Chippewa Flowage (DRAFT). TWDB area-capacity tables (terrain thread, read-only) add 6 fleet lakes. Anchors for maximum depth: EPA NLA 2007 DEPTHMAX (118 lakes; index-site depth, so a lower bound), OWRB points (10), MI IFR points (9), IL and IN survey attributes, and the supplied observed depths from the GLOBathy thread.

**Method** (`contour_match.py`, `contour_twdb.py`): contours are grouped per source lake (spatial clusters for the unnamed FL/KS/IL files). For each group and each fleet polygon (EPSG:5070, 150 m digitising buffer): `fracLenIn` = share of contour length inside the polygon; `hullCov` = convex hull of the in-polygon lines over polygon area; `nameAgree` = normalised name equality or containment.
* `verified_spatial`: fracLenIn >= 0.70 with name agreement, an unnamed group, or hull covering >= 25 % of the lake; or 0.25-0.70 with name agreement (partial overlap). TWDB: pool polygon and fleet polygon each overlap the other by >= 0.5.
* `rejected`: weak overlap (24 pairs), contours fully inside a polygon but a different, tiny named water body (6 pairs; e.g. Ossipee Lake's named bays, Minnetonka's neighbouring small lakes), and scout candidates without geometric support (3).
* `name_only_unverified`: scout candidates whose data is only an index or a catalog (USGS inventory 24, ScienceBase releases 16, Great Lakes topobathy 10, MGS soundings 6, local services 3).
* Name collisions were resolved by geometry: Gull Lake MI (8.3 km2) and Gull Lake MN (40.0 km2), Indian Lake OH, Congamond (MA and CT halves) all matched only to the geometrically consistent polygon.
* Fleet duplicates: "Tohopekaliga (Toho)" and "East Lake Tohopekaliga" are the same lake (identical truth); counted once.

Verified lakes by source (any quality): CT 12, MN 12, NH 12, OH 12, WV 12, KS 11, MA 10, NE 10, FL 8, MT 7, TWDB 6, OK 5, WA 4, ND 3, MI 9 (7 usable rows), IN 2, NJ 2, IL 1, PA 1, UT 1, WI 1. Geometry QA: against the survey's own outline (MN, OH and NE acres, or shore rings in the contour file) the fleet polygon agrees within +/-10 % for 68 of 79 lakes with a reliable check (76 of 79 within -20/+25 %); polygons below 0.7 or above 1.43 of the survey area (Lake Hudson OK 0.64, Bighorn 0.69) were pushed to tier C.

## 3. Normalisation rules (`contour_ingest.py`)

One table, all sources: `depth_ft` is positive down, feet, below the surveyed water surface (not elevation). Rules: MN, OH, OK, ND, FL store negative feet (take the absolute value; MN depth >= 0 is shoreline); NJ is metres (x 3.28084); TN reads `Name = "10ft"`; MA flags shoreline with `SHORE = 1`; CT and NH carry explicit shore rows; MT types S and I are shoreline and island (0); MI `MinDepth == MaxDepth` rows are contours, `Min < Max` rows are band rings of unknown depth convention (kept as `kind = band`, not used); IL `CONTOUR` is depth for most lakes but elevation-like (up to 620) for some, resolved per spatial cluster with the survey's `max_dpth` and `norm_pool` (unresolvable clusters dropped); UT Utah Lake contours are elevations converted with the 4489.045 ft compromise level (low confidence; tier C). No datum shifts applied to depth files (all are already below pool or below the surveyed surface); TWDB is handled by its area-capacity tables (the terrain thread's datum work). The merged table is `contour_segments_normalized.gpkg` (260,127 segments; columns lakeId, matchConfidence, src, grp, depth_ft, kind) outside git.

## 4. Shares from contours: method and its measured accuracy

`contour_grid.py` rasterises the fleet polygon (cell 5-30 m, area dependent), burns the contours, and labels the water between contours ("faces"). A face bounded by two levels is interpolated by distance ratio between the two bracketing contours; a face bounded by one level is "deeper than the innermost ring" (set to ring plus half the local step) or "shallower than a shoal ring". Shoreline is the polygon edge (depth 0). Shares are fractions of surveyed water; unsurveyed faces (only shoreline) are excluded. Distances (shore to 3/6 ft), steep share and flats are computed on the same raster.

| check | result |
|---|---|
| Synthetic cone (known answer 27.8/51/75 % shallower than 3/6/10 ft) | 27.2/51.0/74.4 % with 5-ft contours; 27.4/50.6/74.5 % with 10-ft contours |
| 18 real TWDB lakes, native 1-2 ft contours vs exact table shares (<=3 / <=6 / <=10 ft) | bias +0.012/+0.010/+0.010; MAE 0.013/0.010/0.010; max abs error 0.027/0.036/0.051 |
| same lakes, only every 5th foot kept | MAE 0.015/0.024/0.026 (bias +0.014/+0.024/+0.024) |
| same lakes, only every 10th foot kept | MAE 0.070/0.053/0.020; share <= 3 ft overstated by +0.07 |
| 30 fleet lakes with 1-3 ft contours, decimated to 5 ft; lakes >= 25 ft deep (n = 17) | MAE 0.037/0.033/0.038 (p90 0.07-0.11) |
| same, lakes < 25 ft deep (n = 13) | MAE 0.22/0.16/0.03: a 5-ft ladder cannot resolve the shallow zone of shallow lakes (rule built into tiers) |
| MN: this thread vs terrain thread (9 lakes) | MAE 0.022 (<3 ft), 0.024 (<6 ft), Spearman 0.87; Minnetonka off by 0.13 (polygon 55.6 vs 66.7 km2) |

Uncertainty to carry: tier A shares +/-0.03 absolute (p90 0.07-0.09); tier B shares are biased high at <= 6 ft by about +0.05. Method failure modes found: contour rings with gaps connect shallow and deep faces and bias shares shallow (Chippewa Flowage DRAFT file; caught only by the top-of-survey rule); a polygon larger or smaller than the surveyed surface moves the 0-3 ft share (checked above); deepest faces are constants, so mean depth is a lower bound.

## 5. The truth table (`data/contour_truth_lakes.csv`, `contour_truth_summary.json`)

One row per lake (best source), with: shares 0-3, 3-6, 6-10, > 10 ft and `shr_lt6`; max contour depth, mean depth (lower bound), p95 depth; shore-to-3-ft and shore-to-6-ft distance (median, quartiles, p90); `steep_share_6ft_30m` (shoreline fraction with the 6 ft contour within 30 m); flats shallower than 6 ft at least 100 m and 200 m wide (count, hectares, largest patch, share of surveyed area; patches >= 1 ha; inscribed-disk test, valid where the cell is <= 25 m, which is 90 % of lakes); coverage (hull and raster), ladder class, anchors and a `max_depth_check`, `tier`, `flags`, licence note, and the fleet features used later.

Tier A (n = 76) distribution: 0-3 ft mean 10.7 % (median 9.4, p90 18.4); 3-6 ft median 8.7 %; 6-10 ft median 11.2 %; > 10 ft median 69 %. Lake-class medians of share < 6 ft (A+B): natural shallow 47 % (n = 4: Lochloosa, Istokpoga, Lake Wawasee, White Bear Lake), open-basin storage 18 % (39), regulated natural 17 % (22), flow-through reservoir 18 % (16), dendritic storage 16 % (8), natural deep 12 % (5), run-of-river pool 10 % (2), small impoundment 58 % (1: Mansfield Hollow). The shallowest-lake extremes: Grand Lake St. Marys OH 95 % < 6 ft, Lochloosa 84 %, Orange Lake 74 %, Istokpoga 60 %; the steepest: Jennings Randolph 0.7 %, McConaughy 1.6 %, Canyon Ferry 1.8 %, Flathead 3.8 %, Mille Lacs 3.9 % (Mille Lacs agrees with the DNR hypsometry, 4.0 %).

**Representativeness caveat.** The truth set is 65 % reservoirs and sits in the Midwest, Northeast and Plains (WV, MN, OH, NE, KS, MA, CT, FL, TX). There is no Southeast (GA, AL, SC, NC, TN, KY, VA), Mountain West or Pacific reservoir, and only 10 natural lakes. All validation statements apply to that population.

Licences (ledger `S-contour-*`): FL FWC data "should not be distributed" (internal only); TWDB maps "not for navigation or fishing"; MI, MN, IN, MT, WV, NJ, TN have no explicit licence in the scout notes, CT is CC0 (one copy says CC BY 4.0), NH and others carry use-at-own-risk notes; EPA NLA is US Government public. Nothing in git is raw contour geometry; the rasters and the merged GeoPackage stay in the research data directory.

## 6. Re-validation of GLOBathy and the proxies

Truth for all tests: `contour_truth_lakes.csv`, fleet duplicates removed, set A (n = 76) primary and A+B (n = 102) as sensitivity; GLOBathy lakes whose Dmax was supplied (observed pass-through) are excluded from the tests of the model; constant baselines are leave-one-state-out means or medians; 95 % CIs are lake-level bootstrap (2000). Share thresholds were matched to GLOBathy's (1.2/1.8/3.0 m = 3.94/5.91/9.84 ft) by recomputing truth from the rasters (TWDB: S4/S6/S10).

### 6.1 GLOBathy

| test | n | result | constant baseline |
|---|---|---|---|
| Dmax vs contour max depth (top >= 15 ft; modeled Dmax; A+B, verified+weak match) | 73 | median ratio 1.14, within 1.25x 23 %, within 2x 66 %, Spearman 0.18 (-0.08 to 0.41), over 3x too deep for 6 lakes | within 2x 62 %, MAE 11.4 m vs 13.0 m for GLOBathy |
| same, only the 33 lakes whose HydroLAKES match is "verified" | 33 | Spearman 0.24 (-0.15 to 0.57), within 2x 64 % | 70 % |
| same, only lakes whose contour maximum agrees with an independent agency depth (0.75-1.33x) | 19 | Spearman 0.08 (-0.49 to 0.65), within 2x 68 % | 37 % (tiny n, very wide CI) |
| pass-through lakes (observed Dmax supplied) | 19 | median ratio 1.07 (as expected) | n/a |
| share < 1.2 m (3.9 ft) of area, tier A | 55 | MAE 0.084, bias 0.00, Spearman 0.13 (-0.14 to 0.40), tercile accuracy 36 % | MAE 0.075; tercile 35 % |
| share < 1.8 m (5.9 ft) | 55 | MAE 0.135, bias -0.02, Spearman 0.09 (-0.20 to 0.37), AUC broad-shallow third 0.53 (0.35-0.69), tercile accuracy 44 % | MAE 0.128; tercile 35 % |
| share < 3.0 m (9.8 ft) | 55 | MAE 0.206, bias -0.05, Spearman 0.11 (-0.21 to 0.40), AUC 0.49 (0.33-0.67) | MAE 0.205 |

Skill against the constant (1 - MAE / MAE_const) is -0.12, -0.06 and -0.01 for the three thresholds, intervals spanning zero in every case. The tercile accuracy of 44 % at 5.9 ft is the only number above baseline and is within sampling noise at n = 55 (standard error about 7 points). Verified-only matches (n = 23 in tier A) are worse, not better (skill -0.22 to -0.26, AUC 0.35-0.48). The failure pattern is the one found before: the model returns a middling Dmax (6-97 m predicted for lakes whose contour maxima are 9-380 ft) and a near-constant shallow share. Worst cases: Istokpoga (contour maximum 9 ft, GLOBathy Dmax 70 m, share < 1.8 m predicted 0.06 vs true 0.59), Beech Fork WV (0.00 vs 0.42), East Lynn WV (0.18 vs 0.48), Harris FL (0.35 vs 0.05), Houghton Lake MI (0.17 vs 0.46).

### 6.2 Cheap proxies for "broad-shallow" lakes

Target: top third of the share shallower than 6 ft (tier A cut 0.214; A+B cut 0.211). AUC and Spearman use raw predictor scores with the sign fixed beforehand (no fitting); lake-level bootstrap CIs.

| predictor (tier A) | n | AUC | AUC 95 % CI | Spearman vs share < 6 ft |
|---|---|---|---|---|
| HydroLAKES/NID mean depth (-) | 74 | **0.62** | 0.48-0.76 | 0.18 |
| GLOBathy Dmax (-) | 55 | 0.59 | 0.42-0.75 | 0.18 |
| NID dam height (-) | 69 | 0.59 | 0.45-0.73 | 0.18 |
| log10 area (-) | 76 | 0.56 | 0.42-0.69 | 0.15 |
| frac_narrow_300m (+) | 76 | 0.55 | 0.41-0.69 | 0.19 |
| frac_within_100m (+) | 76 | 0.54 | 0.40-0.68 | 0.14 |
| GLOBathy shallow share < 1.8 m (+) | 55 | 0.53 | 0.34-0.70 | 0.09 |
| shore development (+) / solidity (-) | 76 | 0.47 / 0.47 | 0.34-0.61 / 0.32-0.61 | 0.08 / 0.01 |
| ORACLE true contour mean depth (-) | 69 | 0.91 | 0.83-0.97 | 0.76 |
| ORACLE true contour max depth (-) | 76 | 0.79 | 0.68-0.89 | 0.55 |

Leave-one-state-out models on the 55 lakes where every feature exists (17 states): constant MAE 0.130; lake-class mean 0.131 (AUC 0.34, rank correlation negative); ridge on polygon proxies 0.162 (skill -0.25, CI -0.61 to -0.03); ridge on GLOBathy 0.135; ridge on mean depth 0.140; polygon plus mean depth 0.151 (AUC 0.55, 0.38-0.71); all features 0.156. No model beats the constant on MAE, and none exceeds AUC 0.55. A+B (n = 102) is the same: best single predictor is again mean depth (AUC 0.57) with nid_height 0.56 and log area 0.54; models never beat the constant.

Other targets (tier A, Spearman with 95 % CI): share < 3 ft is predicted by frac_narrow_300m 0.39 (0.17-0.57), frac_within_100m 0.35 (0.12-0.55) and small area 0.30 (0.07-0.51), but the effect fades at 6 ft and is gone for A+B at the < 6 ft threshold. The median shore-to-6-ft distance (how wide the shallow band is) correlates with frac_within_100m at -0.66 (-0.81 to -0.46), frac_narrow_300m -0.60, log area -0.50 (larger lakes have wider shallow bands) and mean depth -0.48 (-0.66 to -0.26: lakes that are shallower on average have wider shallow bands, the physically sensible direction). Flats at least 200 m wide are geometrically limited by lake width, so their correlation with the polygon proxies (-0.4 to -0.5) is mostly a size effect.

3DEP shoreline-slope proxies on the overlap with the terrain thread's table (18 lakes: 9 MN, 5 TWDB, 4 CWMS): Spearman of slope_10_60 with share < 6 ft -0.17 (-0.61 to 0.33), AUC 0.46 (0.17-0.74); none of nine slope variables is distinguishable from zero; the polygon proxies on the same 18 lakes are no better (frac_within_100m 0.45, CI -0.08 to 0.82). n is too small to say more.

### 6.3 Mean depth

HydroLAKES/NID mean depth (`lake_features.mean_depth_m`) against contour mean depth (17 tier-A lakes with a confirmed top): Spearman 0.64 (0.18-0.85) but a median overestimate of 1.40x and MAE 8.4 m vs 3.9 m for a constant; against the supplied observed mean depths (n = 20) Spearman 0.70 (0.33-0.93), median ratio 1.55x. GLOBathy mean depth: Spearman 0.20 (-0.36 to 0.74), median ratio 1.00 (n = 17). The ranking value of storage-based mean depth is real but its absolute values are biased high and its power for the broad-shallow third is weak (AUC 0.62).

## 7. Within-lake test with 3DEP (`contour_spatial_test.py`)

46 tier-A/B fleet lakes with contour rasters and a 3DEP shore profile from the terrain thread (the fleet profile has two offsets, 10 and 60 m, so only the 10-60 m slope is available for most; the nine MN lakes use the dense 10-offset profile). 5,718 shoreline segments of 500 m.

* Segment level: per-lake Spearman of the 10-60 m slope with the share of the 0-100 m near-shore band that is <= 6 ft: mean -0.24 (-0.32 to -0.16), median -0.29, 33 of 44 lakes negative; with the median shore-to-6-ft width: mean -0.27 (-0.34 to -0.20), 37 of 44 negative. Pooled rank-within-lake correlation -0.27 (share) and -0.28 (width), n = 5,717. Steeper shore means a narrower shallow band, as expected, but 11 of 44 lakes go the wrong way (Johnson Lake NE +0.52, Jennings Randolph +0.20). Slopes over 30-100 m and 60-200 m (nine lakes only) and the 200 m rise are weaker (-0.04 to -0.11).
* Mask level (truth = depth <= 6 ft): predicted zone within W of shore with W fit leave-one-lake-out as a constant: mean IoU 0.403; W = 6 ft / tan(slope): 0.439 (+0.036, CI 0.005 to 0.073; better in 26 of 44); with the slopes shuffled among segments of the same lake 0.378 (slope-aware better than shuffled in 37 of 44).
* Cell-level ranking: AUC for depth <= 6 ft: distance only 0.818, distance plus slope 0.822 (lake-level change -0.015 to 0.022; slope helps in 22 of 44 lakes); slope alone 0.586. Same pattern at 3 ft (0.864 to 0.875) and 10 ft (0.778 to 0.780).

Reading: shoreline slope carries real within-lake information (rank correlation and IoU), but after distance from shore is known it adds almost nothing to cell-level ranking. Distance from shore predicts the shallow zone surprisingly well (AUC 0.82 at 6 ft) because most lakes drop quickly.

## 8. Limitations and failure cases

* Truth is measured but old and heterogeneous (digitised lake maps of mixed vintage in MN, MA, CT, NH, MT, WA; modern hydroacoustic in FL, TWDB, WV, NE). Water level at survey time versus the fleet polygon is a known bias (0-3 ft share), checked only where the survey outline exists.
* Contour gaps bias shares shallow; closed top rings give a constant for the deepest face; max and mean depth are therefore lower bounds. 3 lakes are flagged `deep_part_missing_vs_reference` (mean and max depth invalid, shares to 10 ft still usable) and 62 of 137 rows have no independent max-depth anchor at all.
* Pool-level datum: reservoirs are drawn at conservation pool; operating levels shift the real 0-3 ft band (see the effective-depth thread).
* The truth set is not random: states with open data, mostly reservoirs, mostly 5 to 400 km2. Leave-one-state-out has 17-20 states but 7 of them have 1-3 lakes.
* Resolution: cell 5 m for most lakes and up to 30 m for the largest; the steep-bank share (6 ft within 30 m) is a 5-15 m resolution statement; flats at 100 m use a 50 m inscribed disk.
* Rejected and not-verified lakes (Buckeye Lake OH, Marion Reservoir KS, Crescent Lake FL; Higgins, Torch, Elk MI) are fleet polygon problems or band-only data and are listed in `contour_matches_verified.csv` with the reason.

## 9. Recommendations

1. Treat the 102 tier-A/B lakes as lake-specific truth: publish per-lake derived metrics (shares, shore-to-6-ft distance, flats) after licence review; keep FL FWC and all raw contours out of the app and repo.
2. For the other ~520 lakes the honest output is "unknown", not a modelled number. No proxy tested here (GLOBathy, polygon geometry, NID/HydroLAKES, lake class, 3DEP slope) beats a constant on the share of area shallower than 6 ft; the best ranking signal is storage-based mean depth at AUC about 0.6.
3. Highest-value acquisitions: southeastern, southwestern and western USACE and utility reservoirs (nothing public found in the scout), more state contour services (ArcGIS Online catalog in `sources/ago_bathy_catalog.json`: 561 hits), the USGS releases already listed (Table Rock, Beaver, Norfolk, Nimrod, Koocanusa, Buckhorn), and a re-pull of the incomplete IL set.
4. If a modelled prior is still wanted, build it on mean depth (oracle AUC 0.91) from storage/area where NID or USGS volume exists, calibrated on this truth, and report it as low confidence; do not use Dmax.
5. Within a known-shallow lake, use distance from shore as the primary map layer and shoreline slope as a minor modifier.

## 10. Reproduction

Venv python with `-I`. Order: `contour_ingest.py` -> `contour_match.py` -> `contour_twdb.py` -> `contour_anchors.py` -> `contour_survey_area.py` -> `contour_truth.py` -> `contour_truth_select.py` -> `contour_method_check.py` + `contour_method_check_post.py` -> `contour_revalidation.py` -> `contour_spatial_test.py` -> `contour_normalize_merge.py` -> `contour_ledger.py`. Library: `contour_grid.py`. Outputs: `data/contour_matches_verified.csv`, `contour_truth_lakes.csv`, `contour_truth_summary.json`, `contour_revalidation.json` (+`_lakes.csv`), `contour_spatial_test.json`, `contour_method_check*.{json,csv}`, `contour_anchors_verified.csv`, `contour_survey_area.csv`, `contour_twdb_truth.csv`; ledger `ledger/contour.jsonl` (24 source records with licences, 9 findings).
