# Cost-efficient jobs, scheduling & orchestration — implementation record (2026-10-13)

Branch `feat/cost-efficient-scheduling` (from `main` @ e596a6bb). Follows the read-only audit
`JOBS_SCHEDULES_COST_AUDIT_2026-10-13.md`. Customer boundary respected throughout: no `sector-engine`
revision, traffic, tag or minScale change; no candidate promotion; no 5A; no customer science or app change;
no private Clarity exposure; nothing deleted (schedulers paused, not removed).

## Schedule matrix — before → after

| Workload | Before (audit) | After | Class |
|---|---|---|---|
| `wind-hourly` | `5 * * * *` UTC, re-reads the newest NBM cycle every run | same cron; **NBM early exit** when the newest cycle is already archived complete for every lake; redeployed from main (`main@e6a5026f`, Brain publish on the contract code) | INTERNAL (science RESEARCH_CANDIDATE) |
| `water-temp-tva-archive` | `20 * * * *` UTC | unchanged (source retains ~24 h) — full `/jobs` record | INTERNAL |
| `hydrology-hourly` | `15 * * * *` UTC, ENABLED | **PAUSED** (kept) | RESEARCH |
| `clarity-current-hourly` | `40 * * * *` UTC, ENABLED | **PAUSED** (kept) | RESEARCH |
| `lake-surface-daily` | `0 3 * * *` CT: 8 tasks × 4 vCPU / 16 Gi for all 621 lakes, 74–87 min | **dispatcher-triggered** only for lakes with a newer pass, task count sized to the work; its scheduler PAUSED (kept); image untouched (D4 exception) | INTERNAL |
| `lake-surface-dispatch` (new) | — | `0 3 * * *` CT, single task 1 vCPU / 512 Mi, ~17 s discovery over 599 outlines; attempted-pass ledger so a rejected pass is never re-read | INTERNAL |
| `clarity-candidate-shadow` | PAUSED | PAUSED (stays) | SHADOW |
| `lake-brain` (new job) | manual `swift run`, state stale (last 2026-10-12 23:46) | scale-to-zero Cloud Run job, **orchestrator-triggered** (TIME, staleAfterHours 3), pilot 5 lakes, no cron | INTERNAL |
| `water-temp-brain` (new job) | never deployed (script would have created `25 */3 * * *`) | scale-to-zero Cloud Run job, **orchestrator-triggered** only when the 6-h rule requires, fleet, no cron | INTERNAL |
| `water-clarity-brain` | manual; its script would create a daily cron | **MANUAL by decision** (`docs/brains/WATER_CLARITY_BRAIN_SCHEDULING.md`); no longer writes other jobs' records | INTERNAL |
| `biological-brain` | manual | in-process in the orchestrator when its own `plan()` says PUBLISH (VERSION); no cron | INTERNAL |
| `sector-intelligence-brain` | manual | in-process when its `plan()` says PUBLISH (FINGERPRINT), pilot only; no cron | INTERNAL |
| `brain-scores` | manual | in-process after a Brain state change (`--if-changed`) | INTERNAL |
| `brain-orchestrator` (new) | design only (D10) | `50 * * * *` UTC wake-up, 1 vCPU / 512 Mi, scale-to-zero | INTERNAL |
| `sector-engine`, Cloud Functions | — | unchanged; classified PRODUCTION in `/jobs` | PRODUCTION |

## What was built
- **`/jobs/{jobId}` contract (jobs-v1)** — `docs/brains/JOBS_CONTRACT.md`; `sector_brain_platform/jobs.py` (+`gcp.py`).
  Cloud Scheduler authoritative for enabled/cron/timezone/nextScheduledAt; executions for runtime; manifest for
  design facts; cost metadata without dollars. Platform-only root (Python, Swift, conformance fixture + 4 cases).
  Published by the orchestrator (one canonical path). 21 records live.
- **Ops read access** — the Ops repo had already committed and deployed rules for `jobs`, `control`, `scores`,
  `engine` (verified live: opsUsers read-only, nothing public). Decision recorded in `OPS_CONTROL_PLANE_CONTRACT.md`:
  `/control/overview` is the Engine summary; no `/engine/summary` projection.
- **Compact fleet summary** — `/control/overview/fleet` (`fleet_summary()`): counts per slot/readiness, stale,
  evidence-stale, issues, newest update; Overview no longer needs 621 `/lakeFleet` rows. Plus `/control/overview/jobs`.
- **Orchestrator executor** — `jobs/brain-orchestrator` (design updated in `ORCHESTRATOR_DESIGN.md`).
- **Satellite dispatcher** — `jobs/lake-surface-dispatch` (least-privilege SA `lake-surface-dispatch`: custom role
  `jobRunnerWithOverrides` on `lake-surface-daily` only, `storage.objectUser` on the bucket).
- **Brain jobs image** — `jobs/brain-image-build.sh` builds the Engine Dockerfile (now also `LakeBrainJob`) to
  `brain-jobs:<commit>` with Cloud Build; `jobs/lake-brain` / `jobs/water-temp-brain` deploy jobs from it. SA
  `brain-writer` (`firebasedatabase.admin`, `run.viewer`, `cloudscheduler.viewer`, job-level `run.invoker`, bucket reads).
- **Warm-tag guard** — `ops/check_warm_tags.sh`, `deploy.sh --check-warm-tags`, post-promote report. Current state: ✓
  (no tagged 0 % revision with minScale ≥ 1; `00080-wes` carries minScale 1 and serves 100 %).
- **Optional CI** — `.github/workflows/python-jobs-tests.yml`, offline, no credentials.

## Measurements
- Wind: `run_hourly` itself 72–79 s; a full execution ≈ 3.8 min (≈ 1 min container start + ≈ 90 s Wind Brain publish
  after the ingest). The scheduled 05:05 run after a manual 04:59 run skipped the already-archived 04Z cycle:
  **110 s** vs 20-run average 202 s. In steady state every hourly run finds a new NBM cycle (posted ~:57), so the
  guard saves time only on extra/late runs; the Brain publish, not the ingest, is the larger fixed cost.
- Dispatcher discovery (cloud, 599 outlines, 8 workers): **17 s**; first work set 299 lakes (267 newer tile-level
  pass, 32 never published) — the heavy job rejects most of those once it reads the lake, which is why the
  attempted-pass ledger exists: each rejected pass is read once, not daily until the next revisit.
- Orchestrator live cycle: ~8 s + the in-process publishes (`/jobs` sync + plan + Intelligence publish ≈ 1 min).
- Estimated job compute after (from `/jobs` cost metadata, cron × avg runtime × resources): wind 1.35 vCPU-h/day,
  TVA archive 0.57, orchestrator ≈ 0.5 (first cycles 151 s incl. dry runs; expected < 1 min), dispatcher 0.05,
  lake-brain/water-temp-brain ≈ 0.2–0.4 (8 × 8 s + 4 × 4.4 min), lake-surface-daily now proportional to real work.
  Before: lake-surface-daily ≈ 9.6 vCPU-h/day (67 vCPU-h + 271 GiB-h per 7 d), hydrology 0.93, clarity-current 1.5.

## First live cycle
(filled below after execution)
