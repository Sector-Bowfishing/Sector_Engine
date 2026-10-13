# 07. NLA 2017 x Sentinel-2 validation of the Vegetation Brain (pre-registered section 4 protocol)

Offline research. No git repo modified (the pre-registration repo `Sector_Engine-vegetation-adoption` was read only). All work and outputs are in `~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/nla/`; every new file is logged (bytes, sha256) in `../../MANIFEST.jsonl`. Frozen gates are those of `docs/brains/vegetation/VEGETATION_VALIDATION_PREREGISTRATION.md` sections 1, 2, 4, 5. Nothing was tuned on the evaluation lakes.

## 1. Headline (read first)

| item | result |
|---|---|
| Fleet lakes with an NLA 2017 site inside the analysis polygon | **60** (of 621 registry lakes; 29 have `geometry:null` and cannot be tested: they have no registry bbox, and by registry point only Point Judith Pond RI has an NLA17 site within 5 km, at 4.3 km) |
| ... with >= 1 phab cover row (eligible per section 4) | **48** lakes. **15 positive, 8 negative, 25 ambiguous**, 12 lakes have a site but no cover rows |
| 2017 Sentinel-2 L2A scenes within +-21 d of the visit | **Not mostly NO_SCENE.** all 47 searched lakes have >= 1 acquisition date (collection `sentinel-2-l2a`; **`sentinel-2-c1-l2a` has zero 2017 items for every lake**); median 4 dates in the 43-day window; Lake Mead (59 M px window) was skipped (`SKIPPED_TOO_LARGE`, not searched), so 47 of the 48 eligible lakes were processed |
| Lakes that actually received a score (>= 10 seen belt cells) in 2017 | observer **S 17** (6 pos / 5 neg), **A 26** (7 pos / 4 neg / 15 amb), **P 26** (same as A; only 1 lake had >= 3 accepted scenes) |
| **Gate (c)** NLA lake AUC >= 0.80 **and** Spearman >= 0.50, >= 15 lakes, >= 3 regions | **FAIL for S, A and P** (primary 2017). A: AUC 0.82 (95 % CI 0.50-1.00, 7 pos vs 4 neg) but Spearman **0.31** (CI -0.08..0.61), n = 26, 7 EPA regions. S: AUC 0.80 (0.44-1.00), Spearman 0.41 (-0.16..0.80), n = 17. P = A |
| **Gate (d)** negative-control flagged share <= 2 % | **FAIL for S, A and P.** Mean belt share over NLA-negative lakes **9.0 %** (A; 4 negatives, 2 of them above 2 %: Keystone 14.8 %, Jocassee 19.6 %), pooled over cells 15.2 % (A) / 13.0 % (S) |
| Secondary (2018-2019 substitute, **not mixed into primary**) | Same verdict: gate (c) FAIL (A: AUC 0.62, Spearman 0.17, n = 36, 10 regions; S: AUC 0.80, Spearman 0.34, n = 30), gate (d) FAIL (A negative mean 12.3 %; S 9.0 %) |
| Why | Almost all flagged belt cells are in the 10-30 m strip next to the polygon edge (pooled A-primary share by distance bin: positives 48 % / 19 % / 9 %, negatives 25 % / 12.5 % / 9 % for 10-30 / 30-60 / 60-90 m), i.e. the production plant rule is not separating emergent/floating plants from bank vegetation, overhanging trees and polygon-edge misregistration in a belt that begins 10 m from the edge. Restricting to 40-90 m (the production rule's own 40 m erosion; exploratory, not a gate) cuts the negative-control share to 4.0 % (A) / 3.4 % (S) but still fails (d) and does not rescue Spearman (A 0.19) |

Bottom line: on this pre-registered test the observer **does not earn gates (c) or (d)**. There is a weak-to-moderate lake-level ordering signal for the highest-cover lakes (Box Butte NE, Piney Run MD, Concord Pond DE, Lake Washington MS are among the top-ranked by A, together with ambiguous lakes such as Winnisquam NH, Fish Lake UT, Harlan NE) and AUC point estimates of about 0.8, but the sample is tiny (4-5 negatives), the intervals reach 0.5, rank agreement with the cover code is below the 0.50 gate, and negative controls are polluted by shoreline false positives. The vegetation state stays `NOT_VALIDATED` on these two gates. This is not evidence against surface-mat/floating-leaf detection where it was shown to work (note 04/05, clear PNW lakes); it is evidence that the shore belt score as specified is not a valid lake-level discriminator for the fleet's mostly-reservoir NLA lakes.

## 2. Eligible set (computed from data)

Sources: `sources/nla_2017_phab/nla_2017_site_information-data.csv` (NLA17 sites with `DATE_COL`: 1,113 first visits + 97 revisits; visit 1 used), `nla_2017_phab-data.csv` (12,076 station rows, 1,147 sites), registry `registry/lakes.v1.json` (621 lakes, 29 `geometry:null`, skipped; they carry no registry bbox, so I used the registry point: no NLA site within 5 km except Point Judith Pond RI at 4.25 km). Analysis polygons (`geometry.v1.analysis.geojson.gz`) fetched only for the 79 lakes whose bbox contains an NLA point (`data/geom/`). Join rule: NLA lake point (`LAT_DD83/LON_DD83`) **inside** the analysis polygon (strict). 61 site-lake pairs, 60 lakes; 32 further bbox hits fall outside the polygon (mostly arms/pools of big reservoirs; nearest miss 70 m at Wild Horse Reservoir NV) and are not used. Two sites map to two registry lakes each (NLA17_SD-10001 Oahe ND/SD, NLA17_SC-10023 Clarks Hill GA / Strom Thurmond SC; both have no cover rows).

Classes per section 4 (code scale 0-4 = 0 %, <10 %, 10-40 %, 40-75 %, >75 %): station score = mean(emergent, floating); **positive** = lake mean >= 1.0 **or** >= 20 % of stations with emergent or floating code >= 2; **negative** = every visit-1 station 0 for emergent, floating **and** total macrophyte (a missing value blocks negative); else **ambiguous**. If one reads "mean(emergent+floating)" as the sum instead of the mean, positives would be 11 not 15 (sensitivity only; Spearman is unaffected).

By EPA region (`out/report_tables.md`, table A):

| EPA region | lakes with site | lakes with cover rows | POS | NEG | AMB |
|---|---|---|---|---|---|
| 01 | 2 | 2 | 0 | 0 | 2 |
| 02 | 2 | 2 | 0 | 0 | 2 |
| 03 | 8 | 8 | 4 | 0 | 4 |
| 04 | 13 | 7 | 4 | 2 | 1 |
| 05 | 4 | 4 | 2 | 1 | 1 |
| 06 | 7 | 7 | 1 | 2 | 4 |
| 07 | 6 | 6 | 2 | 2 | 2 |
| 08 | 10 | 6 | 0 | 1 | 5 |
| 09 | 6 | 5 | 2 | 0 | 3 |
| 10 | 2 | 1 | 0 | 0 | 1 |
| **total** | **60** | **48** | **15** | **8** | **25** |

By state (lakes with cover rows / POS / NEG / AMB): AR 1/1/0/0, AZ 1/1/0/0, CA 1/0/0/1, CT 1/0/0/1, DE 2/2/0/0, FL 1/1/0/0 (Griffin), GA 1/0/0/1, IN 4/2/1/1, KS 1/1/0/0, LA 1/0/0/1, MD 2/2/0/0, MO 2/0/1/1, MS 2/2/0/0, MT 1/0/0/1, NC 1/0/1/0, ND 1/0/0/1, NE 3/1/1/1, NH 1/0/0/1, NM 1/0/0/1, NV 3/1/0/2, NY 2/0/0/2, OK 3/0/1/2, OR 1/0/0/1, PA 2/0/0/2, SC 1/0/1/0, SD 2/0/0/2, TN 1/1/0/0, TX 1/0/1/0, UT 2/0/1/1, VA 1/0/0/1, WV 1/0/0/1 (full table in `out/report_tables.md`, with the lakes that have a site but no cover rows: AL, GA, SC x2, SD x3, WY, FL (Okeechobee), NV (Pyramid), MS (Sardis), OR (Owyhee)). The eligible set is skewed to large reservoirs (median 28 km2, max 544) and contains only **8 negatives and 4 southern/hydrilla-type lakes**; there is no turbid-vs-clear stratification.

### What the NLA phab data carry spatially (shoreline-belt limitation)

* Per-station coordinates **do exist** in `nla_2017_phab-data.csv` (`LATITUDE`, `LONGITUDE`, stations A-J, sometimes K/L): 467 of 491 stations in the eligible lakes have coordinates; 303 fall inside the analysis polygon; 191 are within 10 m of the polygon edge (median distance to edge **12.6 m**); only 162 are inside the 10-90 m belt (`out/nla_station_geometry.csv`). Station cover codes describe a small shoreline plot (protocol knowledge, not in the data file: plots are of the order of 10-15 m, about one S2 pixel, at the shore), i.e. almost entirely in the SHORE_ADJACENT strip that section 1 excludes. The lake-level belt score therefore compares **offshore 10-90 m satellite cells** with **shore-plot cover**: a proxy for littoral emergent/floating extent, not a co-located measurement. A station-level supplement (3x3 cells around each station in the belt, `out/nla_station_level.csv`, `nla_station_level_metrics.json`, non-gate) is weak: A primary AUC (code >= 2 vs 0) 0.66 on 6 positive / 45 negative stations, secondary 0.45 (17 / 87).
* Dates: one visit per site; the 2017 reference date is the lake's first visit date (Lake Wawasee has two sites: 2017-06-28 and 07-13, first used). Revisit rows (97, `VISIT_NO` 2) are not used.
* Only about 10 stations per lake (median 10, max 20): lake cover codes are noisy.

## 3. Methods

Code: `experiments/adoption/nla/scripts/` (`n1_eligible.py`, `n2_classes.py`, `n4_cells.py`, `nlalib.py`, `n5_score.py`, `n6_stations.py`, `n7_station_level.py`, `n8_report.py`, `n9_manifest.py`). No `adoption/prod_harness/` existed when I started (only `adoption/umr/`), so I wrote my own observer on top of note 05's `cell_lib.py` (a port of `jobs/lake-surface/derive_water_surface.py`, constants verbatim) plus the production `hidden` indicator that `cell_lib` omits (re-derived from `_s2_native_fields`).

* **Scenes.** Earth Search v1; per lake window = lake bbox + 0.007 deg; items with tile cloud >= 90 % skipped before reading (secondary: >= 50 %, and at most the 6 dates nearest the anniversary per year to limit volume). Bands `red` (10 m), `nir08`, `swir16`, `scl` (20 m nearest-upsampled to 10 m). `sentinel-2-c1-l2a` first (offset from `raster:bands` = -0.1), `sentinel-2-l2a` second (offset 0, already removed); in 2017 only `sentinel-2-l2a` exists. Tiles of the same date and CRS are merged (first tile wins where it has data; no feathered blending). NO_SCENE is recorded when both collections return nothing in the window (it never happened: 0 of 47 searched lakes).
* **Pixel and cell rule (production).** Plant pixel = NDVI(B8A,B4) >= 0.30 (`max(1e-6, sum)` denominator) on a seen pixel; seen = SCL > 0 and >= 60 m from SCL cloud/shadow/cirrus/snow classes; production haze/cloud-edge/structure standoffs give the `hidden` indicator. 10 m pixels are averaged onto the production 50 m web-mercator frame; cell = PLANT if seen share >= 0.5, plant share of seen pixels >= 0.5, and the cell is not a "turbidity-read" open-water cell (`have`, production readability gate: water SCL, SWIR <= 0.0215, FAI <= 0.005, NDVI <= 0.10, 100 m structure standoff, 10 m bank standoff, >= 25 % of the cell).
* **Prereg guards added.** Pixels with red and B8A both < 0.01 are excluded; cell UNKNOWN if hidden share >= 0.5 (`UNK_cloud_haze`), >50 % of seen pixels dark (`UNK_dark`), or < 50 % of the cell's in-polygon pixels seen (`UNK_insufficient`). **Glare** (SWIR/B8A pattern, wind flag) is **not implemented**: the prereg gives no numeric rule and no wind flag is available, so the glare guard is absent from these results. Scene-reference gap > 21 d is excluded by construction.
* **Deviations from production (inherent to the prereg).** (1) Only pixels inside the analysis polygon enter a cell (production lets land pixels contribute); (2) no 40 m erosion (the prereg belt starts 10 m from the edge; production calls grass only >= 40 m in, plus a bed-to-bank extension that is not applied); (3) window pad 780 m not 1 km; (4) no tile blending, no grass-under-cloud borrowing, no speck/pocket filters; (5) glare guard absent. SHORE_ADJACENT = cell centre within 10 m of the polygon edge (boundary densified at 4 m, ground distance in the scene's UTM); belt = 10 < d <= 90 m.
* **Observers (prereg section 1).** Lake reference date r. **S**: nearest scene with >= 75 % of lake cells seen (not UNKNOWN), gap <= 21 d, else lake `NO_CLEAR_SCENE_75`. **A**: nearest scene that reads >= 50 % of the non-plant clarity water (clarity = lake eroded 40 m; `have` cells / non-plant cells); fallback best coverage >= 25 %, else `NO_ACCEPTED_PASS`. **P**: median of g' (plant fraction with read cells = 0) over scenes with coverage >= 0.5 and gap <= 21 d, requiring >= 3 such scenes; per-cell needs >= max(2, ceil(n/2)) seen scenes; with < 3 accepted scenes it is A and carries `persistence: INSUFFICIENT` (implementation choices fixed before scoring, listed in `n5_score.py`).
* **Lake score** = plant cells / seen cells in the belt (SHORE_ADJACENT excluded); lake UNKNOWN if < 10 seen belt cells (fixed before scoring).
* **Metrics.** Spearman (belt share, lake mean of mean(emergent, floating)) over all scored lakes incl. ambiguous; AUC positives vs negatives (ties = 0.5); bootstrap over lakes (2,000 resamples, percentile 95 %); negative-control share = mean over NLA-negative lakes of the belt share (also pooled-cell and whole-lake shares reported). Gate verdict rules fixed here: (c) PASS iff n scored >= 15, >= 3 EPA regions, AUC >= 0.80 and Spearman >= 0.50 (point estimates); NOT_TESTABLE if fewer lakes/regions or no pos/neg; (d) PASS iff the negative-lake mean belt share <= 2 %. **Shore-distance matching:** every lake is scored on the same 10-90 m support; as a check, `std_share` re-weights each lake's 10-30/30-60/60-90 m shares to the pooled bin mix (no change in verdicts). `b40_share` (40-90 m, the production erosion) is exploratory.
* **Secondary (labelled).** Same observers on `Jun-Sep`-clipped windows +-21 d around the **anniversary** of the visit date in 2018 and 2019 (a lake-year each; lake score = mean of available years). Only run because it was cheap to run alongside, not because 2017 was NO_SCENE (it was not). Caveats: temporal substitution; lake class assumed stable; collection is mostly `sentinel-2-c1-l2a` (as in production) where 2017 is `sentinel-2-l2a` (older Sen2Cor); the two are not interchangeable and the secondary result should not be read as a replacement for the primary.

## 4. Results

### 4.1 Which lakes were scored, and why others were not (`out/report_tables.md` D-E)

2017 primary, 48 lakes with cover rows:

| observer | SCORED | NO_ACCEPTED_PASS | NO_CLEAR_SCENE_75 | SKIPPED (Mead) |
|---|---|---|---|---|
| S | 17 | 0 | 30 | 1 |
| A | 26 | 21 | 0 | 1 |
| P | 26 | 21 | 0 | 1 |

By class (A): POS 7 scored / 7 no pass / 1 skipped; NEG 4 / 4 / 0; AMB 15 / 10 / 0. So 11 of the 23 NLA positives+negatives are unscored by A; the refusal is largely the production readability gate (turbid water: the median water-pixel B11 is 0.019-0.022 in 2017-2019 scenes and 43-51 % of scenes have a median above the 0.0215 gate, `report_tables.md` H), not missing imagery. P degenerates to A: only 1 of 26 lakes had >= 3 accepted scenes in 2017 (secondary: 9 of 58 lake-years), so **persistence is essentially untested here**.

Belt-cell fate (belt cells excluding SHORE_ADJACENT, over lakes where the observer produced a map):

| mode | obs | lake maps | plant | open water | UNK cloud/haze | UNK dark | UNK insufficient | SHORE_ADJACENT cells excluded |
|---|---|---|---|---|---|---|---|---|
| primary | S | 17 | 14.4 % | 74.2 % | 8.5 % | 0.1 % | 2.9 % | 10,081 |
| primary | A | 26 | 13.9 % | 56.2 % | 22.3 % | 4.4 % | 3.2 % | 15,354 |
| primary | P | 26 | 13.9 % | 56.6 % | 21.9 % | 4.4 % | 3.2 % | 15,354 |
| secondary | S | 39 lake-yrs | 13.9 % | 74.7 % | 6.9 % | 0.9 % | 3.6 % | 20,658 |
| secondary | A | 58 | 11.8 % | 59.6 % | 15.8 % | 5.9 % | 6.9 % | 35,162 |
| secondary | P | 58 | 12.1 % | 59.9 % | 15.0 % | 6.0 % | 7.1 % | 35,162 |

Glare is not a column (not implemented). The cloud/haze guard is the largest UNKNOWN source; the dark-water guard fires on 4-6 % of A belt cells.

### 4.2 Lake-level metrics and gates (belt share 10-90 m; 95 % bootstrap CI over lakes)

| mode | obs | n scored (pos/neg/amb) | regions | Spearman | AUC | negative mean share (n>2 %) | gate (c) | gate (d) |
|---|---|---|---|---|---|---|---|---|
| **primary 2017** | S | 17 (6/5/6) | 7 | 0.41 [-0.16, 0.80] | 0.80 [0.44, 1.00] | 8.9 % (4 of 5) | **FAIL** | **FAIL** |
| **primary 2017** | A | 26 (7/4/15) | 7 | 0.31 [-0.08, 0.61] | 0.82 [0.50, 1.00] | 9.0 % (2 of 4) | **FAIL** | **FAIL** |
| **primary 2017** | P | 26 (7/4/15) | 7 | 0.31 [-0.10, 0.62] | 0.82 [0.43, 1.00] | 9.0 % (2 of 4) | **FAIL** | **FAIL** |
| secondary 18-19 | S | 30 (9/5/16) | 9 | 0.34 [-0.06, 0.67] | 0.80 [0.50, 1.00] | 9.0 % (3 of 5) | FAIL | FAIL |
| secondary 18-19 | A | 36 (11/5/20) | 10 | 0.17 [-0.20, 0.52] | 0.62 [0.28, 0.92] | 12.3 % (3 of 5) | FAIL | FAIL |
| secondary 18-19 | P | 36 (11/5/20) | 10 | 0.14 [-0.21, 0.47] | 0.62 [0.28, 0.92] | 12.4 % (3 of 5) | FAIL | FAIL |

Negative-control detail (primary A): Willard Bay UT 0.0 %, Sherman NE 1.4 % (the only two within 2 %), Keystone OK 14.8 %, Jocassee SC 19.6 %; four more negatives (Buchanan TX, Hickory NC, Monroe IN, Pomme de Terre MO) had no accepted 2017 pass. Pooled over negative-lake cells: 15.2 % (A), 13.0 % (S); mean whole-lake (>10 m from edge) share 4.2 %. Exploratory variants (all `out/nla_metrics.json`, none changes a verdict except one secondary S/b40 gate (d) PASS that comes with a failing gate (c)): `std_share` (distance-standardised): primary A AUC 0.86, Spearman 0.32; `b40_share`: primary A AUC 0.86, Spearman 0.19, negative mean 4.0 %; primary S: AUC 0.83 / 0.83, Spearman 0.43 / 0.39, negative mean 8.8 % / 3.4 %.

Distance profile (`out/nla_lakelevel_primary_A.csv`, pooled plant/seen cells in the 10-30 / 30-60 / 60-90 m bins): primary A positives 48 % / 19 % / 9 %, negatives 25 % / 12.5 % / 9 %, ambiguous 38 % / 17 % / 9 %; secondary A positives 37 % / 16 % / 9 %, negatives 34 % / 8 % / 1.5 %. The 60-90 m bin is the only one where negatives look clean in the secondary, and it carries few cells.

### 4.3 Per-region breakdown (observer A; `report_tables.md` G)

Primary: Region 3 (2 pos) median 0.39; Region 4 (3 pos, 1 neg, 1 amb) 0.195 / 0.196 / 0.194 (no separation); Region 7 (1 pos 0.76, 1 neg 0.014, 2 amb 0.39); Region 8 (1 neg 0.0, 5 amb 0.08; Spearman 0.03); Region 9 (1 pos 0.11); Regions 1, 6 have only ambiguous/negative lakes. Secondary: Region 4 (4 pos median 0.33, 1 neg 0.39), Region 7 (2 pos 0.43, 1 neg 0.06); Regions 6 and 8 negatives 0.4-0.7 %. A within-region Spearman is computable only where n >= 6: Region 8 (0.03, primary), Region 4 (0.09, secondary). Per-region n is 1-6, so no region-level claim is possible.

Per-lake outputs: `out/nla_lake_scores.csv` (long: lake x mode x observer, with cell counts, refusal reason, gap, class), `out/nla_per_lake_wide.csv` (one row per lake), `out/nla_lakelevel_{primary,secondary}_{S,A,P}.csv` (scored lakes incl. variants), `out/nla_fleet_join*.csv`, `out/nla_lake_classes.csv`, `out/nla_station_geometry.csv`, `out/nla_station_level*.{csv,json}`, `out/nla_metrics.json`, `out/report_tables.md`.

## 5. Gate statements (prereg section 5)

* **(c) NLA lake-level AUC >= 0.80 and Spearman >= 0.50 on >= 15 eligible lakes spanning >= 3 regions: FAIL** (observers S, A, P, primary 2017). Population requirement met (A/P 26 scored lakes, 7 regions; S 17 lakes, 7 regions). AUC clears 0.80 on point estimates (S 0.80, A/P 0.82) but its lower bound is 0.43-0.50 and rests on 4-5 negatives; Spearman is 0.41 / 0.31 / 0.31 against the 0.50 floor. Secondary substitute: also FAIL (best S: AUC 0.80, Spearman 0.34).
* **(d) negative-control flagged share <= 2 %: FAIL** (S 8.9 %, A/P 9.0 %; 4 of 5 / 2 of 4 negatives above 2 %). Secondary: FAIL (9.0-12.4 %).
* The PARTIAL state therefore cannot be reached through the NLA arm. (a), (b), (e) are not addressed here.

## 6. Limitations (read before quoting any number)

1. **Small, skewed sample.** 15 positives / 8 negatives exist, but only 7 / 4 are scorable by A in 2017 (6 / 5 by S); AUC intervals span 0.5-1.0. Ambiguous lakes (25 of 48) carry most of the Spearman. Large reservoirs dominate; 4 southern lakes; no strata for turbid vs clear.
2. **Proxy mismatch.** NLA cover codes are shoreline-plot values (approximately one pixel at the bank), the satellite belt is 10-90 m offshore, inside an NHD analysis polygon simplified at about 25 m tolerance (`analysisToleranceM` 25 on the registry record I inspected). Polygon edge misregistration and bank vegetation inside the polygon directly inflate belt shares; the data cannot separate that from true marginal vegetation. The negative control (stations 0 at 10 shoreline plots) does not prove the rest of a big reservoir shoreline has no emergent vegetation either.
3. **Observer not identical to production** (section 3 deviations; glare guard missing). The production 40 m erosion was deliberately dropped to follow the prereg belt; the 40-90 m variant shows what the production-eroded call would give.
4. **2017 imagery is `sentinel-2-l2a` (older Sen2Cor, no offset); the production collection is `c1`.** Water SWIR medians are similar across 2017/2018/2019 (0.019-0.022), so I see no clear collection artifact, but the production haze/readability thresholds were designed on c1 and fire on about half the scenes here.
5. **Thin temporal coverage.** Median 4 dates in a 43-day window (any cloud), cloud/haze hides 22 % of A belt cells, only 1 lake reached >= 3 accepted scenes, so persistence (P) was effectively not tested.
6. **Reference date handling:** one date per lake; Wawasee's second site date unused. Secondary uses anniversaries with at most 6 dates per lake-year (volume cap, chosen without reference to results) and a cloud < 50 % tile prefilter.
7. **Lake Mead** (59 M px window, positive) was not processed; 29 `geometry:null` lakes cannot be tested.
8. **Data volume.** The task cap was < 2 GB of new downloads. The local cache `out/s2cache_nla` holds 5.0 GB of recompressed uint16 windows (about 25 % primary, 75 % 2018-2019). Network bytes were not metered; they probably exceeded 2 GB (the first pass read every 2018-2019 date of the large lakes before I added the 6-date cap). The primary 2017 share was not separately metered. Cache files are logged `retention: cache-deletable`.
9. **Ties and Spearman:** many lake scores are tied at small values; bootstrap intervals are percentile intervals on <= 36 lakes.

## 7. Reproduce

```
cd ~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/nla
PY=../../.venv/bin/python        # numpy pandas scipy shapely pyproj rasterio pystac-client requests tabulate scikit-learn
$PY scripts/n1_eligible.py       # NLA x registry join, fetches analysis polygons (79 small files) -> data/geom, out/nla_fleet_join*.csv
$PY scripts/n2_classes.py        # lake cover codes + POS/NEG/AMB -> out/nla_lake_classes.csv
ls out/lakes_todo.txt            # 47 lakes (Mead excluded); then per lake (6 parallel):
cat out/lakes_todo.txt | xargs -P 6 -I{} sh -c "$PY scripts/n4_cells.py {} both > out/cells/log_{}.txt 2>&1"   # network: STAC + COG range reads -> out/s2cache_nla, out/cells
$PY scripts/n5_score.py          # observers S/A/P, lake scores, metrics, gates -> out/nla_lake_scores.csv, out/nla_metrics.json
$PY scripts/n6_stations.py && $PY scripts/n7_station_level.py
$PY scripts/n8_report.py         # -> out/report_tables.md, out/nla_per_lake_wide.csv
$PY scripts/n9_manifest.py       # appends bytes + sha256 to ../../MANIFEST.jsonl
```
Note: the first pass of `n4_cells.py` ran with a `maxcloud` of 90 and no per-year cap for the first 13 completed lakes (Allatoona, Arkabutla, Folsom, Grand, Griffin, Harlan, Keuka, Buchanan, Monroe, Rye Patch, Walker, Willard Bay and others) and partially for Bitter, Keystone, Raystown, Skaneateles, Skiatook, Wilson; the 6-date, cloud < 50 % secondary cap was applied from the second pass. Cached cell files from the first pass were kept, so re-running from scratch will give slightly different secondary scene sets for those lakes (primary is identical).
