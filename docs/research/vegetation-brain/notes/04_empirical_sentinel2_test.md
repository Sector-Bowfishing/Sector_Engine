# 04. Empirical test: Sentinel-2 indices vs real aquatic-vegetation survey data

Research only. No git repo touched. Everything lives under `~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/` (scripts in `scripts/`, outputs in `out/`, raw ground truth in `data/`). Every data file is logged with bytes + sha256 in `../MANIFEST.jsonl` (240 rows appended by `scripts/06_manifest.py`).

## 1. Headline (honest version)

| question | answer |
|---|---|
| Surface-reaching floating-leaf beds (lilies, watershield), clear PNW lakes, same-week Sentinel-2 | **Detected very well.** Shore-distance-matched AUC: NDAVI 0.995, FAI 0.992, NDVI 0.982. Best-threshold F1 0.96-0.97, IoU 0.92-0.95, leave-one-lake-out F1 0.94-0.97. |
| Same, but Sector's fixed rule `NDVI >= 0.30` (B8A/B4, exact formula from `derive_water_surface.py`) | Recall 0.993 but **false-positive rate on open water 9.9 % per pixel (single date)**: precision 0.49 at the survey's raw prevalence (8.9 % of pixels), 0.73 when negatives are shore-matched. F1 0.66 raw. A cell-level vote (Sector uses `gfrac >= 0.5`) would suppress most of this noise; not tested here. |
| Surface-reaching floating + emergent, Florida (7 lakes, FWC point survey, presence-only) | **Mediocre.** Sector rule recall **0.60** (single date within about +-7 d), 0.74 with a 3-month max composite; AUC vs background only 0.65-0.67 shore-matched (0.86-0.89 unmatched), best-F1 barely beats the trivial classifier. Recall is 0.85 within 30 m of shore and 0.35 beyond 120 m. |
| Submerged vegetation (any index, either region) | **Not usefully detectable.** Shore-matched AUC 0.57-0.77 in PNW (best NDAVI 0.77), 0.57-0.69 in Florida (best FAI 0.68); best-F1 about equal to the all-positive baseline (0.667). Sector rule recall on pure submersed (Florida): **4.5 %** (single), 12 % (composite). Several lake/depth strata have AUC below 0.5. |
| 3-month max composite vs single date | Does **not** beat a good same-week scene for ranking (PNW surface AUC 0.982 to 0.960 NDVI). It raises recall of a fixed threshold (FL 0.60 to 0.74; submerged 0.585 to 0.833 in PNW) but **roughly triples the false-positive rate** (PNW 9.9 % to 31.7 %; FL 4.5 % to 8.6 %). Composite only helps when the single date is cloudy or off-season. |
| Multi-band gradient-boosted model, leave-one-lake-out (upper bound, no fixed threshold) | PNW surface AUC 0.71-0.998 (4 of 5 lakes above 0.98); PNW submerged 0.59-0.83; Florida surface 0.57-0.72, submerged 0.41-0.79 (Apopka is the only lake above 0.7, Harris/Cypress/Panasoffkee/Yale are at chance). ML does not rescue submerged. |

Bottom line for the Vegetation Brain: Sentinel-2 can map **dense surface mats and floating-leaf beds** (the "topped-out grass" the Sector rule targets) at near-survey quality in clear water, but only when the plant canopy actually reaches the surface in the pixel, and the existing 0.30 rule needs a spatial/cell-level vote and a dark-water guard. It cannot map **submerged** vegetation, which for bowfishing (fish cover under the surface) is the harder and more valuable product. Anything for submerged habitat needs a different source (depth/clarity-conditioned prior, sonar like the FWC biovolume rasters, or a learned model on survey labels).

## 2. Ground truth: what was tried

| source | access | verdict |
|---|---|---|
| **Snohomish County (WA) Surface Water Mgmt lake aquatic plant surveys** `gis.snoco.org/host/rest/services/Hosted/Lake_Aquatic_Plant_Surveys_Service/FeatureServer` | Works, no auth. 16 layers, dated field-survey polygons (yellow/fragrant waterlily, watershield, native assemblages, curly-leaf pondweed, slender arrowhead) + milfoil points + lake polygons | **USED.** 5 lakes, surveys Jul-Aug 2023 (Roesiger Jul 2021). Real polygons with density, same-month as imagery. |
| **FWC Florida Long-Term Monitoring plant point intercepts** `ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer/33` (+ lake polygons layer 35, depth bands layer 31) | Works. 96,055 dated points, 2012-2023, species lists per site | **USED.** 7 lakes. Presence-only (see limitations). Species mapped to life form in `scripts/lifeform.py`. |
| FWC `WHOML_test/MapServer` (the URL web search returned) | HTTP 500 "service not found" | Dead end; the same layers exist under `WhatsHappeningOnMyLake` (found by listing the services directory). |
| FWC BioVolume ImageServers (`WhatsHappening_BioVolume2015..2023`) | Exist (sonar-derived SAV biovolume rasters) | **Not tested; flagged as the best next ground truth for submerged vegetation** (dense, dated, depth-aware). |
| USFWS NWI `fwsprimary.wim.usgs.gov/server/rest/services/Wetlands/MapServer` | Layer list empty, `/0` returns 500 | Dead end. `fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0` does respond (layer "Wetlands"). **Not used**: NWI is photo-interpreted with mapping dates from 1980s to 2010s, so it fails the "dated, near the imagery" requirement. |
| USGS UMESC / LTRM Upper Mississippi vegetation (`umesc.usgs.gov/data_library/vegetation/...`) | Page returned HTTP 200 by curl, 502 via WebFetch; ScienceBase items located (1998-2019 macrophyte release) but no point CSV located in the time budget | Not used. Candidate for a Midwest, turbid-river class next round. |
| USGS Lake Erie eastern basin AV polygons (ScienceBase `5a32dd18...`) | Item lists only the FGDC xml file in the json; zip not fetched | Not used; also OBIA from aerial imagery (a classification, not a survey). |
| Minnesota Biological Survey lakes + aquatic plants (`gisdata.mn.gov`) | Dataset page responds (301); points only | Not downloaded (presence points, no extent). |
| TVA Guntersville, Wisconsin DNR point-intercept, TPWD, EDDMapS | Not probed (time) | Open. |

## 3. Data actually used

**Snohomish (PNW, clear to mesotrophic, cool).** Layers 6,7,8 (yellow waterlily, watershield, fragrant waterlily) = **floating_leaf = "surface"** (57 ac mapped, 188 dense polygons). Layers 9-13 + milfoil points = `submerged_assemblage` (native mixed assemblages, curly-leaf; **note** several assemblages list floating-leaf pondweed, bulrush and spike-rush, so this class is a mixed shallow-water bed, not pure submersed). Layer 14 = slender arrowhead (`arrowhead`, partly emergent/submersed). "Submerged" in the tables = `submerged_assemblage` + `arrowhead`. Background = lake pixels (county lake polygon eroded 10 m) at least 20 m from any mapped polygon. Lakes and survey dates (median polygon date): Serene 2023-07-25, Bosworth 2023-08-01, Blackmans 2023-08-07, Storm 2023-08-17, Roesiger 2021-07-18. 21,946 labelled pixels in the pooled set (1,669 surface, 3,220 submerged, 17,057 background). Storm has only 20 floating-leaf pixels.

**FWC (Florida, eutrophic to clear-spring, warm).** Lakes and survey year: Orange 2022, Griffin 2019, Apopka 2021, Harris 2018, Panasoffkee 2022, Yale 2023, Cypress 2022 (all May-Sep). Point class: `floating` if any floating or floating-leaved taxon is recorded (water-lettuce, hyacinth, spatterdock, lilies, tussock...), else `emergent` if any emergent, else `submersed` (hydrilla, eelgrass, coontail, naiad, stonewort, bladderwort ...); algae and woody/shore records are excluded from the classes. "Surface" = floating + emergent; "submerged" = submersed-only points. Each point is 1 pixel (10 m). Pooled: 2,264 surface px, 12,805 submerged px, 2.75 M background px (single date).

**Sentinel-2.** Earth Search STAC `https://earth-search.aws.element84.com/v1`, collection **`sentinel-2-c1-l2a`** (the collection Sector uses; reflectance = DN*1e-4 - 0.1). This collection has **no 2022 scenes** (queried 2026-10-13), so the 2022 lakes (Orange, Panasoffkee, Cypress) fall back to `sentinel-2-l2a`, whose COGs already have the offset removed (Sector's module docstring documents the same trap). A first pass of this experiment applied the -0.1 offset twice on `sentinel-2-l2a`; every result from that pass was discarded (`out/_discarded_double_offset/`). SCL cloud/shadow/cirrus/snow/no-data masked with a 1-pixel dilation. All scenes within +-45 d of the survey were read (windowed COG range reads, 20 m bands nearest-resampled to the 10 m grid). Single date = the clearest scene (>= 75 % of lake pixels clear) closest in time to the survey (|dt| 1-7 d, except Panasoffkee +18 d). Composite = per-pixel max over all clear scenes in the +-45 d window (4-19 scenes; **Harris and Panasoffkee only have 1 qualifying scene**, so their composite = single). Bands B02-B08, B8A, B11, B12 + SCL.

**Indices.** NDVI=(B8-B4)/(B8+B4); NDAVI=(B8-B2)/(B8+B2); FAI=B8-[B4+(B11-B4)*(842-665)/(1610-665)]; red-edge NDRE1=(B8A-B5)/(B8A+B5), NDRE2=(B8A-B6)/(B8A+B6); NDWI=(B3-B8)/(B3+B8); NDII=(B8-B11)/(B8+B11); plus raw NIR/SWIR. Normalised-difference denominators floored at 0.01 to stabilise dark water. **Sector rule** = exact formulas from `jobs/lake-surface/derive_water_surface.py`: `NDVI=(B8A-B4)/max(1e-6,B8A+B4) >= 0.30`, and the "+FAI" variant `or FAI(B8A,B4,B11) > 0.005`. (In Sector FAI > 0.005 is a water-quality *gate*, not the grass test; it is shown because the task asked for it, and it is very noisy as a vegetation test.)

**Metrics.** Pixel-level, background vs class. AUC (rank, expected direction; NDWI inverted). Best-F1 threshold on pooled data; leave-one-lake-out (LOLO) threshold transfer. **Shore-distance matching:** vegetation sits near shore, where adjacency, bottom reflectance and mixed land pixels brighten NIR, so unmatched AUC flatters every index (NIR and SWIR alone reach AUC 0.998 in the PNW). I therefore reweight background pixels to the positives' distance-to-shore histogram (bins 0/15/30/45/60/90/150/300 m) and report "matched" numbers as the primary ones. Matched P/R/F1 sit at 50 % prevalence, where "predict everything" scores F1 = 0.667; anything near 0.67 is no skill. Raw-prevalence numbers are given for the Sector rule so precision is not overstated.

## 4. Results

Full tables: `out/tables.md` (all indices, both variants, per lake, with 3x3 max-filter variant for FWC). Key rows:

### 4.1 PNW polygons (Snohomish, 5 lakes) - shore-matched AUC

| class | index | single date | 3-mo max composite |
|---|---|---|---|
| surface (floating-leaf) | NDAVI | **0.995** | 0.973 |
| | FAI | 0.992 | 0.987 |
| | NDVI | 0.982 | 0.960 |
| | NDWI | 0.975 | 0.984 |
| | red-edge NDRE1 | 0.809 | 0.599 |
| submerged (assemblages + arrowhead) | NDAVI | 0.771 | 0.751 |
| | SWIR | 0.719 | 0.723 |
| | NDWI | 0.707 | 0.731 |
| | NDVI | 0.696 | 0.696 |
| | FAI | 0.655 | 0.662 |
| | NDRE1 | 0.607 | 0.567 |

Best-threshold surface scores (single date, matched, in-sample): NDAVI thr 0.52 P 0.973 R 0.972 F1 0.973 IoU 0.947 (LOLO F1 0.968); FAI thr 0.037 F1 0.970 IoU 0.941; NDVI thr 0.53 F1 0.955 IoU 0.915 (LOLO 0.943). Submerged best F1 0.70-0.74 against a 0.667 no-skill baseline (NDAVI 0.739 IoU 0.586).

Per lake (single date, NDVI raw/matched AUC, surface): Blackmans 0.996/0.994, Bosworth 1.0/1.0, Roesiger 0.999/0.994, Serene 0.986/0.774, **Storm 0.856/0.536 (20 px)**. Submerged NDVI raw/matched: Blackmans 0.79/0.69, Bosworth 0.97/0.86, Roesiger 0.93/0.73, Serene 0.94/0.66, Storm 0.64/0.56.

**Sector rule (NDVI >= 0.30), PNW pooled:**

| set | class | recall | precision raw prev. | F1 raw | IoU raw | FPR on open water |
|---|---|---|---|---|---|---|
| single date | floating-leaf | 0.993 | 0.494 | 0.66 | 0.49 | 9.9 % |
| single date | submerged mix | 0.585 | 0.526 | 0.55 | 0.38 | (same) |
| composite | floating-leaf | 0.999 | 0.236 | 0.38 | 0.24 | 31.7 % |
| composite | submerged mix | 0.833 | 0.331 | 0.47 | 0.31 | (same) |
| single, `or FAI > 0.005` | floating-leaf | 0.998 | 0.352 | 0.52 | 0.35 | 18.0 % (90.6 % composite) |

Per-lake single-date recall/precision for floating-leaf: Blackmans 0.993/0.941, Bosworth 0.994/0.703, Roesiger 0.996/0.598, Serene 0.983/0.653, Storm 0.90/0.021. The Sector rule's "submerged recall" of 0.585 comes together with the 9.9 % background FPR and AUC of only 0.70: the mixed assemblage polygons contain floating-leaf and emergent species, so some recall is genuine surface canopy, not submerged detection.

Figure: `out/figures/map_snoco_Roesiger.png` (NDVI | ground truth | Sector rule) shows the floating-leaf bed reproduced almost exactly, with a fringe of shoreline false positives and no detection of the blue submerged edge beds. Other lake maps: `out/figures/map_snoco_*.png`; AUC bar charts `out/figures/auc_snoco_{single,composite}.png`.

Why precision is only 0.49 despite recall 0.99: with exact Sector arithmetic, open-water pixels whose red and B8A reflectances are both about 0.005 give NDVI +/- large values from tiny differences; about 6-10 % of dark-water pixels cross 0.30 on a single date (Roesiger 2021-07-19: 6.3 %). Lake-level and per-cell aggregation in Sector reduces this, and it is concentrated within 15-80 m of shore.

### 4.2 Florida points (FWC, 7 lakes) - presence-only

| class | index | AUC raw | AUC shore-matched (single) | matched (composite) |
|---|---|---|---|---|
| surface (floating + emergent) | FAI | 0.891 | 0.672 | 0.654 |
| | NDVI | 0.864 | 0.661 | 0.651 |
| | NDAVI | 0.850 | 0.648 | 0.638 |
| | NDRE1 | 0.860 | 0.637 | 0.622 |
| submerged (submersed-only points) | FAI | 0.680 | 0.679 | 0.644 |
| | NDVI | 0.631 | 0.631 | 0.585 |
| | NDRE1 | 0.624 | 0.624 | 0.598 |
| | NDAVI | 0.568 | 0.569 | 0.483 |

Best-F1 values (0.67-0.71 at 50 % prevalence) are indistinguishable from the 0.667 baseline: no usable threshold. With a 3x3 max filter on every index (tolerates +-10 m GPS error), surface AUC rises only to NDVI 0.655-0.665 matched (0.899-0.915 raw).

**Sector rule, Florida pooled (single date / composite):** recall on `floating` 0.60 / 0.76, on `emergent` 0.60 / 0.69, on `submersed` 0.045 / 0.124; with `or FAI > 0.005`: 0.69/0.82 (floating/emergent), 0.135 / 0.263 (submersed). Background pixel flag rate 4.5 % / 8.6 % (NDVI rule), 8.3 % / 16.3 % (with FAI). Per-lake surface recall (single): Cypress 0.82, Orange 0.81, Harris 0.69, Griffin 0.65, Yale 0.60, Apopka 0.55, **Panasoffkee 0.13** (scene +18 d from survey, one scene). Precision at raw prevalence is meaningless here (0.7-2 %) because the background includes unsurveyed vegetation, so it is not reported as a result.

By distance from shore (surface class): recall 0.85 (0-30 m), 0.56 (30-60), 0.61 (60-120), 0.35 (>120 m). Submerged: 0.42 / 0.17 / 0.11 / 0.03.

**Depth (FWC bathymetry bands, 4 lakes; `out/metrics_depth.json`):** surface AUC_NDVI by depth band 0.67 (0.6-1.2 m), 0.70 (1.2-2.0 m), 0.94 (2.0-3.0 m, only 29 px); Sector recall 0.60 / 0.33 / 0.48. Submerged AUC_NDVI 0.37 (0.6-1.2 m), 0.48 (1.2-2.0), 0.57 (2.0-3.0), 0.52 (>3 m): at or below chance at every depth, and Sector recall 9.6 % / 4.7 % / 1.0 % / 0.5 %, falling with depth. Clarity (Secchi) was not available at point level, so no clarity stratification; the lake-level contrast (clear PNW surface AUC > 0.98 vs Florida 0.65, Apopka hypereutrophic and tannic lakes lowest) is confounded with label type (polygons vs points) and cannot be attributed to clarity.

### 4.3 Single date vs 3-month composite

Ranking quality (AUC) does not improve. Fixed-threshold recall does, at a large false-positive cost. Numbers in the tables above (PNW: recall 0.993 to 0.999, FPR 9.9 % to 31.7 %; FL: recall 0.60 to 0.74, FPR 4.5 % to 8.6 %; PNW submerged recall 0.585 to 0.833 but precision 0.53 to 0.33). Max-composites also pick up undetected thin cloud/shadow and sun-glint edges. A median or "second-highest" composite, or per-pixel persistence (>= 2 of N dates above threshold), is the obvious next test.

### 4.4 Learned upper bound

`scripts/08_ml_lolo.py`: HistGradientBoosting on 12 features (indices + RGB/NIR/SWIR reflectance, no distance feature), trained on the other lakes, weights matched to shore distance. Held-out matched AUC, single date: PNW surface Blackmans 0.986, Bosworth 0.997, Roesiger 0.998, Serene 0.998, Storm 0.707; PNW submerged 0.59-0.83 (Serene 0.831, Roesiger 0.738, Blackmans 0.718, Bosworth 0.675, Storm 0.588); FL surface Apopka 0.718, Griffin 0.675, Orange 0.657, Yale 0.671, Harris 0.609, Panasoffkee 0.589, Cypress 0.571; FL submerged Apopka 0.794, Griffin 0.625, Orange 0.537, Yale 0.509, Cypress 0.507, Panasoffkee 0.488, Harris 0.409. The classifier is no better than a good single index for surface and does not generalise for submerged. (`out/ml_lolo_*.json`.)

## 5. Limitations (read before quoting any number)

1. **Survey-date mismatch.** Snohomish single scenes are 1-4 d from the survey; FWC scenes 1-18 d; FWC surveys run over 2-4 weeks, so one scene date cannot match every point. Floating mats move in days; hydrilla topping out changes in weeks.
2. **FWC is presence-only.** The point layer holds only sites where plants were recorded (no empty site rows). "Background" is every lake pixel >= 20 m from any recorded point, so it contains unsurveyed vegetation and every precision/FPR on FWC is pessimistic; only recall and the AUC-vs-background (a lower bound) are meaningful. FWC sampling is also stratified toward vegetated littoral zone.
3. **Snohomish absence is assumed.** Unmapped lake area is treated as vegetation-free; the county maps bed polygons, not exhaustive absence. Small lakes (18-140 ha), one agency, one region, 5 lakes (Storm has 20 surface pixels), 2 survey years. Surface class = water-lily / watershield beds only; no true emergent class there.
4. **Mixed pixels and geolocation.** 10 m pixels vs polygon edges and 1-pixel GPS points (+-3-10 m). I did not erode polygons for the headline numbers; a 3x3 max filter was tested on FWC only.
5. **Shore effects.** Lake polygons (county layer, FWC LTM) are not perfectly registered to the imagery; I eroded the PNW lake mask by 10 m and matched distances, but the 0-30 m band remains contaminated by land adjacency. Matched numbers are lower than raw for every index; I report both.
6. **Reflectance floor.** Dark water reaches the L2A floor; Sen2Cor can leave small negative or near-zero red/NIR. The denominator floor (0.01) for my own indices hides some of this; Sector's exact formula has no such floor, which is why its FPR is visible.
7. **No clarity data.** Secchi/turbidity per lake/date was not available; clarity is only inferable from lake class. Depth stratification exists for 4 FL lakes only (bathymetry bands, nominal 0.3-1 m depth resolution, not survey-date water level).
8. **Collection mix.** 2022 lakes use `sentinel-2-l2a` (offset already removed), others `sentinel-2-c1-l2a`; baselines differ.
9. **Class definitions are mine.** Species-to-life-form mapping (`scripts/lifeform.py`) is hand-built; floating-leaf and "tussock" classed as floating, bladderwort as submersed, filamentous algae excluded. A floating point can co-occur with emergent and submersed plants. FWC "submerged" is submersed-only points, which are often *under* hydrilla/eelgrass canopy that may or may not reach the surface.
10. Pooled metrics weight lakes by pixel count (Apopka dominates FL). Pixels are spatially autocorrelated, so the effective sample size is far smaller than the pixel counts and no confidence intervals are given.

## 6. Reproduce

```
cd ~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments
python3 -m venv .venv && .venv/bin/pip install numpy pillow pyproj shapely rasterio requests pystac-client matplotlib scikit-learn scipy
.venv/bin/python scripts/01_fetch_fwc.py          # FWC points + lakes   -> data/
.venv/bin/python scripts/02_fetch_snoco.py        # Snohomish layers     -> data/
.venv/bin/python scripts/07_fetch_bathy.py        # FWC depth bands      -> data/
.venv/bin/python -u scripts/03_extract.py snoco   # S2 range reads + label rasters -> out/stack_snoco_*.npz (~10 min)
.venv/bin/python -u scripts/03_extract.py fwc     # ~25 min
.venv/bin/python scripts/04_metrics.py snoco ; .venv/bin/python scripts/04_metrics.py fwc ; .venv/bin/python scripts/04_metrics.py fwc --max3
.venv/bin/python scripts/09_depth.py ; .venv/bin/python scripts/08_ml_lolo.py snoco ; .venv/bin/python scripts/08_ml_lolo.py fwc
.venv/bin/python scripts/05_figures.py snoco ; .venv/bin/python scripts/05_figures.py fwc
.venv/bin/python scripts/10_tables.py             # -> out/tables.md
.venv/bin/python scripts/06_manifest.py           # appends to ../MANIFEST.jsonl
```

Outputs: `out/metrics_{snoco,fwc,fwc_max3,depth}.json`, `out/ml_lolo_*.json`, `out/tables.md`, figures `out/figures/*.png` (per-lake maps for all 12 lakes, `auc_*` bar charts). Network volume: about 1 GB of compressed windowed COG reads (cache `out/s2cache` 1.0 GB, `data/` 30 MB), well under the 3 GB cap.

## 7. What to do next

1. Get a real submerged ground truth: the FWC sonar BioVolume ImageServers (2015-2023) are already served and dated; test S2 against them, stratified by depth and a clarity proxy.
2. Add a dark-water guard and a cell-level vote to the 0.30 rule, then re-score at cell level (what Sector ships), and test a persistence composite instead of max.
3. Add a turbid Midwest/Southern reservoir (UMESC LTRM or TVA Guntersville) for clarity transfer; add Secchi from state monitoring.
4. For bowfishing, model submerged vegetation as a probability from depth, clarity, season, lake history and shoreline context, and use S2 only for the surface-canopy layer where it is demonstrably strong.
