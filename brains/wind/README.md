# Wind Brain (`brainId: wind`)

**What it is.** The Wind Brain answers, per lake: *what are the wind and water-surface conditions doing?* It archives NOAA **NBM** forecasts (10 m wind/gust + probabilistic quantiles), **RTMA-RU** analyses and **METAR/AWOS** observations for Guntersville, Wheeler, Wilson and Pickwick, and turns wind into bank surface exposure with frozen fetch physics. **Bowfisher decision:** where on the lake the surface is calm enough to see and shoot, and when that changes overnight. Lifecycle CALIBRATION, science `NOT_VALIDATED`; customer `/conditions` wind is Open-Meteo, not this Brain.

Rules for every session: **[`BRAIN_OPERATING_CONTRACT.md`](BRAIN_OPERATING_CONTRACT.md)**. Identity and edges: [`brain.json`](brain.json). Published contract: [`contracts/wind-publication-v1.json`](contracts/wind-publication-v1.json).

| Path | Holds |
|---|---|
| `runtime/` | production: `main.py` (job entrypoint), `sector_wind/` (ingest, decoder, store, sample/interp, validate, monitor, bowfishing physics, `brain/` adapter + Publisher V2 artifact builder), `lakes.json` (interim Lake Registry reference copy), `requirements.txt` |
| `contracts/` | `wind-publication-v1.json` (derived from the Publisher registry by `describe_contract.py --check`) |
| `tests/` | production tests (offline; network tests marked `network`) |
| `research/` | research rules (README) and `tools/`: research scripts and the research-only package `sector_wind_research` (+ its tests). Never in the image |
| `deploy/` | `deploy-job.sh` (stages the image context; refuses without approval), `Dockerfile`, `read_service/` (internal candidate read service) |
| `docs/` | design notes (`WIND_BRAIN_DESIGN_V1.md`, partly superseded by the contract) and history |

```bash
cd brains/wind
python -m venv venv && venv/bin/pip install -r runtime/requirements.txt -r research/tools/requirements.txt pytest
venv/bin/python -m pytest                         # production + research-tool tests (pytest.ini sets import roots)
venv/bin/python -m pytest -m network              # golden cells vs Open-Meteo (needs network)
PYTHONPATH=../../jobs/brain_platform venv/bin/python runtime/main.py hourly --store local:./archive
PYTHONPATH=../../jobs/brain_platform venv/bin/python runtime/main.py validate --store local:./archive --start 2026-09-22 --end 2026-10-05
deploy/deploy-job.sh --stage-only /tmp/wind-context  # assemble the exact image context, no gcloud
```

Decoder traps (hard tests): NBM alternating-row scanning; HRRR grid-relative U/V; every cycle runs a smoothness self-check and is not published if it fails. Deploy scripts refuse to run without `MICHAEL_APPROVED_WIND_DEPLOY=yes`; nothing here is deployed by the repository migration. Status, certification and cutover: `docs/architecture/certification/wind/`.
