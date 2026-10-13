#!/usr/bin/env bash
#
# NOT RUN YET — needs Michael's go (see docs/brains/WATER_CLARITY_BRAIN_INTEGRATION.md, "Deployment").
#
# The Water Clarity Brain publisher: restates production Clarity (Engine
# /conditions + gs://sector-lake-surface) into the dedicated Brain RTDB
# (sector-brain) that Sector Ops reads. It is its own job: it reads production
# and never writes to it, so a Brain RTDB outage cannot affect customer Clarity.
#
#   account    $SA: writes the Brain RTDB, reads Cloud Run / Scheduler status
#   job        $JOB: Cloud Run Job, one task, the whole directory
#   schedule   $SCHEDULE_JOB: daily at $CRON ($SCHEDULE_TZ), after lake-surface-daily (03:00 CT)
#
# IAM note: Firebase RTDB IAM is project-wide, so roles/firebasedatabase.admin
# also reaches the app databases. The code refuses any app-database URL
# (brain_platform.APP_DATABASES); tighter scoping (REST auth_variable_override
# + sector-brain rules for this uid) is listed as an open item.
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-water-clarity-brain}"
SCHEDULE_JOB="${SCHEDULE_JOB:-water-clarity-brain}"
SA_NAME="${SA_NAME:-water-clarity-brain}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
CRON="${CRON:-30 4 * * *}"
SCHEDULE_TZ="${SCHEDULE_TZ:-America/Chicago}"
cd "$(dirname "$0")"

echo "▶ service account $SA"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Water Clarity Brain publisher"
fi
for role in roles/firebasedatabase.admin roles/run.viewer roles/cloudscheduler.viewer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" --role "$role" --condition=None >/dev/null
done

echo "▶ job $JOB"
cp ../lake-surface/polygons.geojson.gz .
# The shared Brain Platform (docs/brains/BRAIN_PLATFORM_CONTRACT.md): vendored into the image.
rm -rf sector_brain_platform && cp -R ../brain_platform/sector_brain_platform .
trap 'rm -f polygons.geojson.gz' EXIT
gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" \
  --service-account "$SA" \
  --tasks 1 --max-retries 1 --cpu 1 --memory 1Gi --task-timeout 2h \
  --set-env-vars "BRAIN_TOKEN_MODE=metadata,BRAIN_RTDB_URL=https://sector-brain.firebaseio.com${CLARITY_PRIVATE_CATALOG:+,CLARITY_PRIVATE_CATALOG=$CLARITY_PRIVATE_CATALOG}"
# Optional private overlay (detailed candidate research, never in this public repo): set
# CLARITY_PRIVATE_CATALOG=gs://<private-bucket>/<object> and grant $SA roles/storage.objectViewer on that bucket.

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
echo "✅ Run it now:  gcloud run jobs execute $JOB --project $PROJECT_ID --region $REGION"
