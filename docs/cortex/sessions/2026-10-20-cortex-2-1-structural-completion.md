# Sector Engine — Cortex 2.1 all-Brain structural completion — Session Record

```text
Standards: Rehtac Cortex 2.1.0 @ 0f9ee75 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/architecture-standardization-2026-10-20 · Draft PR #40 (pushed; not merged) · Start commit: 2c794d39 · Date: 2026-10-20
```

This continues `2026-10-20-cortex-2-1-memory.md` on the same branch. The user authorized pushing this branch and opening a **draft** PR, for this branch and this assignment only. Nothing was merged or deployed. No production Firebase write, IAM, rules, schedule, live publication, rubric or score changed. Cortex was not modified.

## 1. Scope

- **Request:** "Cortex 2.1 all-Brain structural completion". The priorities were:
  - finish Depth and Vegetation in canonical packages;
  - shared architecture: identity, execution contracts, Swift boundaries, memory, scoring authority, Orchestrator and Publisher boundaries;
  - seven separate status layers per Brain;
  - push, open a draft PR and run GitHub CI including Linux Swift, fixing failures introduced by this work;
  - keep `engineering-status.json` current.
- **Inspected:**
  - the Depth and Vegetation branches, with read-only dependency maps produced by two agents;
  - the current platform: control plane, Publisher registry, ownership, dependency graph and health plane;
  - the Kit V1 proofs and harness;
  - the Swift stores and write sites, and the Swift package-access surface;
  - the CI workflows and the Dockerfiles.
- **Not accessible:** production, Sector Ops, Sector Pulse, and Docker on this Mac. Image builds run in CI instead.

## 2. Structural results (all eight Brains)

| Brain | Canonical package | Kit V1 (recorded run, `inputs/certification.json`) | Domain + memory tests |
|---|---|---|---|
| Fish `biological-state` | `brains/fish` | P01–P19 PASS; 30 mutations defeat their proofs | 400 (+2 skipped) |
| Wind `wind` | `brains/wind` | P01–P19 PASS; 30 mutations | 220 (16 network-deselected) |
| Water Clarity `water-clarity` | `brains/water-clarity` | P01–P19 PASS; 31 mutations | 131 |
| Sector Intelligence `sector-intelligence` | `brains/sector-intelligence` | P01–P19 PASS; 30 mutations | 96 |
| Lake `lake-brain` | `brains/lake` (Swift targets) | P01–P13, P15–P19 PASS. P14 NOT_APPLICABLE (Python-only proof); the Swift equivalent gate passes | Python 49 (+4 skipped); Swift in the full run |
| Water Temp `water-temp` | `brains/water-temperature` (Swift targets) | same as Lake | Python 50 (+4 skipped); Swift in the full run |
| **Depth `depth`** | **`brains/depth` (new)** | **P01–P19 PASS; 30 mutations** | 277 (+9 research-data skips); **298/298 pass with the research snapshot** |
| **Vegetation `vegetation`** | **`brains/vegetation` (new)** | **P01–P19 PASS; 30 mutations** | 171 (the branch's 2 failures are fixed) |

## 3. Depth and Vegetation: what was done

**Both Brains:**
- Migrated by reconciling files against current code, not by merging branches. The source branches and their worktrees are untouched.

**Depth (`ec5db259`):**
- **Runtime:** `runtime/run.py` is the only publish entry. Package `depth_brain` covers contract, shift, datum, zones, rating, evidence, state, publish, writer, ops_summary, fleet metrics, inputs, the knowledge loader and the artifact builder.
- **Knowledge release:** `runtime/knowledge/` holds `candidates.json` (compacted to 830 KB, within budget), `claim_levels.json` and `stage_area_curves.json`, under `knowledge-release.json`. Release `depth-knowledge-candidate-2026-10-20.1`, approval NOT_RECORDED.
- **Abstention:**
  - Without an APPROVED release, `--plan` reports SKIP/`BLOCKED_AWAITING_APPROVED_RELEASE`.
  - `--write` refuses (exit 2), even with `DEPTH_SHADOW_WRITE_APPROVED=1`.
  - `--dry-run` requires `--allow-unapproved-release` and never writes.
  - A missing or tampered release refuses the run.
- **Removed couplings:**
  - **Docs:** runtime reads of `docs/` are gone.
  - **Lake's Swift source:** the manifest builder now reads Lake's `reviewed-lake-bindings-v1` contract. The rebuilt manifest is byte-equal to the released one, proven with the research snapshot.
  - **Orchestrator source:** that test now asserts the control-manifest declaration instead.
  - **Developer-machine paths:** the `/Users/` paths sit only in research data, which stays outside the repo (`$DEPTH_RESEARCH_DATA`).
- **Scoring:**
  - The research maturity rubric and score proposals v1/v2 moved to `research/tools/depth_research`.
  - The runtime publishes `research.maturity = OFFLINE_RESEARCH_ONLY`, no number.
  - The research CLI's `publish --rtdb` route was removed.
- **Platform and registration:**
  - Control-plane SHADOW support ported (`d9653754`): visible, never scored, never in a roll-up.
  - Publisher SHADOW registration `depth-publication-v1`.
  - Lake lists Depth as an authorized consumer.
  - The id is locked.

**Vegetation (`f5cf9790`):**
- **Runtime and release:** `runtime/run.py` offers `--plan` and `--dry-run`; there is still no live writer. The release `vegetation-knowledge-candidate-2026-10-20.1` covers `fleet.json` and the two agency datasets.
- **Map correction:** the agent's map corrected an earlier finding. The runtime never read research documents (the evidence check ran only in tests). What it did do was publish the research maturity score; that is now removed. The ledger and the matrix are corrected.
- **Moved to `research/tools`:** maturity, validation gates, holdout guard, fleet builder, agency builders and shared-pass harnesses.
- **Tests:** the preregistration is carried as a frozen research record, so its gate test runs. The two branch failures are fixed.
- **Platform:**
  - Publisher SHADOW registration with no activity family (Vegetation writes no events).
  - Lake lists Vegetation as an OPTIONAL consumer (the control manifest's provisional edge).
  - The id is locked.

**Awaiting scientific release approval (gated G-1), not structural:** promotion of either candidate release to APPROVED.

## 4. Shared architecture

- **A. Identity:**
  - `stable_brain_ids.json` (8) = packages (8) = control manifest (8) = `keys.BRAINS` = Swift mirror.
  - No unmigrated Brain remains.
  - brain.json and control-manifest lifecycles agree (Kit P03).
- **B. Execution contracts:**
  - Depth and Vegetation declare their real inputs (P06; no dependency-graph drift).
  - Neither has an executor (`kind: none`), declared and tested.
  - No scheduler or publication system was added.
- **C. Swift boundaries:**
  - `test_swift_write_ownership.py` is the Swift equivalent of P14:
    - write call sites are pinned;
    - every constructed store carries the Brain id;
    - the shared stores run `BrainOwnership.check`;
    - the recorded write sets are entirely Brain-owned.
  - `test_swift_brain_boundary.py`:
    - pins the 60 customer-library `package` symbols the Brain targets use (decision D-C);
    - checks that no customer source imports a Brain target;
    - checks that the `SectorEngine` product excludes the Brain targets.
  - Extracting a non-customer library would move customer-module types, so it stays decision D-C.
- **D. Memory:** the standing checks were re-run.
  - Depth and Vegetation are now PASS on store/owner, developer machine, memory-unavailable and Pulse independence.
  - Both are PARTIAL on release identity (no image) and on separation/approval (NOT_RECORDED).
  - The standing gate covers all eight Brains and five releases.
- **E. Scoring:**
  - The shared scorer has no Depth or Vegetation entry.
  - Both Brains have no score block (Kit `has_score=False`) and write no `/scores` path.
  - No rubric or score changed.
- **F. Orchestrator and Publisher:**
  - Ownership is unchanged; every registration is SHADOW.
  - The control-plane change is additive and not deployed.

## 5. Kit V1 harness (Engine copy)

- Added the `has_score` spec field. With it False, the proofs require that no score block is declared, and a new mutation proves that declaring one fails.
- The carried-finding mutation now runs only when the spec carries findings.
- No existing proof was weakened. All six earlier Brains still pass.
- Cortex gaps: CG-2.1-5 and CG-2.1-6.

## 6. Verification

Local results; CI is in §7.

**Python:**
- Platform: 739.
- Orchestrator: 46.
- Scores: 35.
- Kit: 32.
- Architecture: 133.
- Verification: 15.
- Brain suites as in §2.
- Depth with the research snapshot: 298.

**Other:**
- **Swift:** the full run is in the memory session (325 tests). For this session, Linux results come from CI.
- **Knowledge manifests:** 5 of 5 OK.
- **`describe_contract --check`:** 8 of 8.
- **Architecture report:** no Depth or Vegetation findings.
- **Pytest-only venv:** the foundation CI job was reproduced locally with no third-party packages.
- **Not run locally:** Docker, because it isn't installed.

No test contacted production. The research snapshot used for Depth was extracted from the branch into scratch and is never committed.

## 7. CI

Draft PR [Sector-Bowfishing/Sector_Engine#40](https://github.com/Sector-Bowfishing/Sector_Engine/pull/40).

- **First run:** one failure introduced by this work. The Wind staged-release test needed numpy in the pytest-only foundation job. Fixed in `ede81316` by applying the file's dependency gate.
- **Added in this session:**
  - Linux Swift (`swift:6.1-jammy`, the production toolchain);
  - image-build verification: wind-hourly, water-clarity-brain and brain-orchestrator builds plus in-container release checks, and the root brain-jobs build.
- **Final results:** recorded in `docs/cortex/engineering-status/inputs/ci.json` and the final report.

## 8. Records

- `COMPLIANCE.md`: Depth and Vegetation columns, BR-18/19 and the standing-check matrix re-evaluated.
- `CORTEX_GAPS.md`: CG-2.1-5 to 7.
- `engineering-status.json`: v1.1.0, with seven layers per Brain and actual proof results.
- Navigation refresh: `2026-10-20-cortex-2-1-structural-completion.md`.

## 9. Decisions and approvals

The list is in `engineering-status/inputs/decisions.json`:
- A-1 (merge) to A-3;
- M-1 to M-8;
- G-1;
- V-1 (Vegetation agency block);
- K-1 (Kit harness upstream);
- D-C to D-F;
- O-1.
