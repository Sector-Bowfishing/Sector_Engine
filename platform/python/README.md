# platform/python/

**Owner:** Platform
**Purpose:** Future installable `sector_brain_platform` Python package (stdlib-only).

**Belongs here (eventually):** Envelope, keys, freshness, health, ownership, lineage helpers, once migrated.

**Does NOT belong here:** Brain-specific code; third-party dependencies.

**Import / dependency rules:** Stdlib-only. Existing jobs keep importing the current location until the migration phase repoints them.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at jobs/brain_platform/sector_brain_platform. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
