# Repository Migration Plan V1 (LOCKED SEQUENCE; NO EXECUTION)

**Status:** `REPOSITORY_ARCHITECTURE_V1_APPROVED_FOR_PHASE_1`. Plan only. Nothing is moved by the audit. Each phase starts on its own go-ahead, on its own branch, and the next phase starts only after the previous gate is green.

## Global rules
* **Moves are `git mv` + compatibility shim**, never copy-then-delete; history is preserved. Old paths keep working until Phase 7.
* **Behavior-neutral gates on every phase after 1B:** (1) golden `/conditions` and `/lakes` responses byte-compare, (2) all Python suites, (3) Swift tests, (4) Swift+Python conformance fixtures, (5) score before/after identical, (6) effective Cloud Run job definitions unchanged, (7) image `commit` labels preserved.
* **No deploy** unless a phase says so; deploys follow the lineage rule (verify deployed SHA and safe lineage before any shared deploy; only additive specialist commits).
* **No branch/worktree deletion** in any phase (RA-23). No product-behavior fixes to make migration green: pre-existing failures are recorded as baseline.
* Hand-synchronized registries are replaced by generated ones only after generated output is proven equivalent (diff test).
* Parallel lanes (data-architecture, Publisher V1 shadow, Wind certification) are not modified; their commits are adopted, not re-implemented.
* `docs/` historical relocation waits for the RA-14 read-only private-content review.

## Phase 0: Repository Architecture V1 approval / lock: **DONE**
Locked by `REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`. No files besides docs.

## Phase 1A: Additive skeleton and machine schemas (NO runtime moves)
| | |
|---|---|
| Files affected | **create only**: `engine/`, `providers/`, `platform/` (incl. `platform/registries/{brains,lakes,species}/`), `contracts/`, `brains/_template/`, `tools/`, `deploy/`, `tests/architecture/`, root-level `docs/{platform,history}/` index READMEs. Machine schemas: `contracts/schemas/brain.schema.json`, `providers.schema.json`, registry schemas for Brain/Lake/Species, `customerIntegrationMode` enum. Operating-contract template + checklist in `brains/_template/`. **No empty ceremonial directories**: each new directory holds a README or schema stating its purpose and import rules. `pyproject.toml` stub for `sector_brain_platform` allowed only if it does not change how existing jobs import it. |
| Tests | schema self-tests (valid/invalid examples); architecture tests exist but are **report-only** |
| Compatibility | nothing existing is touched or re-pointed; existing jobs and Swift build identical |
| Rollback | revert the commit(s) |
| Runtime change / deploy | none / none |
| Stop condition | skeleton + schemas reviewed; `swift build` and all current suites unchanged |

## Phase 1B: Baseline CI, conformance and golden behavior gates
| | |
|---|---|
| Files affected | `.github/workflows` (Swift build+test enters CI, or a scheduled/path-filtered workflow if the 20-minute cost demands it; missing Python suites: `jobs/lake-brain/**` tests, `jobs/lake-geometry`, all `jobs/brain-scores` tests, `scripts`/tools where practical); non-Brain infrastructure enrolled **explicitly** (platform, providers, customer Engine, cross-cutting integration); Brain coverage additionally derivable from `brain.json` once Brains declare it. **Move `docs/brains/conformance/*` → `contracts/conformance/`** (RA-11) with one path constant and a pointer README at the old path (the only relocation in Phase 1). Golden fixtures for `/conditions` and `/lakes` and the score baseline recorded. |
| Tests required | Swift tests; existing Python suites; missing Python suites; architecture + conformance checks (report-only); **clean-clone install/import checks** (fresh venv, install platform, import each registered package); golden `/conditions`, golden `/lakes`, score baseline |
| Baseline policy | **record existing failures as baseline; do not fix unrelated product behavior.** The architecture report's violation list is the migration backlog. |
| Compatibility | old conformance path retained as stub; CI path filters updated |
| Rollback | revert; workflows are additive |
| Runtime change / deploy | none / none |
| Stop condition | CI green or baseline-recorded; golden artifacts committed; report-only architecture output reviewed |

## Gate P: Publisher / Wind shadow prerequisites (owned by the Publisher and Wind lanes; NOT performed by repository sessions)
Run in parallel with, or immediately after, Phase 1. The latest Wind certification pass consumed Publisher V1 Shadow `d090c4283fbbc2d95ef0a815c650ae5789294799`; nothing live changed. Findings to be addressed or explicitly resolved before Wind's final Publisher/cutover certification and before Phase 2 (RA-6 D):

| ID | Finding | Owner lane |
|---|---|---|
| F-1 | volatile scalar children not fully stripped from comparison, so SKIP is not reliable | Publisher |
| F-2 | one logical Wind run yields multiple publication plans; the model is one Brain artifact / one deterministic atomic publication boundary where appropriate | Publisher + Wind |
| F-3 | publication metadata overwritten per plan instead of being Publisher-owned publication state | Publisher |
| F-4 | no DELETE semantic, so stale optional children persist; deletion must be explicit and safe; missing/null never implies delete | Publisher |
| F-5 | several legacy Wind paths unauthorized under the new ownership model (legacy `lakeFleet` identity projection, snapshot identity/version projections, health/jobs legacy state). Do not broaden Wind ownership to keep legacy layout; classify each as **platform-owned**, **derived compatibility projection**, or **legacy reader dependency**, and migrate intentionally | Publisher + Platform + Wind |
| F-6 | Ops depends on some legacy health/job representation; preserve Ops behavior until the replacement contract exists | Platform/Ops |
| F-7 | legacy activity pruning / failure-health behavior must be reassigned or retired, not blindly copied into Wind's package | Platform |
| F-8 | Wind's volatile-comparison contract needs a finalized registered definition | Wind + Publisher |
| F-9 | shadow baseline representation ≠ live state; an intentional equivalence/migration comparison is required before cutover | Publisher + Wind |

**Wind research-preservation facts incorporated:** Wind evidence is scattered across Git branches, local research directories, caches, iOS Git and private storage; the standardized research workspace is intentionally still empty; a research manifest/hash catalog exists as a planning artifact; significant time-sensitive Wind evidence needs durable backup (CERT-4); Lake Registry geometry found under Wind is **Lake Registry-owned reference material, not Wind truth**; no research data moves until approved.

**Publisher security gate (high level; details stay private):** specialist Brain production write permission must eventually be removed and the Publisher becomes the production door, **but the Publisher itself needs an acceptably bounded production write model**; moving an excessively broad production role from Wind to the Publisher does not fix the architecture. This is a **live-cutover blocker** governed by certification/security (CERT-9), not a repository migration task, and no private detail goes in this repo.

## Phase 2: Wind repository migration
**Entry requirements (all):** A Architecture V1 locked ✔; B additive skeleton (1A) ✔; C baseline CI/conformance/golden gates (1B) ✔; D Gate P findings addressed or explicitly resolved to the point the Publisher shadow contract is stable enough for Wind's artifact home; and no live behavior change.
| | |
|---|---|
| Files affected | `jobs/wind-hourly/**` → `brains/wind/**` per `STANDARD_BRAIN_PACKAGE_V1` §5; adopt `artifact.py` from the cert branch; write `BRAIN_OPERATING_CONTRACT.md`, `brain.json`, `contracts/`, `research/GAPS.json` + manifest metadata; classify research artifacts (Standard §3a); consume **Lake Registry** contract instead of `lakes.json` once the registry contract exists (until then `lakes.json` kept, marked derived); replace hard-coded paths with env/config; platform installed rather than `sys.path`; keep a thin `jobs/wind-hourly` stub |
| Tests | Wind suite (8 files) unchanged results; `test_publish_artifact`; Publisher shadow integration; `brain.json` schema test; no-absolute-path test; golden Wind write-plan compare (shadow) |
| Compatibility | `sector_wind` import path preserved; Cloud Run job names/SA/schedules unchanged; image `COPY` list re-verified to exclude research |
| Rollback | revert merge; stub restored; deployed job unaffected (no redeploy required) |
| Runtime / deploy | no behavior change; optional separate lineage-safe redeploy |
| Stop condition | architecture tests enforce for `brains/wind`; shadow output identical; Wind accepted as the reference Brain |

## Phase 3: Validate Wind structure / build / import / conformance
Full Python + Swift suites; clean-clone install; Wind image build (dry run); orchestrator staging without sibling-directory imports for Wind; import-lint enforce mode for `engine/`, `providers/`, `platform/`, `brains/wind`. Stop: a new session can onboard to Wind from `brains/wind/README.md` + contract only; zero open Wind violations.

## Phase 4: Fish migration (`brains/fish`, brainId `biological-state`)
`jobs/biological-brain/**` → `brains/fish/**`; adopt `feat/biological-brain-adoption` content after Fish certification triage (classify each artifact per Standard §3a); remove the three `brain_platform.py` shims **for Fish only**; Species Registry skeleton content under `platform/registries/species/` (CERT-8); rubric → `brains/fish/scoring/`; orchestrator reads Fish through the Brain Registry. Tests: Fish suite; registry-derived Runner; score identical; `SpeciesDatabase` adapter parity. Stop: Fish at standard; Phase 5 may begin.

## Phase 5: Architecture Audit #1
Re-run the audit scans on Wind + Fish + skeleton; compare against the 1B baseline; amend the standard and Brain order if warranted. Stop: Michael signs the revised standard.

## Phase 6: Remaining Brains (order reorderable by Audit #1)
| Brain | Special steps |
|---|---|
| Lake | **Lake Registry** (platform-owned) established first: identity, aliases, classification, basic geographic identity, stable metadata, geometry/boundary **reference**; split-by-storage per Target §6a; `Support/LakeDirectory` split out; then Lake Brain proper (hydrology, pool/level interpretation, source bindings, presence, validation) in `brains/lake/`; consumers (Wind, Clarity, Temperature, Fish) switch from copies/HTTP to the Registry contract in small behavior-preserving commits |
| Water Temperature | `customerIntegrationMode: embedded` library; `jobs/water-temp-brain` one-file dir folded in; TVA archive ownership via PROVIDERS.json (no TVA consolidation before D8) |
| Water Clarity | **BLOCKED by D4** until separately resolved; then `Hydrology/` science library (`embedded`), stop calling customer `/conditions` and `/lakes` (RA-20), `scripts/hydrology/*` classified, large evidence/polygons per policy |
| Depth, Vegetation | adopt foundation branches at their turn; branches preserved |
| Sector Intelligence | dependencies derived from `brain.json`; last |
Gate per Brain: contract + `brain.json` valid; required contracts/runtime/tests represented; score unchanged; golden customer responses unchanged for touched Swift.

## Phase 7: Retire proven legacy structures
Remove empty stubs, per-Brain shims, pointer READMEs; split `docs/brains/` leftovers into `docs/platform` and `docs/history` (after RA-14 review); move `Sources` into `engine/`, `providers/`, `platform/`, `brains/` using the Swift order (split tests → platform target → providers target → Brain library targets → physical move) with golden gates; generated registries replace hand copies after equivalence proof; `writer.py` direct-write code retired only per the 14-step retirement after Publisher cutover; update root `README.md` (RA-21). **Branch/worktree deletion remains a separate task.**

## What is not in this plan
Publisher implementation or fixes (Gate P lanes), Publisher security design, live cutover, deleting branches/worktrees, history rewrite, Cloud Run/IAM/Firebase/RTDB rule changes, score or customer-response changes, TVA consolidation, Clarity D4 decision, renaming `biological-state`.
