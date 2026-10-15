# platform/registries/lakes/

**Owner:** Platform
**Purpose:** LAKE REGISTRY: canonical lake identity (lakeId, lake_key, names, aliases, classification, centroid, geometry REFERENCE). Lake Brain owns intelligence ABOUT lakes. Schema: `contracts/schemas/registry-lakes.schema.json`.

**Belongs here (eventually):** Schema, generator, key-derivation conformance, small identity source, manifest pointing at released geometry.

**Does NOT belong here:** Hydrology, bindings, condition interpretation, per-lake species presence (private), polygons ≥ 1 MB (release storage + manifest).

**Import / dependency rules:** Wind, Clarity, Water Temperature, Fish and Lake Brain resolve lakes here, not through Lake Brain. No data migrated in Phase 1A.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at Sources/SectorEngine/LakeDirectory*, jobs/lake-surface, jobs/lake-geometry, scripts/generate-lake-*.py. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
