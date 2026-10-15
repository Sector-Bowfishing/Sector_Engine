# contracts/conformance/

**Owner:** Platform (change-controlled)
**Purpose:** the single canonical home of the cross-language conformance fixtures. Python (`jobs/brain_platform/tests`, `jobs/lake-brain/validation`) and Swift (`Tests/SectorEngineTests/BrainPlatformConformanceTests.swift`, `LakeRulesV2Tests.swift`) run the very same files and must agree.

**Belongs here:** conformance fixtures only (`*.json`). **Does NOT belong here:** a second copy of anything; Brain-private fixtures; golden customer-response baselines (those are in `verification/fixtures/`).

**Import / dependency rules:** read-only inputs to tests; no runtime code may read them. Changing a fixture changes the contract: both language implementations must be updated in the same commit.

**Migration status:** relocated from `docs/brains/conformance/` in Phase 1B. Content is byte-identical (SHA-256 manifest in `docs/architecture/repository-foundation-v1/PHASE_1B_IMPLEMENTATION.md`); a pointer README remains at the old path. `tools/architecture` and `verification/integration/test_conformance_home.py` fail if a duplicate live copy reappears.
