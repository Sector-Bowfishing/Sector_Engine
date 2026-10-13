# Lake Brain: hydrologic, classification and shallow-water context (Tracks 5, 6, 7)

Research thread `context`, 2026-10-13. Research only: no deploy, no RTDB/bucket write (read-only `gsutil cat` of the Water Clarity `index.json`, five pilot `history.json` files and one `latest.json`, ledger S-context-017), no change to any lifecycle, rubric or customer surface.
Base: `feat/cost-efficient-scheduling` @ `48168baa`, branch `docs/lake-brain-research`.
Reproduce: `research/lake-brain/context_*.py` (see section 6). Ledger: `ledger/context.jsonl` (22 sources including every dead end, 7 blockers, 2 actions). Bulk data: `~/Desktop/Development/Sector_Research_Data/lake-brain/context/` only (retention rows in `MANIFEST.jsonl`).

**Product filter applied to everything below:** Sector is a bowfishing product. A characteristic is kept only if it helps say where, when or under what conditions a bowfisher meets useful fish and water (shallow flats, coves, tributary mouths, flooded vegetation, shoreline, at night, clear-ish water), or if it helps knowledge transfer between lakes. Everything else is listed as low value and not pursued.

## 0. Bottom line

| # | Finding | Evidence |
|---|---|---|
| 1 | The Tennessee-River pilots are **one hydraulic system, not four independent samples.** The predicted outflow of each TVA dam equals the next pool's predicted inflow within 0.3-4 % and pool elevations move 0-0.14 ft/day. Hydrology-driven claims validated on Guntersville/Wheeler/Wilson/Pickwick have an effective n of about 1-2. | section 2.4 |
| 2 | "Run-of-river vs storage" is computable for **577 of 621 lakes** from storage (HydroLAKES/NID) and mean annual inflow (NHDPlus HR EROM at the dam). All four TN pilots are run-of-river (8.6-13.0 d); Hartwell is storage (370 d). The ordering and magnitudes are sensible across the fleet (Lewis & Clark Lake 10 d, Kentucky Lake 45 d, Powell 2.1 y, Mead 3.1 y); they were not checked against a published table in this thread. | section 2.3 |
| 3 | Current release data exist only from the operators: **TVA RestApi works for all 16 TVA lakes** (hourly discharge, tailwater, 3-day predicted inflow/outflow); USACE CWMS carries outflow series for hundreds of projects. USGS discharge gauges on the TN mainstem were discontinued 1994-2004. | section 2.5 |
| 4 | A watershed model is **not** needed. Seven static, public attributes per lake (storage, inflow, residence time, drainage area, dam presence/height, upstream/downstream directory lakes, release-feed availability) cover the hydrologic context. | section 2.6 |
| 5 | A lightweight class scheme is feasible for all 621 lakes: **11 classes from five ordered rules; 615 of 621 lakes get a class from measured or directory data (6 have no usable data)** (table 3.3). It adds modest explanatory value over geography: class explains 10 % of the variance in turbidity rank, region 25 %, both 31 %; vegetation share is explained 1 % / 11 % / 12 %. Region must be a stratifier; vegetation must be measured, not inferred. | section 3.4 |
| 6 | The 5 pilots sit in 2 of 9 modelled classes (R1, R3) and one region (SE): **17 % of the fleet is within a "similar lake" distance of a pilot (25 % at a looser threshold).** Ten additional type slots raise that to 62 % (82 % looser), versus 50 % for ten random lakes. | section 3.5 |
| 7 | **Shoreline slope from the 3DEP DEM is the one shallow-water proxy that validated.** Against stage-area curves derived from USACE storage and pool series for 33 reservoirs, the predicted share of surface gained per foot of pool has Spearman 0.76 (shape-only -0.16, GLOBathy 0.33) and is within a factor of two for 82 % of lakes (a constant guess: 76 %); Hartwell is predicted 0.0174 per ft vs 0.0166 measured. | section 4.3 |
| 8 | Not worth integrating: JRC occurrence (confounded by vegetation and clarity), NWI littoral class (mapping rules differ county to county), GLOBathy depth (46 m modeled vs about 20 m real at Guntersville), tributary-mouth density (0.03-0.055 per shore km everywhere), lake-wide bathymetry projects. | sections 4.2, 4.4 |
| 9 | Data-quality findings for other threads: directory `hasDam=false` for 13 lakes whose NID dam is 25 ft or higher (Pend Oreille 180 ft); 22 lakes have no polygon and about 20 polygons disagree with HydroLAKES/NID by more than 2x. | section 3.1 |

## 1. What was built and how lakes were joined

All numbers use the 621-lake directory snapshot (`directory_lakes_2026-10-13.json`) and the 599 engine polygons.

| Dataset | Used for | Join rule | Matched lakes | Notes |
|---|---|---|---|---|
| Directory attributes | hasDam, operator, poolBasis, apiLevel, gauge, CWMS office | direct | 621 | `hasDam` is unreliable for dammed natural lakes (3.1) |
| Engine polygons | area, perimeter, shoreline development, narrow-water fractions, arm counts, shore-distance bands | direct | 599 (22 missing) | per-lake equal-area projection |
| HydroLAKES v1.0 points (79 MB) | storage, Lake_type, modeled discharge, watershed area | within 5 km of the polygon; same normalised name (or one name contains the other) with area ratio 0.2-5, else the closest-in-size unclaimed candidate (ratio 0.4-2.5); one HydroLAKES lake to one directory lake unless the rows are the same lake listed twice | 554 (348 name, 206 geometry) | name collisions are real (HydroLAKES "Wilson Lake" is Kansas); about 9 % of the audited named geometry matches were wrong neighbours (Fort Loudoun -> Tellico, Griffin -> Eustis) |
| NID via Esri mirror (92,627 dams) | dam presence, height, year, purposes, storage, drainage area | within 5 km; name match preferred, dikes/saddles demoted, else surface area 0.2-5x polygon | 501 (460 name, 41 geometry) | official API returns 403 (B-context-001) |
| NHDPlus HR flowline at the matched dam | EROM mean annual flow, drainage area, stream order | +-0.004 degree box around the dam, keep largest `totdasqkm` | 499 of 501 | rejected where yield < 0.01 cfs/km2 |
| GLOBathy (Dmax, A = a h^b) | modeled depth and shallow fraction | via HydroLAKES id | 554 | modeled, see 4.3 |
| NLDI downstream navigation (250 km) | upstream/downstream directory lakes | from the matched dam coordinate | {{CHAIN_N}} lakes processed | resumable, NLDI rate-limits |

Derived reference quantities (all in `lake_features.csv`): `area_ref_km2` = max of polygon, HydroLAKES, and NID surface area when within 2x of the other two; `storage_mcm` = HydroLAKES capacity, else NID; `inflow_m3s` = EROM gage-adjusted (qema), else runoff EROM, else HydroLAKES; `res_time_d` = storage / inflow; `dor` = residence time / 365 (degree of regulation); `mean_depth_m` = storage / `area_ref`.

Coverage of derived fields: residence time 577, mean depth 577, inflow 575, drainage area 599, dam attributes 501, polygon morphometry 599.

## 2. Track 5: hydrologic context

### 2.1 Questions Sector must be able to answer, and what answers them

| Question (bowfishing relevance) | Machine-readable answer | Scales to | Tested |
|---|---|---|---|
| Is the pool held steady by an upstream/downstream dam, or does it swing with inflow? (flats exposed or flooded) | residence time and degree of regulation (storage / mean annual inflow) | 577 lakes | 5 pilots + fleet sanity list |
| Which reservoir feeds which? (upstream release drives current, clarity and level in the next pool) | NLDI downstream main-stem navigation from the dam, intersected with directory polygons | any lake with a dam coordinate | Tennessee chain reproduced |
| What flows in, how big is the basin? (flood pulses, turbid inflow after rain) | NHDPlus HR `qema`, `totdasqkm` at the dam; HydroLAKES `Dis_avg`, `Wshd_area`; NID `DRAINAGE_AREA` | 499 + 554 + 501 lakes | cross-checked 3 ways |
| Where are the tributary zones? | polygon arms (narrow-water fraction, arm count); NHD flowline mouths | 599 / pilots | sections 3, 4 |
| Is there a public release / generation feed? | TVA RestApi, CWMS, NWM reaches | 16 + ≥177 lakes | live GETs |
| Is it regulated at all? | NID dam match + height, HydroLAKES `Lake_type` | 501 / 554 | fleet crosstab |

### 2.2 Hydrologic attributes of the pilots

| Lake | class | area_ref km2 | storage Mm3 | inflow m3/s (EROM qema) | residence time d (computed / HydroLAKES) | degree of regulation | drainage km2 |
|---|---|---|---|---|---|---|---|
| Guntersville | R1 | 267 | 1,294 | 1,156 | 13.0 / 9.8 | 0.036 | 61,910 |
| Wheeler | R1 | 212 | 1,319 | 1,370 | 11.1 / 8.5 | 0.031 | 75,037 |
| Wilson | R1 | 63 | 1,055 (HL geometry match) | 1,418 | 8.6 / 6.6 | 0.024 | 77,983 |
| Pickwick | R1 | 173 | 1,363 | 1,501 | 10.5 / 8.0 | 0.029 | 83,314 |
| Hartwell | R3 | 226 | 4,242 | 133 | 369.8 / 398.6 | 1.013 | 5,425 |

Run-of-river means the whole pool turns over in about one to two weeks at mean flow (current flow in October, about 28,000 cfs, gives about 19 days at Guntersville). Hartwell holds more than a year of inflow.

### 2.3 How good are the flow and storage numbers?

| Check | Result |
|---|---|
| EROM `qema` vs long-term gauge means below/near the pilots | Guntersville 40,809 cfs vs Whitesburg gauge 43,265 (-6 %); Wilson 50,084 vs Florence 52,139 (-4 %); Pickwick 53,022 vs Savannah TN 56,477 (-6 %); Hartwell 4,689 vs Savannah River near Iva 4,525 (+4 %) |
| HydroLAKES `Dis_avg` vs the same gauges | Guntersville +24 %, Wheeler +22 %, Wilson +25 %, Pickwick +23 % (runoff routing without regulation); Hartwell -4 % |
| EROM vs HydroLAKES, fleet | median log10 ratio -0.03 (-7 %), IQR -0.13 to +0.06, n = 433 |
| Drainage area: EROM vs NID | within x1.25 for 80 % (n = 483); HydroLAKES vs EROM median log10 -0.005 |
| NID attribute errors found | Wheeler Dam drainage 232 mi2 (true about 29,000) and storage 228,045 ac-ft (HydroLAKES 1.07 M); Bull Shoals surface area about 10x; outlet structures on natural lakes carry the structure's surface area (Sebago x16) |
| EROM failure mode | about 0 cfs at some western and plains dams (diverted / endorheic). Rejected where `qema/DA < 0.01 cfs/km2` or residence time > 10,000 d; falls back to HydroLAKES |
| Fleet sanity (computed residence time; plausible, not checked against a published table) | Lewis & Clark Lake 10 d, Lake Sharpe 28 d, Kentucky Lake 45 d, Fontana 189 d, Norris 308 d, Texoma 382 d, Lanier 638 d, Powell 760 d (2.1 y), Mead 1,142 d (3.1 y) |

Reservoir classes by residence time (397 lakes classified as reservoirs): run-of-river < 30 d: 57; flow-through 30-180 d: 91; storage > 180 d: 239; unknown: 10.

### 2.4 The river-reservoir chain

NLDI main-stem navigation from the Guntersville dam (comid 19626226) returns, with straight-line distance from the dam: Wheeler 0 km, Wilson 117 km, Pickwick 143 km, Kentucky Lake 205 km. The same call from Wheeler and Wilson returns the rest of the chain, so the Tennessee River graph is derivable from dam coordinates alone. UM navigation also returns the adjacent downstream pool (its headwater touches the dam); direction is therefore taken from DM only.

How tightly the pilot pools are coupled (TVA RestApi `predicted-data`, 3-day average cfs, fetched 2026-10-13):

| Day | Guntersville out | Wheeler in | Wheeler out | Wilson in | Wilson out | Pickwick in |
|---|---|---|---|---|---|---|
| 10/13 | 29,545 | 30,667 | 30,560 | 30,068 | 30,883 | 30,962 |
| 10/14 | 28,437 | 29,295 | 28,370 | 27,833 | 28,905 | 28,923 |
| 10/15 | 28,452 | 29,225 | 28,370 | 27,820 | 27,825 | 27,827 |

Downstream inflow equals upstream outflow plus 0-4 % of tributary water; midnight pool elevations change by 0 to 0.14 ft per day (Guntersville 593.81 -> 593.95 -> 594.06). **Consequence for validation:** leave-one-lake-out inside this chain mostly tests the same flow signal four times. Transfer evidence has to come from lakes outside the chain (section 3.5).

Fleet chains: {{CHAIN_FLEET}}

### 2.5 Public release / discharge data (verified 2026-10-13)

| Source | Content | Coverage | Lag | Notes |
|---|---|---|---|---|
| TVA RestApi `observed-data/<id>.json` | hourly pool elevation, tailwater elevation, average hourly discharge | 16 of 16 TVA directory lakes: GVDA1 WHLA1 WLSA1 PICT1 NKJT1 CKDT1 FLDT1 DUGT1 KYDK2 NRST1 FONN7 WBOT1 CRKT1 HIWN7 SHDT1 TMFT1 (ids are the NWS pool-gauge ids; also MHDT1 Melton Hill, NRMT1 Normandy) | about 1 h | serves the current day only (8 rows); `*Tailwater*` ids return []. HTML pages on tva.com return 403, the JSON does not |
| TVA RestApi `predicted-data/<id>.json` | 3-day average inflow, outflow, midnight elevation | same | daily | the basis of the chain-coupling table above |
| USACE CWMS Data API | `Flow-In`, `Flow-Out`, `Flow-Power`, `Flow-Spill`, `Stor`, `Elev-Pool`, `Elev-Tail`; Hartwell daily archive from 1962, hourly raw from 1997/2000 | 177 directory lakes carry a `cwmsOffice`; flow-type series exist at hundreds of locations (projects and gauges: SWT 437, SPL 253, LRH 220, SPK 165, SWF 163, SPA 141, SAJ 73 ...). Naming differs by district (`Flow-Out`, `Flow-Res Out`, plain `Flow`); NWK and NWO data sit under office `NWDM` | about 5 days at SAS | catalog `extents` are stale (Hartwell showed 2026-09-13 while values reached 2026-10-08), so freshness must be tested on values |
| USGS NWIS daily/annual | discharge at gauges near each dam | 310 directory lakes list a gauge | n/a | the TN mainstem gauges are historical: 03575500 Whitesburg 57 y to 1994, 03589500 Florence to 2002, 03593500 Savannah TN to 2004; 03573500 and 02187252 return nothing current. Only operators publish current releases |
| NOAA NWPS gauge catalog | ids and names of pool/tailwater gauges (found the TVA ids) | TN valley 750 gauges | live | National Water Model reach flows are already used by `hydrology-hourly` |

Hartwell on 2026-10-08: pool 648.93 ft (about 11 ft under the 660 ft full-pool value in the directory), generation 0 cfs. Release behaviour differs fundamentally from the TN chain even though both are "hydropower".

### 2.6 Does Sector need a watershed model?

No. The evidence shows that static, public attributes capture the regime (section 2.3) and the coupling (section 2.4), and the dynamic part is supplied by operator feeds (section 2.5). A model would add value only if Sector wanted to forecast pool or inflow for lakes with no operator feed (about 444 lakes have no CWMS office and 605 are not TVA); that is a Track 9/10 decision and was not needed to characterise any lake here.

Retained hydrologic features (computed for the fleet): `res_time_d`, `dor`, `inflow_m3s`, `drainage_km2`, `da_to_area`, `n_up_lakes`, `n_down_lakes`, `nearest_down`, `chain_id`, plus the booleans "TVA feed" and "CWMS office" which already exist in the directory.

### 2.7 Dead ends and leads (also in the ledger)

* USACE NID bulk API returns 403 to scripts; worked around with the Esri Federal Data mirror (B-context-001).
* USGS StreamStats legacy services (`watershed.json`, `stateservices.json`) are decommissioned (2026-01-30); the replacement SS-Delineate/SS-Hydro was not needed (B-context-002).
* USGS OGC API returns `OVER_RATE_LIMIT` without a key; NLDI throttled the chain job after about 1,000 calls in 35 minutes (the job now waits two minutes per throttled call and resumes).
* TVA tailwater ids and USGS TN mainstem discharge give no current data.

## 3. Track 6: lightweight classification

### 3.1 What is cheaply computable, what needs external data

| Group | Fields | Lakes | Source |
|---|---|---|---|
| Polygon morphometry | area, perimeter, shoreline development index SDI = P / (2 sqrt(pi A)) (also exterior-only `sdi_ext`), parts, islands, solidity, elongation, share of area within 50/100/250 m of shore, share of water narrower than 300 m and 800 m, count and length of narrow arms | 599 | `context_geom.py` |
| Directory | hasDam, operator family, poolBasis, apiLevel, gauge, CWMS office, fullPoolFt | 621 | snapshot |
| HydroLAKES | storage, Lake_type (1 lake, 2 reservoir, 3 control structure), modeled depth, discharge, watershed | 554 | free point file |
| NID | dam height, year, purposes (hydropower), storage, surface area, drainage | 501 | Esri mirror |
| NHDPlus HR | mean annual flow, drainage area, stream order | 499 | per-dam query |
| GLOBathy | modeled Dmax and shallow-area fraction | 554 | 640 MB download, tested in 4.3 |

Operator families in the fleet: USACE 168, other (utilities, states, municipal) 253, no operator 113, USBR 71, TVA 16 (directory `operatorName` normalised).

Data-quality findings:

* **`hasDam` is not a reliable "regulated" flag.** 105 lakes with `hasDam=false` carry a dam signal (an NID name match or HydroLAKES reservoir/control-structure type); among the 93 with a name-matched NID dam, 13 dams are 25 ft or higher and four 50 ft or higher (Lake Pend Oreille 180 ft, Jackson Lake WY 84 ft, Lake Chelan 66 ft, Catahoula 61 ft). Maine, New Hampshire and Minnesota headwater lakes are dam-raised natural lakes.
* **Polygon area is the currently mapped water.** Against NID surface area, 81 % of polygons are within 0.7-1.4, 13 % are below 0.7 (low-pool western reservoirs: Alamo 0.07, Elephant Butte 0.26, Oahe ND 0.35, Roosevelt 0.31) and 6 % above 1.4. Against HydroLAKES, 67 % are within 0.8-1.25; HydroLAKES under-maps large narrow reservoirs (Powell 121 vs 518 km2). `area_ref_km2` takes the maximum of the credible estimates.
* About 20 polygons are wrong by more than 2x or tiny (Lake Shafer IN 0.0002 km2, Buckeye Lake OH 0.003, Longview Lake MO 0.08, Reelfoot TN 0.75); 22 lakes have none. B-context-007, handed to the geometry thread.
* Multi-state lakes appear as separate rows with separately trimmed polygons (Oahe ND/SD, Kerr NC/VA, Thurmond GA/SC, Flaming Gorge UT/WY).

### 3.2 Proposed retained feature set (11 features)

Selected by the product filter: each feature must change what a bowfisher would expect, or let the model borrow strength from a similar lake.

| # | Feature | Computed for | Why it matters to bowfishing or to transfer |
|---|---|---|---|
| 1 | `regime`: reservoir / regulated natural / natural / very large | 621 | decides whether pool management exists at all; the largest single driver of exposed flats and shoreline access |
| 2 | `res_time_d` (and class RoR / FLOW / STOR) | 577 | current, mixing, how fast an upstream release or storm pulse reaches the flats; the transfer axis between TVA-style pools and storage lakes |
| 3 | `area_ref_km2` | 599 | amount of shoreline and habitat; scale effect on wind exposure |
| 4 | `mean_depth_m` | 577 | depth sets the shallow fraction, thermal regime and clarity; reservoirs from capacity/area are good (Guntersville 4.8 m), natural lakes rely on modeled HydroLAKES depth |
| 5 | `sdi_ext` and `frac_narrow_300m` (arms, coves) | 599 | coves, arms and tributary zones are where bowfishers operate; free from the polygon |
| 6 | `frac_within_100m` (shore band share) | 599 | share of the surface within casting distance of a shoreline |
| 7 | operator family and release-feed availability | 621 | determines how the pool is managed (flood-season drawdown, irrigation draw, hydropower peaking) and what data exist |
| 8 | region (SE / NE / MW / GP / W / AK-HI) | 621 | explains more variance in clarity than any hydraulic class (3.4) |
| 9 | shoreline slope index from 3DEP (median slope, share under 2 degrees, run per foot) | pilots + 51 lakes now; about 1 min per lake | the only proxy that predicts how much surface is gained or lost per foot of pool change (4.3) |
| 10 | chain position: `n_up_lakes`, `n_down_lakes`, `nearest_down` | {{CHAIN_N}} lakes | upstream releases govern downstream pools; defines non-independent validation lakes |
| 11 | measured vegetated-shallows share: Water Clarity `grassPct` (existing production product) | 566 lakes | vegetation is lake-specific and cannot be inferred from morphology (3.4); Guntersville 23 %, Wheeler 5.8 %, Hartwell 6.4 %, Pickwick 2.0 %, Wilson 1.6 % |

Low value (computed or tested, not retained): `hl_type` as a standalone feature (folded into regime), elevation, HydroLAKES shore development (duplicates SDI), volume (area x depth), NID dam year/height beyond the regulated flag, hydropower flag beyond operator, GLOBathy Dmax and shallow fraction (4.3), JRC occurrence, NWI littoral class, tributary-mouth density.

### 3.3 Draft class scheme and counts (621 lakes)

Rules are applied in order; thresholds come from the observed distributions (30 d and 180 d are near the 10th and 30th percentile of reservoir residence times; SDI 8 is the 75th percentile; 6 m is the 25th percentile of mean depth).

1. **X_very_large**: area_ref above 1,500 km2, or Great Lakes and bays.
2. **Regime**: reservoir = directory says dam and pool basis is a built full pool; regulated natural = a dam signal (NID name match, HydroLAKES reservoir/control type, directory dam) on a natural-surface lake, or a "no dam" lake with a dam signal; natural = no dam signal.
3. **Reservoirs**: small impoundment if area_ref < 2 km2; else by residence time: run-of-river (< 30 d), flow-through (30-180 d), storage (>= 180 d or unknown) split into dendritic (`sdi_ext` >= 8) and open basin.
4. **Regulated natural**: small (< 2 km2) or other.
5. **Natural**: small, shallow (mean depth < 6 m) or deep/unknown.

| Class | Lakes | median area km2 | median res. time d | median mean depth m | median SDI | examples |
|---|---|---|---|---|---|---|
| R1 run-of-river pool | 46 | 47 | 13 | 7.4 | 8.9 | Guntersville, Wheeler, Wilson, Pickwick, Barkley, Dardanelle, Lewis and Clark Lake |
| R2 flow-through reservoir | 85 | 28 | 105 | 11.7 | 7.0 | Kentucky Lake, Douglas, Cherokee, Keystone, Allatoona |
| R3 dendritic storage | 91 | 73 | 417 | 22.3 | 12.3 | Hartwell, Lanier, Norris, Table Rock, Powell, Mead |
| R4 open-basin storage | 146 | 18 | 517 | 15.5 | 4.4 | Great Plains and western reservoirs, Moultrie |
| R5 small impoundment | 25 | 0.4 | 32 | 2.5 | 2.5 | Delaware ponds, Mansfield Hollow |
| N1a natural deep / depth unknown | 56 | 70 | 2,125 | 24.5 | 2.2 | Yellowstone, Alaska lakes, Champlain |
| N1b natural shallow | 34 | 27 | 343 | 3.5 | 2.1 | Istokpoga, Lochloosa, Spirit Lake IA |
| N2 regulated natural lake | 99 | 28 | 401 | 4.8 | 2.7 | Moosehead, Sebago, Leech, Winnibigoshish, Pend Oreille |
| N3 small pond or outlet-dam lake | 15 | 1.1 | 366 | 4.9 | 1.9 | CT and HI small lakes |
| X very large | 18 | 1,650 | 440 | 3.8 | 2.4 | Great Lakes, Okeechobee, Pontchartrain |
| Z no data | 6 | n/a | n/a | n/a | n/a | Hawaiian reservoirs, Iliamna, Chickahominy |
| **Total** | **621** | | | | | |

Reservoir/regime counts: reservoir 397, regulated natural 108, natural 98, very large 18. Classes by region (SE / NE / MW / GP / W / AK-HI): R1 29/3/4/4/6/0; R2 33/13/9/11/19/0; R3 41/3/16/17/14/0; R4 12/25/21/33/54/1; R5 1/18/3/2/0/1; N1a 3/8/13/1/20/11; N1b 15/7/4/4/3/1; N2 8/49/21/5/16/0; N3 1/9/1/0/2/2; X 2/3/11/1/1/0. By operator family, TVA lakes are R1 (8), R2 (4), R3 (4); USACE lakes dominate R3 (55) and R2 (32); USBR lakes are R4 (38) and R2 (14).

### 3.4 Does the classification help?

Independent test: the production Water Clarity index (read-only copy of the fleet `index.json`, latest pass per lake, 2026-10-12, n = 563 classifiable lakes with a clarity pass). The class is built from hydraulics and shape only, so any explanatory power is evidence that the scheme carries information that transfers. Adjusted R2 of an OLS on rank-transformed outcomes:

| Predictor set | turbidity (fnuP50) | vegetation share (grassPct) |
|---|---|---|
| class (9 levels) | 0.10 | 0.01 |
| region (6) | 0.25 | 0.11 |
| operator family (5) | 0.08 | 0.01 |
| regime (3) | 0.07 | 0.01 |
| class + region | 0.31 | 0.12 |

Single morphometric features are weak (Spearman with turbidity: area +0.17, depth -0.14, SDI +0.15, latitude -0.35; with vegetation share every feature within +-0.12). Medians by region: turbidity GP 5.1 FNU, MW 3.8, SE 2.9, W 1.6, NE 1.2, AK-HI 0.9. Small impoundments are the exception for vegetation (median grassPct 22 % vs 3-8 % for the other classes).

Conclusions: (a) the scheme adds a few points beyond region and is cheap, so it is worth keeping as a stratifier for transfer; (b) region must be part of every transfer design; (c) vegetation and clarity are lake-specific and should remain measured; (d) the class is best used to choose comparable lakes (section 3.5), not to predict habitat directly.

### 3.5 Pilot coverage and the transfer slots (Track 10 evidence)

Pilot coverage today: classes R1 (4 pilots) and R3 (1); region SE only; operators TVA and USACE; share of classifiable fleet lakes in a pilot class 23 % (137 of 597); share in the pilot region 24 % (146 of 621). Using a lake-distance (RMS of standardised log area, log residence time, log mean depth, log SDI, plus 0.5 for a different regime, 0.4 region, 0.25 operator family; 597 classifiable lakes):

| Pilot set | mean nearest-pilot distance | within 0.75 | within 1.0 | within 1.25 |
|---|---|---|---|---|
| 5 pilots | 1.88 | 10 % | 17 % | 25 % |
| 5 pilots + 10 slot picks below | 0.91 | 37 % | 62 % | 82 % |
| 5 pilots + 10 random lakes (200 draws) | 1.03 | n/a | 50 % (95th pct 57 %) | n/a |
| 5 pilots + 10 greedy k-medoid picks (data-unconstrained optimum) | 0.83 | 45 % | 71 % | n/a |

The four TN pilots count as one hydraulic system (2.4), so the effective pilot count is two (TN chain, Hartwell).

**Recommended minimal type slots** (12 slots; S01 and S03 are already covered by the pilots; the first two candidates per slot are the lakes closest to the slot's centre (medoids) among lakes with at least 3-5 public-data flags: CWMS or TVA feed, USGS gauge, dedicated API, HydroLAKES and NID name matches, a polygon within 0.7 of the reference area, and a CWMS storage/pool pair; alternatives with a measured stage-area curve are added where they exist). Candidates are suggestions for the pilot-selection decision, not lake claims.

| Slot | Type | Fleet lakes | Candidate lakes | Why this slot |
|---|---|---|---|---|
| S01 | Run-of-river hydropower pool, SE mainstem, TVA | 8 | pilots Guntersville, Wheeler, Wilson, Pickwick (others: Chickamauga, Fort Loudoun) | covered |
| S02 | Run-of-river / low-head pool, non-TVA operator | 38 | Lake Wateree SC, Jordan AL; CWMS-fed alternatives Dardanelle AR, Lake Hudson OK (measured stage-area curve) | tests transfer across operator and basin |
| S03 | Deep dendritic Piedmont/Appalachian storage | 41 | pilot Hartwell; add Cave Run KY (measured curve) or Norfork AR | second storage lake with a different operator or basin (Hartwell, Russell and Thurmond are one cascade, 2.4) |
| S04 | Dendritic Ozark / interior-highland storage | 33 | Stockton MO, Broken Bow OK | deep clear storage outside the SE |
| S05 | Shallow open-basin plains flood-control reservoir | 22 | Sardis OK (measured curve), El Dorado KS (measured curve), Lake Darling ND | turbid, large pool swings, the largest block of the fleet |
| S06 | Western storage reservoir with large drawdown | 68 | Starvation UT (measured curve), Blue Mesa CO (measured curve), Heron NM | steep shores, snowmelt regime, USBR |
| S07 | Flow-through reservoir, 30-180 d | 49 | Allatoona GA, Millwood AR | intermediate flushing |
| S08 | Dam-raised natural lake, NE glacial | 49 | Massabesic NH, Sunapee NH | outlet-dam lakes, state data |
| S09 | Regulated natural lake, Upper Midwest | 26 | Lake Mendota WI, Houghton Lake MI | managed outlets, shallow, vegetated |
| S10 | Natural deep lake, no dam | 44 | Yellowstone WY, Clear Lake CA | negative control for pool-management features |
| S11 | Natural shallow vegetated lake | 34 | Eagle Lake MS, Crescent Lake FL (Istokpoga FL is also in the class) | the dam-free vegetated-flat archetype |
| S12 | Small impoundment (< 2 km2) | 40 | Highland Lake CT, Mansfield Hollow CT | high count, low data per lake |

Per-slot details and the unconstrained greedy order are in `data/transfer_slots.json`. A pilot set that satisfies the filter would add roughly one lake for each of S02, S04, S05, S06, S07, S08, S09, S10, S11 and S12 (10 lakes) and one more storage lake for S03; slots S04-S07 can reuse CWMS series and the stage-area truth built in Track 7.

### 3.6 Classification: low-value items

Great Lakes and bays (18 very large lakes) are not modelled as lakes; HydroLAKES `Lake_type` alone; GLOBathy maximum depth; any attempt to predict vegetation or clarity from class; elevation as a standalone feature; classifying the 22 polygon-less lakes before their geometry is fixed.

## 4. Track 7: shallow-water and backwater context

### 4.1 Candidate datasets and verdicts

| Dataset | What it gives | Result | Verdict |
|---|---|---|---|
| 3DEP DEM (ImageServer getSamples, 1 m lidar where available) | shoreline slope and horizontal run per vertical foot | sampled 4 offsets x about 700 points per lake for 56 lakes; validated in 4.3 | **integrate** (static feature) |
| USACE CWMS storage + pool elevation | measured stage-area slope near full pool | 53 projects matched to 52 directory polygons (SWT 11, LRL 15, SPK 10, MVK 7, SAM 3, SAS 3, NAB 3, SPL 1; 74 more with Stor+Elev under office NWDM were not processed) | **integrate** for CWMS lakes; also the validation truth |
| Water Clarity `grassPct` (production) | measured vegetated-shallows share, 566 lakes | already published per pass | **integrate** (consume, do not rebuild) |
| Polygon shore bands and narrow-water fractions | littoral share, coves/arms | 599 lakes, free | **integrate** |
| GLOBathy (modeled bathymetry) | Dmax, A(h) power law | Dmax 46 m for Guntersville vs about 20 m real; relative area change per foot Spearman 0.33 vs truth | low value |
| JRC Global Surface Water v1.4 (tile 90W_40N, 82 MB) | occurrence, seasonality | fluctuating share inside the polygon: Guntersville 0.56, Hartwell 0.38, Pickwick 0.33, Wheeler 0.30, Wilson 0.16 | screen only (confounded) |
| NWI (Esri mirror; FWS service is down) | aquatic bed, littoral (L2), palustrine fringe | aquatic bed Guntersville 10.6 % and about 0 elsewhere; L2 share is mapped on 15 % of Guntersville/Wheeler but 0.1-2.4 % of the others | aquatic bed informative, L2 not comparable |
| NHDPlus HR flowline mouths (>= 5 km2) | tributary mouths per shore km | 0.039, 0.055, 0.054, 0.048, 0.031 (Guntersville, Wheeler, Wilson, Pickwick, Hartwell) | low value (no discrimination); arms in the polygon do the job |
| State/TWDB surveys, NOAA NCEI, topobathy lidar | real bathymetry | TWDB covers 15 Texas lakes; NCEI/topobathy are coastal and Great Lakes | not pursued (ledger leads) |

### 4.2 Proxies computed for the pilots

| Lake | shore slope 10-60 m (median, degrees) | share of shore under 2 degrees | share over 8 degrees | median run per vertical ft | GSW fluctuating share | NWI aquatic bed | NWI fringe km2 per shore km | S2 grassPct | share of area within 100 m of shore | narrow-water share (< 300 m) | GLOBathy area < 1.2 m |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Guntersville | 1.3 | 0.59 | 0.16 | 45 | 0.56 | 0.106 | 0.0093 | 23.1 | 0.35 | 0.14 | 0.09 |
| Wheeler | 1.1 | 0.62 | 0.09 | 52 | 0.30 | 0.001 | 0.0285 | 5.8 | 0.30 | 0.13 | 0.08 |
| Wilson | 8.0 | 0.21 | 0.50 | 7 | 0.16 | 0.000 | 0.0067 | 1.6 | 0.22 | 0.11 | 0.09 |
| Pickwick | 3.9 | 0.41 | 0.38 | 15 | 0.33 | 0.000 | 0.0221 | 2.0 | 0.26 | 0.08 | 0.12 |
| Hartwell | 6.3 | 0.17 | 0.34 | 9 | 0.38 | 0.000 | 0.0009 | 6.4 | 0.46 | 0.23 | 0.10 |

Reading, from a bowfishing viewpoint:

* **Guntersville and Wheeler are flat-shored and shallow-edged** (median 1.1-1.3 degrees, about 60 % of the shoreline under 2 degrees, so each foot of pool change moves the waterline tens of feet); **Wilson and Hartwell are steep** (6-8 degrees) and **Pickwick sits in between**. Predicted surface change per foot of pool, using the validated proxy: Guntersville 6.5 % of its surface (about 4,300 acres), Wheeler 7.2 % (3,800 acres), Pickwick 1.6 % (560 acres), Hartwell 1.7 % (590 acres; measured 1.66 %), Wilson 0.8 % (120 acres). Wilson has the least exposure per foot and also the least vegetation (Water Clarity grass share 1.6 %).
* **Vegetated shallows:** the satellite grass share (Guntersville 23 %, others 1.6-6.4 %) and NWI aquatic bed (Guntersville 10.6 %, others about 0) agree on the one lake known for dense aquatic beds. JRC occurrence ranks Guntersville first too, but it also puts Hartwell (0.38) above Pickwick (0.33) and Wheeler (0.30) although Hartwell is the steep, least-vegetated of the three by every other proxy, so it is treated as a confounded screen.
* **Arms and coves:** Hartwell has the largest share of narrow water (0.23) and of area within 100 m of shore (0.46), the TN lakes 0.08-0.14; GLOBathy's shallow fraction is nearly flat across lakes (0.08-0.12) and cannot distinguish Guntersville's flats from Wilson's gorge. NWI wetland fringe per shore km is highest at Wheeler (0.029) and lowest at Hartwell (0.0009), consistent with Piedmont versus floodplain geology.

### 4.3 Validation: can cheap proxies predict littoral exposure?

Truth: for each USACE project with both daily pool elevation and daily storage in CWMS, a quadratic fit of storage on pool level over the top 15 ft below the 95th-percentile pool gives surface area A_ref (acre) and its slope dA/dz (acre per ft); `rel_per_ft = dA/dz / A_ref` is the share of the surface gained per foot of rise. The 53 matched pairs gave 41 fits (the rest had under 300 days in the top 15 ft or a range under 5 ft); fits with R2 below 0.9 and unit mismatches (Lake Tahoe) were excluded: n = 33 lakes with pool series of 1.4 to 36 years.

Predictors (none uses bathymetry): `P_shape` = perimeter / area; `P_dem` = perimeter x median horizontal run per vertical foot (from 3DEP slope between 10 and 60 m outside the shoreline) / area; `P_glob` = b / (Dmax in ft) from GLOBathy's power law; `P_slope` = median slope alone.

| Predictor | Spearman vs truth | log-Pearson | log10 RMSE | within a factor of 2 |
|---|---|---|---|---|
| shape only (perimeter / area) | -0.16 | -0.17 | n/a | n/a |
| **3DEP shoreline slope (P_dem)** | **0.76** | **0.84** | **0.22** | **82 %** |
| slope alone | 0.73 | n/a | n/a | n/a |
| GLOBathy | 0.33 | 0.24 | 0.41 | 48 % |
| constant (median truth, 0.0231 per ft) | n/a | n/a | 0.33 | 76 % |

Rank-regression R2: shape only 0.03, shape plus slope 0.61. The truth spans a narrow range (10th-90th percentile 0.0056-0.0327 per ft, medians 0.0231), so the constant is a hard baseline for the absolute error; the shoreline-slope proxy beats it on error and, more importantly, ranks lakes correctly: steep western reservoirs (Don Pedro 0.0044, Blue Mesa 0.0045, Folsom 0.0055, Jordanelle 0.0060) are separated from the flat plains lakes (Eufaula 0.025, Texoma 0.033, Caddo 0.11, El Dorado 0.043). The Southeast storage lakes land where predicted: Hartwell 0.0174 vs 0.0166, Thurmond 0.0257 vs 0.0249, Russell 0.0241 vs 0.0184. Failure cases: Enid (0.138 predicted vs 0.027) and Caddo (0.24 vs 0.11), where the DEM beside the polygon is flat wetland; Sardis OK (0.037 vs 0.0095); Texoma (0.016 vs 0.033).

Limits stated honestly:

* The DEM stores a flat water surface. The proxy describes the bank **above** the current waterline, so it predicts the response to a rise and to a small drawdown that re-exposes recently flooded ground; it does not see the bottom profile that is exposed in deep drawdowns.
* The truth is area change per foot near full pool, not depth distribution. It says how much flats appear or disappear, not whether fish use them.
* Sample is USACE reservoirs (Plains, Ozarks, Midwest, California, a few SE). No TVA lake has truth because TVA publishes no storage series.
* 7-25 % of sampled outward slopes in the pilots are negative (the DEM beside the polygon edge is lower than at 10 m), a polygon-edge or lidar-water artefact; medians are used for that reason.

### 4.4 Recommendation (and what not to build)

1. **Integrate (static, one-time per lake):** 3DEP shoreline slope index (median slope, share under 2 degrees, run per foot, predicted `rel_per_ft`), polygon shore-band and narrow-water fractions, and the Water Clarity `grassPct` already in production. Cost: about 1 min of DEM sampling per lake (the fleet of 599 is about 10 hours at one request per second, or 3 hours with three workers), plus nothing for polygon features.
2. **Integrate where it exists:** CWMS-derived stage-area slope for CWMS lakes (177 directory lakes carry a CWMS office; 163 projects with both storage and pool series found across nine offices, 53 matched to directory polygons) as measured truth, replacing the proxy.
3. **Do not build:** lake-wide bathymetry projects, GLOBathy depth features, JRC- or NWI-derived "shallow" scores, tributary-mouth counts, a satellite hypsometry pipeline. They either did not discriminate between pilots, were not comparable across lakes, or duplicated the polygon. A satellite hypsometry (water extent per pass paired with pool level) was not built: the Water Clarity pipeline stores percentages (`measuredPct`, `grassPct`), not wet area per pass, so it would be new processing, and the DEM proxy already reaches Spearman 0.76 against measured curves. NLCD wetland classes were not tested; NWI already shows the wetland-fringe signal is geology-driven and available only where mapped.
4. **Pre-registered next test (cheap):** repeat the validation on the 74 Stor+Elev locations under CWMS office `NWDM` and report whether the Spearman holds on lakes not used here; do not use the proxy as a binding or score input until it does.

## 5. Blockers and actions

| ID | Item | Status |
|---|---|---|
| B-context-001 | USACE NID API 403 | worked around (Esri mirror) |
| B-context-002 | StreamStats legacy decommissioned | worked around |
| B-context-003 | FWS NWI MapServer HTTP 500 | worked around (Esri mirror) |
| B-context-004 | no bathymetry / stage-area at scale | worked around (CWMS pairs + DEM proxy), no Michael action |
| B-context-005 | TVA release history and tailwater discharge | OPEN, **M-ctx-01** (approve extending the existing TVA archiver from 5 to 16 dams; a deploy) |
| B-context-006 | USGS OGC API needs a key | worked around, optional **M-ctx-02** |
| B-context-007 | polygon accuracy for about 40 lakes | worked around, handed to the geometry thread |

## 6. Files and reproducibility

| Item | Path |
|---|---|
| Features for all lakes | `docs/research/lake-brain/data/lake_features.csv` (621 rows, 43 columns), `lake_features_summary.json` |
| Transfer slots and coverage | `data/transfer_slots.json`, `data/class_eval.json`, `data/hypso_validation.json` |
| Scripts | `research/lake-brain/context_features.py` (build), `context_geom.py`, `context_join.py`, `context_fetch_nid.py`, `context_erom.py`, `context_chain.py`, `context_transfer.py`, `context_class_eval.py`, `context_shore_dem.py`, `context_gsw.py`, `context_nwi.py`, `context_tribs.py`, `context_hypso_validate.py`, `context_hypso_truth.py`, `context_hypso_eval.py`, `context_hypso_cwms.py` |
| Bulk data (never in Git) | `~/Desktop/Development/Sector_Research_Data/lake-brain/context/` with retention rows in `MANIFEST.jsonl` |
| Order | fetch NID and HydroLAKES, `context_geom.py`, `context_join.py`, `context_erom.py`, `context_chain.py`, `context_features.py`, `context_transfer.py`, `context_class_eval.py`; Track 7: `context_shore_dem.py`, `context_hypso_validate.py`, `context_hypso_truth.py`, `context_hypso_eval.py` |
