# platform/publisher/

**Owner:** Platform
**Purpose:** Publisher service and Orchestrator API: the only intended writer of `sector-brain`.

**Belongs here (eventually):** Publisher code, envelope validation, path-ownership enforcement.

**Does NOT belong here:** Brain-specific artifact logic; security/IAM topology detail (stays private).

**Import / dependency rules:** Owned by the Publisher lane. This directory is a reserved destination only; Phase 1A does not touch the Publisher worktree.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at Not on this branch (lives on `feat/publisher-v1-shadow`, owned by the Publisher lane). Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
