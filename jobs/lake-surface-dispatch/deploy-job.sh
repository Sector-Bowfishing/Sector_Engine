#!/usr/bin/env bash
#
# lake-surface-dispatch: the cheap daily Sentinel-2 discovery job that starts lake-surface-daily
# only for lakes with a newer pass (cost work 2026-10-13, Phase 8). Single task, 1 vCPU / 512 Mi.
#
# Least privilege: its own service account `lake-surface-dispatch` with
#   roles/run.invoker            on job lake-surface-daily only (job-level, not project-level)
#   roles/storage.objectUser     on gs://$BUCKET (dispatch/<date>.json summaries + the attempted-pass ledger, overwritten daily; latest.json is read publicly)
# It never redeploys lake-surface-daily (live source is feat/clarity-algal-warning @ 03937913 — LINEAGE.md).
#
# The schedule MOVES from lake-surface-daily to this job: the old scheduler is PAUSED (not deleted) and a new
# `lake-surface-dispatch` scheduler fires at the same 03:00 America/Chicago.
#
#   ./deploy-job.sh                   build + deploy the job, bind IAM, create/update the scheduler, pause the old one
#   DRY_RUN=1 ./deploy-job.sh         print the commands only
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-sector-lake-surface}"
JOB="${JOB:-lake-surface-dispatch}"
HEAVY_JOB="${HEAVY_JOB:-lake-surface-daily}"
OLD_SCHEDULE_JOB="${OLD_SCHEDULE_JOB:-lake-surface-daily}"
SA_NAME="${SA_NAME:-lake-surface-dispatch}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
CRON="${CRON:-0 3 * * *}"
SCHEDULE_TZ="${SCHEDULE_TZ:-America/Chicago}"
COMMIT="$(git -C "$(dirname "$0")" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
run() { if [[ "${DRY_RUN:-0}" == "1" ]]; then echo "+ $*"; else "$@"; fi; }
cd "$(dirname "$0")"

echo "▶ service account $SA"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  run gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Lake surface dispatch (satellite discovery)"
fi
run gcloud run jobs add-iam-policy-binding "$HEAVY_JOB" --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:$SA" --role roles/run.invoker
run gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectUser

echo "▶ job $JOB (commit $COMMIT)"
cp ../lake-surface/polygons.geojson.gz .
rm -rf sector_brain_platform && cp -R ../brain_platform/sector_brain_platform .
trap 'rm -rf polygons.geojson.gz sector_brain_platform' EXIT
run gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --tasks 1 --max-retries 1 --cpu 1 --memory 512Mi --task-timeout 20m \
  --labels "commit=$COMMIT" \
  --set-env-vars "BUCKET=$BUCKET,HEAVY_JOB=$HEAVY_JOB,BRAIN_TOKEN_MODE=metadata"
run gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:$SA" --role roles/run.invoker

echo "▶ schedule $JOB ($CRON $SCHEDULE_TZ); pause $OLD_SCHEDULE_JOB"
RUN_URI="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$JOB:run"
if gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  run gcloud scheduler jobs update http "$JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone "$SCHEDULE_TZ" --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA"
else
  run gcloud scheduler jobs create http "$JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone "$SCHEDULE_TZ" --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA"
fi
if gcloud scheduler jobs describe "$OLD_SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" --format 'value(state)' 2>/dev/null | grep -q ENABLED; then
  run gcloud scheduler jobs pause "$OLD_SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION"
fi
echo "✅ $JOB deployed. Discovery only: gcloud run jobs execute $JOB --region $REGION --args=--dry-run"
