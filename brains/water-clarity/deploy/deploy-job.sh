#!/usr/bin/env bash
#
# NOT RUN, NOT AUTHORIZED. Deploying the Water Clarity Brain job needs Michael's explicit go (see docs/brains/WATER_CLARITY_BRAIN_INTEGRATION.md,
# "Deployment"); this script refuses to run without MICHAEL_APPROVED_WATER_CLARITY_DEPLOY=yes. Execution is MANUAL by decision
# (docs/brains/WATER_CLARITY_BRAIN_SCHEDULING.md); the schedule step below is NOT part of the certified state.
#
# The Water Clarity Brain publisher: restates production Clarity (Engine /conditions + gs://sector-lake-surface) into the dedicated Brain RTDB
# (sector-brain) that Sector Ops reads. It is its own job: it reads production and never writes to it, so a Brain RTDB outage cannot affect customer Clarity.
#
#   account    $SA: writes the Brain RTDB, reads Cloud Run / Scheduler status
#   job        $JOB: Cloud Run Job, one task, the whole directory
#
# IAM note: Firebase RTDB IAM is project-wide, so roles/firebasedatabase.admin also reaches the app databases. The code refuses any app-database URL
# (brain_platform.APP_DATABASES); tighter scoping (REST auth_variable_override + sector-brain rules for this uid) is listed as an open item.
#
set -euo pipefail
# Build context: assembled from the Water Clarity Brain package into a temporary directory, never by vendoring into the source tree. The context holds exactly
# what the Dockerfile COPYs:  Dockerfile  *.py  catalog.json  knowledge-release.json  polygons.geojson.gz  sector_brain_platform/
# from brains/water-clarity/deploy, brains/water-clarity/runtime, jobs/lake-surface (outlines) and the shared Brain Platform (jobs/brain_platform).
#   ./deploy-job.sh --stage-only DIR   assemble the context into DIR and exit (no gcloud; used by the staged-layout test)
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$(dirname "$DEPLOY_DIR")"
REPO_ROOT="$(cd "$BRAIN_DIR/../.." && pwd)"
stage_context() {
  local dest="$1"
  mkdir -p "$dest"
  cp "$DEPLOY_DIR/Dockerfile" "$dest/"
  cp "$BRAIN_DIR/runtime/"*.py "$BRAIN_DIR/runtime/catalog.json" "$BRAIN_DIR/runtime/knowledge-release.json" "$dest/"
  cp "$REPO_ROOT/jobs/lake-surface/polygons.geojson.gz" "$dest/"
  cp -R "$REPO_ROOT/jobs/brain_platform/sector_brain_platform" "$dest/sector_brain_platform"
  find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +
}
if [[ "${1:-}" == "--stage-only" ]]; then
  stage_context "${2:?--stage-only needs a destination directory}"
  echo "staged water-clarity-brain build context -> $2"
  exit 0
fi
if [[ "${MICHAEL_APPROVED_WATER_CLARITY_DEPLOY:-}" != "yes" ]]; then
  echo "Refusing: set MICHAEL_APPROVED_WATER_CLARITY_DEPLOY=yes only after Michael approves the water-clarity-brain deploy." >&2
  exit 2
fi

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-water-clarity-brain}"
SCHEDULE_JOB="${SCHEDULE_JOB:-water-clarity-brain}"
SA_NAME="${SA_NAME:-water-clarity-brain}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
CRON="${CRON:-30 4 * * *}"
SCHEDULE_TZ="${SCHEDULE_TZ:-America/Chicago}"

echo "▶ service account $SA"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Water Clarity Brain publisher"
fi
for role in roles/firebasedatabase.admin roles/run.viewer roles/cloudscheduler.viewer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" --role "$role" --condition=None >/dev/null
done

echo "▶ job $JOB"
CONTEXT="$(mktemp -d)"
trap 'rm -rf "$CONTEXT"' EXIT
stage_context "$CONTEXT"
cd "$CONTEXT"
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
