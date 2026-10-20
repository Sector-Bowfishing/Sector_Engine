# Wind measurements activation runbook (prepared 2026-10-19, NOT executed)

**What it activates:** `/scores/wind/measurements` (`wind-score-measurements-v1`). This block holds:
- **Wind Capability** `wind-specialist-capability-v2`: **6.7**, ADOPTED by Michael 2026-10-19 "as written"; measured skill 28.25/61 + model capability 39/39; measured-only view 4.6.
- **Scientific Confidence:** LIMITED (statuses).
- **Production Readiness:** NOT_READY (gates).
- Certification 3.3 and BWIS v1 5.4, carried verbatim.

**What it does not do:**
- It does not change the certification value, version or breakdown.
- It emits no `score.changed` event.
- It does not touch any other Brain, the Publisher, the Wind job or any customer surface.
- It is not a bowfishing recommendation; that is Sector Intelligence's job.

**Who:** every step that deploys or writes needs Michael's explicit go-ahead for that step.

## What is already in place (PR #34)

| Piece | Behaviour |
|---|---|
| `score_brains.py --wind-measurements` | Attaches the envelope in RTDB-normal form. HELD (not attached) if the envelope is inconsistent or the evidence is missing. Defaults OFF. |
| `orchestrate.score_cmd()` | Adds the flag only when the job env has `WIND_MEASUREMENTS=on`. |
| `deploy-job.sh` | `WIND_MEASUREMENTS=${WIND_MEASUREMENTS:-off}`. Refuses any value other than `on` or `off`. Passes it in `--set-env-vars`. Stages the rubric and evidence (brain.json is already staged). |
| Tests | Switch default off; image layout attaches 3.3 / 6.7 ADOPTED / LIMITED / NOT_READY; missing evidence → HELD; no RTDB-illegal keys; an identical hourly re-run does not rewrite `/scores/wind`. |

## Read-only production dry run (done 2026-10-19, nothing written)

`python3 jobs/brain-scores/score_brains.py --wind-measurements --report …` against the live Brain RTDB returned:
- wind 3.3 unchanged, measurements attached (12 KB), Capability 6.7 ADOPTED, runtimeHealth OPEN (HEALTHY);
- planned changes: `wind: breakdown refreshed (displayed 3.3 unchanged)` and **`engine: 7.2 → 7.0`**.

**About the Engine move:** it is **not caused by Wind**. The same dry run without the flag gives the same `engine: 7.2 → 7.0`; it comes from runtimeReliability, the finding already reported with PR #33. **Any** scorer `--write`, with or without this flag, will publish it. Decide that move separately before step 3.

The dry run also caught and fixed two defects before any write:
1. **RTDB-illegal keys.** `Freshness/reliability` was used as a key. One such key would have failed the whole multi-path update, scores included.
2. **Hourly rewrite churn.** Clock timestamps and nulls would have made `/scores/wind` rewrite on every run with no real change.

## Steps

1. **Merge PR #34** (approval). This changes nothing in production. It may land before or after PR #33: the trial merge is conflict-free and tests pass.

2. **Preview the deploy** from the merged `main` checkout:
   ```bash
   DRY_RUN=1 WIND_MEASUREMENTS=on jobs/brain-orchestrator/deploy-job.sh
   ```
   This prints the gcloud commands. Check that `--set-env-vars` ends with `WIND_MEASUREMENTS=on` and that the lineage preflight and stale-score guard pass. (DRY_RUN still stages the image context locally and runs the read-only `describe` checks.)

3. **Deploy** (shared-orchestrator deploy; approval; `preflight_lineage.py` applies):
   ```bash
   WIND_MEASUREMENTS=on jobs/brain-orchestrator/deploy-job.sh
   ```
   The scheduler stays **PAUSED** (cost freeze) unless `SCHEDULE_STATE=enabled` is also given. Do not give it as part of this activation.

4. **Dry cycle in the cloud** (writes nothing):
   ```bash
   gcloud run jobs execute brain-orchestrator --region us-central1 --args=--dry-run --wait
   ```

5. **Publish once** (approval). This writes `/scores` and `/control`, including the Engine 7.0 move above:
   ```bash
   gcloud run jobs execute brain-orchestrator --region us-central1 --args=--force-scores --wait
   ```
   This is the same path every scorer publish takes. **Do not** publish with a local `score_brains.py --write --wind-measurements` while the deployed orchestrator lacks the switch: its next score write would remove the block again.

6. **Read back** (read-only), and confirm:
   - `/scores/wind/value == 3.3` and `scoreVersion == wind-certification-rubric-v1`;
   - `/scores/wind/measurements/windCapability/value == 6.7` and `rubricStatus == ADOPTED`;
   - there is no new `score.changed` activity event for wind;
   - Sector Ops still renders Wind 3.3. Ops has no tile for the measurements yet; showing them is a separate, scoped Ops change that renders the Engine's numbers verbatim.

## Rollback

```bash
WIND_MEASUREMENTS=off jobs/brain-orchestrator/deploy-job.sh
```

Then run one scorer publish (step 5). The wind block is computed without `measurements`, its content differs from what is published, so `/scores/wind` is rewritten whole and the node disappears. No event, no value change.

## Not part of this activation
- Producing the Wind exposure assessment from `wind-hourly` (a Wind deploy).
- A Publisher contract for it (after Wind's cutover turn: Water Clarity → Fish → Wind).
- Sector Intelligence consuming it.
- A real certification refresh.
- Enabling the scheduler.

Each of these remains its own approval.
