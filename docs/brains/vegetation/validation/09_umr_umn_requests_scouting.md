# Note 09 - UMR landcover, UMN Minnesota, and agency request scouting

Date: 2026-10-13. Offline research; nothing sent or submitted, no forms filled, no bot challenges bypassed. Total downloaded about 100 MB. New files are in MANIFEST.jsonl. Scripts: `experiments/adoption/umr/`.

## 0. Bottom line

| Item | Result |
|---|---|
| UMRS 2020 pool zips (ScienceBase 6102cbf7...) | **NOT obtained.** Files are S3-backed; the public download route needs a browser-session token (GraphQL returns UNAUTHENTICATED to plain HTTP, bulk "attached files" zip times out with Cloudflare 524). Metadata XML obtained, so the **schema is confirmed**. Manual steps in section 1.4. |
| Substitute UMRS polygons that DID download | **2015 Pool 5 drawdown LCU** (aerial 12 Aug 2015, 4,812 polygons, 5,469 ha, genus-level, same classification). Disk-stored on ScienceBase so plain HTTP works. |
| Surface-class schema | Confirmed. Rooted floating aquatics (Rf = lotus/water lily) and emergent marsh classes exist. Submersed (Sv) exists but is not surface-reaching. |
| Fleet overlap with UMR LTRM SAV CSV | Only **Lake Pepin MN** (779 site-years, 181 in 2015-2019). No Keokuk, no Illinois River lake, no other pool-type fleet lake in the registry. LTRM CSV is submersed taxa only: no surface labels. |
| Scoring | Done on Pool 5 (not a fleet lake). **S2 L2A does not exist in the Earth Search archive for 2015**, so per prereg this is `NO_SCENE`; the 2017/2018 results below are **labelled substitutes (2.9 and 3 years after the polygons)**. Headline: cell F1 0.95-0.97 vs open water, but see caveats. |
| UMN Minnesota dataset | **Obtained in full** (37 MB zip + readme + R script) via the public DSpace REST API. Has a point-level `SURFACE_GROWTH` flag, but it is NA/empty for all fleet-lake surveys; taxon lookup needed. Five MN fleet lakes have point coordinates. |
| Agencies | WI DNR: view-only app + email, no bulk PI export found. TVA: Cloudflare challenge on plain HTTP (dead end by rule). TPWD: no vegetation GIS, formal open-records channel. **SFWMD: Okeechobee and Kissimmee littoral vegetation polygons are openly downloadable ArcGIS feature services (2003-2016).** |

## 1. USGS UMRS land cover/use

### 1.1 What was obtained
- `sources/umrs_landcover/_meta/2020_LCU_UMRS.xml` (76 KB): FGDC metadata for the 2020 release (CC0, imagery 11-26 Aug 2020, mapped to 0.4 ha MMU above L&D 13 and 1.0 ha below; 0.2 m / 0.4 m aerial imagery; 4-band RGB+NIR).
- `sources/umrs_landcover/pool5_dd_2015/lc_2015_p5dd.zip` (23 MB, unzipped under `x/`): ScienceBase item 57750ae1e4b07dd077c70751, DOI 10.5066/F7CZ358G, EPSG:26915. Imagery 2015-08-12, 6 in/pixel true colour, stereo interpretation, same classification as 2000/2010/2020.
- Download of 2020 pool zips failed: `sciencebase.usgs.gov/manager/download/<cuid>` returns the SPA shell; `api.sciencebase.gov/graphql` returns "Incorrect authorization header"; `catalog/file/get/<item>` (all files) never answered within 15 min (524). I did not try to forge a token. 2010/11 pool items carry only WMS/WFS links and no files; they are not S2-era anyway.

### 1.2 Attribute schema and class definitions (from the 2020 XML; Pool 5 2015 shapefile has the same fields plus finer genus codes)
Fields: `LCU_C1` (map class + cover modifier A-D + tree height), `LCU_N1`, `LCU_C2/N2`, `COVER_C` (A 10-33 %, B 33-66, C 66-90, D >90), `HEIGHT_*`, `CLASS_31` / `CLASS_15` / `CLASS_7` (merged class ladders), `HNA_*`, `HYDRO_*`, `LAND_WATER`, `USNVC_*`. Source classification: Dieck et al. 2015, USGS TM 2-A1.

| CLASS_31 | Definition (verbatim sense from metadata) | Surface-reaching? |
|---|---|---|
| **Sv** | Open water with submersed vegetation | No (submersed; out of scope for observation, kept only as a "not open water" stratum) |
| **Rf** | Emergents - rooted floating aquatics (lotus and/or water lily), may include <50 % emergents | **Yes, floating-leaved** (Pool 5: Nelumbo, Nymphaea genus codes) |
| **Dma** | Deep marsh annual (predominantly wild rice, may include rooted floating) | **Yes, emergent** |
| **Dmp** | Deep marsh perennial, semipermanently flooded (arrowhead, bur-reed, cattail, pickerelweed) | **Yes, emergent** |
| Sma / Smp | Shallow marsh annual / perennial (seasonally flooded; beggartick, millet / arrowhead, bulrush, cattail, giant reed) | Mostly emerged but on mud flats; treated as ambiguous, not scored |
| Ow | Open water, non-vegetated | Negative class |
| Md, Sb, Sd | Mud, sand bar, sand | Land/bare |

Pool 5 2015 area by class (ha, share of mapped 5,469 ha): Ow 1,697 (31 %), Sv 985 (18 %), Rf 541 (9.9 %), Dma 259, Dmp 226, Smp 260, Sma 8; floodplain forest and others the remainder. In `LAND_WATER`, Dma/Dmp/Rf/Sv/Ow are "Water".

### 1.3 (b) UMR LTRM SAV CSV (`sources/usgs_sav_upper_miss_rf/vegetation_data.csv`)
28,998 site-year rows, 1998-2019, UTM 15N coordinates (confirmed by conversion). 19 taxa columns (presence 0/1), none of them a surface layer; `NLPW` is not defined in the release codes (unverified; probably a native floating/pondweed group, do not use as truth).

| Pool code | Rows | Years | Mean lon/lat |
|---|---|---|---|
| 13 | 9,571 | 1998-2019 | -90.18, 42.02 |
| 8 | 9,907 | 1998-2019 | -91.25, 43.70 |
| L4 (lower Pool 4) | 3,359 | 1998-2019 | -91.99, 44.38 |
| U4 | 3,015 | 1998-2019 | -92.49, 44.57 |
| 26 | 1,635 | 1998-2004 | -90.37, 38.91 |
| LG (La Grange) | 1,511 | 1998-2004 | -90.15, 40.25 |

Fleet overlap (registry `lakes.v1.json`, 621 lakes; canonical analysis polygons from the GCS registry, point-in-polygon plus 500 m proximity):

| Fleet lake | Sites inside polygon | Years | Sites 2015-2019 | Notes |
|---|---|---|---|---|
| Lake Pepin MN | 779 (766 "U4", 13 "L4") | 1998-2019 | 181 (33-43 per year) | 46 % of 2015+ sites have any SAV taxon; top taxa POPE6 39 %, CEDE4 26 %, ELCA7 12 % |
| Rice Lake IL | 0 (bbox hit only) | - | 0 | Illinois River backwater, no LTRM sites inside |
| Keokuk, Pool 8/13/26 as lakes, other Illinois River lakes | not in the 621-lake registry | - | - | No fleet entity to join. Registry has no lake named Keokuk and nothing else within the UMR/Illinois corridor. |

Lake Pepin 2015+ site-years are submersed-taxon presence/absence only. They are a **submersed** check and cannot validate surface presence. The matching surface truth for Lake Pepin would be the UMRS 2020 Pool 4 polygons (not obtained).

### 1.4 Manual steps to get the 2020 pool zips (human, in a normal browser)
1. Open https://www.sciencebase.gov/catalog/item/6102cbf7d34ef8d7055e7971 (DOI 10.5066/P9U46VQP).
2. In "Attached Files" click the pool zip name (smallest useful ones: `2020_LCU_Pool_04.zip` 62.7 MB covers Lake Pepin; `2020_LCU_Pool_08.zip` 62.6 MB; `2020_LCU_Pool_01.zip` 1.9 MB; `2020_LCU_Pool_15.zip` 2.6 MB). The browser SPA fetches a signed URL after load; this is what plain curl cannot do.
3. Save to `~/Desktop/Development/Sector_Research_Data/vegetation-brain/sources/umrs_landcover/pool_04/` (one new empty dir per pool), then tell the next session to unzip and run `experiments/adoption/umr/s_score_pool5.py` with the polygon path changed. The class fields are the same (verified via XML).

### 1.5 (c) Production-style surface observer vs UMRS Pool 5 polygons

**Setup (exactly what was run).** Script `experiments/adoption/umr/s_score_pool5.py`. Rule from `derive_water_surface.py`: B8A as NIR (20 m, nearest to 10 m), B04 10 m, `NDVI = (B8A-B4)/max(1e-6, B8A+B4) >= 0.30`, pixels "seen" if SCL > 0 and at least 60 m from SCL cloud/shadow/cirrus/defective, dark water guard (red and B8A both < 0.01 excluded), 50 m cells, plant fraction = plant px / seen px, cell flagged at >= 0.5, cell UNKNOWN if < 50 % of its pixels seen. Reflectance `DN*1e-4 - 0.1` for `sentinel-2-c1-l2a` (2018), offset-free for `sentinel-2-l2a` (2017). Haze/structure standoffs from production were **not** reproduced (simplification). Cells use a UTM 15N 50 m grid, not the production Web Mercator grid (about 41 m on the ground).
Truth cells (50 m): positive = Rf + Dma + Dmp area fraction >= 0.5 (3,932 cells; 2,095 of them Rf-only); negative = Ow >= 0.9 (5,192 cells) or Ow+Sv >= 0.9 (8,249). Shore-adjacent cells (mean distance to land < 10 m) excluded. Shore matching: negatives reweighted to the positives' histogram over bins 0/15/30/45/60/90/150/300 m (positives: 2/296/357/247/384/527/1,344 per bin; negatives 1/186/434/463/779/1,359/1,927 - the 0-15 m bin is empty, so matching is only informative above 15 m).

**Scene availability (important).** No Sentinel-2 L2A exists in Earth Search for the Pool 5 bbox in 2015 or 2016 (collections `sentinel-2-c1-l2a` and `sentinel-2-l2a`; first L2A summer is 2017, c1 first summer 2018). Per prereg section 4 logic this is `NO_SCENE`. Substitutes, **clearly labelled**:
- 2018 (c1), reference 12 Aug 2018, +-21 d: 14 items, 5 usable dates; S and A use 10 Aug (gap 2 d); P uses 3 accepted scenes (31 Jul, 10 Aug, 15 Aug).
- 2017 (l2a), only 4 items: nearest scene 30 Aug (18 d), P = INSUFFICIENT (1 accepted scene).

Results (shore-matched unless stated; open-water negatives = Ow only):

| Year / observer | Truth | Recall | Precision (raw / matched) | F1 matched | IoU matched | Open-water FPR (raw / matched) |
|---|---|---|---|---|---|---|
| 2018 S | Rf+marsh | 0.963 | 0.979 / 0.964 | 0.964 | 0.930 | 1.6 % / 2.7 % |
| 2018 A | Rf+marsh | 0.963 | 0.979 / 0.964 | 0.964 | 0.930 | 1.6 % / 2.7 % |
| 2018 P (median of 3) | Rf+marsh | 0.967 | 0.982 / 0.971 | 0.969 | 0.940 | 1.3 % / 2.2 % |
| 2018 P | Rf only | 0.961 | 0.967 / 0.956 | 0.958 | 0.920 | 1.3 % / 1.8 % |
| 2017 S (18 d gap) | Rf+marsh | 0.934 | 0.987 / 0.975 | 0.954 | 0.912 | 0.95 % / 1.9 % (P row reported = A, insufficient) |
| 2018 S, negatives Ow+Sv | Rf+marsh | 0.963 | 0.663 / 0.651 | 0.777 | 0.635 | 23 % / 25 % |

Interpretation and caveats:
- Against pure open water the NDVI cell rule separates floating-leaved and emergent beds very well in this turbid river backwater, even single pass (matches the PNW polygon result of note 04 once the cell vote is applied).
- 23 % of Sv cells flag. Those are plausibly real topped-out submersed canopy (the 2015 Sv code classes C and D are 66-100 % cover) plus 3-year change; they are **not** counted as false positives in the headline but show that "open water" in the truth is the clean stratum. Report both.
- The polygons are 2015 and the imagery 2017/2018, so recall mixes observer error with 3 years of bed change; this is a labelled substitute, not a prereg headline (needs survey-image gap <= 7 d).
- Ow cells in this drawdown product are mostly channel and pool centre, so shore matching has thin support at 0-45 m.
- Single pool, not a fleet lake, turbid river environment: **do not pool with clear lakes**, and this alone cannot satisfy gate (a) (needs >= 3 independent truth lakes with >= 30 positive cells; here one system, 3,932 positive cells).
- No bootstrap CIs were computed (one pool); LOLO not applicable (no tuning).
- Outputs: `experiments/adoption/umr/out/pool5_score_2018.json`, `pool5_score_2017.json`.

## 2. UMN Minnesota dataset (DOI 10.13020/av1t-c667)

**Obtained.** `doi.org` redirects to `conservancy.umn.edu/handle/11299/264079` and that HTML page returns an Azure WAF JavaScript challenge, which I did not attempt to bypass. The repository's public DSpace REST endpoints under `/server/api/...` answered normally to a plain browser User-Agent: `pid/find?id=hdl:11299/264079` (item uuid 5a35c985-acb0-42cb-a843-ad419943f01c), `core/items/<uuid>/bundles`, `core/bundles/<ORIGINAL uuid>/bitstreams`, `core/bitstreams/<uuid>/content`. DataCite (`api.datacite.org/dois/10.13020/av1t-c667`) confirms CC0 and the handle.
Files in `sources/mn_umn/dl/`: `Readme_MN_Aquatic_Plants_6Nov2025.txt` (36 KB), `a_MNsynthesis_dataprep.R` (100 KB), `data.zip` (36.9 MB; unzipped to `data_extracted/`, 1.1 GB on disk: inputs 286 MB + outputs). The 2.7 MB html report was not downloaded.
Licence: CC0 1.0; DRUM terms of use apply (https://conservancy.umn.edu/pages/drum/policies/#terms-of-use). Authors: M. R. Verhoeven (contact in the dataset README), D. J. Larkin (contact in the dataset README). README states 3,194 surveys, 1,520 lakes, 367,382 points (the DataCite text says 372,091), 231 taxa. Personnel names stripped; protected species de-identified and their locations stripped.

Key files (`data_extracted/data/output/DRUM/`): `plants_env_data.csv` (one row per point x taxon; DOW, LAKE_NAME, SURVEY_ID, SURVEY_DATE, POINT_ID, Longitude, Latitude, DEPTH_FT, Secchi_m, NO_VEG_FOUND, SURFACE_GROWTH, TAXON, REL_ABUND), `plants_occurrence_wide.csv` (572 MB, one row per point, 253 columns), `surveys_aqplants.csv` (survey level).

`SURFACE_GROWTH` ("plant growth reached surface of water"): only 14,365 rows = 1 of 726k have value 1, and value 1 occurs only in small-lake surveys (Mitchell, Blueberry, Ann, Coal, Lower Mission, Otter...). **No fleet-lake survey has it set**, so surface truth for fleet lakes must come from taxon life-form lookup (my crude regex: Nymphaea, Nuphar, Brasenia, Nelumbo, Potamogeton natans/nodosus, Lemna family = floating-leaved; Typha, Schoenoplectus, Zizania, Sagittaria, Sparganium, Phragmites... = emergent).

Fleet overlap (points inside the analysis polygon; 12 MN registry lakes tested):

| Fleet lake | Surveyed points with coordinates | Survey years | S2-era (2015+) | Floating-leaf taxon points / emergent-taxon points |
|---|---|---|---|---|
| Lake Minnetonka | about 3,000 | 2011, 2014-2018 | 2015-2018 (2015: 1,501 pts; 2016: 548; 2017: 183; 2018: 273) | 2015: 183 / 3; 2016: 125 / 1; 2017: 6 / 0; 2018: 25 / 0 |
| Mille Lacs | about 7,500 | 2009, 2010, 2014, 2017 | 2017: 1,215 pts | 2017: 274 / 4 (2014: 367 / 34) |
| Lake Winnibigoshish | 786 | 2017 (31 Jul-8 Aug) | yes | 10 / 7 |
| Leech Lake | many | 2002-2005 | no | - |
| Gull Lake | 167 | 2008 | no | - |
| Lake Pepin, Rainy, Red, Vermilion, Bemidji, Otter Tail, White Bear | 0 matched | - | - | no coordinates inside polygon in this release |

Use: recall by lake on floating-leaf/emergent taxa for Minnetonka 2015-2016 and Mille Lacs/Winnibigoshish 2017 (point labels are presence-only; precision never computed). Survey dates are first-day-of-survey; multipart surveys span days. Not scored yet.
No MANUAL_DOWNLOAD_STEPS.md written because it was not needed.

## 3. Agency request channels (plain-HTTP probes only)

### Wisconsin DNR (SWIMS / point-intercept)
- Aquatic plants hub: https://dnr.wisconsin.gov/topic/lakes/plants (200). Links there: **Aquatic Plant Explorer (APEx)** https://dnr-wisconsin.shinyapps.io/AquaticPlantExplorer/ (Shiny app, view-only: statewide distributions, lake maps of abundance/species count, trends; no download control found by plain HTTP), Sampling Maps https://apps.dnr.wi.gov/lakes/plants/samplingmaps/ (point-intercept grids and GPS coordinates by county, i.e. sample locations, not results), Research page https://dnr.wisconsin.gov/topic/lakes/plants/research (PI protocol and the Excel data-entry form).
- SWIMS: https://apps.dnr.wi.gov/swims/ redirects to `securitygateway/login` (login-gated). WI DNR open data hub search "aquatic plant" returned no PI dataset (only an unrelated Aquatic Plant Survey web map).
- Contact published on the page: **DNRAPMProgram@Wisconsin.gov** (Aquatic Plant Management program), plus the regional APM coordinator map PDF `/sites/default/files/topic/Lakes/APMCoordinatorMap.pdf`.
- Status: request-only for bulk PI data (point-level species, abundance). Licence/terms: none stated on the pages. Format unknown until requested (the data form is an Excel template; a SWIMS export is the likely format).
- Fleet-relevant WI lakes: Winnebago, Mendota, Monona, Petenwell, Castle Rock, Big Green, Lake Wisconsin, Geneva, Chippewa Flowage, Courte Oreilles.

### TVA
- Probes of tva.com aquatic-plant pages (`/aquaticplants`, treatment schedule, regional contacts) all returned **403 with a Cloudflare "Just a moment" challenge**. Per rules I did not attempt to bypass. The pages are readable only by a human browser.
- From web-search snippets of those pages (not directly verified): public treatment-schedule page with "potential management zone" maps per reservoir (Guntersville, Wheeler, Pickwick, Watts Bar...), an Aquatic Plant Identification tool with public observation reporting, and an "Email us" link whose address I could not read. The TVA Public Land Information Center phone listed by a search snippet is 1-800-882-5263. A local news article names Stephen Turner as Aquatic Plant Management Program manager (secondary source, unverified). TVA has used hydroacoustic mapping (secondary sources).
- Status: **request-only** (maps shown on website; GIS not published as far as visible). The human should open tva.com/aquaticplants and take the contact address from the page.

### TPWD (Texas)
- No vegetation GIS download found. Habitats page https://tpwd.texas.gov/landwater/water/habitats/ (200) lists lakes/rivers/wetlands but no aquatic-vegetation data; TPWD GIS page https://tpwd.texas.gov/gis/ lists a "Landscape Ecology Program: Vegetation Mapping" (terrestrial) and external GIS resources. Old aquatic-vegetation and lake-management URLs 404.
- Annual fisheries survey reports (PDF, with vegetation sections) at https://tpwd.texas.gov/publications/pwdpubs/media/lake_survey/ (e.g. `pwd_rp_t3200_1251_2024.pdf`); these give coverage tables, not polygons.
- **Formal channel (published by TPWD):** Open Records page https://tpwd.texas.gov/site/openrecords. Portal "Open Records Center": https://tpwdtexas.govqa.us ; email **Public.Information@tpwd.texas.gov**; fax (512) 389-4482; mail Open Records Coordinator, 4200 Smith School Road, Austin, Texas 78744. Texas Public Information Act: request must be in writing, existing information only, no reason required. District fisheries offices are the likely data owners.
- Status: request-only.

### SFWMD (Lake Okeechobee)
- **Directly downloadable.** SFWMD open data (ArcGIS Online org `SFWMDOpenData`, id sDAPyc2rGRn7vf9B; portal link https://geodata.sfwmd.gov) hosts anonymous ArcGIS feature services:
  - Lake Okeechobee Littoral Vegetation: 1972-73, 1994-95, 2003, 2003N, 2006, 2007, 2010, 2011, 2012, 2015, 2016 (e.g. `https://services1.arcgis.com/sDAPyc2rGRn7vf9B/arcgis/rest/services/VEG_OKE_2016/FeatureServer/0`, 48,425 polygons, 1 ha grid cells, photointerpreted from 9 in stereo aerials of June 2016, fields VEGLABEL1_CODE/DESC to VEGLABEL4, GENERAL_DESC; maxRecordCount 1000, so page with `resultOffset`).
  - Kissimmee Chain of Lakes Littoral Vegetation: 2005, 2007, 2009, 2016 (`VEG_KCOL_2016`); Kissimmee River floodplain vegetation 1996-2020.
  - Class counts saved in `sources/agency_probes/sfwmd_okee2016.classes.json` / `sfwmd_okee2015.classes.json`. 2016 surface-relevant classes: MFF floating emergent marsh 5,091 cells, MFFe lotus 45, MFFh Hydrocotyle 133, MFGtD dominant cattail 7,504, torpedo grass 1,712, OW open water 14,238, SAV 56.
  - Scope caveat: the layers cover the **littoral marsh** (Moore Haven and south islands) not the open-lake SAV. The annual **open-lake SAV** mapping (about 700 1-km grid sites, late Aug-mid Sep; methods doc saved as `sfwmd_yearly_sav_mapping_methods_and_results.doc`, overview `sfwmd_savprojoverview.pdf`) has **no GIS layer found**: request.
  - Terms (item licenseInfo): provided "in response to the Florida Public Records Law, Chapter 119 ... AS IS", acknowledgment of SFWMD appreciated; SFWMD Scientific Data Management Policies govern monitoring data.
- Request channels published on sfwmd.gov: GIS data questions **gisdata@sfwmd.gov** (https://www.sfwmd.gov/science-data/gis); public records **publicrecords@sfwmd.gov**, phone (561) 682-2729, GovQA portal linked from https://www.sfwmd.gov/who-we-are/public-request; mail: Public Records Officer, Office of Ombuds and Open Government (Mail Stop 2510), 3301 Gun Club Road, West Palm Beach, FL 33406. SFWMD notes email addresses are public records.
- Fleet lakes this unlocks: Okeechobee (emergent/floating beds, 2015-2016 matches S2 era via c1 from 2018 only; again check scene availability: c1 starts 2018, l2a 2017), Kissimmee/Cypress area.

## 4. Dead ends and corrections to earlier notes
- Note 01 said the UMRS 2020 class schema was unconfirmed: now confirmed (section 1.2). It also said "download via browser"; reason is the signed-URL requirement above.
- ScienceBase 2010/11 pool items have no downloadable files, only WMS/WFS; 2000 pool zips are S3-backed too (same block); 2002 Pool 8 (`lcu_2002_p8.zip`, 40 MB) is disk-stored and downloadable but pre-S2.
- Earth Search had no Sentinel-2 L2A for summer 2015 or 2016 in the Pool 5 bbox (checked only there): other 2015/2016 truth sets (SFWMD 2015/2016 Okeechobee, FWC 2015 points) should have their scene availability checked per location before relying on them.
- Not tried: L1C scenes for 2015 (no production offset path); WFS for 2010/11 Pool 4 (not S2-era).
