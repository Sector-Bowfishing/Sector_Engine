# Sector Engine — Cortex coordinated architecture completion — Session Record

```text
Standards: Rehtac Cortex 2.0.1 @ fc56557 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/architecture-standardization-2026-10-20 (local, not pushed) · Start commit: 93ee9c74 · Date: 2026-10-20
```

Continuation of `2026-10-20-architecture-all-brains.md` (same branch; its eight commits are preserved). `origin/main` is still `7dae7051`; nothing was pushed, merged or deployed.

## 1. Scope

- **Request and mode:** "Cortex coordinated architecture completion" — implement the remaining structural work for all eight Brains and the shared infrastructure, local and nonproduction only. The user's authorization in this session covers decisions D-1…D-14 of the previous record as listed in the request (package migration, SwiftPM target separation, `brain.json`, declared-input alignment, one identity model, orchestrator timeouts/retry, fallback honesty, internal contract fixes, tests, Depth/Vegetation reconciliation where compatible, text-only scoring metadata, synthetic species examples). Excluded: push, merge, deploy, production writes, schedules, Publisher LIVE, rules/IAM, numeric scores/rubrics, breaking public contracts, renaming stable ids, activating parked/shadow Brains, editing Cortex.
- **Inspected:** everything in the previous record, plus Certification Kit V1 internals (`spec.py`, `proofs.py`, `suite.py`, `mutations.py`), the Publisher registry and handoff, `Package.swift`, the Swift Brain runtimes and their tests, the root `Dockerfile`, the orchestrator image staging, the Swift and Python generators, the score baseline and artifact guards, the Depth and Vegetation branch packages (extracted read-only to a scratch directory).
- **Not inspected / not accessible:** production (deployed images, schedulers, RTDB, IAM, rules); Sector Ops and Pulse; a Linux `docker build` (the image products were built on macOS from the Dockerfile's exact COPY set).

## 2. Results by Brain

| Brain | Package | Runtime ownership | Certification Kit V1 | Structural status |
|---|---|---|---|---|
| Fish `biological-state` | `brains/fish/` | Python, in-process (orchestrator) | P01–P19 pass (51) | Canonical, certified V1 (unchanged); trigger declaration aligned |
| Wind `wind` | `brains/wind/` | Python job `wind-hourly` | P01–P19 pass (51) | Canonical, certified V1; `staleHours` 1.5 (was 6) |
| Water Clarity `water-clarity` | `brains/water-clarity/` | Python job (MANUAL) | P01–P19 pass (52) | Canonical, certified V1; manifest note on C1 vs C2 |
| Sector Intelligence `sector-intelligence` | `brains/sector-intelligence/` (**migrated**) | Python, in-process (orchestrator; image layout unchanged) | **P01–P19 pass (51)** | Canonical; Publisher SHADOW registration; versioned evaluation contract |
| Lake `lake-brain` | `brains/lake/` (**migrated**) | Swift targets `LakeBrain` + `LakeBrainJob` (brain-jobs image) | **P01–P13, P15–P19 pass; P14 NOT_APPLICABLE** (Swift writes) | Canonical; Publisher SHADOW registration; fallback record (PL-03) |
| Water Temperature `water-temp` | `brains/water-temperature/` (**migrated**) | Swift targets `WaterTemperatureBrain` + `WaterTempBrainJob` | **P01–P13, P15–P19 pass; P14 NOT_APPLICABLE** | Canonical; Publisher SHADOW registration; published schedule strings corrected |
| Depth `depth` | none on `main` (branch `feat/depth-brain-foundation`, `jobs/depth-brain/`) | none on `main` | not adopted | **BLOCKED** (§5.2) |
| Vegetation `vegetation` | none on `main` (branch `feat/vegetation-brain-foundation`, `jobs/vegetation-brain/`) | none on `main` | not adopted | **BLOCKED** (§5.2) |

Structural status is not production readiness: no Brain's lifecycle, schedule, writer or customer visibility changed. Every Publisher registration is SHADOW (Publisher LIVE authorizes no Brain).

## 3. Changes (13 commits on top of `93ee9c74`)

| Commit | Change | Class (as authorized) | Decision / requirement |
|---|---|---|---|
| `163d95d6` | Cert Kit harness: Brain-agnostic builder-import mutation; mutations of a NOT_APPLICABLE proof skip visibly. No proof changed | safe (harness fix) | Kit integration |
| `58967c9e` | Publisher SHADOW registrations for Intelligence, Lake, Water Temp; shared `publisher/flat_artifact.py`; provider catalog (11 providers); Lake-only fleet sources owned by `lake-brain` (Python + Swift) | authorized D-1 | PL-05, PL-11 |
| `11f18c1e` | Migrations: Intelligence → `brains/sector-intelligence/`; Lake, Water Temp → SwiftPM targets in `brains/lake/`, `brains/water-temperature/`; `package` access for the SectorEngine symbols they use; Dockerfile COPY set; deploy scripts; generators; Swift write-set fixture tests; Water Temp test seam; Kit adapters; architecture scan ignores Swift comments; baseline debt carried; D-9 schedule strings | authorized D-1, D-9, D-14(a) | BR-05/06/07/19, PL-05 |
| `40ccbfd3` | Mission checkpoint | records | — |
| `c606f7d4` | Intelligence: `provenance.brainVersion`, evaluation `sourceObservationAt`, inventory-mode blockers only without a pilot, catalog `2026-10-20.1`; `intelligence-evaluation-v1.schema.json` validated on real output | authorized D-8 | BR-13, BR-17, BR-20 |
| `9c3df55a` | Lake `sourceFallback` record (DEGRADED_USABLE / STALE_LAST_VALUE, primary kept, selected source and capability); additive, fixture unchanged | authorized D-4 | PL-03 |
| `05b04c89` | Declarations aligned: Wind `staleHours` 1.5, Fish trigger `dependency`, jobs.py inputs = observed, clarity purpose, manifest notes (Clarity C1/C2, Depth) | authorized D-2, D-10, D-11 | BR-09 |
| `fdf9ae46` | One identity model: consistency test across stable ids, packages, manifest, `keys.BRAINS`, Swift mirror, ownership, job/provider owners | authorized D-3 | PL-11, BR-07 |
| `57fcd26b` | Orchestrator: scorer timeout isolated; declared timeouts; bounded retry gate for automatic triggers | authorized D-7 | PL-02 |
| `89445e5d` | Scoring metadata text fixes (engine-score fact path, frozen-scores description and Wind scoreboard path); baseline hashes re-recorded; values unchanged | authorized D-12 | SC-08 |
| `ea4577d3` | Synthetic species-presence examples (Lake docs, Intelligence test fixture); history not rewritten | authorized D-13 | BR-12 |
| `05e780de` | Proposal (not active): label score measurements; retire Wind's self-published score copy | proposal (D-5, D-6) | SC-01, SC-04 |
| `6d7ae03a` | BR-03 publication guards for Lake, Water Temp, Intelligence; package READMEs | safe | BR-03, BR-01 |

### Implementation decisions taken (safest backward-compatible option, recorded)

1. **Swift target split** keeps the shared Swift Brain platform, fetchers and lake directory in `SectorEngine` (customer code uses them); only Brain-only code moved. Cross-module access uses Swift `package` (not `public`): no public API change. Product names, image paths, job ids and the orchestrator's staged layout are unchanged.
2. **Kit input for Swift Brains** is the runner's real write set on deterministic inputs, produced and drift-checked only by Swift tests; P14 is NOT_APPLICABLE with the reason (the kit audits Python write sites; Swift writes are pinned by `BrainOwnership.check` and the fixture tests).
3. **Intelligence snapshot field** is Brain-authored for evaluated lakes (a COPY projection would publish it for every lake).
4. **Lake fallback**: additive record; the ratified readiness ladder and `sourceCapability` are unchanged. The earlier "datum mislabel" suspicion was wrong (fallback readings are converted to the binding datum).
5. **Retry gate** only holds automatic runs back; explicit runs and callers without a ledger are unaffected.
6. **Clarity manifest**: a note instead of re-pointing `executionTarget` or adding a job (the cost-freeze test requires every Clarity job in the map to be PAUSED).
7. **Lake offline tooling** stays in `jobs/lake-brain/` (data files need classification before a move).
8. **Fixture integrity**: an edit to `contracts/conformance/lake_rules_v2.json` (pinned by hash) was reverted rather than re-pinning; its description keeps the old test path.
9. **Architecture report**: Swift comments no longer count as runtime `docs/` references (same rule as Python); real string literals still do. The Swift Brains' `import SectorEngine` (invariant 11) and Water Temp's published `artifactRef` labels (invariant 8) are carried baseline debt with `carriedFrom`.

## 4. Verification (final, on `6d7ae03a`)

| Check | Result | Baseline (start of standardization, `8a75b01b`) |
|---|---|---|
| `jobs/brain_platform` | 722 passed | 715 |
| `jobs/brain-orchestrator` | 46 passed | 42 |
| `jobs/brain-scores` | 35 passed | 35 |
| Legacy suites (lake-surface-dispatch, water-temp-tva-archive, lake-brain bindings/ledger/validation/review, lake-geometry) | 11 / 14 / 13 / 23 / 70 / 24 / 22 passed | same (Intelligence moved out of this list) |
| `brains/fish` | 395 passed, 2 skipped | 393 + 2 skipped |
| `brains/wind` | 215 passed, 16 deselected | 213 |
| `brains/water-clarity` | 127 passed | 125 |
| `brains/sector-intelligence` | 91 passed | (33 in `jobs/sector-intelligence-brain`) |
| `brains/lake` | 49 passed, 4 skipped (P14 NOT_APPLICABLE + its mutations) | — |
| `brains/water-temperature` | 50 passed, 4 skipped | — |
| `tools/brain_certification` (kit self-tests) | 32 passed | 32 |
| `tools/architecture` | 104 passed | 87 |
| `verification` | 14 passed | 14 |
| Wind package gates (deps required) | 6 passed | 6 |
| Architecture report / baseline | 0 new, 0 resolved, 35 known | 0 new, 20 known |
| `describe_contract.py --check` | 6 of 6 match the Publisher registry | 3 of 3 |
| Swift `swift build && swift test` | build OK; 316 tests, 0 failures | 313 |
| Image products from the Dockerfile COPY set (macOS) | SectorEngineServer, WaterTempBrainJob, LakeBrainJob, ClarityPrecompute: 0 errors | — |
| Orchestrator image staging (staging block only, no cloud) | staged runtime imports; both in-process executors resolve to the staged layout | — |
| Generators | `generate-lake-directory.py` reproduces `LakeDirectory.swift` byte for byte; `generate-lake-bindings.py --check` up to date | — |
| Output equivalence | Intelligence artifact byte-identical before/after the builder refactor; Lake fixture unchanged by the fallback change; Water Temp fixture diff = exactly the two D-9 strings; scoring JSON identical with strings masked | — |
| Depth / Vegetation branch suites on the current platform (scratch) | 226 passed, 13 failed / 108 passed, 2 failed | — |

**Not run:** a Linux Docker build; any job, orchestrator cycle, Publisher or scorer run against production; the Wind, Lake and Water Temp live `--dry-run` commands (they fetch live providers or the production Engine).

## 5. Open items

### 5.1 Structural requirements still open
- **D-14b** shared, non-customer Swift library: the Swift Brains import `SectorEngine` (fetchers, lake directory, Swift Brain platform); invariant 11 debt is carried (`legacy_violations.json`).
- **Lake offline tooling** in `jobs/lake-brain/` → `brains/lake/research/tools/` after the binding tables and hold-out results are classified.
- **Water Clarity C1 job registration** in the control manifest (blocked by the cost-freeze job-map invariant; needs a decision on how MANUAL jobs are listed).
- **Engine aggregate and score labels** (Proposal A) and **Wind's self-published score copy** (Proposal B): `docs/brains/platform/SCORE_MEASUREMENT_SEPARATION_PROPOSAL_V1.md`.
- **Stale description** in the hash-pinned fixture `contracts/conformance/lake_rules_v2.json` (old test path).

### 5.2 Depth and Vegetation — blocked (incompatible without redesign or missing decisions)
- **Depth** (`feat/depth-brain-foundation` @ `525b6b26`, 40 ahead / 178 behind `origin/main`): its runtime and tests read `docs/brains/depth/data/*.json` and a progress log (docs as runtime data; BR-11, invariant 8); read the Lake Brain's private Swift source (`LakeSourceBindings.swift`; invariant 7 — needs a Lake bindings contract); read the orchestrator's source; `score_v1/v2_proposal.py` compute scores inside the Brain (SC-04); a 1.06 MB `candidates.json` exceeds the data budget; `datum_providers.json` / `twdb_prereg.json` contain `/Users/…` paths. On the current platform: 226 passed, 13 failed (all those dependencies).
- **Vegetation** (`feat/vegetation-brain-foundation` @ `26555d8d`, 19 / 178): code is compatible with the current platform (108 passed); the 2 failures and the runtime's maturity check (`maturity.check_increase`) require ~25 evidence documents from `docs/brains/vegetation/` and the research branch `docs/vegetation-brain-research` to exist in the repository (runtime reads research evidence; BR-11; "research artifacts are not bulk-moved"); `maturity.py` computes a research maturity score inside the Brain (SC-04, marked official=false).
- Neither branch was merged, modified or deleted. Both stay registered as PARKED/`kind: none` in the manifest; their lifecycle is unchanged.

### 5.3 Blocker classes
1. **Current release blockers:** none identified (no customer path reads any Brain; obs.05).
2. **Structural certification blockers:** Depth and Vegetation (5.2); D-14b for Lake/Water Temp (invariant 11 carried); P14 for the Swift Brains needs a Swift write-site audit in the kit.
3. **Production integration blockers:** Publisher LIVE not wired (every Brain writes directly); rules/IAM unverified; Wind's self-published score copy; score measurement labels; orchestrator scheduler state and job lineage not verified; the `lake-brain-ledger-daily` scheduler is not reproducible from the repository.
4. **Future capability improvements:** Intelligence consuming the Fish/Wind assessments; versioned Lake/Water Temp state schemas; customer `/conditions` reading Brain outputs.
5. **Future scientific research:** field validation for every Brain; Water Temp protected truth; Lake hold-out H-C; Clarity customer-number validation.

## 6. Decisions and approvals (one list)

| # | Item | Kind | Recommendation |
|---|---|---|---|
| A-1 | Push `cortex/architecture-standardization-2026-10-20` (23 commits ahead of origin/main, incl. the Cortex activation commit) and open a **draft** PR to `main` | approval (push) | approve; CI then runs the Linux Swift build and every Python job |
| A-2 | Deploy order once merged: brain-jobs image (Lake/Water Temp moved targets, D-9 strings, Lake fallback record), orchestrator image (Intelligence staging, retry gate, scorer isolation, D-8) | approval (deploy) | deploy to non-customer jobs only, with the usual lineage preflight |
| A-3 | Read-only production checks (job labels/lineage, scheduler states, IAM, deployed rules) | approval (production read) | approve before A-2 |
| D-A | Depth: rework the branch so runtime data is package/knowledge-release data, consume a Lake bindings contract instead of Swift source, move score proposals to the platform scorer | decision | approve a Depth certification session |
| D-B | Vegetation: move the evidence-file check to research tooling (or a knowledge release), then migrate | decision | approve a Vegetation certification session |
| D-C | D-14b shared non-customer Swift library | decision | approve as a separate Swift refactor (touches the customer target) |
| D-D | Score measurement labels and the Engine aggregate (Proposal A); Wind score copy (Proposal B) | decision + Sector Ops | approve Proposal B first (smaller); A after Ops agrees |
| D-E | Water Clarity C1 job in the control manifest job map | decision | allow MANUAL jobs in the map (adjust the cost-freeze invariant to "scheduled jobs are PAUSED") |
| D-F | Lake tooling move and data classification | decision | schedule with the Lake research lane |

## 7. Tested vs. intended

Tested: every row of §4. Intended but not executed: the Linux image build (CI), any production run, Ops rendering of the new optional fields (`sourceFallback`, evaluation `sourceObservationAt`), which are additive and need no Ops change to keep working.

## 8. Cortex gaps

Appended to `docs/cortex/CORTEX_GAPS.md`: the Kit cannot certify a Brain without a Publisher registration; P14 audits Python only; Kit mutation assumptions (fixed in the Engine harness, to be upstreamed); BR-05/BR-08 for Swift Brains (resolved here by in-package SwiftPM targets — the pack should say so); registered-but-branch-only Brains.

## 9. Next step

Approve **A-1**: push the branch and open a draft PR, so CI runs the Linux Swift build and every Python job on this branch.
