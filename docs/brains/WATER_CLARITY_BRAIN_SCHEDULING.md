# Water Clarity Brain — scheduling decision (2026-10-13)

**Decision: the Water Clarity Brain stays MANUAL.** The `30 4 * * *` America/Chicago cron that
`brains/water-clarity/deploy/deploy-job.sh` would create was **not** created, and the job was not deployed.
`/brains/water-clarity` says `executionMode: MANUAL`, `deploymentStatus: NOT_DEPLOYED`.

## Why a daily cron is the wrong shape
- One fleet run reads `/conditions` for 621 lakes (27 min, `durationMs 1,640,062` on 2026-10-12) and every
  lake's `latest.json`. Sentinel-2 revisits a lake every 2–3 days and most passes are cloudy, so a daily run would
  republish 621 states of which only the dispatched subset (typically 0–40 lakes/day) has new satellite evidence.
- Its freshness rule (`staleAfterHours 26`) is a *display* rule, not a science cadence: the clarity state does not
  change until a new usable pass is rasterized by `lake-surface-daily`.
- It called the Cloud Run / Scheduler APIs to write `/health/jobs` records for jobs it does not own; those were
  stale whenever the Brain had not run. That code path is removed; `/jobs` is the Engine's one sync.

## Follow-up architecture (not built; needs approval)
1. **Dispatcher-driven publish.** `lake-surface-dispatch` already knows the work set each morning and writes
   `dispatch/<date>.json`. When the heavy run for that work set completes (the dispatcher can poll the execution,
   or the Orchestrator can read `/jobs/lake-surface-daily.lastSuccessfulAt` on its next wake-up), the Brain runs
   **for those lakes only** (`run.py --lakes …`, to be added) — a few lakes, seconds, not 27 minutes.
2. **Orchestrator trigger.** Register the Clarity Brain in `brain-orchestrator`'s `EXECUTORS` as a Cloud Run job
   with a `plan()` hook: PUBLISH when `/jobs/lake-surface-daily.lastSuccessfulAt` is newer than the Brain's
   `lastSuccessfulRun`, or when the Engine serving revision changed (the `/conditions` clarity path), else SKIP.
   This needs the Brain to publish `stalenessModel: "VERSION"` with a `fingerprint` (lake-surface run id +
   serving revision) instead of the 26-h TIME rule.
3. **Deploy as a scale-to-zero job** with `brains/water-clarity/deploy/deploy-job.sh` **minus** the scheduler block
   (delete the `gcloud scheduler jobs create` branch before running it), service account `water-clarity-brain`
   with `roles/firebasedatabase.admin` only (drop `run.viewer`/`cloudscheduler.viewer`, no longer needed).

Until then: `python3 brains/water-clarity/runtime/run.py --write` by hand after a satellite update worth publishing.
