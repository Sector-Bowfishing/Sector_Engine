# engine/

**Owner:** Engine (customer-serving)
**Purpose:** The customer-serving scoring engine: `/conditions`, `/lakes`, scoring, forecast, API.

**Belongs here (eventually):** Engine scoring/API code, engine-owned tests, build-time reference data (`full_pool.csv`, `temp_sensors.csv`), endpoint/scoring docs.

**Does NOT belong here:** Brain runtime, provider clients, research, anything that reads `sector-brain` directly.

**Import / dependency rules:** May depend on `providers/` and `platform/` contracts. Reaches Brain output only through an approved `customerIntegrationMode` contract/library (Customer Engine → Brain contract, never the reverse).

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at Sources/SectorEngine, Sources/SectorEngineServer, Tests/ (root; `Package.swift` stays at the repo root). Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
