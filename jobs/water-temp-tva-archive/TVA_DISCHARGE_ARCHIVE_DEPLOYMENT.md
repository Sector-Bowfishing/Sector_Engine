# TVA discharge archive: deployment record

**Deployed 2026-10-07** with Michael's explicit approval (Stage 2D instructions, Part E). This is **development infrastructure** for the Water Temp track. It does not change the Water Temp score, and no Water Temp model or production surface reads this data.

| Item | Value |
|---|---|
| GCP project | `sector-9393c` (us-central1) |
| Cloud Run **job** | `water-temp-tva-archive` (1 task, 1 vCPU / 512 MiB, 10 min timeout, 1 retry) |
| Cloud Scheduler | `water-temp-tva-archive`, `20 * * * *` **UTC** (hourly at :20), HTTP POST to the job's `:run`, OAuth token, scope cloud-platform |
| Service account | `water-temp-archive-job@sector-9393c.iam.gserviceaccount.com`. Roles: `storage.objectAdmin` on this bucket only; `run.invoker` on this job only. |
| Bucket | `gs://sector-water-temp-archive`: **private**, `public_access_prevention: enforced`, uniform bucket-level access, US-CENTRAL1 |
| Prefix | `water-temp/tva/` |
| Dams | NKJT1 (Nickajack), GVDA1 (Guntersville), WHLA1 (Wheeler), WLSA1 (Wilson), PICT1 (Pickwick) |
| Source | `https://www.tva.com/RestApi/observed-data/<DAM>.json` and `/predicted-data/<DAM>.json` (`Accept: application/json`) |
| Code | `Sector_Engine` branch `intelligence/water-temp`, `jobs/water-temp-tva-archive/` |
| Deployment commits | `19b108d6` (archiver), `fb1e836d` (job-scoped invoker), `b854f501` (Midnight/Noon parsing; **deployed revision**) |
| Alerting | Cloud Monitoring policy **"Water Temp TVA archive failing"** (`projects/sector-9393c/alertPolicies/6142279662462198213`) → email channel "Sector engine alerts (mgcather07@gmail.com)". Fires on any failed execution, or no successful execution for 3 h. |
| Logs | Cloud Logging, `resource.type="cloud_run_job" resource.labels.job_name="water-temp-tva-archive"`. One JSON line per dam per run; errors go to stderr. |

## Layout

```
water-temp/tva/raw/<DAM>/observed/<YYYY-MM-DDTHH>Z.json    exact response bytes (one per fetch hour)
water-temp/tva/raw/<DAM>/predicted/<YYYY-MM-DDTHH>Z.json
water-temp/tva/<DAM>/<YYYY-MM-DD>.json                     daily record (local date of the hour-ending label)
    observed[<ISO local hour>] = {raw, parsed, firstSeenAt}   never overwritten
    revisions[]                = later fetches whose values differ
    predicted[<fetch hour>Z]   = {fetchedAt, rows}            kept separate from observed
```

**Time convention.** TVA times are **hour-ending labels**. `"10/06/2026 Midnight CDT"` follows `"10/06/2026 11 PM CDT"` and is stored as `2026-10-07T00:00:00-05:00`. "Noon" is 12:00. Raw strings are always kept.

## Separation (verified 2026-10-07)

- **New resources only.** The job, schedule, service account and bucket are all new. No name collides with existing resources: `hydrology-hourly`, `lake-surface-daily`, `clarity-current-hourly`, `clarity-candidate-shadow`, `wind-hourly`; `gs://sector-lake-surface` and `gs://sector-clarity-candidate`.
- **Clarity untouched.** Clarity's `hydrology-hourly` was not modified; it kept running on its own schedule.
- **No production traffic touched.** `sector-engine` traffic is unchanged (100 % `sector-engine-00044-b6m`; tag `clarity` → `00071-cuw`). No Cloud Run service was deployed.

## Verification (2026-10-07)

1. **Tests.** 14 passed: the 13 from Stage 2C plus one for the hour-ending Midnight/Noon labels.
2. **First live execution (`water-temp-tva-archive-cv782`) FAILED loudly, exit 1, nothing written.** All five dams raised `SchemaError: unexpected Time format: 'Midnight CDT'`. The schema guard worked as designed. I fixed the parser (hour-ending convention), added a test, and redeployed.
3. **Execution `water-temp-tva-archive-b6jc8` succeeded.** All 5 dams were fetched, 8 new observed hours each. Raw observed and predicted files were written (10). Daily files were written for 2026-10-06 and 2026-10-07 (10).
4. **Idempotency.** Execution `water-temp-tva-archive-vg5hk`, a rerun in the same hour, succeeded with 0 new hours, 0 revisions and no new predicted snapshot. The `WLSA1/2026-10-06.json` object generation was unchanged (`1791352349692510`).
5. **Scheduler.** ENABLED, `20 * * * *` UTC, next run 06:20Z.

## Operate

- **Pause:** `gcloud scheduler jobs pause water-temp-tva-archive --location us-central1`
- **Run now:** `gcloud run jobs execute water-temp-tva-archive --region us-central1 --wait`
- **Redeploy:** `I_HAVE_MICHAELS_APPROVAL=yes ./deploy-job.sh` (idempotent)
- **Inspect:** `gcloud storage ls -r gs://sector-water-temp-archive/water-temp/tva/`
- **Cost:** negligible (one ~10 s execution per hour and a few KB per dam-day).
