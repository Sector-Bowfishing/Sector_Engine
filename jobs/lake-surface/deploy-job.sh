#!/usr/bin/env bash
#
# The daily lake-surface job: fresh Water Clarity for every directory lake,
# published to a public-read Cloud Storage bucket the engine and apps read.
#
#   bucket     gs://$BUCKET (public read; lakes/<slug>/clarity/…, index.json)
#   account    $SA — writes the bucket, and runs the job for the scheduler
#   job        $JOB — Cloud Run Job, $TASKS tasks, each every Nth lake
#   schedule   $SCHEDULE_JOB — daily at $CRON ($SCHEDULE_TZ), after the day's passes
#              have reached Earth Search
#
# Safe to re-run: existing pieces are kept, the job is redeployed from source.
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-sector-lake-surface}"
JOB="${JOB:-lake-surface-daily}"
SCHEDULE_JOB="${SCHEDULE_JOB:-lake-surface-daily}"
SA_NAME="${SA_NAME:-lake-surface-job}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
TASKS="${TASKS:-8}"
CRON="${CRON:-0 3 * * *}"
SCHEDULE_TZ="${SCHEDULE_TZ:-America/Chicago}"
cd "$(dirname "$0")"

echo "▶ bucket gs://$BUCKET"
if ! gcloud storage buckets describe "gs://$BUCKET" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$BUCKET" --project "$PROJECT_ID" \
    --location "$REGION" --uniform-bucket-level-access
  gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
    --member allUsers --role roles/storage.objectViewer >/dev/null
fi

echo "▶ service account $SA"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" \
    --display-name "Lake surface daily job"
fi
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member "serviceAccount:$SA" --role roles/storage.objectAdmin >/dev/null

# Memory: a build peaks at ~1.5 GB + 0.45 GB per million frame cells; 8 GiB
# with a 6.5 GB budget runs three small lakes at once, a big one alone.
echo "▶ job $JOB"
gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" \
  --service-account "$SA" \
  --tasks "$TASKS" --parallelism "$TASKS" --max-retries 1 \
  --cpu 2 --memory 8Gi --task-timeout 3h \
  --set-env-vars "BUCKET=$BUCKET,LAKE_WORKERS=3,MEM_BUDGET_GB=6.5"

gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:$SA" --role roles/run.invoker >/dev/null

echo "▶ schedule $SCHEDULE_JOB ($CRON $SCHEDULE_TZ)"
RUN_URI="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$JOB:run"
if gcloud scheduler jobs describe "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone "$SCHEDULE_TZ" --uri "$RUN_URI" --http-method POST \
    --oauth-service-account-email "$SA"
else
  gcloud scheduler jobs create http "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone "$SCHEDULE_TZ" --uri "$RUN_URI" --http-method POST \
    --oauth-service-account-email "$SA"
fi

echo
echo "✅ Run it now:   gcloud run jobs execute $JOB --project $PROJECT_ID --region $REGION"
echo "   Results:      https://storage.googleapis.com/$BUCKET/index.json"
