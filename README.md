# Sector Engine

The **single source of truth** for Sector's bowfishing shooting-conditions scoring.
Extracted from the iOS app into a standalone Swift service so **iOS, Android, and
any future client render identical results** from one engine — change the scoring
here and every phone picks it up on its next call, no app-store release.

Pure Swift, no UI. Runs as an HTTP service on **Google Cloud Run**, in the same GCP
project as Firebase (`sector-9393c`).

**Live:** `https://sector-engine-e43utajroa-uc.a.run.app`

Status: **live in production.** Both the iOS and Android apps render every conditions
surface (dashboard gauge, tiles, breakdown, where-to-look, tonight window + 7-night
outlook, My Lakes, redzone detail, trips, lake alerts) from this service — no
on-device scoring engine. Tuning is driven live from Firebase Remote Config.

## Endpoints
| Method | Path | Returns |
|---|---|---|
| `GET`  | `/health` | `ok` |
| `GET`  | `/conditions?lat=&lon=` | the full render payload for one coordinate |
| `POST` | `/conditions/batch` | `{points:[{lat,lon}]}` → slim `{score,band}` per point (My Lakes rings) |
| `GET`  | `/lakes` | the lake directory `{version, count, lakes}` both apps search; ETagged, so `If-None-Match` gets a 304 |

The lake directory is generated from `docs/data/Sector_Lakes_APIs_2.xlsx` by
`scripts/generate-lake-directory.py`; the apps ship a snapshot of `/lakes` for a first
launch offline (the script's header says how to refresh it). Each lake carries its
normal **full pool** from `docs/data/full_pool.csv` (see `docs/data/FULL_POOL.md`), and
`/conditions` reports it beside the reservoir pool (`generation.fullPoolFt`) so a lake
reads as flooded or drawn down.

`/conditions` returns the **complete** payload every client needs to render without a
local engine: score / band / regime / confidence, the per-factor breakdown, gates,
where-to-look, the tonight window with its hourly curve, the 7-night outlook with
per-night breakdowns, and the raw live readings (weather, water, dam generation with
release windows, modeled water-temp series, NWS alerts, moon). Clients keep only
presentation (icons, tints, prose, timezone-local formatting) and an ephemeris; they
rebuild their own domain types from this JSON so existing views render unchanged.

## Layout
- `Sources/SectorEngine/Engine/` — the pure engine (aggregator, gates, factors, config, astronomy) + `RemoteConfigStore` + `ConditionsConfigOverrides`
- `Sources/SectorEngine/Fetchers/` — weather / water / temp / alerts data sources
- `Sources/SectorEngine/Forecast/` — 7-night outlook + tonight's window + snapshot provider (both cached)
- `Sources/SectorEngine/Support/` — value-type support + the Linux shims (`CoreLocationShim`, `ObservableShim`)
- `Sources/SectorEngine/API/` — `SectorEngineAPI` + `ConditionsResponse`, the one public entry point + DTO every client calls
- `Sources/SectorEngineServer/` — thin Hummingbird HTTP server (the routes above)
- `Tests/` — the engine's regression suite (76 tests)

## Build & test (macOS)
```
swift build
swift test
swift run SectorEngineServer      # serves http://localhost:8080
```
The Linux shims supply CoreLocation / Combine stand-ins where those Apple frameworks
don't exist, so the *exact same engine* compiles for the server. (Locally, off Cloud
Run, the Remote Config fetch no-ops and the engine uses its compiled defaults.)

## Deploy (Cloud Run)
No local Docker needed — Cloud Build compiles the `Dockerfile` server-side.
```
# one-time
gcloud auth login
gcloud config set project sector-9393c
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
# every deploy
./deploy.sh
```
Change the engine → `./deploy.sh` → both phones pick up the new numbers on their next
call. Scales to zero (≈ $0/mo idle).

**Performance:** warm requests ~90 ms (forecast + snapshot caches, request coalescing);
cold ~15–20 s (first hit after scale-to-zero, all upstream fetches). Independent fetches
run in parallel and every upstream call is timeout-bounded so one slow source can't
tentpole a response.

## Live tuning — Firebase Remote Config
Scoring knobs can change **without a redeploy**. The server reads a `conditions_config`
Remote Config parameter (a typed `ConditionsConfigOverrides` JSON blob — per-regime
factor weights + high-value thresholds), applies it onto the compiled
`ConditionsConfig.default`, and scores both the gauge and the forecast with the result.
Cached ~10 min; every failure path falls back to defaults, so a config outage is harmless.

One-time setup: grant the Cloud Run service account `roles/cloudconfig.viewer`, then create
a JSON parameter named `conditions_config` in the Firebase console (Remote Config →
Parameters). Example — starve the two biggest factors:
```json
{ "weightsNormal": { "wind": 0.02, "clarity": 0.02 } }
```
Publish → both phones score with the new knobs within ~10 minutes. No deploy, no release.

## History
Built in phases (all complete): engine extracted → HTTP server → iOS A/B parity →
Linux + Cloud Run → iOS on the DTO → Android on the DTO → Firebase Remote Config tuning.
See `docs/audits/` in the iOS repo for the migration audit.
