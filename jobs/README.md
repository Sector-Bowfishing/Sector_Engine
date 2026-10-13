# Sector Engine jobs — registry and lineage

Every scheduled job in project `sector-9393c` (us-central1), what it runs, where its canonical
source lives, and whether a customer can see its output. Kept current by the consolidation
log (`docs/consolidation/STABILIZATION_LOG.md`). Verified 2026-10-12.

Rule (docs/production/PRODUCTION_LINEAGE.md): jobs deploy from `main`, and each image
self-labels the commit it was built from. "Canonical" below means `main` reproduces the
live job file-for-file (checked by matching the Cloud Run build-source zip to git blobs).

| Job | Schedule (UTC) | Source dir | Canonical on `main`? | Live image built from | Writes | Customer-visible? | Owner (Brain) |
|---|---|---|---|---|---|---|---|
| `hydrology-hourly` | `15 * * * *` | `jobs/hydrology-hourly` (+ deploy copies `scripts/hydrology/catchment_rain.py`, `docs/data/hydrology/guntersville/guntersville.{hydrology,mrms_weights}.json`) | **yes** | 2026-09-27 build; `hourly.py` identical on main and the fusion lineage | `gs://sector-lake-surface/hydrology/<slug>/hourly/<date>.json`, `rain/<slug>/catchments.json` | indirectly: production `ClarityStateLoader` reads them behind `/clarity/state`, which iOS does not call | Clarity |
| `water-temp-tva-archive` | `20 * * * *` | `jobs/water-temp-tva-archive` | **yes** (landed 2026-10-12 from `intelligence/water-temp` @ `79b966cc`, identical to the live source) | `79b966cc`-era source (no commit label on the image) | `gs://sector-water-temp-archive/water-temp/tva/*` | no (Lake Brain reads it) | Water Temp / Lake |
| `wind-hourly` | `5 * * * *` | `jobs/wind-hourly` (upload excludes `research/`, `tests/`, `read_service/`, `*.md` per `.gcloudignore`) | **yes** (landed 2026-10-12 from `brain/wind` @ `948fd5e2`; live tree = `4da234cb`, identical) | env `SECTOR_WIND_BUILD=brain/wind@4da234cb` | `gs://sector-wind-candidate/wind/v1/*` and the Brain RTDB (`sector-brain`) hourly | no — the candidate is RESEARCH_CANDIDATE; production wind is Open-Meteo in-process | Wind |
| `wind-candidate-read` (Cloud Run **service**) | on request | `jobs/wind-hourly/read_service` | **yes** (same landing) | `--source .` 2026-10-07, no commit label | serves `latest/<lake>.json.gz` to 3 master UIDs only | no (master-only, 4 lakes) | Wind |
| `lake-surface-daily` | `0 3 * * *` | `jobs/lake-surface` | **NO — explicit exception.** Live source is `feat/clarity-algal-warning` @ `03937913` (pushed): `daily.py` +129/−44 and `derive_water_surface.py` +99 vs main (Clarity Stage 4 per-cell files, arm anchors, NDCI, `--pass-dates` backfill), plus deploy copies of `scripts/hydrology/{current_cells,arm_anchor}.py` and `docs/data/hydrology/guntersville/guntersville.{current_regions.bin,current_regions.json,arm_cells.json}` — two of which are not on main. See `jobs/lake-surface/LINEAGE.md` | 2026-09-29 build (`00070-pej` era) | `gs://sector-lake-surface/lakes/<slug>/clarity/*` | no (Clarity Brain reads `latest.json`; production reads `arms/latest.json`, which nothing writes) | Clarity |
| `clarity-current-hourly` | `40 * * * *` | `Sources/ClarityPrecompute` + `Sources/SectorEngine/Clarity/*` | **NO — explicit exception.** Runs `/app/ClarityPrecompute` from `03937913`; depends on the Clarity Stage 5 engine sources (`PreparedClarityWorld`, `prepareCurrentClarity`) that are not on main (~2,400 lines, hand-off says "NOT READY"). Image self-labels `SECTOR_ENGINE_COMMIT=03937913…` | `03937913` | `gs://sector-lake-surface/clarity/current/<slug>/*` | no (read only by fusion-lineage server code and iOS `feat/clarity-*` worktrees) | Clarity |
| `clarity-candidate-shadow` | **PAUSED** | private (`feat/clarity-candidate-shadow`, never pushed) | **NO — private research.** Not on any public branch by design | `6855cb3d` (private) | `gs://sector-clarity-candidate/*` | no | Clarity (research) |
| `biological-brain` (manual) | none | `jobs/biological-brain` (shim over `jobs/brain_platform`) | **yes** (landed 2026-10-12 from `brain/biological` @ `99c18f78`) | not deployed; `python3 run.py --write` | Brain RTDB `/species`, `/brains/biological-state` | no | Biological |
| `sector-intelligence-brain` (manual) | none | `jobs/sector-intelligence-brain` (shim) | **yes** (from `brain/sector-intelligence` @ `df138c49`) | not deployed | Brain RTDB `/brains/sector-intelligence`, 621 `NOT_EVALUATED` states | no | Sector Intelligence |
| `water-clarity-brain` (manual) | none | `jobs/water-clarity-brain` (shim; `deploy-job.sh` vendors the package) | **yes** (from `brain/water-clarity` public-safe @ `6220491b`) | not deployed (`deploy-job.sh` not run) | Brain RTDB clarity states for 621 lakes | no (mirrors `/conditions`) | Water Clarity |
| `water-temp-brain` (manual) | none | `Sources/WaterTempBrainJob` + `Sources/SectorEngine/Brain` (built into the serving image as `/app/WaterTempBrainJob`) | **yes** (replayed from `brain/water-temp` @ `ec0ae0fa`) | not deployed (`jobs/water-temp-brain/deploy-job.sh` not run) | Brain RTDB water-temp states for 621 lakes | no | Water Temp |
| `lake-brain` (manual) | none | `Sources/LakeBrainJob` + `Sources/SectorEngine/LakeBrain` | **yes** (merged `sector/lake-brain` @ `eda56c90`) | not deployed (`swift run LakeBrainJob`) | Brain RTDB lake states for 5 pilots; `gs://sector-lake-brain` | no | Lake |
| `brain-scores` (manual) | none | `jobs/brain-scores` | **yes** | not deployed; `python3 score_brains.py --write` | Brain RTDB `/brains/{id}/score`, `/engine/score` | no (Ops displays) | Brain Platform |

## Decisions that would change this table
- **D4 (Clarity Stage 3–5):** land `03937913`'s job code on main as job-only, keep it a
  job-only branch, or retire `clarity-current-hourly`. Until decided, redeploying
  `lake-surface-daily` or `clarity-current-hourly` **must** be done from
  `feat/clarity-algal-warning`, never from main (main's `jobs/lake-surface` is older than
  what is live).
- Job images without a commit label (`water-temp-tva-archive`, `wind-candidate-read`) get one
  on their next deploy; add `--labels commit=$(git rev-parse --short=12 HEAD)` to their
  `deploy-job.sh`/`deploy-read.sh` at that time (not changed here — no redeploy in Phase 3).

## Running the job tests locally (offline)
```
python3 -m venv .venv && .venv/bin/pip install pytest requests google-cloud-storage numpy eccodes shapely pyproj
(cd jobs/water-temp-tva-archive && ../../.venv/bin/python -m pytest -q)      # 14 tests
(cd jobs/wind-hourly && ../../.venv/bin/python -m pytest -q)                 # network tests deselected by pytest.ini
```
`shapely` and `pyproj` are needed only by the Stage 3A field-ops tests, not by the job image.
