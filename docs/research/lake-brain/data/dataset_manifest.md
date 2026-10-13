# Lake Brain research — dataset retention manifest (generated)

For Sweep: `KEEP` valuable irreplaceable research · `ARCHIVE_FIRST` valuable, large, archive before any removal · `REBUILDABLE` can be regenerated (rebuild command given) · `SAFE_TO_REMOVE` disposable cache · `REVIEW_REQUIRED`.
Data lives outside Git under `~/Desktop/Development/Sector_Research_Data/lake-brain/` (see `MANIFEST.jsonl` there for checksums).

| Path | Bytes | Track | Retention | Rebuild | Note |
|---|---|---|---|---|---|
| history/cwms | 55246698 | baselines | REBUILDABLE | research/lake-brain/baseline_fetch.py cwms <office> <name> <out.csv> | CWMS timeseries pulls (Hartwell daily, Pickwick/Kentucky/Normandy hourly, Cave Run, Allatoona, Pueblo 15-min, Shasta, guide-curve daily) |
| history/cwms_levels | 15101722 | baselines | REBUILDABLE | GET /cwms-data/levels?office=O&level-id-mask=*.Elev*.*, /catalog/LOCATIONS?office=O, /catalog/TIMESERIES?office=O&like=.*\.Elev... | CWMS levels, locations catalog and Elev time-series catalog per office |
| history/hads | 24312709 | baselines | REBUILDABLE | hads/dl.sh pattern: https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations=<ID>&sts=<iso>&ets=<iso>&what=txt&delim=comma | IEM HADS HP/HT/PC pulls for GVDA1, WHLA1, WLSA1, PICT1 in 6-month files 2022-10-20 to 2026-10-14 |
| history/nws_rvdhun | 21996349 | baselines | REBUILDABLE | https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=RVDHUN&limit=9999&fmt=text&sdate=Y-01-01&edate=Y-12-31 then research/lake-brain/parse_rvdhun.py | IEM AFOS RVDHUN yearly text dumps 2001-2022 and parsed pool CSV |
| history/nws_rvdmeg | 22948047 | baselines | SAFE_TO_REMOVE | same pattern with pil=RVDMEG | IEM AFOS RVDMEG yearly text dumps 2013-2021 (Pickwick headwater) |
| history/noaa | 681943 | baselines | REBUILDABLE | NOAA CO-OPS datagetter product=daily_mean station=9063063 | Lake Erie Cleveland daily mean 1962-2026 |
| history/usgs | 787298 | baselines | REBUILDABLE | research/lake-brain/baseline_fetch.py usgs-dv 04294500 62614 <out.csv> | Lake Champlain 04294500 daily 62614 |
| history/tva_guides | 249177 | baselines | REBUILDABLE | curl TVA RestApi with browser User-Agent and Accept: application/json | TVA operating-guide JSON for 5 locations, TVA locations list, scan.json of 43 locations |
| history/tva_pilots | 674486 | baselines | KEEP | research/lake-brain/tva_pilot_history.py | Composite daily pool history for the four TVA pilots (GVDA1/WHLA1/WLSA1/PICT1 *_daily.csv, validation_summary.json) - the candidate backfill |
| history/tva_archive | 221705 | baselines | SAFE_TO_REMOVE | gcloud storage cat gs://sector-water-temp-archive/water-temp/tva/<LOC>/<date>.json | 8 days of the shared TVA hourly archive copied read-only for the HADS equality check |
| history/lakebrain_gcs | 1794282 | baselines | SAFE_TO_REMOVE | gcloud storage cat gs://sector-lake-brain/history/<key>/daily.csv | Read-only copies of gs://sector-lake-brain/history/<key>/daily.csv for the 4 pilots + Hartwell |
| history/guide_availability_cwms.json | 108190 | baselines | REBUILDABLE | research/lake-brain/guide_availability.py | per-lake CWMS level match and history span (automatic, unreviewed) |
| history/venv_baselines | 224353799 | baselines | SAFE_TO_REMOVE | python3 -m venv; pip install numpy pandas scipy shapely pypdf | Python venv (numpy, pandas, scipy, shapely, pypdf) |
| context/geom_features.json | 357913 | context | REBUILDABLE | research/lake-brain/context_geom.py | polygon morphometry for 599 lakes |
| context/external_join.json | 430251 | context | REBUILDABLE | research/lake-brain/context_join.py (needs hydrolakes/ and nid/) | HydroLAKES + NID join per directory lake |
| context/erom.json | 178232 | context | REBUILDABLE | research/lake-brain/context_erom.py | NHDPlus HR EROM + VAA at each matched dam (~25 min) |
| context/chain.json | 47062 | context | REBUILDABLE | research/lake-brain/context_chain.py | NLDI downstream/upstream directory lakes (~1.5 h) |
| context/nid/nid_v1_subset.json | 63417366 | context | REBUILDABLE | research/lake-brain/context_fetch_nid.py | NID (Esri mirror) 92,627 dams, 26 fields |
| context/hydrolakes/HydroLAKES_points_v10_shp.zip | 78725399 | context | REBUILDABLE | curl https://data.hydrosheds.org/file/hydrolakes/HydroLAKES_points_v10_shp.zip | HydroLAKES v1.0 points (polygons 820 MB deliberately NOT downloaded) |
| context/hydrolakes/pts | 441491546 | context | SAFE_TO_REMOVE | unzip HydroLAKES_points_v10_shp.zip | extracted shapefile |
| context/globathy/GLOBathy_basic_parameters.zip | 115568963 | context | REBUILDABLE | curl https://ndownloader.figshare.com/files/28919991 | GLOBathy basic parameters (Dmax estimates) |
| context/globathy/basic | 588035057 | context | SAFE_TO_REMOVE | unzip GLOBathy_basic_parameters.zip (16 split CSVs duplicate ALL_LAKES.csv) | extracted CSVs ~570 MB |
| context/globathy/GLOBathy_hAV_relationships.nc | 525404045 | context | REBUILDABLE | curl https://ndownloader.figshare.com/files/28917783 | GLOBathy head-area-volume curves |
| context/gsw/occurrence_90W_40Nv1_4_2021.tif | 53487920 | context | REBUILDABLE | curl https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_90W_40Nv1_4_2021.tif | JRC GSW occurrence tile |
| context/gsw/seasonality_90W_40Nv1_4_2021.tif | 29200682 | context | REBUILDABLE | curl https://storage.googleapis.com/global-surface-water/downloads2021/seasonality/seasonality_90W_40Nv1_4_2021.tif | JRC GSW seasonality tile |
| context/gsw_features.json | 39494 | context | REBUILDABLE | research/lake-brain/context_gsw.py | GSW stats for 105 lakes in tile |
| context/nwi_features.json | 2122 | context | KEEP | research/lake-brain/context_nwi.py (~7 min, Esri NWI mirror) | NWI proxies for 5 pilots |
| context/tribs.json | 1142 | context | KEEP | research/lake-brain/context_tribs.py (~10 min) | tributary-mouth counts for 5 pilots |
| context/shore_dem.json | 2912 | context | KEEP | research/lake-brain/context_shore_dem.py | 3DEP shoreline slope, 5 pilots (~6 min) |
| context/shore_dem_val_a.json | 14824 | context | KEEP | SHORE_OUT=shore_dem_val_a.json context_shore_dem.py @list | 3DEP shoreline slope for the validation lakes (half a) |
| context/shore_dem_val_b.json | 14134 | context | KEEP | SHORE_OUT=shore_dem_val_b.json context_shore_dem.py @list | 3DEP shoreline slope for the validation lakes (half b) |
| context/hypso_pairs.json | 19087 | context | REBUILDABLE | research/lake-brain/context_hypso_validate.py | CWMS Stor+Elev pairs matched to directory polygons |
| context/hypso_truth.json | 32356 | context | KEEP | research/lake-brain/context_hypso_truth.py (~1 h of CWMS requests) | CWMS-derived stage-area slope per lake |
| context/hypso_cwms_hartwell.json | 1106 | context | REBUILDABLE | research/lake-brain/context_hypso_cwms.py | Hartwell stage-area curve from CWMS |
| context/cwms | 38237 | context | REBUILDABLE | catalog queries in context_hypso_validate.py / see doc | CWMS catalog caches |
| context/clarity_read | 138412 | context | REBUILDABLE | gsutil cat gs://sector-lake-surface/index.json and lakes/<slug>/clarity/history.json (read only) | copy of production clarity index + pilot histories |
| context/venv | 480250453 | context | SAFE_TO_REMOVE | python3 -m venv venv && pip install numpy shapely pyproj rasterio geopandas pyogrio pandas requests xarray netCDF4 scipy | context research venv |
| context/tva_snapshot | 6876 | context | KEEP | GET https://www.tva.com/RestApi/{observed,predicted}-data/<id>.json (live feed keeps only the current day) | TVA RestApi snapshot 2026-10-13 for the 5 pilot-chain dams (basis of the chain-coupling table) |
| species/audit_presence_aggregates.json | 4417 | species | KEEP | presence_evidence_probe.py audit | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/coverage_summary.json | 3925 | species | KEEP | presence_evidence_probe.py coverage | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/validation_aggregates.json | 6413 | species | KEEP | presence_evidence_probe.py validation | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/state_probe_results.json | 495 | species | KEEP | presence_evidence_probe.py state | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/lake_species_evidence.json | 104585 | species | REBUILDABLE | presence_evidence_probe.py lake | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/gbif/gbif_lake_bbox_records.jsonl.gz | 378695 | species | REBUILDABLE | presence_evidence_probe.py gbif | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/nas/nas_occurrences_target_species.json.gz | 1342881 | species | REBUILDABLE | presence_evidence_probe.py nas | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/nas/nas_lake_matches.json | 531168 | species | REBUILDABLE | presence_evidence_probe.py nas | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/wbd/lake_huc8.json | 42634 | species | REBUILDABLE | presence_evidence_probe.py wbd | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/wqp_lake_matches.json | 4070 | species | REBUILDABLE | presence_evidence_probe.py wqp | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/midfish_lake_matches.json | 18606 | species | REBUILDABLE | presence_evidence_probe.py midfish | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/midfish_surveyed_lakes.csv | 542637 | species | REBUILDABLE | presence_evidence_probe.py midfish | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/midfish_target_species_by_lake.csv | 369621 | species | REBUILDABLE | presence_evidence_probe.py midfish | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/coarse_range/agap_coarse_fish_ranges_v2_0.csv | 2142161 | species | REBUILDABLE | presence_evidence_probe.py agap | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/midfish/Midwest_Hive_Data_Files.zip | 279845764 | species | REBUILDABLE | presence_evidence_probe.py Midwest | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/midfish/Abundance_Data_Files.zip | 8558191 | species | SAFE_TO_REMOVE | presence_evidence_probe.py Abundance | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/midfish/hive | 579210519 | species | SAFE_TO_REMOVE | unzip Midwest_Hive_Data_Files.zip (ScienceBase 68a75ab9d4be02616520f462) | species-presence research; public sources only (aggregates-of-private files have no rows) |
| species/other/states | 3937198 | species | REBUILDABLE | curl of the state endpoints in LAKE_BRAIN_SPECIES_PRESENCE_RESEARCH.md section 5 | species-presence research; public sources only (aggregates-of-private files have no rows) |
