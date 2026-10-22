# Sector Engine jobs — registry and lineage

Every scheduled job in project `sector-9393c` (us-central1), what it runs, where its canonical
source lives, and whether a customer can see its output. Kept current by the consolidation
log (`docs/consolidation/STABILIZATION_LOG.md`). Verified 2026-10-13 (cost-efficient scheduling work).

Rule (docs/production/PRODUCTION_LINEAGE.md): jobs deploy from `main`, and each image
self-labels the commit it was built from. "Canonical" below means `main` reproduces the
live job file-for-file (checked by matching the Cloud Run build-source zip to git blobs).

| Job | Trigger / schedule | Class | Source dir | Canonical on `main`? | Live image built from | Writes | Customer-visible? | Owner (Brain) |
|---|---|---|---|---|---|---|---|---|
| `brain-orchestrator` | Cloud Scheduler `50 * * * *` UTC (hourly wake-up, scale-to-zero) | INTERNAL | `jobs/brain-orchestrator` (stages `brain_platform`, `biological-brain`, `sector-intelligence-brain`, `brain-scores`) | **yes** | `e6a5026f` (label `commit`) | Brain RTDB `/jobs/*`, `/control/orchestrator`, `/scores/*`, `/control/*`; starts `lake-brain` / `water-temp-brain`; runs Biological / Intelligence in-process | no (Ops displays) | Brain Platform |
| `wind-hourly` | Cloud Scheduler `5 * * * *` UTC; **NBM early exit** when the newest cycle is already archived | INTERNAL (science RESEARCH_CANDIDATE) | `brains/wind` (deploy stages only `runtime/` + the platform package into a temp context: `brains/wind/deploy/deploy-job.sh`; moved from `jobs/wind-hourly` in Repository Phase 2) | **yes** | **`e6a5026f` (main; redeployed 2026-10-13)** — env `SECTOR_WIND_BUILD=main@e6a5026f` | `gs://sector-wind-candidate/wind/v1/*` and the Brain RTDB wind slot hourly | no — production wind is Open-Meteo in-process | Wind |
| `wind-candidate-read` (Cloud Run **service**) | on request | INTERNAL | `brains/wind/deploy/read_service` | **yes** | `--source .` 2026-10-07, no commit label | serves `latest/<lake>.json.gz` to 3 master UIDs only | no | Wind |
| `water-temp-tva-archive` | Cloud Scheduler `20 * * * *` UTC (source retains ~24 h) | INTERNAL | `jobs/water-temp-tva-archive` | **yes** | `79b966cc`-era source (no commit label) | `gs://sector-water-temp-archive/water-temp/tva/*` | no (Lake / Water Temp Brains read it) | Water Temp / Lake |
| `lake-surface-dispatch` | Cloud Scheduler `0 3 * * *` America/Chicago (single task, 1 vCPU / 512 Mi) | INTERNAL | `jobs/lake-surface-dispatch` | **yes** | `e6a5026f` | `gs://sector-lake-surface/dispatch/<date>.json`; starts `lake-surface-daily` with `--lakes` for lakes with a newer pass | no | Clarity (satellite) |
| `lake-surface-daily` | **dispatcher-triggered** (its own scheduler is PAUSED, kept) | INTERNAL | `jobs/lake-surface` | **NO — explicit exception.** Live source is `feat/clarity-algal-warning` @ `03937913`; see `jobs/lake-surface/LINEAGE.md`. Not redeployed. | 2026-09-29 build | `gs://sector-lake-surface/lakes/<slug>/clarity/*` | no (Clarity Brain reads `latest.json`) | Clarity |
| `hydrology-hourly` | **PAUSED 2026-10-13** (`15 * * * *` kept) | RESEARCH | `jobs/hydrology-hourly` | **yes** | 2026-09-27 build | `gs://sector-lake-surface/hydrology/<slug>/hourly/<date>.json` | indirectly (`/clarity/state`, which iOS does not call) | Clarity |
| `clarity-current-hourly` | **PAUSED 2026-10-13** (`40 * * * *` kept) | RESEARCH | `Sources/ClarityPrecompute` (fusion lineage, not on main) | **NO — explicit exception** (`03937913`) | `03937913` | `gs://sector-lake-surface/clarity/current/<slug>/*` | no | Clarity |
| `clarity-candidate-shadow` | **PAUSED** (stays) | SHADOW | private (`feat/clarity-candidate-shadow`, never pushed) | **NO — private research** | `6855cb3d` (private) | `gs://sector-clarity-candidate/*` | no | Clarity (research) |
| `lake-brain` | **orchestrator-triggered** (TIME, staleAfterHours 3; pilot 5 lakes); no cron | INTERNAL | `brains/lake/runtime/{LakeBrainJob,LakeBrain}` (SwiftPM) → `/app/LakeBrainJob` in the brain-jobs image; deploy `brains/lake/deploy/deploy-job.sh`; tooling stays in `jobs/lake-brain` | **yes** | `jobs/brain-image-build.sh` (label `commit`) | Brain RTDB lake states for 5 pilots; `gs://sector-lake-brain` | no | Lake |
| `water-temp-brain` | **orchestrator-triggered** (TIME, staleAfterHours 6; fleet); no cron | INTERNAL | `brains/water-temperature/runtime/{WaterTempBrainJob,WaterTemperatureBrain}` (SwiftPM) → `/app/WaterTempBrainJob`; deploy `brains/water-temperature/deploy/deploy-job.sh` | **yes** | `jobs/brain-image-build.sh` | Brain RTDB water-temp states for 621 lakes | no | Water Temp |
| `water-clarity-brain` (manual) | **MANUAL by decision** (`docs/brains/WATER_CLARITY_BRAIN_SCHEDULING.md`) | INTERNAL | `brains/water-clarity` (C1; `jobs/water-clarity-brain` is a retirement pointer) | **yes** | not deployed | Brain RTDB clarity states (621) | no | Water Clarity |
| `biological-brain` | in-process in `brain-orchestrator` when its `plan()` says PUBLISH (VERSION) | INTERNAL | `brains/fish/runtime` (retirement pointer: `jobs/biological-brain`) | **yes** | staged into the orchestrator image | Brain RTDB `/species`, `/brains/biological-state` | no | Biological |
| `sector-intelligence-brain` | in-process in `brain-orchestrator` when its `plan()` says PUBLISH (FINGERPRINT; pilot only) | INTERNAL | `jobs/sector-intelligence-brain` | **yes** | staged into the orchestrator image | Brain RTDB `/brains/sector-intelligence`, pilot states | no | Sector Intelligence |
| `brain-scores` | in-process in `brain-orchestrator` after a state change (`--if-changed`); also manual | INTERNAL | `jobs/brain-scores` | **yes** | staged into the orchestrator image | Brain RTDB `/scores/*`, `/control/*` | no (Ops displays) | Brain Platform |

The `/jobs/{jobId}` records (`docs/brains/JOBS_CONTRACT.md`) are the live version of this table: Cloud
Scheduler is authoritative for enabled / cron / next run, and the classification column above is the manifest
in `jobs/brain_platform/sector_brain_platform/jobs.py`.

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
(cd brains/wind && ../../.venv/bin/python -m pytest -q)                      # Wind Brain; network tests deselected by pytest.ini
(cd jobs/brain_platform && ../../.venv/bin/python -m pytest -q)              # platform incl. the /jobs contract
(cd jobs/lake-surface-dispatch && ../../.venv/bin/python -m pytest -q)       # satellite dispatcher
(cd jobs/brain-orchestrator && ../../.venv/bin/python -m pytest -q)          # orchestrator executor
```
`.github/workflows/python-jobs-tests.yml` runs the same offline suites on GitHub (no credentials).
`shapely` and `pyproj` are needed only by the Stage 3A field-ops tests, not by the job image.
