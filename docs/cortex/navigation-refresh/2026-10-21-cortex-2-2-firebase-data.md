# Navigation refresh — Cortex 2.2 Firebase data (2026-10-21)

Standards: Rehtac Cortex 2.2.0 @ ae59e2d, pack sector/engine. Architecture differences between Cortex's data model and the Engine as built (proposals only; Cortex not modified).

| Item | Cortex says | Engine / production | Evidence |
|---|---|---|---|
| Fish operational node | none verified (fnd.04) | `/brains/biological-state`, written by Fish; no alias | export + live; `test_fish_is_published_under_its_canonical_id_only` |
| Per-lake shared families | single writer per family | per-slot ownership (`ownership.path_allowed`), lakeId/brainVersions shared by every slot writer | `test_family_writers_match_the_ownership_table` |
| Rollup parents (`/lakeFleet/{k}/lastUpdatedAt`, `/snapshots/{k}/latest/{generatedAt,snapshotVersion}`) | not modelled | ORPHANED (writer none), frozen 2026-10-12/13 | inventory; `test_orphaned_rollup_parents_are_writable_by_nobody` |
| `/control/orchestrator` | legacy record (fnd.05) | live state written and read back by `orchestrate.py` | `orchestrate.py:282,438` |
| Snapshot writes | — | Clarity, Wind, Lake, Water Temp write `/snapshots/{k}/latest/*` but omit them from `brain.json` pathFamilies | session record S-3 |
| Lake registry | Publisher `LAKE_REGISTRY_CHILDREN` | production also carries `claimMaturity`, `predictionLedger` (image a6622f99, not on main) | session record E-8 |
| Engine-side family map | — | `verification/firebase/tests/path_families.json` (machine-readable; can seed the registry correction) | — |
| Undeclared runtime writes | — | **Fixed 2026-10-21:** `brain.json` `publishes[].legacyDirectWrites` (7 Brains), tested against the real write sets | `brains/*/tests/test_declared_write_set.py`, `tools/architecture/tests/test_legacy_direct_writes.py` |
| Lake registry fields | — | **Fixed:** optional `evidence` group in `LAKE_REGISTRY_CHILDREN` | `test_production_registry_children_are_inside_the_publisher_contract` |
| `/jobs` ledger owner | — | **Fixed:** `jobs.MANIFEST["lake-brain-ledger-daily"]` | `test_jobs.py` |
| Freshness | — | **Fixed (source):** `/control/fleet/{k}.staleSlots` FLAG/AGE; overview `healthCurrent` | `test_control.py` |
