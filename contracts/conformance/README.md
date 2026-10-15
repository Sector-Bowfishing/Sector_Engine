# contracts/conformance/

**Owner:** Platform
**Purpose:** DESTINATION for cross-language conformance fixtures.

**Belongs here (eventually):** Fixtures proving Python and Swift agree.

**Does NOT belong here:** A second copy of fixtures.

**Import / dependency rules:** The relocation `docs/brains/conformance` → here is Phase 1B (RA-11). Until then there is exactly ONE source of truth: the old path. Do not copy fixtures here in Phase 1A.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at docs/brains/conformance (still authoritative; existing CI and tests reference it). Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
