# 05. Sonar biovolume, cell-level re-score of Sector's grass rule, persistence composites, clarity proxy

Research only. No git repo touched, nothing imported from the Sector repo (the rule was re-implemented from a read of `jobs/lake-surface/derive_water_surface.py`). All work is inside `~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/` (scripts `scripts/11..25`, outputs `out/`, raw data `data/`). Every new file is logged with bytes and sha256 in `../MANIFEST.jsonl` (`scripts/25_manifest05.py`). Follows note 04 (`04_empirical_sentinel2_test.md`); the collection lesson is respected throughout: `sentinel-2-c1-l2a` with the -0.1 offset applied, `sentinel-2-l2a` (used only when c1 has no scenes, e.g. all of 2022) with offset 0 (`read_lean` in `scripts/20_pac_extract.py` sets `off` per item collection).

## 1. Headline (read this first)

| goal | result |
|---|---|
| **1. FWC BioVolume ImageServers (pixel-level sonar rasters)** | **Could not be tested. The services are listed but dead.** `WhatsHappening_BioVolume2015..2023` appear in the services directory of `ocean.floridamarine.org`, but every request to them (`?f=json`, `exportImage`, `query`, POST, from curl and from a browser, HTTP and HTTPS) hangs until timeout (40 s to 40 min, never an answer; sibling services answer in 0.2 s). The FWC viewer itself requests these URLs (`PlantMonitoring.js`), so its biovolume layer is presumably broken too. Service name, years and the app's use are confirmed; layer units, extent and resolution **could not be read**. Neither the lake coverage nor the units (percent biovolume vs canopy height) nor resolution were obtained; I did not guess them. Re-try later; `scripts/` contains everything needed except the fetch (see section 3). |
| **1b. Substitute sonar truth that does work: FWC LTM lake-level PAC and PVI** (`MapServer/41`, 126 lakes, 2015-2023) | PAC = sonar percent area covered, PVI = percent water volume occupied (mean biovolume over the lake). Real sonar, absences are real, **but lake-year level only (no pixels, no per-pixel depth)**. 130 lake-years, 50 lakes, 2018-2023 with a qualifying Sentinel-2 scene. Sector's cell-level grass fraction vs sonar: **Spearman 0.43 with PVI, 0.35 with PAC** (pixel NDVI>=0.30 share 0.47 / 0.40; FAI 90th pct 0.45 / 0.39). High-volume vs low-volume lakes (PVI>=20 vs <5): AUC **0.79** cell grass fraction, 0.84 pixel NDVI share, 0.84 FAI q90. High cover vs low cover (PAC>=50 vs <20): AUC only **0.65** (0.70 px, 0.75 FAI q90). So S2 follows sonar *volume* (canopy height / depth) much better than sonar *area*, as expected for a sensor that sees only canopy at the surface. |
| **canopy-height / depth ratio at which S2 starts to see vegetation** (lake-level proxy: mean biovolume in covered area = PVI/PAC, lakes with PAC>=30) | Sector grass cells as % of lake cells, median by mean BV: 0.15-0.25: **1.5 %** (n=15); 0.25-0.4: **2.8 %** (27); 0.4-0.6: **10.2 %** (16); 0.6-1.0: **12.6 %** (4). Step between 0.25-0.4 and 0.4-0.6. Topped-out (PVI/PAC>=0.5, n=10) vs low (<0.25, n=17) lake-years: AUC 1.0 (very small, lake-clustered sample). **Whole-lake proxy, not the per-pixel threshold you asked for.** |
| **2. Sector grass rule at cell level, Snohomish polygons** (5 lakes, **60 positive cells, 54 of them Roesiger**) | Recall **1.00** (every mapped floating-leaf cell the rule can reach is found). Precision depends on which scene: closest clear date 0.54 (F1 0.70, IoU 0.54), driven by one bad scene (Storm 2023-08-18, 39 false cells); **a Sector-style pass-acceptance rule (scene must read >= 50 % of non-grass water) 0.92 (F1 0.96, IoU 0.92)**; persistence (median of the clear dates >= 0.5) **1.00 / 1.00 / F1 1.00** (zero false cells). Votes >= 2 of N gives only 0.40 precision, second-highest 0.40, max 0.21: those are not strong filters here. The 40 m shore erosion in Sector's grass mask makes **49 % of the whole-lake truth unreachable**: whole-lake recall 0.51 for the single pass. The "bed-to-bank" strip Sector adds recovers it (whole-lake R 0.92, P 0.91, F1 0.92 with the strip). Small positive set; do not generalise. |
| **2b. Same rule vs Florida FWC points** (7 lakes, presence-only; recall on cells holding a point) | Cell recall on surface (floating+emergent) points **0.32** single date (0.32 shipped-style pass); persistence lifts it: median across clear dates 0.43, votes>=2 0.48, max 0.54 (flag rate on background cells stays 0.4-0.6 %). On submersed-only cells the vote is **3-8 %** (essentially none). Recall is lower than the 0.60 per-pixel recall of note 04 because a cell needs >= 50 % plant pixels and a point is a single 10 m pixel in a ~44 m cell. |
| **3. Clarity proxy** | Secchi from the Water Quality Portal (FL LAKEWATCH + FDEP + water-management districts) for 7 tested lakes and 49 of the 50 PAC lakes. **Clarity does not rescue detection; the relation is confounded and runs the "wrong" way.** Across the 7 original lakes (n=7!) the best-clarity lake (Yale, 3.0 m) still has submerged AUC 0.52 and cell-level surface recall 0.37. In the 128 lake-years with Secchi, S2-vs-sonar agreement (rho with PVI) is highest in turbid lakes (<0.5 m: 0.78, n=16; 0.5-1 m: 0.63, n=57) and vanishes in clear lakes (1-2 m: 0.26; >=2 m: 0.11) because clear Florida lakes carry their sonar volume as *deep* submerged beds that never reach the surface. Among high-sonar-volume lake-years (PVI>=15, n=37) grass fraction falls with Secchi (rho -0.56): clear lakes like Kings Bay, Maitland, Sheen, Fairview (Secchi 2-3 m, PVI 17-34) show 0-1 % grass cells. The proxy quality is low (lake/year medians of sparse, multi-agency, multi-station readings; not at the pixel or scene date). |
| **Fallback pilot: Carver County MN sonar biovolume points** (Reitz Lake, 12,342 points) | **Inconclusive/negative.** Biovolume is nearly all in a 1-2 pixel shoreline fringe; open water is zero. Per-scene AUC of NDVI/NDAVI/FAI 0.46-0.58 (chance), Lyzenga depth-invariant indices 0.4-0.77 and erratic scene to scene. Survey date is not in the metadata (layer published Dec 2019), so scene dates are guesses; no depth. One small eutrophic lake. |

Bottom line, honestly: the data that would answer the pixel-level, depth-banded question (BioVolume rasters) is not obtainable today. What I can say with real sonar absences is lake-level: S2 plus Sector's rule tracks sonar **volume** moderately (rho about 0.4-0.5, AUC about 0.8 for high vs low), tracks sonar **area** weakly, and only sees beds whose mean canopy reaches roughly 40 % of the water column or more. Cell voting, a read-coverage acceptance rule and temporal persistence all clean the false positives of the single-date pixel rule on clear-water lily beds; none of them make submerged vegetation visible.

## 2. FWC BioVolume ImageServers: what was found and how it failed

* Services directory: `https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC?f=json` lists `WhatsHappening_BioVolume2015` ... `2023` (ImageServer), `WhatsHappeningOnMyLake` (MapServer), `WHOML_bathymetryService` (MapServer). ArcGIS Online items by FWC (`franklin.alexander`) point to an internal host (`fwc-spws8.fwc.state.fl.us:6443`, unreachable) and name two further services (`LTM_BioVolume_mosaics`, `LTM_BioVolume2019`, `WHOML_lakesBathymetry`) that return "not found" on the public host and "Token Required" on `gis.myfwc.com`.
* The live viewer (`https://gis.myfwc.com/whoml/`, Aquatic Plants widget `PlantMonitoring.js`, function `_addBioVolumeData`) builds `.../Projects_FWC/WhatsHappening_BioVolume<year>/ImageServer` as an ArcGIS image-service layer (year from the LTM year filter, opacity 0.75, legend `bioVol_legendDiv`). The units are therefore only known to be the BioBase biovolume convention (percent biovolume = canopy height / water depth x 100 per ping, kriged to a grid) from FWC's use of BioBase; not verified against service metadata.
* Failure evidence: 8+ concurrent `curl -m 100` and four `curl -m 580` requests, one open-ended `curl` that finally returned an empty body after about 45 min, a browser `fetch` aborted at 40 s from the viewer's own origin. `.../ImageServer/info` answers instantly with an error (the web server is up; the image-service instance is hung).
* What exists around it and works: `MapServer/31` (lake bathymetry bands, depth in ft, used in note 04), `MapServer/33` (LTM point intercepts), `/35` lakes, `/36` LTM plant data (215,653 site x species rows with `Value`; not used), `/41` `LTM_lakes_PAC_PVI` (used here). These live under the same MapServer, so they are also the closest sonar-derived absence information FWC currently serves publicly.
* Other biovolume sources found by ArcGIS Online search: Carver County MN Reitz/Brickyard (points, used as pilot; Brickyard is 300 m wide and its SCL water mask has 140 pixels, not usable), NYSDEC Niagara River 2023 biovolume contours (36 overlapping polygon bands in a flowing river, no depth; not attempted), Winter Haven FL tile cache (`BioVolume_Update_20180522`, rendered tiles only), Lake St Clair 2003-2011 rasters (pre-Sentinel-2). None gives pixel biovolume plus depth plus S2-era dates for lakes.

Not delivered because of this: AUC/PR per biovolume class (none/low/moderate/high), stratification by FWC bathymetry band against biovolume, "surface-topped vs below surface" at pixel level, S2 indices (NDAVI, FAI, band ratios, Lyzenga G/B and G/R, red-edge) against pixel biovolume for 3-6 lakes. The code that would do it is written and generic (`scripts/bvlib.py`: features incl. log band ratios and covariance-method Lyzenga indices, distance-matched weighted AUC; `scripts/16_carver_test.py` is the template) and only needs a biovolume raster aligned to the 10 m grid.

## 3. Data sources and URLs

| item | URL / path | notes |
|---|---|---|
| FWC LTM lake PAC/PVI (sonar, lake-year) | `https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer/41` -> `data/fwc_ltm_lakes_PAC_PVI.json` | 423 rows, 126 lakes, 2015-2023. PAC/PVI definitions as FWC/BioBase use them (percent area covered; percent volume infested); I did not find a methods page, so exact sonar processing is **assumed**. Okeechobee rows (sub-areas) excluded. |
| LTM survey dates | layer 33 points (`data/fwc_ltm_point_intercepts.json`, note 04) | lake-year median date of point intercepts used as the survey date (the sonar survey date itself is not published; same program, same summer). |
| FWC lakes polygons | layer 35 (`data/fwc_ltm_lakes.geojson`) | selection: 1.5-130 km2, survey month May-Oct: 151 lake-years (`data/pac_lakeyears.json`); after dropping 8 Okeechobee rows 143 lake-years in 53 lakes were processed, 130 lake-years in 50 lakes had a usable scene. |
| Sentinel-2 | Earth Search `https://earth-search.aws.element84.com/v1`, `sentinel-2-c1-l2a` (fallback `sentinel-2-l2a`, 2022) | up to 2 clear (>=75 % of lake cells seen) scenes within +-21 d of the survey median per lake-year; lean cache `out/s2cache_pac/` (482 files, 1.5 GB local; total new network use under the 2 GB cap, not metered). 13 lake-years had no qualifying scene (e.g. Panasoffkee 4 years). |
| Secchi | Water Quality Portal `https://www.waterqualitydata.us/data/Station/search` and `/Result/search`, characteristic "Depth, Secchi disk depth" -> `data/secchi/*.csv`, `out/secchi_*.json` | stations inside the lake polygon (+80 m); unit-converted to m; per lake-year median May-Oct of the survey year (n>=2) else +-1 year (n>=3). WQP returns HTTP 429 under load; the fetch script retries with sleeps. |
| Snohomish polygons and FWC points | as note 04 (`data/`) | unchanged. |
| Carver County MN biovolume points | `https://services.arcgis.com/wMZT8kNwa6tOxhKg/arcgis/rest/services/ReitzLakeBiovolume/FeatureServer/0` (and Brickyard) -> `data/carver_*_biovolume.json` | field `BioVolume` 0.0001-0.83 (fraction of water column, assumed from BioBase convention). |

## 4. Methods

### 4.1 Cell-level replica of Sector's grass rule (`scripts/cell_lib.py`, `11_cells.py`, `12_cell_metrics.py`, `13_cell_fwc.py`)

Replicated from `derive_water_surface.py` (constants copied verbatim): 10 m pixel fields in `_s2_native_fields` (veg = NDVI(B8A,B04) >= 0.30 with `max(1e-6, sum)` denominator; SCL bank classes (2,4,5,7); 60 m cloud standoff and 600 m "real cloud" standoff (clouds of >= 25 px at 20 m); 100 m structure standoff; 100 m haze standoff; cloud-edge SWIR gate 0.012 within 1.5 km; haze-edge 400 m / SWIR 0.010; turbidity-readable gate `SWIR <= 0.0215 & FAI <= 0.005 & NDVI <= 0.10 & red > 0`). Pixels are averaged onto Sector's 50 m web-mercator frame (`Frame`, `Resampling.average`; ground cell 33.5 m at the Snohomish latitude, 43.5-44 m in Florida). A cell is **grass** when `gfrac >= 0.5` (share of seen pixels that are plant), the cell lies in the lake eroded 40 m (`clarity` mask) **and no turbidity was read there** (`isnan(acc)`; a read needs >= 25 % readable pixels). Variants:

* `single (closest clear date)`: nearest scene with >= 75 % of lake cells seen.
* `SHIPPED pass`: Sector's pass acceptance from `build_clarity`: nearest-to-survey scene that reads >= 50 % of the non-grass clarity water (fallback: best coverage >= 25 %). (Sector walks back from the newest date; here "nearest to the survey".)
* Persistence over the clear dates within +-45 d (+-21 d also run): `votes >= 2 / >= 3 of N`, `majority of seen dates`, `max`, `second-highest`, `median` of g' where g' = gfrac with read cells set to 0 (so the not-read guard is inside the composite), each also restricted to coverage-passing scenes ("only cov>=0.5 passes").
* "+ to_bank strip": Sector's post-step that paints the unread band behind a bed (within 90 m of grass, in the 40 m band) as grass; evaluated on the whole-lake population.

Ground truth cells: polygon share of each cell (Snohomish). Positive = floating-leaf share >= 0.5. Negatives = "strict-none" (< 5 % of any mapped class) or "buffered-none" (no label within 2 cells, removes edge cells). Populations: (A) grass-eligible cells (what the rule can call), (B) whole lake. FWC points: recall on cells containing >= 1 surface point; vote rate on submersed-only cells; flag rate on background cells > 3 cells from any recorded point.

**Deviations from Sector (limitations of the replica):** window is the lake bbox + about 200 m (Sector pads 1 km), so cloud/structure/haze standoff distances are truncated at the window edge; 20 m B8A/B11/SCL come from the cached 10 m nearest upsampling (equal to Sector's `up()` except where the window origin is not 20 m aligned); single tile, no tile blending or offset matching; speck/shadow/tiny-patch post filters and grass-under-cloud borrowing (`build_clarity`) were not replicated, so reported coverage of the pass test and the bed-to-bank strip are approximate; the pass-acceptance coverage test is therefore stricter than production (median pass coverage only 0.36 in the 130 lake-years, 43 pass 0.5).

### 4.2 Lake-level test against sonar PAC/PVI (`scripts/19..21`, `24`)

Per lake-year, per scene: Sector cell grass fraction of lake cells, pixel shares (NDVI(B8A,B4)>=0.30; FAI>0.005), percentiles (NDVI/NDAVI/FAI/NIR) on lake pixels >= 40 m from shore. "single" = nearest passing scene (cov>=0.5, else best coverage); "min2" = the lower of the two scenes (a two-date persistence). Metrics: Spearman against PAC and PVI, AUC for high vs low lake-years, binned medians; per-lake-mean Spearman as a clustering check; Secchi strata. Lake-years are not independent (50 lakes, up to 6 years each).

### 4.3 Carver pilot (`scripts/14..16`)
Points to a 10 m grid (mean per pixel), classes none (<0.02) / >=0.10 / >=0.25 / >=0.50, shore proxy = distance to the edge of the filled surveyed area, shore-distance-matched weighted AUC per clear scene May-Oct 2019, band ratios and covariance-method Lyzenga index (no depth available).

## 5. Results

### 5.1 Cell-level, Snohomish (positives: floating-leaf share >= 0.5; population = grass-eligible cells; +-45 d clear dates, N = 16-18 per lake)

Pooled over 5 lakes: 60 positive cells (Roesiger 54, Blackmans 6, Serene/Storm/Bosworth 0, because their beds lie inside the 40 m shore band), 1,331 strict negatives. Source: `out/metrics_cell_snoco.json`.

| method | TP | FP | FN | precision | recall | F1 | IoU | FPR |
|---|---|---|---|---|---|---|---|---|
| single, closest clear date | 60 | 51 | 0 | 0.54 | 1.00 | 0.70 | 0.54 | 3.8 % |
| **shipped-style pass (cov >= 0.5)** | 60 | 5 | 0 | 0.92 | 1.00 | 0.96 | 0.92 | 0.4 % |
| max g' >= 0.5 over all dates | 60 | 228 | 0 | 0.21 | 1.00 | 0.35 | 0.21 | 17.1 % |
| votes >= 2 of N | 60 | 90 | 0 | 0.40 | 1.00 | 0.57 | 0.40 | 6.8 % |
| votes >= 3 of N | 60 | 42 | 0 | 0.59 | 1.00 | 0.74 | 0.59 | 3.2 % |
| second-highest g' >= 0.5 | 60 | 90 | 0 | 0.40 | 1.00 | 0.57 | 0.40 | 6.8 % |
| majority of seen dates | 60 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| **median g' >= 0.5** | 60 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |
| votes >= 2 (cov-passing scenes only) | 60 | 20 | 0 | 0.75 | 1.00 | 0.86 | 0.75 | 1.6 % |
| median (cov-passing scenes only) | 60 | 0 | 0 | 1.00 | 1.00 | 1.00 | 1.00 | 0 |

Against "buffered-none" negatives (excludes cells next to mapped polygons) the single date reaches P 0.68 and the shipped pass P 1.00; with +-21 d windows votes >= 2 reaches P 0.97 (F1 0.98). With "any mapped vegetation >= 0.5" as the target (adds assemblage/arrowhead beds): single P 0.70 R 0.64 F1 0.67; median P 1.00 R 0.56 F1 0.72, shipped P 0.95 R 0.55 F1 0.69, i.e. the rule finds only about 55-64 % of the mixed native beds, which are not always surface-reaching.

Whole-lake population (grass mask only covers the lake eroded 40 m): single pass P 0.54 R 0.51 F1 0.53 IoU 0.36; shipped pass P 0.92 R 0.51 F1 0.66; **shipped pass + bed-to-bank strip P 0.91 R 0.92 F1 0.92 IoU 0.84** (FPR 0.7 %). The strip is credited with the recall, but it is a proximity rule, not a reading.

Why "single" fails: false cells come in whole-scene bursts. Storm 2023-08-18 gave 53 grass cells (39 false) with only 4 readable cells (haze/thin cloud the SCL missed); Serene 2023-08-03 76 cells (57 false) with zero readable cells; Storm 2023-09-09 68 cells with 61 false. The coverage acceptance test rejects those scenes; persistence rejects them without needing that test. Figure `out/figures/cell_snoco_Roesiger_Storm.png` (truth | single | shipped pass | median, Roesiger above, Storm below). Roesiger alone: single P 0.86 F1 0.92; shipped P 0.92 F1 0.96; median 1.00.

### 5.2 Cell-level, Florida (FWC points, presence-only), 7 lakes, `out/metrics_cell_fwc.json`

Rate of positive vote among cells that hold: surface (floating or emergent) points, floating points, emergent points, submersed-only points, and background cells.

| method | surface | floating | emergent | submersed-only | background flag |
|---|---|---|---|---|---|
| single | 0.320 | 0.316 | 0.338 | 0.029 | 0.004 |
| shipped-style pass | 0.322 | 0.307 | 0.382 | 0.043 | 0.004 |
| votes >= 2 of N | 0.484 | 0.490 | 0.458 | 0.076 | 0.005 |
| votes >= 3 of N | 0.435 | 0.432 | 0.444 | 0.054 | 0.004 |
| majority of seen dates | 0.445 | 0.445 | 0.449 | 0.038 | 0.004 |
| median g' | 0.432 | 0.429 | 0.444 | 0.036 | 0.004 |
| max | 0.542 | 0.555 | 0.489 | 0.100 | 0.006 |

Only 1-9 qualifying dates per lake (Harris and Panasoffkee have one), so persistence is thin there. Panasoffkee's only scene is 18 d from the survey (recall 0.06). Because FWC is presence-only, background flag rate is "unsurveyed cells flagged", not a false-positive rate. Cell recall is below note 04's per-pixel recall (0.60) for the reason in section 1.

### 5.3 Lake-level vs sonar PAC/PVI (130 lake-years, 50 lakes), `out/metrics_pac.json`, `out/pac_lakeyear_table.json`, figure `out/figures/pac_lake_level.png`

| S2 summary (single pass) | Spearman vs PVI | vs PAC | AUC PVI>=20 vs <5 (27/44) | AUC PAC>=50 vs <20 (43/51) |
|---|---|---|---|---|
| Sector cell grass fraction | 0.43 | 0.35 | 0.79 | 0.65 |
| share of lake pixels NDVI(B8A)>=0.30 | 0.47 | 0.40 | 0.84 | 0.70 |
| share FAI>0.005 | n/a | 0.36 | 0.82 | 0.70 |
| FAI 90th pct | 0.45 | 0.39 | 0.84 | 0.75 |
| NDVI 90th pct | 0.43 | 0.34 | 0.81 | 0.72 |
| NDAVI 90th pct | | | 0.78 | 0.63 |
| NIR 90th pct | | | 0.65 | 0.55 |

Per-lake means (50 lakes): Spearman of cell grass fraction 0.42 (PVI), 0.33 (PAC): clustering does not change the picture. Persistence ("min of two scenes", n=96): rho 0.41 with PVI, 0.32 with PAC, no gain. **Restricted to the 43 lake-years whose scene passes the coverage test, rho collapses to about 0 (PVI 0.10, PAC -0.01)**: the pass test selects lakes with little surface vegetation (high-cover lakes fail it), which is both a sample-size and a selection effect; treat the whole-sample numbers as the primary and this as a caution about the acceptance rule on small lakes under my truncated window.

Dose response with mean biovolume in the covered area (PVI/PAC, PAC>=30, n=64), median Sector grass cells as % of lake cells: 0.15-0.25 1.5 %, 0.25-0.4 2.8 %, 0.4-0.6 10.2 % (75th pct 28 %), 0.6-1.0 12.6 %. By PAC alone the median is flat above PAC 40 (4.5 %, 2.6 %, 2.4 % for PAC 40-60, 60-80, 80-100). By PVI: 0.4 % (PVI<2), 1.0 %, 2.3 %, 2.7 %, 6.4 %, 9.4 % (PVI>40).

Misses: Yale 2023 (PAC 76, PVI 14, Secchi 3.0 m) 2.2 % grass cells; Apopka 2021 (37 / 15) 1.3 %; Harris 2018 (30 / 11) 1.0 %; Griffin 2019 (38 / 10) 2.8 %; versus Cypress 2022 (99 / 73) 9.7 % and Tohopekaliga 2018-2023 (PVI 24-41, PAC 55-85) 24-34 %. High grass fractions with low sonar PAC (a few lake-years at 18-27 %) most likely reflect floating or emergent mats that sonar under-counts, or scene artefacts (not checked lake by lake).

### 5.4 Clarity proxy

Seven original lakes (survey-year May-Sep Secchi median, WQP): Orange 0.73 m, Griffin 0.65, Apopka 0.34, Harris 0.91, Panasoffkee 1.2, Yale 3.0, Cypress 0.4 (only 2 readings). Spearman (n=7, not significant) of Secchi with: surface AUC_NDVI -0.18, submerged AUC_NDVI -0.43, cell recall of surface -0.71, vote rate on submersed cells -0.68: **no support for "clearer is more detectable"**; the two clearest lakes (Panasoffkee, Yale) detect worst at cell level. Table `out/secchi_strat.json`, `out/secchi_spearman.json`.

128 PAC lake-years with Secchi (`out/metrics_pac_secchi.json`), rho of cell grass fraction with sonar PVI by Secchi stratum: <0.5 m 0.78 (n=16, 8 lakes), 0.5-1 m 0.63 (57), 1-2 m 0.26 (34), >=2 m 0.11 (21). AUC (pixel NDVI>=0.30 share, PVI>=15 vs <5): 0.98 at 0.5-1 m (13 vs 20), 0.66 at 1-2 m (11 vs 14); other strata too few. Secchi itself correlates with sonar cover and volume (rho 0.43 PAC, 0.29 PVI). Interpretation: in this data set Secchi mostly marks the **type** of vegetation (clear lakes: deep submerged beds with large volume; turbid shallow lakes: surface-reaching mats), so it cannot be separated from canopy height / depth. **Proxy quality: low.** Lake-level medians of mixed agency data; per-scene or per-pixel clarity not available; Secchi on the bottom flagged rarely (0-5 %) so depth-limited readings are not corrected.

### 5.5 Carver MN pilot (`out/metrics_carver_reitz.json`, `out/figures/map_carver_reitz.png`)
Reitz Lake: 3,198 "none", 536 >= 0.10, 254 >= 0.25, 63 >= 0.50 biovolume pixels. Per clear scene (11 scenes May-Oct 2019) shore-distance-matched AUC vs none for BV >= 0.10: NDVI 0.48-0.57, NDAVI 0.47-0.58, FAI 0.50-0.59, Lyzenga G/B 0.40-0.69, G/R 0.47-0.76 (no consistent date); BV >= 0.50: NDVI 0.46-0.63. NDVI over the lake is negative in every scene; Sector's rule flags 9-18 % of "none" pixels (shore pixels) and 64-95 % of BV >= 0.10 pixels, but that is the shore fringe both share. Not usable evidence either way.

## 6. Limitations (read before quoting a number)

1. **The primary request (pixel biovolume, depth-banded, surface-topped vs below surface) was not tested**; lake-level PAC/PVI is a coarse substitute and measures different things (lake-wide averages of sonar surveyed along transects, not per-pixel canopy).
2. PAC/PVI processing and survey dates are not documented in the services; survey date is assumed equal to the median LTM point-intercept date for that lake-year. Sonar misses floating mats and cannot see in very shallow water; PAC counts all vegetation, including types S2 cannot see at all. PAC/PVI definitions are taken from BioBase/FWC usage, not from FWC documentation.
3. Lake-years are clustered (50 lakes), the selection excludes lakes > 130 km2, lakes with no clear scene, and Okeechobee (polygon ambiguity): "Okeechobee-class lakes" are represented only by Kissimmee-chain lakes (Tohopekaliga, East Toho, Hatchineha) and Apopka.
4. The Snohomish cell test has 60 positive cells (54 in one lake); cell-level perfect scores for median/majority persistence are from a single clear-water bed and say nothing about turbid lakes. Absence is assumed outside mapped polygons (note 04). Shore erosion removes most beds in the small lakes.
5. The replica deviates from production (section 4.1). In particular pass coverage is understated, so the pass-acceptance rule is more aggressive here than in production; the "shipped-style" numbers should be read as "with a coverage gate", not as exactly what ships.
6. Single-date vs persistence comparisons in Florida use 1-9 dates per lake; Harris and Panasoffkee have one.
7. Secchi: lake/year medians from sparse multi-agency readings (n=2 to 90 per lake-year), no scene-date match, confounded with vegetation type and depth.
8. Carver pilot has unknown date, one lake, no depth.
9. No confidence intervals. Pixels and cells are spatially autocorrelated, lake-years clustered.

## 7. Dead ends

* `WhatsHappening_BioVolume2015..2023` ImageServers (all years, metadata/export/query/POST/WMS, curl and browser): hang. Retry later; if they come back, run the template in `scripts/16_carver_test.py` with a raster read via `exportImage`.
* `LTM_BioVolume_mosaics`, `LTM_BioVolume2019`, `WHOML_lakesBathymetry`, `WhatsHappeningOnMayLake_bioVolume`, `WhatsHappeningBathymetry`: named in ArcGIS Online, not on the public server (not found / token required); the host they list (`fwc-spws8.fwc.state.fl.us:6443`) is unreachable from outside.
* `gis.myfwc.com/arcgis/...` (404), `gis.myfwc.com/image|mapping/rest/services/Projects_FWC` (exist but no biovolume).
* Web search found no public BioBase export for Florida lakes; Niagara River biovolume contours are overlapping bands in a river (not attempted); Lake St Clair rasters predate Sentinel-2; Brickyard Lake (MN) too small.
* WQP rate limits (HTTP 429) silently emptied about half of the first Secchi pulls; fixed by retries and resume.

## 8. Reproduce

```
cd ~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments
# (note 04 data and stacks already present)
.venv/bin/python -W ignore -u scripts/11_cells.py snoco ; .venv/bin/python -W ignore -u scripts/11_cells.py fwc   # cell fields per lake
.venv/bin/python -W ignore scripts/12_cell_metrics.py snoco     # -> out/metrics_cell_snoco.json
.venv/bin/python -W ignore scripts/13_cell_fwc.py               # -> out/metrics_cell_fwc.json
.venv/bin/python -W ignore scripts/22_cell_figs.py              # -> out/figures/cell_snoco_Roesiger_Storm.png
.venv/bin/python scripts/17_secchi.py ; .venv/bin/python scripts/18_secchi_strat.py   # 7 lakes
# lake-level sonar (PAC/PVI) test; PAC/PVI json pulled with a plain query to MapServer/41 (see section 3)
.venv/bin/python scripts/19_pac_select.py
.venv/bin/python -W ignore -u scripts/20_pac_extract.py 5       # ~1 h, ~1.5 GB cache, resumable
.venv/bin/python scripts/23_secchi_pac.py                       # WQP is rate-limited; re-run until complete
.venv/bin/python -W ignore scripts/21_pac_analysis.py ; .venv/bin/python -W ignore scripts/24_pac_secchi.py
# pilot
.venv/bin/python scripts/14_fetch_carver.py ; .venv/bin/python -u scripts/15_carver_s2.py ; .venv/bin/python -W ignore scripts/16_carver_test.py
.venv/bin/python scripts/25_manifest05.py                       # appends new files to ../MANIFEST.jsonl
```
PAC/PVI download: `GET .../WhatsHappeningOnMyLake/MapServer/41/query?where=1=1&outFields=*&returnGeometry=false&f=json&resultRecordCount=3000` saved to `data/fwc_ltm_lakes_PAC_PVI.json` (rows = `features[].attributes`).

Outputs: `out/metrics_cell_{snoco,fwc}.json`, `out/metrics_pac.json`, `out/metrics_pac_secchi.json`, `out/pac_lakeyear_table.json`, `out/secchi_*.json`, `out/metrics_carver_reitz.json`, figures `out/figures/{cell_snoco_Roesiger_Storm,pac_lake_level,map_carver_reitz}.png`.
