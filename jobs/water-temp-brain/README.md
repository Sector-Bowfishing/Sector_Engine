# Moved: `jobs/water-temp-brain` → `brains/water-temperature/`

**Status: RETIRED (Water Temperature migration, Cortex architecture completion 2026-10-20).** The Water Temperature Brain's (`brainId: water-temp`) permanent home is [`brains/water-temperature/`](../../brains/water-temperature/README.md). Nothing here is code, an entrypoint or a deploy unit.

| Was | Now |
|---|---|
| `deploy-job.sh` | `brains/water-temperature/deploy/deploy-job.sh` |
| Swift `Sources/SectorEngine/Brain/WaterTemperatureBrain*.swift`, `Sources/WaterTempBrainJob/` | `brains/water-temperature/runtime/WaterTemperatureBrain/`, `brains/water-temperature/runtime/WaterTempBrainJob/` (SwiftPM targets) |

The Cloud Run job id `water-temp-brain`, the product `WaterTempBrainJob` and the image path `/app/WaterTempBrainJob` are unchanged.
