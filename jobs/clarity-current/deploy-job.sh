#!/usr/bin/env bash
#
# The hourly Current Clarity job (Clarity Fusion Stage 5): prepares each lake's
# world so the routes never build one while someone waits. It runs
# /app/ClarityPrecompute from the engine's own image, taken from a deployed
# revision, so the job and the routes always run the same code.
#
#   job        $JOB — 1 task, writes gs://$BUCKET/clarity/current/<slug>/…
#   schedule   $SCHEDULE_JOB — at :40 every hour UTC, after hydrology-hourly (:15)
#   image      the image of revision $REVISION (default: the one tagged $TAG)
#
#   ./jobs/clarity-current/deploy-job.sh              the revision tagged "clarity"
#   REVISION=sector-engine-00070-abc ./jobs/clarity-current/deploy-job.sh
#
# Safe to re-run. The engine commit is recorded in every world.json.
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-sector-engine}"
TAG="${TAG:-clarity}"
BUCKET="${BUCKET:-sector-lake-surface}"
JOB="${JOB:-clarity-current-hourly}"
SCHEDULE_JOB="${SCHEDULE_JOB:-clarity-current-hourly}"
SA="${SA:-lake-surface-job@$PROJECT_ID.iam.gserviceaccount.com}"
CRON="${CRON:-40 * * * *}"
cd "$(dirname "$0")/../.."

if [[ -z "${REVISION:-}" ]]; then
  REVISION=$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format=json \
    | python3 -c "import json,sys; print(next(t['revisionName'] for t in json.load(sys.stdin)['status']['traffic'] if t.get('tag') == '$TAG'))")
fi
IMAGE=$(gcloud run revisions describe "$REVISION" --project "$PROJECT_ID" --region "$REGION" --format "value(spec.containers[0].image)")
COMMIT="${COMMIT:-$(git rev-parse HEAD)}"
echo "▶ job $JOB from $REVISION ($IMAGE), engine commit $COMMIT"

gcloud run jobs deploy "$JOB" --image "$IMAGE" \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --command /app/ClarityPrecompute \
  --tasks 1 --max-retries 1 --cpu 2 --memory 2Gi --task-timeout 15m \
  --set-env-vars "SECTOR_CLARITY_BUCKET=$BUCKET,SECTOR_ENGINE_COMMIT=$COMMIT"
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
