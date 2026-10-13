#!/usr/bin/env bash
#
# The Water Temperature Brain job (Sector Brain Platform): every 3 h it runs the
# production water-temperature path for all 621 directory lakes and writes the
# Brain RTDB (https://sector-brain.firebaseio.com), which Sector Ops reads.
# It runs /app/WaterTempBrainJob from the engine image of a deployed revision,
# so the job and /conditions run the same code. It never touches the service.
#
#   ./jobs/water-temp-brain/deploy-job.sh                    the revision serving 100 %
#   REVISION=sector-engine-00073-abc ./jobs/water-temp-brain/deploy-job.sh
#
# REQUIRES Michael's approval (Sector Engine deploy policy):
#   I_HAVE_MICHAELS_APPROVAL=yes ./jobs/water-temp-brain/deploy-job.sh
#
# Prerequisite: that revision's image must contain /app/WaterTempBrainJob, i.e.
# an engine build from a commit that includes Sources/WaterTempBrainJob.
#
set -euo pipefail
[[ "${I_HAVE_MICHAELS_APPROVAL:-}" == "yes" ]] || { echo "refusing: set I_HAVE_MICHAELS_APPROVAL=yes (Michael must approve Sector Engine deploys)"; exit 3; }

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-sector-engine}"
JOB="${JOB:-water-temp-brain}"
SCHEDULE_JOB="${SCHEDULE_JOB:-water-temp-brain}"
SA_NAME="${SA_NAME:-brain-writer}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
RTDB_URL="${RTDB_URL:-https://sector-brain.firebaseio.com}"
CRON="${CRON:-25 */3 * * *}"
cd "$(dirname "$0")/../.."

if [[ -z "${REVISION:-}" ]]; then
  REVISION=$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format=json \
    | python3 -c "import json,sys; print(next(t['revisionName'] for t in json.load(sys.stdin)['status']['traffic'] if t.get('percent') == 100))")
fi
IMAGE=$(gcloud run revisions describe "$REVISION" --project "$PROJECT_ID" --region "$REGION" --format "value(spec.containers[0].image)")
COMMIT="${COMMIT:-$(git rev-parse HEAD)}"
echo "▶ job $JOB from $REVISION ($IMAGE), engine commit $COMMIT → $RTDB_URL"

if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Sector Brain RTDB writer"
fi
# NOTE: RTDB IAM is project-wide — this role can also write the app's RTDB instances.
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" \
  --role roles/firebasedatabase.admin --condition=None >/dev/null

gcloud run jobs deploy "$JOB" --image "$IMAGE" \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --command /app/WaterTempBrainJob \
  --tasks 1 --max-retries 0 --cpu 1 --memory 1Gi --task-timeout 20m \
  --set-env-vars "SECTOR_BRAIN_RTDB_URL=$RTDB_URL,SECTOR_ENGINE_REVISION=$REVISION,SECTOR_ENGINE_COMMIT=$COMMIT"
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
