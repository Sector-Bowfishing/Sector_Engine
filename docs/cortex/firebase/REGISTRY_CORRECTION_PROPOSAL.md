# Cortex data-contract registry correction proposal (from Sector Engine, 2026-10-21)

Standards: Rehtac Cortex 2.2.0 @ ae59e2d, pack sector/engine.

**Target:** `projects/sector/shared/data/firebase-data-contracts.json`, for a Cortex maintenance session. Nothing here changes Cortex.

**Evidence:**
- the 2026-10-21 production export, plus narrow read-only live reads;
- Engine source at the head of `cortex/firebase-data-audit-2026-10-21`;
- the RTDB emulator.

**Machine-readable Engine view:** `verification/firebase/path_families.json` (every production family, with writer, readers, status and freshness), which tests keep current.

## 1. Corrections to findings

| Registry item | Correction | Evidence |
|---|---|---|
| **fnd.04** "No verified Fish operational node" | **Wrong. Close it.** `/brains/biological-state` exists in production and is written by Fish (status PROFILED, version `biological-brain-0.1.0`, researchVersion `2026-10-17.1`, manifest reference + sha256, deploymentVersion `brain/biological@a26febb8`, lastSuccessfulRun 2026-10-19). There is no `/brains/fish` or other alias. **mig.03 is not needed.** | export + live; `test_fish_is_published_under_its_canonical_id_only` |
| fnd.02 Wind stale score copy | **Confirmed, and remediated in code.** The copy is labelled `FROZEN_VALIDATION_EVIDENCE`, `authoritative: false`, `authoritativeScorePath: /scores/wind`, with a retirement switch. mig.01 order: Ops reader → switch off → gated delete | `brains/wind/tests/test_legacy_score_copy.py` |
| fnd.05 legacy orchestrator record | `/control/orchestrator` is **load-bearing state**: written and read back by `orchestrate.py` (state carry). Classify it as CANONICAL internal, or plan its migration into `orchestratorV1`. It is not a delete candidate | `orchestrate.py:282,438` |
| fnd.09 `/validation`, `/activity` not established | **Established.** Each Brain writes its own `/validation/{brainId}` and `/activity/*-{brainId}-*`. Promote to CANONICAL | export; `ownership.path_allowed` |
| fnd.10 species presence in RTDB | Classification **PRIVATE**, but the deployed rules let every allowlisted Ops user read it (emulator-verified). Add an FD-11 finding with a decision. A least-privilege proposal exists | `rules_emulator_check.py --proposed` |
| fnd.12 Lake writes from an image not on main | **Confirmed live:** lake-brain `a6622f99ed9e`. That image writes `predictionLedger` and `claimMaturity`, which are now declared as optional Publisher registry children | `test_production_registry_children_are_inside_the_publisher_contract` |
| fnd.13 health writer not established | **Established:** each Brain writes its own `/health/brains/{brainId}`, a status recorded at its last execution | export; ownership |
| **New** | `/jobs/lake-brain-ledger-daily` had no owner (unmanifested). Fixed in the Engine manifest | `test_jobs.py` |
| **New** | Four Brains wrote `/snapshots` and other paths without declaring them in `brain.json`. Now declared as `legacyDirectWrites` | `brains/*/tests/test_declared_write_set.py` |
| **New** | Orphaned rollup parents `/lakeFleet/{k}/lastUpdatedAt` and `/snapshots/{k}/latest/{generatedAt, snapshotVersion}` are frozen since 2026-10-12/13, with no writer and no reader. **Deprecated**, deletion candidates | `test_orphaned_rollup_parents_are_writable_by_nobody` |

## 2. Corrections to families

1. **Per-slot ownership** for `fam.lakefleet`, `fam.snapshots` and `fam.lake-*-state`:
   - writer = the slot's Brain (`keys.BRAINS` slot and snapshot field);
   - `lakeId` and `brainVersions/{brainId}` are written by every slot Brain today (`legacyDirectWrites`, disposition `PLATFORM_OWNED_STOP_WRITING` / `PUBLISHER_COMPATIBILITY_PROJECTION`).
   - Today the registry names a single writer (`brain.wind` / `brain.lake-brain`), which produces most of `data-check`'s UNDECLARED_ACCESS findings.
2. **A new family for the ORPHANED rollup parents,** with writer `none`, status LEGACY, retention "delete after baseline".
3. **Register the missing roots:**
   - `/health/sources/{source}` (writer: the source owner);
   - `/health/jobs/{job}` (Brain; disposition ORCHESTRATOR_DERIVED);
   - `/sources/{source}`;
   - `/control/fleet/{k}`, `/control/beta` (platform scorer in the orchestrator);
   - `/engine/score` (LEGACY alias of `/scores/engine`);
   - `/access/opsUsers/{uid}` (PRIVATE; external writer);
   - `/access/privateResearchUsers/{uid}` (proposed);
   - `/species` root reads.
4. **Declare readers:**
   - `platform.publisher-shadow` reads every family it validates;
   - `verification.cross-component` reads every family (the audit tests);
   - Sector Intelligence and Fish read `/snapshots/{k}/latest`.
5. **Add a freshness semantic per family.**
   - Slot `stale` and `/health/brains/*` are **write-time**.
   - The authoritative current freshness is `/control/fleet/{k}.staleSlots` (FLAG / AGE) and `/control/overview.brains[*].healthCurrent`.
6. **Answer the production checks:**
   - pc.01–pc.07 and pc.09 are answered;
   - pc.08: rules answered (identical to Sector Ops `database.rules.json`; emulator-verified); IAM stays NOT_VERIFIED.

## 3. Cortex tool / standard gaps (also in CORTEX_GAPS)

- **CG-2.2-2:** write-time freshness flags (FD-07).
- **CG-2.2-3:** `data-check` reports reads as writes and matches placeholders to the most specific family. It also counts test data outside `tests/` (fixtures, classification maps) as production access.
- **CG-2.2-4:** PRIVATE vs INTERNAL_OPS in terms of reader scope.
- **CG-2.2-5:** `legacyDirectWrites` should become part of the Brain manifest standard (BR / FD-01). The Kit's P05 compares only the Publisher contract.
