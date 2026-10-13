# Vegetation Brain: ground-truth / authoritative dataset survey

Checked 2026-10-13. Research only; no repo changes. Downloads live outside git under
`~/Desktop/Development/Sector_Research_Data/vegetation-brain/sources/` and are in `MANIFEST.jsonl` (5 lines appended).

Verification legend: **V-fetch** = I fetched the URL/API and saw real content/records today. **V-200** = landing page returned HTTP 200 only (content not read in detail). **V-search** = surfaced by web search with the description quoted from the result; I did not open the file. **Unverified** = from background knowledge, not checked. **Dead/blocked** = no response or error today.

Honest headline: there is NO single multi-state, downloadable, polygon-level submerged-vegetation ground truth for US reservoirs. The usable pieces are (a) a few point-intercept survey databases (FL FWC, MN, WI, UMRS), (b) EPA NLA shoreline cover classes, which map directly to SUBMERGED/EMERGENT/FLOATING + 5-level density, (c) wetland/land-cover layers (NWI, NLCD, C-CAP) as coarse priors, and (d) presence-only invasive records (USGS NAS, EDDMapS) for validating specific species. Most Corps/TVA/state agency "maps" are PDFs or request-only.

## 1. Ranked table

Rank is by value as validation ground truth for a Sentinel-2-based vegetation brain across a ~621-lake fleet.

| # | Source | Owner | Content | Access | Fleet reuse | Class mapping | Role |
|---|---|---|---|---|---|---|---|
| 1 | EPA NLA 2017 physical habitat (AM_* fields) | EPA NARS | Per-station (10 per lake) cover class 0-4 for emergent, floating, submergent, total macrophytes; 1,147 lakes, 48 states, 12,076 rows | Open CSV (verified, downloaded) | Low per-fleet overlap: only 112 of 5,721 site-visits are >1,000 ha; fleet lakes sampled by chance only (Lake Oahe SD found) | Direct: EMERGENT / FLOATING / SUBMERGED + density bins (0, <10, 10-40, 40-75, >75 %) | Validation (class + density), CONUS-wide generalization test |
| 2 | FL FWC Long-Term Monitoring point intercepts | FWC Freshwater Mgmt / FWRI | 96,055 GPS points, 2015-2023, species list per point; 96 lake-name strings incl. Okeechobee, Kissimmee, Istokpoga, Toho, Harris, Griffin, Apopka, Lochloosa | Open ArcGIS REST, queryable, downloaded | FL fleet lakes (~12) plausibly 5-10 | Species-list per point to class via a species lookup table; presence not area; density only via species count | Validation (FL), strong |
| 3 | Minnesota aquatic plant occurrence 1999-2018 (Verhoeven and Larkin) | Univ. of Minnesota Data Repo, DOI 10.13020/av1t-c667 | 3,194 surveys, 1,520 lakes, 372,091 sampled points, 231 taxa, depth, some point-level abundance, Secchi join | CC0 (V-search; repo page returned a WAF challenge to curl, not downloaded) | MN fleet lakes (~12) plausibly most; also helps clear-water northern-lake validation | Taxon to class lookup; point abundance subset for density | Validation (MN), strong |
| 4 | USGS UMESC LTRM vegetation + SAV RF release | USGS UMESC / Delaney and Larson | Per-site SAV presence by species 1998-2019 (29k rows), UTM coords; random forest predictions 2010-2019 | CC0-style USGS release; DOI 10.5066/P9QGD5NI resolves to ScienceBase item 64540e54d34eefd5da843ac9 (V-fetch; vegetation_data.csv downloaded) | Pools 4-26, La Grange, Open River (Mississippi/Illinois lakes and pools) | Species presence to SUBMERGED/FLOATING/EMERGENT; no density except rake class in LTRM raw | Validation (UMR pools) |
| 5 | UMRS 2020 Systemic Land Cover/Use (and 2010/11, 2000, 1989) | USGS UMESC / Corps LTRM | Photo-interpreted polygons by pool; dozens of 1.9-124 MB zips listed (V-fetch listing) | Open, ScienceBase item 6102cbf7d34ef8d7055e7971, DOI 10.5066/P9U46VQP | Mississippi/Illinois pools | LTRM 31-class scheme; whether aquatic-veg classes (submersed / floating / emergent) are in 2020 schema NOT confirmed | Validation polygons (best polygon source I found) |
| 6 | USGS NAS (Nonindigenous Aquatic Species) | USGS Gainesville | Presence-only occurrence points, plants incl. hydrilla, water hyacinth, Eurasian milfoil; Darwin Core 692k records, CC0 (V-search); REST API v2 returns real records (V-fetch, e.g. hydrilla Rodman Reservoir FL) | Open API + DwC-A | Nationwide, uneven | Species to class | Species-level validation, weak for absence |
| 7 | USFWS NWI Wetlands REST | USFWS | Polygons with Cowardin code (ATTRIBUTE) + WETLAND_TYPE + ACRES; e.g. L2USCh, PEM1Ch near Guntersville (V-fetch query returned) | Open REST: `https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0` (maxRecordCount 500), WMS; statewide shapefile downloads page V-200 | CONUS, vintage varies decades by county | L2UB/L2AB aquatic bed (SUBMERGED/FLOATING), PEM emergent, PFO/PSS flooded woody | Prior / coarse validation; NOT current |
| 8 | MN MBS Lakes and Aquatic Plant Data | MN DNR | Point per surveyed lake with species list (rare focus); point at boat access | Open, Geospatial Commons (V-search; page via WAF-redirect to curl) | MN lakes | Species list only | Weak |
| 9 | MI EGLE ANC Vegetation Survey Sites | Michigan EGLE | 674 survey locations 1986-present (V-fetch count); reports not geometries | Open ArcGIS REST layer 14 | MI lakes | Only tells you where/when surveyed | Index to request reports |
| 10 | WI DNR PI survey sampling grids / SWIMS | WI DNR | Sampling maps and GPS points (V-200); results in SWIMS and consultant PDFs | Sampling grids open; results by request / PDFs | WI fleet lakes | Rake-fullness 0-3 per point (known method) | Validation if obtained, high effort |
| 11 | NLCD (aquatic bed not in Anderson scheme; Woody + Emergent Herbaceous Wetlands) | USGS/MRLC | 30 m raster; classes 90 Woody Wetlands, 95 Emergent Herbaceous Wetlands | Open; mrlc.gov/data V-200 | CONUS | EMERGENT / FLOODED-TERRESTRIAL only; no submerged | Prior only |
| 12 | NOAA C-CAP regional land cover | NOAA OCM | 30 m, coastal watersheds; includes Palustrine Aquatic Bed class | Open; Digital Coast page V-200 | Coastal lakes only | Aquatic bed (SUBMERGED/FLOATING mixed) | Prior for coastal states |
| 13 | LANDFIRE EVT | USGS/USFS | 30 m existing vegetation type incl. herbaceous wetland and aquatic types | Open; landfire.gov V-200 (not studied) | CONUS | Mostly EMERGENT/FLOODED-TERRESTRIAL | Prior only |
| 14 | TVA aquatic plant management | TVA | Annual surveys on Guntersville, Wheeler, Nickajack, Chickamauga, Pickwick, Watts Bar; treatment schedule and zone maps; PI tool to submit observations (V-search; tva.com returns 403 to curl) | Reports / maps; no download found | ~6 TN-Valley reservoirs | Species + acreage | Validation if requested from TVA |
| 15 | SFWMD Lake Okeechobee annual SAV mapping | SFWMD | ~700-site 1 km grid, annual Aug-Sept, acres by species (eelgrass, peppergrass, hydrilla, chara), bulrush; goal >40,000 ac SAV (V-search) | Reports; no GIS download found | Okeechobee | Species to SUBMERGED/EMERGENT | Validation (request) |
| 16 | Texas TPWD vegetation surveys (e.g., Lake Austin 456 ac hydrilla Sept 2025, Canyon Lake ~10%) | TPWD Inland Fisheries | Annual acreage / % cover per reservoir in reports and treatment proposals | PDFs / web; no GIS found | Selected TX lakes | % coverage by species | Validation by % area |
| 17 | CA Delta hyperspectral SAV (CSTARS/DBW 2003-2008) | UC Davis / DBW | Egeria and water hyacinth classification, accuracy tables (93% / 73% at 51 ha sites; 29% / 65% Delta-wide) (V-search) | No downloadable files found | Delta only | SUBMERGED (Egeria) / FLOATING (hyacinth) | Accuracy benchmark only |
| 18 | Corps APIS | USACE ERDC | Plant ID and management info system; NOT survey data (V-search) | n/a | n/a | n/a | Species-to-class lookup only |
| 19 | EDDMapS, MISIN (Midwest), iMapInvasives, MIDAS | UGA CBIOS / MSU / NatureServe | Crowd and agency presence records; EDDMapS 200 (403 without UA), MISIN 200, iMapInvasives 200 | Free account for download (unverified per portal) | Nationwide uneven | Species presence | Weak validation |

## 2. Downloaded here (all outside git)

| File | Bytes | sha256 |
|---|---|---|
| sources/fwc_ltm_point_intercepts/fwc_ltm_point_intercepts.csv | 11,884,956 | 026f8d90...bdc457ee64 |
| sources/nla_2017_phab/nla_2017_phab-data.csv | 4,279,608 | 0346e959...4cd9730ae6cc |
| sources/nla_2017_phab/nla_2017_phab-metadata.txt | 20,559 | 8ba67a93...1fff9e1e9 |
| sources/nla_2017_phab/nla_2017_site_information-data.csv | 4,361,425 | 9d52dc17...e595e782 |
| sources/usgs_sav_upper_miss_rf/vegetation_data.csv | 2,919,342 | 9ab31942...082abaf2 |

Full hashes are in `MANIFEST.jsonl`. NLA site info joins to phab on SITE_ID and carries LAT_DD83/LON_DD83, GNIS_NAME, AREA_HA, PSTL_CODE.

## 3. Per-source detail

### 3.1 EPA National Lakes Assessment 2017 (physical habitat)
- URL: https://www.epa.gov/national-aquatic-resource-surveys/data-national-aquatic-resource-surveys (V-fetch, file links harvested). Direct: `.../sites/default/files/2021-04/nla_2017_phab-data.csv`.
- Content (verified in downloaded file): fields AM_EMERGENT, AM_FLOATING, AM_SUBMERGENT, AM_TOTALCOVER, FC_AQUATIC, MACRO_LAKEWARD; cover coded 0=0%, 1=<10%, 2=10-40%, 3=40-75%, 4=>75% per shoreline station plot. 12,076 rows, 1,147 sites, 48 states (no AK/HI; counts per state 7-58). Submergent code distribution: 0:4312, 1:2667, 2:1958, 3:1672, 4:1261.
- Caveat: plots are the littoral/near-shore (about 10 m x 15 m riparian plots plus adjacent shallow water), not whole lake. Site-info shows only 112 of 5,721 visits are lakes >1,000 ha; large reservoirs in the fleet are rarely sampled. Of my named big-lake probes only Lake Oahe SD (125,497 ha) matched.
- Vintage: summer 2017; NLA runs every 5 years (2007, 2012, 2017, 2022). NLA 2022 data not located by me. 2012 phab files also listed (nla2012_wide_phab_08232016_0.csv).
- Licence: public domain (US gov). Role: only multi-state source with SUBMERGED/EMERGENT/FLOATING + density in exactly the target taxonomy. Best for calibrating class/density thresholds on small/medium lakes.

### 3.2 FL FWC Long-Term Monitoring point intercepts
- URL: https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer (V-fetch). Layer 33 "LTM Point Intercepts", 35 "LTM Lakes", 54 "Aquatic Plants" (metadata response not parseable), 30/31 Bathymetry.
- Content: fields Site_Id, Date, Year, Lake, Species (comma list; also codes like A_TUSS = floating tussock/emergent mat, A_Marsh), Latitude, Longitude. 96,055 points; lakes seen: Okeechobee (multiple sectors), Kissimmee, Hatchineha, Toho (East Toho), Istokpoga, Harris, Griffin, Apopka, Lochloosa, Johns, Monroe, George, Beauclair, Eustis, etc. Years 2015-2023.
- Mapping: species names (hydrilla, coontail, eelgrass, Southern naiad, bladderwort = SUBMERGED; spatterdock, fragrant water-lily = floating-leaved; water-hyacinth, water-lettuce, duckweed = FLOATING; cattail, bulrush, pickerelweed, maidencane = EMERGENT; willow, wax myrtle, bald cypress = FLOODED-TERRESTRIAL). Density only as per-point species richness.
- Name hygiene needed (typos: "Istopoga_West_Shore", "Cherry(Lake)").
- Also exists: FWC annual statewide inventory of ~460 public waters, 1.25 M acres, and Annual Report of Aquatic Plant Control (V-search; myfwc.com/AquaticPlants, landing page V-200). Related FWC treated-acres layers 1998-2021 were in the same service per search metadata (not downloaded).
- Licence: state open data, contact GISLibrarian@MyFWC.com says always acquire from FWC.

### 3.3 Minnesota (Verhoeven and Larkin, UMN Data Repository)
- Citation found via search: "Occurrence and environmental data for aquatic plants of Minnesota from 1999-2018", DOI 10.13020/av1t-c667; CC0; 3,194 surveys, 1,520 lakes, 372,091 points, 231 taxa; depth and (subset) point-level abundance; Secchi joined. Repository pages return an Azure WAF JS challenge to non-browser clients, so I could not fetch or download (Unverified file layout; open in a browser to download).
- MN DNR per-lake vegetation survey reports are PDFs at `files.dnr.state.mn.us/natural_resources/water/lakes/vegetation_reports/<DOWID>.pdf` (V-search; many results). LakeFinder (https://www.dnr.state.mn.us/lakefind/index.html V-200).
- MBS dataset: https://gisdata.mn.gov/ru/dataset/env-mbs-lakes-and-aquatic-plants (V-search, points at boat access; content date Apr 30 2025).

### 3.4 USGS UMESC / Corps LTRM (Upper Mississippi River System)
- SAV release: https://www.sciencebase.gov/catalog/item/64540e54d34eefd5da843ac9 (V-fetch). Files: vegetation_data.csv (2.9 MB, downloaded; one row per sampled site-year, species presence 0/1 for CEDE4 coontail, ELCA7 elodea, MYSP2 milfoil, VAAM3 wild celery, NAGU/NAFL najas, POCR3 curlyleaf etc., plus UTM, pool, stratum, substrate, depth), water_full.csv (12.9 MB), RF results. Years in the file begin 1998.
- 2020 Systemic Land Cover/Use: https://www.sciencebase.gov/catalog/item/6102cbf7d34ef8d7055e7971 (V-fetch listing, per-pool zips e.g. LaGrange 124 MB, Pool 4 62.7 MB); DOI 10.5066/P9U46VQP. Aerial photography summer 2020; 2000, 2010/11 share a classification; 1989 crosswalked. Not downloaded (pool zips; Open River 96 MB; I did not confirm classes).
- LTRM annual vegetation status reports 1997-2002 on ScienceBase (V-search). umesc.usgs.gov vegetation page V-200 (old URLs for land cover pages 404).
- Usefulness: lake-like backwaters, navigation pools (Pool 4/Lake Pepin area, 8, 13, 26, La Grange).

### 3.5 USGS NAS
- API: `https://nas.er.usgs.gov/api/v2/occurrence/search?genus=Hydrilla&state=FL` returned a real record (V-fetch). Species endpoint returned hydrilla speciesID 6 and 2942 (note: speciesID=6 with state=AL returned zero records, so filter by genus/species name). Bulk Darwin Core archive on IPT (page returned 503 during my check; GBIF mirror DOI 10.15468/ijccz9 per search); CC0.
- Use: spatial join of hydrilla / hyacinth / milfoil / salvinia / Egeria presence to fleet lakes; no absences; uneven reporting.

### 3.6 USFWS NWI
- Service list page: https://www.fws.gov/wetlands/data/web-map-services.html (V-fetch). REST base `https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer` (V-fetch: one layer "Wetlands", fields ATTRIBUTE, WETLAND_TYPE, QAQC_CODE, ACRES, maxRecordCount 500). Spatial query near Lake Guntersville returned L1UBHh, L2USCh, PEM1Ch with WETLAND_TYPE "Lake"/"Freshwater Emergent Wetland". Page lists WMS for Wetlands, Data_Source (imagery vintage), Wetlands_Status, Riparian; says no WFS. (The old `fwsprimary.wim.usgs.gov` host returned an empty layer list.)
- Cowardin mapping: L2AB / PAB = aquatic bed (SUBMERGED or FLOATING via modifiers 1-7: 1 algal, 2 aquatic moss, 3 rooted vascular, 4 floating vascular), PEM = EMERGENT, PFO/PSS = FLOODED-TERRESTRIAL, L2US = unconsolidated shore (exposed/drawdown). Photo-interpreted, varies by decade; Data_Source layer gives per-quad imagery year; not a current-state label.
- Statewide shapefile downloads: https://www.fws.gov/program/national-wetlands-inventory/download-state-wetlands-data (V-200, not downloaded; multi-GB per state).

### 3.7 NLCD / C-CAP / LANDFIRE
- https://www.mrlc.gov/data V-200 (the specific nlcd-2021/2023 deep links I guessed 404, so use the index). NLCD classes 90/95 only; Annual NLCD exists (unverified). C-CAP: https://coast.noaa.gov/digitalcoast/data/ccapregional.html V-200; includes Palustrine Aquatic Bed (unverified in schema read). LANDFIRE https://landfire.gov/ V-200.
- Verdict: use as priors/masks (e.g., wetland fringe, shallow-water exclusion), not as validation of submerged vegetation.

### 3.8 TVA, SFWMD, TPWD, other agency monitoring (no download confirmed)
- TVA: tva.com aquatic plant pages return 403 to curl; web search shows an aquatic plant ID tool, treatment schedule, "potential management zone" maps for Guntersville, Wheeler, Pickwick, Watts Bar; 2025 reported 10,000 acres surveyed, Guntersville 1,494 ac treated (from a trade article, not TVA). Dominant plants now include hybrid eelgrass (Vallisneria) and hydrilla/Eurasian milfoil (V-search). Request GIS polygons directly from TVA.
- SFWMD: yearly SAV mapping document and overview PDF exist (V-search); annual GIS layers not found; ask SFWMD; DBHYDRO is the usual data portal (unverified for this theme).
- TPWD: treatment proposals page (V-search) lists acreage (Toledo Bend 2,500 ac, Caddo 13,000 ac proposed treatment); annual survey narratives for Austin, Canyon. TPWD aquatic vegetation old URL returned 404.
- Corps Mobile District / Lake Seminole: no public survey data found; reports mention hydrilla coverage 35 percent to 24 percent after fluridone.

### 3.9 Academic and open repositories
- Dryad API worked (V-fetch): returned only 5 hits for "submerged aquatic vegetation", none a US reservoir map set (e.g., Back Bay VA SAV and waterfowl 1991-2017, doi:10.5061/dryad.jh9w0vtbd; coastal, not fleet).
- ScienceBase text search for lake macrophyte maps returned only Louisiana barrier-island habitat maps; no reservoir SAV polygon sets.
- Zenodo API did not respond to my curl; web search found no Sentinel-2 SAV validation polygon release for US lakes; found European method papers (Lake Starnberg, Iseo, Mantua, Lithuanian lakes) with reported accuracy but no confirmed data deposits.
- GBIF and EDI search pages returned 200 but I did not mine them. Gap: a targeted EDI/Dryad/Figshare sweep (e.g., Lake Mendota, Lake Tahoe, Lake Champlain, Great Lakes SAV mapped by Landsat/Sentinel; USGS Great Lakes SAV "Lake Erie aquatic vegetation data" page exists per search but returned 403 to curl).
- Gulf-wide SAV (NOAA Gulf Data Atlas) exists as a REST service per search (coastal seagrass, not lakes).

## 4. Best 10 validation lakes

Criteria: real survey points/polygons in hand or highly likely obtainable, plus expected decent Sentinel-2 water clarity. I did NOT measure clarity; "clarity" below is expectation from known trophic status, so verify with Secchi/NLA before use.

| # | Lake / system | State | Ground truth | Clarity expectation |
|---|---|---|---|---|
| 1 | Lake Istokpoga | FL | FWC LTM points 2015-2023 (9 years, downloaded) | Moderate; shallow, vegetation visible |
| 2 | Kissimmee chain (Kissimmee, Hatchineha, East Toho) | FL | FWC LTM points 2015-2023 (downloaded) | Moderate |
| 3 | Lake Harris / Griffin (Harris chain) | FL | FWC LTM points 8-9 years | Variable, eutrophic |
| 4 | Lake Okeechobee | FL | FWC LTM sector points + SFWMD annual 700-site SAV map (report) | Turbid central lake, clearer near-shore; caution |
| 5 | Lake Pepin / Pool 4 area | MN/WI | USGS LTRM vegetation + 2020 land cover polygons | Turbid; poor S2 clarity but best polygons |
| 6 | Pool 8 (La Crosse) | WI/MN | USGS LTRM vegetation + systemic land cover | Moderate; known large SAV beds |
| 7 | Mille Lacs, Minnetonka, Leech and other fleet MN lakes | MN | UMN occurrence dataset (CC0), DNR PDF survey reports | Good to very good in many |
| 8 | WI fleet lakes (e.g., Lake Winnebago system, Pewaukee, Okauchee) | WI | DNR PI surveys, consultant PDFs, sampling grids | Mixed; Winnebago turbid, smaller lakes good |
| 9 | Lake Guntersville | AL | TVA annual surveys (request), NWI aquatic bed polygons (verified query) | Good; shallow clear-ish, extensive hydrilla/milfoil/eelgrass |
| 10 | Lake Austin (and Canyon Lake) | TX | TPWD annual survey acreage (456 ac hydrilla Sept 2025) | Clear; good for S2 |

Notes: #1-#4 usable today from downloaded data; #5-#6 usable today from verified ScienceBase releases (2020 polygons require another download); #7-#8 need browser/request step; #9-#10 are request-based and of lower reproducibility. Add the Lake Oahe SD NLA 2017 site (NLA17_SD-10001) only as low-vegetation negative control.

## 5. State-by-state availability (best known)

Status key: D = downloadable data I verified exists; R = report/PDF or request-only; S = search-only, not opened; N = none found.

| State | Best known survey / dataset |
|---|---|
| AL | TVA annual aquatic plant surveys (Guntersville, Wheeler, Pickwick) R/S; NWI; NLA 2017 (9 sites) D. ADCNR/outdooralabama aquatic plants page 404. |
| AK | None found; NLA 2017 has no AK sites in phab (state list has 48). |
| AZ | NLA 2017 (13 sites) D; no state survey found. |
| AR | NLA (9) D; AGFC vegetation surveys not located. |
| CA | Delta hyperspectral Egeria/hyacinth 2003-2008 (accuracy known, no files) S; NLA (28) D; Lake Tahoe research maps (not verified). |
| CO | NLA (27) D; none else found. |
| CT | NLA (11) D; CT Agricultural Experiment Station invasive aquatic plant surveys (unverified). |
| DE | NLA (7) D. |
| FL | FWC LTM point intercepts 96k pts D (downloaded); FWC annual inventories of ~460 waters R; SFWMD Okeechobee SAV R; UF IFAS plants site V-200. Best state. |
| GA | Lake Seminole hydrilla reports (Corps Mobile) R/S; NLA (13) D; gadnr page 404. |
| HI | None found. |
| ID | NLA (28) D; none else found. |
| IL | UMRS/La Grange Pool LTRM D; NLA (14) D. |
| IN | NLA (58 sites) D; IDNR lake survey reports (unverified). |
| IA | UMRS pools D (Mississippi); NLA (17) D. |
| KS | NLA (18) D; none else. |
| KY | NLA (9) D; Kentucky Lake: TVA/Corps reports R/S. |
| LA | LDWF aquatic vegetation control plans and spray acres (Toledo Bend 1,542 ac treated one June, ~80% giant salvinia) R/S; NLA (15) D. |
| ME | NLA (27) D; MIPAP/Maine DEP invasives page V-200, lake-level data not examined. |
| MD | NLA (8) D; Chesapeake SAV (VIMS) is estuarine, not reviewed here. |
| MA | NLA (11) D; MassDEP lake surveys unverified. |
| MI | EGLE ANC survey-site index, 674 locations D (REST layer 14); MSU 78 northern lakes R/S; NLA (56) D. |
| MN | UMN CC0 occurrence dataset (1,520 lakes) S; MN DNR PDF reports R; MBS points S; NLA (54) D. Second-best state. |
| MS | NLA (15) D; Ross Barnett hydrilla (MSU 2006) R/S. |
| MO | NLA (27) D; MDC/Corps Table Rock, Truman reports unverified. |
| MT | NLA (37) D. |
| NE | NLA (32) D. |
| NV | NLA (16) D; Lake Tahoe separate. |
| NH | NLA (15) D; NH DES exotic species page 403 to curl, data unverified. |
| NJ | NLA (13) D. |
| NM | NLA (13) D. |
| NY | NLA (13) D; APIPP site did not respond; iMapInvasives V-200 (account for data). |
| NC | NLA (13) D; NCWRC aquatic plant pages 404. |
| ND | NLA (57) D; none else. |
| OH | NLA (17) D. |
| OK | NLA (38) D. |
| OR | NLA (55) D. |
| PA | NLA (19) D. |
| RI | NLA (8) D. |
| SC | Santee Cooper / SC DES aquatic plant management (SCAPM minutes) R/S; NLA (12) D; dnr.sc.gov aquaticnuisance 404. |
| SD | NLA (55) D incl. Lake Oahe. |
| TN | TVA reservoirs (Chickamauga, Nickajack, Watts Bar) R/S; NLA (9) D. |
| TX | TPWD annual hydrilla acreage (Lake Austin, Canyon) R; TPWD approved treatment list (Toledo Bend, Caddo) R/S; TWDB GIS exists for volumetric surveys, not vegetation; NLA (48) D. |
| UT | NLA (26) D. |
| VT | NLA (10) D; DEC AIS reports R; ANR Atlas lake layers unverified. |
| VA | NLA (29) D; Back Bay SAV (Dryad) coastal D. |
| WA | Ecology says all aquatic plant data since 1994 is in its lakes database (S, likely EIM); county PDFs R; NLA (35) D. Ecology pages tested 404. |
| WV | NLA (8) D. |
| WI | DNR PI sampling grids + SWIMS + consultant PDFs R; NLA 2017 (55) D plus WI added PI to NLA lakes. |
| WY | NLA (22) D. |

Every state with NLA sites is covered by NLA 2017 at roughly 7-58 lakes; this is mostly small/natural lakes, not the large reservoirs a bowfishing fleet emphasizes.

## 6. Dead links / not verified

- `apis.erdc.dren.mil`, `midas.aqua.wisc.edu`, `apipp.org`, `dbw.parks.ca.gov` page, `lakes.nrri.umn.edu`: no response (000).
- 404: ecology.wa.gov freshwater-plants path, dnr.sc.gov aquaticnuisance, gadnr ANS, TPWD aquatic_vegetation habitat path, ncwildlife plant path, vermont aquatic-invasives path, outdooralabama aquatic-plants, MRLC nlcd-2021/2023 deep links, UMESC land_cover_page.
- 403 to curl (may work in a browser): tva.com, nh DES, usgs.gov data-tools, EDDMapS without browser UA (worked with UA), usgs.gov Lake Erie aquatic vegetation data page.
- WAF-blocked: conservancy.umn.edu, gisdata.mn.gov dataset API (301 loop).
- NAS IPT bulk resource returned 503 at check time.
- I could not confirm Sentinel-2 clarity for any lake, nor the aquatic-vegetation class definitions inside the UMRS 2020 products, nor TVA/SFWMD/TPWD GIS availability.

## 7. Recommended next steps (research only)

1. Build a species-to-class lookup (SUBMERGED / EMERGENT / FLOATING-LEAVED / FLOATING-FREE / FLOODED-TERRESTRIAL) from FWC Species strings; compute per-lake counts; use as first validation set.
2. Join NLA 2017 + 2012 phab to site info on SITE_ID for class/density calibration on lakes within the fleet's size range.
3. Browser-download the UMN CC0 repository and the UMRS 2020 pool zips for the two highest-value non-FL ground truths; check UMRS class schema.
4. Email requests: TVA (Guntersville/Wheeler annual maps), SFWMD (Okeechobee SAV GIS), TPWD Inland Fisheries, WI DNR lakes (SWIMS PI export).
5. Use NWI/NLCD/C-CAP only as coarse priors and masks.
