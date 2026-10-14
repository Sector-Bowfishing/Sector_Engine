# Running a Brain manually during the freeze

Nothing here needs a schedule. Run, test, publish if needed, and the cloud goes quiet again. Jobs/targets/IAM were not changed, so every command below still works.

| Goal | Command |
|---|---|
| Orchestrator plan, no side effects | `gcloud run jobs execute brain-orchestrator --region us-central1 --args=--dry-run --wait` |
| Full orchestrator cycle (starts what is stale, publishes scores/control if state changed) | `gcloud run jobs execute brain-orchestrator --region us-central1 --wait` (add `--args=--force-scores` to publish regardless) |
| Lake Brain (pilots) | `gcloud run jobs execute lake-brain --region us-central1 --wait` |
| Water Temp Brain (fleet) | `gcloud run jobs execute water-temp-brain --region us-central1 --wait` |
| Scores / control only, from a checkout | dry run: `python3 jobs/brain-scores/score_brains.py --if-changed`; publish: add `--write` (stale-score guard applies; override only `SCORE_GUARD_ALLOW=<brainId>`) |
| Biological | `cd jobs/biological-brain && python3 run.py --plan` then `--write` |
| Sector Intelligence | `cd jobs/sector-intelligence-brain && python3 run.py --plan` then `--write` |
| Satellite scene discovery (Clarity/Vegetation) | `gcloud run jobs execute lake-surface-dispatch --region us-central1 --args=--dry-run --wait` first; a real run starts the heavy 8×4 vCPU job for lakes with new passes (≈ $3–5/run) |
| TVA archive snapshot | `gcloud run jobs execute water-temp-tva-archive --region us-central1 --wait` (only captures what TVA currently serves) |
| Wind, extra capture | `gcloud run jobs execute wind-hourly --region us-central1 --wait` |
Depth, Vegetation, Biological and Intelligence have no cloud job at all: run them from the specialist branch locally.
After a manual run, check the bill driver with `gcloud run jobs executions list --job <name> --region us-central1 --limit 3` and leave schedulers as they are.

## Staying paused
`jobs/brain-orchestrator/deploy-job.sh` now leaves the scheduler PAUSED unless `SCHEDULE_STATE=enabled` is given with a recorded gate; `jobs/brain-orchestrator/check_preproduction_schedules.py` (read-only) fails when an enabled Brain scheduler is not on the allowlist in `schedule-policy.json`.
