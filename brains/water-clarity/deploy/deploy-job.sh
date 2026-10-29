#!/usr/bin/env bash
#
# Deploying needs Michael's explicit go; this script refuses to run without MICHAEL_APPROVED_WATER_CLARITY_DEPLOY=yes. Approved 2026-10-22 for
# INTERNAL OPERATION (owner directive: all-eight internal production activation): a scale-to-zero job scoped to the pilot lakes, started by
# brain-orchestrator when the state is 26 h old (docs/brains/WATER_CLARITY_BRAIN_SCHEDULING.md option 2). There is NO scheduler of its own and
# NO new service account: it runs as the existing Brain writer (brain-writer), and the orchestrator deploy grants itself run.invoker on this job.
#
# The Water Clarity Brain publisher: restates production Clarity (Engine /conditions + gs://sector-lake-surface) into the dedicated Brain RTDB
# (sector-brain) that Sector Ops reads. It is its own job: it reads production and never writes to it, so a Brain RTDB outage cannot affect customer Clarity.
#
#   account    $SA: reads the Brain RTDB (read-only role) and Cloud Run / Scheduler status; creates its sealed artifact in the private bucket (no database write)
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
SA_NAME="${SA_NAME:-clarity-brain-job}"                     # Cortex 3.1 / owner-approved pilot 2026-10-29: its OWN identity. RTDB read-only (roles/firebasedatabase.viewer), create-only on
                                                            # artifacts/water-clarity/ of the private artifact bucket; it can NOT write canonical Brain RTDB paths (the central Publisher does).
ARTIFACT_BUCKET="${CLARITY_ARTIFACT_BUCKET:-sector-9393c-brain-artifacts}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
LAKES="${LAKES:-Guntersville|AL,Lake Hartwell|SC}"            # pilot scope (control_manifest scopes guntersville, lake-hartwell); never the fleet
COMMIT="$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD)"

gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null || { echo "service account $SA missing" >&2; exit 2; }

echo "▶ job $JOB (lakes: $LAKES; commit $COMMIT)"
CONTEXT="$(mktemp -d)"
trap 'rm -rf "$CONTEXT"' EXIT
stage_context "$CONTEXT"
cd "$CONTEXT"
# '^;^' switches gcloud's list delimiter so the comma-separated lake list stays one argument.
gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" \
  --service-account "$SA" \
  --tasks 1 --max-retries 0 --cpu 1 --memory 2Gi --task-timeout 30m \
  --labels "commit=$COMMIT" \
  --args="^;^--lakes;$LAKES" \
  --set-env-vars "BRAIN_TOKEN_MODE=metadata,BRAIN_RTDB_URL=https://sector-brain.firebaseio.com,CLARITY_ARTIFACT_BUCKET=$ARTIFACT_BUCKET,DEPLOYMENT_VERSION=water-clarity-brain@$COMMIT${CLARITY_PRIVATE_CATALOG:+,CLARITY_PRIVATE_CATALOG=$CLARITY_PRIVATE_CATALOG}"
# Optional private overlay (detailed candidate research, never in this public repo): set CLARITY_PRIVATE_CATALOG=gs://<private-bucket>/<object>
# and grant $SA roles/storage.objectViewer on that bucket. Without it the registry carries the public catalog (catalogDetail PUBLIC_ONLY).

echo
echo "✅ deployed (no scheduler: brain-orchestrator starts it when due). Manual run:  gcloud run jobs execute $JOB --project $PROJECT_ID --region $REGION --wait"
echo "   rollback: gcloud run jobs delete $JOB --region $REGION   (or redeploy the previous commit); disable: set water-clarity activityState PARKED"
