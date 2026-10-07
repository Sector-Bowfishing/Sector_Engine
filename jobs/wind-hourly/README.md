# wind-hourly (Wind Stage 2 candidate ingestion)

Pulls NOAA **NBM v4.3** (forecast: 10 m WIND/WDIR/GUST, plus qmd P10/P50/P90 wind and P90 gust on
00/06/12/18Z cycles), **RTMA-RU** (15-minute analysis, typed `analysis`), and **METAR/AWOS** via IEM
(typed `observed`, evidence and validation only), and archives per-lake grid cut-outs for
Guntersville, Wheeler, Wilson and Pickwick. Every forecast keeps init, valid, lead and retrieval
time, so validation uses forecasts that actually existed.

Candidate `wind-candidate-2026.10.stage2-baseline`. **Not production.** Nothing here reads or
writes production resources.

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt pytest
venv/bin/python -m pytest              # offline: decoder traps, conventions, scoring rules
venv/bin/python -m pytest -m network   # golden cells vs Open-Meteo (needs network)
venv/bin/python main.py hourly   --store local:./archive
venv/bin/python main.py backfill --store local:./archive --start 2026-09-22 --end 2026-10-05 --leads 1,3,6,12,18
venv/bin/python main.py validate --store local:./archive --start 2026-09-22 --end 2026-10-05
```

Decoder traps (hard tests): NBM alternating-row scanning; HRRR grid-relative U/V. Every cycle also
runs a row/column smoothness self-check and is **not published** if it fails.

`deploy-job.sh` is prepared but refuses to run without Michael's approval
(`MICHAEL_APPROVED_WIND_DEPLOY=yes`). It targets a new **private** bucket, never
`sector-lake-surface` or `sector-clarity-candidate`; `GcsStore` refuses those too.

## Stage 3A evidence and field-operations tools (read-only over the archive)

Mirror first: `gcloud storage rsync --recursive gs://sector-wind-candidate/wind/v1 $MIRROR` (or `./check-live.sh`).

| Command | What it answers |
|---|---|
| `python -m sector_wind.evidence status --store local:$MIRROR` | Archive health, skill by lead (+1…+18 h), event hits/misses/false alarms (INSUFFICIENT EVENTS below 10 observed), gust and direction diagnostics |
| `python -m sector_wind.evidence harvest --store local:$MIRROR` | Upcoming ≥ 10 / ≥ 15 mph and ≥ 20 kt gust windows with direction persistence, per lake |
| `python -m sector_wind.fieldops opportunities --store local:$MIRROR [--predictions …]` | Where and when to collect, ranked by validation information value (not by wind) |
| `python -m sector_wind.fieldops packet --store local:$MIRROR --lake L --night YYYY-MM-DD [--block 01\|03\|05] [--practice]` | One blind session folder: OBSERVER-SHEET.csv, SEALED-KEY.json, SESSION-README.txt, MAP-LINKS.txt |
| `python -m sector_wind.field_qa ingest EXPORT --observer X --date D` / `verify` / `qa RAW` | Write-once raw intake (hashed, read-only), and ELIGIBLE / INELIGIBLE / PRACTICE with reasons |
| `python -m sector_wind.field_run gaps\|calstatus\|diagnostics predictions.jsonl` | What strata are still needed; whether calibration may run; geometry/shelter miss clustering (calibration share only) |
| `python -m sector_wind.exemplars add\|review\|status` | Human-labelled photo exemplars; counted only after a second person agrees |
| `python -m sector_wind.overwater import FILE` / `compare --station ID` | Over-water station ingestion (height never assumed) and station vs RTMA vs NBM comparison |
| `python -m sector_wind.scoreboard --store local:$MIRROR --evidence-dir …/stage3a/evidence --log …/WIND_SCORE_CHANGE_LOG.jsonl` | The Candidate score, derived from the frozen rubric and evidence; append-only log |

None of these change the Candidate, the fetch method, the thresholds or the rubric, and none of them read holdout accuracy.
