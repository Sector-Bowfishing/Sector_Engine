# 08. Seasonal back-test of the Vegetation Brain (observer A, accepted-pass belt share, 2017-2025)

Offline research. No git repo touched. All code, caches and outputs live in `~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/seasonal/` (scripts `scripts/s1..s7`, per-scene tables `out/scenes_*.jsonl`, analysis `out/analysis.json`, `out/summary.json`, figures `figs/`). New files are logged (bytes, sha256) in `../MANIFEST.jsonl`. Pre-registration used: `VEGETATION_VALIDATION_PREREGISTRATION.md` s1 (observer A) and s7 (seasonal gate), frozen, unchanged.

## 0. Read this first

1. **Download budget was exceeded; this is a protocol violation, not a rounding issue.** The brief said keep downloads under 3 GB. I estimated the cost from the size of my own compressed cache (about 0.7 MB per scene) and did not measure real network transfer until late. Sentinel-2 COGs on Earth Search have 1024 x 1024 internal tiles, so a 5 km window forces whole tiles to be fetched: a probe of one Leech Lake scene (HTTP Content-Range accounting) fetched about 4.7 MB (B04) + 1.5 MB (B8A) + 1.4 MB (B11) + 0.08 MB (SCL), roughly 7.6 MB per scene, about 10 times my estimate. Across 2,556 scene reads plus 5,499 SCL-only probes the total transfer was about 17 GB (en0 byte counter rose 17.4 GB over the run; the per-scene probe gives a similar order). That is roughly 5-6 times the budget. I stopped the fetch queue the moment I measured this. The four lakes not yet fetched (Sam Rayburn TX, Chippewa Flowage WI, Milford KS, Clear Lake CA) were **not run**, and partial caches for two of them were deleted. Nothing was deleted from other people's data. Anyone repeating this must read overview levels or 20 m bands only, or use a tiled-by-window service, or cap on measured bytes (`GDAL` `/vsicurl` stats) rather than on cache size.
2. **Scope achieved: 8 lakes, 5 of the requested lake classes.** Southeast reservoirs (Guntersville AL, Hartwell SC/GA), Florida (Istokpoga, Orange Lake), Pacific NW (Fern Ridge OR, Lake Sammamish WA), upper-Midwest river pool (Lake Pepin MN/WI), northern ice-affected (Leech Lake MN). **Not covered: Texas reservoir, Plains reservoir, Southwest/California, a second northern lake.** Those classes are `NOT_TESTABLE` here for lack of data collection, not for lack of signal. The Snohomish Co lakes used in notes 04/05 are not in the 621-lake fleet registry, so Fern Ridge and Sammamish stand in for the PNW.
3. **Headline.** With 6 lakes that had a measurable surface signal (747 evaluated scenes) the lake-specific climatology agreed exactly with the observed state class in **0.562** of scenes (95 % CI over lakes 0.47-0.66) vs **0.175** for the generic calendar rule (difference +30 to +48 points); within-one agreement 0.892 (CI 0.83-0.95). Per lake the prereg s7 gate gives 4 PASS (Guntersville, Orange Lake, Fern Ridge, Lake Pepin), 2 FAIL (Istokpoga, Sammamish; both on within-one), 2 NOT_TESTABLE (Hartwell and Leech Lake have essentially no surface-vegetation signal, belt share about 0.3 % and 1 %).
4. **Do not read the PASSes as a licence to publish seasonal states.** Three reasons, all in the data. (a) The calendar baseline is nearly worthless almost everywhere (exact agreement 0.01-0.30 except Guntersville 0.49), so beating it by 10 points is a low bar. A trivial "always predict the lake's most common state" rule scores 0.50 pooled and beats the climatology outright at Istokpoga (0.71 vs 0.53) and Sammamish (0.53 vs 0.39). (b) Persistence of the last accepted observation beats the climatology when the last pass is under about a month old (pooled exact 0.667 vs 0.571 on the common set) and loses only beyond about 60 days. The seasonal prior is a fallback for stale observations, not a replacement for them. (c) Several lakes peak in autumn or winter, not July-August, and the signal is confounded with pool level (section 6).
5. **Observability is the bigger finding.** Only 30-52 % of clear-enough scenes are accepted by observer A's read-coverage rule, so after cloud, refusal and ice a lake gets at most 0-8 accepted passes in a given month (mean per year) and **none** in several winter months. The 90th-percentile age of the newest accepted pass exceeds 30 days in 59 of 96 lake-months and the median age exceeds 30 days in 17 (section 5); the 90th percentile exceeds 100 days in Feb at Fern Ridge, Sammamish, Pepin and Leech Lake (and in Jan at Fern Ridge and Sammamish). A seasonal fallback is needed in those lake-months; for Florida and the Southeast outside summer it is rarely needed (median age 5-18 days).

## 1. Lakes and windows

Canonical analysis polygons from `https://storage.googleapis.com/sector-lake-registry/lakes/{lakeKey}/geometry.v1.analysis.geojson.gz` (`geom/`). Registry polygons are large (Guntersville 71 x 83 km), so for each lake I analysed **one fixed window of at most 5 x 5 km** (+250 m read pad), chosen by script `s1_windows.py` as the window with the **longest shoreline** that still has at least 25 % water. Selection used geometry only, never vegetation imagery, but it is a geometric choice and it means: window results are not whole-lake results; windows with long shoreline over-represent belt and shore effects; "whole-lake plant-cell share" below means share of the window's analysis cells (>= 35 m from shore).

| Lake | key | class | window lon/lat (W,S,E,N) | water share of window |
|---|---|---|---|---|
| Guntersville AL | Guntersville_AL | SE reservoir | -85.9398, 34.7464, -85.8852, 34.7916 | 0.28 |
| Hartwell SC/GA | Lake_Hartwell_SC | SE reservoir | -82.8790, 34.4280, -82.8245, 34.4732 | 0.70 |
| Istokpoga FL | Istokpoga_FL | Florida | -81.3145, 27.3251, -81.2639, 27.3703 | 0.76 |
| Orange Lake FL | Orange_Lake_FL | Florida | -82.1894, 29.4187, -82.1378, 29.4639 | 0.45 |
| Fern Ridge OR | Fern_Ridge_Reservoir_OR | Pacific NW | -123.3182, 44.0509, -123.2557, 44.0961 | 0.56 |
| Sammamish WA | Lake_Sammamish_WA | Pacific NW | -122.1119, 47.5553, -122.0551, 47.6005 | 0.44 |
| Lake Pepin MN/WI | Lake_Pepin_MN | river pool | -92.4797, 44.5367, -92.4168, 44.5819 | 0.36 |
| Leech Lake MN | Leech_Lake_MN | northern, ice | -94.5666, 47.0842, -94.5005, 47.1294 | 0.51 |

Planned but not run (see section 0): Sam Rayburn TX, Chippewa Flowage WI, Milford Lake KS, Clear Lake CA (windows already in `out/windows.json`).

## 2. Methods

**Scenes.** Earth Search STAC, 2017-01-01 to 2025-12-31, tile `eo:cloud_cover < 85`. `sentinel-2-c1-l2a` preferred (reflectance = DN x 1e-4 - 0.1); `sentinel-2-l2a` fills dates c1 lacks (all 2022, 2017). `sentinel-2-l2a` is offset-free (the lesson in the brief was re-verified: same tile and day: B04 DN 5th/50th percentile 1194/1300 in c1 vs 194/300 in l2a, so only c1 needs the -0.1). A paired check of 16 same-tile same-date c1/l2a scenes (`s2b_pair.py`) found identical SCL in all 16 and reflectance identical in about half; the rest differ in a few pixels (max B04 difference 0.055, B11 0.004), so the collections are interchangeable **when the processing baseline matches**. Older baselines (00.01, 02.x, 03.01; present only in l2a-only dates, mainly 2017) accept less often at some lakes (table in section 8); a "modern baselines only" sensitivity is reported. Same-date items from adjacent tiles are mosaicked.

**Two-stage reads.** Stage 1 reads only SCL for every STAC date (5,499 date-probes) and computes cloud/shadow/snow/no-data shares over the lake pixels in the window. Stage 2 reads B04 (10 m), B8A and B11 (20 m, nearest to 10 m) only for dates whose SCL clear share is at least 25 % (cell-level acceptance needs at least that, so this prefilter loses almost nothing). Because of the budget, stage 2 was further **subsampled** per lake: if the candidate list exceeded about 210 MB of estimated cache, I kept the max-clear date in each N-day bin (N = 4 to 10, per lake, recorded as `bin d` in the table below). Skipped dates are labelled `SKIPPED_SUBSAMPLE`. Per-month usable rates and gap statistics impute them as accepted with the lake-month's observed acceptance rate (20 Monte-Carlo draws); the raw accepted-only gap statistics are also in `out/analysis.json` (`age_raw`).

**Observer A (prereg s1).** `cell_lib.native_fields` (verbatim port of `derive_water_surface.py` constants: plant pixel NDVI(B8A,B4) >= 0.30 on SCL-clear pixels, cloud/haze/structure/bank standoffs) -> 50 m Web-Mercator cells by mean. A cell is a plant cell if the mean plant fraction of its seen pixels >= 0.5, at least 50 % of its footprint was seen, and no turbidity reading exists in the cell (production `grass_vote` guard). Dark-water pixels (red and B8A both < 0.01) are excluded from "seen". `SHORE_ADJACENT` = cell centre within 35 m of the true polygon edge (excluded; a 50 m cell with a centre closer than 25 m contains land). **Belt** = cells 35-90 m from shore; **whole-lake** share = all cells >= 35 m from shore. Glare (wind-flag) guard was not applied (no wind data in this run). Window-edge truncation of cloud standoffs (pad 250 m, not Sector's 1 km) is a documented deviation from production.

**Pass acceptance.** Scene "reads" at least 50 % of the non-plant clarity-mask water (cells with a turbidity reading) -> `ACCEPTED`; 25-50 % -> `FALLBACK` (not used in the series); below 25 % -> `REFUSED`. Statuses `NODATA` (SCL no-data >= 50 %), `ICE` (SCL snow/ice >= 30 %), `CLOUD` (SCL clear < 25 %) come from stage 1. A scene gives a belt value if at least 20 belt cells were seen, a whole-lake value if at least 100 cells were seen.

**Climatology (lake-specific).** 16-day DOY bins; per-bin per-year median; median across training years (at least 2 years with data in a bin; gaps filled by circular interpolation); 3-bin circular smoothing. A year is a *testable year* if it has at least 6 accepted scenes. Leave-one-year-out (LOYO): the held-out year never contributes to the curve or to the range used to normalise it.

**States (from the lake's OWN cycle).** u = (value - min) / (max - min) of the training climatology, clipped to [0,1]. DORMANT u < 0.2; PEAK u >= 0.8; between: EMERGING (rising, u < 0.5), GROWING (rising, u >= 0.5), DECLINING (falling). Direction for the *predicted* state comes from the curve (rising between its trough and peak, falling otherwise). Direction for the *observed* state comes from the held-out year's own neighbouring accepted scenes within +-40 days (later mean minus earlier mean, flat if under 10 % of lake amplitude); scenes whose mid-level state has no determinable direction are dropped from the 5-state test (DORMANT and PEAK need no direction). Cyclic order DORMANT-EMERGING-GROWING-PEAK-DECLINING; "within-one" = cyclic distance <= 1. All thresholds were fixed before the first result was inspected, except the no-signal rule below.

**Baselines.** (a) generic calendar: Dec-Feb DORMANT, Mar-Apr EMERGING, May-Jun GROWING, Jul-Aug PEAK, Sep-Nov DECLINING. (b) persistence: the state of the previous accepted scene, computed causally (direction from earlier scenes only), same normalisation. (c) added sanity baseline: lake's most frequent observed state (in-sample, so generous). **GDD proxy:** daily mean air temperature from the Open-Meteo archive at the window centre (`out/airtemp_*.json`), cumulative degree-days above 10 C from Jan 1; the proxy warps each year's DOY by that year's day of reaching 100 degree-days relative to the training median. It is air temperature, labelled as a proxy only; Water Temp Brain will own temperature.

**Gate (prereg s7, applied literally per lake):** at least 4 testable years, exact agreement >= calendar + 10 points **and** within-one >= 0.85 -> PASS else FAIL. I added one rule that is **not in the prereg**: a lake whose climatology maximum belt share is under 5 % is `NOT_TESTABLE` (no measurable surface signal; with about 1,000 belt cells one cell is 0.1 % and the normalised "state" is noise). Hartwell (max 4.9 %) is borderline; Leech Lake (2.5 %) is clearly below. Class verdicts pool the testable lakes of a class; bootstrap = 2,000 resamples of lakes (not scenes).

## 3. Scene accounting

| Lake | STAC dates | read (clear>=25%) | accepted of read | fallback | refused | cloud (<25% clear) | ice/snow | no data | not read (subsample) | bin d |
|---|---|---|---|---|---|---|---|---|---|---|
| Guntersville AL | 910 | 301 | 125 (42%) | 73 (24%) | 103 (34%) | 191 (21% of dates) | 3 | 64 | 351 | 10 |
| Hartwell SC/GA | 458 | 322 | 165 (51%) | 34 (11%) | 123 (38%) | 94 (21% of dates) | 1 | 1 | 40 | 6 |
| Istokpoga FL | 525 | 315 | 111 (35%) | 39 (12%) | 165 (52%) | 99 (19% of dates) | 0 | 0 | 111 | 8 |
| Orange Lake FL | 488 | 297 | 155 (52%) | 30 (10%) | 112 (38%) | 93 (19% of dates) | 0 | 0 | 98 | 8 |
| Fern Ridge OR | 837 | 313 | 141 (45%) | 33 (11%) | 139 (44%) | 233 (28% of dates) | 5 | 0 | 286 | 8 |
| Sammamish WA | 776 | 361 | 174 (48%) | 44 (12%) | 143 (40%) | 285 (37% of dates) | 7 | 1 | 122 | 5 |
| Lake Pepin MN/WI | 769 | 307 | 92 (30%) | 56 (18%) | 159 (52%) | 213 (28% of dates) | 91 | 20 | 138 | 6 |
| Leech Lake MN | 736 | 313 | 133 (42%) | 25 (8%) | 155 (50%) | 213 (29% of dates) | 142 | 1 | 67 | 4 |

`STAC dates` = distinct dates with tile cloud < 85 in the window; Pepin and Leech show the ice effect (91 and 142 `ICE` dates). `Accepted of read` is the share of stage-2 scenes that pass observer A's coverage rule: **30-52 %**, i.e. roughly half of cloud-free scenes are refused or only fall back. Refusal is driven by the read gates (SWIR <= 0.0215, FAI <= 0.005, NDVI <= 0.10 on water, haze/cloud-edge standoffs), so it reflects how often production Clarity-style reading works, not only weather.

## 4. Observability by month

Each cell: **usable-scene rate** (accepted passes as a share of all STAC dates that month, with unread dates imputed) / **expected accepted passes per year** in that month. Example: "48% / 1.9" in Jan means about 1.9 accepted passes per January.

| Month | Guntersville AL | Hartwell SC/GA | Istokpoga FL | Orange Lake FL | Fern Ridge OR | Sammamish WA | Lake Pepin MN/WI | Leech Lake MN |
|---|---|---|---|---|---|---|---|---|
| 1 | 41% / 2.9 | 33% / 1.1 | 55% / 1.9 | 58% / 1.7 | 0% / 0.0 | 11% / 0.6 | 0% / 0.0 | 0% / 0.0 |
| 2 | 41% / 2.4 | 45% / 1.4 | 28% / 1.4 | 56% / 2.4 | 2% / 0.1 | 16% / 0.7 | 0% / 0.0 | 0% / 0.0 |
| 3 | 14% / 1.1 | 59% / 2.3 | 33% / 1.6 | 43% / 2.0 | 26% / 1.7 | 24% / 1.6 | 9% / 0.7 | 7% / 0.4 |
| 4 | 36% / 2.8 | 42% / 1.7 | 10% / 0.4 | 35% / 1.5 | 41% / 2.8 | 25% / 1.8 | 29% / 1.7 | 20% / 1.1 |
| 5 | 8% / 0.7 | 14% / 0.6 | 10% / 0.5 | 35% / 1.8 | 27% / 2.1 | 22% / 1.7 | 18% / 1.3 | 27% / 2.0 |
| 6 | 13% / 1.2 | 10% / 0.4 | 0% / 0.0 | 26% / 1.2 | 39% / 3.6 | 24% / 2.2 | 6% / 0.4 | 11% / 0.8 |
| 7 | 11% / 1.1 | 20% / 1.1 | 9% / 0.5 | 19% / 0.9 | 58% / 6.2 | 53% / 5.2 | 22% / 2.1 | 22% / 2.2 |
| 8 | 29% / 3.0 | 31% / 1.4 | 19% / 1.0 | 22% / 1.1 | 72% / 7.7 | 48% / 4.6 | 16% / 1.3 | 41% / 3.6 |
| 9 | 51% / 4.5 | 57% / 2.7 | 40% / 2.2 | 45% / 2.2 | 64% / 5.8 | 51% / 4.1 | 37% / 3.2 | 48% / 3.3 |
| 10 | 52% / 4.8 | 56% / 2.9 | 28% / 1.5 | 52% / 2.7 | 45% / 3.8 | 32% / 2.2 | 28% / 2.2 | 41% / 3.0 |
| 11 | 35% / 3.2 | 69% / 3.1 | 59% / 3.1 | 66% / 2.8 | 0% / 0.0 | 28% / 1.7 | 31% / 1.7 | 32% / 1.6 |
| 12 | 34% / 2.7 | 54% / 1.9 | 52% / 2.4 | 61% / 2.7 | 0% / 0.0 | 5% / 0.2 | 12% / 0.6 | 0% / 0.0 |

Reading it: Southeast/Florida lakes are observable year-round (1-3 passes a month in dry season) but nearly blind in early summer for Guntersville (1.1-1.2 accepted passes in Jun-Jul) and Istokpoga (0-1.0 in Jun-Aug; zero accepted passes in June in nine years) because of summer cloud and haze/read refusals. Pacific NW lakes are the opposite: 4-8 accepted passes a month in Jul-Sep, **none** in Jan-Feb at Fern Ridge (0.0-0.1) and 0.6-0.7 at Sammamish. Pepin and Leech have no accepted passes in Jan-Feb (ice then cloud), 0-0.6 in December and 0.4-1.7 in Mar-Apr (ice-out); the main window is May-Oct.

## 5. Cloud-gap behaviour (observation age)

On every calendar day from the first accepted pass to 2025-12-31 I computed the age of the newest accepted pass. Cells below are **median / 90th percentile age in days / share of days with age > 30 d**, by month, pooled over years (skipped dates imputed). Figure: `figs/observation_age_p90.png`; per-lake bar panel in each `figs/lake_*.png`.

| Month | Guntersville AL | Hartwell SC/GA | Istokpoga FL | Orange Lake FL | Fern Ridge OR | Sammamish WA | Lake Pepin MN/WI | Leech Lake MN |
|---|---|---|---|---|---|---|---|---|
| 1 | 7 / 32 / 12% | 14 / 28 / 6% | 7 / 24 / 5% | 9 / 25 / 4% | 90 / 107 / 100% | 44 / 104 / 72% | 50 / 80 / 92% | 68 / 86 / 100% |
| 2 | 7 / 27 / 5% | 18 / 45 / 34% | 12 / 30 / 10% | 6 / 22 / 3% | 119 / 136 / 97% | 34 / 134 / 52% | 79 / 109 / 100% | 97 / 115 / 100% |
| 3 | 13 / 40 / 14% | 7 / 22 / 5% | 11 / 37 / 16% | 7 / 24 / 5% | 16 / 156 / 40% | 13 / 163 / 18% | 102 / 136 / 72% | 126 / 145 / 89% |
| 4 | 7 / 48 / 16% | 10 / 29 / 8% | 24 / 45 / 34% | 10 / 27 / 7% | 6 / 58 / 15% | 15 / 47 / 25% | 11 / 138 / 21% | 150 / 172 / 71% |
| 5 | 18 / 42 / 22% | 23 / 48 / 34% | 45 / 72 / 68% | 10 / 26 / 4% | 8 / 26 / 6% | 11 / 30 / 9% | 15 / 123 / 25% | 7 / 181 / 15% |
| 6 | 17 / 51 / 28% | 37 / 73 / 57% | 65 / 101 / 81% | 13 / 37 / 20% | 6 / 30 / 10% | 10 / 23 / 2% | 26 / 52 / 41% | 14 / 30 / 10% |
| 7 | 18 / 54 / 28% | 19 / 74 / 31% | 76 / 127 / 80% | 26 / 59 / 44% | 2 / 9 / 0% | 3 / 13 / 1% | 14 / 65 / 34% | 8 / 44 / 21% |
| 8 | 7 / 32 / 10% | 19 / 49 / 29% | 21 / 123 / 42% | 19 / 63 / 31% | 2 / 6 / 0% | 3 / 12 / 0% | 15 / 41 / 21% | 6 / 23 / 4% |
| 9 | 3 / 14 / 2% | 6 / 20 / 3% | 9 / 34 / 13% | 9 / 50 / 19% | 2 / 10 / 0% | 4 / 15 / 1% | 6 / 49 / 15% | 5 / 23 / 2% |
| 10 | 4 / 13 / 0% | 5 / 29 / 10% | 13 / 43 / 17% | 6 / 18 / 1% | 4 / 16 / 0% | 8 / 22 / 3% | 8 / 20 / 2% | 6 / 31 / 10% |
| 11 | 5 / 20 / 2% | 4 / 17 / 1% | 5 / 38 / 12% | 5 / 19 / 0% | 28 / 45 / 42% | 20 / 49 / 31% | 13 / 32 / 13% | 12 / 28 / 7% |
| 12 | 6 / 22 / 3% | 8 / 19 / 0% | 6 / 15 / 0% | 5 / 19 / 9% | 58 / 75 / 100% | 22 / 70 / 30% | 20 / 46 / 26% | 35 / 54 / 61% |

Inter-pass gaps (accepted to accepted, raw, no imputation): median 10 d (Fern Ridge, Sammamish, Leech) to 20 d (Pepin); 90th percentile 34-85 d; maximum 100-260 d (`gap_all` in `out/analysis.json`). In Jan-Feb at Fern Ridge, Pepin and Leech the median age is 50-120 days. **Implication:** observation age for the Brain is routinely above the 21-day reference window of prereg s1 in these lake-months, so some fallback (climatology, labelled as such, or UNKNOWN) is needed there; elsewhere the last observation is usually fresh enough.

## 6. Seasonal back-test results

### 6.1 Gate verdicts per lake

| Lake | Class | n eval | years | clim exact | calendar exact | delta pts | clim within-1 | persistence exact (common n) | verdict |
|---|---|---|---|---|---|---|---|---|---|
| Guntersville AL | SE reservoir | 120 | 9 | 0.77 | 0.49 | +28 | 0.97 | 0.81 (109) | **PASS** |
| Hartwell SC/GA | SE reservoir | 163 | 9 | 0.67 | 0.15 | +52 | 0.88 | 0.69 (159) | **NOT_TESTABLE** |
| Istokpoga FL | Florida | 111 | 9 | 0.53 | 0.21 | +32 | 0.79 | 0.72 (107) | **FAIL** |
| Orange Lake FL | Florida | 143 | 9 | 0.56 | 0.08 | +48 | 0.85 | 0.70 (128) | **PASS** |
| Fern Ridge OR | Pacific NW | 140 | 9 | 0.59 | 0.01 | +58 | 0.96 | 0.76 (113) | **PASS** |
| Sammamish WA | Pacific NW | 153 | 9 | 0.39 | 0.08 | +31 | 0.82 | 0.39 (143) | **FAIL** |
| Lake Pepin MN/WI | Upper Midwest/river pool | 80 | 9 | 0.59 | 0.30 | +29 | 1.00 | 0.72 (69) | **PASS** |
| Leech Lake MN | Northern ice-affected | 122 | 9 | 0.51 | 0.11 | +40 | 0.84 | 0.46 (110) | **NOT_TESTABLE** |

| Lake | verdict | detail |
|---|---|---|
| Guntersville AL | **PASS** | exact 0.77 vs calendar 0.49 (+28 pts; need >= +10), within-one 0.97 (need >= 0.85) |
| Hartwell SC/GA | **NOT_TESTABLE** | no measurable surface signal (climatology max belt share 0.049 < 0.05) |
| Istokpoga FL | **FAIL** | exact 0.53 vs calendar 0.21 (+32 pts; need >= +10), within-one 0.79 (need >= 0.85) |
| Orange Lake FL | **PASS** | exact 0.56 vs calendar 0.08 (+48 pts; need >= +10), within-one 0.85 (need >= 0.85) |
| Fern Ridge OR | **PASS** | exact 0.59 vs calendar 0.01 (+58 pts; need >= +10), within-one 0.96 (need >= 0.85) |
| Sammamish WA | **FAIL** | exact 0.39 vs calendar 0.08 (+31 pts; need >= +10), within-one 0.82 (need >= 0.85) |
| Lake Pepin MN/WI | **PASS** | exact 0.59 vs calendar 0.30 (+29 pts; need >= +10), within-one 1.00 (need >= 0.85) |
| Leech Lake MN | **NOT_TESTABLE** | no measurable surface signal (climatology max belt share 0.025 < 0.05) |

Orange Lake's within-one is exactly at the 0.85 line (0.853 unrounded), so that PASS is marginal.

### 6.2 By lake class and pooled

| Lake class | lakes (testable) | pooled clim exact | pooled calendar exact | pooled clim within-1 | bootstrap over lakes (delta pts) | class verdict |
|---|---|---|---|---|---|---|
| Florida | Istokpoga FL, Orange Lake FL (Istokpoga FL, Orange Lake FL) | 0.55 | 0.13 | 0.83 | [+32, +48] | **FAIL** (lakes passing: 1/2) |
| Northern ice-affected | Leech Lake MN (none) | - | - | - | - | **NOT_TESTABLE** (all member lakes no signal) |
| Pacific NW | Fern Ridge OR, Sammamish WA (Fern Ridge OR, Sammamish WA) | 0.48 | 0.05 | 0.88 | [+31, +58] | **PASS** (lakes passing: 1/2) |
| SE reservoir | Guntersville AL, Hartwell SC/GA (Guntersville AL) | 0.77 | 0.49 | 0.97 | n/a (1 lake) | **PASS** (lakes passing: 1/1) |
| Upper Midwest/river pool | Lake Pepin MN/WI (Lake Pepin MN/WI) | 0.59 | 0.30 | 1.00 | n/a (1 lake) | **PASS** (lakes passing: 1/1) |

Pooled and sensitivity variants (bootstrap over lakes, 2,000 resamples):

| Variant | lakes | n scenes | clim exact [95 % CI over lakes] | calendar exact [CI] | delta pts [CI] | clim within-1 [CI] |
|---|---|---|---|---|---|---|
| PRIMARY: belt share, DOY climatology, 6 testable lakes | 6 | 747 | 0.562 [0.47-0.66] | 0.175 [0.07-0.32] | +38.7 [+30 to +48] | 0.892 [0.83-0.95] |
| all 8 lakes incl. 2 no-signal lakes | 8 | 1032 | 0.573 [0.49-0.65] | 0.163 [0.08-0.27] | +41.0 [+33 to +48] | 0.884 [0.84-0.93] |
| whole-lake plant-cell share instead of belt | 6 | 684 | 0.577 [0.50-0.67] | 0.212 [0.09-0.36] | +36.5 [+28 to +47] | 0.880 [0.80-0.95] |
| GDD-proxy thermal-time warp (Open-Meteo air temp) | 6 | 740 | 0.535 [0.46-0.61] | 0.178 [0.07-0.32] | +35.7 [+27 to +44] | 0.881 [0.82-0.94] |
| excluding scenes from legacy processing baselines (<04.00) | 6 | 602 | 0.563 [0.47-0.65] | 0.154 [0.06-0.30] | +40.9 [+32 to +50] | 0.890 [0.84-0.95] |

Reading the variants: swapping belt for whole-lake share, removing legacy baselines, or adding the GDD warp changes pooled exact agreement by at most 0.03, and the GDD proxy does **not** help (0.535 vs 0.562): year-to-year timing in these lakes is not explained by degree-days above 10 C of air temperature; interannual amplitude shifts (Orange Lake, Guntersville 2019-21 vs 2023-25) and pool-level changes are the more likely drivers (not tested).

### 6.3 Climatology vs persistence vs trivial baseline

On the scenes where persistence is defined (common set, 669 scenes, 6 testable lakes): persistence 0.667, lake climatology 0.571, calendar 0.167 exact. By age of the last accepted observation:

| Age of last accepted observation | n scenes | persistence exact | lake climatology exact | calendar exact | persistence within-1 | climatology within-1 |
|---|---|---|---|---|---|---|
| <=14d | 321 | 0.71 | 0.56 | 0.17 | 0.88 | 0.88 |
| 15-30d | 223 | 0.69 | 0.57 | 0.16 | 0.86 | 0.88 |
| 31-60d | 75 | 0.57 | 0.56 | 0.19 | 0.79 | 0.92 |
| >60d | 50 | 0.44 | 0.66 | 0.16 | 0.70 | 0.96 |

Persistence wins when the last pass is fresh and loses beyond about 60 days (0.44 vs 0.66), the crossover is around 31-60 days. Within-one agreement of the climatology stays 0.88-0.96 at all ages. The 'age > 60 d' bin has only 50 scenes pooled, so the crossover is indicative, not established.

Trivial majority-state baseline (in-sample, generous to the baseline):

| Lake | most frequent observed state (share) | lake climatology exact |
|---|---|---|
| Guntersville AL | DORMANT (0.44) | 0.77 |
| Hartwell SC/GA | DORMANT (0.71) | 0.67 |
| Istokpoga FL | DORMANT (0.71) | 0.53 |
| Orange Lake FL | PEAK (0.41) | 0.56 |
| Fern Ridge OR | DORMANT (0.46) | 0.59 |
| Sammamish WA | DORMANT (0.53) | 0.39 |
| Lake Pepin MN/WI | DORMANT (0.42) | 0.59 |
| Leech Lake MN | DORMANT (0.39) | 0.51 |

Pooled majority-state exact agreement over the 6 testable lakes is 0.50 against 0.562 for the climatology. Because DORMANT dominates observed labels in low-share lakes (Istokpoga 71 %, Sammamish 53 %), the exact-agreement gap to a trivial guess is small there, and the prereg s7 gate (which compares only to the calendar rule) does not catch this. I recommend adding a "majority-state" or "persistence at age <= 14 d" comparator to any amendment; I did not change the gate.

Figures: `figs/agreement_by_lake.png` (exact agreement, three predictors per lake); `figs/climatologies_overlay.png`.

## 7. Peak timing vs the research note 03 expert table, bimodality, winter appearance

| Lake (class) | Note-03 expert row | expert D window | lake climatology peak (full data) | per-year peak median [IQR], n years | inside expert window (clim / share of years) | signal? |
|---|---|---|---|---|---|---|
| Guntersville AL (SE reservoir) | Southeast reservoir (D Jul-Sep) | Jul 01-Sep 30 | Sep 05 (u>=0.8 window Jul 28-Oct 31) | Sep 07 [Sep 01-Oct 01], 7 | yes / 0.71 | yes |
| Hartwell SC/GA (SE reservoir) | Southeast reservoir (D Jul-Sep) | Jul 01-Sep 30 | Nov 08 (u>=0.8 window Nov 01-Dec 02) | Oct 28 [Oct 13-Nov 03], 8 | no / 0.25 | NO (<5 % belt share) |
| Istokpoga FL (Florida) | Deep South / Gulf (D Jun-Sep) | Jun 01-Sep 30 | Dec 10 (u>=0.8 window Nov 17-Dec 18) | Nov 29 [Oct 27-Nov 29], 3 | no / 0.33 | yes |
| Orange Lake FL (Florida) | Deep South / Gulf (D Jun-Sep) | Jun 01-Sep 30 | Jan 24 (u>=0.8 window Jan 01-Dec 31) | Nov 24 [Nov 19-Nov 28], 8 | no / 0.00 | yes |
| Fern Ridge OR (Pacific NW) | Pacific NW (D Jul-Aug) | Jul 01-Aug 31 | Nov 08 (u>=0.8 window Sep 30-Dec 02) | Oct 09 [Oct 07-Oct 18], 9 | no / 0.00 | yes |
| Sammamish WA (Pacific NW) | Pacific NW (D Jul-Aug) | Jul 01-Aug 31 | Oct 07 (u>=0.8 window Sep 14-Oct 31) | Sep 30 [Sep 07-Oct 02], 9 | no / 0.11 | yes |
| Lake Pepin MN/WI (Upper Midwest/river pool) | Midwest (M-D May CLP; M-D Aug) | May 01-May 31; Aug 01-Aug 31 | Sep 05 (u>=0.8 window Jul 28-Sep 13) | Sep 03 [Aug 06-Sep 10], 7 | no / 0.14 | yes |
| Leech Lake MN (Northern ice-affected) | Great Lakes/upper Midwest (D Aug, M-D Jul) | Jul 01-Aug 31 | Oct 23 (u>=0.8 window Sep 30-Dec 18) | Oct 19 [Sep 19-Nov 04], 8 | no / 0.00 | NO (<5 % belt share) |

* **Expert July-August "peak" is not supported as a rule.** For the 6 lakes with a signal, the per-year belt-share maximum falls in September-October (Guntersville Sep 7 median, Lake Pepin Sep 3, Sammamish Sep 30, Fern Ridge Oct 9) or November-December (Istokpoga Nov 29, Orange Lake Nov 24), and the share of individual years whose peak lies inside the note-03 window is 0.0-0.71 (Guntersville 0.71 is the only lake where the expert window fits; its D window is Jul-Sep, which includes the observed peak). Per-year peaks use only years with at least 8 accepted Apr-Nov scenes (Istokpoga: 3 years only, so thin). Offsets from the expert window centre: Guntersville +21 d, Pepin +20 d (vs Aug), Sammamish +68 d, Fern Ridge +100 d, Istokpoga +132 d, Orange Lake -188 d (i.e. winter).
* **Why, and what is NOT proven.** Candidate explanations: late-season mat accumulation (supports a real autumn peak), shoreline vegetation and tree-canopy phenology inside the belt, and **pool-level change**. Fern Ridge is a flood-control reservoir drawn down in autumn (peak belt share Oct-Nov, a pattern that matches exposed vegetated flats entering the fixed polygon rather than a plant peak); Orange Lake and Istokpoga peak in the dry season (Nov-Jan) when exposed shoreline and wet marsh both read as plant. No lake-level time series was joined, so none of this is tested. The expert table cannot be falsified or confirmed for biomass from these data; what is supported is that **observer A's belt share peak falls outside the note-03 expert window at 5 of 6 lakes (all but Guntersville), later at four of them and in the dry season at the two Florida lakes**. Guntersville (TVA reservoir, winter drawdown) is the best-behaved: one peak, ~Sep 7, quiet winter.
* **Bimodality.** The smoothed climatology has exactly one local maximum with prominence >= 25 % of its amplitude at all 8 lakes. There is **no evidence of bimodal belt share**, including at Lake Pepin where the Midwest row of note 03 predicts a curlyleaf May peak. With 6-12 accepted passes per lake-year and 16-day bins, an early curlyleaf pulse of two to three weeks would be easy to miss; this is a thin-data negative, not a refutation.
* **Dormant-winter appearance.** Winter (Dec-Feb) belt share relative to the climatology maximum: Guntersville 0.02 (clean dormancy, n = 39 winter scenes), Hartwell 0.07 (no signal), Istokpoga 0.31 (n = 40), **Orange Lake 0.94 (n = 48; belt stays at 85-100 % in winter: evergreen emergent/floating marsh vegetation and exposed marsh, so DORMANT is never observed there)**, Fern Ridge 0.45 (n = 1), Sammamish 0.35 (n = 6), Pepin 0.15 (n = 4). Fern Ridge, Sammamish and Pepin have too few winter passes to say anything (observability, section 4). Emergent stands that are physically present but low-NDVI in winter cannot be told apart from open water by NDVI >= 0.30; the tan-stem effect in the brief's note 03 is untestable here (no emergent ground truth).

| Lake | accepted scenes | belt share median [p10-p90] | clim min-max | Dec-Feb accepted n | winter median / clim max | local maxima (prominence >= 25 % amp) | accept rate legacy baseline (<04.00) vs modern |
|---|---|---|---|---|---|---|---|
| Guntersville AL | 125 | 32.7% [0.3-92.7] | 0.7-85.5% | 39 | 0.02 | 1 | 56% (n=50) vs 39% (n=251) |
| Hartwell SC/GA | 165 | 0.3% [0.1-5.8] | 0.1-4.9% | 36 | 0.07 | 1 | 53% (n=47) vs 51% (n=275) |
| Istokpoga FL | 111 | 6.9% [3.3-64.9] | 4.3-26.5% | 40 | 0.31 | 1 | 48% (n=54) vs 33% (n=261) |
| Orange Lake FL | 155 | 63.6% [17.4-99.3] | 28.9-94.4% | 48 | 0.94 | 1 | 47% (n=51) vs 53% (n=246) |
| Fern Ridge OR | 141 | 10.1% [1.3-25.8] | 2.3-34.1% | 1 | 0.45 | 1 | 32% (n=57) vs 48% (n=256) |
| Sammamish WA | 174 | 18.6% [1.7-66.2] | 8.9-56.4% | 6 | 0.35 | 1 | 36% (n=66) vs 51% (n=295) |
| Lake Pepin MN/WI | 92 | 21.4% [1.2-62.2] | 0.6-46.9% | 4 | 0.15 | 1 | 42% (n=43) vs 28% (n=264) |
| Leech Lake MN | 133 | 0.9% [0.0-3.5] | 0.0-2.5% | 0 | - | 1 | 43% (n=35) vs 42% (n=278) |

### 7.1 Shore contamination of the belt

Mean plant share by distance from the polygon edge, accepted June-September scenes (the "35-90 m" columns are the belt):

| Lake | 35-50 m | 50-70 m | 70-90 m | 90-150 m | 150-300 m | >300 m |
|---|---|---|---|---|---|---|
| Guntersville AL | 81.9% | 75.4% | 74.2% | 68.5% | 64.6% | 29.1% |
| Hartwell SC/GA | 1.8% | 0.5% | 0.0% | 0.0% | 0.0% | 0.0% |
| Istokpoga FL | 11.5% | 4.5% | 4.2% | 2.7% | 1.0% | 0.0% |
| Orange Lake FL | 55.6% | 46.7% | 37.6% | 29.3% | 19.8% | 6.0% |
| Fern Ridge OR | 19.4% | 11.6% | 10.8% | 5.5% | 1.0% | 0.0% |
| Sammamish WA | 28.7% | 22.0% | 10.0% | 3.4% | 2.2% | 2.9% |
| Lake Pepin MN/WI | 49.8% | 42.1% | 32.9% | 26.2% | 14.2% | 7.1% |
| Leech Lake MN | 3.5% | 0.6% | 0.1% | 0.1% | 0.1% | 0.0% |

Belt share decays steeply with distance at Sammamish (29 % at 35-50 m vs about 3 % beyond 90 m), Fern Ridge, Istokpoga, Hartwell and Leech, which is the signature of shoreline vegetation or polygon mis-registration leaking into the belt (land pixels with NDVI >= 0.3 lying within the 50 m cell footprint, overhanging trees, mapped-shoreline offset), not of open-water plants. Guntersville, Orange Lake and Lake Pepin keep high shares offshore (29 %, 6 %, 7 % beyond 300 m), consistent with extensive surface vegetation. **For lakes in the first group the "belt share" seasonal cycle is partly a shoreline-greenness cycle**, and the seasonal states there (Sammamish, Fern Ridge) must not be sold as aquatic-vegetation phenology without a ring-offset sensitivity. Whole-lake share (cells >= 35 m) behaved the same in agreement terms (pooled 0.577), so changing the series does not remove this.

## 8. Processing-baseline and source effects

Acceptance rate (accepted of read) by processing baseline family appears in the right-hand column of the table above: scenes from legacy baselines (<04.00, from l2a only, mostly 2017) were accepted less often at Sammamish (36 % vs 51 %), Fern Ridge (32 % vs 48 %) and Istokpoga (48 % vs 33 %: opposite sign) and about equally elsewhere; no consistent baseline artefact, but 2017 data are thin (6-14 accepted scenes per lake). Excluding legacy baselines moved pooled exact agreement by 0.001 (0.563 vs 0.562).

## 9. Limitations (what is too thin or uncertain)

* **No ground truth.** "Observed state" is defined from the same observer that the climatology predicts; agreement tests self-consistency of the observer's own cycle, not biology. It says nothing about whether the observer is right about plants (notes 04/05 cover that: floating-leaf beds in clear water well detected, emergents/floating at Florida lakes mediocre, submerged not).
* **8 lakes, one 5 x 5 km window each, 9 years, 6-26 accepted scenes per lake-year** (Guntersville 2024 only 6, 2025 only 8 in the sampled series). 2017 data are thin everywhere (S2B only from mid-2017 and legacy baselines). Class results rest on 1-2 lakes each; the class "verdicts" are not generalisable. Classes Texas, Plains, Southwest, and a second northern lake: not collected.
* **Subsampling.** Between 40 and 351 clear-enough dates per lake were not read (bins of 4-10 d). Gap and usable-rate statistics for those lakes (Guntersville 351 skipped, Fern Ridge 286) are model-imputed and optimistic if clear scenes are autocorrelated with acceptance; `age_raw` (no imputation) is pessimistic.
* **Tile-level prefilter** (tile `eo:cloud_cover < 85`) excludes a few scenes where the lake window was clear but the tile was not; they count as unobserved.
* **Observed-direction noise.** 5-state labels depend on neighbours within +-40 d; sparse or noisy series make the observed label itself unreliable. Mid-level states (EMERGING/GROWING/DECLINING) are 10-44 % of labelled scenes depending on lake (`obs_dist` in `out/summary.json`); the gate is therefore mostly a DORMANT-vs-PEAK test.
* **Pool-level and management are confounds** (section 7); not controlled. Herbicide (Guntersville), grass carp, hurricanes (none tested), TVA/USACE drawdowns would all break a climatology.
* **No glare/wind guard**, window-edge standoff truncation, 20 m bands upsampled, polygons are NHD shoreline not water-level-aware.
* **Gate rule I added** (no-signal under 5 % climatology maximum) was set after seeing that Hartwell and Leech Lake were at 0.3 % and 1 % belt share. Without it both would "PASS" the literal gate (clim exact 0.67 vs calendar 0.15 at Hartwell; 0.51 vs 0.11 at Leech Lake) on noise-normalised labels. Treat that as a judgement call to be ratified or removed by amendment.
* Classes with PASS (SE reservoir, Pacific NW, upper-Midwest river pool) pass on 1 or 2 lakes; the Pacific NW class PASS is pooled while one of its two lakes (Sammamish) FAILs the per-lake gate.

## 10. Recommendations that follow from the data

1. Publish `seasonalState` only with an explicit `observationAgeDays` and `source: climatology-fallback`; never as an observation. Per section 6.3, prefer the last accepted observation when it is under about 30 days old, and the lake climatology beyond about 60 days.
2. A generic calendar fallback is wrong for most lakes tested (0.01-0.30 exact); if any prior is used before a lake has 4+ years of its own history, use `UNKNOWN`.
3. Do not state "July-August peak" anywhere; observer A peaks in Sep-Dec at most lakes tested.
4. Amend s7 before the next run: add a majority-state and a persistence comparator, a minimum-signal rule, a pool-level covariate or exclusion for drawdown reservoirs, and a shoreline-ring sensitivity.
5. Cost: if this back-test is repeated, read overview or 20 m bands only, or batch windows per tile, and meter bytes.

## 11. Figures

Per lake (time series + climatology + overpass fate + observation age): `figs/lake_Guntersville_AL.png`, `figs/lake_Lake_Hartwell_SC.png`, `figs/lake_Istokpoga_FL.png`, `figs/lake_Orange_Lake_FL.png`, `figs/lake_Fern_Ridge_Reservoir_OR.png`, `figs/lake_Lake_Sammamish_WA.png`, `figs/lake_Lake_Pepin_MN.png`, `figs/lake_Leech_Lake_MN.png`. Summaries: `figs/agreement_by_lake.png`, `figs/observation_age_p90.png`, `figs/climatologies_overlay.png`. (All under `experiments/adoption/seasonal/`.)

## 12. Reproduction

```
cd ~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/seasonal/scripts
PY=../../../.venv/bin/python
$PY s1_windows.py                         # polygons + windows
$PY s2_fetch.py LAKEKEY 210               # NETWORK HEAVY: ~2 GB per lake in practice (see section 0). Do not loop over lakes blindly.
$PY s2c_aux.py                            # Open-Meteo air temperature + STAC processing baselines
$PY s3_cells.py LAKEKEY                   # observer A per scene (from cache)
$PY s4_analysis.py && $PY s6_summary.py   # LOYO, gate, bootstrap, tables
$PY s5_figs.py && $PY s7_note.py          # figures; recompose this note
```
`s2b_pair.py Lake_Sammamish_WA 16` reproduces the c1/l2a pair check. Random seeds: 20260713 (gap imputation), 7 (bootstrap).
