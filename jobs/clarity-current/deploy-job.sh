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

# Central scheduling (owner directive 2026-10-23; Rehtac Cortex 2.7.0 PL-15/PL-18): this deploy NEVER creates, updates or resumes a Cloud
# Scheduler job. Automatic Brain execution belongs to brain-orchestrator alone (and only while /control/executionControlV1 is ENABLED);
# this job's own scheduler is deprecated and stays PAUSED (or absent). The only scheduler action here is pausing one found ENABLED.
for S in "$SCHEDULE_JOB"; do
  if gcloud scheduler jobs describe "$S" --project "$PROJECT_ID" --location "$REGION" --format 'value(state)' 2>/dev/null | grep -q ENABLED; then
    gcloud scheduler jobs pause "$S" --project "$PROJECT_ID" --location "$REGION"
  fi
done
echo "scheduler: not managed by this deploy (central scheduling); "$SCHEDULE_JOB" stay PAUSED"
echo "✅ Run it now: gcloud run jobs execute $JOB --project $PROJECT_ID --region $REGION"
