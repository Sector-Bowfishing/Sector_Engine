# platform/orchestrator/

**Owner:** Platform
**Purpose:** Brain executor, control plane, lineage preflight, deploy of the shared Brain jobs image.

**Belongs here (eventually):** Orchestrator code and tests; control manifest generated from `brain.json`.

**Does NOT belong here:** Brain domain logic.

**Import / dependency rules:** Reads Brains only through the generated Brain Registry.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at jobs/brain-orchestrator. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
