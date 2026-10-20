# brains/

**Owner:** Each Brain (see `brain.json`)
**Purpose:** Specialist Brains, one home each, standard package. Machine ids never change.

**Belongs here (eventually):** `_template/` and, after each Brain's migration, `wind/ fish/ lake/ water-temperature/ water-clarity/ depth/ vegetation/ sector-intelligence/`.

**Does NOT belong here:** Other Brains' internals, customer Engine code, raw research data, secrets, empty placeholder Brain directories.

**Import / dependency rules:** May import `providers/`, `platform/` (incl. registry contracts) and other Brains' `contracts/` only. `brains/fish` has `brainId` `biological-state`.

**Migration status:** three Brains are migrated and live here as canonical packages: `wind/` (Repository Phase 2), `fish/` (`biological-state`, Fish Structural Certification V1) and `water-clarity/` (Water Clarity Structural Certification V1); their old `jobs/*` directories are retirement pointers. Not yet migrated: Lake (`lake-brain`: `Sources/SectorEngine/LakeBrain/`, `Sources/LakeBrainJob/`, `jobs/lake-brain/`), Water Temperature (`water-temp`: `Sources/SectorEngine/Brain/WaterTemperatureBrain*.swift`, `Sources/WaterTempBrainJob/`) and Sector Intelligence (`jobs/sector-intelligence-brain/`); until they migrate, their operating contracts live under `docs/architecture/certification/<brain>/`. Depth and Vegetation exist only on their unmerged branches. `tools/architecture` enforces that no other `brain.json` exists before a Brain migrates. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
