# Pre-Production Recurring Job Inventory (cost freeze)

Inventory taken **2026-10-14 05:11Z** from live Cloud Scheduler / Cloud Run (project `sector-9393c`, us-central1), not from handoffs. Raw configs: `snapshots/` (scheduler + run-job JSON, taken before any change). Policy: **pre-production Brains are off by default**; see `PREPRODUCTION_COST_POLICY` in `../SECTOR_BRAIN_MODEL_V1.md`.

## 1. Every Brain-related scheduler job
| Scheduler job | Before | Cron (tz) | Target Cloud Run job | Image / rev | CPU / mem | Typical run | Last run | Owner | Customer dep.? | Validation dep.? | **After** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `brain-orchestrator` | ENABLED | `50 * * * *` UTC | `brain-orchestrator` (gen 8, `5fd727effa4a`) | brain-orchestrator@sha256:23ceb4d9… | 1 / 512Mi | 92 s | 04:50Z | Platform | no | indirectly (started Lake for the ledger) | **PAUSED** |
| `wind-hourly` | ENABLED | `5 * * * *` UTC | `wind-hourly` (gen 4, `e6a5026f5d0f`) | wind-hourly@sha256:410e7c46… | 1 / 2Gi | 198 s | 05:05Z | Wind | no (customers get Open-Meteo) | **yes** — live reliability ledger | **ENABLED (temporary)** |
| `water-temp-tva-archive` | ENABLED | `20 * * * *` UTC | `water-temp-tva-archive` (gen 2) | …@sha256:f2e45516… | 1 / 512Mi | 90 s | 04:20Z | Water Temp | no (Lake reads it) | indirect (Lake trend basis) | **PAUSED** |
| `lake-surface-dispatch` | ENABLED | `0 3 * * *` America/Chicago | `lake-surface-dispatch` (gen 2, `0d7e932f5d0e`) → starts `lake-surface-daily` | …@sha256:4e436e32… | 1 / 512Mi (+ heavy job 4 vCPU/16Gi × 8 tasks) | 133 s dispatch; heavy 52–74 min wall × 8 tasks | 08:00Z 10-13 | Clarity / Vegetation | **no** (`/clarity/*` is a review build, not routed in production) | no | **PAUSED** |
| `lake-brain-ledger-daily` | *(did not exist)* | `0 12 * * *` UTC | `lake-brain` (pilots, args baked) | brain-jobs:a9d1af8f749b | 1 / 1Gi | 103 s | — | Lake | no | **yes** — prospective prediction ledger | **ENABLED (temporary, new, see §3)** |
| `lake-surface-daily` | PAUSED | `0 3 * * *` Chicago | itself | | 4 / 16Gi × 8 | | | Clarity | | | PAUSED (unchanged) |
| `hydrology-hourly` | PAUSED | `15 * * * *` | | | | | | Clarity | | | PAUSED (unchanged) |
| `clarity-current-hourly` | PAUSED | `40 * * * *` | | | | | | Clarity | | | PAUSED (unchanged) |
| `clarity-candidate-shadow` | PAUSED | `0 7 * * *` Chicago | | | | | | Clarity | | | PAUSED (unchanged) |

Jobs **started by the orchestrator, with no scheduler of their own** (stop when it is paused): `lake-brain` (~8.4 runs/day, 103 s, 1 vCPU/1Gi), `water-temp-brain` (~4.7 runs/day, 356 s, 1 vCPU/1Gi), plus in-process Biological and Sector Intelligence `--plan`/`--write` (no-ops unless input/version changed) and the score/control publisher. No Depth, Vegetation or Biological/Intelligence scheduler exists.

## 2. Cloud Run services (Brain-related)
| Service | min / max | Note |
|---|---|---|
| `wind-candidate-read` | min unset (0) / max 2 | reads GCS bundles; scale-to-zero already; non-production candidate |
| `sector-engine` | **min 1** / max 30, 2 vCPU 1Gi | **customer production** — out of scope, untouched. Tagged revisions `clarity`, `fusion` have no min instance. It is the single largest always-on cost in the project (~$15–30/mo idle) |
| `adminlistusers`, `appstorenotifications`, `conditions`, `playnotifications`, `tournamentpage` | no min | not Brain-related |
No pre-production Brain Cloud Run **service** holds a minimum instance.

## 3. The four gate forms (jobs that survive or were challenged)
**JOB: `wind-hourly`** — WHAT PRODUCTION GATE: Wind live-reliability gate (30 valid live archive days, now 5 of 30; projected 2026-11-07) and the timed provider-forecast archive whose publication time/latency make it valid prospective evidence. IRREPLACEABLE DATA LOST IF PAUSED: each missed hour's NBM/RTMA/METAR capture and the valid-day clock itself (a day with gaps is not valid; NOAA's own history can reproduce forecasts but not the *live-retrieval* reliability being measured). WHY NOT MANUAL: the evidence is that it ran unattended on schedule. COST: ≈ **$4.1/mo** gross compute (198 s × 24 × 30 at 1 vCPU/2 GiB) + ~$0.05 storage (46 MB archive); 4 lakes only, not fleet. CUSTOMER DEPENDS: **NO**. STOP: reliability gate satisfied (≥ 30 valid live days, ≈ 2026-11-08) → then re-decide; or the Wind validation campaign ends. VERDICT: **KEEP TEMPORARILY**. Cheaper variant proposed, not applied (change denied by the permission classifier): drop `SECTOR_WIND_BRAIN_RTDB_URL` so the hourly run stops rewriting the Brain RTDB fleet (≈ 620 paths/h) and stops calling the Engine directory — the archive and ledger live in GCS and are unaffected → `COST_FREEZE_DECISION_QUEUE.md` C-1.

**JOB: `lake-brain-ledger-daily` (new, replaces 8 orchestrator-triggered runs/day)** — GATE: Lake prospective prediction ledger (≥ 90 days for PARTIAL item 4, ≥ 12 months for VALIDATED); calendar time cannot be bought later; started 2026-10-13T18:53Z. LOST IF PAUSED: one ledger day per day (headline stats use one line per lake per base date, so one run/day is sufficient). WHY NOT MANUAL: a missed day is permanently missing. COST: ≈ **$0.08/mo** (103 s/day). CUSTOMER: NO. STOP: Michael's decision on the Lake validation campaign, or the 90-day/12-month mark reached. VERDICT: **KEEP TEMPORARILY**; created because the orchestrator pause would otherwise have silently ended the ledger. Pause with one command (`PREPRODUCTION_PAUSED_JOBS.md`). Michael confirms: queue C-2.

**JOB: `water-temp-tva-archive`** — the challenge: TVA's RestApi keeps only recent hours, so this data is genuinely irreplaceable (8 days held since 2026-10-06, 2 MB). But the Water Temp docs classify it as discharge/level context "for a *future* residence-time and tailwater feature" — it carries no temperature and advances **no defined readiness gate**; the Water Temp gate is protected-truth lakes (Wilson/Wheeler forebay profiles) and the Level-4 comparison. Its only live consumer is the Lake Brain's 72 h trend for the four TVA pilot lakes; without it the Lake Brain falls back to the 24 h trend and *flags* it (`trend24hFallback`, recorded in each ledger line) — degraded, not corrupted. COST ≈ **$1.6/mo**. VERDICT: **PAUSE** (default policy; cannot be answered convincingly). Existing history kept. Trade-off for Michael: C-3.

**JOB: `lake-surface-dispatch` (+ heavy `lake-surface-daily`)** — GATE: none active (Clarity R3.1 is a certified candidate `NOT_DEPLOYED`; Vegetation V1 is a manual surface-only shadow). COST: the dispatch itself $0.10, but it starts the 8-task × 4 vCPU × 16 GiB job: the last two runs took 74 and 52 min wall → **$3.4–4.8 per run**; ≈ **$30–145/mo** depending on how many lakes have a new pass (observed daily). CUSTOMER: NO (`/clarity/*` "REVIEW BUILD … not routed in production", only tagged-revision test hits, last 2026-10-12). VERDICT: **PAUSE**. Manual invocation kept.

## 4. Cost baseline and result (list prices, us-central1 tier 1, **gross of free tier**)
Rates: $0.000024/vCPU-s, $0.0000025/GiB-s; Scheduler $0.10/job/month (paused jobs still count); RTDB $1/GB downloaded; GCS standard $0.02/GB-mo. Run time and frequency are measured from the last 40 executions of each job.

| Item | Runs/mo | Basis | Before $/mo | After $/mo |
|---|---|---|---|---|
| brain-orchestrator | 720–1000 | 92 s × 1 vCPU/0.5 Gi | 1.7 | 0 |
| lake-brain via orchestrator (8.4/day) | 250 | 103 s × 1 vCPU/1 Gi | 0.7 | — |
| lake-brain ledger daily | 30 | 103 s | — | 0.08 |
| water-temp-brain via orchestrator (4.7/day) | 140 | 356 s × 1 vCPU/1 Gi | 1.3 | 0 |
| water-temp-tva-archive | 720 | 90 s × 1 vCPU/0.5 Gi | 1.6 | 0 |
| wind-hourly | 720 | 198 s × 1 vCPU/2 Gi | 4.1 | 4.1 |
| lake-surface-dispatch | 30 | 133 s | 0.1 | 0 |
| **lake-surface-daily (heavy)** | 30 | 8 tasks × 4 vCPU/16 Gi × 52–74 min | **≈ 100 (30–145)** | 0 |
| Cloud Scheduler | 9–10 jobs | $0.10 each beyond free | 0.6 | 0.7 |
| RTDB download (publisher/orchestrator ≈ 1.2 MB × 720) + Ops | | | ≈ 0.9 | ≈ 0.1 |
| GCS storage (clarity-candidate 29 GB, lake-surface 0.4 GB, wind 47 MB, others small) | | kept, none deleted | 0.7 | 0.7 |
| **Recurring Brain total** | | | **≈ $112 (range $43–158)** | **≈ $5.7** |
| **Savings** | | | | **≈ $106/mo, ≈ 95 %** (range 90–96 %) |
Always-on/scheduled only (this table). Manual research cost (one-off Cloud Run runs, e.g. a Clarity backfill) and Claude/development cost are **not** included. Not Brain cost but larger than the entire remaining Brain bill: `sector-engine` customer service `min instances = 1` (≈ $15–30/mo idle). The Cloud Run free tier (240k vCPU-s, 450k GiB-s) is probably consumed by that service, so incremental billing applies. Remaining largest Brain item: **Wind hourly ≈ $4.1/mo**, then storage/scheduler pennies.

## 5. Provider/API and data-store effects
| Chain | Provider calls | Firebase | Storage |
|---|---|---|---|
| wind-hourly | NOAA NBM/RTMA-RU (AWS open data), IEM METAR — free | each run writes the Brain RTDB (4 wind-lake states + 621-lake readiness) and GETs the Engine directory | +~1.5 MB/day to `sector-wind-candidate` |
| tva archive | TVA RestApi, 10 GETs/h | none | ~0.3 MB/day |
| orchestrator | `/jobs` sync (Scheduler/Run APIs), Engine `/lakes` for Intelligence `--plan` | ~1.2 MB reads per cycle; ~620 control paths rewritten per cycle | none |
| lake-surface-daily | Earth Search STAC + Sentinel-2 COG reads (AWS), ~hundreds of scenes | none | ≤ 0.4 GB total; 29 GB clarity archive static |
| lake ledger | USGS/NWPS/TVA reads | 5 pilot lakes | ~6.5 KB/object |
