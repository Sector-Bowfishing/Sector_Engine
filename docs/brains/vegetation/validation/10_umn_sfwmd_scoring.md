# Note 10 - UMN Minnesota and SFWMD scoring of the production surface observer

Date: 2026-10-13. Offline research. No git repo was touched (the production code in `Sector_Engine-vegetation-adoption/jobs/lake-surface/derive_water_surface.py` is imported read-only through `experiments/adoption/prod_harness/prod_import.py`, bytecode off). Prereg gates (`VEGETATION_VALIDATION_PREREGISTRATION.md`) were not changed. All new work is in `experiments/adoption/umn_sfwmd/`.

## 0. Bottom line (read this first)

| Question | Answer |
|---|---|
| UMN surface-taxon recall, same-year scene (tier E, 3 lakes, 86 points) | **Poor: recall 0.17 among points the observer actually reads (7/40), 0.08 counting every refusal as a miss.** Gap <=7 d: 0.21 (6/28). Only 86 surface points have a S2-era scene within +-21 d, and 36 % of them sit in the 40 m SHORE_ADJACENT band. Tiny n, three lakes, no CI. |
| UMN, labelled substitutes (survey 2014-16, scenes 2017/18, tier N) | Recall known 0.39-0.64 (Minnetonka 0.67-0.90 on n=6-39 points per row, Mille Lacs 0.36-0.40). Substitute evidence only. |
| By life form (pooled E+A+N, observer A) | **Floating-leaved/free-floating points 0.72 (68/94); emergent-only points 0.19 (31/165).** Emergents (bulrush, wild rice, cattail) are mostly narrow shoreline stands or sparse stems that never reach plantFraction >= 0.5 of a 44 m cell. |
| Submersed-only points (the "cannot observe submerged" limit) | Near zero in the two northern clear lakes: **Winnibigoshish 2 % (2/106 known), Mille Lacs 2 % (12/794); 0/58 on non-canopy-capable submersed taxa.** Minnetonka (eutrophic, dense curlyleaf/milfoil/coontail) is the exception: 12 % known (7 % under v1fix), up to 43 % for 2014 points against a 2017 scene, because canopy-capable submersed taxa do top out there. This is real surface canopy, not a violation of the limit; but UMN has no per-point canopy flag for fleet lakes, so it cannot be separated from submersed truth. |
| SFWMD, Lake Okeechobee marsh (2015+2016 polygons, 2018/2019 S2) | **Weak.** Shore-matched precision 0.82-0.83 but recall 0.24 (2018) / 0.38 (2019) among known cells and only 12-18 % counting refusals; 46-53 % of positive cells are UNKNOWN (cloud/haze standoffs in June); only 1-2 accepted scenes so P = INSUFFICIENT. |
| SFWMD, Lake Tohopekaliga littoral (April 2016 polygons, 2018/2019 S2) | **Best result in this note:** shore-matched precision 0.93-0.98, recall 0.82-0.87 known (0.68-0.84 all), F1 matched 0.80-0.88, IoU 0.67-0.79. Substitute truth 2-3 y old, one lake. |
| SFWMD, Lake Kissimmee littoral (June 2015 polygons) | **Not scoreable:** no accepted pass in 2018 (S/A: NONE) and in 2019 only one single pass with 5 % non-plant-water read; its read cells give precision 0.98 / recall 0.63 but 57 % of positives are UNKNOWN. Reported as a data failure, not a result. |
| Registry finding | `East_Lake_Tohopekaliga_FL` and `Tohopekaliga_Toho_FL` carry the **identical analysis polygon**, and it is Lake Tohopekaliga (lon -81.42..-81.32, lat 28.14..28.30). East Lake Toho (SFWMD 2016 polygons at lon -81.33..-81.23, lat 28.25..28.34) has no correct fleet polygon. Worth a registry fix. |

None of this passes anything. Section 6 maps it to the gates.

## 1. Observer, scenes, and what was reused

- Observer: the imported production `dws.s2_pass` (plant pixel NDVI(B8A,B4) >= 0.30, SCL, cloud/haze/structure standoffs, 50 m Web-Mercator Frame ~44 m on the ground at 45 N, ~44.5 m at 27 N, plantFraction >= 0.5), driven from cached reflectance windows exactly as `10_run_cells.py`/`12_run_pac.py` do. Observers S/A/P from `prod_harness/score_lib.py` (prereg section 1). **Mode `v1` (guards as written, production scene gate ON, rejected scenes dropped) is primary**; `v1fix` (dark open water is a valid CLEAR read, a dark pixel can never be a plant) is a sensitivity.
- **Shore band:** production `clarity` mask = lake polygon eroded 40 m. Everything outside it is `SHORE_ADJACENT` (prereg text says "1 pixel"; the harness uses 40 m, the production rule). It is the same convention as notes 05 and the NLA runs.
- Scenes: `sentinel-2-c1-l2a` (DN*1e-4-0.1) for 2018+, `sentinel-2-l2a` (offset free) for 2017; JP2-only items skipped; same-date tiles of the same CRS are mosaicked. **There is no S2 L2A in Earth Search before 2017** (0 items in 2015-16 for all lakes here; 2017 l2a is sparse). `raw_to_dn` adds the 1000 offset for l2a so production decodes it unchanged.
- Fetch budget: 1.0 GB of cached windowed COG reads (`out/s2cache`, 140 date files) plus 0.58 GB of SFWMD JSON (Kissimmee 2015 alone 451 MB uncompressed, gzipped afterwards). Total below the 2 GB cap. Leech Lake (surveys 2002-05, 450 km2) was **not scored**: 13+ y gap and it would not fit the budget.

## 2. Taxon -> life-form lookup (task 1)

Path: `experiments/adoption/umn_sfwmd/out/umn_taxon_lifeform_lookup.csv` (230 rows - all 230 non-empty UMN TAXON strings; columns taxon, n_rows, life_form, surface_tier, canopy_capable_submersed, confidence, rationale). Built by `scripts/a_taxon_lookup.py`; every decision is a line in that script and a row in the CSV.

- `STRICT` surface (headline truth) = FLOATING_LEAVED (15 taxa: Nymphaea, Nuphar, Brasenia, Nelumbo, P. natans/nodosus, floating Sparganium) + FREE_FLOATING (7: Lemna minor, Spirodela, Wolffia...) + EMERGENT (28: Typha, Schoenoplectus/Scirpus/Bolboschoenus, Zizania, Pontederia, Sagittaria latifolia/rigida/cuneata, Sparganium eurycarpum...).
- `INCLUSIVE` adds low-confidence items (Persicaria, Phragmites/Phalaris/other tall shoreline grasses, Equisetum, spikerush, genus-level `sparganium` and `sagittaria`, Sagittaria graminea).
- `NO` (never surface truth): SUBMERSED (73 taxa; includes Lemna trisulca, bladderworts, mosses, Heteranthera dubia, P. gramineus/epihydrus/vaseyi/alpinus which have only partial floating leaves, Eleocharis acicularis, Hippuris), ALGAE (charophytes), SHORELINE_WOODY, TERRESTRIAL_FORB (wet-meadow forbs), sedges/rushes at the shore, NONTAXON ("Protectedspecies N").
- **Topped-out canopy taxa are kept separate:** `canopy_capable_submersed = Y` for Ceratophyllum, M. spicatum, M. sibiricum, Potamogeton crispus/zosteriformis/praelongus/richardsonii/amplifolius/illinoensis/robbinsii and broad genus, Stuckenia, Elodea, Heteranthera, Vallisneria and Utricularia vulgaris. They are never counted as surface truth. They only split the submersed-only group.
- Point groups (`scripts/b_points.py`): `surface_strict`/`surface_inclusive` (any matching taxon at the point); `submersed_only` (>=1 submersed taxon and nothing surface/other); `..._noncanopy_only` and `..._canopy_capable_only`; `no_veg_recorded` (NO_VEG_FOUND and no taxon).
- `SURFACE_GROWTH` is empty for every fleet-lake survey (note 09), so it is not used.

## 3. UMN fleet-lake scoring (task 1)

Fleet joins: all 27 registry lakes whose bbox touches the Minnesota region (analysis polygons from the GCS registry, cached in `out/geom/`) were point-in-polygon tested against all 367k UMN points. Lakes with points: Lake Minnetonka (2011, 2014-18), Mille Lacs (2009, 2010, 2014, 2017), Winnibigoshish (2017), Leech (2002-05), Gull (2008). Lake Pepin, Rainy, Red, Vermilion, Bemidji, Otter Tail, White Bear, Big Stone and the WI/SD/IA lakes have 0 points inside the canonical polygon. Points table: `out/umn_fleet_points.csv` (per point date, flags, taxa).

Reference date = each point's own survey day (`SURVEY_DATE`; multipart surveys span days). Scene tiers: **E** = scene within +-21 d in the survey year (only 2017 and 2018 surveys); **A** = adjacent-year substitute for those same surveys (next year, same month-day, +-21 d); **N** = surveys 2014-16 scored against 2017 and 2018 scenes (substitute, 1-4 y); **F** = surveys <=2013 against 2018 scenes (far substitute, 5-16 y; context only). A point is evaluated at the 50 m cell that contains it. Points whose cell is not in the production lake mask are dropped (`in_lake` false).

Metrics: **recall only.** "Recall known" = FLAG / (FLAG + CLEAR) at the point's cell; "recall all" = FLAG / all points (SHORE_ADJACENT, cloud, haze, dark, no-scene all count as misses). No precision, no FPR on presence data. Full per lake/year/tier/observer tables for both modes: `out/umn_tables_v1.md`, `out/umn_tables_v1fix.md` (and JSON summaries).

### 3.1 Pooled surface_strict recall (mode v1; point-weighted; no CIs, lakes n=3)

| tier / scene yr | gap | obs | points | recall known | recall all | SHORE_ADJ | cloud/haze/nodata | dark | no scene / not accepted |
|---|---|---|---|---|---|---|---|---|---|
| E (2017+2018) | <=7 d | S | 65 | 0.21 (6/29) | 0.09 | 0.29 | 0.15 | 0.11 | 0.00 |
| E | <=7 d | A | 55 | 0.21 (6/28) | 0.11 | 0.35 | 0.02 | 0.13 | 0.00 |
| E | 8-21 d | A | 26 | 0.08 (1/12) | 0.04 | 0.46 | 0.04 | 0.04 | 0.00 |
| E | all | S / A / P | 86 | 0.18 / 0.17 / 0.17 | 0.08 | 0.36 | 0.12 / 0.02 / 0.02 | 0.08-0.09 | 0 / 0.06 / 0.06 |
| A (adjacent yr, 2018) | all | A | 69 | 0.11 (4/35) | 0.06 | 0.30 | 0.07 | 0.01 | 0.10 |
| N (scene 2017) | all | A | 280 | 0.63 (63/100) | 0.23 | 0.47 | 0.15 | 0.03 | 0.00 |
| N (scene 2018) | all | A | 280 | 0.39 (24/61) | 0.09 | 0.47 | 0.21 | 0.00 | 0.10 |
| F (scene 2018) | all | A | 285 | 0.32 (27/84) | 0.09 | 0.35 | 0.04 | 0.00 | 0.32 |

The E-tier points are Minnetonka 2017 (4) and 2018 (17), Winnibigoshish 2017 (10), Mille Lacs 2017 (55). P equals A everywhere in E: it had < 3 accepted scenes (`persistence: INSUFFICIENT`) or the same median. **Gap <= 7 d headline per prereg 2.5 is 0.21 on 28-29 known points.** v1fix (dark water not refused): E recall known 0.12-0.13, dark refusals 0; the dark guard costs reads, not recall.

### 3.2 Per-lake rows that matter (observer A, v1)

| lake | survey yr | tier | points | recall known | recall all | SHORE_ADJ | note |
|---|---|---|---|---|---|---|---|
| Mille Lacs | 2017 | E (scene 2017, gap median set by Jun-Jul survey vs 14 Jul / 9 Jun scenes) | 55 | 0.17 (5/29) | 0.09 | 0.33 | dark refusals 12.7 % of surface points, 45 % of all Mille Lacs 2017 points |
| Mille Lacs | 2014 | N 2017 / N 2018 | 124 | 0.40 (17/43) / 0.36 (20/55) | 0.14 / 0.16 | 0.27 | |
| Minnetonka | 2018 | E | 17 | 0.29 (2/7) | 0.12 | 0.59 | |
| Minnetonka | 2017 | E | 4 | 0/1 | 0 | 0.75 | |
| Minnetonka | 2014-16 | N 2017 | 31 / 89 / 36 | 0.90 / 0.77 / 0.88 | 0.29-0.34 | 0.55-0.75 | n known 10 / 39 / 8 |
| Winnibigoshish | 2017 | E | 10 | 0 (0/3 known) | 0 | 0.00 | 50 % NOT_ACCEPTED, 10 % dark |
| Gull 2008, Minnetonka 2011 | F | 14, 2 | n/a | 0 | 0.57-1.0 | all refused (shore / no scene) |

### 3.3 Why recall is low (diagnostic, pooled E+A+N, A observer, v1fix; `out/umn_diag.md`)

| split | class | points | recall known | SHORE_ADJ share |
|---|---|---|---|---|
| life form | floating-leaved / free-floating (+- emergent) | 420 | **0.72** (68/94) | 0.63 |
| life form | emergent-only | 312 | **0.19** (31/165) | 0.19 |
| lake | Minnetonka / Mille Lacs / Winnibigoshish | 354 / 358 / 20 | 0.70 / 0.26 / 0.00 | 0.62 / 0.29 / 0.00 |
| recorded depth | <=2 ft / 2-4 / 4-6 / >6 ft | 42 / 354 / 278 / 58 | 0.30 / 0.52 / 0.31 / 0.11 | 0.71 / 0.54 / 0.32 / 0.24 |

(Rows are double counted across the E, A, N scene years; use for direction only.) A rake point with a water-lily in the cell does not mean 50 % of the 44 m cell is plant: rake-point presence is a much weaker condition than the observer's cell rule, so recall against presence points understates cell-level skill. Conversely a 40 m shore band removes 36 % of all E-tier surface points (62 % at Minnetonka) before any pixel is read.

### 3.4 Submersed-only recall (task 1 "cannot observe submerged")

Pooled over E+N+A scene tiers, observers A (P identical), mode v1:

| group | lake | points | recall known | recall all | FLAG/known |
|---|---|---|---|---|---|
| submersed only | Winnibigoshish (clear northern, 2017) | 194 | **0.02** | 0.01 | 2/106 |
| submersed only | Mille Lacs (clear northern) | 2,140 | **0.02** | 0.01 | 12/794 |
| non-canopy-capable submersed only | Mille Lacs / Winnibigoshish / Minnetonka | 210 / 28 / 26 | **0.00** | 0.00 | 0/58, 0/16, 0/5 |
| canopy-capable submersed only | Mille Lacs / Winnibigoshish | 1,006 / 130 | 0.01 / 0.03 | 0.00 / 0.02 | 2/347, 2/71 |
| submersed only | Minnetonka (eutrophic, milfoil/curlyleaf) | 3,852 | 0.12 (0.07 v1fix) | 0.03 | 123/1,055 |
| canopy-capable submersed only | Minnetonka | 2,610 | 0.09 | 0.02 | 65/755 |

Same-year (E) rows: Minnetonka 2017 0/9, 2018 0/128; Mille Lacs 2017 2/165; Winnibigoshish 2017 1/16. So in the northern clear lakes the observer essentially does not see submerged vegetation (two percent, the same order as the flagged share at NO_VEG points). Minnetonka's substitute-tier numbers (13-43 % for some survey/scene pairs) arise where the survey's canopy-capable species were at the surface; that is a canopy-timing and habitat-class matter, not evidence the observer sees submerged plants.

### 3.5 Flag share at NO_VEG_FOUND points (informational; a rake null is not a verified absence of floating mats, so this is **not** FPR or precision)

Minnetonka E 0/32, N 7/204 (3 %); Winnibigoshish E 0/128; Mille Lacs E 1/173, N 3/845 (<1 %). Supports (does not prove) low open-water false flagging at northern lakes.

### 3.6 Refusal shares

Reported in every table: SHORE_ADJ 29-59 % of E-tier surface points, 1-7 % of submersed points in the large lakes (because their points are offshore); cloud/haze/nodata 2-15 %; dark water 1-13 % of surface points and up to 45 % of Mille Lacs 2017 points under v1 (red and B8A both < 0.01 -> cell UNKNOWN; clear northern water is dark; v1fix removes this); no scene/not accepted 0-50 %. Ice never appeared: all references are Jun-Sep and no scene was refused for snow/ice (SCL snow class 11 is in the cloud/haze counts and was negligible).

## 4. SFWMD littoral polygons (task 2)

**Weak historical-substitute truth. Read this before quoting numbers.** The polygons are 2015-2016 photointerpretation (1 ha dominant-type grid for Okeechobee; FLUCCS communities for the KCOL lakes) scored against S2 from **2018 and 2019** (2-4 years later; emergent belts are fairly stable, floating mats and torpedograss/cattail margins are not, and SFWMD itself treats and removes cattail and torpedograss). This is weak evidence about stable emergent belts, not a gate-eligible truth set.

Downloads: public ArcGIS FeatureServer (`services1.arcgis.com/sDAPyc2rGRn7vf9B/.../VEG_OKE_2015, VEG_OKE_2016, VEG_KCOL_2015, VEG_KCOL_2016`), counts match server (27,659 / 48,425 / 5,962 / 4,994). `scripts/h_fetch_sfwmd.py`. `VEG_KCOL_2015.geojson.gz` is gzipped to save disk; gunzip to rerun.

Truth definition (`scripts/i_score_sfwmd.py`): polygons rasterised at 10 m Web-Mercator and averaged into the 50 m production cells. **Positive** = herbaceous surface vegetation fraction >= 0.5: Okeechobee classes MFF* floating emergent marsh, lotus, hydrocotyle, frog's-bit, cattail (MFGt*), all other MF*/EpD/EG/MSGs herbaceous marsh; KCOL FLUCCS 6410-6424, 6440/6442/6445 (pads, lilies, spatterdock), first code of mixed codes. **Excluded from both classes:** woody (willow/swamp shrub/forest), SAV, canals, levees, treated, open-water marsh (MFO). **Negative** = explicit open-water class >= 0.9 (Okeechobee `OW`, KCOL `5200 Lake`); where the KCOL lake class is the only open-water record. Shore matching: negatives reweighted to the positives' distance-to-polygon-edge histogram (matched population is only the bins that have both; here 100 % of positives were matchable, but all cell distances come in ~44 m steps and the bins 0-15 and 15-30 m are empty by construction). Precision "matched" is at 50 % prevalence (as in `20_score.py`); "raw" is at the cell mix in the lake.

### 4.1 How much truth the shore standoff removes, and how much is outside the lake polygon

| lake | positive cells (ha) in registry polygon | of which in the 40 m SHORE_ADJACENT band (unclaimed by design) | mapped herbaceous surface vegetation in the polygons overall (ha) | share inside the registry lake polygon |
|---|---|---|---|---|
| Okeechobee (2015+2016) | 36,802 cells (7,311 ha) | **4,762 cells = 12.9 %** | 36,454 ha | **20 %** (the rest is marsh landward of the NHD lake line) |
| Kissimmee (2015) | 13,980 (2,730 ha) | 1,778 = 12.7 % | 3,923 | 70 % |
| Tohopekaliga (2016) | 12,911 (2,506 ha) | 1,147 = 8.9 % | 2,872 | 87 % |

So the shoreline standoff removes 9-13 % of the in-polygon truth cells, and for Okeechobee the observer is by construction blind to ~80 % of the mapped marsh because it lies outside the registry water polygon. Positives are also far from shore: the first matchable bin (30-45 m) holds only 1-4 % of positives; 45 % or more lie > 150 m inside.

### 4.2 Results (scene year = labelled substitute; mode v1; positive cells reachable outside the shore band)

| lake / truth | scene year (obs) | scene (gap) | positive / negative cells | precision matched (raw) | recall known | recall all (UNKNOWN = miss) | F1 matched | IoU matched | open-water flag share (raw, known) | positives UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|---|
| Okeechobee 2015+16 | 2018 S/A/P | 20 Jun (10 d); P INSUFFICIENT (1 accepted) | 32,040 / 97,145 | 0.83 (0.54) | 0.24 | 0.12 | 0.21 | 0.12 | 6 % | 49 % |
| Okeechobee | 2019 S/A/P | 5 Jun (5 d); P INSUFFICIENT | 32,040 / 97,145 | 0.82 (0.91) | 0.38 | 0.18 | 0.29 | 0.17 | 1 % | 53 % |
| Kissimmee 2015 | 2018 S/A/P | none | 12,202 / 45,827 | n/a | n/a | 0 | n/a | n/a | n/a | 100 % |
| Kissimmee | 2019 S | 23 Jun (8 d) | 12,202 / 45,827 | 0.98 (1.00) | 0.63 | 0.27 | 0.43 | 0.27 | 0.4 % | 57 % |
| Kissimmee | 2019 A/P | none accepted (non-plant read < 25 %) | | n/a | n/a | 0 | | | | 100 % |
| Tohopekaliga 2016 | 2018 S (A fallback) | 25 Mar (21 d) | 11,764 / 22,600 | 0.98 (1.00) | 0.82 | 0.68 | 0.80 | 0.67 | 0.2 % | 18 % |
| Tohopekaliga | 2019 S/A/P | 24 Apr (9 d); P = A (<3 scenes) | 11,764 / 22,600 | 0.93 (0.97) | 0.87 | 0.84 | 0.88 | 0.79 | 2 % | 4 % |

Sub-class recall (known cells, 2019): Tohopekaliga floating/pads 0.99, cattail 0.94; Okeechobee floating emergent marsh 0.37, cattail 0.37; Kissimmee floating 0.70 (one pass). 2018 Tohopekaliga: pads 0.96, cattail 0.95. Recall by distance, UNKNOWN counted as miss (Okeechobee 2019): 30-45 m 0.61 (99/161), 60-90 m 0.55, 90-150 m 0.41, 150-300 m 0.18, > 300 m 0.05 - the interior marsh far from the line is where the observer fails, plausibly because the polygons mark a 100 m cell's dominant type (often sparse or senescent cattail under a canopy that is also partly rejected as haze/cloud) and because hazards (haze/cloud standoff) are not randomly distributed. UNKNOWN alone explains half the miss: 46-53 % of Okeechobee positives, mostly CLOUD/HAZE standoffs (June cumulus).

Per-observer notes: S, A, P are identical on all of these lakes except where only one scene qualified. P could not be tested (never >= 3 accepted scenes), and no temporal-persistence claim is possible from this data. v1fix changes nothing material (Okeechobee recall known 0.22-0.38; `out/sfwmd_scores_v1fix.json`).

Honest read: against floating-and-emergent beds in a clear, shallow, bright-marsh lake (Tohopekaliga) the production rule is good even with a 2-3 year substitute. Against Okeechobee's huge marsh it recovers little, because (a) the lake polygon excludes most of it, (b) cumulus sets the UNKNOWN share, (c) the scored interior is dominated by dense cattail/pads cells far from shore whose recall is 0.2-0.4. There is no way to tell how much of that miss is truth age.

## 5. Limits (all)

- Presence-only UMN points give recall only; recall is point-in-cell, a weaker condition than the cell rule; small n, three lakes, no bootstrap (a lake bootstrap on 3 units is meaningless).
- Same-year S2 exists only for the 86 surface points of the 2017-2018 surveys. Every other row is a labelled substitute 1-16 years off; do not pool substitute tiers with E.
- Survey dates are per point but multipart surveys span weeks; scenes were chosen per point date.
- 40 m shore standoff (not 1 pixel) per the production mask; shorelines are exactly where emergent belts and lily beds live, so a large share of every truth set is unclaimable.
- Dark-water guard (v1) refuses a lot of clear northern water (Mille Lacs 2017: 45 % of points). v1fix shown as sensitivity only; any use needs a documented amendment, not an edit.
- l2a (2017) and c1 (2018+) differ by collection; JP2-only 2017 items skipped; the Winnibigoshish and Mille Lacs 2017 summer coverage is 3-5 dates.
- Taxon lookup is a hand mapping with explicit confidence; the inclusive tier is sensitivity only.
- SFWMD: age, class-mapping judgement (what counts as surface herbaceous), 1 ha dominant-type grid, only ~20 % of Okeechobee marsh in the polygon, cloud/haze UNKNOWN, 1-2 accepted scenes, assumed registry polygon correctness (Toho key problem).
- Sample of fields not verified: `cell_ground_m` for shore-distance bins; the KCOL FLUCCS modifier (density D/S) was ignored.

## 6. Which prereg section 5 gates this informs (task 3)

- **(a) cell precision >= 0.80 and recall >= 0.70 pooled and for each of >= 3 independent truth lakes with >= 30 positive cells:** none of this passes it. UMN is presence-only, so it can never supply precision; its same-year recall (0.17 known) is far below 0.70. SFWMD supplies both, and **Tohopekaliga 2019 numerically meets it (P 0.93, R 0.87 known / 0.84 all)**, Okeechobee fails recall, Kissimmee is unscoreable; with one passing substitute-truth lake it is not 3 lakes, and the prereg's 7 d survey-image gap is not met (the truth is 2-3 years older than the scene). It informs (a) only as a directional, substitute-truth data point; **it cannot count toward the gate**.
- **(b) open-water FPR <= 2 %:** SFWMD open-water cells (explicit OW, marsh ponds and lake) give raw flagged shares 0.0-6 % (Okeechobee 6 % in a hazy 2018 scene, 1 % in 2019; Tohopekaliga 0.2-2 %; Kissimmee 0.4 %). UMN NO_VEG points give 0-3 %, and are not verified open water. Weak, substitute evidence for (b).
- **(c) NLA:** not informed. **(d) negative-control flagged share:** not informed (NO_VEG points are not NLA-zero lakes), but they are consistent with it. **(e) bootstrap F1 lower bound >= 0.65:** not informed; there are too few units for lake-level bootstrap.
- **RESEARCH** entry ("scored once on >= 2 independent truth sets") was already met; these are two more. **CALIBRATION/PARTIAL "truth lakes" counts:** the prereg's CALIBRATION text needs >= 10 truth lakes but does not say recall-only or substitute-date lakes count. Under the most conservative reading (same-year or <= 7 d truth only) this note adds **0** truth lakes (E-tier UMN has 86 surface points, Winnibigoshish 10; no polygons). Under a looser reading that admits labelled substitutes: **+3 recall-only UMN lakes** (Minnetonka, Mille Lacs, Winnibigoshish; Winnibigoshish is marginal at 10 surface points) and **+2 polygon lakes** (Tohopekaliga, Okeechobee; Kissimmee excluded, no accepted pass). I recommend counting them only in a separate "substitute / recall-only" column and an explicit prereg amendment if the team wants them to move CALIBRATION. They also give the regional spread the gate wants: northern clear lakes (MN) and a subtropical shallow lake (FL), but not a turbid reservoir or a hydrilla system.

## 7. Files and commands

All under `~/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/umn_sfwmd/` (cwd for every command; python = `experiments/.venv/bin/python`).

```
a_taxon_lookup.py                       -> out/umn_taxon_lifeform_lookup.csv  (needs out/taxa_counts.json: Counter of TAXON in plants_env_data.csv)
b_points.py                             -> out/umn_fleet_points.csv, out/geom/*.geojson (registry analysis polygons)
d_fetch_run.py LAKEKEY fetch|run|both   -> out/s2cache/*.npz, out/cells50_{lake}.npz   (Lake_Minnetonka_MN, Mille_Lacs_Lake_MN, Lake_Winnibigoshish_MN, Gull_Lake_MN, Okeechobee_FL, Kissimmee_FL, Tohopekaliga_Toho_FL)
e_score_umn.py v1|v1fix                 -> out/umn_point_results_{mode}.csv
f_summarize_umn.py v1|v1fix             -> out/umn_tables_{mode}.md, out/umn_summary_{mode}.json
g_diag_umn.py                           -> out/umn_diag.md
h_fetch_sfwmd.py SERVICE...             -> out/sfwmd/{service}.geojson   (gunzip VEG_KCOL_2015 before scoring)
i_score_sfwmd.py v1|v1fix               -> out/sfwmd_scores_{mode}.json
lakes_cfg.py                            (reference dates, tiers, SFWMD scene settings)
```
Production code is imported, not copied: `prod_harness/prod_import.py` (`dws.s2_pass`, `Frame`, `lake_masks`), observers in `prod_harness/score_lib.py`. New files are logged in `MANIFEST.jsonl` (kind `umn_sfwmd`).
