# Repository Migration Plan V1 (PROPOSED; NO EXECUTION)

**Status:** plan only. Nothing is moved by this audit. Each phase needs its own approval, its own branch, and a green gate before the next starts.

## Global rules
* **Moves are `git mv` + compatibility shim**, never copy-then-delete; history is preserved. Old paths keep working (shim or symlink-free re-export) until the Phase 7 retirement.
* **Behavior-neutral gates on every phase:** (1) golden `/conditions` + `/lakes` response byte-compare (Swift build), (2) all Python suites, (3) conformance fixtures Swift+Python, (4) score before/after identical, (5) rendered Cloud Run job definitions unchanged (diff of `deploy-job.sh` effective args), (6) image labels still carry `commit`.
* **No deploy** unless a phase says so; deploys follow the existing lineage rule (verify deployed SHA + safe lineage before any shared deploy; only additive specialist commits).
* **No branch/worktree deletion** in any phase before Phase 7, and only for branches proven fully contained.
* Hand-synchronized registries are **replaced by generated ones only after** the generated output is byte-identical to the hand copy (diff test).
* The three parallel workstreams (data-architecture, Publisher V1 shadow, Wind certification) are not touched; their commits are adopted, not re-implemented.

## Phase 0: Approve structure
| | |
|---|---|
| Files affected | none (decisions in `REPOSITORY_AUDIT_DECISIONS.md`) |
| Tests | none |
| Compatibility | none |
| Rollback | n/a |
| Runtime change / deploy | no / no |
| Stop condition | Michael approves RA-1…RA-6 (tree, `brain.json` format, Lake registry home, embedded-adapter rule, CI plan, Wind-first) |

## Phase 1: Platform/shared skeleton (additive)
| | |
|---|---|
| Files affected | **create** `platform/`, `contracts/`, `providers/`, `engine/`, `brains/_template/`, `tools/`, `tests/architecture/`; add `pyproject.toml` for `sector_brain_platform`; add `contracts/schemas/brain.schema.json`; add architecture tests (report-only mode). **Move** `docs/brains/conformance/*` → `contracts/conformance/` with CI path update and a pointer README at the old path. No source file other than conformance fixtures moves. |
| Tests | conformance (Python + Swift) reading the new path; architecture tests in report-only (warn) mode; CI path filter updated; add Swift build/test to CI or scheduled run |
| Compatibility | old conformance path keeps a stub README only; tests read via one constant |
| Rollback | revert the commit (additive + one fixture move) |
| Runtime change / deploy | none / none |
| Stop condition | CI green on both languages; architecture report lists current violations as the baseline (the violation list *is* the migration backlog) |

## Phase 2: Wind as first certified example
Depends on Publisher V1 shadow (approved HEAD `d090c428`) and the Wind certification session.
| | |
|---|---|
| Files affected | `jobs/wind-hourly/**` → `brains/wind/**` per `STANDARD_BRAIN_PACKAGE_V1` §5; adopt `artifact.py`; write `BRAIN_OPERATING_CONTRACT.md`, `brain.json`, `contracts/`, `research/GAPS.json` + `MANIFEST.json`; triage `feat/wind-brain-adoption` docs; replace hard-coded paths with env config; platform becomes `pip`-installed (Wind stops using `sys.path`); `wind-hourly` deploy script moved; `jobs/wind-hourly` left as thin stub (README → new location) |
| Tests | Wind suite (8 files) unchanged results; `test_publish_artifact`; Publisher shadow integration; new `brain.json` schema test; no-absolute-path test for `brains/wind`; **golden Wind RTDB write plan identical** (shadow compare) |
| Compatibility | `sector_wind` import path preserved; deploy script path alias; Cloud Run job names/SA/schedule unchanged; image still labeled with commit; image `COPY` list updated and verified to still exclude research |
| Rollback | revert merge; `jobs/wind-hourly` stub restored from history; deployed job unaffected because no redeploy |
| Runtime / deploy | **No behavior change.** A redeploy of `wind-hourly` is optional and separate (lineage rule); not required to validate the move |
| Stop condition | architecture tests for `brains/wind` pass in enforce mode; BEFORE/AFTER shadow output identical; Michael accepts Wind as the reference Brain |

## Phase 3: Validate build / tests / import compatibility
| | |
|---|---|
| Files affected | none new; fixes only |
| Tests | full Python + Swift suites; clean-clone install (`pip install platform`, build Wind image locally/Cloud Build dry-run); orchestrator image staging test (no sibling-dir imports for Wind); import-lint in enforce mode for `engine/`, `providers/`, `platform/`, `brains/wind` |
| Compatibility | confirm Dockerfile `.dockerignore` (`docs/`, `jobs/` excluded from the Swift build context) still works as `Sources/` start moving later |
| Rollback | revert fixes |
| Runtime / deploy | none / none |
| Stop condition | a developer or AI session can onboard to Wind using only `brains/wind/README` + contract; zero open violations for Wind |

## Phase 4: Migrate Fish (`biological-state`)
| | |
|---|---|
| Files affected | `jobs/biological-brain/**` → `brains/fish/**` (brainId unchanged); adopt `feat/biological-brain-adoption` content (rules, features, movement, 11 schemas, tools, 16 tests) after Fish certification triage; delete the 3 `brain_platform.py` shims *only for Fish*; Species Registry skeleton → `platform/species-registry/` (CERT-8); `docs/brains/scoring/biological-state-score-v1.json` → `brains/fish/scoring/rubric.json`; the orchestrator stage list reads Fish via `brain.json` |
| Tests | Fish suite; orchestrator test using registry-derived Runner; score identical; `SpeciesDatabase` adapter parity test (Engine unchanged) |
| Compatibility | orchestrator keeps an alias for the old `dir`; scoring publisher reads the rubric from either path via one resolver |
| Rollback | revert; resolver falls back |
| Runtime / deploy | no behavior change; orchestrator redeploy needed only when its staging changes (separate approval) |
| Stop condition | Fish at standard; **Phase 5 audit may begin** |

## Phase 5: Architecture Audit #1
Re-run this audit's scans against `brains/wind` + `brains/fish` + platform skeleton. Compare the Phase-1 baseline violation list with reality; adjust the standard (the process in `BRAIN_CERTIFICATION_V1` already schedules it). Outputs: revised `STANDARD_BRAIN_PACKAGE`, any reordering of Lake → Temperature → Clarity → Depth → Vegetation → Intelligence. No file moves except standard corrections. Stop: Michael signs the revised standard.

## Phase 6: Migrate remaining Brains sequentially
Order proposed (reorderable by Audit #1): **Lake** (foundation; registry first), **Water Temperature**, **Water Clarity**, **Depth**, **Vegetation**, **Sector Intelligence** last.

| Brain | Special steps |
|---|---|
| Lake | create `brains/lake/registry` (xlsx + generators → versioned registry contract); Swift `LakeBrain` target `path:` re-pointed (no source edit); split `Support/LakeDirectory` out; move `jobs/lake-brain/*` tooling (fix ≈12 legacy paths; add to CI); `jobs/lake-geometry`; adopt `feat/lake-consolidated` content after triage; Wind/Clarity switch from `lakes.json` / `/lakes` HTTP to Lake contract (small behavior-preserving commits, each compared byte-for-byte) |
| Water Temperature | library target for the embedded adapter; move `Brain/WaterTemperature*` + `WaterTemp/`; `jobs/water-temp-brain/` one-file dir folded in; TVA archive → `providers`/Water Temp; research from `docs/water-temp-brain-research` → workspace + manifest |
| Water Clarity | **first resolve D4** (live `lake-surface-daily`/`clarity-current-hourly` source off-main); `Hydrology/` → Clarity science library; `scripts/hydrology/*` → `research/tools`; 12 MB evidence + 7.5 MB polygons → release artifact or exception; stop reading the customer `/conditions` API (consume providers + Lake contract) |
| Depth, Vegetation | adopt branch code as the reference copy; no base code exists to move; preserve branches |
| Sector Intelligence | derive dependencies from `brain.json`; leave pilot scope; evidence-layer contracts adopted |
| Each | tests: Brain suite + before/after score + golden customer response for touched Swift; one PR per Brain; `jobs/<dir>` stub README until Phase 7 |

Gate per Brain: contract written, `brain.json` valid, architecture tests enforce, score unchanged, deployed jobs untouched or redeployed through lineage-safe process.

## Phase 7: Retire proven legacy structures
| | |
|---|---|
| Files affected | remove empty stubs under `jobs/`; remove per-Brain `brain_platform.py` shims; remove `docs/brains/conformance`/`scoring` pointers; split `docs/brains/` leftovers into `docs/platform` and `docs/history`; engine move (`Sources/SectorEngine/Engine…` → `engine/`) and provider extraction (`Fetchers`, `Adapters` → `providers/swift`) executed here or earlier as separate PRs with golden-response gates; replace hand-synced registries by generated; delete `.pyc`; retire `writer.py` direct-write code only per the 14-step retirement after Publisher cutover |
| Tests | full suite + golden customer responses + score identity + Publisher-only write test |
| Compatibility | 2-cycle deprecation notice (README redirects) for old paths |
| Rollback | revert per-PR; branches still exist |
| Runtime / deploy | none by themselves; customer redeploy only if `Sources` moves change the build (rebuild produces identical binary behavior; verify via golden test), through `deploy.sh` with explicit approval |
| Stop condition | architecture tests enforce for all Brains; zero baseline violations; Michael approves branch hygiene as a *separate* task |

## Suggested ordering of the Swift moves
SwiftPM `path:` lets targets move without edits to source. Do it in this order to minimize risk: (1) tests split into per-target test targets while sources stay; (2) `SectorBrainPlatform` target; (3) `SectorProviders`; (4) Lake / Water Temp / Clarity library targets; (5) physically move `Sources` into `engine/`, `providers/`, `platform/`, `brains/`. Each step compiles with `swift build` and passes the golden test before the next.

## What is deliberately not in this plan
Deleting branches/worktrees, rewriting history, changing Cloud Run/IAM/Firebase/RTDB rules, changing any score or customer response, Publisher cutover (separate, CERT-2), research migration out of branches (separate, per-Brain certification), renaming `biological-state`.
