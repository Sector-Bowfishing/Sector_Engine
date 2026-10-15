# contracts/schemas/

**Owner:** Platform
**Purpose:** JSON Schemas (2020-12) for `brain.json`, `PROVIDERS.json`, research GAPS/MANIFEST, and the Brain/Lake/Species registries.

**Belongs here (eventually):** Schemas validated by `tools/architecture` (incl. `large-file-exceptions.schema.json`, added in Phase 1B).

**Does NOT belong here:** Brain-private schemas.

**Import / dependency rules:** Semver in `$id`/`schemaVersion`; breaking change = new major.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at n/a (new). Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
