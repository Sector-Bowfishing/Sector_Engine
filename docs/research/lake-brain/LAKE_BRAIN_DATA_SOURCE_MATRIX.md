# Lake Brain — data source matrix (generated)

Sources worth permanently integrating (ACCEPTED) or following up (LEAD), grouped by what they support.

## -

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Pilot-lake 3DHP vs NHD area check | USGS | 1 | 582 of 590 equal within 0.1% | - | - | api (machine) | public domain | coverage | S-geometry-025 |

## 16-18 complete years for the TVA pilots

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NWS Huntsville RVDHUN Daily River and Lake Summary (IEM AFOS archive) | NWS Huntsville (TVA-supplied pool elevations), archived by Iowa Environmental Mesonet | 1 | Guntersville 2005-01-30, Wilson 2005-01-30, Wheeler 2005-11-23, Pickwick 2003-01-14 to 2014-04-17 (+Nickajack HW) | 2003-2021-09-30 | daily | api (machine) | public (NWS product; IEM free) | historyQuality, seasonalBaseline | S-baselines-008 |

## HUC8 native-range prior for gars, common carp, bowfin, drum

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | Native Ranges of Freshwater Fishes of North America (Daniel and Neilson, HUC8/HUC12, 320 species) | USGS NAS | 1 | not obtained | — | static (2022) | bulk (Data.zip 10.3 GB) (machine) | public domain | — | S-species-010 |

## HUC8 occurrence prior

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS Coarse Range Maps for Fish Species in the CONUS using HUC8s v2.0 | USGS (Cooper et al.) | 1 | used as HUC8 prior for 6 of 14 species (3 buffalo, grass/bighead/silver carp) | — | static (2024-12) | bulk csv (machine) | public domain | — | S-species-009 |

## Pickwick deep history (7 yrs), Kentucky Lake test series (28 yrs)

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | CWMS LRD TVA-supplied lake elevations | USACE Great Lakes and Ohio River Division (data supplied by TVA) | 1 | Pickwick 2019-10, Kentucky 1998-05, Normandy 2019-11 | 1998-2026 | hourly | api (machine) | US government (CWMS public) | historyQuality, seasonalBaseline | S-baselines-006 |

## USBR guide/flood levels

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | USBR RISE API | US Bureau of Reclamation | 1 | 838 locations listed | varies | daily | api (machine) | public | operatorPlan | S-baselines-018 |

## a measured fleet-wide shallow-vegetation proxy and turbidity that already exists in production; used as the independent outcome for evaluating the class scheme

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Sector Water Clarity production bucket index and per-lake history (read-only GET) | Sector (internal) | 3 | 566 lakes (latest pass 2026-10-12), pilots' history 3-16 passes | 2026 | daily | bulk (machine) | private | coverage | S-context-017 |

## agency survey

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | MidFish (USGS data release P1337ZQC): Upper Midwest state fisheries aggregation | USGS (Link et al.) | 1 | 74 directory lakes matched to a surveyed lake; 50 lakes with >=1 target species (WI/MN/IA/IN/SD only) | 1940-2023 | static (2026 release) | bulk (parquet, 280 MB) (machine) | public domain (USGS) | — | S-species-008 |
| ACCEPTED | MN DNR LakeFinder API by_id/by_point (fishSpecies per lake) | MN DNR | 1 | 14 directory lakes: 11 resolved, 9 with species list (common carp 4, bowfin 7) | survey-driven | per survey | api (machine) | undocumented public API; no terms found | — | S-species-017 |
| ACCEPTED | Indiana Data Hub CKAN: Fish_Surveys, Batch_Fish_Records, Fish_Records (aged fish) | IN DNR Fish & Wildlife | 1 | 14 directory lakes: 4 with batch species rows, 1 with a bowfishing target; 373 waterbodies / 48 with species rows statewide | 2010-2025 | about daily/annual | bulk csv (machine) | blank in CKAN (unknown terms) | — | S-species-018 |

## agency survey (observed)

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | MARIS - Multistate Aquatic Resources Information System, fish (via GBIF dataset e0ae862b) | state fish agencies / USGS | 3 | 73 of 621 lakes | to ~2014 | static | api (machine) | CC BY 4.0 | — | S-species-006 |
| ACCEPTED | EPA/USGS Water Quality Portal biological results, siteType lake/reservoir, subjectTaxonomicName | EPA/USGS/NWQMC | 3 | 122 of 621 lakes (common carp 100 lakes; drum 16; smallmouth buffalo 12; others <8) | varies | continuous | api (machine) | public domain | — | S-species-007 |

## agency survey / stocking

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | TX state fish agency open data (per-waterbody species / stocking) | TPWD | 1 | — | — | — | mixed (machine) | unstated | — | S-species-019 |
| LEAD | IL state fish agency open data (per-waterbody species / stocking) | IDNR/iFish | 1 | — | — | — | mixed (machine) | unstated | — | S-species-020 |
| LEAD | WI state fish agency open data (per-waterbody species / stocking) | WDNR | 1 | — | — | — | mixed (machine) | unstated | — | S-species-021 |
| LEAD | OK state fish agency open data (per-waterbody species / stocking) | ODWC/OWRB | 1 | — | — | — | mixed (machine) | unstated | — | S-species-022 |
| LEAD | KY state fish agency open data (per-waterbody species / stocking) | KDFWR | 1 | — | — | — | mixed (machine) | unstated | — | S-species-023 |
| LEAD | MO state fish agency open data (per-waterbody species / stocking) | MDC | 1 | — | — | — | mixed (machine) | unstated | — | S-species-024 |

## alligator gar spawning habitat vs flooded vegetation; terrestrial vegetation establishes on exposed bottom

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Texas Parks and Wildlife Falcon Reservoir 2021 Fisheries Management Survey Report | Texas Parks and Wildlife Dept (Nisbet, Myers) | 3 | 1 reservoir | 2021-2022 | biennial | pdf (machine) | public agency | floodDroughtContext | S-baselines-024 |

## alternate NID mirror, hydropower attributes

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | NID companion layers (USACE Dams_Public FeatureServer; HILARRI, GRAND in NLDI) | USACE / ORNL / SEDAC | 1 | not tested | — | — | api (machine) | public | — | S-context-021 |

## aquatic bed share, littoral (L2) share, palustrine fringe length

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NWI mirror: Esri hosted 'USA_Wetlands' FeatureServer | Esri Landscape / USFWS NWI | 4 | 5 pilots tiled (17-69 tiles, 1,298-5,849 polygons each) | mapping vintages vary by county (1980s-2020s) | static | api (machine) | public domain (NWI) | coverage | S-context-015 |

## area validator, dam/lake link

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USACE National Inventory of Dams (public national gpkg) | USACE | 1 | 389 polygon lakes matched by dam name <=25 km | annual | annual | bulk (machine) | public | coverage | S-geometry-006 |

## audit baseline

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Sector lake-presence release lake-presence-2026-10-12.1 (private; audited aggregates only) | Sector (private research repo) | 1 | 621 rows-lakes; 529 with >=1 non-unknown species; 287 with >=1 established/reported/stocked | records 1905-2026 | release-driven | bulk (machine) | private | — | S-species-001 |

## baseline geometry

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Engine lake polygons jobs/lake-surface/polygons.geojson.gz | Sector (Engine repo) | 1 | 599 of 621; 22 missing | NHD features 2001-2023; file 2026-09-27 | static | bulk (machine) | NHD public domain; 11 osm features ODbL | coverage | S-geometry-001 |

## canonical shoreline

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS NHD High Resolution waterbody (REST nhd/MapServer/12) | USGS | 1 | 606 of 621 matched | 2001-2023 per feature | rolling | api (machine) | public domain | coverage | S-geometry-002 |

## comparison only

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Private research NHD polygons for Guntersville, Wheeler, Wilson, Pickwick (private worktree) | Sector (private) | 1 | 4 | 2026-10-08 | static | bulk (machine) | private | coverage | S-geometry-019 |

## consumer audit

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Sector-Ops MapCard / LakeDetail Info | Sector (Ops repo) | 1 | - | - | - | code (machine) | private | coverage | S-geometry-023 |

## covariates only

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | EPA StreamCat / LakeCat; EPA NARS/NLA fish | EPA | 1 | — | — | — | bulk (machine) | public domain | — | S-species-037 |

## dam presence/height/year/purposes, hydropower flag, storage and drainage area cross-check

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | National Inventory of Dams via Esri Federal Data hosted layer NID_v1 | USACE NID (mirror: Esri_US_Federal_Data) | 4 | 501 of 621 lakes matched (460 by name+location, 41 by location+area) | 2026 snapshot | periodic | api (machine) | public domain | coverage | S-context-003 |

## delivery path

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Public bucket gs://sector-lake-surface | Sector | 1 | 599 | daily | daily | bulk (machine) | public read | coverage | S-geometry-022 |
| ACCEPTED | Firebase Hosting rewrites (Sector-Ops firebase.json) | Sector (Ops repo) | 1 | - | - | - | code (machine) | private | coverage | S-geometry-024 |

## depth/chemistry for sampled lakes; water-extent series

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | LAGOS-US, EPA NLA, ReaLSAT, EPA EROM bulk tables | various | 2 | not downloaded | — | — | bulk (machine) | various | — | S-context-022 |

## drainage area, characteristics

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | StreamStats SS-Delineate / SS-Hydro (replacement services) | USGS | 1 | not tested | — | — | api (machine) | public domain | — | S-context-008 |

## drawdown vegetation response

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Howard & Wells 2009, Wetlands Ecol Manage 17:565-583 | peer-reviewed | 2 | Felsenthal pool | 1995 | n/a | portal (machine) | publisher | floodDroughtContext | S-baselines-022 |

## fallback + validator

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | OpenStreetMap natural=water via Overpass (overpass-api.de) | OpenStreetMap contributors | 6 | 593 of 621 have a name-matched candidate | continuous | continuous | api (machine) | ODbL (share-alike on derived databases) | coverage | S-geometry-009 |

## finding TVA RestApi location ids

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NOAA NWPS gauge catalog (api.water.noaa.gov/nwps/v1/gauges) | NOAA/NWS | 1 | bbox query for the TN valley returned 750 gauges | live | live | api (machine) | public domain | — | S-context-018 |

## fluctuating-water share inside the polygon and in a 150 m outside ring

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | JRC Global Surface Water v1.4 occurrence and seasonality (tile 90W_40N) | EC JRC / Google (Pekel et al. 2016) | 2 | 105 directory lakes inside the tile (SE US) incl. all 5 pilots | 1984-2021 | static | bulk (machine) | CC BY 4.0 / Copernicus | coverage | S-context-013 |

## guide availability

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | Utility operator pages (Alabama Power, Duke Energy, Georgia Power, Santee Cooper, LCRA) | operators | 6 | Alabama Power 8, Duke 8 directory lakes | n/a | n/a | portal (machine) | unknown | operatorPlan | S-baselines-019 |

## historic mean annual flow at the dam outlet; reference for EROM

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS NWIS Site / Daily values / Statistics services | USGS | 1 | 310 directory lakes list a USGS gauge; 5 pilots' tailwater/river gauges inspected | varies | daily | api (machine) | public domain | coverage | S-context-011 |

## independent QA, holes test

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | JRC Global Surface Water occurrence v1.4 (2021) | EC JRC | 2 | 100% of footprint | 1984-2021 | static | bulk (machine) | free and open; cite Pekel et al. 2016 | coverage | S-geometry-007 |

## inland reservoir bathymetry

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | NOAA NCEI bathymetry / USGS topobathymetric lidar | NOAA / USGS | 1 | not tested | — | — | portal (machine) | public | — | S-context-020 |

## lake->HUC8 join key for NAS and range tables

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS WBD ArcGIS MapServer layer 4 (HUC8 by point) | USGS | 1 | 621 of 621 lakes resolved | — | periodic | api (machine) | public domain | — | S-species-016 |

## level fluctuation affects lake ecological processes

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Wantzen et al. 2008, Hydrobiologia 613:1-4 | peer-reviewed editorial | 2 | n/a | 2008 | n/a | pdf (machine) | publisher | floodDroughtContext | S-baselines-021 |

## littoral habitat sensitivity to level fluctuation

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Zohary & Ostrovsky 2011, Inland Waters 1:47-59 | peer-reviewed | 2 | n/a | 2011 | n/a | pdf (machine) | publisher | floodDroughtContext | S-baselines-020 |

## littoral spawners depend on timing/variability of water levels

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Vaisvil, Caldwell, Frey 2022, J Fish Wildl Manag 13 | peer-reviewed | 2 | single reservoir | 2017-2018 | n/a | pdf (machine) | open | floodDroughtContext | S-baselines-023 |

## live guide/zone; 2-year history only

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | TVA RestApi operating-guide | Tennessee Valley Authority | 1 | 16 TVA directory lakes (15 with GuideCurve, 9 with zones) | 2 calendar years | daily | api (machine) | TVA public data (terms not reviewed) | operatorPlan, historyQuality | S-baselines-001 |

## live pool only

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | TVA RestApi observed-data-48-hours / observed-data | Tennessee Valley Authority | 1 | TVA lakes | 48 hours | hourly | api (machine) | TVA public data | sourceAuthority | S-baselines-002 |

## mean annual inflow, drainage area, stream order at the dam; residence time = storage / qema

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NHDPlus HR MapServer, NetworkNHDFlowline layer (VAA + EROM) | USGS National Hydrography | 1 | 499 of 501 lakes with a matched dam coordinate returned a flowline (envelope +-0.004 deg) | NHDPlus HR 2020s | static | api (machine) | public domain | coverage | S-context-001 |

## methodology test series

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | CWMS timeseries (Hartwell, Cave Run, Allatoona, Pueblo, Shasta) | USACE SAS/LRL/SAM/SPA/SPK | 1 | Hartwell 1962+, Pueblo 1998+, Cave Run 2002+, Allatoona 2007+, Shasta 2013+ | 1962-2026 | varies | api (machine) | public | seasonalBaseline | S-baselines-015 |

## modeled depth and shallow-area fraction

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | GLOBathy basic parameters and head-area-volume relationships | Khazaei et al. 2022, Sci. Data; figshare | 2 | keyed by Hylak_id: available for every HydroLAKES-matched lake (554) | model | static | bulk (machine) | CC0 | coverage | S-context-006 |

## natural-lake test series

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NOAA CO-OPS daily_mean, Lake Erie at Cleveland (9063063) | NOAA CO-OPS | 1 | Lake Erie | 1962-2026 fetched | daily | api (machine) | public domain | seasonalBaseline | S-baselines-016 |
| ACCEPTED | USGS NWIS daily values, Lake Champlain at Burlington (04294500, 62614) | USGS | 1 | Lake Champlain | 1907-2026 | daily | api (machine) | public domain | seasonalBaseline | S-baselines-017 |

## network attributes

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | NHDPlus HR (REST NHDPlus_HR/MapServer/9, National Release 2 GDB 31.3 GB) | USGS | 1 | same as NHD HR | release 2 2026-02-11 | release | bulk (machine) | public domain | — | S-geometry-004 |

## normal-pool extent

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | USGS 3DEP elevation ImageServer (DEM pool extent at fullPoolFt) | USGS | 1 | n/a | varies | varies | api (machine) | public domain | — | S-geometry-014 |

## observed record in waterbody

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | GBIF occurrence search API (14 target taxa, lake bbox + point-in-polygon) | GBIF | 5 | 282 lakes iNaturalist, 181 museum, 73 MARIS, 21 other (any target species) | museum 1900s-2026 | continuous | api (machine) | per-dataset (CC0 / CC-BY / CC-BY-NC) | — | S-species-003 |

## observed record in waterbody (recent)

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | iNaturalist research-grade observations (via GBIF dataset 50c9509d) | iNaturalist | 6 | 282 of 621 lakes (any target species) | 2010s-2026 | continuous | api (machine) | CC BY-NC 4.0 (dataset-level) | — | S-species-004 |

## observed record in waterbody, HUC8 occurrence, failed/eradicated

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS Nonindigenous Aquatic Species (NAS) occurrence API v2 | USGS | 1 | 300 of 621 lakes have >=1 record of a target species in/at polygon (+500 m); common carp 62,026 records | 1830-2026 | continuous | api (machine) | CC0 (per GBIF dataset record); asks publishers to contact NAS team | — | S-species-002 |

## operator override

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | State portals (e.g. TWDB existing-reservoir boundaries) | State agencies | 1 | TX only (example) | 2012-era | irregular | portal (machine) | public | — | S-geometry-016 |

## operatorPlan, floodDroughtContext candidates

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USACE CWMS levels API | USACE (all districts on the public host) | 1 | 143 of 621 matched; 132 with flood-pool bottom/top of conservation, 58 seasonal guide, 89 drought/bottom of conservation | n/a (current definitions) | n/a | api (machine) | public | operatorPlan, floodDroughtContext | S-baselines-014 |

## other

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | USGS MARIS Wisconsin fish sampling 1945-2014 (ScienceBase 53c57a0be4b0b58d96eeb70b) | USGS | 1 | — | 1945-2014 | static | bulk zip 16 MB (machine) | public domain | — | S-species-034 |
| LEAD | Fishes of Minnesota mapper (CSV/shapefile) | MN DNR | 3 | — | 1808-2012 | static | bulk (machine) | MN DNR | — | S-species-035 |

## outflow/inflow/spill/power (release context) and storage-vs-elevation => empirical stage-area curve

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USACE CWMS Data API (cwms-data.usace.army.mil/cwms-data) | USACE | 1 | 177 directory lakes carry a cwmsOffice; 53 CWMS projects with BOTH daily Elev and Stor series matched to 52 directory polygons within 12 km (SWT 11, LRL 15, SPK 10, MVK 7, SAM 3, SAS 3, NAB 3, SPL 1) | 1962-2026 | hourly raw / daily archive | api (machine) | public domain | coverage | S-context-010 |

## pilot geometry

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Sector-mapbox FishIntel cache and app assets (Guntersville) | Sector (iOS repo) | 1 | 1 lake | 2026-09-19 | static | bulk (machine) | USGS public domain | coverage | S-geometry-018 |

## pilot history 2022-10 on; same stream for all TVA dams

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NWS/TVA HADS DCP pool elevation (HP) via IEM | NWS HADS archived by Iowa Environmental Mesonet | 1 | 16 TVA directory lakes (12 beyond the pilots probed on 2023-06-15) | 2022-10-27 to today | hourly (15-min stamps, hourly HP) | api (machine) | public domain (NWS); IEM requests polite use | historyQuality, seasonalBaseline, sourceAuthority | S-baselines-010 |

## pool-extent layer + validator

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USACE Reservoirs usace_rez | USACE | 1 | 149 of 621 lakes | edited 2024-04-02 | ad hoc | api (machine) | used without restrictions per item metadata; national scale | coverage | S-geometry-005 |

## possible proxy for other lakes

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | ResOpsUS dataset | Steyaert, Condon, Turner, Voisin (Sci Data 2022) | 5 | TVA coverage unconfirmed | 1974-2020 | daily | bulk (machine) | open (figshare doi 10.6084/m9.figshare.17161415 per search result) | historyQuality | S-baselines-011 |

## pre-spawning rise vs year class

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | Stoll et al. 2013, J Applied Ichthyology (pre-spawning water-level increase and year-class strength) | peer-reviewed | 2 | n/a | 2013 | n/a | pdf (machine) | publisher | floodDroughtContext | S-baselines-025 |

## range prior

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | Page & Burr, FishTraits, Georgia Biodiversity Portal and other book/portal compilations | various | 2 | — | — | — | pdf/portal (machine) | — | — | S-species-038 |

## real bathymetry/hypsometry for Texas reservoirs

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | TWDB volumetric and hydrographic surveys | Texas Water Development Board | 1 | regional | survey dates | per survey | portal (machine) | public | — | S-context-019 |

## reference

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | HydroLAKES v10 | HydroSHEDS / McGill | 5 | 587 of 621 matched | ~2000 water mask, v10 2016 | static | bulk (machine) | HydroSHEDS licence: free with attribution (verify) | — | S-geometry-008 |
| LEAD | GeoDAR / GRanD reservoir polygons (Zenodo) | Zenodo | 5 | n/a | n/a | n/a | bulk (machine) | CC | — | S-geometry-015 |

## registry audit

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Engine lake directory source (docs/data/Sector_Lakes_APIs_2.xlsx -> LakeDirectory.swift -> GET /lakes) | Sector | 1 | 621 | generated | deploy | api (machine) | private | coverage | S-geometry-021 |

## release / tailwater / inflow data for the TVA chain; predicted outflow of an upstream dam equals the next pool's inflow within 0.3-4 %

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | TVA RestApi observed-data / predicted-data per dam (NWS-style location id) | TVA | 1 | 16 of 16 TVA directory lakes verified returning rows (GVDA1 WHLA1 WLSA1 PICT1 NKJT1 CKDT1 FLDT1 DUGT1 KYDK2 NRST1 FONN7 WBOT1 CRKT1 HIWN7 SHDT1 TMFT1) | live ~8 h | hourly, ~1 h lag | api (machine) | public TVA site (no stated licence) | coverage | S-context-009 |

## river-reservoir chain: which directory lakes lie downstream/upstream on the main stem; nearby NWIS gauges and reference dams

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS NLDI (Network Linked Data Index) linked-data API | USGS | 1 | 377 of 501 lakes with a dam coordinate navigated (DM 250 km) for upstream/downstream directory-lake relations; NLDI throttled after ~1,000 calls, remaining 124 pending (resumable) | static network | static | api (machine) | public domain | coverage | S-context-002 |

## shoreline slope, horizontal run per vertical foot

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS 3DEP seamless DEM ImageServer getSamples | USGS National Map | 1 | sampled 4 offsets x ~700 shore points per lake for 5 pilots + 51 validation lakes | 2000s-2020s | static | api (machine) | public domain | coverage | S-context-012 |

## state/range prior

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NatureServe Explorer API (speciesSearch, state/province native/exotic + ranks) | NatureServe | 5 | state-level only | — | periodic | api (machine) | NatureServe terms (check) | — | S-species-011 |

## storage (GRanD capacity for reservoirs), Lake_type, modeled discharge, residence time

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | HydroLAKES v1.0 point file (pour points with lake attributes) | HydroSHEDS / McGill (Messager et al. 2016) | 5 | 554 of 621 lakes matched (348 name+location, 206 location+area ratio 0.4-2.5 with one-to-one conflict resolution, 67 none incl. 22 without polygons); ~9 % of audited named geometry matches were wrong neighbours | ~2000s mask | static | bulk (machine) | CC BY 4.0 (HydroSHEDS licence) | coverage | S-context-005 |

## summer operating range held through Labor Day

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | TVA 2004 preferred-alternative press release (web-harvest copy) | TVA via webharvest.gov | 1 | Guntersville, Wheeler, Pickwick, Chickamauga | 2004 | n/a | portal (machine) | US government | operatorPlan | S-baselines-026 |

## tributary mouth counts by catchment-size class per shoreline km

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NHDPlus HR flowlines for tributary-mouth detection (layer 3, totdasqkm>=5) | USGS | 1 | 5 pilots (361-1,101 flowlines each, 42-136 s/lake) | static | static | api (machine) | public domain | coverage | S-context-016 |

## upgrade path

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS 3DHP_all waterbody (REST 3DHP_all/MapServer/60) | USGS | 1 | 609 of 621 matched | 2023-09-14 (602), 2025-2026 (7) | annual | api (machine) | public domain | coverage | S-geometry-003 |
