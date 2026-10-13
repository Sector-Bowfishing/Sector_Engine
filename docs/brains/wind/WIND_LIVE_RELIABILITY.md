# Wind live reliability clock (audited 2026-10-13 19:10Z)

**Method:** `jobs/wind-hourly/research/live_reliability.py` over operational metadata only (ingest ledger status lines, run counters/errors, Cloud Run execution status, Brain-publish status lines). No forecast, analysis, observation or state value from the sealed H2 period was opened. A UTC day is VALID only if the frozen rule in `WIND_VALIDATION_PHASE_PREREG.md §L` holds on every live lake: ≥ 99% of 24 hourly NBM cycles `complete`, ≥ 95% of 96 RTMA-RU quarter-hours, METAR day count present, no state-refresh gap > 90 min, no failed execution. The scheduler running is not evidence.

## Result
| UTC day | NBM complete (worst lake) | RTMA-RU (worst lake) | METAR obs | Exec / max gap | Verdict | Reason |
|---|---|---|---|---|---|---|
| 2026-10-07 | 24/24* | 89/96 (92.7%) | 378 | 23 / 60 min | **INVALID** | Live clock started 04:59Z (first run 05:01Z, only 19 live hourly cycles possible); RTMA 92.7% < 95%. (*hours 00–04Z were backfilled, not live) |
| 2026-10-08 | 24/24 | 96/96 | 426 | 24 / 60 min | VALID | |
| 2026-10-09 | 24/24 | 96/96 | 416 | 24 / 60 min | VALID | one NBM cycle (00Z) first archived `partial`, completed by catch-up |
| 2026-10-10 | 24/24 | 96/96 | 440 | 24 / 60 min | VALID | |
| 2026-10-11 | 24/24 | 96/96 | 453 | 24 / 60 min | VALID | 12Z NBM partial then completed; RTMA 21:45Z attempt failed once, filled by catch-up |
| 2026-10-12 | 24/24 | 96/96 | 441 | 24 / 60 min | VALID | 06Z and 12Z partials completed; redeploy at ≈ 06:30Z with a 15-minute Brain-RTDB 401 window (see below) did not break the archive |
| 2026-10-13 | 19/24 (so far) | 76/96 (so far) | — | open | OPEN | day not finished |

**Valid live days: 5 (2026-10-08 … 2026-10-12). Invalid: 1 (10-07). Open: 1.**

## Totals since the clock started (2026-10-07 04:59Z)
- Executions: **164, 0 failed** (median run 202 s, max 446 s). Scheduler cadence hourly at :05; median gap between successful runs 60 min, max 60.3 min.
- Ledger: NBM 744 complete (+24 partial, all 24 resolved to complete by the 3–4 h catch-up); RTMA-RU 2,580 complete (+4 failed attempts, one 21:45Z quarter-hour, recovered); METAR 182 complete.
- **Availability** (day-level, worst lake): 100% NBM and 100% RTMA-RU on all five valid days. **Freshness:** a cycle's first complete archive time after init: median 1.14 h, p95 2.15 h, max 2.17 h (n = 632 lake-cycles since 05Z 10-07) — NBM posts ≈ 1 h after init, so this is the product floor, not job lag. **Failure rate:** 0 failed executions; 4 transient RTMA failures of 2,584 attempts (0.15%). **Stale rate:** 0 stale Brain states of 156 lake-states logged.
- **Malformed state:** none observed (39 Brain publishes `ok`, 0 schema errors). **Unexpected churn:** none — all 156 logged lake-states are `analysis / CALIBRATION / not stale`.

## Brain publish chain (separate, stricter)
- First Brain publish attempt 2026-10-12 06:38Z failed twice with HTTP 401 (IAM propagation, documented in `BRAIN.md`; the archive was unaffected); first successful publish **2026-10-12 06:55Z**; 39 successes since, hourly, 0 failures after the fix.
- First complete Brain-publish UTC day: **2026-10-13** (in progress, 21 of 21 expected so far OK).

## 30-live-day gate (projected from evidence, not from the old estimate)
| Gate | Definition | Valid days so far | Earliest eligibility if every remaining day is valid |
|---|---|---:|---|
| **Archive (certification dim 8 / BWIS E2 basis)** | 30 valid days of the Candidate `wind-hourly` ledger | 5 | 30th valid day = **2026-11-06**; closes 2026-11-07 00:00Z and verifies ≈ **2026-11-07 03:00Z**. The old estimate (≈ 2026-11-07) **holds only if no further day is invalid**; each invalid day moves it one day later. |
| **Brain publish (production-readiness basis)** | 30 valid days of successful hourly Brain state publication | 0 complete (10-13 open) | 30th day = 2026-11-11; verifies ≈ **2026-11-12 03:00Z** |

## Risks to the clock
1. **Redeploys.** Deploying `feat/cost-efficient-scheduling` (wind early-exit, `/jobs` contract) or this adoption branch changes the running job; the day of any deploy should be audited for partial cycles before it counts. No deploy is made here.
2. NBM or RTMA source outages (NOAA S3) are not controllable; catch-up windows cover ≈ 3–4 h only.
3. The 90-minute state-refresh rule assumes the hourly schedule; a missed run followed by a late one can invalidate a day.
4. Day 10-07 shows backfilled hours must never be counted as live.

## Re-running
`gcloud storage cp -r gs://sector-wind-candidate/wind/v1/{ledger,runs} <meta>/`, `gcloud run jobs executions list --job wind-hourly --region us-central1 --format=json > <meta>/executions.json`, `gcloud logging read '… textPayload:"windbrain"' > <meta>/brainlogs.json`, then `python research/live_reliability.py <meta> out.json`. Data copy: `docs/brains/wind/data/live_reliability_asof_2026-10-13.json`.
