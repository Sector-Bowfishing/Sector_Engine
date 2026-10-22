# platform/publisher/

**Owner:** Platform
**Purpose:** Publisher service and Orchestrator API: the only intended writer of `sector-brain`.

**Belongs here (eventually):** Publisher code, envelope validation, path-ownership enforcement.

**Does NOT belong here:** Brain-specific artifact logic; security/IAM topology detail (stays private).

**Import / dependency rules:** Owned by the Publisher lane. This directory is a reserved destination only; no code lives here yet.

**Migration status:** Structure only. Nothing has been moved here. The current implementation is on `main` under `jobs/brain_platform/sector_brain_platform/`: `publisher/` (shadow validation, plan, registry of path families) and `publisher_live/` (Publisher LIVE V1). Publisher LIVE V1 is repository-implemented and owns **no** production writes: only tests and certification tooling import it, and every Brain still writes RTDB directly. Its sole-writer cutover (Water Clarity → Fish → Wind) is planned and approval-gated (`docs/architecture/production/PRODUCTION_CUTOVER_PLANS_V1.md`). Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
