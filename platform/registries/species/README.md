# platform/registries/species/

**Owner:** Platform
**Purpose:** SPECIES REGISTRY: canonical species identity (CERT-8). Fish Brain (`biological-state`) owns intelligence ABOUT fish. Schema: `contracts/schemas/registry-species.schema.json`.

**Belongs here (eventually):** Schema, generator, public identity source.

**Does NOT belong here:** Legality, per-lake presence (private, never public Git), fish behavior intelligence.

**Import / dependency rules:** No data migrated in Phase 1A.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at Fish Brain species data (to be separated at Fish certification). Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).

**Water domains (V1):** `species_water_domains.json` is the authoritative FRESHWATER/BRACKISH/MARINE classification (schema `contracts/schemas/registry-species-water-domains.schema.json`; doc `docs/architecture/data/SPECIES_WATER_DOMAIN_V1.md`). Fish runtime carries a generated projection; regenerate with `brains/fish/runtime/tools/gen_water_domain_projection.py`.
