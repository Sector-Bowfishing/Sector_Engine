# Sector Engine Navigation Refresh Report
Standards: Rehtac Cortex 3.1.3 @ 8ad5469 (clean), pack sector/engine
Snapshot compared: sector-engine@939a0fa-2026-11-12
Engine repository: Sector-Bowfishing/Sector_Engine · HEAD f1fd4a8aa221b0ec1df96d4a25bca61ee77abb5a · ref origin/main ("fix(intelligence): --emit refuses a missing parent folder up front … (#174)") · Date 2026-11-15
Drift command output: `cortex.py drift sector/engine --repo .` at HEAD `f1fd4a8aa221`: "22 files changed between snapshot and HEAD." CHANGED: `brain.wind` (`brains/wind/`, `brains/wind/runtime/sector_wind/`, `brains/wind/tests/`); `brain.sector-intelligence` (`brains/sector-intelligence/`, `brains/sector-intelligence/runtime/run.py`, `brains/sector-intelligence/tests/`); `platform.brain-platform-library` (`jobs/brain_platform/`); `platform.publisher-live` and `artifact.brain-orchestrator-image` (`jobs/brain-orchestrator/publication-cutover.json`); `platform.runner-leases` (`jobs/brain_platform/sector_brain_platform/runner-policy.json`, `docs/architecture/production/RUNNER_LEASE_AND_UPLOADER_V1.md`). "Brain inventory in `jobs/brain_platform/sector_brain_platform/control_manifest.json` matches the snapshot (8 Brains)." "6 item(s) need verification."

**Why one consolidated report.** Cortex holds exactly one source document per snapshot (`REFRESH.md`). This report supersedes `docs/cortex/navigation-refresh/2026-11-12-consolidated-navigation.md` as the import candidate: it records the changes since `939a0fa` (table below) **and** restates the whole navigation at HEAD in sections A–G (carried forward from the 2026-11-12 report and updated where HEAD differs), so a new snapshot can be grounded in this file alone. Section letters match the earlier reports.

**Evidence labels:**
- **[V]** verified by inspection of `f1fd4a8aa221` (git ls-tree / cat-file / show / diff, JSON reads, local test runs).
- **[V-prod 2026-11-15]** read-only production observation through the repository's `ops-status` workflow (run 43679109782, 2026-11-15T05:0xZ, read-only status account). Dated, not live status.
- **[REPORTED]** stated in an owner-approved Sector_Ops comment or a merged PR in another repository; not re-observed here.
- **NOT VERIFIED** not established.

No Engine, Cortex, Firebase or Git state was changed by this inspection, apart from committing this file on its branch. No secrets or private research locations are recorded. Every path is repository-relative.

## Changes (since `939a0fa`)

| # | Snapshot ID affected | Change type | Was (snapshot) | Now (HEAD) | Evidence | Label |
|---|---|---|---|---|---|---|
| 1 | `platform.runner-leases`, `brain.lake-brain`, `external.sector-pulse` | OWNERSHIP_CHANGED | Runner policy: only `water-clarity: pulse`; Lake on Pulse planned (Engine PR #168 open) | `jobs/brain_platform/sector_brain_platform/runner-policy.json` `primary` adds `lake-brain: pulse` with approval `owner-approval-2026-11-12/sector-ops-51-lake-on-pulse`; `failover.enabled` stays false. Design text updated in `docs/architecture/production/RUNNER_LEASE_AND_UPLOADER_V1.md` | `git diff 939a0fa f1fd4a8 -- jobs/brain_platform/sector_brain_platform/runner-policy.json` (merge `a59f1fe`, PR #168) | VERIFIED_IMPLEMENTATION |
| 2 | `platform.publisher-live`, `artifact.brain-orchestrator-image`, obs.04 | OWNERSHIP_CHANGED | Only `water-clarity` CENTRAL; every other Brain DIRECT_WRITE | `jobs/brain-orchestrator/publication-cutover.json` adds `lake-brain: CENTRAL` (`approvalRef` as row 1, `orderReviewRef owner-approval-2026-11-02/sector-ops-50#L-2`). Lake's cloud direct writer (the `lake-brain` Cloud Run job) stays paused and is retired at B6 | file read at HEAD | VERIFIED_IMPLEMENTATION |
| 3 | cycle watchdog (`platform.orchestrator`) | OWNERSHIP_CHANGED | Watchdog scope: `water-clarity` (holder pulse, 2 lakes) | `jobs/brain_platform/sector_brain_platform/watchdog-policy.json` adds `lake-brain` (holder `pulse`; lakes `Guntersville_AL`, `Wheeler_AL`, `Wilson_AL`, `Pickwick_Lake_TN`, `Lake_Hartwell_SC`) | file read at HEAD | VERIFIED_IMPLEMENTATION |
| 4 | `platform.runner-leases` | ROUTE_ADDED | Staged fragment `tools/ops/hybrid-stage/lake-brain.json` (STAGED, 7 blockers) | Fragment APPLIED (`blockers: []`, `resolvedBlockers` recorded); `tools/ops/hybrid_stage.py` gains `is_live` / `live_problems`, so `check` verifies the live policies against an applied fragment | `git diff 939a0fa f1fd4a8 -- tools/ops/hybrid_stage.py tools/ops/hybrid-stage/lake-brain.json` | VERIFIED_IMPLEMENTATION |
| 5 | `brain.lake-brain` | ROUTE_ADDED | Lake ran as the cloud `lake-brain` job, DIRECT_WRITE | Live on Pulse: lease granted to Pulse (`GRANTED … pulse:lake-brain-20261112T2150Z`), first CENTRAL publish 2026-11-13T15:27Z (publishId `f42933d1-c300-4906-b75b-91340f84fcbd`, 75/75 paths read back) | owner's Cloud Shell log, Sector_Ops #51 (2026-11-13) | PRODUCTION_OBSERVATION 2026-11-13 [REPORTED] |
| 6 | `brain.wind` | ROUTE_ADDED (off) | Wind archives NBM grids for the home lakes only | `brains/wind/runtime/sector_wind/points.py` + `brains/wind/runtime/points.json` (142 W1 lakes): nearest-cell NBM point forecasts, called from `brains/wind/runtime/sector_wind/live.py` `run_hourly` only when `WIND_NBM_POINTS=1` (unset everywhere); writes `nbm-points/<cycle>.json.gz` to the Wind store; nothing publishes or reads it; `points.json` is not in Wind's knowledge release. Tests `brains/wind/tests/test_nbm_points.py` | PR #90 (`d216e3c`); file reads | VERIFIED_IMPLEMENTATION |
| 7 | `brain.sector-intelligence` | ROUTE_ADDED (off) | `run.py --artifact` seals an artifact; no runner hand-off | `brains/sector-intelligence/runtime/run.py` adds `--emit FILE` (create-only local copy of the stored artifact bytes, sha256-checked) and `--emit-decision FILE` (PUBLISH/SKIP verdict) for a Pulse hand-off; refused before any read when `--artifact` is missing, the path is remote, exists, or its parent folder is missing. Tests `brains/sector-intelligence/tests/test_artifact_mode.py`. Intelligence is not in the runner policy or the cutover document, so nothing runs it on Pulse | PRs #172 (`88d2fc2`), #174 (`f1fd4a8`) | VERIFIED_IMPLEMENTATION |
| 8 | `external.sector-pulse` | ROUTE_ADDED (off) | — | Sector-Pulse catalogs a `sector-intelligence-central` job (default off, lease-only, `--artifact --emit --emit-decision`) next to `lake-central` and `water-clarity-central` | Sector-Pulse PR #6 (merged `59f18b4`) | NOT_VERIFIED (other repository) [REPORTED] |
| 9 | `service.customer-engine`, obs.07 | CORRECTION | Serving `sector-engine-00092-sem` (commit `fd1aa21d9b81`) | Serving `sector-engine-00095-rax`, 100 % traffic, commit label `d216e3cf4bb6`, an ancestor of HEAD; `SECTOR_LAKES_READY_OUTPUT` still off | ops-status run 43679109782; `git merge-base --is-ancestor d216e3cf f1fd4a8` | PRODUCTION_OBSERVATION 2026-11-15 |
| 10 | `platform.orchestrator` | ROUTE_ADDED | — (no change in routes) | Scheduler `brain-orchestrator` ENABLED `50 * * * *`; five newest real cycles succeeded (04:50Z newest); watchdog latch none | ops-status run 43679109782 | PRODUCTION_OBSERVATION 2026-11-15 |

---

## A. Repository overview

| Item | Value |
|---|---|
| Repository | `Sector-Bowfishing/Sector_Engine` (GitHub) [V] |
| Default branch | `main` |
| Inspected commit | `f1fd4a8aa221b0ec1df96d4a25bca61ee77abb5a` (`origin/main`, PR #174) [V] |
| Inspection date | 2026-11-15 |
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
| `wind` | Wind | `brains/wind/` | `brains/wind/brain.json`, `brains/wind/BRAIN_OPERATING_CONTRACT.md` | `brains/wind/runtime/main.py` (package `brains/wind/runtime/sector_wind/`) | `brains/wind/contracts/wind-publication-v1.json`, `brains/wind/contracts/wind-exposure-assessment-v1.json`, `brains/wind/contracts/wind-validation-entrypoints-v1.json` | `brains/wind/tests/` (`brains/wind/tests/test_wind_kit_certification.py`), `brains/wind/research/tools/tests/` | Cloud Run job `wind-hourly` via `brains/wind/deploy/deploy-job.sh`, **started by the orchestrator** when due (1.5 h); its own scheduler deprecated and PAUSED; read service `brains/wind/deploy/read_service/`; NBM point forecasts `brains/wind/runtime/sector_wind/points.py` off unless `WIND_NBM_POINTS=1` |
| `water-clarity` | Water Clarity | `brains/water-clarity/` | `brains/water-clarity/brain.json`, `brains/water-clarity/BRAIN_OPERATING_CONTRACT.md` | `brains/water-clarity/runtime/run.py` (logic `brains/water-clarity/runtime/clarity_brain.py`) | `brains/water-clarity/contracts/clarity-publication-v1.json`, `brains/water-clarity/contracts/INPUTS_V1.json` | `brains/water-clarity/tests/` (`brains/water-clarity/tests/test_clarity_kit_certification.py`) | Job `water-clarity-brain` via `brains/water-clarity/deploy/deploy-job.sh`, orchestrator-owned (26 h); **Pulse primary** by runner policy; published centrally (CENTRAL) |
| `lake-brain` | Lake | `brains/lake/` | `brains/lake/brain.json`, `brains/lake/BRAIN_OPERATING_CONTRACT.md`; integration doc `docs/brains/LAKE_BRAIN_INTEGRATION.md` | `LakeBrainJob`: `brains/lake/runtime/LakeBrainJob/main.swift` (`--dry-run DIR [--read-rtdb URL]` / `--rtdb URL`); library `brains/lake/runtime/LakeBrain/`; artifact builder `brains/lake/runtime/publish_artifact.py` | `brains/lake/contracts/lake-publication-v1.json`, `brains/lake/contracts/lake-state-v1.schema.json`, `brains/lake/contracts/reviewed-lake-bindings-v1.json`; Swift types `brains/lake/runtime/LakeBrain/LakeBrainContract.swift`; conformance `contracts/conformance/lake_keys.json`, `contracts/conformance/lake_rules_v2.json` | `brains/lake/tests/` (`brains/lake/tests/test_lake_kit_certification.py`; Swift `brains/lake/tests/swift/`); tooling tests in `jobs/lake-brain/` | `brain-jobs` image (`jobs/brain-image-build.sh`) + `brains/lake/deploy/deploy-job.sh`; job `lake-brain` (cloud direct writer) paused, retired at B6; `lake-brain-ledger-daily` deprecated and PAUSED. **Pulse primary** by runner policy (Pulse job `lake-central`, 26 h cooldown); published centrally (CENTRAL) since 2026-11-13 |
| `water-temp` | Water Temperature | `brains/water-temperature/` | `brains/water-temperature/brain.json`, `brains/water-temperature/BRAIN_OPERATING_CONTRACT.md`; doc `docs/brains/WATER_TEMP_BRAIN.md` | `WaterTempBrainJob`: `brains/water-temperature/runtime/WaterTempBrainJob/main.swift` (`--dry-run DIR` / `--rtdb URL`, `--lake`, `--limit`); library `brains/water-temperature/runtime/WaterTemperatureBrain/` | `brains/water-temperature/contracts/water-temp-publication-v1.json`, `brains/water-temperature/contracts/water-temp-state-v1.schema.json`; Swift state type `Sources/SectorEngine/WaterTemp/WaterTemperatureState.swift` | `brains/water-temperature/tests/` (`brains/water-temperature/tests/test_water_temp_kit_certification.py`; Swift `brains/water-temperature/tests/swift/`) | `brain-jobs` image + `brains/water-temperature/deploy/deploy-job.sh`; job `water-temp-brain` started by the orchestrator (6 h) |
| `sector-intelligence` | Intelligence | `brains/sector-intelligence/` | `brains/sector-intelligence/brain.json`, `brains/sector-intelligence/BRAIN_OPERATING_CONTRACT.md`; docs `docs/brains/SECTOR_INTELLIGENCE_BRAIN_INTEGRATION.md`, `docs/brains/SECTOR_INTELLIGENCE_BRAIN_STATUS.md` | `brains/sector-intelligence/runtime/run.py` (module `brains/sector-intelligence/runtime/sector_intelligence_brain.py`, evaluation `brains/sector-intelligence/runtime/evaluation.py`, catalog `brains/sector-intelligence/runtime/catalog.json`) | `brains/sector-intelligence/contracts/sector-intelligence-publication-v1.json`, `brains/sector-intelligence/contracts/intelligence-evaluation-v1.schema.json` | `brains/sector-intelligence/tests/` (`brains/sector-intelligence/tests/test_intelligence_kit_certification.py`) | In-process in `brain-orchestrator` (`executionTarget.dir: brains/sector-intelligence/runtime`); staged under the legacy layout `jobs/sector-intelligence-brain/`; dependencies on all five live specialists are OPTIONAL; `run.py --artifact --emit` / `--emit-decision` exist for a future Pulse hand-off (off) |
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
| **Runner leases and Pulse uploader** | `jobs/brain_platform/sector_brain_platform/runner_lease.py`, `jobs/brain_platform/sector_brain_platform/runner-policy.json`, `tools/runner/runner.py`; doc `docs/architecture/production/RUNNER_LEASE_AND_UPLOADER_V1.md`; Lake plan `docs/architecture/production/LAKE_CUTOVER_B1_B7_PULSE_V1.md` | Policy at HEAD: default primary cloud; `water-clarity` and `lake-brain` primary Pulse; failover off. Orchestrator gate `RUNNER_LEASES=on` (deploy switch) |
| **Scoring pipeline** | `jobs/brain-scores/score_brains.py` (+ `jobs/brain-scores/fish_capability_publication.py`, `jobs/brain-scores/refresh_wind_score.py`, `jobs/brain-scores/check_score_artifacts.py`); library `jobs/brain_platform/sector_brain_platform/scoring.py`, `jobs/brain_platform/sector_brain_platform/fish_capability.py`, `jobs/brain_platform/sector_brain_platform/wind_measurements.py`, `jobs/brain_platform/sector_brain_platform/wind_score_refresh.py`, `jobs/brain_platform/sector_brain_platform/score_explanation.py`, `jobs/brain_platform/sector_brain_platform/beta.py`, `jobs/brain_platform/sector_brain_platform/publication.py`; rubrics `docs/brains/scoring/` (`docs/brains/scoring/biological-state-score-v1.json`, `docs/brains/scoring/fish-biological-capability-v2.json`, `docs/brains/scoring/fish-capability-cohorts-v2.json`, `docs/brains/scoring/wind-specialist-capability-v2.json`, `docs/brains/scoring/lake-brain-score-v1.json`, `docs/brains/scoring/sector-intelligence-score-v1.json`, `docs/brains/scoring/engine-score-v1.json`, `docs/brains/scoring/beta-readiness-v1.json`, `docs/brains/scoring/frozen-scores.json`); spec `docs/brains/scoring/SCORING.md` | In-process from the orchestrator. Ops computes no scores |
| **Publisher** | Shadow `jobs/brain_platform/sector_brain_platform/publisher/` (`jobs/brain_platform/sector_brain_platform/publisher/registry.py`, `validate.py`, `canonical.py`, `plan.py`, `storage.py`); live `jobs/brain_platform/sector_brain_platform/publisher_live/` (`publisher.py`, `apply.py`, `locks.py`, `authorization.py`, `baseline.py`, `release_resolver.py`, `gcs_store.py`, `rtdb_client.py`, `security_model.py`, customer-copy builders `customer_copies.py` and siblings); recurring job `jobs/brain-publisher/publish_job.py` (deploy `jobs/brain-publisher/deploy-job.sh`); reviewed cutover `jobs/brain-orchestrator/publication-cutover.json`, order `jobs/brain_platform/sector_brain_platform/cutover_order.json`; per-Brain contracts `brains/<dir>/contracts/*-publication-v1.json`; docs `docs/architecture/publisher/`, `docs/architecture/production/PUBLISHER_LIVE_V1.md`, `docs/architecture/production/PRODUCTION_CUTOVER_PLANS_V1.md`, `docs/architecture/production/PRODUCTION_EXIT_GATE_V1.md` | **Water Clarity and Lake are CENTRAL** (owner pilot 2026-10-29; Lake 2026-11-12); every other Brain DIRECT_WRITE. The Publisher writes only the producing Brain's validated paths and, when switched on, CUSTOMER-lane copies. `platform/publisher/README.md` is stale |
| **Feeder and archive jobs** | `jobs/lake-surface-dispatch/`, `jobs/lake-surface/`, `jobs/hydrology-hourly/`, `jobs/clarity-current/` (deploy script only), `jobs/water-temp-tva-archive/` | Registry and lineage table `jobs/README.md`. Live scheduler states NOT VERIFIED in this refresh |
| **Customer-lane copies** | Design `docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md`; builders in `publisher_live/`; Engine readers `Sources/SectorEngine/API/BrainCopyRead.swift`, `Sources/SectorEngine/Conditions/BrainOutputReaderConfig.swift`; endpoints `Sources/SectorEngine/API/LakesReadyAPI.swift` (with lake-wide wind `Sources/SectorEngine/API/LakeWind.swift`), `Sources/SectorEngine/API/LakeLevelOutputAPI.swift`; proposed rules `platform/security/rtdb.rules.customer-copies.PROPOSED.json` | The app never reads the Brain database; the Engine reads only CUSTOMER-lane copies, and only behind flags (`SECTOR_BRAIN_OUTPUT_READER`, none by default) |
| **Firebase / writer boundaries** | `jobs/brain_platform/sector_brain_platform/ownership.py`, `jobs/brain_platform/sector_brain_platform/rtdb.py`, `jobs/brain_platform/sector_brain_platform/data_ownership.json`; Swift `Sources/SectorEngine/Brain/BrainContract.swift` (`BrainOwnership`); target rules `platform/security/rtdb.rules.target.json` (not deployed); `platform/security/publisher_security_plan.json`, `platform/security/identity_split_plan.json`; docs `docs/architecture/certification/BRAIN_PATH_OWNERSHIP_V1.md`, `docs/architecture/certification/BRAIN_READ_WRITE_SECURITY_V1.md` | Deployed rules are owned by the iOS repository (orchestrator ADR 0002), not this one. IAM NOT VERIFIED here |
| **Sector Ops interfaces** | `docs/brains/OPS_CONTROL_PLANE_CONTRACT.md`, `docs/brains/platform/OPS_CONTROL_CONTRACT.md`, `docs/brains/platform/HEALTH_PLANE_OPS_CONSUMER_CONTRACT_V1.md`, `docs/brains/JOBS_CONTRACT.md`; read-only status `tools/deploy/ops_status.py` + `.github/workflows/ops-status.yml`; engineering status `docs/cortex/engineering-status/engineering-status.json` | Ops internals NOT VERIFIED here |
| **Sector Pulse** | Engine side: `tools/runner/runner.py` (tests `tools/runner/tests/`), `runner_lease.py`, Pulse collectors `jobs/water-clarity-h1-shadow/`, `jobs/lake-level-crosscheck/`; deterministic entry points `brains/wind/contracts/wind-validation-entrypoints-v1.json`, `brains/fish/runtime/capability_run.py` (see `docs/brains/scoring/FISH_BIOLOGICAL_CAPABILITY_V2.md` §8) | Pulse repository NOT VERIFIED (separate project) |
| **Intelligence integration** | Declared dependencies `control_manifest.json` (`sector-intelligence`), `jobs.py`; reads in `brains/sector-intelligence/runtime/evaluation.py`; assessment contracts `brains/fish/contracts/fish-biological-assessment-v1.json`, `brains/wind/contracts/wind-exposure-assessment-v1.json` | Assessment-contract consumption not re-verified in this refresh |
| **Providers** | `providers/PROVIDERS.json` (schema `contracts/schemas/providers.schema.json`) | Clients in `Sources/SectorEngine/Fetchers/` and the Brain runtimes |
| **Customer Engine** | `Sources/SectorEngine/` (`API/`, `Conditions/`, `Engine/`, `Fetchers/`, `Forecast/`, `Hydrology/`, `Support/`, `WaterTemp/`, `Clarity/`, `Brain/`), server `Sources/SectorEngineServer/main.swift`; deploy `deploy.sh` and `.github/workflows/deploy-engine.yml`; Remote Config tiles `Sources/SectorEngine/Conditions/TileFlags.swift`, `tools/deploy/conditions_tiles_flag.py`, `.github/workflows/set-conditions-tiles.yml`; contracts `Sources/SectorEngine/API/SectorEngineAPI.swift`, `verification/fixtures/conditions/response_contract.golden.json`, `contracts/phone/conditions-phone-contract-v1.json`, `contracts/phone/lakes-ready-v1.json`; lineage `docs/production/PRODUCTION_LINEAGE.md` | Always-on: `GET /health`, `GET /conditions`, `POST /conditions/batch`, `GET /lakes`, `GET /hydrology`. Flag-gated (default off): `GET /lakes/ready`, `GET /lake/level`, clarity review routes. Serving `sector-engine-00095-rax` from `d216e3cf4bb6` [V-prod 2026-11-15] |
| **CI** | `.github/workflows/foundation-verification.yml`, `.github/workflows/python-jobs-tests.yml`, `.github/workflows/swift-tests.yml`, `.github/workflows/image-build-verification.yml`; manual: `.github/workflows/deploy-engine.yml`, `.github/workflows/deploy-orchestrator.yml`, `.github/workflows/ops-status.yml`, `.github/workflows/set-conditions-tiles.yml` | — |

---

## D. Dependency and execution map

### D.1 Implemented execution routes [V repo; V-prod 2026-11-12 where marked]

```text
Cloud Scheduler: brain-orchestrator only (ENABLED 50 * * * * [V-prod 2026-11-15]); wind-hourly, lake-brain-ledger-daily deprecated and PAUSED
 └─ brain-orchestrator (Cloud Run job) ──► jobs/brain-orchestrator/orchestrate.py
       ├─ execution control /control/executionControlV1 (fail closed) + cycle watchdog
       ├─ plan per Brain (control_manifest.json: TIME / VERSION / FINGERPRINT)
       ├─ cloud-primary Brains: start Cloud Run jobs wind-hourly | water-temp-brain (when due)
       ├─ Pulse-primary Brains water-clarity, lake-brain (runner-policy.json, RUNNER_LEASES=on): grant a lease, start nothing
       │     Sector Pulse (Mac mini) ──► runs the Brain locally ──► tools/runner/runner.py upload ──► artifacts/{brainId}/ (create-only) + execution record
       ├─ in-process: Fish (brains/fish/runtime), Intelligence (brains/sector-intelligence/runtime), score_brains.py --if-changed ──► /scores/*
       ├─ publication stage: requests for CENTRAL Brains ──► starts brain-publisher (PUBLICATION_HANDOFF=on)
       │     brain-publisher (jobs/brain-publisher/publish_job.py) ──► producing Brain's validated RTDB paths (+ CUSTOMER-lane copies when switched on)
       └─ control plane ──► /control/*, /jobs, /health
CENTRAL Brains: water-clarity, lake-brain (publication-cutover.json). DIRECT_WRITE Brains (all others) still write their own RTDB paths.
Pulse-only collectors (no cloud, no database): jobs/water-clarity-h1-shadow, jobs/lake-level-crosscheck.

Customer path:
 iOS / Android / Web ConditionsGateway (client code) ──► Cloud Run service sector-engine (Sources/SectorEngineServer)
   ──► Sources/SectorEngine (Open-Meteo, USGS, TVA, CWMS, SWPA, NWS fetchers; Remote Config conditions_tiles_v1) ──► /conditions, /lakes
   ──► behind flags: /lakes/ready, /lake/level ──► CUSTOMER-lane copies only (BrainOutputReader)
```

- **Pulse-side jobs at HEAD [V]:** the SHADOW lane `jobs/water-clarity-h1-shadow/h1_shadow.py` (`jobs/water-clarity-h1-shadow/README.md`) writes a local file only; the 30-day read-only collector `jobs/lake-level-crosscheck/crosscheck.py` (`jobs/lake-level-crosscheck/README.md`) compares Lake Barkley with an independent USACE gauge and appends local JSON lines only.
- **Images:** `brain-jobs` (root `Dockerfile`, `jobs/brain-image-build.sh`) carries `LakeBrainJob` and `WaterTempBrainJob`; `sector-engine` is built from the same `Dockerfile` by `.github/workflows/deploy-engine.yml` / `deploy.sh`; `brain-orchestrator` is staged by `jobs/brain-orchestrator/deploy-job.sh` (platform, Fish and Intelligence runtimes under legacy job names, scorer, rubrics, `brains/*/brain.json`, the cutover document); `brain-publisher` by `jobs/brain-publisher/deploy-job.sh`.

### D.2 Planned but NOT implemented (at HEAD)

- Retiring Lake's cloud direct writer and marking its cutover complete (B6).
- CENTRAL publication for Brains beyond Water Clarity and Lake (order in `cutover_order.json`); Intelligence on Pulse (hand-off flags exist, not in the runner policy or the cutover document).
- Wind NBM point forecasts switched on (`WIND_NBM_POINTS`), and the Wind runtime reading NBM probability fields.
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
4. **Changed:** the Publisher is active for Water Clarity and Lake (CENTRAL) through `brain-publisher`; others DIRECT_WRITE (was obs.04).
5. **Changed:** the customer Engine can read Brain output, but only CUSTOMER-lane copies behind flags that default off (was obs.05).
6. **Resolved:** Depth and Vegetation are on `main` (was obs.06).
7. **Changed:** the serving Engine revision is built from a `main` commit (`d216e3cf4bb6`) [V-prod 2026-11-15]; job image lineage not re-checked (was obs.07).
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
- **Production (read-only):** `ops-status` workflow run 43679109782 (2026-11-15): five newest real `brain-orchestrator` executions succeeded (04:50Z newest); watchdog latch none; scheduler `brain-orchestrator` ENABLED `50 * * * *`; Engine serving `sector-engine-00095-rax` (100 %, commit label `d216e3cf4bb6`); GATE PASSED.
- **Test evidence.** Re-run at `f1fd4a8aa221` on 2026-11-15 for the suites touched since `939a0fa`: `brains/sector-intelligence` 122 passed; `jobs/brain_platform` 948 passed, 2 skipped; `jobs/brain-orchestrator` 261 passed; `jobs/brain-publisher` 19 passed; `tools/runner` 10 passed; `tools/architecture` 187 passed; `brains/wind` 265 passed, 6 skipped (eccodes present). The table below is the 2026-11-12 run at `939a0fa` for the unchanged suites:

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

  Swift (no toolchain here) was not run; CI runs it.

## Path verification

Every backtick-quoted, repository-relative path in this report (sections Changes and A–G) was extracted and checked with `git cat-file -e f1fd4a8aa221b0ec1df96d4a25bca61ee77abb5a:<path>`. Names cited relative to a parent (the `Sources/SectorEngine/` sub-folders, `publisher_live/`, Wind's `brain/*.py` and `assessment/` under `brains/wind/runtime/sector_wind/`) were checked under that parent. Not counted as paths: the repository slug, branch names, approval references, RTDB and HTTP routes (leading `/`, or `lakes/ready` as a grep pattern), and `.build/`.

| Result | Count |
|---|---|
| Resolved to an existing file or directory | **342** |
| Missing | **0** |
| Templated, not checkable literally | **12** (`brains/<dir>/…`, `brains/*/…`, `.github/workflows/*.yml`); each resolves for every package it names |

The two pre-move locations listed as missing in the 2026-11-12 report appeared only in its Changes table, which this report does not carry forward.

## Not checked

- Sector Pulse repository and its pipeline (separate project), including the `sector-intelligence-central` catalog entry (row 8); only the Engine side of the hybrid flow is verified. Lake's live Pulse runs and first publish (row 5) are from the owner's log, not re-observed.
- Sector Ops, iOS, Android and Web repositories (including `ConditionsGateway`); only their Engine-side contracts.
- IAM bindings, deployed RTDB rules, Cloud Scheduler objects other than `brain-orchestrator`, Cloud Run job images and their commit labels, `brain-publisher` deployment state, and the CUSTOMER-lane copy switches.
- Score semantics (obs.09) and the stale Wind score copy (obs.14).
- The Swift test suite.
- Private research workspaces (deliberately not mapped).
