# Water Temperature Brain (`brainId: water-temp`)

**What it is.** The Water Temperature Brain answers, per lake: *what is the water temperature doing?* It restates the production measurement-or-model selection (lake sensor ≤ 6 h and ≤ 15 mi, else a nearby USGS lake gauge, else the `surface-energy-balance-v2` model, else unavailable) as Brain state, profile, registry, validation and health, with provenance and no invented confidence. **Bowfisher decision (temperature part):** how warm the water is, whether that is measured or modelled, and which way it is trending; Sector Intelligence makes the bowfishing recommendation. Consumers: Sector Ops and Sector Intelligence. Lifecycle `CALIBRATION` (activity PARKED); validation `GLOBAL_HOLDOUT_ONLY`.

Rules for every session: **[`BRAIN_OPERATING_CONTRACT.md`](BRAIN_OPERATING_CONTRACT.md)**. Identity and edges: [`brain.json`](brain.json). Published contract (SHADOW): [`contracts/water-temp-publication-v1.json`](contracts/water-temp-publication-v1.json). Vocabularies and paths: `docs/brains/WATER_TEMP_BRAIN.md`. The machine id is `water-temp`; the directory is `water-temperature` (never renamed).

| Path | Holds |
|---|---|
| `runtime/WaterTemperatureBrain/` | Swift library target `WaterTemperatureBrain` (state, profile, registry, runner). Depends on the shared `SectorEngine` library (fetchers, resolver, lake directory, Swift Brain platform); the customer `/conditions` path does not import it |
| `runtime/WaterTempBrainJob/` | Swift executable `WaterTempBrainJob` (`/app/WaterTempBrainJob` in the brain-jobs image) |
| `runtime/publish_artifact.py` | Publisher V2 artifact builder over one run's write set (**shadow only**) |
| `contracts/` | `water-temp-publication-v1.json` (derived from the Publisher registry by `describe_contract.py --check`) |
| `tests/swift/` | Swift test target `WaterTemperatureBrainTests` (vocabularies, unknowns, health rule, pruning, the write-set fixture) |
| `tests/golden/` | `water_temp_run_updates.json`: the runner's real write set on deterministic inputs, produced only by `WaterTemperaturePublicationFixtureTests` |
| `tests/*.py` | Brain Certification Kit V1 adapter (`water_temp_cert_spec.py`) |
| `research/` | research rules (README). Never data |
| `deploy/` | `deploy-job.sh` (Cloud Run job `water-temp-brain` from the brain-jobs image; **no scheduler**: the Brain Orchestrator starts it when stale; approval-gated) |

```bash
swift build --product WaterTempBrainJob
swift test --filter WaterTemperatureBrainTests
SECTOR_WRITE_BRAIN_FIXTURES=1 swift test --filter WaterTemperaturePublicationFixtureTests   # regenerate the write-set fixture (review the diff)
cd brains/water-temperature && python3 -m pytest -q                    # Certification Kit V1 over the fixture
.build/debug/WaterTempBrainJob --dry-run /tmp/brain --lake "Guntersville|AL"     # every path as a JSON file; no database (fetches live providers)
```

Nothing here is deployed, scheduled or published by the repository.
