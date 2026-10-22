# Sector Engine architecture standardization — all eight Brains — Session Record

```text
Standards: Rehtac Cortex 2.0.1 @ fc56557 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/architecture-standardization-2026-10-20 · Start commit: 8a75b01b · Date: 2026-10-20
```

Start commit `8a75b01b` = `origin/main` `7dae7051` + the local, unpushed Cortex activation commit (`cortex/activation-2026-10-20`). The work branch was created from it so the records folder exists; it therefore carries that activation commit too.

## 1. Scope

- **Request and mode:** "standardize all eight Sector Engine Brains and their shared architecture … make every authorized structural correction … preserve existing science, scoring and production behavior … do not push, merge, or deploy." Mission `sector-engine-architecture`, **Standardize** mode (Stages A–F), whole platform.
- **Inspected:** the Brain registries (`tools/architecture/stable_brain_ids.json`, `control_manifest.json`, `jobs.py` MANIFEST, `ownership.py`/`keys.py`, `brains/*/brain.json`, `contracts/conformance/ownership.json`, `jobs/sector-intelligence-brain/catalog.json`); the three canonical packages `brains/{fish,wind,water-clarity}`; Lake (`Sources/SectorEngine/LakeBrain/`, `Sources/LakeBrainJob/`, `jobs/lake-brain/`); Water Temp (`Sources/SectorEngine/Brain/WaterTemperatureBrain*.swift`, `Sources/SectorEngine/WaterTemp/`, `Sources/WaterTempBrainJob/`, `jobs/water-temp-brain/`); Intelligence (`jobs/sector-intelligence-brain/`); Depth and Vegetation (absent on `main`; branches `feat/depth-brain-foundation`, `feat/vegetation-brain-foundation` read with `git ls-tree`/`git show` only); orchestrator (`jobs/brain-orchestrator/`, `orchestration.py`, `orchestrator.py`, `control*.py`); scorer (`jobs/brain-scores/`, `scoring.py`, `docs/brains/scoring/`); Publisher (`publisher/`, `publisher_live/`); `platform/security/`, `platform/registries/`; Brain Factory docs and `brains/_template/`; Certification Kit V1; `tools/architecture`; CI workflows; `Package.swift`. Four read-only sub-agents gathered per-Brain evidence; every claim used for a change was re-read before editing.
- **Scope expansion:** none beyond the request. The Intelligence Brain was checked for its boundary (BR-04) only; no functionality was added.
- **Not inspected / not accessible:** production (job labels, scheduler states, deployed images, RTDB contents, IAM, deployed rules): no approved production access. Sector Ops, Sector Pulse and mobile clients: separate projects. The Wind publish `--dry-run` command now documented in `brains/wind/README.md` was **not executed**, because it reads the public production Engine `GET /lakes`.

### Stage A facts

- Remote `Sector-Bowfishing/Sector_Engine`, default branch `main`, worktree clean; 80 sibling worktrees (81 including this one) (branches, not alternate implementations). Open PRs at start: #39, #36 (draft), #17, #16, #15, #14, #13, #12, #11, #10, #9; none covers this mission.
- Drift: see the navigation refresh (`navigation-refresh/2026-10-20-architecture-all-brains.md`): 5 files changed since the snapshot, 8 Brains match, 0 items to verify.
- Brain ID sets by registry: stable ids **6**, control manifest **8**, `ownership.BRAINS` **8**, JM owners **8** (incl. `brain-platform`, `sector-engine`), JM `brainDependencies` **5**, `brain.json` **3** (obs.02 still true).
- Brain Factory: `docs/architecture/certification/audit-1/BRAIN_FACTORY_V1.md`, `brains/_template/`, `docs/architecture/repository-audit-v1/STANDARD_BRAIN_PACKAGE_V1.md`. Certification Kit V1: `tools/brain_certification/brain_cert_kit/proofs.py` (P01–P19), adopted by Fish, Wind, Clarity through `brains/<dir>/tests/test_*_kit_certification.py`.

## 2. Findings

The compliance matrix, per-Brain evidence records and structural status are in **`docs/cortex/COMPLIANCE.md`** (all BR, PL and SC rows × 8 Brains + Platform). Headline findings:

| ID | Finding | Status | Evidence |
|---|---|---|---|
| F-01 | Lake, Water Temp, Intelligence have no canonical package; the Engine gate forbids `brain.json` before migration | BR-05/07/19 FAIL/PARTIAL | `tools/architecture/tests/test_foundation.py` `test_real_repo_registers_only_migrated_brains` |
| F-02 | Lake, Water Temp, Intelligence had no operating contract / stated bowfishing purpose | BR-01/06 FAIL → **PASS** | fixed `e622a10f` |
| F-03 | Recommendation guard existed only on Intelligence-facing assessments, not ordinary publications | BR-03 PARTIAL → **PASS** (Fish, Wind, Clarity) | fixed `da1e43df` |
| F-04 | Stale structural docs: `platform/publisher/README.md`, `platform/registries/*`, `brains/README.md`, `_template/README.md`, Wind contract §9 and research README, Fish/Clarity README purpose, scorer/planner docstrings | obs.08 PARTIAL → resolved for these files | `0af34d09`, `4cffb28b` |
| F-05 | Intelligence docs say it "evaluates nothing"; since `568d6bb1` it publishes 5 pilot evaluations | BR-20 PARTIAL (docs fixed; `catalog.json` remains, D-8) | `b0452ce1` |
| F-06 | Lake/Water Temp docs describe a deployment state that no longer holds | fixed (docs) | `f900ec52` |
| F-07 | Declared-vs-observed conflicts: Wind `staleHours 6` vs 1.5 (obs.03); Clarity CM entry describes C2; Fish trigger; JM input omissions; Water Temp declares an unread archive; Intelligence REQUIRED vs OPTIONAL | BR-09 FAIL/PARTIAL | D-2 |
| F-08 | Lake CWMS→USGS fallback not reported as degraded; capability/datum from the binding | PL-03 PARTIAL | `LakeLevelClassifier.swift:148-155,181,190,211-218`; D-4 |
| F-09 | Orchestrator: scorer timeout uncaught; retry/backoff only on legacy path; manifest timeouts unread | PL-02 PARTIAL | `orchestrate.py:221,271,334`; D-7 |
| F-10 | One score type for different measurements; Wind self-publishes a stale score copy | SC-01 FAIL, SC-04 PARTIAL | obs.09, obs.14; D-5, D-6 |
| F-11 | Publisher LIVE implemented, not wired; rules/IAM unverified | PL-07 PARTIAL, PL-08 NOT_VERIFIED | obs.04 |
| F-12 | Depth, Vegetation registered with no code on `main`; branches 178 commits behind | BR-02 PARTIAL, BR-05/08/18/19 FAIL | D-11 |
| F-13 | `verify.01` resolved: Intelligence 33/33 under pytest; "32" is `unittest discover` missing one pytest function | resolved | `python -m pytest -q` → 33 passed |
| F-14 | `docs/brains/LAKE_BRAIN_INTEGRATION.md` §8 names a real lake's species-presence state in a public file | BR-12 PARTIAL | D-13 |
| F-15 | Tracked bytecode `scripts/hydrology/__pycache__/*.pyc` (2 files) | out of Brain scope; recorded only | `git ls-files \| grep __pycache__` |

### Architecture decision record (ADR-CX-2026-10-20)

- **Context.** Cortex BR-05 wants every Brain in a canonical `brains/<dir>/` package. The Engine's own Brain Factory treats packaging as **migration** (runtime moves with it) and its architecture gate fails if a `brain.json` exists for an unmigrated Brain. Lake and Water Temp are Swift inside the customer library target; Intelligence is staged into the orchestrator image from `jobs/sector-intelligence-brain/`.
- **Decision.** (1) Do not create `brains/lake/`, `brains/water-temperature/`, `brains/sector-intelligence/` or any `brain.json` in this session; migration is decision D-1. (2) Standardize the unmigrated Brains through the Engine's documented pre-migration convention: an operating contract at `docs/architecture/certification/<dir>/BRAIN_OPERATING_CONTRACT.md`, which moves with the Brain at migration, and pin it with an architecture test. (3) Fix shared-platform documentation once. (4) Add boundary tests only where they describe existing behaviour. (5) Change no runtime code, published output, manifest value, rubric file, schedule or deploy script.
- **Consequences.** BR-01/BR-06 now pass for all six Brains on `main`; BR-05/BR-07/BR-19 stay open for three Brains until D-1 is decided. Nothing published changes.

## 3. Plan and changes made

| Correction | Class | Finding IDs | Files | Commit |
|---|---|---|---|---|
| CX-P1 Correct stale Publisher/registry READMEs and scorer/planner docstrings | safe | F-04 (obs.08) | `platform/publisher/README.md`, `platform/registries/README.md`, `platform/registries/species/README.md`, `jobs/brain-scores/score_brains.py` (docstring), `jobs/brain_platform/sector_brain_platform/{orchestrator,wind_score_refresh}.py` (docstrings) | `0af34d09` |
| CX-I1 Record the Intelligence pilot on `main`; mark the 2026-10-12 closeout historical | safe | F-05, BR-20 | `jobs/sector-intelligence-brain/README.md`, `docs/brains/SECTOR_INTELLIGENCE_BRAIN_{INTEGRATION,STATUS}.md` | `b0452ce1` |
| CX-B1 Correct stale package READMEs; state the bowfisher decision for Fish and Clarity | safe | F-04, BR-01 | `brains/README.md`, `brains/_template/README.md`, `brains/{fish,water-clarity,wind}/README.md`, `brains/wind/BRAIN_OPERATING_CONTRACT.md` (§9 stale sentence), `brains/wind/research/README.md` | `4cffb28b` |
| CX-L1/CX-W1 Record Lake and Water Temp deployment state; add `jobs/water-temp-brain/README.md` | safe | F-06 | `docs/brains/LAKE_BRAIN_INTEGRATION.md`, `docs/brains/WATER_TEMP_BRAIN.md`, `jobs/lake-brain/ledger/README.md`, `jobs/water-temp-brain/README.md` | `f900ec52` |
| CX-OC1 Operating contracts for Lake, Water Temp, Intelligence + guard test | safe | F-01, F-02 (BR-01, BR-06) | `docs/architecture/certification/{lake,water-temperature,sector-intelligence}/BRAIN_OPERATING_CONTRACT.md`, `tools/architecture/tests/test_unmigrated_brain_contracts.py` | `e622a10f` |
| CX-T1 Publication specialist-boundary tests | safe | F-03 (BR-03) | `brains/{fish,wind,water-clarity}/tests/test_publication_specialist_boundary.py` | `da1e43df` |
| CX-T2 Explicit assertions instead of silently skippable ones | safe | test quality (BR-16) | `jobs/sector-intelligence-brain/tests/test_evaluation.py` | `5155e769` |
| Records | safe | — | `docs/cortex/COMPLIANCE.md`, this record, `navigation-refresh/2026-10-20-architecture-all-brains.md`, `CORTEX_GAPS.md` | records commit |

Every correction is documentation or tests. Risk: low. Rollback: `git revert <commit>`. No runtime module changed except docstrings in three Python files (verified by `py_compile` and the full suites).

## 4. Verification

| Check | Command | Before (baseline, HEAD `8a75b01b`) | After (work branch) |
|---|---|---|---|
| Platform | `cd jobs/brain_platform && python -m pytest -q` (likewise orchestrator, scores) | 715 / 42 / 35 passed | 715 / 42 / 35 passed |
| Legacy suites | `jobs/{lake-surface-dispatch,sector-intelligence-brain,water-temp-tva-archive,lake-brain/bindings,lake-brain/ledger,lake-brain/validation,lake-brain/review,lake-geometry}` | 11 / 33 / 14 / 13 / 23 / 70 / 24 / 22 passed | same |
| Fish | `cd brains/fish && python -m pytest -q` | 393 passed, 2 skipped | 395 passed, 2 skipped (+2 new) |
| Wind | `cd brains/wind && python -m pytest -q` | 213 passed, 16 deselected | 215 passed, 16 deselected (+2) |
| Water Clarity | `cd brains/water-clarity && python -m pytest -q` | 125 passed | 127 passed (+2) |
| Certification Kit self-tests | `python -m pytest -q tools/brain_certification` | 32 passed | 32 passed |
| Kit V1 per Brain | `pytest -rA tests/test_<b>_kit_certification.py` | — | Fish 51, Wind 51, Clarity 52 cases: **P01–P19 all PASS** for each |
| Architecture gates | `python -m pytest -q tools/architecture` | 87 passed | 94 passed (+7 new) |
| Verification gates | `python -m pytest -q verification` | 14 passed | 14 passed |
| Wind package (deps required) | `SECTOR_REQUIRE_WIND_DEPS=1 python -m pytest -q verification/integration/test_wind_package.py` | 6 passed | 6 passed |
| Architecture report | `python tools/architecture/report.py` and `--legacy --baseline` | 17 invariants (inv 8: 5 known); 20 known, 0 new, 0 resolved | identical |
| Publication contracts | `PYTHONPATH=jobs/brain_platform python brains/<b>/contracts/describe_contract.py --check` | match ×3 | match ×3 |
| Swift | `swift build && swift test` | build OK; 313 XCTests, 0 failures | build OK; 313, 0 failures (no Swift file changed) |
| Guard test fails when it should | removed a section heading from the Lake contract, ran the new test, restored | — | 1 failed as expected, then 7 passed |
| Output equivalence | no runtime logic changed; describe `--check`, golden/byte-identical science tests (`test_fish_certification.py:272`, Clarity `tests/golden/`) and Kit P07/P08 pass unchanged | — | unchanged |
| Diff hygiene | `git status`, `git diff --stat 8a75b01b..HEAD` | — | clean tree; only the files in §3 |

Environment: Python 3.12.8 venv in the session scratchpad with CI's dependency set (`pytest numpy requests google-cloud-storage`, Wind `runtime/requirements.txt` + `research/tools/requirements.txt`, `jobs/lake-geometry/requirements.txt`); Swift as installed. Note: collecting `tools/architecture tools/brain_certification verification` in **one** pytest invocation errors at collection (3 errors, conftest/module-name collisions), before and after; CI runs them separately and so did this record.

**Not run:** the Wind publish `--dry-run` (reads production Engine `/lakes`); any orchestrator, Publisher or scorer run against production (needs approval); `WaterTempBrainJob`/`LakeBrainJob --dry-run` (fetch live providers; no Swift changed).

## 5. Open items

### Current release blockers
None identified. No named release was shown to depend on any open item (no mobile or customer release depends on Brain outputs: the customer Engine reads no Brain output, obs.05).

### Structural certification blockers
- Lake, Water Temp, Intelligence: no canonical package, no `brain.json`, Kit V1 not adopted (D-1).
- Depth, Vegetation: no code on `main` (D-11).
- BR-09 conflicts: Wind (FAIL), Clarity (FAIL), Fish/Lake/Water Temp/Intelligence (PARTIAL) (D-2).
- Brain identity spread across ≥ 6 hand-kept registries (D-3).

### Production integration blockers
- Publisher LIVE not wired; every Brain writes RTDB directly (obs.04); no publication contracts for Lake, Water Temp, Intelligence.
- Rules and IAM unverified; writer SA holds a project-wide database admin role (PL-08, verify.02).
- Wind stale self-published score copy (D-5); one score type for different measurements (D-6).
- Orchestrator retry/timeout semantics (D-7); Lake fallback reporting (D-4).
- `lake-brain-ledger-daily` scheduler not reproducible from the repository (obs.11).

### Future capability improvements
- Intelligence consuming `fish-biological-assessment-v1` / `wind-exposure-assessment-v1`; versioned JSON output contracts for Lake, Water Temp, Intelligence; Swift boundary tests for Lake and Water Temp; customer `/conditions` reading Brain outputs (`customerIntegrationMode`); generated Brain registry.

### Future scientific research
- Field validation for every Brain; Water Temp protected truth (Level-4 gate); Lake hold-out H-C failure; Clarity validation of the customer number.

## 6. Decisions required and approvals

### Decisions required (options, recommendation)
| # | Item | Options | Recommendation | Evidence |
|---|---|---|---|---|
| D-1 | Canonical packages for Lake, Water Temp, Intelligence | (a) migrate Intelligence first (Python, self-contained; move to `brains/sector-intelligence/`, add `brain.json`, adopt Kit V1, update orchestrator image staging); (b) Lake/Water Temp later with a SwiftPM target split; (c) leave as is with the new operating contracts | (a) as its own certification session, then (b) after a target-split decision | F-01; Engine gate; `jobs/brain-orchestrator/deploy-job.sh` stages SI |
| D-2 | Declared-value conflicts | per item: Wind `brain.json` `staleHours` 6 → 1.5; Fish `brain.json` trigger vs CM `INPUT_DRIVEN`; Clarity CM `executionTarget` (C2) vs the C1 job; JM inputs add `GET /lakes` (Wind, Clarity), Lake's five fetchers, drop Water Temp's unread TVA archive; Intelligence `REQUIRED` vs `OPTIONAL` | align declarations to observed runtime in one reviewed change per Brain (Wind's runtime already uses 90 min) | COMPLIANCE BR-09 |
| D-3 | Brain identity registries (8/8/6/5/3) | keep hand-kept; or generate from `brain.json` + a registry file | defer to the planned generated registry; do not hand-edit now | obs.02 |
| D-4 | Lake fallback honesty | report fresh-fallback as degraded-but-usable, take capability/datum from the selected source, keep the primary error text; or keep flags only | adopt PL-03 semantics; review with `fix/lake-brain-cwms-retry` | F-08 |
| D-5 | Wind `/brains/wind/scores` stale copy (3.1 vs 3.3) | retire the copy; or keep with a "not canonical" label | retire after confirming no Ops reader (cross-repo) | obs.14 |
| D-6 | One score type for different measurements | distinct score types per measurement; or document | distinct types (contract change for Ops; gated) | obs.09, SC-01 |
| D-7 | Orchestrator execution safety | catch scorer timeout; read CM `timeoutSeconds`; wire bounded retry; or keep | catch the scorer timeout first (small); then decide retry policy | F-09 |
| D-8 | Intelligence output inconsistencies | bump `catalog.json` (blockers, "evaluates nothing", method text), add `brainVersion`, evaluation freshness from input times, degrade on read failure | one reviewed catalog bump + small code fix with tests | F-05, COMPLIANCE BR-04/17/20 |
| D-9 | Water Temp published `schedule` string | change to orchestrator/when-stale; or leave | change (published value, trivial) | `WaterTemperatureBrain.swift:37` |
| D-10 | `jobs.py` clarity `purpose` "(not on main)" and `sourceLineage` (published to `/jobs`) | correct strings; or leave | correct | `jobs.py:93-95,112` |
| D-11 | Depth and Vegetation | bring each branch to `main` as a canonical package (separate certification sessions); or deregister from CM until then | certification sessions; also fix the vague CM Depth note and the branch's `/Users/` data paths | F-12 |
| D-12 | Stale descriptive strings inside runtime-loaded scoring JSON (`engine-score-v1.json:10` path, `frozen-scores.json:2,28,31`) | edit (gated: rubric files); or leave | approve a text-only correction with no value change | platform evidence |
| D-13 | Real species-presence state for a named lake in `LAKE_BRAIN_INTEGRATION.md` §8 (public repo) | replace with a synthetic example; or keep | replace (history still contains it) | F-14 |
| D-14 | Lake and Water Temp in the customer `SectorEngine` library target | split targets; or keep | decide with D-1(b) | obs.12 |

### Approvals (gated)
| # | Action | Target, effect, rollback, risk | Granted (scope) / pending |
|---|---|---|---|
| G-1 | Push `cortex/architecture-standardization-2026-10-20` (it contains the activation commit) and open a **draft** PR to `main` | GitHub `Sector-Bowfishing/Sector_Engine`; makes the branch reviewable; rollback: close PR / delete remote branch; risk: low (docs + tests) | pending |
| G-2 | Text-only correction of D-12 strings in `docs/brains/scoring/*.json` | runtime-loaded rubric files; no numeric change; rollback: revert; risk: low but rubric-gated | pending |
| G-3 | Read-only production checks (job labels/lineage, scheduler states, IAM, deployed rules) to close verify.02/03 and obs.07 | production read only; no writes | pending |

No approval was requested or used during the session. Nothing was pushed, merged or deployed.

## 7. Tested vs. intended

- **Tested:** every suite and gate in §4, the per-proof Kit V1 results, the publication contract checks, the guard test's failure mode.
- **Only documented, not executed:** the Wind publish `--dry-run` command (module docstring usage); the Water Temp and Lake `--dry-run` commands (existing documented usage).
- **Not claimed:** no Brain is newly certified, validated, deployed, published or customer-visible. The new operating contracts are DRAFT descriptions; the Lake, Water Temp and Intelligence structural certification remains open.

## 8. Cortex gaps

Five entries appended to `docs/cortex/CORTEX_GAPS.md`: the brain.json safe/gated/Engine-gate conflict; Swift Brains vs BR-05/BR-08; no shared BR-03 vocabulary; grading registered Brains with no code on `main`; runtime-only SC-08 values. Navigation differences are in `navigation-refresh/2026-10-20-architecture-all-brains.md` (16 rows).

## 9. Next step

Decide **D-1(a)**: authorize an Intelligence Brain migration and certification session (move to `brains/sector-intelligence/`, `brain.json`, Kit V1 adoption), which also absorbs D-8.
