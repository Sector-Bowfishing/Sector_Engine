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

## binding

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS NWIS site service + series catalog (legacy waterservices) | USGS | 1 | — | 1900-present | daily/15min | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-001 |
| LEAD | USGS OGC API (api.waterdata.usgs.gov/ogcapi/v0) | USGS | 1 | — | - | - | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-002 |
| ACCEPTED | USACE CWMS Data API (cwms-data.usace.army.mil/cwms-data) | USACE | 1 | — | to 1950s | 15min-daily | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-003 |
| ACCEPTED | USACE Access2Water reporting API | USACE | 1 | — | latest + levels | hourly-daily | api (machine) | US public domain / public data | sourceAuthority, operatorPlan, floodDroughtContext, trendQuality | S-binding-004 |
| ACCEPTED | USBR RISE API | USBR | 1 | — | decades | daily | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-005 |
| ACCEPTED | TWDB Water Data for Texas reservoirs | Texas Water Development Board | 1 | — | 1999-present | daily | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-006 |
| ACCEPTED | NOAA NWPS gauges API | NOAA/NWS | 1 | — | latest ~30d | 15min-hourly | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-007 |
| ACCEPTED | NOAA CO-OPS Great Lakes water level | NOAA | 1 | — | decades | 6min | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-008 |
| ACCEPTED | TVA RestApi (locations, observed-data-48-hours, operating-guide) | TVA | 1 | — | 48h + 2y guide | hourly | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-009 |
| ACCEPTED | National Inventory of Dams (USACE) via hosted ArcGIS FeatureServer NID_v1 | USACE NID | 1 | — | current | periodic | api (machine) | US public domain / public data | coverage | S-binding-010 |
| LEAD | WWDH (Internet of Water) USACE EDR mirror | Internet of Water / Western Water Data Hub | 3 | — | - | - | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-012 |
| LEAD | California CDEC JSONDataServlet | CA DWR | 1 | — | decades | daily | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-013 |
| LEAD | Colorado DWR CDSS telemetry REST | CO DWR | 1 | — | - | 15min | api (machine) | US public domain / public data | sourceAuthority, trendQuality, historyQuality | S-binding-014 |
| LEAD | Operator pages without APIs: Alabama Power, Duke Energy, Georgia Power, Santee Cooper, SRP, LCRA, Dominion, state DEPs | operators | 4 | — | - | - | portal (machine) | US public domain / public data | sourceAuthority | S-binding-015 |
| ACCEPTED | NOAA CO-OPS Great Lakes water level (IGLD85) | NOAA NOS CO-OPS | 7 | 13 lakes with live candidate | 1900-2026 (Duluth, Buffalo, Cleveland, Toledo, Rochester, Oswego, Harbor Beach, Mackinaw City); 1950s-70s for most others; Green Bay East 2009-, only 5 complete years | — | api (machine) | NOAA public domain | coverage, historyQuality | S-gaps-001 |
| ACCEPTED | USACE LRE CWMS Great Lakes lake-wide mean levels (gpl-ccp) | USACE Detroit/Buffalo (Coordinating Committee on Great Lakes Basic Hydraulic and Hydrologic Data) | 6 | 13 lakes with live candidate | 2020-2026 only (5 complete years) | — | api (machine) | USACE public | coverage, historyQuality | S-gaps-002 |
| ACCEPTED | MN DNR Cooperative Stream Gaging (CSG) API | Minnesota DNR / PCA / USACE / USGS (providers) | 6 | 2 lakes with live candidate | White Bear 2013-2026 (hourly->daily, 8 complete years); Vermilion outlet 2008-2026 (stage, winter gaps -> 0 complete years) | — | api (machine) | MN DNR public (provisional data) | coverage, historyQuality | S-gaps-004 |
| ACCEPTED | USGS NWIS IV/DV state sweep (lake-elevation params 62614/62615/62616/00062/72020/00065) | USGS | 7 | 8 lakes with live candidate | 1933-2026 West Okoboji/Spirit; 1974- Houghton (+offset 1129.61 validated to 0.00 ft vs live 62615); 1988- Longview; 1993- Green Lake & Chain O'Lakes; 2008- Clinton; 2016- Minnetonka | — | api (machine) | USGS public domain | coverage, historyQuality | S-gaps-005 |
| ACCEPTED | USACE CWMS (NWDM, SWT, MVP, MVR) pool/elev series | USACE Omaha / Tulsa / St. Paul / Rock Island Districts | 7 | 6 lakes with live candidate | see candidates (hourly record, daily means computed) | — | api (machine) | USACE public | coverage, historyQuality | S-gaps-006 |
| ACCEPTED | Environment & Climate Change Canada / Water Survey of Canada real-time + daily-mean hydrometric (OGC API) | WSC (contributor Lake of the Woods Control Board) | 7 | 1 lakes with live candidate | 1913/1962/1963/1983 - 2025 daily + last 30 d realtime (gap Jan-Sep 2026) | — | api (machine) | Open Government Licence - Canada | coverage, historyQuality | S-gaps-007 |
| ACCEPTED | NWS National Water Prediction Service (NWPS) gauges | NOAA/NWS (forecast offices + RFCs) | 4 | 8 lakes with live candidate | none (30 d window) | — | api (machine) | NOAA public domain | coverage, historyQuality | S-gaps-008 |
| ACCEPTED | CNPPID Lake & Reservoir Elevations table | Central Nebraska Public Power & Irrigation District | 6 | 2 lakes with live candidate | none (only 1 wk/1 mo/1 yr ago values) | — | portal | public web page (operator) | coverage, historyQuality | S-gaps-009 |
| ACCEPTED | NPPD Reservoir Elevations and Canal Flows (v1.nppd.com) | Nebraska Public Power District | 6 | 1 lakes with live candidate | none in HTML (12-month and 1-month graph images via chart.aspx) | — | portal | public web page (operator) | coverage, historyQuality | S-gaps-011 |
| ACCEPTED | NIPSCO 'Current Lake Levels' (Norway/Oakdale hydro) | NIPSCO (NiSource) | 6 | 2 lakes with live candidate | none | — | portal | public web page (operator) | coverage, historyQuality | S-gaps-012 |
| ACCEPTED | We Energies / Wisconsin Public Service / Wisconsin River Power hydro project data page | WPS / We Energies / WRPCO | 6 | 1 lakes with live candidate | none | — | portal | public web page (utilities) | coverage, historyQuality | S-gaps-013 |
| ACCEPTED | Alliant Energy hydro flow-rate page (Prairie du Sac, Kilbourn) | Alliant Energy | 6 | 1 lakes with live candidate | none | — | portal | public web page (utility) | coverage, historyQuality | S-gaps-014 |
| ACCEPTED | CWLP Lake Springfield water level table | City Water, Light & Power (Springfield IL) | 6 | 1 lakes with live candidate | 2 years of ~weekly reads (not daily) | — | portal | public web page (utility) | coverage, historyQuality | S-gaps-015 |
| LEAD | Minnesota (Lake Minnetonka) MCWD water level updates | Minnehaha Creek Watershed District | 6 | 1 lakes with live candidate | none | — | portal | public / US gov or operator web data | coverage, historyQuality | S-gaps-017 |
| LEAD | Apps.sd.gov Measured Lakes (SD DENR/GFP spring+fall surface elevations) | South Dakota DANR | 5 | 0 lakes with live candidate | none | — | portal | public / US gov or operator web data | coverage, historyQuality | S-gaps-018 |
| ACCEPTED | SD glacial lakes live elevation | NWS ABR / USACE Omaha / USGS | 5 | 1 lakes with live candidate | none | — | api (machine) | public / US gov or operator web data | coverage, historyQuality | S-gaps-019 |
| ACCEPTED | Michigan inland lakes (Burt, Torch, Gull, Elk, Charlevoix, Houghton) | USGS MI / EGLE / county | 7 | 2 lakes with live candidate | none | — | api (machine) | public / US gov or operator web data | coverage, historyQuality | S-gaps-022 |
| ACCEPTED | Iowa lakes (East Okoboji, Big Creek, Lake Macbride) | USGS IA / USACE MVR / Iowa DNR | 6 | 2 lakes with live candidate | none | — | api (machine) | public / US gov or operator web data | coverage, historyQuality | S-gaps-024 |
| LEAD | per-lake dead end: Big Stone Lake\|SD | various | 1 | 0 lakes with live candidate | none | — | portal | public / US gov or operator web data | coverage, historyQuality | S-gaps-026 |
| ACCEPTED | NHDES real-time lake-level platform (RTI 'Amanzi', Dam Bureau telemetry) | NH Department of Environmental Services, Dam Bureau | 7 | 8 lakes with live candidate | 2010-04 .. now, hourly (daily means in history/nhdes_*) | — | api (machine) | Public data; NHDES disclaimer: provisional, informational, use at own risk | coverage, historyQuality | S-gaps-050 |
| ACCEPTED | Brookfield Renewable 'Safe Waters' public facility pages | Brookfield Renewable North America (dam owner/operator; Great Lakes Hydro America, Brookfield White Pine, Brookfield Power PA) | 6 | 6 lakes with live candidate | none (current value only) | — | portal | Public safety information; terms not stated. Hourly polling of ~6 pages is light. | coverage, historyQuality | S-gaps-051 |
| ACCEPTED | USGS NWIS (iv/dv/site services), 12-state series-catalog scan | U.S. Geological Survey | 7 | 4 lakes with live candidate | West Grand 2010-, Youghiogheny 2007- (dv to 2015 + iv), Lake Arthur 2007-, Haven Lake 2015- | — | api (machine) | Public domain (provisional data) | coverage, historyQuality | S-gaps-052 |
| ACCEPTED | USACE CWMS data API (NAE, LRP) | U.S. Army Corps of Engineers | 7 | 1 lakes with live candidate | Mansfield Hollow 2005-2026 | — | api (machine) | Public domain | coverage, historyQuality | S-gaps-054 |
| ACCEPTED | NOAA/NWS NWPS gauges (api.water.noaa.gov/nwps/v1) | NOAA National Water Prediction Service | 5 | 3 lakes with live candidate | none (about 30 d) | — | api (machine) | Public domain | coverage, historyQuality | S-gaps-055 |
| ACCEPTED | NJ Water Supply Authority operations data (Manasquan page + Raritan weekday PDF) | New Jersey Water Supply Authority | 6 | 2 lakes with live candidate | none online (accumulate) | — | pdf | Public | coverage, historyQuality | S-gaps-056 |
| LEAD | MWRA Quabbin/Wachusett reservoir levels | Massachusetts Water Resources Authority / MA DCR | 6 | 0 lakes with live candidate | monthly since 2005 (not daily) | — | portal | Public | coverage, historyQuality | S-gaps-057 |
| LEAD | Maryland / Baltimore reservoirs (Baltimore City DPW, MDE drought reports, WSSC, Constellation Conowingo) | Baltimore City DPW; MDE; WSSC Water; Constellation | 6 | 1 lakes with live candidate | none | — | portal | n/a | coverage, historyQuality | S-gaps-063 |
| LEAD | Connecticut MDC (Barkhamsted/Nepaug) reservoir status | Metropolitan District Commission | 6 | 0 lakes with live candidate | none | — | portal | n/a | coverage, historyQuality | S-gaps-064 |
| ACCEPTED | Duke Energy Lake View API (api.hydro-derived.duke-energy.app) | Duke Energy | 7 | 8 lakes with live candidate | 5 y rolling daily mean (2021-10-13+) = 4 complete calendar years (Robinson: since 2022-05-26) | — | api (machine) | public web-app endpoint; terms not stated (Duke site ToS apply); API is undocumented -> may change | coverage, historyQuality | S-gaps-087 |
| ACCEPTED | NWPS Catawba/Keowee chain gauges (Duke relay) | NOAA NWS / Duke Energy | 6 | 7 lakes with live candidate | ~30 days only | — | api (machine) | NOAA public domain | coverage, historyQuality | S-gaps-088 |
| ACCEPTED | SJRWMD WISKI-Web public data store (mdp.sjrwmd.com/data/internet) | St. Johns River Water Management District | 7 | 7 lakes with live candidate | Daily means since 1992-2005 depending on station (Harris 1993, George 1992, Jesup 1996, Lochloosa/Orange 1995, Apopka NP 2005, Jake Voss 2020, Griffin Emeralda 2020) | — | bulk (machine) | SJRWMD public data; no explicit licence | coverage, historyQuality | S-gaps-089 |
| ACCEPTED | USACE CWMS data API (SAJ) - SFWMD stage mirror | USACE Jacksonville / SFWMD | 7 | 1 lakes with live candidate | 2010-2026 hourly | — | api (machine) | USACE public | coverage, historyQuality | S-gaps-090 |
| ACCEPTED | USACE CWMS data API (SAM) - Alabama Power Logan Martin | Alabama Power / USACE Mobile | 7 | 1 lakes with live candidate | 2017-2026 | — | api (machine) | USACE public | coverage, historyQuality | S-gaps-091 |
| ACCEPTED | USGS NWIS 02193900 THURMOND LAKE NEAR PLUM BRANCH, SC | USGS / USACE Savannah | 7 | 2 lakes with live candidate | 1954-2026 (68 complete years) | — | api (machine) | USGS public | coverage, historyQuality | S-gaps-092 |
| ACCEPTED | USGS NWIS 02079490 + CWMS SAW 'ROA JHK' (John H. Kerr) | USACE Wilmington / USGS | 7 | 1 lakes with live candidate | 2005-2026 (20 complete years) | — | api (machine) | public | coverage, historyQuality | S-gaps-093 |
| ACCEPTED | CWMS SAM Whitten / Stennis (Tenn-Tom) | USACE Mobile | 7 | 2 lakes with live candidate | Whitten 2018-; Stennis 2018- (after +100 ft correction) | — | api (machine) | USACE public | coverage, historyQuality | S-gaps-094 |
| ACCEPTED | CWMS MVK Chicot Pumping Plant landside | USACE Vicksburg | 6 | 1 lakes with live candidate | 2011-2026 hourly (11 complete years) | — | api (machine) | USACE public | coverage, historyQuality | S-gaps-095 |
| ACCEPTED | CWMS MVN False River at New Roads (52330) | USACE New Orleans | 6 | 1 lakes with live candidate | 1996-2026 | — | api (machine) | USACE public | coverage, historyQuality | S-gaps-096 |
| ACCEPTED | USGS NWIS 07027000 Reelfoot Lake near Tiptonville TN | USGS | 7 | 1 lakes with live candidate | 1984-2026 | — | api (machine) | USGS public | coverage, historyQuality | S-gaps-097 |
| ACCEPTED | USGS NWIS 073802302 Pass Manchac nr Lake Maurepas | USGS | 5 | 1 lakes with live candidate | 2022-2026 | — | api (machine) | USGS public | coverage, historyQuality | S-gaps-098 |
| ACCEPTED | NOAA CO-OPS 8770475 Port Arthur TX | NOAA CO-OPS | 6 | 1 lakes with live candidate | 2012-2026 (patchy 2013-2017) | — | api (machine) | NOAA public domain | coverage, historyQuality | S-gaps-099 |
| ACCEPTED | AEP / Appalachian Power plant-levels API | AEP (Appalachian Power) | 7 | 1 lakes with live candidate | none (poll-and-archive) | — | api (machine) | public web-app endpoint | coverage, historyQuality | S-gaps-100 |
| ACCEPTED | NWPS Dominion/AEP/USACE pool relays (GASN7, SMIV2, CHDS1, KERV2) | NOAA NWS | 6 | 13 lakes with live candidate | ~30 days | — | api (machine) | NOAA public domain | coverage, historyQuality | S-gaps-101 |
| ACCEPTED | ARWA Chesdin Reservoir Daily Status Report | Appomattox River Water Authority | 6 | 1 lakes with live candidate | none | — | portal | public web page | coverage, historyQuality | S-gaps-102 |
| LEAD | Dominion Energy Lake Gaston water levels page | Dominion Energy | 7 | 0 lakes with live candidate | none | — | portal | public web page | coverage, historyQuality | S-gaps-106 |
| LEAD | Re-pointing notes for wave-1 'candidates-rejected' lakes in this area | n/a | 3 | 0 lakes with live candidate | n/a | — | analysis | n/a | coverage, historyQuality | S-gaps-114 |
| ACCEPTED | USBR Pacific Northwest Hydromet (pn-bin instant.pl / daily.pl) | US Bureau of Reclamation, Columbia-Pacific NW Region | 1 | 6 lakes with live candidate | CSC 1979-, CRE 1982-, POT 1952-, BNK 1951-, HEN 1977-, PAY 1943- (daily.pl; a 655 ft sentinel in PAY 1991 is removed by the outlier filter) | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-115 |
| ACCEPTED | California Data Exchange Center (CDEC) JSONDataServlet | California DWR (aggregator for PG&E, USBR, USACE, utilities) | 2 | 2 lakes with live candidate | BER 1985- (26 complete yrs), ALM 1985- (gappy, 11 complete yrs by the 90% rule); sentinels -1/959746 ft dropped | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-116 |
| ACCEPTED | Salt River Project Watershed Connection public JSON (streamflow.watershedconnection.com/api/watershedconnectiondata) | Salt River Project (SRP) | 1 | 4 lakes with live candidate | 2023-10-13 .. now (about 3 yrs, 5-min; daily means written) | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-117 |
| ACCEPTED | Colorado DWR / CDSS telemetry REST API | Colorado Division of Water Resources (data from Denver Water) | 2 | 1 lakes with live candidate | 1987-06..2002 + 2021..now (16 complete years by the 90% rule; sentinel values dropped) | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-118 |
| ACCEPTED | USACE CWMS Data API, office NWDP (Northwest Division portal) | US Army Corps of Engineers NWD (republishing USBR, Seattle District, Tacoma, Seattle City Light data) | 1 | 2 lakes with live candidate | LWSC 2001-, GCL 1960- | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-119 |
| ACCEPTED | NWRFC station XML (xml.cgi, pe=HF forebay elevation) | NOAA/NWS Northwest River Forecast Center (relay of Tacoma Power, USBR, utilities) | 4 | 2 lakes with live candidate | none (10 days) | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-120 |
| ACCEPTED | USGS NWIS (iv, dv, site) - systematic state sweep | US Geological Survey | 1 | 6 lakes with live candidate | GSL 10010000 1900-, UKL 11507000 1904-, Payette 1965-, Henrys 1977-, Georgetown 2013-, Eagle Nest 2013- (dv) | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-121 |
| ACCEPTED | Utah Lake Commission live data feed (WordPress admin-ajax action=ulc_data) | Utah Lake Commission, data stated to originate from Utah Division of Water Rights | 3 | 1 lakes with live candidate | about 90 days only | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-122 |
| ACCEPTED | USBR RISE API (data.usbr.gov/rise/api/result) | US Bureau of Reclamation | 1 | 2 lakes with live candidate | daily from dam closure (1960s) | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-123 |
| LEAD | NOAA NWPS gauges API (api.water.noaa.gov/nwps/v1/gauges/{lid}) | NOAA National Water Prediction Service | 4 | 0 lakes with live candidate | none | — | api (machine) | US public domain / public data | coverage, historyQuality | S-gaps-125 |
| LEAD | Tacoma Public Utilities - River Flows & Lake Levels page | Tacoma Power | 2 | 0 lakes with live candidate | none | — | portal | US public domain / public data | coverage, historyQuality | S-gaps-126 |
| LEAD | Oregon Water Resources Department near-real-time hydrographics | Oregon WRD | 2 | 0 lakes with live candidate | none | — | portal | US public domain / public data | coverage, historyQuality | S-gaps-127 |
| LEAD | Denver Water supply data (Water Watch report / reservoir page) | Denver Water | 2 | 0 lakes with live candidate | none | — | pdf | US public domain / public data | coverage, historyQuality | S-gaps-128 |
| LEAD | Mono Lake level tables (Mono Lake Committee / LADWP) | Mono Lake Committee, LADWP | 2 | 0 lakes with live candidate | none | — | portal | US public domain / public data | coverage, historyQuality | S-gaps-129 |
| LEAD | Lassen County Eagle Lake monthly survey | Lassen County Surveyor | 3 | 0 lakes with live candidate | none | — | portal | US public domain / public data | coverage, historyQuality | S-gaps-130 |
| ACCEPTED | USGS NWIS iv bounding-box scan for 00062/62614/62615/62616/72020/72022/00065 (binding2/usgs_scan.py) | USGS | 1 | — | — | — | api (machine) | public data | coverage, historyQuality | S-gaps-181 |
| LEAD | USGS gage height + site altitude (alt_va) as derived elevation | USGS | 1 | — | — | — | api (machine) | public data | coverage, historyQuality | S-gaps-182 |
| ACCEPTED | IEM HADS raw DCP archive (mesonet.agron.iastate.edu/cgi-bin/request/hads.py) as NWPS history | Iowa Environmental Mesonet / NWS | 2 | — | — | — | api (machine) | public data | coverage, historyQuality | S-gaps-183 |
| ACCEPTED | NWPS as DIRECT_LAKE_GAUGE (acceptability test) | NOAA/NWS | 1 | — | — | — | api (machine) | public data | coverage, historyQuality | S-gaps-184 |

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

## floodDroughtContext (tier 2)

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | TWDB recent-conditions: conservation_pool_elevation, dead_pool_elevation, flood_control_lake | TWDB | 1 | 122 reservoirs; 13 core bound lakes | snapshot | n/a | api (machine) | public (US federal/state data; see source terms) | floodDroughtContext, operatorPlan | S-plan-017 |

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

## history

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | TWDB Water Data for Texas reservoir CSV | TWDB | 1 | Amistad 1968+, Falcon 1953+ | 1953 -> today | daily | api (machine) | public (US federal/state data; see source terms) | historyQuality | S-plan-005 |
| ACCEPTED | NOAA CO-OPS daily_mean (IGLD) station 9034052 | NOAA CO-OPS | 1 | Lake St. Clair | 1995 -> 2026 | daily | api (machine) | public (US federal/state data; see source terms) | historyQuality | S-plan-006 |
| ACCEPTED | NWS RVDHUN text archive (Nickajack HW 2007-2021, Tims Ford 2003-2013) | NWS Huntsville via IEM AFOS | 1 | Nickajack (13 complete y with HADS), Tims Ford (6 y) | 2003 -> 2021 | daily | api (machine) | public (US federal/state data; see source terms) | historyQuality | S-plan-007 |

## history for NWPS-relay lakes: same DCP stream that NWPS serves live

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | IEM HADS archive, pool elevation stream HPIR* by NWS location id | NWS HADS via Iowa Environmental Mesonet | 1 | 34 NWPS-bound lakes (27 core + 7 flagged) lacked >= 5 y; archive starts 2010-12/2011-01 | 2011 -> today | 15 min - daily | api (machine) | public (US federal/state data; see source terms) | historyQuality, seasonalBaseline | S-plan-001 |

## history legs

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | CWMS Data API timeseries (unit=EN) on alternative tsids | USACE CWMS | 1 | Chatfield 40 y, Buckhorn 23 y, Okatibbee 14 y, Pend Oreille (Hope) 26 y, Lake Washington 30 y, Kentucky Lake 27 y | 1984 -> 2026 | 15 min - 1 h | api (machine) | public (US federal/state data; see source terms) | historyQuality, seasonalBaseline | S-plan-004 |

## history legs for lakes whose binding feed is a relay or a different USGS statistic

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | USGS NWIS dv statCd 30800/32400 and iv->daily; gage height 00065 with calibrated datum offset | USGS | 1 | Taneycomo 29 y, Herrington 15 y, Topaz 25 y, Indian Lake NY 100+ y, Priest 69 y, Bartlett 48 y, D'Arbonne 16 y, Ute 15 y (iv), Buckeye 6 y (iv), Lahontan 24 y (two parameter codes) | 1900 -> 2026 | daily | api (machine) | public (US federal/state data; see source terms) | historyQuality, seasonalBaseline | S-plan-003 |

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

## normal pool only

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | KARS GeoPlatform PhysicalLakeData (76 lakes, Elev_ft) | Kansas Water Office / KARS | 4 | 76 Kansas lakes | static | n/a | api (machine) | public (US federal/state data; see source terms) | floodDroughtContext | S-plan-023 |

## normal pool only (not an operator flood-pool bottom)

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | NWPS gauge normalThreshold | NOAA NWPS | 3 | 11 of 48 NWPS-bound gauges carry a non-zero value | snapshot | n/a | api (machine) | public (US federal/state data; see source terms) | floodDroughtContext | S-plan-018 |

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

## operatorPlan

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | TVA RestApi operating-guide (GuideCurve, TopOpZone, BtmOpZone, TopOfGates) | TVA | 1 | 17 bound TVA lakes | 2 calendar years | daily | api (machine) | public (US federal/state data; see source terms) | operatorPlan | S-plan-016 |
| LEAD | FERC eLibrary (docket documents) and operator pages: Santee Cooper (P-199), Appalachian Power Smith Mountain (P-2210), Duke Catawba-Wateree (P-2232), GRDA Pensacola | FERC / operators | 1 | 0 of 8 Duke lakes bound; Santee Cooper, SML, Norman bound or bindable | n/a | n/a | pdf | public (US federal/state data; see source terms) | operatorPlan | S-plan-020 |
| LEAD | lakes.santeecooper.com/lakes (daily table incl. rule curve) | Santee Cooper | 1 | Lake Marion, Lake Moultrie | daily | daily | portal (machine) | public (US federal/state data; see source terms) | operatorPlan | S-plan-021 |

## operatorPlan validation

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | GRDA Datawrapper: historic and current seasonal target lake elevations (monthly CSV) | Grand River Dam Authority | 1 | Grand Lake o' the Cherokees (Pensacola) | static | n/a | api (machine) | public (US federal/state data; see source terms) | operatorPlan | S-plan-022 |

## operatorPlan, floodDroughtContext

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | Access2Water locations: levels (label/type/tsid/latest), aliases (NWS Handbook 5 ID, USGS station, NIDID) | USACE Access2Water | 1 | 613 projects; 23 without coordinates are matched by alias only | snapshot | n/a | api (machine) | public (US federal/state data; see source terms) | operatorPlan, floodDroughtContext | S-plan-014 |
| ACCEPTED | CWMS /levels (all Elev levels) plus CWMS time-series guides (Elev-Guide Curve, Elev-Top Con, Elev-Zone, Elev-L1..L3) | USACE CWMS | 1 | see plan_flood_evidence.csv | snapshot | n/a | api (machine) | public (US federal/state data; see source terms) | operatorPlan, floodDroughtContext | S-plan-015 |

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

## possible fill for TVA tributary lakes and others

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| LEAD | ResOpsUS (Steyaert et al. 2022) daily storage/elevation 1980-2020, 679 reservoirs | PNNL / U. Arizona (Zenodo 5367383, 5893641) | 2 | unknown overlap with our 71 targets (TVA tributaries?) | 1980 -> 2020 | daily | bulk (machine) | public (US federal/state data; see source terms) | historyQuality | S-plan-011 |

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

## relevance of flooded vegetation and drawdown access

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | bowhuntersunited.com 'best locations and habitats for successful bowfishing' (opened); USBR news release 5214 Banks Lake 6.2 ft drawdown (opened) | community / USBR | 6 | n/a | 2023, 2025 | n/a | web | public (US federal/state data; see source terms) | operatorPlan | S-plan-024 |

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

## usgsId relay to long USGS series; normalThreshold = normal pool for 11 gauges

| Decision | Source | Org | Auth | Lake coverage | Time | Cadence | Access | License | Dimension | ID |
|---|---|---|---|---|---|---|---|---|---|---|
| ACCEPTED | NWPS gauge metadata (usgsId, normalThreshold, flood categories) | NOAA NWS NWPS API | 1 | 48 NWPS-bound lakes | snapshot | n/a | api (machine) | public (US federal/state data; see source terms) | historyQuality, floodDroughtContext | S-plan-002 |
