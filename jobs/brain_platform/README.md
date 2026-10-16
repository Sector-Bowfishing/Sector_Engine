# sector_brain_platform

The shared Python implementation of `docs/brains/BRAIN_PLATFORM_CONTRACT.md` (stdlib-only).
Every Python Brain job vendors this package (its `deploy-job.sh` copies
`jobs/brain_platform/sector_brain_platform` into the job directory before `gcloud run jobs deploy --source .`),
the same way the lake-surface and hydrology jobs copy their inputs in.

Tests are the conformance suite: `python3 -m pytest -q` here (fixtures in `contracts/conformance/`).
The Swift implementation (`Sources/SectorEngine/Brain/`) runs the same fixtures from
`Tests/SectorEngineTests/BrainPlatformConformanceTests.swift`.
