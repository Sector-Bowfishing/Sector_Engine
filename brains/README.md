# brains/

**Owner:** Each Brain (see `brain.json`)
**Purpose:** Specialist Brains, one home each, standard package. Machine ids never change.

**Belongs here (eventually):** `_template/` and, after each Brain's migration, `wind/ fish/ lake/ water-temperature/ water-clarity/ depth/ vegetation/ sector-intelligence/`.

**Does NOT belong here:** Other Brains' internals, customer Engine code, raw research data, secrets, empty placeholder Brain directories.

**Import / dependency rules:** May import `providers/`, `platform/` (incl. registry contracts) and other Brains' `contracts/` only. `brains/fish` has `brainId` `biological-state`.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at jobs/*, Sources/SectorEngine/*Brain*, per-Brain docs. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
