# Depth Brain - measured bathymetry source scout (2026-10-13)

Scope: research only. No production code, Brain, or deploy touched. Raw data lives outside git at
`~/Desktop/Development/Sector_Research_Data/depth-brain/sources/` (about 4.6 GB). Machine ledger:
`ledger/sources.jsonl` (40 records, ids S-depth-001..040). Candidate fleet matches: `fleet_candidate_matches.csv`.
Validation shortlist (46 lakes): `validation_truth_shortlist.csv` (same table below).

Authority tier scale used in the ledger (1 best): 1 modern instrument survey by owner/USGS with raster/points; 2 agency instrument survey contours;
3 state agency contours of mixed vintage; 4 digitized legacy maps / third-party hosted; 5 max-depth-only anchor; 6 modeled/derived; 7 unusable/unknown.

## Headline

* 26 ledger records are **ACCEPTED** (10 LEAD, 4 DEAD_END). About 20 statewide/multi-lake REST services were fully downloaded as GeoJSON (EPSG:4326; IL pull incomplete), plus 4 TWDB shapefile packages, 9 MGS sounding zips, USGS inventory v4 and the EPA NLA 2007 CSV.
* Fleet coverage (name+state, **candidate matches only**, none hand-verified): **136 of 621 lakes** have a contour/point survey candidate by name; **158** if the 22 lakes matched only by location (KS 12, FL 9, IL 1) are included. **262 of 621** have at least one candidate of any kind once max-depth-only anchors (NLA 2007, OWRB, MI IFR, ND) are counted (EPA NLA alone: 109).
* Strongest scalable sources: MN DNR (46k contours, ~1,900 lakes), Michigan DNR/IFR (25k lines, 1,482 groups; completeness issues), Montana FWP (25k lines), WV DNR (53k lines incl. 11 Corps lakes), Massachusetts MassWildlife (28k), Florida FWC (24k 1-ft contours, hydroacoustic), Indiana DNR (10k), Nebraska NGPC (6k, USBR/NGPC joint program), Ohio DOW (2.8k, 134 lakes), CT DEEP (7.5k), NH GRANIT (9k), TWDB (123 reservoirs with shapefiles), USGS ScienceBase releases + USGS Inland Bathy Inventory v4 (314 survey footprints).
* Not found (see Dead ends): any public GIS for AL, GA (large reservoirs), SC, NC, KY (beyond USGS), VA, LA, MS, MO (beyond USGS), AR (beyond USGS), IA, SD, CO, WY, NM, AZ, NV, OR, ID, CA, NY, PA, DE, RI, VT, ME. Web search budget ran out mid-scout, so "not found" is not proof of absence.

## Fleet coverage by state (strict name-based, contour/survey sources only)

AR 3, CT 11, ID 2, IN 3, KY 1, MA 7, MD 6, MI 8, MN 10, MO 2, MT 7, ND 3, NE 10, NH 11, NJ 2, NV 1, OH 11, OK 6, PA 1, TX 11, UT 4, WA 4, WI 1, WV 11. States with **zero** candidates from contour/survey sources after this pass (max-depth anchors may still exist): AK, AL, AZ, CA, CO, DE, GA, HI, IA, LA, ME, MS, NC, NM, NY, OR, RI, SC, SD, TN, VA, VT, WY. Location-only matches (weak): FL 9, IL 1, KS 12.

## Source table (decision, authority, reachable)

| id | source | type | fleet cands | local copy | decision / auth |
|---|---|---|---|---|---|
| S-depth-001 | TWDB volumetric surveys | contours/TIN/raster | 12 | twdb_shapefiles (4 zips) | ACCEPTED / 1 |
| S-depth-002 | MN DNR lake bathymetry (REST) | contours+DEM | 10 | mn_dnr (3 GeoJSON, 536 MB) | ACCEPTED / 3 |
| S-depth-003 | Indiana DNR Lake_Bathymetry | contours | 2 (+blank-name lines) | in_dnr | ACCEPTED / 3 |
| S-depth-004 | Montana FWP Lakes Bathymetry | contours | 6 | mt_fwp | ACCEPTED / 3 |
| S-depth-005 | Nebraska NGPC Lake Contours | contours | 10 | ne_ngpc | ACCEPTED / 2 |
| S-depth-006 | ND Game & Fish contours | contours | 3 | nd_gnf | ACCEPTED / 3 |
| S-depth-007 | NH GRANIT/NHDES | contours | 11 | nh_des | ACCEPTED / 2 |
| S-depth-008 | WA Ecology | contours (legacy USGS maps) | 4 | wa_ecy | ACCEPTED / 4 |
| S-depth-009 | MI DNR/IFR inland lake contours | band contours (digitized) | 8 | mi_dnr_contours | ACCEPTED / 4 (partial lakes) |
| S-depth-010 | MassWildlife inland bathymetry | contours | 7 | ma_masswildlife | ACCEPTED / 3 |
| S-depth-011 | Kansas KBS BathymetryContour | contours (no names) | 12 spatial | ks_kbs | ACCEPTED / 2 |
| S-depth-012 | FWC select Florida lakes (1 ft) | contours (no names) | 9 spatial | fl_fwc (512 MB) | ACCEPTED / 1 (do not redistribute) |
| S-depth-013 | OWRB LOK contours | contours | 5 | ok_owrb | ACCEPTED / 2 |
| S-depth-014 | Illinois DNR lake depth | contours (no names) | 1 spatial | il_idnr (partial pull) | ACCEPTED / 2 |
| S-depth-015 | Ohio DOW lake bathymetry | contours | 11 | oh_dow | ACCEPTED / 3 |
| S-depth-016 | TWRA small-lake contours | contours | 0 | tn_twra | LEAD / 3 |
| S-depth-017 | WV DNR public fishing lake contours | dense contours | 11 | wv_dnr | ACCEPTED / 2 |
| S-depth-018 | NJDEP lake bathymetry | contours (m) | 2 | nj_dep | ACCEPTED / 3 |
| S-depth-019 | CT DEEP lake bathymetry | contours | 11 | ct_deep | ACCEPTED / 3 |
| S-depth-020 | USGS Inland Bathy Inventory v4 | index of 314 surveys | 24 | usgs_sciencebase/inventory_v4 | ACCEPTED / 1 |
| S-depth-021..023 | OWRB / MI IFR / ND max-depth points | max depth | 11 / 9 / 1 | ok_owrb, mi_ifr, nd_gnf | ACCEPTED / 5 |
| S-depth-024 | USGS ScienceBase per-reservoir releases (356-item harvest) | points/DEM/contours | 16 | catalog json only | ACCEPTED / 1 (not downloaded) |
| S-depth-025 | Maryland Geological Survey soundings | points | 6 | md_mgs (9 zips) | ACCEPTED / 1 |
| S-depth-026 | GLOBathy 30 m | MODELED | all HydroLAKES | not downloaded (16.7 GB) | LEAD / 6 |
| S-depth-027 | 3D-LAKES (ICESat-2) | derived | ? | unreachable (zenodo HTTP 000) | LEAD / 6 |
| S-depth-028 | UMN hypsography MN/WI/SD readme | digitized hypsometry | ? | not located | LEAD / 4 |
| S-depth-029 | Wisconsin DNR GIS | none found | 0 | - | DEAD_END |
| S-depth-030 | NOAA NCEI Great Lakes bathymetry | open-lake grid | ~10 | - | LEAD / 5 |
| S-depth-031 | USGS Great Lakes seamless topobathy DEM | raster | ~10 | - | LEAD / 1 |
| S-depth-032 | USGS 3DEP/TNM topobathy | lidar | ? | - | LEAD / 2 |
| S-depth-033 | Chippewa/Harveys/Utah Lake contours | contours | 3 | misc_ago | ACCEPTED / 4 |
| S-depth-034 | SJRWMD soundings | points | ? | - | LEAD / 1 |
| S-depth-035 | Georgia PFA bathymetry | contours (no names) | 0 | - | LEAD / 3 |
| S-depth-036 | USACE CWMS data API | time series only | 0 | - | DEAD_END |
| S-depth-037 | TVA bathymetry | not public | 0 | - | DEAD_END |
| S-depth-038 | USBR RISE | unreachable (HTTP 000) | ? | - | LEAD |
| S-depth-039 | EPA NLA 2007 DEPTHMAX | max depth at index site | 109 | epa_nla | ACCEPTED / 5 |
| S-depth-040 | Remaining state agencies not located | - | 0 | - | DEAD_END (search exhausted) |

## Key findings and cautions

1. **Statewide REST services are the scalable path.** Everything downloaded used anonymous ArcGIS REST queries (objectId-chunked, f=geojson). Reusable script pattern: query `returnIdsOnly`, then POST `objectIds` in chunks of 100-500 with `outSR=4326`. The ArcGIS Online sharing search (`https://www.arcgis.com/sharing/rest/search?q=...&f=json`) returned 561 hits for "lake bathymetry contours" and is the best way to find more state services (catalog saved at `sources/ago_bathy_catalog.json`).
2. **Completeness varies inside a dataset.** MN: Rainy Lake contours only to -15 ft, Mille Lacs -40 ft (fine, true max ~42) but Rainy is partial. MI: Higgins Lake and Torch Lake show only 0-5 ft bands though IFR max-depth points say 130/250 ft. WA: legacy 1960s digitization (Lake Chelan steps of 100 ft). Always compare contour max vs a max-depth anchor (S-depth-021/022/039) before treating a lake as full truth.
3. **Datums/units differ**: MN depth is negative feet (and DEM in feet); OWRB negative feet; NJ metres; NE/MT/NH positive feet; TWDB shapefiles in state plane NAD83 with elevation datums (NGVD29 vs NAVD88 in older surveys); MGS UTM18N metres + depth in feet. KS/FL/IL contours have no lake-name attribute (spatial join required).
4. **Name collisions**: many fleet names are generic (Indian Lake OH/NY, Gull Lake MI/MN, Bear Lake, Clear Lake, Grand Lake LA/OK/OH). Matches here use name+state (and location where available); treat as `candidate` until a human checks a few.
5. **Spatial-only matches are weak** (KS 12, FL 9): fleet point within ~3 km of any contour line; no check that the contours belong to that lake.
6. **Redistribution**: FL FWC metadata says the data should not be distributed; keep internal. TWDB says maps are not for navigation or fishing; none of this data should be shipped to app users as raw contours without license review.
7. **ScienceBase API quirk**: `www.sciencebase.gov/catalog/items?...` redirects to SSO login unless the request carries `Accept: application/json`.
8. **USGS inventory** polygons for coastal-plain/river projects are enormous boxes; do not use them for location matching.
9. **IL pull incomplete**: IDNR reports 4,828 contour lines but the ids query returned 3,402; re-pull (smaller page, retry) before relying on it. KS contours have no pagination support: pull by objectIds (done).
10. **Great Lakes / bowfishing relevance**: NCEI 3 arc-second and USGS seamless topobathy cover open lake and nearshore; shallow bays (Green Bay, Saginaw Bay, Lake St. Clair flats, Erie western basin) are the bowfishing targets and need topobathy/3DEP lidar or state surveys. Not downloaded here (files 0.5-14 GB).
11. **Max-depth ground truth**: EPA NLA 2007 DEPTHMAX is index-site depth (not guaranteed lake max); OWRB depth_max is a regulator-reported value. Both useful for scoring GLOBathy-style priors.

## Validation-truth shortlist (46 lakes, none on the Tennessee River chain)

Types covered: natural deep/shallow, run-of-river, dammed reservoir, complex multi-arm, repeat-survey. Paths are under `~/Desktop/Development/Sector_Research_Data/depth-brain/sources/` and are local, outside git.

| lake | type | source | path | filter | caution |
|---|---|---|---|---|---|
| Lake Texoma (TX) | reservoir / complex arms (Red R. + Washita) | S-depth-001 | `twdb_shapefiles/Texoma_2002-07.zip` | Tex_cont_5.shp (5-ft), Tex_pts.shp points | 2002 survey; Cumberland Pool included; shapefiles in TX/OK state plane |
| Lake Eufaula (OK) | reservoir / complex arms (3 rivers) | S-depth-001 | `twdb_shapefiles/Eufaula_OK_2004-06.zip` | Euf_cont_2.shp, Euf_cont_5.shp, XYZeuf_pts.shp | 2004 survey; several pool elevations (585-590 ft) |
| Canyon Lake (TX) | deep clear Hill Country reservoir | S-depth-001 | `twdb_shapefiles/Canyon_2001-11.zip` | recalculated 2016 shapefiles | 209 MB; 2001 survey recalculated 2016 |
| Lake Tawakoni (TX) | shallow-ish flat Texas reservoir | S-depth-001 | `twdb_shapefiles/tawakoni_2009-08.zip` | contour + points | 2009 survey; 280 MB |
| Grand Lake o' the Cherokees (OK) | large reservoir / complex arms | S-depth-013 | `ok_owrb/ok_owrb_contours.geojson` | lake=='Grand' (27 lines, 5-ft step to -130 ft) | OWRB 2009; also USGS release ScienceBase 5e4c001fe4b0ff554f6c6531 |
| Lake Hudson (OK) | run-of-river hydro impoundment (Grand R.) | S-depth-013 | `ok_owrb/ok_owrb_contours.geojson` | lake=='Hudson' (13 lines, 5-ft step) | Max about -60 ft |
| Sardis Lake (OK) | small/mid reservoir | S-depth-013 | `ok_owrb/ok_owrb_contours.geojson` | lake=='Sardis' (5 lines) | Coarse (10 ft step) |
| Lake McConaughy (NE) | large western reservoir | S-depth-005 | `ne_ngpc/ne_lake_contours.geojson` | Name=='Lake McConaughy' (87 lines, 5 ft step to 160 ft) | Large drawdown swings; check Elevation field vs pool |
| Calamus Reservoir (NE) | sandhills reservoir with shallow flats | S-depth-005 | `ne_ngpc/ne_lake_contours.geojson` | Name=='Calamus Reservoir' (140 lines, 3 ft step) |  |
| Merritt Reservoir (NE) | canyon reservoir | S-depth-005 | `ne_ngpc/ne_lake_contours.geojson` | Name=='Merritt Reservoir' (278 lines, 10 ft step) |  |
| Harlan County Lake (NE) | broad shallow Corps reservoir | S-depth-005 | `ne_ngpc/ne_lake_contours.geojson` | Name=='Harlan County Lake' (124 lines, 5 ft step to 45) | good shallow-flats test |
| Lake Ogallala (NE) | small sandy reservoir below McConaughy | S-depth-005 | `ne_ngpc/ne_lake_contours.geojson` | Name=='Lake Ogallala' (131 lines, 2 ft step) | dense 2-ft contours: best for flats |
| Tiber Reservoir (Lake Elwell) (MT) | Reclamation prairie reservoir | S-depth-004 | `mt_fwp/mt_lakes_bathymetry.geojson` | LAKENAME=='Tiber Reservoir' (7,583 lines, 10 ft step) | very dense lines; check SOURCE attr |
| Hebgen Lake (MT) | mountain reservoir (natural + dam raise) | S-depth-004 | `mt_fwp/mt_lakes_bathymetry.geojson` | LAKENAME=='Hebgen Lake' (17 lines, 5 ft step) |  |
| Georgetown Lake (MT) | shallow natural-ish reservoir | S-depth-004 | `mt_fwp/mt_lakes_bathymetry.geojson` | LAKENAME=='Georgetown Lake' (7 lines to 25 ft) | shallow-lake test |
| Flathead Lake (MT) | large natural lake, deep | S-depth-004 | `mt_fwp/mt_lakes_bathymetry.geojson` | LAKENAME=='FLATHEAD LAKE' (224 lines to 380 ft) |  |
| Leech Lake (MN) | large natural lake, mixed basin | S-depth-002 | `mn_dnr/mn_bathy_contours.geojson` | lake_name=='Leech (Main Basin)' (142 lines, 10 ft step to -135) | main basin only; other bays are separate groups |
| Mille Lacs Lake (MN) | large shallow natural lake (max ~42 ft) | S-depth-002 | `mn_dnr/mn_bathy_contours.geojson` | lake_name=='Mille Lacs' (816 lines, 5 ft step to -40) | best shallow-big-lake test |
| Lake Winnibigoshish (MN) | shallow flowage-type natural lake / Corps dam | S-depth-002 | `mn_dnr/mn_bathy_contours.geojson` | lake_name=='Winnibigoshish' (107 lines, 5 ft step) | Mississippi headwater reservoir/natural |
| Otter Tail Lake (MN) | chain natural lake | S-depth-002 | `mn_dnr/mn_bathy_contours.geojson` | lake_name=='Otter Tail' (308 lines, 10 ft step) |  |
| Lake Pepin (MN) | run-of-river (Mississippi Pool 4) | S-depth-002 | `mn_dnr/mn_bathy_contours.geojson` | lake_name=='Pepin' (33 lines, 10 ft step to -50) | river channel + navigation pool; also USGS Pool 4 survey in inventory |
| Lake Minnetonka (MN) | complex multi-bay suburban lake | S-depth-002 | `mn_dnr/mn_bathy_contours.geojson` | lake_name=='Minnetonka' (518 lines) | many sub-bays |
| Houghton Lake (MI) | very shallow natural lake (max 21 ft) | S-depth-009 | `mi_dnr_contours/mi_inland_lake_contours.geojson` | Name=='Houghton Lake' (72 lines, 1 ft step) | max depth 21 ft confirmed by S-depth-022 point |
| Gull Lake (MI) | mid-depth natural | S-depth-009 | `mi_dnr_contours/mi_inland_lake_contours.geojson` | Name=='Gull Lake' (34 lines to 110 ft) | max 110 ft matches S-depth-022 |
| Burt Lake (MI) | large shallow-shelf natural | S-depth-009 | `mi_dnr_contours/mi_inland_lake_contours.geojson` | Name=='Burt Lake' (12 lines to 73) |  |
| Lake Winnipesaukee (NH) | large complex island lake | S-depth-007 | `nh_des/nh_bathy_lines.geojson` | LAKE=='WINNIPESAUKEE' (270 lines) | 20-ft interval |
| Umbagog Lake (NH) | shallow border lake / dam-controlled | S-depth-007 | `nh_des/nh_bathy_lines.geojson` | LAKE=='UMBAGOG LAKE' (137 lines to 45) |  |
| Massabesic Lake (NH) | reservoir | S-depth-007 | `nh_des/nh_bathy_lines.geojson` | LAKE=='MASSABESIC LAKE' (265 lines) |  |
| Candlewood Lake (CT) | pumped-storage reservoir | S-depth-019 | `ct_deep/ct_lake_bathy_lines.geojson` | WBNAME=='Candlewood Lake' (521 lines) | check METHOD/DATADATE |
| Wachusett Reservoir (MA) | water supply reservoir | S-depth-010 | `ma_masswildlife/ma_inland_bathy.geojson` | NAME=='Wachusett Reservoir' (287 lines, 10 ft) |  |
| Pontoosuc Lake (MA) | shallow reservoir (max 35 ft) | S-depth-010 | `ma_masswildlife/ma_inland_bathy.geojson` | NAME=='Pontoosuc Lake' (151 lines, 1 ft step) | 1-ft contours for flats |
| Buckeye Lake (OH) | shallow flood-control/canal lake | S-depth-015 | `oh_dow/oh_dow_lake_bathymetry.geojson` | LAKE_NAME=='BUCKEYE LAKE' (47 lines) |  |
| Indian Lake (OH) | shallow reservoir | S-depth-015 | `oh_dow/oh_dow_lake_bathymetry.geojson` | LAKE_NAME=='INDIAN LAKE' (116 lines) | do not confuse with Indian Lake|NY |
| Alum Creek Lake (OH) | Corps reservoir | S-depth-015 | `oh_dow/oh_dow_lake_bathymetry.geojson` | LAKE_NAME=='ALUM CREEK LAKE' (93 lines) |  |
| Summersville Lake (WV) | deep Corps reservoir | S-depth-017 | `wv_dnr/wv_pfl_contours.geojson` | LakeName=='Summersville Lake' (8,864 lines) | dense lines |
| Stonewall Jackson Lake (WV) | dendritic multi-arm reservoir | S-depth-017 | `wv_dnr/wv_pfl_contours.geojson` | LakeName=='Stonewall Jackson Lake' (7,607 lines) | best complex-arm test |
| Cheat Lake (WV) | run-of-river hydro impoundment | S-depth-017 | `wv_dnr/wv_pfl_contours.geojson` | LakeName=='Cheat Lake' (1,927 lines) |  |
| Moses Lake (WA) | shallow desert lake (max 36 ft) | S-depth-008 | `wa_ecy/wa_ecy_lake_bathy_lines.geojson` | GNIS_Name=='Moses Lake' (28 lines, 6 ft step) | legacy digitized |
| Lake Wawasee (IN) | natural kettle lake | S-depth-003 | `in_dnr/in_lake_bathy_contours.geojson` | lake_name=='Lake Wawasee' (209 lines, 5 ft step) |  |
| Orange Lake (FL) | very shallow Florida lake | S-depth-012 | `fl_fwc/fl_fwc_select_lakes_bathy.geojson` | spatial: features within ~3 km of fleet point (34) | no name field |
| Istokpoga (FL) | shallow Florida lake (max ~12 ft) | S-depth-012 | `fl_fwc/fl_fwc_select_lakes_bathy.geojson` | spatial join (45 features) | no name field |
| Lochloosa (FL) | shallow natural lake | S-depth-012 | `fl_fwc/fl_fwc_select_lakes_bathy.geojson` | spatial join (37 features) |  |
| Deep Creek Lake (MD) | hydro reservoir | S-depth-025 | `md_mgs/DeepCreekLake2012.zip` | CSV sounding points (2012) | UTM18N m, depth ft |
| Triadelphia Reservoir (MD) | water-supply reservoir, repeat surveys | S-depth-025 | `md_mgs/triadelphia2006.zip + triadelphia2015.zip` | CSV points | enables change-detection check |
| Table Rock Lake (MO) | large Ozark reservoir (points) | S-depth-024 | `(not downloaded) https://www.sciencebase.gov/catalog/item/62b4d245d34e8f4977cbd09f` | TableRockLake2020_bathy_pts.zip (211 MB) | download on demand |
| Beaver (AR) | Ozark reservoir | S-depth-024 | `(not downloaded) https://www.sciencebase.gov/catalog/item/5da872cbe4b09fd3b0c9c574` | USGS 2018 bathymetric data | download on demand |

## Downloaded inventory (path, size)

mn_dnr 536 MB, fl_fwc 512 MB, ne_ngpc 378 MB, ma_masswildlife 373 MB, nd_gnf 305 MB, in_dnr 240 MB, mt_fwp 213 MB, nj_dep 209 MB, mi_dnr_contours 198 MB, usgs_sciencebase 183 MB (catalog + inventory v4), il_idnr 144 MB, ks_kbs 143 MB, ok_owrb 128 MB, nh_des 113 MB, md_mgs 102 MB, wv_dnr 96 MB, ct_deep 63 MB, oh_dow 62 MB, misc_ago 52 MB, wa_ecy 15 MB, tn_twra 1 MB, mi_ifr 1 MB, epa_nla 1 MB, twdb_shapefiles 573 MB (Texoma, Eufaula, Canyon, Tawakoni), ago_bathy_catalog.json 1.8 MB. Nothing was placed in git.

## Dead ends and unreachable hosts

* Wisconsin DNR: no inland-lake bathymetry GIS (PDF maps only). `data.dnr.wi.gov` and `opendata.dnr.mo.gov` did not respond (HTTP 000) from this host.
* zenodo.org and data.usbr.gov: HTTP 000 from this host (possible network block); retry elsewhere for 3D-LAKES and Reclamation RISE.
* MassGIS web page returned 403 to curl (ArcGIS server works). MN old `resources.gisdata.mn.gov/.../water_lake_bathymetry/` path 404 (the REST service replaced it).
* USACE CWMS API is reachable but time-series only. TVA bathymetry is not public. LakeATLAS/HydroLAKES carry no bathymetry; Lake-TopoCat is drainage topology (per paper summaries; not fetched).
* No audited source for GA/AL/SC/NC/VA/KY/LA/MS reservoirs. Ask USACE districts (Mobile, Savannah, Wilmington, Nashville, Mobile) and state agencies directly; Georgia Power/Duke/Dominion hold private surveys.

## Suggested next actions

1. Ingest S-depth-002..019 into a single `lake_contours` parquet with fields (source, lake_name, depth_ft, unit, survey_year) for the validation thread; spatial-join KS/FL/IL.
2. Re-pull IL; enumerate SJRWMD services (S-depth-034); locate the DRUM data file for S-depth-028 (WI/SD).
3. Pull USGS releases for Table Rock, Beaver, Norfork, Nimrod, Grand Lake, Koocanusa, Buckhorn (S-depth-024) on demand.
4. Retry zenodo/RISE from another network.
5. Complete a manual review of at least the 'exact' rows in `fleet_candidate_matches.csv` for three states before trusting counts.
