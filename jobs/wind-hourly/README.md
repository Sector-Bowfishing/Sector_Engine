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
