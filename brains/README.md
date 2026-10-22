# brains/

**Owner:** Each Brain (see `brain.json`)
**Purpose:** Specialist Brains, one home each, standard package. Machine ids never change.

**Belongs here (eventually):** `_template/` and, after each Brain's migration, `wind/ fish/ lake/ water-temperature/ water-clarity/ depth/ vegetation/ sector-intelligence/`.

**Does NOT belong here:** Other Brains' internals, customer Engine code, raw research data, secrets, empty placeholder Brain directories.

**Import / dependency rules:** May import `providers/`, `platform/` (incl. registry contracts) and other Brains' `contracts/` only. `brains/fish` has `brainId` `biological-state`.

**Migration status:** six Brains are migrated and live here as canonical packages: `wind/` (Repository Phase 2), `fish/` (`biological-state`), `water-clarity/`, and — Cortex architecture completion, 2026-10-20 — `sector-intelligence/`, `lake/` (`lake-brain`) and `water-temperature/` (`water-temp`). Lake and Water Temperature have Swift runtimes as SwiftPM targets inside their packages (`runtime/<Target>/`). Their old `jobs/*` directories are retirement pointers, except `jobs/lake-brain/`, which keeps Lake's offline tooling. Depth and Vegetation exist only on their unmerged branches (see `docs/cortex/`). `tools/architecture` enforces that no other `brain.json` exists before a Brain migrates.
