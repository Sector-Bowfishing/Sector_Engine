#!/usr/bin/env bash
#
# The hourly hydrology-inputs job (Clarity Fusion Stage 1 item 3): rain over
# each arm's drainage, each arm's flow with provenance, TVA at both dams,
# published to gs://$BUCKET for the engine. Safe to re-run.
#
#   job        $JOB — Cloud Run Job, 1 task, runs as the lake-surface SA
#   schedule   $SCHEDULE_JOB — hourly at minute 15 (MRMS Pass 2 lags ~2 h)
#
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-sector-lake-surface}"
JOB="${JOB:-hydrology-hourly}"
SCHEDULE_JOB="${SCHEDULE_JOB:-hydrology-hourly}"
SA="${SA:-lake-surface-job@$PROJECT_ID.iam.gserviceaccount.com}"
CRON="${CRON:-15 * * * *}"
cd "$(dirname "$0")"

# The aggregator and the lake's data come from the repo, not a copy kept here.
cp ../../scripts/hydrology/catchment_rain.py .
cp ../../docs/data/hydrology/guntersville/guntersville.mrms_weights.json mrms_weights.json
cp ../../docs/data/hydrology/guntersville/guntersville.hydrology.json hydrology.json

echo "▶ job $JOB"
gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --tasks 1 --max-retries 1 --cpu 1 --memory 2Gi --task-timeout 90m \
  --set-env-vars "BUCKET=$BUCKET,LAKE_SLUG=Guntersville_AL,BACKFILL_HOURS=720"
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:$SA" --role roles/run.invoker >/dev/null

echo "▶ schedule $SCHEDULE_JOB ($CRON UTC)"
RUN_URI="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$JOB:run"
if gcloud scheduler jobs describe "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone UTC --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA"
else
  gcloud scheduler jobs create http "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone UTC --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA"
fi
echo "✅ Run it now: gcloud run jobs execute $JOB --project $PROJECT_ID --region $REGION"
