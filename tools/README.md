# tools/

**Owner:** Platform
**Purpose:** Repo-wide developer tooling (generators, linters, architecture report). No domain logic.

**Belongs here (eventually):** `architecture/` report and its tests; `brain_certification/` (BRAIN_CERT_KIT_V1: test-only shared structural-certification kit; needs pytest and the platform package, never vendored into an image).

**Does NOT belong here:** Domain logic; runtime code.

**Import / dependency rules:** Stdlib-only Python (exception: `brain_certification` is test tooling and imports pytest and `sector_brain_platform`).

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at scripts/. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
