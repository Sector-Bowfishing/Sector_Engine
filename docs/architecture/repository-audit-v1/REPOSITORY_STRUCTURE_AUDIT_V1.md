# Repository Structure Audit V1: current-state audit

**Status:** `REPOSITORY_ARCHITECTURE_PROPOSED_V1` (proposal only: not migrated, not certified, not deployed).
**Audited:** base commit `fab115e9` (branch `audit/repository-structure-v1`, local). **Method:** read-only inspection of the tracked tree plus `git` provenance of the Brain branches. No file was moved, renamed, deleted, rewritten, built or deployed.
**Public repo:** this document names no per-lake species data, credentials, live dumps or user identifiers.

Package: `CURRENT_REPOSITORY_MAP` · `BRAIN_REPOSITORY_INVENTORY` · `PROVIDER_AND_SERVING_INVENTORY` · `PLATFORM_REPOSITORY_INVENTORY` · `REPOSITORY_DEPENDENCY_MAP` · `TARGET_REPOSITORY_ARCHITECTURE_V1` · `STANDARD_BRAIN_PACKAGE_V1` · `REPOSITORY_MIGRATION_PLAN_V1` · `REPOSITORY_AUDIT_DECISIONS` (all in this folder).

## 1. Executive summary

Sector_Engine is **one SwiftPM package plus ten Python job directories plus a 454-file `docs/` tree**, grown by adding a Brain wherever its author was working. The result:

* There is **no place that says "this is Brain X".** A Brain is scattered across up to five locations: Swift under `Sources/SectorEngine/{LakeBrain,Brain,WaterTemp,Hydrology}`, a Python job under `jobs/`, docs under `docs/brains/` (flat, 40 files), rubric JSON under `docs/brains/scoring/`, fixtures under `docs/brains/conformance/`, and, for Depth, Vegetation and most of Wind/Fish, **only on branches**.
* **The customer Engine and the Brains share one Swift module** (`SectorEngine`, ~18.8 k lines, one test target). `Engine/` (customer scoring), `Fetchers/` (providers), `Brain/` (platform + Water Temp), `LakeBrain/` (3.9 k lines), `Hydrology/` (Clarity) and `Support/` (which also holds the 621-lake registry) are folders, not boundaries. A Brain job imports customer code (Lake Brain calls `TVAGenerationService`, and documents that the customer parser is wrong for "Midnight" rows).
* **Platform infrastructure exists twice** (Swift `BrainPlatform`/`BrainContract`/`BrainRTDBStore` and Python `sector_brain_platform`, ~4.7 k lines) held together by shared JSON fixtures under `docs/brains/conformance/`. That is a sound technique, but the fixtures live in `docs/`.
* **Python Brains find the platform with `sys.path.insert` and an identical 21-line `brain_platform.py` shim copied into three job dirs** (md5-identical). Deploys vendor a copy of the package into the image.
* **Provider code is not a layer.** TVA is parsed in four places (two Swift, two Python), USGS in at least three, Open-Meteo in the customer fetcher, the Water Temp Brain's forcing, Wind research/bake-off scripts, and as a Clarity fallback. Source ownership (`ownership.py`) records `open-meteo-forecast` as owned by `water-temp`, which is true of the *source-health record* but is not a statement about the client.
* **Docs are partly runtime.** `docs/brains/scoring/*.json` and `frozen-scores.json` are staged into the orchestrator image; `docs/brains/conformance/*.json` are test inputs and CI path triggers; `docs/data/Sector_Lakes_APIs_2.xlsx` is the source of the lake directory; `docs/data/hydrology` (12 MB, 327 files) feeds a generated 100 KB Swift file.
* **Governance is strong; the folder structure does not express it.** `docs/architecture/{data,certification}` already define path ownership, lineage, data classes, research workspace and the Publisher target. The repo layout does not yet let a newcomer find a Brain's contract, schemas, rubric, tests and jobs in one place.

**Answer to the core question:** keep the Swift package where SwiftPM needs it, but make **domains physically separate and import-checked**: `engine/` (customer-serving), `providers/` (acquisition), `platform/` (Brain Platform: orchestrator, publisher, scoring, contracts, registry), `brains/<id>/` (one self-contained home per Brain), `contracts/` (shared language-neutral schemas and conformance fixtures), `docs/` (architecture, platform, history), `tests/` (cross-cutting only). Details in `TARGET_REPOSITORY_ARCHITECTURE_V1.md`.

## 2. What the repository contains (measured)

| Measure | Value |
|---|---|
| Tracked files | 868 (`docs` 454, `jobs` 252, `Sources` 92, `Tests` 37, `scripts` 23) |
| Swift | 19.2 k lines in 5 targets (library `SectorEngine`; executables `SectorEngineServer`, `LakeBrainJob`, `WaterTempBrainJob`, `ClarityReplay`); 26 test files in one target |
| Python | ~29 k lines across 14 job dirs; the largest are `wind-hourly` 9.3 k (incl. 28 research scripts), `lake-brain` 5.1 k (tooling, not runtime), `brain_platform` 4.7 k |
| Worktrees / branches | 55 worktrees, 149 local+remote branches; base is **51 commits ahead of `main`** (the architecture/cost-freeze/orchestrator stack) |
| Tracked generated/large | `polygons.geojson.gz` 7.5 MB; `docs/data/hydrology` 12 MB; `LakeSourceBindingsGenerated.swift` 425 KB; `LakeDirectory.swift` 190 KB; `HydrologyData.swift` 103 KB; `bindings.proposed.v1.json` 760 KB; `holdout_v2_results.json` 494 KB; 2 committed `.pyc` files |
| CI | one workflow (`python-jobs-tests`), Python only, a hand-maintained directory list; Swift not in CI |

## 3. Does a Brain live fully in GitHub today?

**Partially.** What is in the base (`fab115e9`) per Brain:

| Brain | Runtime in base | Contract / docs in base | Where the rest is |
|---|---|---|---|
| wind | yes (`jobs/wind-hourly`, 22 modules + `brain/`) | `BRAIN.md`, `README.md`, `SESSION_CLOSEOUT.md` in the job dir; no `docs/brains/wind` | `feat/wind-brain-adoption` / `deploy/wind-internal-validation`: 91 spec/prereg/decision docs, 17 more `sector_wind` modules, 18 research scripts, 12 tests, field packets, data; `cert/wind-architecture-v1` (artifact builder, certification docs); `feat/publisher-v1-shadow` |
| biological-state (Fish) | thin (789 lines: bundle loader + publisher shim) | `BIOLOGICAL_BRAIN_INTEGRATION.md`, 4 schemas | `feat/biological-brain-adoption`: rules, features, movement, capability, 11 schemas, 10 tools, 16 tests, 36 docs; `docs/biological-brain-research`: 18 research docs |
| lake-brain | yes, **Swift** (`Sources/.../LakeBrain`, `LakeBrainJob`) + Python tooling (`jobs/lake-brain`) | 11 `LAKE_*` docs flat in `docs/brains/` | `feat/lake-consolidated` (70 commits ahead: readiness, +history, +review), `docs/lake-brain-research` (165 files incl. 55 research docs + 100 `research/lake-brain` tool files) |
| water-temp | yes, **Swift** (`Brain/`, `WaterTemp/`, `Fetchers/`) | `WATER_TEMP_BRAIN.md` | `docs/water-temp-brain-research` (178 files `docs/research/water-temp`), `feat/water-temp-brain-adoption` |
| water-clarity | yes, Python (`jobs/water-clarity-brain`) + Swift `Hydrology/` + satellite jobs (`lake-surface*`, `hydrology-hourly`) | 4 `WATER_CLARITY_*` docs, `docs/clarity/` | **fusion lineage** `feat/clarity-algal-warning` (`Sources/ClarityPrecompute`, the *live* `lake-surface-daily` source), `feat/clarity-candidate-shadow` (51 commits, 15 k files, private research), `research/clarity-candidate` |
| depth | **none** | none | `feat/depth-brain-foundation`: 52-file package `jobs/depth-brain/depth_brain`, 26 tests, 82 docs, 59 `research/depth` tools; `docs/depth-brain-research` (99 files) |
| vegetation | **none** | none | `feat/vegetation-brain-foundation`: 19-file package, 9 tests, 103 docs; `docs/vegetation-brain-research` (55 files) |
| sector-intelligence | yes (1.4 k lines + `catalog.json`) | 2 docs | `feat/intelligence-evidence-layer` (contracts, 6 tests), `docs/intelligence-deep-research` (32 files) |

So: **Brain runtime, for six Brains, is in the base; Depth and Vegetation exist only on branches; Wind, Fish and Lake carry most of their specs/validation on branches.** Raw research lives (a) outside GitHub in the local research root, (b) in `docs/*-research` branches as markdown, and (c) in the base as scripts with hard-coded Desktop paths. The principle "the Brain lives in GitHub; the research library does not have to" is **not yet true** for any Brain, and for Depth and Vegetation not even the runtime is on a mainline.

## 4. Source-of-truth separation (validated)

| Layer | Intended | Supported by the repo today? |
|---|---|---|
| GitHub = how the Brain works | contract, runtime, builder, schemas, scoring def., validation, tests | Partly. No operating contract exists for any Brain. Runtime location varies. Scoring rubrics exist for 3 of 8 Brains (`biological-state`, `lake-brain`, `sector-intelligence`); others use `frozen-scores.json`. |
| Research workspace = evidence | outside Git | Partly. Standard root is defined (`BRAIN_RESEARCH_WORKSPACE_V1`), but code still points at the **legacy** `Sector_Research_Data` root and at the iOS repo (`~/Desktop/Development/iOS/...`), and research markdown is parked on `docs/*-research` branches. |
| Canonical release storage | versioned, durable | Partly. Lake presence bundle in a private bucket (public file contains no data: good pattern). Fish canonical bundle loaded by `biological_brain.py`. Wind candidate bucket. No uniform release store yet (CERT-3 approved, not built). |
| `sector-brain` RTDB = compact current state | one writer (Publisher) | Not yet. Every Python Brain `run.py`, Wind's `writer.py`, the Swift `BrainRTDBStore` and the dispatcher write through the platform library with the shared `brain-writer` identity. Publisher V1 exists only in shadow on `feat/publisher-v1-shadow`. |
| Customer app DB | separate | Yes by convention (separate RTDB instances referenced from tooling), not audited here (security handled privately). |

## 5. Anti-pattern scan (results)

| Anti-pattern | Found? | Evidence |
|---|---|---|
| Brain-specific files in generic directories | **Yes** | Lake Brain, Water Temp, platform code in `Sources/SectorEngine/{LakeBrain,Brain,WaterTemp}`; Lake registry in `Support/`; `scripts/generate-lake-*.py`; Clarity science in `Hydrology/` |
| Provider clients duplicated | **Yes** | TVA ×4, USGS ×3+, Open-Meteo ×3+ (see `PROVIDER_AND_SERVING_INVENTORY`) |
| One Brain importing another's / the Engine's internals | **Yes** | Lake Brain → `TVAGenerationService` (Engine adapter); Water Temp Brain → `WaterLevelService`/`WeatherService` (Fetchers shared with `/conditions`); Orchestrator runs `biological-brain` and `sector-intelligence-brain` in-process; Clarity Brain consumes the customer `GET /conditions` and `/lakes` HTTP API |
| Tests with unclear ownership | **Yes** | 26 Swift tests in one flat target (Lake, Water Temp, Clarity, Platform, Engine, USGS mixed); loose `test_*.py` beside scripts in `brain-scores`, `lake-brain`, `lake-surface`; CI omits `lake-brain` tests, `lake-geometry`, most of `brain-scores` |
| Schemas duplicated / implicit | **Yes** | Platform contract in Swift + Python (kept equal by fixtures); per-Brain state shapes mostly implicit (built in code, described in prose); only Fish has JSON Schemas in base; two `catalog.json` files with different roles |
| Scoring logic duplicated | **Partly** | Evaluator single (`scoring.py`); but `beta.py`, `score_brains.py`, `frozen-scores.json`, and rubric JSON in docs are four artifacts for one concept; the customer *Conditions Score* (`conditions-score-v1`) is a separate, unrelated score living beside the readiness machinery |
| Stale/superseded docs beside current | **Yes** | `docs/architecture/data/*` (marked "superseded in part"), `docs/consolidation/*`, `docs/clarity/*`, `docs/scope/*`, `SECTOR_BRAIN_OWNERSHIP_AUDIT_TODO.md`, Wind `SESSION_CLOSEOUT.md` |
| Hard-coded local research paths | **Yes (≈25 sites)** | `jobs/lake-geometry`, `jobs/lake-brain/{review,history,bindings,validation}`, `jobs/wind-hourly/{sector_wind,research}`, `scripts/hydrology/*`; legacy root name `Sector_Research_Data`; code that reads `~/Desktop/Development/iOS/sector-wind` assets at runtime paths (`sector_wind/bowfishing.py`, `bowfishing_score.py`) |
| Direct specialist RTDB writers | **Yes (current, by design)** | All Brains through `sector_brain_platform.rtdb` / `BrainRTDBStore` with one shared writer identity; target is Publisher-only |
| Customer-serving code mixed with research | **Yes** | `Engine/Config/SpeciesLegality` (policy) and `SpeciesDatabase` inside the scoring path; `Hydrology/` research-grade models in the request path |
| Research scripts in runtime packages | **Yes** | `jobs/wind-hourly/research/` (28 scripts) beside the job; excluded from the image only by an explicit `COPY` list |
| Private/sensitive content in public repo | **Low risk, some hygiene** | No keys, tokens or private keys found by pattern scan. Present: GCP service-account emails and a personal email in docs/snapshots (`docs/brains/platform/cost-freeze/snapshots/*.json`, `PRODUCTION_LINEAGE.md`), job IAM topology in docs, Cloud Run job snapshots. Per-lake species data correctly kept out (Lake presence is a private bucket). **Recommend a private-content review before migration** (decision RA-14). |
| Generated data in source | **Yes** | `LakeSourceBindingsGenerated.swift`, `HydrologyData.swift`, `LakeDirectory.swift`, `bindings.proposed.v1.json`, `holdout_v2_results.*`, two `.pyc` |
| Large blobs | **Yes** | `polygons.geojson.gz` 7.5 MB, hydrology evidence 12 MB |
| Dumping-ground folders | **Yes** | `docs/brains/` (flat, 88 files incl. fixtures, rubrics, snapshots), `jobs/` (runtime jobs, research tooling, deploy scripts, platform lib, registry), `Sources/SectorEngine/Support/`, `scripts/` |

## 6. Cross-Brain coupling (summary; full map in `REPOSITORY_DEPENDENCY_MAP.md`)

* **Acceptable (published-contract style):** Sector Intelligence reads upstream Brain *state in RTDB* with each Brain's own staleness rule; Lake Brain's presence bundle takes Fish canonical overrides *through the Fish canonical release*; satellite dispatcher writes a dispatch file consumed by Clarity.
* **Questionable (shared implementation):** Water Temp Brain and customer `/conditions` share one Swift implementation (documented as intentional, `OWNERSHIP_MATRIX`), so a Brain change is a customer change.
* **Direct implementation import:** Lake Brain → `TVAGenerationService`; Orchestrator → Brain run code in-process; `scripts/hydrology/*` → `jobs/lake-surface` modules; `sector_wind` → iOS-repo assets.
* **Brain depends on customer API:** Clarity Brain `run.py` → `GET {ENGINE_URL}/conditions` and `/lakes` plus a Cloud Run service lookup. This couples a Brain's availability and numbers to the customer serving revision.
* **Cycles:** none at module level. A latent conceptual cycle: customer Engine consumes Water Temp/Clarity science that the same Brains are meant to publish.

## 7. Scoring, schemas, tests (summary)

* **Scores.** Types in play: (a) `ENGINE_READINESS_SCORE` per Brain (`/scores/{brainId}`, platform-written, rubric JSON + `scoring.py`, `frozen-scores.json` for Brains without a rubric); (b) the provisional Engine aggregate (`engine-score-v1.json`); (c) a *beta readiness* rubric (`beta.py`, `beta-readiness-v1.json`); (d) science/validation metrics inside Brain research (Wind scoreboard/validate, Lake holdout, Fish prereg analysis); (e) the **customer Conditions Score** (`conditions-score-v1`, `Engine/Aggregator`) which is a product output, not a readiness score. The repo does not separate (e) from (a)–(c) by location. Rubrics are in `docs/`; they are runtime inputs.
* **Schemas.** Platform/control contract: `control_manifest.json`, `control_contract.py`, `model_v1.py`, Swift `BrainContract.swift`. Brain state: Fish has JSON Schemas; every other Brain describes state in code and prose. Publication artifacts: none in base (Wind `artifact.py` and Publisher models exist on branches). API: Swift DTOs (`ConditionsResponse` etc.) only, no schema file. Runtime job manifest: `jobs.py`. Path ownership: `ownership.py` + `conformance/ownership.json` + `RTDB_PATH_OWNERSHIP_MATRIX.json` (three representations).
* **Tests.** Python: 38 test files across 11 dirs, offline, co-located; CI runs 7 dirs plus wind-hourly and one brain-scores file. Swift: 26 test files in one target, not in CI. Ownership by test is recoverable from file names but not from structure.

## 8. Branch / worktree provenance (what matters structurally)

| Brain | Branches | Verdict |
|---|---|---|
| wind | `brain/wind`, `intelligence/wind` (older lineage, all added paths already in base), `feat/wind-brain-adoption` ⊂ `deploy/wind-internal-validation` (same payload +2 commits; adoption superset of base wind), `docs/wind-brain-research`, `cert/wind-architecture-v1` (+5), `feat/orchestrator-wind-score-durability` (0 unique, merged) | Adoption/deploy branches hold the **newer** Wind (17 modules, 91 docs, 18 research scripts) → adoption decision in Wind migration. Older branches superseded. |
| biological-state | `brain/biological` (0 unique), `feat/biological-brain-adoption` (newer, 19 commits), `docs/biological-brain-research`, `feat/biological-score-v2` | Adoption is the real Fish Brain; base is the minimal shim. |
| lake-brain | `sector/lake-brain` & `feat/lake-brain-adoption` (0 unique), `feat/lake-consolidated` (70 ahead; superset of `lake-fleet-*`, `lake-brain-*`, `lake-rubric-proposals`, `lake-review-batch1`), `docs/lake-brain-research` | ~15 fleet/lake branches are slices of `feat/lake-consolidated`; treat consolidated as the candidate; slices REFERENCE only. |
| water-temp | `brain/water-temp`, `intelligence/water-temp` (972/963 files vs merge-base ⇒ older lineage with large research payload), `feat/water-temp-brain-adoption`, `docs/water-temp-brain-research`, `fix/water-temp-*` | 183 research docs on adoption/docs branches; base Swift is current. |
| water-clarity | `brain/water-clarity` (+2), `-public` (0 unique), `feat/clarity-production`, `-fusion-stage1`, `-algal-warning` (**live `lake-surface-daily` source**), `-candidate-shadow` (private), `research/clarity-candidate`, `campaign/clarity-readiness` | Jobs README records the explicit exception: live source is not on main (D4). Highest structural risk. |
| depth / vegetation | `feat/*-brain-foundation`, `docs/*-brain-research` | Only copy. Preserve. |
| sector-intelligence | `brain/sector-intelligence` (0 unique), `feat/intelligence-evidence-layer`, `docs/intelligence-deep-research` | Evidence-layer adds contracts + 6 tests. |
| platform | `feat/publisher-v1-shadow`, `feat/brain-platform-model-v1` (0 unique), `feat/engine-hardening`, `consolidation/*` | Publisher is next-in-line platform code; consolidation branches historic. |

Nothing was deleted or merged. Branch cleanup is out of scope and not recommended until each Brain's migration phase closes.

## 9. Findings to carry into design (ranked)

1. **Customer Engine and Brains share a module with no enforced boundary** (Swift) and share provider clients with divergent behavior (TVA).
2. **Brains are not self-describing**; there is no per-Brain home, contract, manifest, or research-gap register.
3. **Platform lib distribution relies on `sys.path` + vendoring + triplicated shim**, and the platform has two language implementations tied by fixtures that live in `docs/`.
4. **Runtime inputs live in `docs/`** (rubrics, frozen scores, fixtures, lake source spreadsheet, hydrology evidence).
5. **Depth, Vegetation, and most of Wind/Fish/Lake exist only on branches.**
6. **Research tooling sits in runtime trees with hard-coded Desktop paths** (≈25 sites).
7. **Provider layer is absent**, and `ownership.py` conflates source-health ownership with acquisition ownership.
8. **Test placement is un-owned for Swift, CI is Python-only and incomplete.**
9. **Public-repo hygiene**: service-account identities and live-job snapshots in docs; generated/large blobs; committed `.pyc`.
10. **Clarity live source is off-mainline** (jobs README D4).
