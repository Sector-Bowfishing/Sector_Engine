# Current Repository Map

> Current-state inventory (fact at `fab115e9`). Action labels remain planning labels; the locked target is in `TARGET_REPOSITORY_ARCHITECTURE_V1.md`. In the target, the Lake registry rows below land in `platform/registries/lakes/` (Platform-owned identity), not in Lake Brain.

Base `fab115e9`. **Action labels are planning labels only; nothing is executed.**
Labels: `KEEP` `MOVE_LATER` `MERGE_LATER` `RENAME_LATER` `DEPRECATE_LATER` `REFERENCE` `REVIEW` `UNKNOWN`.
Categories: **E** customer Engine · **P** provider/acquisition · **PL** Brain Platform · **B:<id>** specialist Brain · **C** shared contract · **T** tests · **G** governance docs · **H** historical · **R** research · **D** data · **X** build/deploy/CI.

## 1. Repository root

| Path | Current purpose | Owner | Canonical? | Future category | Action |
|---|---|---|---|---|---|
| `Package.swift`, `Package.resolved` | SwiftPM manifest (1 library, 4 executables, 1 test target) | Engine + Brains (shared) | yes | X (stays at root; targets get new `path:`) | KEEP, edit targets later |
| `Sources/` | all Swift | mixed | yes | E / P / PL / B | MOVE_LATER (by target) |
| `Tests/` | all Swift tests, one flat target | mixed | yes | T per owner | MOVE_LATER |
| `Dockerfile`, `.dockerignore` | builds server **and** the Lake/Water Temp job binaries into one image | Engine + Brains | yes | X | KEEP; split image per deploy unit later |
| `deploy.sh` | deploys customer `sector-engine` service | Engine | yes | X | KEEP |
| `README.md` | describes only the customer Engine (layout section omits Brains/jobs/platform) | Engine | stale in part | G | REVIEW (re-point to architecture map) |
| `jobs/` | 14 job dirs: runtime jobs, Brain code, research tooling, platform lib, deploy scripts | mixed | yes | PL / B / P | MOVE_LATER |
| `docs/` | 454 files: architecture, per-Brain docs, runtime JSON, history, data | mixed | yes | G / H / C / D | MOVE_LATER (split) |
| `scripts/` | lake directory/bindings generators; `scripts/hydrology/*` (Clarity research) | Lake / Clarity | yes | B:lake / B:water-clarity | MOVE_LATER |
| `ops/` | alerting setup, warm-tag check | Platform ops | yes | PL | MOVE_LATER |
| `.github/workflows/python-jobs-tests.yml` | only CI | Platform | partial coverage | X | REVIEW (add Swift, missing Python dirs) |
| `.gitignore` | ignores `__pycache__` yet two `.pyc` are tracked | — | — | X | REVIEW |

## 2. `Sources/`

| Path | Lines | Purpose | Category | Action |
|---|---|---|---|---|
| `SectorEngine/Engine/` (Aggregator, Factors, Config, Region, WhereToLook, Adapters, `RemoteConfigStore`, etc.) | 5.2 k | customer Conditions Score: factors, gates, config, dam-generation adapters | E (Adapters are P) | MOVE_LATER |
| `SectorEngine/Engine/Adapters/` (TVA, SWPA, Alabama Power, CWMS generation services) | in 5.2 k | provider clients + parsers | **P** | MOVE_LATER (to providers) |
| `SectorEngine/Engine/Config/SpeciesDatabase.swift`, `SpeciesLegality.swift` | — | spawn knowledge (18 rows) + legality gate in scoring path | E (adapters of Fish/Policy) | REVIEW (decision D5 pending) |
| `SectorEngine/Fetchers/` (Weather, WaterLevel, WaterTemperature, USGS, Alerts, MRMS, LakeTempSensor) | 2.5 k | provider clients used by `/conditions` **and** Water Temp Brain | **P** | MOVE_LATER |
| `SectorEngine/Forecast/` | 1.1 k | 7-night outlook + snapshot (Open-Meteo hourly) | E | KEEP (moves with E) |
| `SectorEngine/API/` | 1.2 k | `SectorEngineAPI`, `ConditionsResponse`, lake directory API, clarity state API, hydrology API | E | MOVE_LATER |
| `SectorEngine/Support/` | 1.2 k | HTTP/Deadline/Coordinate/shims **plus** `LakeDirectory.swift` (621-lake registry) and `LakeDirectorySearch` | mixed: E support + **B:lake registry** | MOVE_LATER (split) |
| `SectorEngine/Brain/` | 1.5 k | Swift Brain Platform (`BrainPlatform`, `BrainContract`, `BrainRTDBStore`) **and** `WaterTemperatureBrain(+Runner)` | PL + B:water-temp | MOVE_LATER (split) |
| `SectorEngine/WaterTemp/` | 0.2 k | water-temp state types, local-date | B:water-temp | MOVE_LATER |
| `SectorEngine/LakeBrain/` | 3.9 k | Lake Brain runtime, bindings (425 KB generated), ledger, species-presence validator, level baseline/classifier/feeds | B:lake | MOVE_LATER |
| `SectorEngine/Hydrology/` | 2.0 k | Clarity: graph, gauge, state, visibility model, 103 KB generated data | B:water-clarity (consumed by E) | MOVE_LATER (REVIEW boundary) |
| `SectorEngineServer/` | 0.1 k | Hummingbird routes | E | MOVE_LATER |
| `LakeBrainJob/`, `WaterTempBrainJob/` | 0.1 k, 0.05 k | job entrypoints | B:lake, B:water-temp | MOVE_LATER |
| `ClarityReplay/` | 0.2 k | replay tool for Clarity | B:water-clarity (R tool) | REVIEW |
| *(branch-only)* `ClarityPrecompute/` | — | live `clarity-current-hourly` source | B:water-clarity | REVIEW (D4) |

## 3. `Tests/`

| Path | Owner | Action |
|---|---|---|
| `ConditionsAggregatorTests`, `ConditionsConfigOverridesTests`, `ConditionsFactorTests`, `ForecastRain*`, `FullPoolTests`, `LakeDirectoryAPITests` | E (the last two touch Lake registry) | MOVE_LATER |
| `USGSWaterDataTests` + `Fixtures/USGS/*` (12 fixture files, ~0.9 MB) | P | MOVE_LATER |
| `BrainPlatformConformanceTests` | PL (Swift side) | MOVE_LATER |
| `LakeBrain*`, `LakeBaselineRateFilter`, `LakeFleetVisibility`, `LakePredictionLedger`, `LakeRulesV2`, `LakeSurfaceSlug` | B:lake | MOVE_LATER |
| `WaterTemp*` (5 files), `WaterTemperatureBrain*` (2) | B:water-temp | MOVE_LATER |
| `Clarity*`, `HydrologyGraphTests` | B:water-clarity | MOVE_LATER |

## 4. `jobs/`

| Path | Purpose | Category | Action |
|---|---|---|---|
| `jobs/README.md` | live job registry & lineage (valuable) | G / PL | KEEP → becomes platform registry doc |
| `jobs/brain-image-build.sh` | builds the Swift Brain-jobs image | X | MOVE_LATER |
| `jobs/brain_platform/` (`sector_brain_platform`, 25 modules, 9 test files) | Python Brain Platform library | PL | MOVE_LATER (becomes installable package) |
| `jobs/brain-orchestrator/` | orchestrator executor, control plane, lineage preflight, deploy | PL | MOVE_LATER |
| `jobs/brain-scores/` | score publisher + checks; tests as loose top-level files | PL | MOVE_LATER (+ test move) |
| `jobs/wind-hourly/` | Wind Brain job + `sector_wind` package + `brain/` + `read_service` + `research/` + docs + tests | B:wind (+R) | MOVE_LATER (**first**) |
| `jobs/biological-brain/` | Fish Brain bundle loader/publisher + 3 shims + schemas | B:biological-state | MOVE_LATER |
| `jobs/sector-intelligence-brain/` | registry/dependency/per-lake inputs publisher + `catalog.json` + `evaluation.py` | B:sector-intelligence | MOVE_LATER |
| `jobs/water-clarity-brain/` | Clarity Brain publisher (catalog, fixtures) | B:water-clarity | MOVE_LATER |
| `jobs/lake-surface/` (+`-dispatch`) | satellite derive/dispatch; **live source is off-main** (`LINEAGE.md`); 7.5 MB polygons | B:water-clarity (acquisition) / P | REVIEW (D4) |
| `jobs/hydrology-hourly/` | hourly hydrology ingest (PAUSED) | B:water-clarity / P | REVIEW |
| `jobs/lake-brain/` | **no runtime**: deploy script + validation, history backfill, review pack, ledger scoring, bindings builder, proposed bindings JSON | B:lake (tooling, V, R, D) | MOVE_LATER (classify per file) |
| `jobs/lake-geometry/` | geometry build/verify (Lake registry geometry) | B:lake | MOVE_LATER |
| `jobs/water-temp-brain/` | **only** `deploy-job.sh` (code is in `Sources/`) | B:water-temp | RENAME_LATER / MERGE_LATER |
| `jobs/water-temp-tva-archive/` | TVA discharge archive (acquisition) consumed by Water Temp + Lake | P (archive) | MOVE_LATER |

## 5. `docs/`

| Path | Files | Nature | Category | Action |
|---|---|---|---|---|
| `docs/architecture/data/` | 16 | data-ownership architecture (partly superseded) | G | KEEP; supersession banners present |
| `docs/architecture/certification/` | 8 | Certification V1 foundation (approved) | G | KEEP |
| `docs/architecture/repository-audit-v1/` | 10 (new) | this audit | G | KEEP |
| `docs/brains/*.md` (flat) | 40 | mix: platform contracts, Lake ×11, Clarity ×4, Intelligence ×2, Fish ×1, Water Temp ×1, matrices, TODOs | G / per-Brain | MOVE_LATER (split into `platform` and per-Brain) |
| `docs/brains/platform/` | 43 | platform models + `cost-freeze/snapshots/*.json` (live job snapshots) | PL / H | MOVE_LATER; REVIEW snapshots for private content |
| `docs/brains/conformance/` | 11 JSON | **cross-language test fixtures** (CI-triggering) | C | MOVE_LATER (to `contracts/conformance`) |
| `docs/brains/scoring/` | 9 | scoring doc + rubric JSON + `frozen-scores.json` (**staged into orchestrator image**) | PL / B | MOVE_LATER (rubrics → Brain homes) |
| `docs/consolidation/`, `docs/clarity/`, `docs/scope/`, `docs/production/` | 11 | dated handoffs, cost audits, lineage | H (+`PRODUCTION_LINEAGE` is governance) | MOVE_LATER to `docs/history/` (keep lineage) |
| `docs/data/` | 4 + hydrology | `Sector_Lakes_APIs_2.xlsx` (registry source), `full_pool.csv`, `temp_sensors.csv`, `FULL_POOL.md`; `hydrology/` 327 files 12 MB | D | MOVE_LATER; REVIEW size policy |

## 6. `scripts/`, `ops/`

| Path | Purpose | Category | Action |
|---|---|---|---|
| `scripts/generate-lake-directory.py`, `generate-lake-bindings.py` | generate Swift lake directory/bindings from xlsx / bindings JSON | B:lake | MOVE_LATER |
| `scripts/hydrology/*` (18 py, 1 README, 2 `.pyc`) | Clarity research/build pipeline; hard-coded iOS paths; imports `jobs/lake-surface` | B:water-clarity (R) | MOVE_LATER / REVIEW; delete `.pyc` later |
| `ops/setup_alerting.py`, `check_warm_tags.sh` | alerting/ops | PL | MOVE_LATER |
