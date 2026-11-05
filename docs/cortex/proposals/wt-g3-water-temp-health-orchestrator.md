# Water Temp G3: Water Temp's health family moves to the Orchestrator (proposal, DRAFT)

**Status:** PROPOSED. Not applied to Cortex. Sector_Ops #52 step G3-1, drafted under the owner's standing approval of 2026-11-05 (Sector_Ops #50: "Water Temp G3/G4 prep as drafts").

Cortex is read-only from the Engine, so this is the text for a Cortex maintenance session. It follows the per-Brain rule Cortex 3.1.2 adopted for Water Clarity (CG-3.1-15): literal rows, landed only with that Brain's approved CENTRAL cutover.

## Proposed Cortex rows (registry only)
Add to `projects/sector/shared/data/firebase-data-contracts.json`, after `fam.health-sources-noaa-mrms`:

| id | pattern | scope | status | writer | targetWriter |
|---|---|---|---|---|---|
| `fam.health-brains-water-temp` | `/health/brains/water-temp` | per-brain | CANONICAL | `platform.orchestrator` | null |
| `fam.health-sources-open-meteo-forecast` | `/health/sources/open-meteo-forecast` | global | CANONICAL | `platform.orchestrator` | null |
| `fam.health-sources-usace-cwms-water-temp` | `/health/sources/usace-cwms-water-temp` | global | CANONICAL | `platform.orchestrator` | null |
| `fam.health-sources-usgs-nwis-00010` | `/health/sources/usgs-nwis-00010` | global | CANONICAL | `platform.orchestrator` | null |

The other columns are copied from `fam.health-brains` / `fam.health-sources`, as for Water Clarity. The source list is the Publisher registry's `_owned_sources(WATER_TEMP)`.

## Ordering (why it must not land early)
A row moves ownership. Before Water Temp is CENTRAL, its Swift job still writes its own health (DIRECT_WRITE). If the rows land first, the guard refuses that write and Water Temp's health goes unwritten.

So these rows, the Engine PR (`feat/wt-health-orchestrator-2026-11-05`), the Cortex pin bump, the `publication-cutover.json` CENTRAL flip and an Orchestrator deploy land together, in one owner-approved change (G3-4).

## Engine side (draft PR)
- **Mirror:** the four rows in `data_ownership.json`.
- **Swift:** `BrainOwnership.orchestratorHealthBrains` and `orchestratorHealthSources` gain the Water Temp ids.
- **Conformance and tests:** the Water Temp cases are added and flipped. The tests that assumed Water Temp writes its own health now use Lake. Lake, Wind and the generic families are unchanged.
- **Expected red check:** the mirror-equality test fails against pinned Cortex `ecaef70` until the rows exist in Cortex. This is the same block Water Clarity had.
