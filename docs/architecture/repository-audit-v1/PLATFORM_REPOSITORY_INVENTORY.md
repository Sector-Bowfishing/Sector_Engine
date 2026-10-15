# Platform Repository Inventory

Base `fab115e9`. Brain Platform = everything a specialist Brain must not re-implement. Records: Brain Platform (umbrella), Orchestrator, Publisher, Scoring Platform, contracts/schemas, lineage/registry, plus the shared-library delivery problem.

## 1. Component table

| Component | Current location | Lines / files | Language | Proposed canonical location | Status |
|---|---|---|---|---|---|
| Platform library (envelope, keys, freshness, health, jobs manifest, ownership, orchestration plan, control, model v1, rtdb, gcp, beta, scoring, fingerprint, enums, failure, field validation, timeutil, activity, dependencies) | `jobs/brain_platform/sector_brain_platform/` | 25 modules, 4.7 k | Python | `platform/python/sector_brain_platform/` (installable: `pyproject.toml`) | Canonical Python implementation |
| Platform library (Swift) | `Sources/SectorEngine/Brain/{BrainPlatform,BrainContract,BrainRTDBStore}.swift` | 1.5 k incl. Water Temp | Swift | `platform/swift/` target `SectorBrainPlatform` | Second implementation of the same contract; parity via fixtures |
| Conformance fixtures | `docs/brains/conformance/*.json` (11) | | JSON | `contracts/conformance/` | **Test inputs living in `docs/`**; CI path trigger |
| Platform contract docs | `docs/brains/BRAIN_PLATFORM_CONTRACT.md`, `docs/brains/platform/*` (models: claim, execution, freshness, lifecycle, validation, scoring semantics, field validation…), `JOBS_CONTRACT`, `OPS_CONTROL_PLANE_CONTRACT`, `ORCHESTRATOR_DESIGN` | ~25 docs | MD | `docs/platform/` | Mixed with stale items |
| Orchestrator executor | `jobs/brain-orchestrator/{orchestrate,control_plane,preflight_lineage,check_preproduction_schedules}.py`, Dockerfile, `deploy-job.sh` (stages `../brain_platform`, `../biological-brain`, `../sector-intelligence-brain`, `../brain-scores`, `docs/brains/scoring/frozen-scores.json` into the image) | 1.0 k | Python (stdlib) | `platform/orchestrator/` | Canonical; staging couples it to Brain dirs and `docs/` |
| Publisher | **not in base**: `feat/publisher-v1-shadow` (HEAD `d090c428`): `sector_brain_platform/publisher/{api,canonical,handoff,model,paths,plan,publisher,refs,registry,sinks,storage,validate}.py` (+6 test files, 3 docs); same payload visible in `cert/wind-architecture-v1` | ~2.5 k + tests | Python | `platform/python/sector_brain_platform/publisher/` → serviced from `platform/publisher/` | Shadow only; approved by CERT-1/2 |
| Scoring platform | `sector_brain_platform/{scoring,beta}.py`, `jobs/brain-scores/{score_brains,check_score_artifacts}.py` (+ 4 loose tests), `docs/brains/scoring/` (SCORING.md, SCORE_ARTIFACT_DURABILITY.md, `engine-score-v1.json`, `beta-readiness-v1.json`, 3 Brain rubrics, `score-artifact-sources.json`, `frozen-scores.json`) | | Python/JSON | code → `platform/scoring/`; engine+beta rubrics → `platform/scoring/rubrics/`; Brain rubrics → `brains/<id>/scoring/` | Rubrics in `docs/` are runtime inputs |
| Brain registry / jobs manifest | `sector_brain_platform/jobs.py` (job classification), `ownership.py` (source/path→brain map), `control_manifest.json`, `conformance/ownership.json`, `OWNERSHIP_MATRIX.md`, `sector-intelligence-brain/catalog.json` (`DEPENDENCY_ORDER`), `jobs/README.md` table | 6 representations | mixed | single `brain.json` per Brain compiled into `platform/registry/` (generated) | Hand-synchronized |
| Path authorization | `ownership.py`; `docs/architecture/data/RTDB_PATH_OWNERSHIP_MATRIX.{md,json}`; certification `BRAIN_PATH_OWNERSHIP_V1`; Publisher `publisher/paths.py` (branch) | 3–4 | mixed | `platform/contracts/path-ownership.json` generated from `brain.json` + Publisher `paths.py` | Rules approved, enforcement not built |
| Lineage | `preflight_lineage.py`, `docs/production/PRODUCTION_LINEAGE.md`, image label `commit`, `BRAIN_IDENTITY_AND_LINEAGE_V1` | | | `platform/lineage/` | Partly implemented |
| Execution/request IDs | `event_id`, fingerprints in `sector_brain_platform`; identity model in certification docs | | | `platform/python/.../identity` | Target model approved |
| Per-Brain `brain_platform.py` shim | `jobs/{biological-brain,sector-intelligence-brain,water-clarity-brain}/brain_platform.py` | 3 × 21 identical | Python | **delete** after platform becomes an installable package | `sys.path` hack |
| Per-Brain `orchestration.py` | Fish + Intelligence (different content) | | Python | each Brain's `runtime/` entrypoint implementing the platform `Runner` interface | |
| Job images | `Dockerfile` (server + Lake + WaterTemp binaries), `jobs/brain-image-build.sh`, per-job Dockerfiles | | | `deploy/` per deploy unit | One image carries three binaries |
| Ops/alerting | `ops/` | | | `platform/ops/` | |

## 2. Record: Orchestrator

* **Does:** hourly wake; per-Brain `plan()`; triggers `lake-brain`/`water-temp-brain` Cloud Run jobs; runs Fish and Intelligence in-process; runs `brain-scores --if-changed`; writes `/control/orchestrator`, `/jobs/*`, scores.
* **Smell:** it executes Brain code by path (`{"kind":"in-process","dir":"../biological-brain"}`), so Brain implementation is part of the orchestrator image.
* **Target:** orchestrator only knows the **Runner interface** declared in each `brain.json` (`runtime.kind: job|in-process|service`, `plan()` entrypoint). Brain code is packaged as a dependency, not read from sibling directories.

## 3. Record: Publisher

* **Current:** does not exist on the mainline. All Brains write through the platform library with the shared `brain-writer` identity (CERT-9: per-Brain writer hardening is later).
* **Shadow (branch):** artifact handoff, canonical form, plan, validate (schema + path ownership), registry, storage (`artifacts/ publishes/ scores/ exports/` prefixes of CERT-3), sinks.
* **Repository requirement:** the Publisher is **Platform code only**. It must be able to load `brain.json` declarations (allowed publish families, schemas) so path ownership is data, not code edited per Brain.

## 4. Record: Scoring Platform

* Single evaluator `scoring.py`; rubric = JSON; `basis` FROZEN or COMPUTED; published at `/scores/{brainId}` by `brain-scores` (`--if-changed`).
* Provisional Engine aggregate (`engine-score-v1.json`, CERT-6 deferred).
* **Structural issue:** score *definitions* (owned by each Brain's maturity story) and score *machinery* (platform) are both in `docs/`. Target: machinery in `platform/scoring`, per-Brain rubric in `brains/<id>/scoring/rubric.json`, engine+beta rubrics in `platform/scoring/rubrics/`, and **no rubric lives in `docs/`**.
* **Score types** (naming rule for the target): `ENGINE_READINESS_SCORE` (per Brain, platform-published) ≠ `SCIENTIFIC_VALIDATION_METRICS` (Brain `validation/`) ≠ `CANDIDATE_SCORE` (a Brain's internal model output, e.g. Wind bowfishing score) ≠ `CONDITIONS_SCORE` (customer product score, `engine/`) ≠ `ENGINE_AGGREGATE` (provisional, platform).

## 5. Shared-library delivery problem (single root cause of many smells)

Python code is not installable; jobs locate the platform with `sys.path.insert(0, "../brain_platform")`, three jobs carry a shim, deploy scripts vendor a copy into the image, Wind's `writer.py` repeats the trick, `scripts/hydrology/*` reach into `jobs/lake-surface`. The `jobs/brain_platform` directory name uses an underscore, its siblings use hyphens, so it is the only importable directory name (by accident).

Target: `platform/python` is a `pyproject.toml` package `sector_brain_platform` (stdlib-only to preserve the orchestrator's zero-dependency image), installed with `pip install -e` for tests and copied/installed at image build; each Brain package depends on it by name. Swift gets the equivalent via SwiftPM target dependency. Both pass `contracts/conformance` fixtures.

## 6. What must not be duplicated inside each Brain

Envelope/publish, keys (`lake_key`), freshness & health vocabularies, job manifest, control state, score evaluation, path ownership, identity/lineage, Publisher handoff, dependency-state reading. Brains supply only: state computation, artifact builder, schemas, rubric, `brain.json`.
