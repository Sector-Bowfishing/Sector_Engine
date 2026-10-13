# Depth Brain: effective current depth = reference bottom elevation + live level (draft)

Research only. Date 2026-10-13. Thread: terrain. Scripts: `research/depth-brain/terrain_{datum_shift,datum_inventory,operating_range,effective_depth_examples,effective_depth_fleet,contour_interval_error}.py`. Data: `docs/research/depth-brain/data/` (`operating_range_by_lake.csv`, `datum_shift_ngvd29_navd88.csv`, `datum_inventory.json`, `effective_depth_examples.json`, `effective_depth_monthly.csv`, `fleet_delta_depth_eligibility.json`, `sigma_propagation.json`, `acres_per_ft_by_lake.csv`, `contour_interval_error.json`). Ledger: `ledger/terrain.jsonl`.

## 1. Executive summary

| # | Finding | Numbers |
|---|---|---|
| 1 | **The single high-value, bathymetry-independent quantity is the shift `level - fullPoolFt`.** A flat that was D feet deep at full pool is D + shift feet deep now. It needs no bottom map, only the live level and the pool figure Lake Brain already publishes (`differenceFromNormalPoolFt`, defined only for `poolBasis = fullPool` with confidence medium or high). | 339 of 621 lakes qualify today (417 are bound to a live level; 387 have a usable pool reference; 339 have both). |
| 2 | **Operating range is large for most lakes that can report it.** For the 187 qualifying lakes with 10 years of history, the 5-95 % level range has median 10.0 ft (10th-90th: 2.0-36.8 ft); 145 lakes are at 4 ft or more, 30 between 1.5 and 4 ft, 12 under 1.5 ft. The typical lake sits 2 ft or more below pool on 37 % of days. | `fleet_delta_depth_eligibility.json` |
| 3 | **Uncertainty is tractable for the delta and not for absolute depth unless three things line up.** With the level and pool in one datum, delta sigma is 0.27 ft (pool figure confidence high) and 1.0 ft (medium). Absolute depth of a surveyed flat is 0.4 ft with 1-ft contours and a reconciled datum, 1.35 ft with 5-ft contours, 1.8 ft with an unreconciled NGVD29/NAVD88 mismatch (fleet RMS), 3.2 ft for a Western lake with an unreconciled datum. | `sigma_propagation.json`, section 6 |
| 4 | **Datum mismatch is real, regional, and measurable.** NGVD29 to NAVD88 shifts at the 412 pool-reference lakes: median 0.64 ft in absolute value, 31 % above 1 ft, up to 5.4 ft (USBR / Mountain West median 3.1 ft; TVA median 0.2 ft, max 0.56). USACE Access2Water records give the vertical datum of 613 projects: 74 % NGVD29, 15 % "LOCAL", 6 % NAVD88. | `datum_shift_ngvd29_navd88.csv`, `datum_inventory.json` |
| 5 | **Winter drawdown is much bigger than 5-15 ft on TVA tributary lakes and much smaller on the mainstem.** Designed drawdown (fullPool minus winter pool, 62 lakes in the pool table): median 5.0 ft, 75th percentile 17.1 ft, 90th 31.5 ft; Guntersville 1.7, Wheeler 5.0, Pickwick 5.0, Kentucky 5.0, Norris 29, Douglas 45.9. | section 5.1 |
| 6 | **Worked example, Guntersville (TVA, GVDA1, 2005-2026): a 4.0 ft flat is 4.0 ft in summer and 2.8-2.9 ft in winter, and never under 1.8 ft.** Shift range -2.16 to +0.9 ft; the flat is under 3 ft on 26 % of days. **Hartwell (USACE, 2016-2026): the same flat is dry on 31 % of days.** Shift p05 -9.1, median -1.5, p95 +1.4 ft. | section 5.2 |
| 7 | **Real bathymetry changes the story.** On Lake Fork (TWDB 2-ft contours, 2008-2026 daily level) the 475 acres that are 3.5-4.5 ft deep at pool are dry on 21 % of the days; on the lowest day (-7.7 ft, Dec 2011) all 475 acres were dry and the 0-3 ft water fell from 10.4 % of the pool-level surface to 6.6 %. A drawdown does not move the shallow band; it removes it. | section 5.3 |
| 8 | **Exposed or flooded shoreline per foot is predictable in rank and roughly in magnitude.** Against CWMS acres per foot (n = 33): median predicted / true ratio 0.95, 85 % within a factor of 2. Fleet median 151 acres per foot (10th-90th: 28-1,662) across 265 of the 339 qualifying lakes (the other 74 were not sampled: the 3DEP service slowed to about one lake a minute); Guntersville 4,890 ac/ft, Wheeler 4,903, Wilson 131, Hartwell 1,002 (CWMS measured 960). | section 5.4 |
| 9 | **How much of the fleet could show a delta depth with usable confidence.** Verified usable now: 175 lakes (qualify, history present, range at least 1.5 ft, no datum failure). Qualify but unverified (no history in this study, mostly USBR, Access2Water lakes without a CWMS series, and smaller operators): 151. Never: 194 natural-surface lakes by the existing rule, 13 with unknown pool basis, 48 full-pool lakes with no bound level, plus the low-confidence pool lakes. | section 7 |
| 10 | **Recommendation.** Publish `effectiveDepthShiftFt = level - fullPoolFt` (with a seasonal-guide companion where the operator publishes a guide curve) first, as a lake-level field, for the qualifying lakes and with a range / confidence class. Add a flat-specific "now about X ft" only where a reference depth with a datum is on file at 1-2 ft contour quality; never from a 5-10 ft map or a modeled depth. | section 8 |

## 2. How Sector represents level today

From `docs/data/FULL_POOL.md`, `docs/brains/LAKE_BRAIN_INTEGRATION.md` and the Swift directory (`LakeDirectory.swift`):

* `fullPoolFt` is "normal full pool in the datum the operator's own lake level reads in": for TVA and CWMS lakes the same system as the live pool reading; for a utility on a local datum (Ameren Union Electric Datum, NIPSCO, Yadkin/Alcoa, Seattle City Light, MWRA, Pensacola) that datum; Duke is MSL (NGVD29), also published on a "100 = full pond" scale.
* `poolBasis`: `fullPool` (managed reservoir; 414 of 621 lakes) or `naturalSurface` (194; a reference only, never called flooded or drawn down; 13 empty). `poolConfidence` high / medium / low; only high and medium may produce `differenceFromNormalPoolFt` and flooded / drawn-down statements. The pool table has 353 high, 34 medium, 25 low full-pool rows.
* `apiLevel`: `dedicated` 272, `usgsOnly` 184, `none` 165 (lake_features.csv).
* Definition of full pool: the level the operator fills to and holds in normal operation; seasonal lakes use the summer normal pool or the top of the held band; never top of dam, top of gates, flood pool, maximum water surface or pool of record. Examples that matter for depth: Guntersville 595 (TVA summer pool; the top of gates is 595.4); Kentucky 359 (winter 354, held for navigation); Missouri mainstem uses the base of flood control; Little Rock District seasonal raises use the base pool; Mobile District winter-drawdown lakes use the summer maximum; USBR uses top of active conservation (or top of joint use); Florida regulated lakes the high of the regulation schedule.
* `levelState` is operator-first (`FLOOD_POOL` above the CWMS top of conservation; `IN_ZONE`, `BELOW_ZONE`, `ABOVE_ZONE` against the operator zone) and `historicalState` is a climatological position; `differenceFromNormalPoolFt` is the only signed number in feet.
* The binding thread bound 417 lakes: 248 `DIRECT_OPERATOR_POOL` and 179 `DIRECT_LAKE_GAUGE`. By provider: Access2Water 112, USGS 79 (67 + 12 daily-value variants), CWMS 64, RISE 46, NWPS 41, TVA 17, CO-OPS 14, Duke 8, and 24 on 21 smaller providers.

Mapping to depth. Effective depth = reference depth at the pool where the bathymetry was measured + (level - that pool). When the reference pool is Sector's `fullPoolFt` and the level is in the same datum, the shift is exact up to gauge and pool-figure error. When the bottom map was surveyed at another pool (a state lake map on an "ordinary high water level", a survey on the day of the sounding), a third term enters: the survey water level (section 6).

## 3. Datum alignment

**What the data say about vertical datums.**

| Evidence | Result |
|---|---|
| USACE Access2Water `vertical_datum` for 613 PROJECT records | NGVD29 456 (74 %), LOCAL 94 (15 %), NAVD88 38 (6 %), unrecorded 25 (4 %) |
| The 112 bound Access2Water lakes | NGVD29 79, LOCAL 22, NAVD88 9, unrecorded 2 |
| USGS parameter of the 79 bound USGS gauges | 62614 (elevation above NGVD29) 31; 62615 (above NAVD88) 19; 00062 (reservoir elevation, datum per site) 14; 00065 gage height + site altitude 13; other 2 |
| NOAA NGS NCAT (VERTCON 3.0), NGVD29 to NAVD88, 412 pool-reference lakes | median abs 0.64 ft; 75th percentile 1.79; 90th 3.59; max 5.42; 61 % over 0.5 ft; 31 % over 1 ft; RMS 1.78 ft |
| ... by operator family | TVA (16): median abs 0.22, max 0.56; USACE (151): 0.46, max 3.96; OTHER (177): 0.72, max 5.33; USBR (66): 3.13, max 5.42 |
| ... by region (state medians) | FL -1.0, CT -0.9, NJ -0.8, NC -0.8 ... ID +3.7, UT +3.9, WA +3.9, CO +4.5 ft |

The shift is the same sign pattern as the 3DEP-vs-gauge issue: the DEM is NAVD88, most operator figures are NGVD29. VERTCON residual uncertainty is small (NCAT reports sigma 0.07 m, 0.23 ft, at the Guntersville test point); it applies only to NGVD29 and NAVD88. A "LOCAL" or utility datum has no modeled shift at all.

**Operator conventions that matter for the shift (documented in the pool table and FULL_POOL.md):**

| Operator | Level system | Pool convention | What the shift means |
|---|---|---|---|
| TVA | operator elevation (the same system as the TVA REST API pool reading; NCAT NGVD29 to NAVD88 median 0.22 ft, so a mismatch is minor) | mainstem summer pool; tributary June fill target = top of guide curve; winter pool lower; "top of gates" is not full pool | `level - fullPool` is negative in winter by design (Guntersville -1.7 ft, Kentucky -5 ft), so a companion `level - guideCurve` is needed to say "unusually low" |
| USACE (CWMS / Access2Water) | per project, mostly NGVD29, some NAVD88, 15 % LOCAL | top of conservation / multipurpose pool (seasonal pools use the summer max or base pool) | positive values are flood-pool storage and mean newly flooded ground; flood-control lakes sit far above pool in floods (30 of 187 history lakes have a 99th percentile more than 15 ft above pool) |
| USBR | NGVD29 or NAVD88 depending on region; RISE / Hydromet | top of active conservation or joint use | USBR lakes have the largest ranges (median 5-95 % range 32 ft, n = 6 with history) |
| Duke (Catawba, Keowee-Toxaway) | MSL (NGVD29); Duke also publishes a local scale where 100 = full pond, one unit per foot (Norman 98.5 = 758.5 ft) | full pond (Wylie: top of flood gates) | on the local scale `level - 100` is already the shift in feet; Lake Robinson is reported in real feet. Normal targets sit 0.5-4 ft below full pond for most of the year (Norman 98.5 summer, 96.0 winter) |
| Santee Cooper (Marion, Moultrie) | feet on the Santee Cooper gauge; stated as the same elevation system as the 75.5 pool | Marion rule curve 72.0 ft winter to 75.5 ft summer, FERC maximum 76.8; Moultrie has no rule curve and follows Marion | designed drawdown 3.5 ft; the datum relation to NAVD88 was not checked here |
| Other utilities (Dominion Saluda, Ameren, NIPSCO, Yadkin) | local plant datums (Lake Murray: 360 ft on the Saluda Plant Datum) | full pool as the utility defines it | a local datum cannot be shifted to NAVD88 without the utility's own conversion |
| States, water districts | gauge datum | regulation schedule or ordinary high water | gage height needs the site datum |

I have not verified TVA's or Santee Cooper's published datum statements against their own documents in this thread; the TVA statement above is what the pool table and the matching of TVA readings to the pool figure support (the table treats them as one system) and the NCAT shift sizes it.

**Alignment rules for a depth computation.**

1. Level and pool in one system: take the pool figure and the live level from the same operator system, as Lake Brain already does. Then `shift` has no datum error. Check: the median of the live series should be within a plausible distance of the stated pool. 212 of 213 lakes with history pass a 200 ft check; 1 fails (Indian Lake OH: series median 1,645 ft vs pool 996 ft, a datum or unit problem in the binding or the pool figure). A flood-control lake can sit 15-50 ft above pool at the 99th percentile (30 of 187 lakes) and two big western / Texas lakes sit more than 15 ft below it (Amistad, Falcon, in drought), neither an error.
2. Bottom reference in a different datum (3DEP, a TWDB survey in NAVD88, a state map): convert with NCAT / VERTCON when both are NGVD29 / NAVD88; if either is LOCAL or unknown, stop and mark the depth `datumUnreconciled`.
3. The reference depth must come with the water level it was measured at (conservation pool, survey day level). If it is not tied to the pool, the absolute depth carries the survey-level error.

## 4. Per-lake operating range

Operating range comes from 10 years (2016 to 2026-10) of daily levels for the 417 bound lakes: CWMS series, Access2Water locations resolved to their CWMS pool series, USGS 62614 / 62615 / 00062 daily means, plus the plan thread's cached composites and HADS extracts. 213 of 417 lakes produced a usable series (coverage by provider: CWMS 60 of 64, Access2Water 81 of 112, USGS 33 of 79, NWPS 33 of 41, TWDB 2 of 2, TVA 3 of 17, CO-OPS 1 of 14, RISE 0 of 46, Duke 0 of 8, all remaining providers 0). `operating_range_by_lake.csv` carries percentiles, annual swing, drawdown percentiles and the share of days below pool by 1, 2, 5, 10 ft.

| Statistic (187 qualifying lakes with history) | 10th | 25th | median | 75th | 90th |
|---|---|---|---|---|---|
| 5-95 % level range, ft | 2.0 | 4.5 | 10.0 | 22.0 | 36.8 |
| mean annual swing (p99 - p01 within a calendar year), ft | 2.6 | 5.5 | 10.3 | 19.0 | 34.9 |

| By operator family | n with history | median 5-95 % range, ft | median 95th-percentile drawdown below pool, ft |
|---|---|---|---|
| USACE | 118 | 13.2 | 6.6 |
| OTHER (utilities, states, districts) | 60 | 4.4 | 4.1 |
| USBR | 6 | 32.4 | 34.2 |
| TVA | 2 | 3.6 | 3.5 |
| none | 1 | 2.8 | 0.2 |

58 lakes have a median level more than 2 ft below pool, 104 have a 95th-percentile drawdown over 5 ft, 59 over 10 ft. The median lake spends 37 % of days more than 2 ft below pool and 8 % more than 5 ft below.

Coverage gaps. 204 of 417 bound lakes have no series here: 31 Access2Water lakes with no CWMS series, 46 USGS lakes with no daily-mean elevation (gage-height sites need the site datum), RISE (all 46 USBR lakes), Duke (8), TVA (14; the four pilot lakes' history was used in the worked examples only), CO-OPS (13) and the small providers had no fetcher written. Their ranges are unknown, not small; the large-range USBR cohort is almost entirely in this gap.

## 5. Worked examples on real histories

Hypothetical flat: 4.0 ft deep at the Sector `fullPoolFt`. Effective depth = 4.0 + (level - fullPoolFt). Source series are the Lake Brain history inputs.

### 5.1 Designed seasonal drawdown (pool table, 62 lakes with a winter pool)

fullPool minus winterPool: 10th percentile 1.7 ft, 25th 3.5, median 5.0, 75th 17.1, 90th 31.5. TVA: Guntersville 1.7, Wilson 3.0, Wheeler 5.0, Pickwick 5.0, Kentucky 5.0, Norris 29.0, Douglas 45.9. The stated "5-15 ft winter drawdown" fits the mainstem lakes at the low end and understates the tributary storage lakes by a factor of 2-3.

### 5.2 Guntersville (TVA GVDA1) and Hartwell (USACE SAS)

| | Guntersville 2005-2026 | Hartwell 2016-2026 |
|---|---|---|
| days | 7,404 | 3,933 |
| fullPoolFt | 595.0 | 660.0 |
| shift p05 / median / p95, ft | -1.53 / -0.67 / 0.00 | -9.14 / -1.52 / +1.41 |
| shift min / max, ft | -2.16 / +0.90 | -11.10 / +4.85 |
| 4-ft flat effective depth p05 / median / p95, ft | 2.47 / 3.33 / 4.00 | -5.14 / 2.48 / 5.41 |
| share of days under 3 ft | 25.7 % | 54.9 % |
| share of days under 2 ft | 0.1 % | 45.9 % |
| share of days dry (<= 0 ft) | 0 % | 30.7 % |
| share of days at least 4 ft | 8.1 % | 31.1 % |

Monthly median shift in feet (Guntersville 2012-2026, from `effective_depth_monthly.csv`): Jan -1.23, Feb -1.10, Mar -1.10, Apr -0.40, May -0.27, Jun -0.30, Jul -0.30, Aug -0.30, Sep -0.50, Oct -0.90, Nov -1.10, Dec -1.15; extremes -2.16 and +0.50. The winter step (-1.7 ft by TVA's guide, -1.2 observed) is the whole story: the delta is visible, regular, and small. Hartwell (2016-2025): median shift runs +0.3 to +0.5 ft in April-June (the annual fill) and falls to -4.0 to -4.7 ft by October-December; the largest monthly extreme is -11.1 ft. Annual swing (p99 - p01 of the shift within a year): Guntersville 1.7-2.2 ft each year; Hartwell 4.7-15.3 ft (2016: 15.3, 2018: 13.3).

Reading: "a flat that was 4 ft is now about 2 ft" is physically right on Hartwell and wrong to say for Guntersville, where the same flat is 2.8-2.9 ft in winter and the lake's own guide says that is normal.

### 5.3 Lake Fork (TWDB 2-ft contours, daily level 2008-2026, fullPool 403.0 ft)

The flat is the set of 15 m cells that are 3.5-4.5 ft deep at pool in the survey contours: 8,549 cells = 475 acres of a 26,895 acre lake.

| | value |
|---|---|
| shift p05 / median / p95 | -6.52 / -1.63 / +0.42 ft (min -7.74 on 2011-12-03, max +2.14) |
| share of area-days of the flat shallower than 2 ft | 43.2 % |
| share of area-days dry | 21.4 % (all 475 acres dry on the lowest day) |
| median effective depth of the flat | 2.42 ft |
| 0-3 ft water as a share of the pool-level surface | 10.4 % at pool; across the record median 6.6 % (10th-90th 5.9-9.6 %); 6.6 % on the lowest day, when 80 % of the surface is still wet |

Fork has an annual swing of 1.5 to 8.3 ft depending on the year (2015: 8.3), so the same flat is a different place each month. A plain shift would say 2.4 ft for the flat; the bathymetry says the region was open water only 79 % of the time. This is the use case where a reference depth map turns the shift into a real place.

### 5.4 Newly flooded / exposed ground per foot

`acres per foot = (predicted share of the surface per foot) x area`, with the share from the 3DEP 10-60 m shoreline slope (`P_dem`, validated in the shallow-zone document). Validation on the 33 CWMS lakes with measured acres per foot: median predicted / true 0.95, 75th percentile 1.30, 85 % within a factor 2, log10 RMSE 0.22; median truth is 359 acres per foot.

Fleet run (400 shore points per lake, 265 of the 339 qualifying lakes; `acres_per_ft_by_lake.csv`): share of surface per foot median 0.018 (10th-90th 0.005-0.090); acres per foot median 151 (10th-90th 28-1,662); 29 % of lakes above 0.03 per foot. Acres use the reference (full-pool) area from `area_ref_km2` because the Sector polygon is often a lower-stage extent (Hartwell: polygon 33,800 ac vs 55,900 ac reference; median ratio 1.05, 75th percentile 1.16, max 3.9). Predicted pilots: Guntersville 0.074 per ft = 4,890 ac, Wheeler 0.093 = 4,903 ac, Wilson 0.008 = 131 ac, Hartwell 0.018 = 1,002 ac (measured 0.0166 = 960 ac), Fork 0.028 = 765 ac (table 0.028 per foot near the top). Multiply by the shift to get exposed or flooded acres: Guntersville's -2.0 ft winter step is about 9,800 acres of shoreline fringe; Wilson's is about 260.

Cautions. The proxy overstates on flat-bottomland lakes (Texas coastal plain) by a factor of 5-10 (shallow-zone document 5.2); 6.8 % of the fleet predictions hit the 0.15 cap. This is the area gained or lost at the waterline, not the depth over a flat; the DEM sees the bank above the pool, so deep drawdowns below pool are outside what it describes.

## 6. Uncertainty propagation

`sigma_depth^2 = sigma_ref^2 + sigma_level^2 + sigma_pool^2 + sigma_datum^2`. The task's three-term form folds the pool figure into the reference; I keep it separate because it is the one term Lake Brain already controls.

Source of each number: **measured** where a data table is cited, **assumed** where flagged.

| Term | Value | Basis |
|---|---|---|
| sigma_level | 0.1 ft | gauge resolution and noise; the plan thread measured live-vs-bound-series agreement at 33 lakes (median 0.00 ft, 90th percentile 0.016 ft, max 0.063 ft), so 0.1 ft is conservative. Spatial representativeness (headwater slope in a river reservoir during high flow, wind setup) is not measured here and is excluded |
| sigma_pool, confidence high | 0.25 ft assumed; empirical upper bound 1.2 ft | robust SD of (95th-percentile level - fullPoolFt) over 149 high-confidence lakes without flood-pool excursions; this includes how far operators let the level exceed pool, so it overstates a pure figure error. The old sheet's full-pool column was off by more than 0.5 ft at 152 lakes |
| sigma_pool, confidence medium / low | 1.0 / 3.0 ft assumed | unverified figures |
| sigma_datum, same system | 0 | by construction |
| sigma_datum, NGVD29 vs NAVD88 reconciled with VERTCON | 0.23 ft | NCAT output sigma at the test point |
| sigma_datum, unreconciled | 1.78 ft (fleet RMS); 3.13 ft (USBR median) | NCAT shifts at 412 lakes |
| sigma_ref, 1-ft contours (survey grade) | 0.3 ft assumed | not measured here |
| sigma_ref, 2 / 5 / 10-ft contours | 0.28 / 1.30 / 2.81 ft | measured: rebuild from every k-th contour of 1-ft TWDB maps (10 lakes), cells under 10 ft; bias -0.07 / -0.51 / -1.63 ft |
| sigma_ref, Landsat drawdown pixel depth | 0.93 ft | measured MAE averaged over 5 Texas lakes (0.44-1.39) |
| sigma_ref, modeled bathymetry | 3 ft assumed | the GLOBathy thread finds only 28 % of modeled Dmax within 1.25x of truth and no shallow-flat skill |
| sigma_ref, survey-level mismatch | 0-2 ft, unmeasured | old state maps drawn at an unrecorded water level |

Resulting sigma_depth (ft); "resolves a 4 ft to 2 ft change" means sigma at most 0.7 ft so that a 2 ft step is a 3-sigma claim:

| Scenario | sigma | resolves "4 ft -> ~2 ft" |
|---|---|---|
| delta only (level - fullPool), same datum, pool high | 0.27 | yes |
| delta only, pool sigma at the measured upper bound | 1.16 | no |
| delta only, pool medium | 1.00 | no |
| delta only, pool low or natural-lake reference | 3.00 | no |
| absolute depth, 1-ft survey contours, datum reconciled, pool high | 0.40 | yes |
| absolute depth, 2-ft contours, datum reconciled | 0.45 | yes |
| absolute depth, 5-ft state map | 1.35 | no |
| absolute depth, 10-ft state map | 2.83 | no |
| absolute depth, survey contours, datum unreconciled (fleet RMS) | 1.83 | no |
| absolute depth, survey contours, Western lake, unreconciled | 3.16 | no |
| Landsat drawdown-derived depth | 0.97 | no |
| modeled bathymetry | 3.01 | no |

The delta is almost free of the largest terms (reference and datum) because both the level and the pool figure live in the operator's system. That is why it is the right first deliverable. Its weakest term is the pool figure on medium and low rows, so the field should carry the pool confidence and withhold the number below it, as Lake Brain's rule already does for `differenceFromNormalPoolFt`.

## 7. How much of the fleet could receive a delta depth

Counts from `fleet_delta_depth_eligibility.json` (621 directory lakes):

| Gate | Lakes |
|---|---|
| bound live level (verified bindings v1 + v2, not STAGE_ONLY) | 417 |
| `poolBasis = fullPool`, confidence high or medium, figure present | 387 |
| both (differenceFromNormalPoolFt would exist) | **339** (USACE 146, other 111, USBR 65, TVA 16, none 1; reservoirs 313, regulated natural 20, natural 5, MEGA 1) |
| ... with 10 years of history fetched here | 188 (187 after the datum check) |
| ... range at least 4 ft | 145 |
| ... range 1.5-4 ft | 30 |
| ... range under 1.5 ft (delta nearly constant, little to say) | 12 |
| qualify but no history in this study (unverified range and datum) | 151 |
| full-pool rows with a pool figure but no bound level | 48 |
| bound but no usable pool reference (natural lakes, low-confidence pool, no pool figure) | 78 |
| natural surface or unknown basis (overlaps the row above where bound) | 207 (194 + 13) |

Confidence classes proposed:

* **A, usable (175 lakes):** qualifies, history shows pool is reached and the range is at least 1.5 ft. Delta publishable with the pool confidence and a range class.
* **B, qualifies but unchecked (151):** needs a history fetch or a one-time datum check of the live series against the pool figure; mostly USBR (65 qualify, 6 with history here), the 49 Access2Water lakes without a CWMS series, and the providers without a fetcher.
* **C, delta of limited meaning (12):** range under 1.5 ft. Publish the number but do not make it a headline.
* **D, none:** natural surface, unknown basis, or no live level.

Flat-specific "was 4 ft, now ~2 ft" claims need a reference depth map in addition. The study found real contours at 1-2 ft for 63 TWDB lakes (6 in the directory) and 9 Minnesota lakes at 5-10 ft (not good enough, section 6). That is the ceiling for flat-level claims today: class A on a lake with a surveyed reference is a small group (the shallow-zone document gives the survey coverage).

## 8. Recommendation

1. Add `effectiveDepthShiftFt = level - fullPoolFt` to the Lake Brain output for the 339 qualifying lakes, with `poolConfidence`, a range class (`large`, `moderate`, `small`) and the datum check status. It is the same number as `differenceFromNormalPoolFt`; the work is the range class and the display.
2. For the 17 TVA lakes publish `level - guideCurve` with it (Guntersville's normal winter step is -1.7 ft) so a regular seasonal drawdown does not read as unusual.
3. Fetch history once for the class B lakes (the Access2Water lakes without a CWMS series, USBR via RISE, the remaining providers) to turn 151 unchecked lakes into class A or C. Operating range is a static feature and needs no refresh more often than a year.
4. Do not publish a flat-specific or absolute depth unless: reference depth is at 2-ft contour quality or better, tied to a pool, in a reconciled datum, and the lake is in class A. Otherwise show the shift only.
5. Add exposed / flooded acres per foot as a coarse number with the validated band (x/÷ 1.7) for the qualifying lakes (265 computed here; the remaining 74 need the same sampling run); hide it where the shoreline-slope proxy is known to overshoot (flat-bottomland lakes) or where it is capped.
6. Datum hygiene: store the vertical datum of each live series and each pool figure (the Access2Water and USGS metadata already give it for most lakes). A lake whose two datums differ and cannot be converted (LOCAL, 15 % of USACE projects) must not receive an absolute depth.

## 9. Limits

* Operating range covers 213 of 417 bound lakes and is biased toward USACE (118 of 187); USBR and utility lakes are under-represented.
* The 10-year window includes dry and wet extremes of different lakes at different times; it is not a design range.
* Pool figures are single values; seasonal and rule-curve lakes need the guide-curve companion.
* Fork is the only lake with both contour truth and a long level series computed into a real flat; the 4-ft flat for Guntersville and Hartwell is hypothetical.
* The sigma terms flagged "assumed" (survey-grade reference 0.3 ft, pool figure 0.25 / 1 / 3 ft, modeled bathymetry 3 ft) are not measured and should be replaced when the validation thread compares sonar or lidar depths to published maps.
* Acres per foot describes the shoreline fringe near full pool and is not a depth map.

## 10. Files

`terrain_datum_shift.py` (NCAT calls, 1 per second, 412 lakes), `terrain_datum_inventory.py`, `terrain_operating_range.py` (fetch + stats, resumable, cached under the raw data folder), `terrain_effective_depth_examples.py`, `terrain_effective_depth_fleet.py` (eligibility, sigma, acres per foot), `terrain_contour_interval_error.py`.
