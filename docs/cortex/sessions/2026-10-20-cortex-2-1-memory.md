# Sector Engine — Cortex 2.1 adoption and coordinated eight-Brain completion — Session Record

```text
Standards: Rehtac Cortex 2.1.0 @ 0f9ee75 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/architecture-standardization-2026-10-20 (local, not pushed) · Start commit: af0548b8 · Date: 2026-10-20
```

This continues `2026-10-20-architecture-completion.md` on the same branch. Its 23 commits are preserved, and its ledger, gaps, checkpoint and navigation refresh were reused. `origin/main` is still `7dae7051`. Nothing was pushed, merged or deployed, nothing touched production Firebase, and no schedule, IAM, rules, rubric or score changed.

## 1. Scope

- **Request:** "Cortex 2.1 adoption & coordinated eight-Brain completion". It asks for:
  - adopting Cortex 2.1.0;
  - permanent Brain memory architecture: research, then approval, then a versioned release, then runtime;
  - the standing memory checks for all eight Brains;
  - finishing Depth and Vegetation;
  - verifying the six canonical Brains against 2.1;
  - architecture discovery;
  - a machine-readable engineering status for Sector Ops;
  - full verification and one consolidated report.
- **Inspected:**
  - every Brain runtime's knowledge loading: Fish `load_bundle`, Wind `ingest.load_config`, Clarity `load_catalog` and its overlay, Intelligence `run.py`, Lake `LakePresenceIndex.load` and `LakeSourceBindings`, the Water Temp runner;
  - deploy scripts, Dockerfiles and orchestrator staging;
  - the Kit lineage proof;
  - the Publisher lineage validator;
  - the CI workflows;
  - the Depth and Vegetation branches (read-only; Depth runtime dependencies mapped by a read-only agent);
  - Cortex 2.1 `brains.md` §5 and `PROJECT.md` §6–§7.
- **Not accessible:** production (deployed images, buckets, RTDB, schedulers, IAM), Sector Ops, Sector Pulse, Docker (not installed here) and Linux CI.

## 2. Cortex 2.1 adoption

- Ran `cortex.py consumer-config sector/engine --pin 0f9ee75`.
  - `CLAUDE.md` now has one Cortex section, pin `0f9ee75`, committed in `b5a766e4`.
  - The SessionStart hook is updated in the primary checkout's `.claude/settings.local.json`, and also in this worktree's own copy. Both are git-ignored and uncommitted.
- The session briefing after reload reports `Standards: Rehtac Cortex 2.1.0 @ 0f9ee75 (clean), pack sector/engine`.

## 3. Memory architecture implemented (local, isolated commits)

**Principle:** research teaches a Brain; approved persistent memory lets it operate on its own afterwards. The four stages stay separate:

1. **Research:** stays in `research/`. It is never read at runtime (Kit P17 and the standing gate).
2. **Approval:** recorded in each release's `approval` block. Today every Brain is `NOT_RECORDED`, because no named release approval exists (decision M-3).
3. **Versioned release:**
   - Brains whose knowledge already ships in the image get one manifest, `knowledge-release.json`. It records the release id, per-file sha256 and bytes, a release digest, the store, the owner and the approval status.
   - `tools/knowledge/build_release_manifest.py` writes and checks it. A content change requires a new release id.
   - Fish keeps its hash-verified private bundle. Lake keeps its fingerprinted presence release and compiled bindings.
4. **Runtime:**
   - The shared stdlib loader `sector_brain_platform.knowledge_release.load_release` verifies the manifest and every file before use.
   - Missing, unreadable, incompatible or tampered memory raises an error. The job refuses (exit 2, "REFUSED (nothing published)") and never falls back to research data, an unversioned file or a default.
   - The release id and digest go into the SHADOW Publisher artifact lineage (`knowledgeRelease`, `manifestRef`, `manifestSha256`), where Kit P09 checks them.

| Commit | Change | Class |
|---|---|---|
| `4ac482e6` | Shared loader + tests (13). Intelligence (`run.load_knowledge`, run summary, artifact lineage, 5 memory tests). Wind (`ingest.verified_release`; `load_config` verifies; Dockerfile COPY and staging; 5 memory tests; staged-image test). Orchestrator staging copies the manifest | **Decision-required (M-1)**, implemented locally at the request's explicit direction (items 3 and 5); deploy is gated |
| `78d55294` | Clarity: the catalog is read only after its release verifies; refusal on import; lineage; Dockerfile and staging; 4 memory tests; exact-listing gates updated | same (M-1) |
| `19e9824c` | Fish: a missing or corrupt pointer or artifact is now `BundleError` → exit 2 REFUSED instead of a traceback. Values and hashes are unchanged | **Decision-required (M-2)** (exit code 1 → 2; the orchestrator treats any nonzero exit as not published) |
| `1492f79b` | Additive optional `knowledge` block in `brain.schema.json`, declared by all six packages. Cross-Brain standing gate `tools/architecture/tests/test_knowledge_memory_standing.py`. Lake Swift memory tests (7) | Safe (tests; declaring existing stores) |
| `44ad7121` | Lake-owned contract `brains/lake/contracts/reviewed-lake-bindings-v1.json`, produced only by a Swift test from the compiled table, with a drift check. It gives Depth a replacement for parsing Lake's Swift source | Safe (additive contract check; no runtime change) |
| `80c0c20a` | `engineering-status-v1` schema, generator, report and tests. CI changes: the foundation workflow checks the releases and the report; Swift CI now triggers on `brains/lake/**` and `brains/water-temperature/**` (a coverage gap left by the earlier target move) | Safe (records, tests, CI coverage) |

Legacy RTDB outputs are unchanged. Adding release lineage to them is decision M-4.

## 4. Standing memory checks — results

These are the full matrix with evidence: `docs/cortex/COMPLIANCE.md` → "Standing memory checks" and `docs/cortex/engineering-status/inputs/memory-standing-checks.json`.

**Branch summary:**
- **Fish:** 5 PASS, 1 PARTIAL (approval).
- **Wind, Intelligence:** 4 PASS, 2 PARTIAL (lineage only in SHADOW artifacts; approval).
- **Clarity:** 3 PASS, 3 PARTIAL (also the polygon fallback).
- **Lake:** 4 PASS, 2 PARTIAL (FNV fingerprint; approval).
- **Water Temp:** 4 PASS, 2 NOT_APPLICABLE (no knowledge store).
- **Depth, Vegetation:** mostly FAIL (no package and no release on `main`).

**Production:**
- Graded from the code at the recorded deployed commit `7dae7051`, or NOT_VERIFIED.
- Wind, Clarity and Intelligence are FAIL for release identity and memory-unavailable until an approved deploy.
- Fish passes release identity (the hash chain is deployed). Its missing-memory behaviour is PARTIAL, because a missing pointer crashes instead of refusing.
- Lake is NOT_VERIFIED: its image is off-main lineage `a6622f99`.

## 5. Depth and Vegetation

### 5.1 What was found

From a read-only Depth agent and the extracted branch packages:

- **What runtime reads:**
  - Depth's runtime (`run.py --plan/--dry-run/--write`) reads only RTDB plus four package-data files:
    - `candidates.json` (1,063,166 B);
    - `claim_levels.json`;
    - `maturity_inputs.json` (research judgment);
    - `stage_area_curves.json` (382,035 B).
  - `docs/`, `research/`, the Lake Swift source and `orchestrate.py` are read only by the offline manifest builder and by 6 tests.
- **Failing tests:** the other 7 failing tests need the branch's `control.py` shadow-Brain support (`SHADOW_BRAINS`, `SHADOW_SLOTS`), which `main` does not have.
- **Scoring and maturity:** score proposals v1 and v2 are test-only and unratified. The runtime evaluates the research maturity rubric (`maturity.evaluate`) and publishes it as unofficial `research.maturity`.
- **Approvals and validation:**
  - **Approved:** the pilot shadow write (5 lakes), the control-plane shadow Brain (not deployed), orchestration preparation (not scheduling) and the Lake datum interface.
  - **No approval record:** the knowledge content itself (datum overrides, ratings, claim levels, maturity).
  - **Validation:** field validation has not started.
- **Developer paths:** `/Users/` paths sit in `datum_providers.json` (6 evidence URLs, not read by code) and in `twdb_prereg.json` (free text, hash-pinned by a test).
- **Vegetation:** the runtime maturity and evidence check reads about 25 research documents. Branch tests: 108 pass, 2 fail.
- **Branches:** neither branch merges cleanly. Depth conflicts in 4 files (CI workflow, orchestrator, orchestrator tests, `control.py`); Vegetation in 1 (CI workflow). Merging either would also bring 59 `research/depth` files or about 100 `docs/brains` research files into this lineage.

### 5.2 Why the migration stopped (genuine blocker)

Moving their operational knowledge into a versioned release is **gated** by PROJECT §7:
- "Promoting research into a production knowledge or model release … needs scientific validation approval plus your approval";
- "duplicating historical datasets".

Packaging releases into images is decision-required (§6). Without the knowledge, a code-only `brains/depth` or `brains/vegetation` package would not run, so it was not created. Both Brains stay branch-only and PARKED/SHADOW. Their branches and worktrees are untouched.

**Done here:** the Lake-owned `reviewed-lake-bindings-v1` contract, the first prerequisite of decision D-A.

### 5.3 Migration plan once G-1 is approved (decisions D-A, D-B)

**Depth → `brains/depth/`:**
- `runtime/`: `run.py`; `depth_brain/{contract,state,publish,writer,ops_summary,shift,datum,zones,rating,evidence}.py`; and a release over `candidates.json`, `claim_levels.json` and `stage_area_curves.json`.
- Move `load_lake_states` and `DEFAULT_MANIFEST` out of `__main__`, so the runtime no longer imports `candidates` or `proposals`.
- Move to `research/tools/`: `maturity.py` (with `maturity_inputs.json`), `candidates.py`, `proposals.py`, `field_validation.py`, `score_v1_proposal.py`, `score_v2_proposal.py` and the CLI.
- **Read nothing at runtime:** `research/depth`, `docs/brains/depth/data`, `inputs/`, `proposals/`.
- **Contract changes:**
  - `candidates.reviewed_lake_ids` reads `brains/lake/contracts/reviewed-lake-bindings-v1.json`;
  - the orchestrator-source test becomes a Depth execution declaration;
  - the 7 control tests need the shadow support in `control.py`, ported with the control-plane owner.
- Sanitize the two `/Users/` strings; this needs a new proposal hash for `twdb_prereg.json`.
- Kit V1 adapter and SHADOW Publisher registration; lock the id in `stable_brain_ids.json`; lifecycle stays PROFILED/SHADOW.

**Vegetation → `brains/vegetation/`:**
- Move the maturity and evidence checks to research tooling.
- Put package data under a release.
- Register with the Kit and Publisher (SHADOW); lock the id; lifecycle stays SHADOW.

## 6. Six canonical Brains against 2.1 (no restructuring)

**Structural (Kit V1):**
- Fish, Wind, Clarity and Intelligence pass P01–P19. Wind, Clarity and Intelligence now do so with their real release lineage instead of NONE.
- Lake and Water Temp pass P01–P13 and P15–P19. P14 is NOT_APPLICABLE (Swift writes).
- All six publication contracts match the Publisher registry (`describe_contract --check`).

**Swift-specific checks for Lake and Water Temp:**
- **Write ownership:** `BrainOwnership.check`, plus write-set fixture tests that re-run the runner and compare with the committed fixture.
- **Runtime knowledge:** compiled bindings with a version, and a presence release verified on load; Water Temp has no store.
- **Developer machine:** the standing scan covers `Sources/SectorEngine` and both Swift runtimes.
- **Production:** the Lake image's lineage is off-main, so it is NOT_VERIFIED.

## 7. Firebase and memory dependency map

| Brain | Approved memory (store) | Operational state | RTDB reads | RTDB writes (legacy, unchanged) |
|---|---|---|---|---|
| Fish | private bundle `gs://sector-biology-private/biology/v1` (hash chain) | — | `brains/biological-state` (plan) | `lakes/*/states/biology`, `brains/biological-state` |
| Wind | image release (`lakes.json`, validation evidence) | forecast archive (own bucket) | — (`GET /lakes`) | `lakes/*/states/wind`, registry, health |
| Clarity | image release (catalog) + optional private overlay | — | — (Engine API, `sector-lake-surface` bucket) | `lakes/*/states/waterClarity`, registry |
| Intelligence | image release (catalog) | — | published state of 5 Brains, `GET /lakes` | `lakes/*/states/intelligence` (pilots), `brains/sector-intelligence` |
| Lake | compiled bindings + presence release `gs://sector-lake-brain` | level baselines (same bucket) | own state, fleet | `lakes/*/states/lake`, `lakes/*/brain`, `speciesPresence`, fleet |
| Water Temp | none (compiled model) | — | own state | `lakes/*/states/waterTemp`, fleet |
| Depth (branch) | package data, no release | — | `lakeFleet`, `lakes/*/states/lake`, `brains/depth`, `activity` | shadow: `lakes/*/states/depth`, snapshots, fleet, `brains/depth`, `validation/depth`, health, activity |
| Vegetation (branch) | package data, no release | — | not re-mapped this session | shadow only |

No Brain keeps knowledge in RTDB.

## 8. Recovery behaviour

**Restart or redeploy:**
- Image releases are immutable per revision and re-verified on every run.
- Fish and Lake re-read and re-verify bucket memory on every run.
- No Brain keeps local or developer-machine state.

**Missing or corrupt memory:**
- Fish, Wind, Clarity and Intelligence refuse; nothing is published.
- Lake writes no presence and records `presenceError`. Level state still publishes, because it comes from live sources and compiled bindings.
- Water Temp is not applicable.

None of this was exercised against production (NOT_VERIFIED, approval A-3).

## 9. Verification (at `44ad7121`; the report generator and tests at `80c0c20a`)

**Python suites (per CI layout):**
- Platform: 735.
- Orchestrator: 46.
- Scores: 35.
- Other jobs: lake-surface-dispatch 11, water-temp-tva-archive 14, lake-brain bindings 13, ledger 23, validation 70, review 24, lake-geometry 22.
- Brains:
  - Fish: 400 passed, 2 skipped.
  - Lake: 49 passed, 4 skipped.
  - Intelligence: 96.
  - Clarity: 131.
  - Water Temp: 50 passed, 4 skipped.
  - Wind: 220 (16 network tests deselected).
- Tools and gates:
  - Kit 32.
  - Architecture 112, then 119 after the status tests.
  - Verification 15.
  - Wind package with dependencies required: 7.

**Swift:** `swift build --build-tests` OK; `swift test` ran 325 XCTest tests with 0 failures (macOS arm64).

**Other checks:**
- `describe_contract --check`: 6 of 6 OK.
- Knowledge manifests `--check`: 3 of 3 OK.
- `--stage-only`: Wind and Clarity contexts include the manifest.
- **Orchestrator staging:** the staging block was extracted to scratch and run without gcloud. The staged Intelligence verifies its release in a clean environment. `deploy-job.sh` itself was not run, because it calls gcloud first.
- Architecture report: exit 0 (report-only).

**Not run:**
- `docker build`: Docker is not installed. The COPY sets were checked through staging instead.
- Linux CI: needs an approved push. Note that Swift CI runs on `macos-15`; Linux Swift is only exercised by the image build.

No test contacted production, private research or live data:
- The memory tests use synthetic bundles, temporary copies and `--offline`.
- The clean-environment subprocesses run with no HOME and a temporary working directory.

## 10. Cortex gaps

`CORTEX_GAPS.md`, CG-2.1-1 … CG-2.1-4:
- digest strength;
- the safe/decision boundary for verifying already-packaged files;
- the approval-record format and the compiled-knowledge profile;
- the status schema and production evidence levels.

Cortex was not modified.

## 11. Decisions and approvals (one list)

This is the same list as `docs/cortex/engineering-status/inputs/decisions.json`. The earlier D-C … D-F carry over.

| Id | Item | Class | Recommendation |
|---|---|---|---|
| A-1 | Push this branch (31 commits ahead of `origin/main`, incl. this record) and open a **draft** PR | approval | approve; Linux CI then runs |
| A-2 | Deploy (brain-jobs, orchestrator, wind-hourly, water-clarity-brain) after merge | approval | lineage preflight; Lake stays on its own lineage |
| A-3 | Read-only production checks | approval | before A-2 |
| M-1 | Adopt packaged releases (verify on load, refuse when missing or tampered; manifest in images) | decision | accept; takes effect only on deploy |
| M-2 | Fish exit 2 REFUSED on missing memory | decision | accept |
| M-3 | Named approver and approval record per release | decision | name approvers |
| M-4 | Release lineage in legacy RTDB outputs | decision | keep it in SHADOW artifacts until the Publisher cutover |
| M-5 | Clarity private overlay as a digest-verified private release | decision | at next overlay update |
| M-6 | Remove Clarity's repo-relative polygon fallback | decision | in a Clarity session |
| M-7 | Lake presence fingerprint FNV-1a → sha256 | decision | with the Lake owner, on the Lake lineage |
| M-8 | Digest-verify scorer rubrics staged from `docs/brains/scoring` (without moving them) | decision | add a manifest |
| G-1 | Promote Depth and Vegetation knowledge into releases | **gated** | scientific validation + owner approval |
| D-A / D-B | Depth / Vegetation migration sessions (§5.3) | decision | after G-1 |
| O-1 | Ops read interface for `engineering-status-v1` | decision | read the committed file at a pinned commit |
