# Vegetation Brain — Dataset Manifest (summary)

Authoritative machine manifest (1,080 JSON lines, bytes + sha256 per file): `~/Desktop/Development/Sector_Research_Data/vegetation-brain/MANIFEST.jsonl`. Raw data and imagery stay **outside Git**. Total on disk ≈ 10 GB (experiments `out/` 9.6 GB: Sentinel-2 window caches ≈2.5 GB, stacks, and **3.7 GB `out/_discarded_double_offset/` from an invalid first pass that can be deleted**). `.venv` 384 MB.

| Group | Path under `Sector_Research_Data/vegetation-brain/` | Source | Retention | Rebuild |
|---|---|---|---|---|
| EPA NLA 2017 phab + site info (3 files, 8.7 MB) | `sources/nla_2017_phab/` | EPA NARS data portal | REBUILDABLE | download from epa.gov NARS data page |
| FWC LTM point intercepts (11.9 MB) | `sources/fwc_ltm_point_intercepts/` | FWC `WhatsHappeningOnMyLake` MapServer layer 33 | REBUILDABLE | `experiments/scripts/01_fetch_fwc.py` |
| USGS UMR SAV `vegetation_data.csv` (2.9 MB) | `sources/usgs_sav_upper_miss_rf/` | ScienceBase 64540e54d34eefd5da843ac9 | REBUILDABLE | download |
| GloBathy fleet match (copied) | `sources/globathy_fleet_match_from_depth_research.csv` | Depth research branch, read-only copy | COPY | from `Sector_Engine-depth-research` |
| Snohomish aquatic plant surveys; FWC lakes, bathymetry, PAC/PVI; Carver MN biovolume; Secchi (WQP) | `experiments/data/` (≈35 MB) | county/state ArcGIS REST, Water Quality Portal | REBUILDABLE | `experiments/scripts/02,07,14,19,2x*.py` |
| Sentinel-2 windowed COG caches | `experiments/out/s2cache*/` (2.5 GB) | Earth Search STAC `sentinel-2-c1-l2a` / `sentinel-2-l2a` | REBUILDABLE | `03_extract.py`, `20_pac_extract.py` |
| Derived stacks, metrics, figures, tables | `experiments/out/` | this campaign | DERIVED | rerun scripts (see note 04 §6) |
| Lake polygons (read-only, not copied) | `Sector_Research_Data/lake-brain/geometry/engine_polygons_599.geojson.gz` | Lake Brain research data | external | n/a |

Tracked in Git (small): `docs/research/vegetation-brain/data/fleet_matrix.csv`, `scripts/fleet_matrix.py`, `scripts/experiments/*.py` (copies), `notes/*.md` (copies of the raw research notes).
