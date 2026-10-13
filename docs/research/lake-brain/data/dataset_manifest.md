# Lake Brain research — dataset retention manifest (generated)

For Sweep: `KEEP` valuable irreplaceable research · `ARCHIVE_FIRST` valuable, large, archive before any removal · `REBUILDABLE` can be regenerated (rebuild command given) · `SAFE_TO_REMOVE` disposable cache · `REVIEW_REQUIRED`.
Data lives outside Git under `~/Desktop/Development/Sector_Research_Data/lake-brain/` (see `MANIFEST.jsonl` there for checksums).

| Path | Bytes | Track | Retention | Rebuild | Note |
|---|---|---|---|---|---|
| directory_lakes_2026-10-13.json | 187633 | all | REBUILDABLE | curl https://sector-engine-e43utajroa-uc.a.run.app/lakes | Production lake directory snapshot (621 lakes) |
| geometry/engine_polygons_599.geojson.gz | 7500435 | geometry | REBUILDABLE | copy of jobs/lake-surface/polygons.geojson.gz @48168baa | Engine-shipped lake polygons; in Git already |
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
| geometry/lake_geometry_flags.csv | 414087 | geometry | KEEP | python3 research/lake-brain/geometry_audit.py --stage all | Per-lake geometry flags (621 rows): audit output; small |
| geometry/gsw_metrics.json | 106529 | geometry | REBUILDABLE | geometry/venv/bin/python research/lake-brain/geometry_gsw.py | Per-polygon JRC GSW occurrence metrics |
| geometry/hydrolakes_metrics.json | 133886 | geometry | REBUILDABLE | geometry/venv/bin/python -I research/lake-brain/geometry_hydrolakes.py | Per-lake HydroLAKES v10 match metrics |
| geometry/simplify_sizes.json | 11300 | geometry | REBUILDABLE | python research/lake-brain/geometry_simplify_sizes.py | Simplification vs size for 5 pilot lakes |
| geometry/fleet_delivery_sizes.json | 625 | geometry | REBUILDABLE | python research/lake-brain/geometry_simplify_sizes.py --fleet | Delivery sizes for all 599 polygons at 0/25/50/100 m |
| geometry/private_geometry_inventory.json | 3599 | geometry | REVIEW_REQUIRED | n/a | Inventory (hash/size/type) of private research geometry files; paths reference a private worktree; do not publish |
| geometry/nhd_full/pilots_nhd_full.geojson | 7686757 | geometry | REBUILDABLE | NHD MapServer/12 query PERMANENT_IDENTIFIER IN (139326855,88572193,87864655,147604857,136157939,120024414), f=geojson, outSR=4326 | Full-resolution NHD HR polygons of the 5 pilots (public USGS data) |
| geometry/sources/usace_rez.geojson | 68105686 | geometry | REBUILDABLE | curl "https://services7.arcgis.com/n1YM8pTrFmm7L4hs/arcgis/rest/services/usace_rez/FeatureServer/0/query?where=1=1&outFields=*&outSR=4326&f=geojson" | USACE Reservoirs: 418 operator pool polygons (public domain per item metadata) |
| geometry/gsw | 1025169476 | geometry | REBUILDABLE | 23 tiles occurrence_<lon>_<lat>v1_4_2021.tif from https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/ (JRC GSW v1.4; free and open, cite Pekel et al. 2016) | JRC Global Surface Water occurrence tiles used by geometry_gsw.py; plus holes_pilots.json |
| geometry/hydrolakes | 2333859763 | geometry | REBUILDABLE | curl -O https://data.hydrosheds.org/file/hydrolakes/HydroLAKES_polys_v10_shp.zip then unzip into hydrolakes/extracted (HydroSHEDS licence: free with attribution, verify before shipping) | HydroLAKES v10 polygons (820 MB zip + extracted), coverage/area comparison only |
| geometry/cache | 218236387 | geometry | REBUILDABLE | python research/lake-brain/geometry_audit.py (re-queries NHD MapServer/12, 3DHP_all MapServer/60, Overpass per state) | Cached REST/Overpass responses keyed by sha1 of the query (about 2.5k files) |
| geometry/osm | 4427078 | geometry | REBUILDABLE | python research/lake-brain/geometry_osm_pilots.py | OSM Overpass raw responses + assembled pilot comparisons (ODbL) |
| geometry/venv | 227951879 | geometry | SAFE_TO_REMOVE | python3 -m venv geometry/venv && pip install rasterio shapely pyproj numpy requests pyogrio | Python venv with rasterio/pyogrio for the GSW and HydroLAKES scripts |
| context/tva_snapshot | 6876 | context | KEEP | GET https://www.tva.com/RestApi/{observed,predicted}-data/<id>.json (live feed keeps only the current day) | TVA RestApi snapshot 2026-10-13 for the 5 pilot-chain dams (basis of the chain-coupling table) |
| binding/catalog.jsonl | 17423581 | binding | REBUILDABLE | python research/lake-brain/binding/build_catalog.py | normalised series catalog (USGS/CWMS/A2W/RISE/TWDB/NWPS/CO-OPS/TVA) |
| binding/candidates_all.csv | 2080182 | binding | REBUILDABLE | python research/lake-brain/binding/match.py | static candidate matches (12 per lake) |
| binding/candidates.csv | 1203753 | binding | KEEP | python research/lake-brain/binding/verify.py | evaluated candidates with review-criteria results |
| binding/verified.csv | 147827 | binding | KEEP | python research/lake-brain/binding/finalize.py | per-lake chosen binding with history class |
| binding/probe_results.json | 853127 | binding | KEEP | python research/lake-brain/binding/probe.py | live probe results 2026-10-13 |
| binding/history_results.json | 177886 | binding | KEEP | python research/lake-brain/binding/history.py | year-completeness per candidate site |
| binding/nid_links.csv | 85938 | binding | REBUILDABLE | python research/lake-brain/binding/nid_link.py | lake -> NID dam links |
| binding/spotcheck.csv | 8247 | binding | KEEP | python research/lake-brain/binding/spotcheck.py | independent spot-check table |
| binding/raw/nid/nid.jsonl | 76499687 | binding | REBUILDABLE | python research/lake-brain/binding/fetch_nid.py | NID 92,627 dams |
| binding/raw/usgs/ | 127926424 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/raw/cwms/ | 45853517 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/raw/a2w/ | 6753970 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/raw/rise/ | 3514090 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/raw/nwps/ | 13166537 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/raw/twdb/ | 73275 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/raw/coops/ | 777392 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/raw/tva/ | 8489 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/raw/probe/ | 25016606 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| binding/history/ | 21133269 | binding | REBUILDABLE | fetch_*.py / probe.py / history.py in research/lake-brain/binding | raw provider downloads and cached probes/history (2026-10-13) |
| plan/history/hads/ | 0 | plan | REBUILDABLE | research/lake-brain/plan/hads_fetch.py <LID,...> (IEM HADS, 3-year chunks; ~1 request per 15-20 s) | IEM HADS pool-elevation extracts (HPIR*) for 34 NWPS gauges |
| plan/history/usgs/ | 0 | plan | REBUILDABLE | research/lake-brain/plan/usgs_fetch.py | USGS daily series used as history legs |
| plan/history/cwms/ | 0 | plan | REBUILDABLE | research/lake-brain/plan/cwms_pull.py | CWMS pool elevation daily series |
| plan/history/twdb/ | 0 | plan | REBUILDABLE | research/lake-brain/plan/twdb_fetch.py amistad falcon | TWDB daily elevation |
| plan/history/coops/ | 0 | plan | REBUILDABLE | research/lake-brain/plan/coops_fetch.py 9034052 1995 | CO-OPS Lake St. Clair daily mean |
| plan/history/composite/ | 0 | plan | KEEP | research/lake-brain/plan/history_extension.py | final daily composites per lake (date,value) gz csv |
| plan/raw/ | 0 | plan | REBUILDABLE | research/lake-brain/plan/nwps_meta.py, nwps_recent.py, usgs_catalog.py | NWPS metadata, 30-day NWPS values, USGS catalogs, fetch logs |
| plan/plan_flood_evidence_base.csv | 0 | plan | REBUILDABLE | research/lake-brain/plan/plan_evidence.py | strict-tier evidence table before tier 2 |
| binding2/unbound_profile.json | 138392 | binding2 | KEEP | python research/lake-brain/binding2/profile_unbound.py | 274 unbound lakes with bowfishing tier |
| binding2/verified_v2_full.csv | 186171 | binding2 | KEEP | python research/lake-brain/binding2/assemble_v2.py | cumulative per-lake binding table (all 621 lakes, layers) |
| binding2/assembled_v2.json | 440164 | binding2 | REBUILDABLE | python research/lake-brain/binding2/assemble_v2.py | assembled records |
| binding2/remaining_unbound.json | 110758 | binding2 | KEEP | python research/lake-brain/binding2/remaining.py | remaining unbound lakes with reason |
| binding2/ablation.json | 4299 | binding2 | KEEP | python research/lake-brain/binding2/ablation.py | v1.1 rule ablation |
| binding2/envelope.json | 15716 | binding2 | REBUILDABLE | python research/lake-brain/binding2/envelope_promote.py | wave-1 flagged lakes history envelope |
| binding2/usgs_stage_calibration.json | 13136 | binding2 | KEEP | python research/lake-brain/binding2/usgs_stage_calibration.py | gage height + alt_va calibration |
| binding2/stage_plus_alt.json | 9927 | binding2 | KEEP | python research/lake-brain/binding2/stage_plus_alt.py | wave-1 stage-only lakes with derived elevation |
| binding2/hads_probe.json | 10914 | binding2 | KEEP | python research/lake-brain/binding2/hads_probe.py | IEM HADS first-year probe for NWPS lake gauges |
| binding2/probe_results_v2.json | 853823 | binding2 | REBUILDABLE | python research/lake-brain/binding2/reprobe_usgs.py | wave-1 probe results with USGS parameter-selection fix |
| binding2/cand/ | 856040 | binding2 | REBUILDABLE | python research/lake-brain/binding2/src_*.py usgs_scan.py hads_history.py | scout + scan candidate series |
| binding2/history/ | 9912930 | binding2 | REBUILDABLE | python research/lake-brain/binding2/src_*.py usgs_scan.py hads_history.py | daily history series (scouts, HADS, USGS dv) |
| binding2/notes/ | 152028 | binding2 | REBUILDABLE | python research/lake-brain/binding2/src_*.py usgs_scan.py hads_history.py | source evaluation records incl. dead ends |
| binding2/raw/ | 38023790 | binding2 | REBUILDABLE | python research/lake-brain/binding2/src_*.py usgs_scan.py hads_history.py | scout raw captures |
| binding2/probe/ | 0 | binding2 | REBUILDABLE | python research/lake-brain/binding2/src_*.py usgs_scan.py hads_history.py | cached probes |
| context/hypso_lakes.json | 1112 | context | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| context/erom.log | 1174 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/external_join.v1.json | 413945 | context | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| context/chain2.log | 160 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/shore_val_b.log | 9389 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/shore_dem.log | 1944 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/chain3.log | 979 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/shore_val_a.log | 9819 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/chain4.log | 1115 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/hypso_truth2.log | 586 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/hypso_pairs.log | 242 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/chain.log | 460 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/hypso_truth.log | 7508 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/tribs.log | 1048 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/nldi_pilot_sites.json | 2898 | context | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| context/join.log | 101 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/nwi.log | 1527 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/cwms_flow.log | 3076 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| context/globathy/dl.log | 0 | context | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| binding2/r7h_control.json | 9827 | binding2 | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| binding2/hads_probe_extra.json | 2594 | binding2 | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| binding2/state_cov.json | 4820 | binding2 | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| binding2/wave1_audit.json | 2349 | binding2 | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| binding2/fp_suspects.json | 1305 | binding2 | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| binding2/hads_probe_extra_1.json | 2594 | binding2 | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| binding2/SPEC.md | 6295 | binding2 | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| plan/targets.json | 26552 | plan | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| plan/tables.json | 8032 | plan | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| plan/history_ext_results.json | 45431 | plan | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| plan/tmp/rvd_BMX_2008-06-02.txt | 2085 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_PAH_2018-06-02.txt | 2117 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_RNK.txt | 3162 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_MRX_2012-06-02.txt | 1706 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_GSP_2012-06-02.txt | 3310 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_LMK_2018-06-02.txt | 1045 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/falcon.csv | 1410990 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_OHX_2008-06-02.txt | 2467 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_OHX.txt | 2612 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_LMK_2012-06-02.txt | 975 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_GSP_2018-06-02.txt | 2498 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_BMX.txt | 2136 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_MRX_2018-06-02.txt | 1705 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_PAH_2012-06-02.txt | 2117 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_RNK_2008-06-02.txt | 2025 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_GSP.txt | 2404 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_LMK_2008-06-02.txt | 977 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_OHX_2012-06-02.txt | 2163 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_MRX.txt | 1701 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_RNK_2012-06-02.txt | 2194 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_BMX_2018-06-02.txt | 2136 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_HUN.txt | 2892 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_MEG.txt | 5225 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_PAH_2008-06-02.txt | 2119 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_MRX_2008-06-02.txt | 0 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/amistad.csv | 1149540 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_BMX_2012-06-02.txt | 2082 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_RNK_2018-06-02.txt | 3184 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_OHX_2018-06-02.txt | 2613 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_GSP_2008-06-02.txt | 3082 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| plan/tmp/rvd_PAH.txt | 2118 | plan | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| species/other/native_ranges/url.txt | 97 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | public species-occurrence downloads (presence_evidence_probe.py) |
| species/other/native_ranges/AGAP_Native_Ranges.xml | 76865 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | public species-occurrence downloads (presence_evidence_probe.py) |
| species/other/in/meta.csv | 5894 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | public species-occurrence downloads (presence_evidence_probe.py) |
| species/other/midfish/midfish_metadata_final.xml | 117383 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | public species-occurrence downloads (presence_evidence_probe.py) |
| species/other/midfish/Taxa_List.csv | 12660 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | public species-occurrence downloads (presence_evidence_probe.py) |
| species/other/midfish/abund/abundance_product.csv | 75232521 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | public species-occurrence downloads (presence_evidence_probe.py) |
| species/other/midfish/abund/cpue_inclusion_table.csv | 29454 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | public species-occurrence downloads (presence_evidence_probe.py) |
| species/other/coarse_range/agap_coarse_fish_ranges_v2_0.xml | 29481 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | public species-occurrence downloads (presence_evidence_probe.py) |
| species/gbif/progress.json | 12947 | species | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| binding/cwms_guides.json | 3509 | binding | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| binding/catalog_usgs_cwms.jsonl | 11779392 | binding | REBUILDABLE | re-run the owning script in research/lake-brain/ | public API catalog capture (binding_pipeline.py) |
| history/holdout/holdout_mt5.json | 95962 | history | KEEP | research/lake-brain/holdout_validation.py | hold-out validation per-lake results (script holdout_validation.py reproduces from binding history) |
| history/holdout/holdout_mt10.json | 61661 | history | KEEP | research/lake-brain/holdout_validation.py | hold-out validation per-lake results (script holdout_validation.py reproduces from binding history) |
| geometry/run4.log | 3346 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| geometry/run_hl.log | 19 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| geometry/run1.log | 435 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| geometry/run2.log | 41 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| geometry/run3.log | 1973 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| geometry/pyogrio_install.log | 0 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| geometry/lake_geometry_flags.pre_osm.csv | 378212 | geometry | REBUILDABLE | re-run the owning script in research/lake-brain/ | intermediate result JSON/CSV from the research scripts |
| geometry/run_gsw.log | 52 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| geometry/run_osm.log | 1990 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| geometry/venv_install.log | 5 | geometry | SAFE_TO_REMOVE | re-run the owning script in research/lake-brain/ | run log / scratch |
| literature/ | 0 | literature | SAFE_TO_REMOVE | n/a | empty directory created at campaign start |
