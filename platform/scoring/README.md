# platform/scoring/

**Owner:** Platform
**Purpose:** Scorer, beta score, score publisher, shared rubric mechanics, platform rubrics, `SCORING.md`.

**Belongs here (eventually):** Platform scoring code and the engine/beta rubrics. Per-Brain rubrics live in `brains/<dir>/scoring/`.

**Does NOT belong here:** Candidate/science scores; any Brain's rubric.

**Import / dependency rules:** Ops never computes scores. Certification never moves a score.

**Migration status:** Phase 1A: structure only. Nothing has been moved here; current implementation remains at jobs/brain-scores. Governing docs: `docs/architecture/repository-audit-v1/` (`REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`, `TARGET_REPOSITORY_ARCHITECTURE_V1.md`).
