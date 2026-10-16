# platform/

**Owner:** Platform
**Purpose:** Brain Platform: everything common to all Brains. Never Brain-specific.

**Belongs here (eventually):** Shared runtime libraries, orchestrator, Publisher, scoring mechanics, lineage, ops, and the three registries (subdirectories).

**Does NOT belong here:** Any Brain's logic or data; imports of a specialist Brain implementation.

**Import / dependency rules:** May depend on `contracts/` and `providers/` (health/IO only). A Brain registers through `brain.json`; platform never imports a Brain.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at jobs/brain_platform, jobs/brain-orchestrator, jobs/brain-scores, Sources/SectorEngine/Brain*. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
