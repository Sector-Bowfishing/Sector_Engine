# Cutover plans for Water Temperature, Lake and Sector Intelligence: Session Record

```text
Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (clean), pack sector/engine (repository pin d5c8380, identical tree)
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/cutover-plans-2026-10-31 · Start commit: ca669772 (origin/main) · Date: 2026-10-31
```

## 1. Scope
- **Request:** overnight run (Sector_Ops issue 24, step 3): a cutover plan for each of Water Temperature, Lake and Sector Intelligence, using `REMAINING_BRAIN_MIGRATIONS_V1.md` and its nine common gates. Documents and a consistency test only.
- **Inspected:** each Brain's `brain.json`, runtime entry points (Swift `--dry-run DIR` modes, `run.py --write`), `publish_artifact.py` builders, `publisher/registry.py` registrations, `cutover_order.json`, `orchestrate.py` in-process wiring.

## 2. Findings
| ID | Finding | Status | Evidence |
|---|---|---|---|
| CP-1 | The three Brains had no cutover plan | FAIL | `REMAINING_BRAIN_MIGRATIONS_V1.md` rows 3–5 |
| CP-2 | All three registrations still authorise `/health/brains/{id}/...`; Lake and Water Temp also authorise `/health/sources/{id}` (gate G3 not met; Cortex 3.1: the Publisher never writes health) | FAIL (recorded in the plans; not changed here) | `publisher/registry.py` Lake, Water Temp, Intelligence registrations |
| CP-3 | Lake's registration authorises `/lakes/{k}/speciesPresence`, which Cortex BA-02 assigns to Fish | PARTIAL: owner decision pending (Sector_Ops 22 D3) | registry Lake lake-state family |
| CP-4 | Sector Intelligence runs in process in the Orchestrator and writes with the Orchestrator's identity | FAIL (FD-15 target) | `orchestrate.py` RUNTIMES `sector-intelligence: in-process` |

## 3. Changes
| Correction | Class | Files |
|---|---|---|
| Cutover plans, nine gates per Brain, batched decisions WT-1, WT-2, SI-1, SI-2, L-1 | requested (docs) | `docs/architecture/production/CUTOVER_PLANS_WT_LAKE_INTELLIGENCE_V1.md` |
| Consistency test (order = `cutover_order.json`; G1–G9 present per Brain) | safe | `tools/architecture/tests/test_cutover_plans_doc.py` |
| Migration table links to the plans | safe | `REMAINING_BRAIN_MIGRATIONS_V1.md` |
| CP-2 registry change (drop health families) | **not made**: it changes a Publisher contract and belongs to each Brain's G3 change | — |

## 4. Verification
`pytest -q tools/architecture` all passed (2 new tests); the full suite set is unchanged (docs and a test only). Engineering status regenerated.

## 5–9
Decisions: in the plan document §4. Cleanup: worktree `Worktrees/Sector_Engine/overnight-plans` (closeout in Sector_Ops 24). Cortex gaps: none. Next step: owner review of WT-1 (it unblocks G1 for both Swift Brains).
