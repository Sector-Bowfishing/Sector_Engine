#!/usr/bin/env bash
#
# wind-hourly — PREPARED, NOT RUN. Wind Stage 2 cloud checkpoint: running this needs Michael's
# explicit approval (it creates a bucket, a service account, a Cloud Run Job and a schedule).
#
#   bucket    gs://$BUCKET (PRIVATE; wind/v1/… archive, never the shared lake-surface bucket)
#   account   $SA — writes only that bucket
#   job       $JOB — one task, hourly at :$MINUTE (NBM posts ~57 min after the cycle)
#
set -euo pipefail
if [[ "${MICHAEL_APPROVED_WIND_DEPLOY:-}" != "yes" ]]; then
  echo "Refusing: set MICHAEL_APPROVED_WIND_DEPLOY=yes only after Michael approves the wind-hourly deploy." >&2
  exit 2
fi
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-sector-wind-candidate}"
JOB="${JOB:-wind-hourly}"
SA_NAME="${SA_NAME:-wind-hourly-job}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
MINUTE="${MINUTE:-10}"
cd "$(dirname "$0")"

gcloud storage buckets describe "gs://$BUCKET" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://$BUCKET" --project "$PROJECT_ID" --location "$REGION" \
    --uniform-bucket-level-access --public-access-prevention
gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Wind hourly candidate job"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$SA" \
  --role roles/storage.objectAdmin >/dev/null
gcloud run jobs deploy "$JOB" --source . --project "$PROJECT_ID" --region "$REGION" \
  --service-account "$SA" --tasks 1 --max-retries 1 --task-timeout 900 --memory 2Gi --cpu 1 \
  --set-env-vars "SECTOR_WIND_GCS_APPROVED=yes" \
  --args="hourly,--store,gs://$BUCKET/wind/v1"
gcloud scheduler jobs describe "$JOB" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud scheduler jobs create http "$JOB" --location "$REGION" --project "$PROJECT_ID" \
    --schedule "$MINUTE * * * *" --time-zone UTC --http-method POST \
    --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB:run" \
    --oauth-service-account-email "$SA"
echo "deployed $JOB → gs://$BUCKET/wind/v1 (private)"
