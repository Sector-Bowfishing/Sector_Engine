# contracts/

**Owner:** Platform (change-controlled)
**Purpose:** Shared, language-neutral, versioned contracts and the machine schemas for the architecture itself.

**Belongs here (eventually):** `schemas/` (architecture + platform schemas), `conformance/` (cross-language fixtures, destination).

**Does NOT belong here:** Brain-private schemas (those live in `brains/<dir>/runtime/schemas`).

**Import / dependency rules:** One definition per contract. Brain-published contracts live in `brains/<dir>/contracts/`.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at docs/brains/conformance (fixtures), docs/brains/platform/*.md (specs). Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
