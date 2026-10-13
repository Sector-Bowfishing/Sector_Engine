# Depth Brain Data Source Matrix

Generated from `ledger/*.jsonl` (research only). Authority scale 1 (best: modern instrument survey by owner/USGS) to 7 (unusable). Reachability was tested by fetch; "not found" for a state is not proof that nothing exists (the scouting web-search budget ran out).

Decision counts (non-GLOBathy ledgers): {'USED_FOR_TRUTH': 21, 'USED_AS_ANCHOR': 3, 'ACCEPTED': 34, 'LEAD': 10, 'DEAD_END': 4, 'ACCEPTED_WITH_LIMITS': 1, 'REJECTED_AS_SCORE': 1}. GLOBathy truth ledger: 223 per-lake truth records (`ledger/globathy.jsonl`), summarised below.

## Scalable multi-lake measured sources and operator/federal leads

| id | source | org | type | coverage | auth | decision | licence |
|---|---|---|---|---|---|---|---|
| S-contour-001 | Minnesota DNR Lake Bathymetric Outlines, Contours, and DEM (REST MapSe | MN DNR / MN Geospatial Commo |  |  |  | USED_FOR_TRUTH | not verified (MN Geospatial Commons data |
| S-contour-002 | Indiana DNR Lake Bathymetry (IndianaMap hosted FeatureServer) | Indiana DNR Fish & Wildlife  |  |  |  | USED_FOR_TRUTH | No license stated; IN public data |
| S-contour-003 | Montana FWP Hydrography - Lakes Bathymetry (layer 4) | Montana Fish, Wildlife & Par |  |  |  | USED_FOR_TRUTH | No license stated |
| S-contour-004 | Nebraska Game & Parks Lake Contours + Lake Shapes | Nebraska Game and Parks Comm |  |  |  | USED_FOR_TRUTH | Public (NGPC open data hub) |
| S-contour-005 | North Dakota Game & Fish Lake Contours (NDGISHUB) | ND Game & Fish / ND GIS Hub |  |  |  | USED_FOR_TRUTH | 'Not for navigation' disclaimer |
| S-contour-006 | NH GRANIT / NHDES Bathymetry Lakes (lines & polygons) | NH Dept of Environmental Ser |  |  |  | USED_FOR_TRUTH | No access constraints; use at own risk;  |
| S-contour-007 | Washington Ecology Lake Bathymetry Contour Lines / Elevation Bands | WA Dept of Ecology |  |  |  | USED_FOR_TRUTH | Public; check Ecology terms |
| S-contour-008 | Michigan DNR/IFR Inland Lake Contours (DNRHydrologyOPENDATA layer 1) | Michigan DNR Fisheries / Ins |  |  |  | USED_FOR_TRUTH | Credit IFR / MDNR Fisheries / UMich |
| S-contour-009 | MassWildlife Inland Water Bathymetry (feature service)  | MassWildlife / MassGIS |  |  |  | USED_FOR_TRUTH | MassGIS open data |
| S-contour-010 | Kansas Biological Survey (KARS) Bathymetry Depth Contours (WaterResour | Kansas Biological Survey, Un |  |  |  | USED_FOR_TRUTH | No constraints; acknowledge KBS |
| S-contour-011 | FWC Bathymetry of Select Lakes in Florida (1-ft contours) | Florida FWC Fish and Wildlif |  |  |  | USED_FOR_TRUTH | Metadata: unrestricted, but 'should not  |
| S-contour-012 | OWRB Lakes of Oklahoma - Contours / Lake Points (LOK_Lakes MapServer) | Oklahoma Water Resources Boa |  |  |  | USED_FOR_TRUTH | OWRB public data |
| S-contour-013 | Illinois DNR Lake Depth and Capacity (WaterResources MapServer) | Illinois DNR Office of Water |  |  |  | USED_FOR_TRUTH | IDNR; no license stated |
| S-contour-014 | Ohio DOW Lake Bathymetry (inland lakes) MapServer | Ohio DNR Division of Wildlif |  |  |  | USED_FOR_TRUTH | ODNR; no license stated |
| S-contour-015 | WV DNR Public Fishing Lake Contours | West Virginia DNR |  |  |  | USED_FOR_TRUTH | unknown |
| S-contour-016 | NJDEP Lake Bathymetry Contours in New Jersey | NJ DEP Bureau of GIS / Fish  |  |  |  | USED_FOR_TRUTH | unknown |
| S-contour-017 | CT DEEP Lake Bathymetry Contours (Lines) | Connecticut DEEP |  |  |  | USED_FOR_TRUTH | CC0 per data.gov copy (another copy says |
| S-contour-018 | TWDB Volumetric & Sedimentation Surveys (completed surveys, GIS shapef | Texas Water Development Boar |  |  |  | USED_FOR_TRUTH | Public; TWDB asks for acknowledgment; st |
| S-contour-019 | Local/association contour services (Chippewa Flowage WI, Harveys Lake  | Chippewa Flowage Area Proper |  |  |  | USED_FOR_TRUTH | unknown |
| S-contour-020 | Local/association contour services (Chippewa Flowage WI, Harveys Lake  | Chippewa Flowage Area Proper |  |  |  | USED_FOR_TRUTH | unknown |
| S-contour-021 | Local/association contour services (Chippewa Flowage WI, Harveys Lake  | Chippewa Flowage Area Proper |  |  |  | USED_FOR_TRUTH | unknown |
| S-contour-A039 | EPA NLA 2007 DEPTHMAX |  |  |  |  | USED_AS_ANCHOR | US Government public |
| S-contour-A021 | OWRB lake points depth_max |  |  |  |  | USED_AS_ANCHOR | OWRB |
| S-contour-A022 | MI IFR max-depth points |  |  |  |  | USED_AS_ANCHOR | credit IFR/MDNR/UMich |
| S-depth-L001 | USACE IENC chart footprints + per-chart S-57 REST (ienccloud.us/arcgis | USACE | S-57 navigation charts (DEPTH_AREA, DEPT | 34 of 621 fleet lakes intersect a footprint (TN 9, MS 5, AL 4, LA 3, OK 3, MN 3, AR 2, IL  | 1 | ACCEPTED | US federal public |
| S-depth-001 | TWDB Volumetric & Sedimentation Surveys (completed surveys, GIS shapef | Texas Water Development Boar | survey: sonar-derived contours (1/2/5ft) | 123 survey directories, 203 shapefile zip links on index; 12 fleet lakes candidate-matched | 1 | ACCEPTED | Public; TWDB asks for acknowledgment; st |
| S-depth-002 | Minnesota DNR Lake Bathymetric Outlines, Contours, and DEM (REST MapSe | MN DNR / MN Geospatial Commo | contour (digitized from DNR lake maps) + | 46,306 contour lines; 7,499 outlines; 1,305 lake survey-metadata polygons (about 1,900 lak | 3 | ACCEPTED | not verified (MN Geospatial Commons data |
| S-depth-003 | Indiana DNR Lake Bathymetry (IndianaMap hosted FeatureServer) | Indiana DNR Fish & Wildlife  | contour polylines (field: contour, lake_ | 10,260 contour lines in 146 name groups (5,034 lines have blank lake_name); 982 outlines;  | 3 | ACCEPTED | No license stated; IN public data |
| S-depth-004 | Montana FWP Hydrography - Lakes Bathymetry (layer 4) | Montana Fish, Wildlife & Par | contour polylines (field CONTOUR, SOURCE | 25,512 contour lines, 706 name groups; 6 fleet lakes candidate-matched by name+state | 3 | ACCEPTED | No license stated |
| S-depth-005 | Nebraska Game & Parks Lake Contours + Lake Shapes | Nebraska Game and Parks Comm | contour polylines (Name, Depth, Elevatio | 6,143 contour lines, 155 name groups, 154 lake shapes (NGPC/USBR joint mapping program); 1 | 2 | ACCEPTED | Public (NGPC open data hub) |
| S-depth-006 | North Dakota Game & Fish Lake Contours (NDGISHUB) | ND Game & Fish / ND GIS Hub | contour polylines (CONTOUR, CONTOURINTER | 4,765 contour lines in 236 name groups; 3 fleet lakes candidate-matched by name+state | 3 | ACCEPTED | 'Not for navigation' disclaimer |
| S-depth-007 | NH GRANIT / NHDES Bathymetry Lakes (lines & polygons) | NH Dept of Environmental Ser | contour lines (DEPTH ft, DATASOURCE, UPD | 9,285 lines, 7,351 polygons, 558 lake groups; 11 fleet lakes candidate-matched by name+sta | 2 | ACCEPTED | No access constraints; use at own risk;  |
| S-depth-008 | Washington Ecology Lake Bathymetry Contour Lines / Elevation Bands | WA Dept of Ecology | contour lines (Depth ft, GNIS_Name, Reac | 2,776 lines in 211 name groups; 2,632 band polygons; 4 fleet lakes candidate-matched by na | 4 | ACCEPTED | Public; check Ecology terms |
| S-depth-009 | Michigan DNR/IFR Inland Lake Contours (DNRHydrologyOPENDATA layer 1) | Michigan DNR Fisheries / Ins | depth-band contour lines (MinDepth, MaxD | 25,492 lines, 1,482 name groups; 8 fleet lakes candidate-matched by name+state | 4 | ACCEPTED | Credit IFR / MDNR Fisheries / UMich |
| S-depth-010 | MassWildlife Inland Water Bathymetry (feature service)  | MassWildlife / MassGIS | contour lines (DEPTH, NAME, SHORE) from  | 27,989 lines in 264 name groups; 7 fleet lakes candidate-matched by name+state | 3 | ACCEPTED | MassGIS open data |
| S-depth-011 | Kansas Biological Survey (KARS) Bathymetry Depth Contours (WaterResour | Kansas Biological Survey, Un | contour polylines (CONTOUR depth ft) - N | 7,667 contour lines; 0 fleet lakes candidate-matched by name+state; 12 more by location on | 2 | ACCEPTED | No constraints; acknowledge KBS |
| S-depth-012 | FWC Bathymetry of Select Lakes in Florida (1-ft contours) | Florida FWC Fish and Wildlif | 1-foot depth contours (DEPTHF, DEPTHM),  | 24,311 lines; 0 fleet lakes candidate-matched by name+state; 9 more by location only | 1 | ACCEPTED | Metadata: unrestricted, but 'should not  |
| S-depth-013 | OWRB Lakes of Oklahoma - Contours / Lake Points (LOK_Lakes MapServer) | Oklahoma Water Resources Boa | contour polylines (lake, depth, elevatio | 876 contour lines in 91 lakes (many municipal lakes); 147 lake points; 5 fleet lakes candi | 2 | ACCEPTED | OWRB public data |
| S-depth-014 | Illinois DNR Lake Depth and Capacity (WaterResources MapServer) | Illinois DNR Office of Water | contour polylines (CONTOUR) + 44 surveye | 3,402 of 4,828 contour lines retrieved (server returned fewer ids than count); 43 of 44 la | 2 | ACCEPTED | IDNR; no license stated |
| S-depth-015 | Ohio DOW Lake Bathymetry (inland lakes) MapServer | Ohio DNR Division of Wildlif | contour polylines (LAKE_NAME, DEPTH) + 1 | 2,809 contour lines in 134 lakes; 11 fleet lakes candidate-matched by name+state | 3 | ACCEPTED | ODNR; no license stated |
| S-depth-016 | TWRA Lake Bathymetry Contours (small TN lakes) | Tennessee Wildlife Resources | contour polylines (4 waterbodies only) | 541 lines, 4 waterbodies; 0 fleet lakes | 3 | LEAD | unknown |
| S-depth-017 | WV DNR Public Fishing Lake Contours | West Virginia DNR | dense contour polylines (Contour, LakeNa | 53,244 lines; 11 fleet lakes candidate-matched by name+state | 2 | ACCEPTED | unknown |
| S-depth-018 | NJDEP Lake Bathymetry Contours in New Jersey | NJ DEP Bureau of GIS / Fish  | contour lines (VAL2NUM metres, DATESAMP, | 1,492 lines in 80 waterbodies; 2 fleet lakes candidate-matched by name+state | 3 | ACCEPTED | unknown |
| S-depth-019 | CT DEEP Lake Bathymetry Contours (Lines) | Connecticut DEEP | contour lines (DEPTH_FT, METHOD, DATADAT | 7,495 lines; 11 fleet lakes candidate-matched by name+state | 3 | ACCEPTED | CC0 per data.gov copy (another copy says |
| S-depth-020 | USGS Inland Bathymetric and Topobathymetric Survey Inventory v4 (Scien | USGS | index polygons of 314 USGS inland bathym | 314 survey footprints; 24 fleet lakes candidate-matched by name+state | 1 | ACCEPTED | USGS public domain |
| S-depth-021 | OWRB Lakes of Oklahoma lake points: depth_max/depth_mean (layer 0) | Oklahoma Water Resources Boa | max-depth/mean-depth + capacity attribut | 147 points (many depth_max null); 11 fleet lakes candidate-matched by name+state | 5 | ACCEPTED | OWRB |
| S-depth-022 | Michigan IFR Lake Deep Points (max depth per lake) | Institute for Fisheries Rese | max-depth points (Max_Depth ft, Lake_Nam | 2,651 points; 9 fleet lakes candidate-matched by name+state | 5 | ACCEPTED | credit IFR/MDNR/UMich |
| S-depth-023 | ND GIS Hub Lake Maximum Depth (points) | ND Game & Fish / ND GIS Hub | max-depth points (DEPTH) | 179 points; ~1 fleet lake | 5 | ACCEPTED | ND: framework layer, not a survey |
| S-depth-024 | USGS ScienceBase per-reservoir bathymetry data releases (harvested cat | USGS Water Science Centers ( | survey: point soundings, DEMs, contours, | 356 harvested items; 16 fleet lakes candidate-matched by name+state | 1 | ACCEPTED | USGS public domain |
| S-depth-025 | Maryland Geological Survey Reservoir Bathymetry Data (depth soundings  | Maryland Geological Survey | point soundings (Easting, Northing UTM18 | 9 zips; 6 fleet lakes candidate-matched by name+state | 1 | ACCEPTED | MGS: illustration only, not for navigati |
| S-depth-026 | GLOBathy global lake bathymetry rasters (30 m) | Khazaei et al. 2022 / Univ o | MODELED bathymetry (GIS + max-depth regr | all fleet lakes in HydroLAKES (~covers fleet by size); 0 measured | 6 | LEAD | CC0 |
| S-depth-027 | 3D-LAKES (ICESat-2 + Landsat lake & reservoir bathymetry) | Huang et al., Scientific Dat | derived: satellite-altimetry hypsometry  | unknown fleet overlap | 6 | LEAD | unknown |
| S-depth-028 | UMN digitized hypsography for ~750 MN/WI/SD lakes (DRUM readme) | Univ. of Minnesota (Hansen e | area-at-depth tables digitized from DNR  | unknown; only readme fetched | 4 | LEAD | unknown |
| S-depth-029 | Wisconsin DNR lake bathymetry GIS | Wisconsin DNR | none found | 0 | 7 | DEAD_END | - |
| S-depth-030 | NOAA NCEI Great Lakes Bathymetry (product page) | NOAA NCEI | grid: 3 arc-sec / 90 m open-lake bathyme | Lake Superior, Michigan, Erie, Ontario, Huron (fleet: ~10 rows) | 5 | LEAD | public |
| S-depth-031 | USGS Great Lakes seamless topobathymetric DEMs / water depth models | USGS Great Lakes Science Cen | raster: seamless topobathy DEM (Erie 521 | Great Lakes rows only; 10 fleet lakes candidate-matched by name+state | 1 | LEAD | USGS public domain |
| S-depth-032 | USGS 3DEP / TNM Access API (Elevation - Topobathy) | USGS National Map | API: dataset tag 'Elevation - Topobathy' | not enumerated | 2 | LEAD | public |
| S-depth-033 | Local/association contour services (Chippewa Flowage WI, Harveys Lake  | Chippewa Flowage Area Proper | contour polylines (small sets) | 3 fleet lakes exact | 4 | ACCEPTED | unknown |
| S-depth-034 | SJRWMD bathymetry soundings (OpenData_Bathymetry*) | St. Johns River Water Manage | sounding points (ELEV_88, DEPTH_FT) 87k  | not matched | 1 | LEAD | SJRWMD |
| S-depth-035 | Georgia PFA_Bathymetry (GA DNR WRD) | Georgia DNR Wildlife Resourc | contour polylines, 201 features, depth o | ~201 lines; no name field | 3 | LEAD | unknown |
| S-depth-036 | USACE CWMS Data API | US Army Corps of Engineers | time series: pool elevation/storage (no  | 0 bathymetry | 7 | DEAD_END | public |
| S-depth-037 | TVA reservoir bathymetry | Tennessee Valley Authority | correspondence stating TVA holds bathyme | 0 downloadable | 7 | DEAD_END | - |
| S-depth-038 | USBR RISE / Reclamation reservoir area-capacity & bathymetry | Bureau of Reclamation | RISE API (reservoir time series, area-ca | unknown | 2 | LEAD | - |
| S-depth-039 | EPA National Lakes Assessment 2007 sampled-lake information (DEPTHMAX  | US EPA | max depth at index site (m), lake area,  | 1,252 rows; 109 fleet lakes candidate-matched by name+state | 5 | ACCEPTED | US Government public |
| S-depth-040 | State agency GIS not located (AL, GA, SC, NC, KY, VA, LA, MS, MO, AR,  | various | - | 0 | 7 | DEAD_END | - |
| S-terrain-001 | TWDB completed-survey packages: elevation-area-capacity .txt + conserv | Texas Water Development Boar | area-capacity table at 0.1 ft; pool poly | 91 surveys with table+zip, 68 with a pool polygon matched to the table area (63 used, >=25 | 1 | ACCEPTED | public; TWDB asks for acknowledgment |
| S-terrain-002 | waterdatafortexas.org reservoir daily level (individual/<slug>.csv) | TWDB Water Data for Texas | daily water level, surface area, storage | Fork, Tawakoni, Brownwood, Lavon, Cedar Creek used (slug known for 11 tested; hubbard-cree | 1 | ACCEPTED | public |
| S-terrain-003 | Minnesota DNR Lake Bathymetric Contours / Outline (MapServer water_lak | Minnesota DNR | depth contour lines (5 or 10 ft interval | 9 of 14 MN directory lakes matched by name (Vermilion not found) | 1 | ACCEPTED_WITH_LIMITS | public |
| S-terrain-004 | USGS 3DEP seamless DEM ImageServer getSamples | USGS National Map | elevation samples (1 m lidar where avail | 33 CWMS + 63 TWDB + 9 MN lakes at 600 pts x 10 offsets; 27 lakes at 150 m spacing x 7 offs | 1 | ACCEPTED | public domain |
| S-terrain-005 | Landsat Collection 2 Level-2 (L5/7/8/9) on Microsoft Planetary Compute | USGS / Microsoft Planetary C | surface reflectance green/SWIR1 + QA_PIX | 5 TX lakes, 2000-2026, 744-834 scenes read per lake, 224-430 used | 1 | ACCEPTED | public (USGS) |
| S-terrain-006 | NOAA NGS NCAT / VERTCON 3.0 llh API | NOAA National Geodetic Surve | NGVD29 -> NAVD88 vertical datum shift at | 412 pool-reference lakes | 1 | ACCEPTED | public domain |
| S-terrain-007 | USACE CWMS Data API timeseries + catalog; Access2Water location record | USACE | daily/hourly pool elevation series; per- | 213 of 417 bound lakes returned a 2016-2026 series (CWMS 60/64, Access2Water 81/112 via CW | 1 | ACCEPTED | public domain |
| S-terrain-008 | USGS NWIS daily values, parameters 62614/62615/00062 | USGS | daily mean lake elevation | 33 of 79 bound USGS lakes gave a series | 1 | ACCEPTED | public domain |
| S-terrain-009 | JRC Global Surface Water v1.4 static layers (prior thread, gsw_feature | EC JRC | occurrence/seasonality shares | 11 CWMS lakes in the SE tile | 1 | REJECTED_AS_SCORE | CC-BY |

## GLOBathy-thread truth records

223 records of max-depth/hypsometry values from agency, USGS and utility sources, each with URL and confidence in `ledger/globathy.jsonl`; decisions/authority: {('evaluated', None): 1, ('used', None): 4, ('used_as_truth', None): 184, ('recorded_no_max_depth', None): 31, ('excluded', None): 3}.

## Reading the matrix for Depth Brain

* **Tier A/B contour sources** (TWDB, MN DNR, NE, OH, WV, MA, CT, NH, MT, KS, OK, ND, FL internal) produced the 103 usable fleet lakes. They are state-by-state; there is no national contour dataset.
* **Federal navigation (IENC)** is channel-biased and binary (9 ft): 34 fleet lakes intersect a footprint, 28 end up with no better evidence. Useful as a shallow/deep sanity check, not as flats evidence.
* **Hypsometry** (USACE CWMS stage-storage, TWDB area-capacity) provides lake-level truth without spatial detail.
* **Max-depth anchors** (EPA NLA 2007: 109 fleet lakes; agency tables) calibrate but do not map.
* **Modeled** (GLOBathy, HydroLAKES) are Tier D priors only; see the GLOBathy evaluation.
* **Dead ends and unreached**: no public TVA bathymetry; USACE CWMS carries time series only; zenodo and data.usbr.gov unreachable from the scouting host (3D-LAKES and Reclamation RISE unverified); Wisconsin DNR has no inland contour GIS (a draft association layer only).
