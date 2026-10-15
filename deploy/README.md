# deploy/

**Owner:** Platform
**Purpose:** Deploy units that belong to no single Brain (shared brain-jobs image, orchestrator).

**Belongs here (eventually):** Shared image recipes and deploy scripts, when migrated.

**Does NOT belong here:** Secrets; Brain-owned deploy units (those live in `brains/<dir>/deploy/`).

**Import / dependency rules:** Phase 1A changes no deploy definition.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at deploy.sh, Dockerfile (root, stay), jobs/*/Dockerfile and deploy scripts. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
