# Lake Brain (`brainId: lake-brain`)

**What it is.** The Lake Brain answers, per lake: *what is the water level doing, against the lake's own operating rules and history, and how sure is that?* It publishes the LakeProfile (pools, operator characteristics, source capability, history coverage) and the LakeState (current elevation, change, and `levelState` / `trendState` / `historicalState` / `floodPoolState` as separate fields, with freshness and provenance), computed with explainable baselines and rules (`doy15-percentile-v2`, `lake-level-rules-v2`; no ML). **Bowfisher decision (level part):** whether a lake is normal, low, high, rising, falling, unusual for the season or in flood pool tonight, and how fresh and reliable that reading is; Sector Intelligence makes the bowfishing recommendation. Consumers: Sector Ops and Sector Intelligence read published Lake state. Lifecycle `CALIBRATION`, validation `NOT_VALIDATED`; no customer path reads it.

Rules for every session: **[`BRAIN_OPERATING_CONTRACT.md`](BRAIN_OPERATING_CONTRACT.md)**. Identity and edges: [`brain.json`](brain.json). Published contract (SHADOW): [`contracts/lake-publication-v1.json`](contracts/lake-publication-v1.json). Integration contract: `docs/brains/LAKE_BRAIN_INTEGRATION.md`.

| Path | Holds |
|---|---|
| `runtime/LakeBrain/` | Swift library target `LakeBrain` (feeds, bindings, baselines, classifier, runner, archive, presence, prediction ledger). Depends on the shared `SectorEngine` library (fetchers, lake directory, Swift Brain platform); nothing in the customer server imports it |
| `runtime/LakeBrainJob/` | Swift executable `LakeBrainJob` (`/app/LakeBrainJob` in the brain-jobs image) |
| `runtime/publish_artifact.py` | Publisher V2 artifact builder over one run's write set (**shadow only**; the job still writes through the Swift platform client) |
| `contracts/` | `lake-publication-v1.json` (derived from the Publisher registry by `describe_contract.py --check`) |
| `tests/swift/` | Swift test target `LakeBrainTests` (classifier, baselines, bindings gate, ledger, rules v2, fleet visibility, the write-set fixture) |
| `tests/golden/` | `lake_run_updates.json`: the runner's real write set on deterministic feeds, produced only by `LakePublicationFixtureTests` |
| `tests/*.py` | Brain Certification Kit V1 adapter (`lake_cert_spec.py`) |
| `research/` | research rules (README). Never data |
| `deploy/` | `deploy-job.sh` (Cloud Run job `lake-brain`, `--scope pilots`, no scheduler of its own; approval-gated) |

The offline Python tooling (binding table, history backfill, ledger scorer, review pack, hold-out validation) stays in `jobs/lake-brain/` (see its README).

```bash
swift build --product LakeBrainJob
swift test --filter LakeBrainTests                                     # Swift suite
SECTOR_WRITE_BRAIN_FIXTURES=1 swift test --filter LakePublicationFixtureTests   # regenerate the write-set fixture (review the diff)
cd brains/lake && python3 -m pytest -q                                 # Certification Kit V1 over the fixture (pytest.ini sets import roots)
PYTHONPATH=jobs/brain_platform python3 brains/lake/contracts/describe_contract.py --check
.build/debug/LakeBrainJob --dry-run /tmp/lake-brain --read-rtdb https://sector-brain.firebaseio.com --archive gs://sector-lake-brain   # GET only; see the integration contract §12
```

Nothing here is deployed, scheduled or published by the repository. **Per-lake species presence is never committed**: it reaches the runtime only from the validated private presence release.
