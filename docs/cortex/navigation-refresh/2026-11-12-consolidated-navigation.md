# Sector Engine Navigation Refresh Report
Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine
Snapshot compared: sector-engine@7dae705-2026-10-20
Engine repository: Sector-Bowfishing/Sector_Engine · HEAD 939a0fa08023edc37b0de5ef165dd24225a1bddb · ref origin/main ("Merge pull request #170 … cortex/lake-release-approval-2026-11-12") · Date 2026-11-12
Drift command output: `cortex.py drift sector/engine --repo .` at HEAD `939a0fa08023`: 816 files changed since the snapshot; 32 items need verification. MISSING: the Lake Swift runtime and contract under the old customer library path and `jobs/lake-brain/deploy-job.sh`; the Water Temp Swift runtime files and `jobs/water-temp-brain/deploy-job.sh`; five Intelligence files under `jobs/sector-intelligence-brain/`. NOW-EXISTS: `brains/lake`, `brains/water-temperature`, `brains/sector-intelligence`. BRANCH-ABSENT: `feat/depth-brain-foundation`, `feat/vegetation-brain-foundation`. CHANGED: orchestrator, scorer, rubrics, Publisher (shadow and live), customer Engine, feeder jobs, images, CI workflows, cross-component verification. "Brain inventory in `jobs/brain_platform/sector_brain_platform/control_manifest.json` matches the snapshot (8 Brains)."

**Why one consolidated report.** Cortex holds exactly one source document per snapshot (`REFRESH.md`, "How a Cortex session imports artifacts"). The five earlier refresh artifacts in this folder (`2026-10-20-architecture-all-brains.md`, `2026-10-20-architecture-completion.md`, `2026-10-20-cortex-2-1-memory.md`, `2026-10-20-cortex-2-1-structural-completion.md`, `2026-10-21-cortex-2-2-firebase-data.md`) were never imported, and later work moved again. This report replaces them as the import candidate. It records the changes (table below) **and** restates the whole navigation at HEAD in sections A–G, so a new snapshot can be grounded in this file alone. Section letters match the 2026-10-20 discovery report, so evidence references (§A…§G) keep their meaning.

**Evidence labels:**
- **[V]** verified by inspection of `939a0fa08023` (git ls-tree / cat-file / show, JSON reads, local test runs).
- **[V-prod 2026-11-12]** read-only production observation through the repository's `ops-status` workflow (run 43267613577, 2026-11-12T17:16Z, read-only status account). Dated, not live status.
- **[REPORTED]** stated in an owner-approved Sector_Ops comment or a session record at HEAD; not re-observed here.
- **NOT VERIFIED** not established.

No Engine, Cortex, Firebase or Git state was changed by this inspection, apart from committing this file on its branch. No secrets or private research locations are recorded. Every path is repository-relative.

## Changes

| # | Snapshot ID affected | Change type | Was (snapshot) | Now (HEAD) | Evidence | Label |
|---|---|---|---|---|---|---|
| 1 | `brain.lake-brain`, obs.01 | RELOCATED | Swift runtime inside the customer library under `Sources/`; no package; `brains/lake/` reserved, absent | Canonical package `brains/lake/` with `brains/lake/brain.json`, `brains/lake/BRAIN_OPERATING_CONTRACT.md`; SwiftPM targets `brains/lake/runtime/LakeBrain/` (library `LakeBrain`) and `brains/lake/runtime/LakeBrainJob/main.swift`; deploy `brains/lake/deploy/deploy-job.sh`; offline tooling stays in `jobs/lake-brain/` | `Package.swift` lines 44–45, 60; `jobs/README.md` row `lake-brain`; `git ls-tree 939a0fa brains/lake/` | VERIFIED_IMPLEMENTATION |
| 2 | `brain.water-temp`, obs.01 | RELOCATED | Swift files under the customer library `Brain/` folder and executable under `Sources/`; no package | Canonical package `brains/water-temperature/`; SwiftPM targets `brains/water-temperature/runtime/WaterTemperatureBrain/` and `brains/water-temperature/runtime/WaterTempBrainJob/main.swift`; deploy `brains/water-temperature/deploy/deploy-job.sh`; `jobs/water-temp-brain/` is a README pointer | `Package.swift` lines 47–48, 61; `jobs/water-temp-brain/README.md` | VERIFIED_IMPLEMENTATION |
| 3 | `brain.sector-intelligence`, obs.01 | RELOCATED | `jobs/sector-intelligence-brain/` (run, module, evaluation, catalog, tests) | Canonical package `brains/sector-intelligence/`; runtime `brains/sector-intelligence/runtime/run.py`; `jobs/sector-intelligence-brain/README.md` is a pointer; the orchestrator image still stages the runtime under the legacy layout | `jobs/sector-intelligence-brain/README.md`; `control_manifest.json` `executionTarget.dir` | VERIFIED_IMPLEMENTATION |
| 4 | `brain.depth`, `brain.vegetation`, obs.06 | RELOCATED | Branch-only (`feat/depth-brain-foundation`, `feat/vegetation-brain-foundation`) | On `main` as `brains/depth/` and `brains/vegetation/`; the branches no longer exist on origin; both run only the SHADOW lane (`executionTarget.kind: none`, `shadowLane.enabled: true`) | `git ls-tree 939a0fa brains/`; `control_manifest.json` | VERIFIED_IMPLEMENTATION |
| 5 | obs.01 | OBSERVATION_RESOLVED | Three registered Brains lacked packages | All eight registered Brains have `brains/<dir>/brain.json`, an operating contract and a Kit V1 adapter (`brains/<dir>/tests/test_*_kit_certification.py`) | §B, §C (cert kit row) | VERIFIED_IMPLEMENTATION |
| 6 | obs.06 | OBSERVATION_RESOLVED | Depth and Vegetation registered but not on `main` | Both on `main` (row 4) | §B | VERIFIED_IMPLEMENTATION |
| 7 | obs.03 | OBSERVATION_RESOLVED | Wind `brain.json` `trigger.staleHours: 6` vs manifest 1.5 | `brains/wind/brain.json` `runtime.trigger.staleHours: 1.5`, manifest `freshness.staleAfterHours: 1.5` | JSON reads at HEAD | VERIFIED_IMPLEMENTATION |
| 8 | `edge.sched-wind`, `edge.sched-lake`, `brain.wind`, `brain.lake-brain`, obs.11 | ROUTE_REMOVED / OWNERSHIP_CHANGED | Wind and Lake ran on their own Cloud Schedulers outside the orchestrator | Central scheduling (Cortex PL-15, 2026-10-23): the orchestrator starts the `wind-hourly` and `lake-brain` jobs when due; their own schedulers are `deprecatedScheduler … state PAUSED, never resume` in the manifest | `control_manifest.json` `brains.wind.schedule`, `brains.lake-brain.schedule` | VERIFIED_IMPLEMENTATION (repo); scheduler objects NOT VERIFIED |
| 9 | `platform.orchestrator` | ROUTE_ADDED | Orchestrator scheduler PAUSED [V-prod 2026-10-20] | Scheduler `brain-orchestrator` ENABLED `50 * * * *`; last five real cycles succeeded; watchdog latch none | ops-status run 43267613577 | PRODUCTION_OBSERVATION 2026-11-12 |
| 10 | `brain.water-clarity` | ROUTE_ADDED | MANUAL Cloud Run job | Orchestrator-owned job `water-clarity-brain` (`executionTarget.kind: cloud-run-job`); runner policy makes **Pulse** its primary runner (`water-clarity: pulse`, approval `owner-approval-2026-11-06/sector-ops-51-o4`), failover off; published centrally (`publication-cutover.json` `water-clarity: CENTRAL`) | `jobs/brain_platform/sector_brain_platform/runner-policy.json`; `jobs/brain-orchestrator/publication-cutover.json` | VERIFIED_IMPLEMENTATION; live Pulse runs REPORTED |
| 11 | new `platform.runner-leases`, `external.sector-pulse`, verify.04 | ROUTE_ADDED | Pulse not located; no Pulse code in the Engine | Hybrid flow: the cloud Orchestrator grants per-Brain leases (`jobs/brain_platform/sector_brain_platform/runner_lease.py`, policy `runner-policy.json`); Pulse runs the Brain locally and uploads the sealed artifact through `tools/runner/runner.py`; the Orchestrator and Publisher stay in Cloud Run. Design `docs/architecture/production/RUNNER_LEASE_AND_UPLOADER_V1.md` | §C, §D.1 | VERIFIED_IMPLEMENTATION (Engine side); Pulse repository NOT VERIFIED |
| 12 | new `job.brain-publisher`, `platform.publisher-live`, obs.04, verify.03 | OWNERSHIP_CHANGED | Publisher LIVE implemented, imported by nothing, zero production writes | Recurring Publisher job `jobs/brain-publisher/publish_job.py`, started by the Orchestrator (`PUBLICATION_HANDOFF`), publishes Brains marked CENTRAL in the reviewed cutover document (Water Clarity only at HEAD). `publisher_live/` also builds CUSTOMER-lane copies (`customer_copies.py`, `customer_clarity.py`, `customer_water_temp.py`, `customer_lake_level.py`, `customer_wind_outlook_model.py`, `customer_generation_binding.py`). Every other Brain is DIRECT_WRITE | `jobs/brain-orchestrator/publication-cutover.json`; `jobs/brain_platform/sector_brain_platform/cutover_order.json`; imports in `jobs/brain-orchestrator/clarity_pilot.py` | VERIFIED_IMPLEMENTATION (repo); production write lineage NOT VERIFIED |
| 13 | new `job.water-clarity-h1-shadow` | ROUTE_ADDED | — | `jobs/water-clarity-h1-shadow/h1_shadow.py`: SHADOW lane on Pulse; writes a local file only, no database, no customer path | `jobs/water-clarity-h1-shadow/README.md` | VERIFIED_IMPLEMENTATION |
| 14 | new `job.lake-level-crosscheck` | ROUTE_ADDED | — | `jobs/lake-level-crosscheck/crosscheck.py`: 30-day read-only collector on Pulse (Lake Barkley vs an independent USACE gauge); appends local JSON lines only | `jobs/lake-level-crosscheck/README.md` | VERIFIED_IMPLEMENTATION |
| 15 | `job.water-temp-tva-archive` | CORRECTION | Archive PAUSED | Code at `jobs/water-temp-tva-archive/` (archive, merge, deploy script refusing without approval). Live scheduler state NOT VERIFIED here | `jobs/water-temp-tva-archive/README.md`; `jobs/README.md` | VERIFIED_IMPLEMENTATION |
| 16 | `ci.github-workflows` | ROUTE_ADDED | Three CI workflows | Plus four manual workflows: `.github/workflows/deploy-engine.yml` (WIF deploy of `sector-engine` with cycle preflight, smoke, live phone-contract check, automatic rollback), `.github/workflows/deploy-orchestrator.yml`, `.github/workflows/ops-status.yml` (read-only status account), `.github/workflows/set-conditions-tiles.yml` (Remote Config `conditions_tiles_v1` presets, never `serve`); and CI `.github/workflows/image-build-verification.yml` | workflow headers at HEAD | VERIFIED_IMPLEMENTATION |
| 17 | `service.customer-engine`, obs.05 | CONTRACT_CHANGED / DEPENDENCY_CHANGED | Endpoints `/conditions`, `/conditions/batch`, `/lakes`, `/health`; reads no Brain output | Adds flag-gated endpoints that read **only CUSTOMER-lane copies** through a configured reader: `GET /lakes/ready` (`SECTOR_LAKES_READY_OUTPUT`, `Sources/SectorEngine/API/LakesReadyAPI.swift`, contract `contracts/phone/lakes-ready-v1.json` 1.2.0) and `GET /lake/level` (`SECTOR_LAKE_LEVEL_OUTPUT`). Both flags default off. Phone contract `contracts/phone/conditions-phone-contract-v1.json`; tile flags under `Sources/SectorEngine/Conditions/` | `Sources/SectorEngineServer/main.swift` lines 155–195 | VERIFIED_IMPLEMENTATION |
| 18 | `service.customer-engine`, obs.07 | CORRECTION | Service built from an older `main` commit | Serving revision `sector-engine-00092-sem`, 100 % traffic, commit label `fd1aa21d9b81`, which is an ancestor of HEAD | ops-status run 43267613577; `git merge-base --is-ancestor fd1aa21d 939a0fa` | PRODUCTION_OBSERVATION 2026-11-12 |
| 19 | obs.12 | OBSERVATION_CHANGED | Swift Brain jobs inside the customer `SectorEngine` library target | Separate SwiftPM targets in their packages (`LakeBrain`, `LakeBrainJob`, `WaterTemperatureBrain`, `WaterTempBrainJob`) that still **depend on** the shared `SectorEngine` library; the customer server imports neither | `Package.swift` | VERIFIED_IMPLEMENTATION |
| 20 | obs.08 | OBSERVATION_CHANGED | `platform/publisher/README.md` stale | Still stale (says Publisher LIVE owns no production writes and every Brain writes directly). `brains/README.md` is also stale: it says Depth and Vegetation exist only on unmerged branches | file reads at HEAD | VERIFIED_IMPLEMENTATION |
| 21 | `legacy.retired-job-stubs` | DEPRECATED | Five stubs | Seven README/deploy pointers: `jobs/biological-brain/`, `jobs/water-clarity-brain/`, `jobs/wind-hourly/`, `jobs/clarity-current/`, `jobs/water-temp-brain/`, `jobs/sector-intelligence-brain/` (README only); `jobs/lake-brain/` is **not** a stub (offline tooling) | §B | VERIFIED_IMPLEMENTATION |
| 22 | `framework.cert-kit-v1` | CERTIFICATION_CHANGED | Adopted by three Brains | Adopted by all eight (§C) | `git ls-tree -r 939a0fa brains/*/tests` | VERIFIED_IMPLEMENTATION |
| 23 | verify.01 | OBSERVATION_RESOLVED | Intelligence 32/33, failing test unknown | `cd brains/sector-intelligence && python -m pytest -q`: 115 passed at HEAD | local run, §G | VERIFIED_IMPLEMENTATION |
| 24 | verify.06 | OBSERVATION_CHANGED | Tests not re-run | Python suites re-run at HEAD (§G); Swift and Wind not run here | §G | VERIFIED_IMPLEMENTATION |
| 25 | new `client.mobile-apps` note | CORRECTION | — | `ConditionsGateway` (Engine first, then cache, then on-device) is client code in the iOS, Android and Web repositories; the Engine repository has no such symbol. Its Engine side is `/conditions`, `/lakes/ready` and the phone contracts | `git grep ConditionsGateway 939a0fa` (only docs under `docs/architecture/conditions/`) | VERIFIED_IMPLEMENTATION (absence); client code NOT VERIFIED |

---

## A. Repository overview

| Item | Value |
|---|---|
| Repository | `Sector-Bowfishing/Sector_Engine` (GitHub) [V] |
| Default branch | `main` |
| Inspected commit | `939a0fa08023edc37b0de5ef165dd24225a1bddb` (`origin/main`, merge of PR #170) [V] |
| Inspection date | 2026-11-12 |
| Stack | **Swift 6.1 / SwiftPM** (customer Engine; Lake and Water Temp Brain targets; clarity tools; `Package.swift`, Hummingbird, AsyncHTTPClient); **Python 3.12** (Brain platform, orchestrator, scorer, Publisher, Python Brains; mostly stdlib) [V] |
| Runtime platform | Google Cloud Run (service `sector-engine`, Cloud Run jobs), Cloud Scheduler (`brain-orchestrator` only, by design), GCS, Firebase Realtime Database, Firebase Remote Config, project `sector-9393c`; Sector Pulse on the owner's Mac mini for leased Brain runs and local collectors [V repo; V-prod 2026-11-12 for the scheduler and service] |
| Config entry points | `Package.swift`; `Dockerfile` (server + `LakeBrainJob` + `WaterTempBrainJob`); `deploy.sh`; `jobs/brain-image-build.sh`; `brains/*/deploy/deploy-job.sh`; `jobs/brain-orchestrator/deploy-job.sh`; `jobs/brain-publisher/deploy-job.sh`; `jobs/brain_platform/sector_brain_platform/control_manifest.json`; `jobs/brain_platform/sector_brain_platform/runner-policy.json`; `jobs/brain-orchestrator/publication-cutover.json`; `providers/PROVIDERS.json`; `.github/workflows/*.yml` [V] |

### Top-level organization

| Directory | Status | Actual content |
|---|---|---|
| `Sources/`, `Tests/` | **Live code** | Swift: customer Engine (`Sources/SectorEngine/`), server (`Sources/SectorEngineServer/`), clarity tools (`Sources/ClarityReplay/`, `Sources/ClarityPrecompute/`), test suite (`Tests/SectorEngineTests/`) |
| `brains/` | **Live** | Eight canonical packages: `brains/fish/`, `brains/wind/`, `brains/water-clarity/`, `brains/lake/`, `brains/water-temperature/`, `brains/sector-intelligence/`, `brains/depth/`, `brains/vegetation/`, plus `brains/_template/` |
| `jobs/` | **Live** | Platform Python (`jobs/brain_platform/`, `jobs/brain-orchestrator/`, `jobs/brain-scores/`, `jobs/brain-publisher/`), Lake offline tooling (`jobs/lake-brain/`), feeder and archive jobs, Pulse collectors, retired pointers |
| `contracts/` | **Live** | `contracts/schemas/`, `contracts/conformance/`, `contracts/phone/` (customer phone contracts), `contracts/moon/` |
| `tools/` | **Live** | `tools/architecture/`, `tools/brain_certification/`, `tools/deploy/` (ops status, tile flag, job env), `tools/runner/` (Pulse uploader), `tools/cutover/`, `tools/knowledge/`, `tools/cortex_status/`, `tools/conditions_golden/`, `tools/ops/`, `tools/research/` |
| `verification/` | **Live** | Cross-component gates and golden fixtures |
| `providers/` | **Live (catalog only)** | `providers/PROVIDERS.json` |
| `platform/` | **Mostly structure only** | READMEs, except `platform/registries/signals/signals.json`, `platform/registries/species/species_water_domains.json` and `platform/security/` (`rtdb.rules.target.json`, `rtdb.rules.customer-copies.PROPOSED.json`, `publisher_security_plan.json`, `identity_split_plan.json`; repo-only target model) |
| `engine/`, `deploy/` | **Structure only** | README |
| `ops/` | Small live scripts | `ops/check_warm_tags.sh`, `ops/setup_alerting.py` |
| `scripts/` | Live generators | `scripts/generate-lake-directory.py`, `scripts/generate-lake-bindings.py`, `scripts/hydrology/`, `scripts/linux-smoke.sh` |
| `docs/` | Docs | Architecture, Brain integration, platform, Cortex records (`docs/cortex/`), scoring rubrics (`docs/brains/scoring/` **is load-bearing**: rubrics and frozen scores are read at runtime and staged into images) |

---

## B. Brain inventory

Identity sources: `tools/architecture/stable_brain_ids.json` (8 directory → ID entries), `jobs/brain_platform/sector_brain_platform/control_manifest.json` (`brains{}`, 8 entries), `jobs/brain_platform/sector_brain_platform/jobs.py` (`MANIFEST`) and each `brains/<dir>/brain.json` [V]. **All eight registered Brains now have a canonical package.**

| Stable ID | Name | Package | Manifest / operating contract | Runtime entry point | Output contracts | Tests and Kit adapter | Execution (manifest at HEAD) |
|---|---|---|---|---|---|---|---|
| `biological-state` | Fish | `brains/fish/` | `brains/fish/brain.json`, `brains/fish/BRAIN_OPERATING_CONTRACT.md` | `brains/fish/runtime/run.py` (`--plan`, `--dry-run --offline`, `--write`, `--patch-species-metadata`); capability `brains/fish/runtime/capability_run.py` | `brains/fish/contracts/fish-publication-v1.json`, `brains/fish/contracts/fish-biological-assessment-v1.json` | `brains/fish/tests/` (`brains/fish/tests/test_fish_kit_certification.py`) | In-process in `brain-orchestrator` (`executionTarget.dir: brains/fish/runtime`), staged by `jobs/brain-orchestrator/deploy-job.sh` under the legacy layout `jobs/biological-brain/`; INPUT_DRIVEN |
| `wind` | Wind | `brains/wind/` | `brains/wind/brain.json`, `brains/wind/BRAIN_OPERATING_CONTRACT.md` | `brains/wind/runtime/main.py` (package `brains/wind/runtime/sector_wind/`) | `brains/wind/contracts/wind-publication-v1.json`, `brains/wind/contracts/wind-exposure-assessment-v1.json`, `brains/wind/contracts/wind-validation-entrypoints-v1.json` | `brains/wind/tests/` (`brains/wind/tests/test_wind_kit_certification.py`), `brains/wind/research/tools/tests/` | Cloud Run job `wind-hourly` via `brains/wind/deploy/deploy-job.sh`, **started by the orchestrator** when due (1.5 h); its own scheduler deprecated and PAUSED; read service `brains/wind/deploy/read_service/` |
| `water-clarity` | Water Clarity | `brains/water-clarity/` | `brains/water-clarity/brain.json`, `brains/water-clarity/BRAIN_OPERATING_CONTRACT.md` | `brains/water-clarity/runtime/run.py` (logic `brains/water-clarity/runtime/clarity_brain.py`) | `brains/water-clarity/contracts/clarity-publication-v1.json`, `brains/water-clarity/contracts/INPUTS_V1.json` | `brains/water-clarity/tests/` (`brains/water-clarity/tests/test_clarity_kit_certification.py`) | Job `water-clarity-brain` via `brains/water-clarity/deploy/deploy-job.sh`, orchestrator-owned (26 h); **Pulse primary** by runner policy; published centrally (CENTRAL) |
| `lake-brain` | Lake | `brains/lake/` | `brains/lake/brain.json`, `brains/lake/BRAIN_OPERATING_CONTRACT.md`; integration doc `docs/brains/LAKE_BRAIN_INTEGRATION.md` | `LakeBrainJob`: `brains/lake/runtime/LakeBrainJob/main.swift` (`--dry-run DIR [--read-rtdb URL]` / `--rtdb URL`); library `brains/lake/runtime/LakeBrain/`; artifact builder `brains/lake/runtime/publish_artifact.py` | `brains/lake/contracts/lake-publication-v1.json`, `brains/lake/contracts/lake-state-v1.schema.json`, `brains/lake/contracts/reviewed-lake-bindings-v1.json`; Swift types `brains/lake/runtime/LakeBrain/LakeBrainContract.swift`; conformance `contracts/conformance/lake_keys.json`, `contracts/conformance/lake_rules_v2.json` | `brains/lake/tests/` (`brains/lake/tests/test_lake_kit_certification.py`; Swift `brains/lake/tests/swift/`); tooling tests in `jobs/lake-brain/` | `brain-jobs` image (`jobs/brain-image-build.sh`) + `brains/lake/deploy/deploy-job.sh`; job `lake-brain` started by the orchestrator (26 h); `lake-brain-ledger-daily` deprecated and PAUSED. Lake on Pulse is being prepared (not on `main`'s runner policy) |
| `water-temp` | Water Temperature | `brains/water-temperature/` | `brains/water-temperature/brain.json`, `brains/water-temperature/BRAIN_OPERATING_CONTRACT.md`; doc `docs/brains/WATER_TEMP_BRAIN.md` | `WaterTempBrainJob`: `brains/water-temperature/runtime/WaterTempBrainJob/main.swift` (`--dry-run DIR` / `--rtdb URL`, `--lake`, `--limit`); library `brains/water-temperature/runtime/WaterTemperatureBrain/` | `brains/water-temperature/contracts/water-temp-publication-v1.json`, `brains/water-temperature/contracts/water-temp-state-v1.schema.json`; Swift state type `Sources/SectorEngine/WaterTemp/WaterTemperatureState.swift` | `brains/water-temperature/tests/` (`brains/water-temperature/tests/test_water_temp_kit_certification.py`; Swift `brains/water-temperature/tests/swift/`) | `brain-jobs` image + `brains/water-temperature/deploy/deploy-job.sh`; job `water-temp-brain` started by the orchestrator (6 h) |
| `sector-intelligence` | Intelligence | `brains/sector-intelligence/` | `brains/sector-intelligence/brain.json`, `brains/sector-intelligence/BRAIN_OPERATING_CONTRACT.md`; docs `docs/brains/SECTOR_INTELLIGENCE_BRAIN_INTEGRATION.md`, `docs/brains/SECTOR_INTELLIGENCE_BRAIN_STATUS.md` | `brains/sector-intelligence/runtime/run.py` (module `brains/sector-intelligence/runtime/sector_intelligence_brain.py`, evaluation `brains/sector-intelligence/runtime/evaluation.py`, catalog `brains/sector-intelligence/runtime/catalog.json`) | `brains/sector-intelligence/contracts/sector-intelligence-publication-v1.json`, `brains/sector-intelligence/contracts/intelligence-evaluation-v1.schema.json` | `brains/sector-intelligence/tests/` (`brains/sector-intelligence/tests/test_intelligence_kit_certification.py`) | In-process in `brain-orchestrator` (`executionTarget.dir: brains/sector-intelligence/runtime`); staged under the legacy layout `jobs/sector-intelligence-brain/`; dependencies on all five live specialists are OPTIONAL |
| `depth` | Depth | `brains/depth/` | `brains/depth/brain.json`, `brains/depth/BRAIN_OPERATING_CONTRACT.md`, `brains/depth/BRAIN_SPEC.md` | `brains/depth/runtime/run.py` (package `brains/depth/runtime/depth_brain/`) | `brains/depth/contracts/depth-publication-v1.json` | `brains/depth/tests/` (`brains/depth/tests/test_depth_kit_certification.py`) | `executionTarget.kind: none`; SHADOW lane every 24 h through the orchestrator (`jobs/brain-orchestrator/shadow_run.py`); approved path abstains until an APPROVED release |
| `vegetation` | Vegetation | `brains/vegetation/` | `brains/vegetation/brain.json`, `brains/vegetation/BRAIN_OPERATING_CONTRACT.md` | `brains/vegetation/runtime/run.py` (package `brains/vegetation/runtime/vegetation_brain/`) | `brains/vegetation/contracts/vegetation-publication-v1.json` | `brains/vegetation/tests/` (`brains/vegetation/tests/test_vegetation_kit_certification.py`) | `executionTarget.kind: none`; SHADOW lane weekly; approved path abstains until an APPROVED release |

The SHADOW lane is enabled in the manifest, but the deployed orchestrator arguments omit `--run-shadow-lane` (owner choice, recorded in `docs/architecture/production/RUNNER_LEASE_AND_UPLOADER_V1.md`) [V repo; deployed args REPORTED].

### Primary modules per Brain [V]

- **Fish (`brains/fish/runtime/`):** knowledge and rules `biological_brain.py`, `rules.py`, `features.py`, `bands.py`; per-lake state `bio_state.py`, `run_state.py`; Intelligence-facing assessment `movement_outlook.py`, `biological_assessment.py`, `evaluated_view.py`; capability `capability.py`, `capability_eval.py`, `capability_run.py`; Publisher artifact `publish_artifact.py`; water domains `water_domain.py`, `water_domain_registry.py`; field patch `species_metadata_patch.py`; tools `tools/`.
- **Wind (`brains/wind/runtime/sector_wind/`):** ingest `ingest.py`, `grib.py`; interpolation `interp.py`; fetch and waves `bowfishing.py`; state and publishing `brain/state.py`, `brain/publish.py`, `brain/writer.py`; assessment V2 `assessment/`; validation `validate.py`; live loop `live.py`.
- **Water Clarity (`brains/water-clarity/runtime/`):** `clarity_brain.py`, `run.py`, `publish_artifact.py`, `catalog.json`, `knowledge-release.json`.
- **Lake (`brains/lake/runtime/LakeBrain/`):** feeds `LakeLevelFeeds.swift`, `LakeLevelFeedsCWMS.swift`, `LakeLevelFeedsFleet.swift`; classification `LakeLevelClassifier.swift`, `LakeLevelBaseline.swift`; bindings `LakeSourceBindings.swift`, `LakeSourceBindingsGenerated.swift`, `LakeGeneratedBindings.swift`, `LakeBindingTypes.swift`; runner `LakeBrainRunner.swift`, `LakeBrainOrchestration.swift`, `LakeBrainProfiles.swift`; archive and ledger `LakeBrainArchive.swift`, `LakePredictionLedger.swift`; presence `LakeSpeciesPresence.swift`. Coverage tool `brains/lake/tools/lake_coverage.py`.
- **Water Temp (`brains/water-temperature/runtime/WaterTemperatureBrain/`):** `WaterTemperatureBrain.swift`, `WaterTemperatureBrainRunner.swift`; state types stay in the shared library `Sources/SectorEngine/WaterTemp/`; source fetchers in `Sources/SectorEngine/Fetchers/`.
- **Intelligence (`brains/sector-intelligence/runtime/`):** `sector_intelligence_brain.py`, `evaluation.py`, `orchestration.py`, `brain_platform.py`, `publish_artifact.py`, `catalog.json`, `knowledge-release.json`.
- **Depth (`brains/depth/runtime/depth_brain/`):** `datum.py`, `zones.py`, `shift.py`, `rating.py`, `evidence.py`, `fleet.py`, `state.py`, `publish.py`, `publish_artifact.py`, `writer.py`.
- **Vegetation (`brains/vegetation/runtime/vegetation_brain/`):** `observer.py`, `metrics.py`, `agency.py`, `language.py`, `state.py`, `publish.py`, `publish_artifact.py`, `writer.py`.

### Research boundaries [V]

- Each package has `brains/<dir>/research/README.md` and a gaps file; private evidence lives outside the repository and its locations are not recorded here. Runtimes read explicit packaged knowledge releases (`brains/<dir>/runtime/knowledge-release.json`, verified on load where present).
- Per-lake species presence must not be committed to the public repository.

### Legacy / duplicate implementations [V]

- **Retired pointers (no code):** `jobs/biological-brain/`, `jobs/water-clarity-brain/`, `jobs/wind-hourly/`, `jobs/sector-intelligence-brain/`, `jobs/water-temp-brain/` (README), `jobs/clarity-current/` (deploy script only, live source is an off-`main` exception per `jobs/README.md`).
- **Not a stub:** `jobs/lake-brain/` keeps Lake's offline tooling (`jobs/lake-brain/bindings/`, `jobs/lake-brain/history/`, `jobs/lake-brain/ledger/`, `jobs/lake-brain/review/`, `jobs/lake-brain/validation/`).
- **Parallel domain logic in the customer Engine** (not Brains): species spawn table `Sources/SectorEngine/Engine/Config/SpeciesDatabase.swift`; wind and water-temperature bands `Sources/SectorEngine/Engine/ConditionsConfig.swift`; synthesis `Sources/SectorEngine/Engine/Aggregator/ConditionsAggregator.swift`, `Sources/SectorEngine/Engine/Aggregator/ConditionsGates.swift`; Clarity Stage 2–5 `Sources/SectorEngine/Clarity/`.

---

## C. Shared infrastructure map

| Component | Authoritative source (repo-relative) | Notes |
|---|---|---|
| **Brain registry (identity)** | `tools/architecture/stable_brain_ids.json`, `brains/*/brain.json`, `jobs/brain_platform/sector_brain_platform/control_manifest.json`, `jobs/brain_platform/sector_brain_platform/jobs.py`, `jobs/brain_platform/sector_brain_platform/ownership.py`, `brains/sector-intelligence/runtime/catalog.json`, `contracts/conformance/ownership.json`, `docs/brains/OWNERSHIP_MATRIX.md`; schemas `contracts/schemas/registry-brains.schema.json`, `contracts/schemas/brain.schema.json` | Still hand-synchronized; no generator (`platform/registries/brains/README.md`) |
| **Other registries** | Signals `platform/registries/signals/signals.json` (loaded by `jobs/brain_platform/sector_brain_platform/signals.py`); species water domains `platform/registries/species/species_water_domains.json`; lake directory generated by `scripts/generate-lake-directory.py` into `Sources/SectorEngine/Support/LakeDirectory.swift`, served at `GET /lakes` (source data under `docs/data/`); lake extents from the public Lake Registry index (`Sources/SectorEngine/API/LakeRegistryExtents.swift`; geometry builder `jobs/lake-geometry/`) | `platform/registries/lakes/` is README-only |
| **Brain Factory** | `docs/architecture/certification/audit-1/BRAIN_FACTORY_V1.md`, `docs/architecture/certification/audit-1/BRAIN_FACTORY_CHECKLIST_V1.md`; template `brains/_template/`; `docs/brains/platform/NEW_BRAIN_ONBOARDING_CHECKLIST.md`; `docs/architecture/repository-audit-v1/STANDARD_BRAIN_PACKAGE_V1.md` | Procedure + template |
| **Brain Certification Kit V1 (P01–P19)** | `tools/brain_certification/brain_cert_kit/` (`tools/brain_certification/brain_cert_kit/proofs.py`, `tools/brain_certification/brain_cert_kit/spec.py`); tests `tools/brain_certification/tests/`; doc `docs/architecture/certification/brain-cert-kit/BRAIN_CERT_KIT_V1.md` | **Adopted by all eight Brains** (`brains/<dir>/tests/test_*_kit_certification.py` + `*_cert_spec.py`) |
| **Architecture gates** | `tools/architecture/report.py`, `tools/architecture/tests/`, `tools/architecture/baseline/`, `tools/architecture/ownership_map.json` | CI (foundation-verification) |
| **Orchestrator / scheduling** | `jobs/brain-orchestrator/orchestrate.py`, `jobs/brain-orchestrator/control_plane.py`, `jobs/brain-orchestrator/preflight_lineage.py`, `jobs/brain-orchestrator/check_preproduction_schedules.py`, `jobs/brain-orchestrator/shadow_run.py`, `jobs/brain-orchestrator/clarity_pilot.py`, `jobs/brain-orchestrator/conditions_sources.py`; library `jobs/brain_platform/sector_brain_platform/` (`orchestration.py`, `orchestrator.py` legacy planner, `control.py`, `control_state.py`, `control_contract.py`, `operational_truth.py`, `freshness.py`, `brain_health.py`, `execution_health.py`, `execution_control.py`, `cycle_watchdog.py`, `consumption.py`, `gcp.py`, `jobs.py`, `shadow_lane.py`, `publication_stage.py`, `publication_requests.py`, `publication_coordination.py`); deploy `jobs/brain-orchestrator/deploy-job.sh` and `.github/workflows/deploy-orchestrator.yml`; docs `docs/brains/ORCHESTRATOR_DESIGN.md`, `docs/brains/platform/EXECUTION_MODEL.md`, `docs/brains/platform/BRAIN_OPERATIONAL_TRUTH_V1.md` | **The only scheduling authority** (PL-15). Scheduler ENABLED `50 * * * *` [V-prod 2026-11-12]. Execution control `/control/executionControlV1` is written only by the owner CLI (`execution_control.py`); the cycle watchdog can halt work (latch none on 2026-11-12) |
| **Runner leases and Pulse uploader** | `jobs/brain_platform/sector_brain_platform/runner_lease.py`, `jobs/brain_platform/sector_brain_platform/runner-policy.json`, `tools/runner/runner.py`; doc `docs/architecture/production/RUNNER_LEASE_AND_UPLOADER_V1.md`; Lake plan `docs/architecture/production/LAKE_CUTOVER_B1_B7_PULSE_V1.md` | Policy at HEAD: default primary cloud; `water-clarity` primary Pulse; failover off. Orchestrator gate `RUNNER_LEASES=on` (deploy switch) |
| **Scoring pipeline** | `jobs/brain-scores/score_brains.py` (+ `jobs/brain-scores/fish_capability_publication.py`, `jobs/brain-scores/refresh_wind_score.py`, `jobs/brain-scores/check_score_artifacts.py`); library `jobs/brain_platform/sector_brain_platform/scoring.py`, `jobs/brain_platform/sector_brain_platform/fish_capability.py`, `jobs/brain_platform/sector_brain_platform/wind_measurements.py`, `jobs/brain_platform/sector_brain_platform/wind_score_refresh.py`, `jobs/brain_platform/sector_brain_platform/score_explanation.py`, `jobs/brain_platform/sector_brain_platform/beta.py`, `jobs/brain_platform/sector_brain_platform/publication.py`; rubrics `docs/brains/scoring/` (`docs/brains/scoring/biological-state-score-v1.json`, `docs/brains/scoring/fish-biological-capability-v2.json`, `docs/brains/scoring/fish-capability-cohorts-v2.json`, `docs/brains/scoring/wind-specialist-capability-v2.json`, `docs/brains/scoring/lake-brain-score-v1.json`, `docs/brains/scoring/sector-intelligence-score-v1.json`, `docs/brains/scoring/engine-score-v1.json`, `docs/brains/scoring/beta-readiness-v1.json`, `docs/brains/scoring/frozen-scores.json`); spec `docs/brains/scoring/SCORING.md` | In-process from the orchestrator. Ops computes no scores |
| **Publisher** | Shadow `jobs/brain_platform/sector_brain_platform/publisher/` (`jobs/brain_platform/sector_brain_platform/publisher/registry.py`, `validate.py`, `canonical.py`, `plan.py`, `storage.py`); live `jobs/brain_platform/sector_brain_platform/publisher_live/` (`publisher.py`, `apply.py`, `locks.py`, `authorization.py`, `baseline.py`, `release_resolver.py`, `gcs_store.py`, `rtdb_client.py`, `security_model.py`, customer-copy builders `customer_copies.py` and siblings); recurring job `jobs/brain-publisher/publish_job.py` (deploy `jobs/brain-publisher/deploy-job.sh`); reviewed cutover `jobs/brain-orchestrator/publication-cutover.json`, order `jobs/brain_platform/sector_brain_platform/cutover_order.json`; per-Brain contracts `brains/<dir>/contracts/*-publication-v1.json`; docs `docs/architecture/publisher/`, `docs/architecture/production/PUBLISHER_LIVE_V1.md`, `docs/architecture/production/PRODUCTION_CUTOVER_PLANS_V1.md`, `docs/architecture/production/PRODUCTION_EXIT_GATE_V1.md` | **Water Clarity is CENTRAL** (owner pilot 2026-10-29); every other Brain DIRECT_WRITE. The Publisher writes only the producing Brain's validated paths and, when switched on, CUSTOMER-lane copies. `platform/publisher/README.md` is stale |
| **Feeder and archive jobs** | `jobs/lake-surface-dispatch/`, `jobs/lake-surface/`, `jobs/hydrology-hourly/`, `jobs/clarity-current/` (deploy script only), `jobs/water-temp-tva-archive/` | Registry and lineage table `jobs/README.md`. Live scheduler states NOT VERIFIED in this refresh |
| **Customer-lane copies** | Design `docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md`; builders in `publisher_live/`; Engine readers `Sources/SectorEngine/API/BrainCopyRead.swift`, `Sources/SectorEngine/Conditions/BrainOutputReaderConfig.swift`; endpoints `Sources/SectorEngine/API/LakesReadyAPI.swift` (with lake-wide wind `Sources/SectorEngine/API/LakeWind.swift`), `Sources/SectorEngine/API/LakeLevelOutputAPI.swift`; proposed rules `platform/security/rtdb.rules.customer-copies.PROPOSED.json` | The app never reads the Brain database; the Engine reads only CUSTOMER-lane copies, and only behind flags (`SECTOR_BRAIN_OUTPUT_READER`, none by default) |
| **Firebase / writer boundaries** | `jobs/brain_platform/sector_brain_platform/ownership.py`, `jobs/brain_platform/sector_brain_platform/rtdb.py`, `jobs/brain_platform/sector_brain_platform/data_ownership.json`; Swift `Sources/SectorEngine/Brain/BrainContract.swift` (`BrainOwnership`); target rules `platform/security/rtdb.rules.target.json` (not deployed); `platform/security/publisher_security_plan.json`, `platform/security/identity_split_plan.json`; docs `docs/architecture/certification/BRAIN_PATH_OWNERSHIP_V1.md`, `docs/architecture/certification/BRAIN_READ_WRITE_SECURITY_V1.md` | Deployed rules are owned by the iOS repository (orchestrator ADR 0002), not this one. IAM NOT VERIFIED here |
| **Sector Ops interfaces** | `docs/brains/OPS_CONTROL_PLANE_CONTRACT.md`, `docs/brains/platform/OPS_CONTROL_CONTRACT.md`, `docs/brains/platform/HEALTH_PLANE_OPS_CONSUMER_CONTRACT_V1.md`, `docs/brains/JOBS_CONTRACT.md`; read-only status `tools/deploy/ops_status.py` + `.github/workflows/ops-status.yml`; engineering status `docs/cortex/engineering-status/engineering-status.json` | Ops internals NOT VERIFIED here |
| **Sector Pulse** | Engine side: `tools/runner/runner.py` (tests `tools/runner/tests/`), `runner_lease.py`, Pulse collectors `jobs/water-clarity-h1-shadow/`, `jobs/lake-level-crosscheck/`; deterministic entry points `brains/wind/contracts/wind-validation-entrypoints-v1.json`, `brains/fish/runtime/capability_run.py` (see `docs/brains/scoring/FISH_BIOLOGICAL_CAPABILITY_V2.md` §8) | Pulse repository NOT VERIFIED (separate project) |
| **Intelligence integration** | Declared dependencies `control_manifest.json` (`sector-intelligence`), `jobs.py`; reads in `brains/sector-intelligence/runtime/evaluation.py`; assessment contracts `brains/fish/contracts/fish-biological-assessment-v1.json`, `brains/wind/contracts/wind-exposure-assessment-v1.json` | Assessment-contract consumption not re-verified in this refresh |
| **Providers** | `providers/PROVIDERS.json` (schema `contracts/schemas/providers.schema.json`) | Clients in `Sources/SectorEngine/Fetchers/` and the Brain runtimes |
| **Customer Engine** | `Sources/SectorEngine/` (`API/`, `Conditions/`, `Engine/`, `Fetchers/`, `Forecast/`, `Hydrology/`, `Support/`, `WaterTemp/`, `Clarity/`, `Brain/`), server `Sources/SectorEngineServer/main.swift`; deploy `deploy.sh` and `.github/workflows/deploy-engine.yml`; Remote Config tiles `Sources/SectorEngine/Conditions/TileFlags.swift`, `tools/deploy/conditions_tiles_flag.py`, `.github/workflows/set-conditions-tiles.yml`; contracts `Sources/SectorEngine/API/SectorEngineAPI.swift`, `verification/fixtures/conditions/response_contract.golden.json`, `contracts/phone/conditions-phone-contract-v1.json`, `contracts/phone/lakes-ready-v1.json`; lineage `docs/production/PRODUCTION_LINEAGE.md` | Always-on: `GET /health`, `GET /conditions`, `POST /conditions/batch`, `GET /lakes`, `GET /hydrology`. Flag-gated (default off): `GET /lakes/ready`, `GET /lake/level`, clarity review routes. Serving `sector-engine-00092-sem` from `fd1aa21d9b81` [V-prod 2026-11-12] |
| **CI** | `.github/workflows/foundation-verification.yml`, `.github/workflows/python-jobs-tests.yml`, `.github/workflows/swift-tests.yml`, `.github/workflows/image-build-verification.yml`; manual: `.github/workflows/deploy-engine.yml`, `.github/workflows/deploy-orchestrator.yml`, `.github/workflows/ops-status.yml`, `.github/workflows/set-conditions-tiles.yml` | — |

---

## D. Dependency and execution map

### D.1 Implemented execution routes [V repo; V-prod 2026-11-12 where marked]

```text
Cloud Scheduler: brain-orchestrator only (ENABLED 50 * * * * [V-prod 2026-11-12]); wind-hourly, lake-brain-ledger-daily deprecated and PAUSED
 └─ brain-orchestrator (Cloud Run job) ──► jobs/brain-orchestrator/orchestrate.py
       ├─ execution control /control/executionControlV1 (fail closed) + cycle watchdog
       ├─ plan per Brain (control_manifest.json: TIME / VERSION / FINGERPRINT)
       ├─ cloud-primary Brains: start Cloud Run jobs wind-hourly | lake-brain | water-temp-brain (when due)
       ├─ Pulse-primary Brains (runner-policy.json, RUNNER_LEASES=on): grant a lease, start nothing
       │     Sector Pulse (Mac mini) ──► runs the Brain locally ──► tools/runner/runner.py upload ──► artifacts/{brainId}/ (create-only) + execution record
       ├─ in-process: Fish (brains/fish/runtime), Intelligence (brains/sector-intelligence/runtime), score_brains.py --if-changed ──► /scores/*
       ├─ publication stage: requests for CENTRAL Brains ──► starts brain-publisher (PUBLICATION_HANDOFF=on)
       │     brain-publisher (jobs/brain-publisher/publish_job.py) ──► producing Brain's validated RTDB paths (+ CUSTOMER-lane copies when switched on)
       └─ control plane ──► /control/*, /jobs, /health
DIRECT_WRITE Brains (all except water-clarity) still write their own RTDB paths.
Pulse-only collectors (no cloud, no database): jobs/water-clarity-h1-shadow, jobs/lake-level-crosscheck.

Customer path:
 iOS / Android / Web ConditionsGateway (client code) ──► Cloud Run service sector-engine (Sources/SectorEngineServer)
   ──► Sources/SectorEngine (Open-Meteo, USGS, TVA, CWMS, SWPA, NWS fetchers; Remote Config conditions_tiles_v1) ──► /conditions, /lakes
   ──► behind flags: /lakes/ready, /lake/level ──► CUSTOMER-lane copies only (BrainOutputReader)
```

- **Images:** `brain-jobs` (root `Dockerfile`, `jobs/brain-image-build.sh`) carries `LakeBrainJob` and `WaterTempBrainJob`; `sector-engine` is built from the same `Dockerfile` by `.github/workflows/deploy-engine.yml` / `deploy.sh`; `brain-orchestrator` is staged by `jobs/brain-orchestrator/deploy-job.sh` (platform, Fish and Intelligence runtimes under legacy job names, scorer, rubrics, `brains/*/brain.json`, the cutover document); `brain-publisher` by `jobs/brain-publisher/deploy-job.sh`.

### D.2 Planned but NOT implemented (at HEAD)

- Lake on Pulse (runner policy `lake-brain: pulse`; Engine PR #168 open, not on `main`).
- CENTRAL publication for Brains beyond Water Clarity (order in `cutover_order.json`).
- CUSTOMER-lane copies switched on, and the Engine reader configured (`/lakes/ready` serving data).
- Generated Brain registry (`platform/registries/brains/`).
- `/conditions` itself reading Brain output (`engine/README.md` describes the intended integration mode); today only the flag-gated endpoints read CUSTOMER-lane copies.
- Approved (non-SHADOW) serving paths for Depth and Vegetation.

---

## E. Cortex navigation instructions (for a future Claude Code session)

1. **Resolve the ID first:** `tools/architecture/stable_brain_ids.json` → `control_manifest.json` `brains.<id>.executionTarget` → `jobs.py` `MANIFEST` → `brains/<dir>/brain.json` (authoritative for declared identity, contracts, providers, tests). Every registered Brain now has one.
2. **Directory ≠ ID:** `brains/fish/` is `biological-state`; `brains/lake/` is `lake-brain`; `brains/water-temperature/` is `water-temp`. Never rename IDs.
3. **Swift Brains:** Lake and Water Temp are SwiftPM targets inside their packages (`brains/<dir>/runtime/<Target>/`, tests in `brains/<dir>/tests/swift/`) that depend on the shared `SectorEngine` library. A change to `Sources/SectorEngine/` can affect both Brains.
4. **Who runs a Brain:** the Orchestrator decides; the runner policy decides cloud vs Pulse; the cutover document decides direct write vs central Publisher. Read all three before reasoning about a Brain's production behaviour.
5. **Customer boundary:** the app reads only the Engine API; the Engine reads only CUSTOMER-lane copies, behind flags. Never wire a customer path to `/brains/*` or `/lakes/*/states`.
6. **Tests:** per Brain `cd brains/<dir> && python -m pytest -q`; platform `jobs/brain_platform`, `jobs/brain-orchestrator`, `jobs/brain-scores`, `jobs/brain-publisher`; `tools/runner`; kit `python -m pytest -q tools/brain_certification`; `tools/architecture`; `verification`; Swift `swift build && swift test` (Lake `swift test --filter LakeBrainTests`). Wind needs `brains/wind/runtime/requirements.txt` (eccodes, shapely). CI definitions in `.github/workflows/` are authoritative.
7. **Production status without a console:** run `.github/workflows/ops-status.yml` (read-only). Deploy only through the manual workflows, under an owner approval.
8. **Not authoritative:** structure-only READMEs (`engine/`, `deploy/`, `platform/orchestrator/`, `platform/scoring/`, `platform/publisher/`, `platform/python/`, `platform/swift/`, `platform/lineage/`, `platform/ops/`, `platform/registries/brains/`, `platform/registries/lakes/`); retired pointers (§B); the stale migration text in `brains/README.md`; `.build/`; local sibling worktrees.

---

## F. Known structural observations (not a corrective audit)

1. **Resolved:** every registered Brain has a canonical package and Kit adoption (was obs.01).
2. **Still true:** Brain identity is spread across hand-maintained registries (was obs.02).
3. **Resolved:** Wind stale threshold agrees (1.5 h in both) (was obs.03).
4. **Changed:** the Publisher is active for Water Clarity (CENTRAL) through `brain-publisher`; others DIRECT_WRITE (was obs.04).
5. **Changed:** the customer Engine can read Brain output, but only CUSTOMER-lane copies behind flags that default off (was obs.05).
6. **Resolved:** Depth and Vegetation are on `main` (was obs.06).
7. **Changed:** the serving Engine revision is built from a `main` commit (`fd1aa21d9b81`) [V-prod 2026-11-12]; job image lineage not re-checked (was obs.07).
8. **Still true:** `platform/publisher/README.md` and `brains/README.md` carry stale text (was obs.08).
9. **Not re-verified:** score-type semantics (was obs.09).
10. **Still true:** the customer Engine duplicates Brain-domain logic (was obs.10).
11. **Changed:** the only scheduler is `brain-orchestrator`; Wind and Lake schedulers are deprecated PAUSED in the manifest (was obs.11).
12. **Changed:** Swift Brains are separate SwiftPM targets in their packages that depend on the shared library (was obs.12).
13. **Still true:** `docs/brains/scoring/` is load-bearing (was obs.13).
14. **Not re-verified:** the stale Wind score copy under `/brains/wind/scores` (was obs.14).
15. **New:** two runners can run a Brain (cloud, Pulse); the lease and grant ledger make the Orchestrator the single authority, with failover off.

---

## G. Navigation verification

- **Method:** see "Path verification" below. JSON reads of `stable_brain_ids.json`, `control_manifest.json`, `runner-policy.json`, `publication-cutover.json` and `brains/wind/brain.json`; header reads of every workflow; `git grep` for `lakes/ready`, `ConditionsGateway`, `publisher_live` imports.
- **Production (read-only):** `ops-status` workflow run 43267613577 (2026-11-12T17:16Z): five newest real `brain-orchestrator` executions succeeded (16:50Z newest); watchdog latch none; scheduler `brain-orchestrator` ENABLED `50 * * * *`; Engine serving `sector-engine-00092-sem` (100 %, commit label `fd1aa21d9b81`); GATE PASSED.
- **Test evidence (run locally at HEAD, Python 3, pytest; 2026-11-12):**

  | Suite | Result |
  |---|---|
  | `jobs/brain_platform` | 948 passed, 2 skipped |
  | `jobs/brain-orchestrator` | 256 passed |
  | `jobs/brain-scores` | 37 passed |
  | `jobs/brain-publisher` | 19 passed |
  | `tools/runner` | 10 passed |
  | `tools/brain_certification` | 32 passed |
  | `tools/architecture` | 187 passed |
  | `verification` | 48 passed, 5 skipped, 1 failed (`test_staged_image_verifies_its_packaged_knowledge_release`: `eccodes` not installed in this environment) |
  | Fish | 407 passed, 2 skipped |
  | Water Clarity | 148 passed |
  | Lake (Python) | 81 passed, 2 skipped |
  | Water Temp (Python) | 59 passed, 2 skipped |
  | Intelligence | 115 passed |
  | Depth | 280 passed, 9 skipped |
  | Vegetation | 174 passed |

  Wind (needs eccodes, shapely) and Swift (no toolchain here) were not run; CI runs them.

## Path verification

Every backtick-quoted, repository-relative path in this report (sections Changes and A–G) was extracted (brace lists expanded; templated forms with `<…>`, `*` or `{…}` counted separately) and checked with `git cat-file -e 939a0fa08023edc37b0de5ef165dd24225a1bddb:<path>`. Module names cited relative to a Brain directory were checked under that directory. Not counted as paths: the repository slug, branch names (`feat/…`, `origin/main`), the approval reference in the runner policy, RTDB and HTTP routes (leading `/`, or `lakes/ready` as a grep pattern), and `.build/` (local build output, absent by design).

| Result | Count |
|---|---|
| Resolved to an existing file or directory | **337** |
| Missing | **2** |
| Templated, not checkable literally | **12** (`brains/<dir>/…`, `brains/*/…`, `.github/workflows/*.yml`); each resolves for every package it names |

The missing entries are expected: they are the pre-move locations named in the drift output and the "Was" column (`jobs/lake-brain/deploy-job.sh`, `jobs/water-temp-brain/deploy-job.sh`). No other path is missing.

## Not checked

- Sector Pulse repository and its pipeline (separate project); only the Engine side of the hybrid flow is verified.
- Sector Ops, iOS, Android and Web repositories (including `ConditionsGateway`); only their Engine-side contracts.
- IAM bindings, deployed RTDB rules, Cloud Scheduler objects other than `brain-orchestrator`, Cloud Run job images and their commit labels, `brain-publisher` deployment state, and the CUSTOMER-lane copy switches.
- Score semantics (obs.09) and the stale Wind score copy (obs.14).
- Swift and Wind test suites.
- Private research workspaces (deliberately not mapped).
