# jobs/water-temp-brain/

Deployment script for the Water Temperature Brain (`brainId: water-temp`) Cloud Run job. **Not a runtime and not a retired stub**: the Brain's code is Swift, in `Sources/SectorEngine/Brain/WaterTemperatureBrain*.swift`, `Sources/SectorEngine/WaterTemp/` and the `WaterTempBrainJob` executable (`Sources/WaterTempBrainJob/main.swift`).

| File | What it does |
|---|---|
| `deploy-job.sh` | Deploys the Cloud Run job `water-temp-brain` from the `brain-jobs` image (`IMAGE=<from jobs/brain-image-build.sh>` is required; `DRY_RUN=1` prints the gcloud commands). Creates **no scheduler**: the Brain Orchestrator starts the job only when the 6-hour freshness rule requires it, and the script warns if a scheduler exists |

Run the Brain locally, writing nothing remote:

```bash
swift build --product WaterTempBrainJob
.build/debug/WaterTempBrainJob --dry-run /tmp/brain --lake "Guntersville|AL"
```

Tests: `swift test --filter WaterTemp`. Contract and vocabularies: `docs/brains/WATER_TEMP_BRAIN.md`. Operating contract: `docs/architecture/certification/water-temp/BRAIN_OPERATING_CONTRACT.md`. Deploying is approval-gated.
