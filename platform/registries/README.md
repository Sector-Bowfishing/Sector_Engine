# platform/registries/

**Owner:** Platform
**Purpose:** Four DIFFERENT registries: Brain Registry, Lake Registry, Species Registry, Signal Registry. Never one 'registry'.

**Belongs here (eventually):** Only the four subdirectories.

**Does NOT belong here:** The provider catalog (`providers/PROVIDERS.json` is a catalog, not an entity registry).

**Import / dependency rules:** See each subdirectory. Entity identity ≠ intelligence.

**Migration status:** `brains/` and `lakes/` are structure only (README). `species/` holds the authoritative water-domain classification `species_water_domains.json` (see its README); species identity itself has not moved here. `signals/` is LIVE since Orchestrator G1/G2 (2026-10-16): definitions only, loaded by `sector_brain_platform.signals`. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
