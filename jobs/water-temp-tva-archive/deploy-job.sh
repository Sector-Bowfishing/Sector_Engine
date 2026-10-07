#!/usr/bin/env bash
#
# Water Temp TVA discharge archiver — NOT YET DEPLOYED. Requires Michael's explicit
# approval before this script is run. Completely separate from Clarity's
# hydrology-hourly job: own private bucket, own service account, own job and
# schedule. Touches no Cloud Run service and no production traffic.
#
#   bucket     gs://$BUCKET  (PRIVATE: uniform access, public access prevention)
#   account    $SA — writes only this bucket, runs the job for the scheduler
#   job        $JOB — 1 task, small
#   schedule   $SCHEDULE_JOB — hourly at :20 (TVA keeps ~8 h of observed rows,
#              so a few missed runs lose nothing)
#
set -euo pipefail
if [[ "${I_HAVE_MICHAELS_APPROVAL:-}" != "yes" ]]; then
  echo "Refusing to deploy: set I_HAVE_MICHAELS_APPROVAL=yes after Michael approves." >&2
  exit 2
fi

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-sector-water-temp-archive}"
JOB="${JOB:-water-temp-tva-archive}"
SCHEDULE_JOB="${SCHEDULE_JOB:-water-temp-tva-archive}"
SA_NAME="${SA_NAME:-water-temp-archive-job}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
CRON="${CRON:-20 * * * *}"
cd "$(dirname "$0")"

echo "▶ private bucket gs://$BUCKET"
if ! gcloud storage buckets describe "gs://$BUCKET" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$BUCKET" --project "$PROJECT_ID" \
    --location "$REGION" --uniform-bucket-level-access --public-access-prevention
fi

echo "▶ service account $SA"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" \
    --display-name "Water Temp TVA archive job"
fi
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member "serviceAccount:$SA" --role roles/storage.objectAdmin >/dev/null

echo "▶ job $JOB"
gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --tasks 1 --max-retries 1 --cpu 1 --memory 512Mi --task-timeout 10m \
  --set-env-vars "WT_ARCHIVE_BUCKET=$BUCKET,WT_ARCHIVE_PREFIX=water-temp/tva"

echo "▶ schedule $SCHEDULE_JOB ($CRON UTC)"
URI="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$JOB:run"
# least privilege: the SA may invoke THIS job only (same pattern as hydrology-hourly)
gcloud run jobs add-iam-policy-binding "$JOB" --region "$REGION" --project "$PROJECT_ID" \
  --member "serviceAccount:$SA" --role roles/run.invoker >/dev/null
if gcloud scheduler jobs describe "$SCHEDULE_JOB" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULE_JOB" --location "$REGION" --project "$PROJECT_ID" \
    --schedule "$CRON" --time-zone UTC --uri "$URI" --http-method POST --oauth-service-account-email "$SA" --oauth-token-scope https://www.googleapis.com/auth/cloud-platform
else
  gcloud scheduler jobs create http "$SCHEDULE_JOB" --location "$REGION" --project "$PROJECT_ID" \
    --schedule "$CRON" --time-zone UTC --uri "$URI" --http-method POST --oauth-service-account-email "$SA" --oauth-token-scope https://www.googleapis.com/auth/cloud-platform
fi
echo "✓ deployed. Run once now: gcloud run jobs execute $JOB --region $REGION"
