# providers/

**Owner:** Platform (per-provider owners in `PROVIDERS.json`)
**Purpose:** Shared acquisition: fetch, parse, normalize, report source health. Providers never interpret domain meaning.

**Belongs here (eventually):** `PROVIDERS.json` catalog (live now), later: provider clients and shared fixtures.

**Does NOT belong here:** Thresholds, gates, scoring, Brain interpretation, credentials.

**Import / dependency rules:** Depends on nothing domain-specific. Consumers must be listed in `authorizedConsumers`; the consumer (not the provider) declares `domainInterpreter` in its `brain.json`. No TVA consolidation before D8; Open-Meteo behavior unchanged.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at Sources/SectorEngine/**, jobs/*/ (Open-Meteo, USGS, TVA, CWMS, SWPA, NBM/RTMA/HRRR…). Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
