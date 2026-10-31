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
# Build context (Repository Architecture V1, Wind Phase 2): the image is assembled from the Wind Brain package into a
# temporary directory, never by vendoring into the source tree. The context holds exactly what the Dockerfile COPYs:
#   Dockerfile .gcloudignore requirements.txt lakes.json main.py sector_wind/ sector_brain_platform/
# from brains/wind/deploy, brains/wind/runtime and the shared Brain Platform (jobs/brain_platform, legacy location;
# docs/brains/BRAIN_PLATFORM_CONTRACT.md). Research tools (brains/wind/research) are never part of the image.
#   ./deploy-job.sh --stage-only DIR   assemble the context into DIR and exit (no gcloud; used by the migration gate)
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$(dirname "$DEPLOY_DIR")"
REPO_ROOT="$(cd "$BRAIN_DIR/../.." && pwd)"
stage_context() {
  local dest="$1"
  mkdir -p "$dest"
  cp "$DEPLOY_DIR/Dockerfile" "$DEPLOY_DIR/.gcloudignore" "$dest/"
  cp "$BRAIN_DIR/runtime/requirements.txt" "$BRAIN_DIR/runtime/lakes.json" "$BRAIN_DIR/runtime/main.py" "$BRAIN_DIR/runtime/knowledge-release.json" "$dest/"
  cp -R "$BRAIN_DIR/runtime/sector_wind" "$dest/sector_wind"
  cp -R "$REPO_ROOT/jobs/brain_platform/sector_brain_platform" "$dest/sector_brain_platform"
  find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +
}
if [[ "${1:-}" == "--stage-only" ]]; then
  stage_context "${2:?--stage-only needs a destination directory}"
  echo "staged wind-hourly build context -> $2"
  exit 0
fi
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
MINUTE="${MINUTE:-5}"   # NBM posts ~57 min after the cycle; :05 catches the previous hour's run
COMMIT="$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)"
CONTEXT="$(mktemp -d)"
trap 'rm -rf "$CONTEXT"' EXIT
stage_context "$CONTEXT"
cd "$CONTEXT"

gcloud storage buckets describe "gs://$BUCKET" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud storage buckets create "gs://$BUCKET" --project "$PROJECT_ID" --location "$REGION" \
    --uniform-bucket-level-access --public-access-prevention
gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Wind hourly candidate job"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$SA" \
  --role roles/storage.objectAdmin >/dev/null
# --set-env-vars REPLACES the job's env: keep the Brain RTDB URL (the Wind Brain publish) and label the build.
BRAIN_RTDB_URL="${BRAIN_RTDB_URL:-https://sector-brain.firebaseio.com}"
# 7-day shadow equivalence (deploy/shadow-equivalence/): OFF unless this deploy is approved with WIND_SHADOW_EQUIVALENCE=on and an evidence bucket the job
# identity may create objects in under exports/shadow-equivalence/wind/ (that grant is a separate approved step; this script binds nothing for it).
WIND_SHADOW_EQUIVALENCE="${WIND_SHADOW_EQUIVALENCE:-off}"
[[ "$WIND_SHADOW_EQUIVALENCE" == "on" || "$WIND_SHADOW_EQUIVALENCE" == "off" ]] || { echo "WIND_SHADOW_EQUIVALENCE must be on or off" >&2; exit 2; }
SHADOW_ENV=""
if [[ "$WIND_SHADOW_EQUIVALENCE" == "on" ]]; then
  SHADOW_ENV=",WIND_SHADOW_EQUIVALENCE=on,WIND_SHADOW_EVIDENCE_BUCKET=${WIND_SHADOW_EVIDENCE_BUCKET:?WIND_SHADOW_EQUIVALENCE=on needs WIND_SHADOW_EVIDENCE_BUCKET}"
fi
gcloud run jobs deploy "$JOB" --source . --project "$PROJECT_ID" --region "$REGION" \
  --service-account "$SA" --tasks 1 --max-retries 1 --task-timeout 900 --memory 2Gi --cpu 1 \
  --labels "commit=$COMMIT" \
  --set-env-vars "SECTOR_WIND_GCS_APPROVED=yes,SECTOR_WIND_BRAIN_RTDB_URL=$BRAIN_RTDB_URL,SECTOR_WIND_BUILD=main@$COMMIT$SHADOW_ENV" \
  --args="hourly,--store,gs://$BUCKET/wind/v1"
gcloud run jobs add-iam-policy-binding "$JOB" --region "$REGION" --project "$PROJECT_ID" \
  --member "serviceAccount:$SA" --role roles/run.invoker >/dev/null
# Central scheduling (owner directive 2026-10-23; Rehtac Cortex 2.7.0 PL-15/PL-18): this deploy NEVER creates, updates or resumes a Cloud
# Scheduler job. Automatic Brain execution belongs to brain-orchestrator alone (and only while /control/executionControlV1 is ENABLED);
# this job's own scheduler is deprecated and stays PAUSED (or absent). The only scheduler action here is pausing one found ENABLED.
for S in "$JOB"; do
  if gcloud scheduler jobs describe "$S" --project "$PROJECT_ID" --location "$REGION" --format 'value(state)' 2>/dev/null | grep -q ENABLED; then
    gcloud scheduler jobs pause "$S" --project "$PROJECT_ID" --location "$REGION"
  fi
done
echo "scheduler: not managed by this deploy (central scheduling); "$JOB" stay PAUSED"
echo "deployed $JOB → gs://$BUCKET/wind/v1 (private)"
