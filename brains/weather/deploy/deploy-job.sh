#!/usr/bin/env bash
#
# weather-brain: the Weather Brain as a scale-to-zero Cloud Run JOB, started ONLY by brain-orchestrator (Cortex PL-15). PREPARED, NOT RUN.
#
# Creating the job costs money and is an owner step (WEATHER_BRAIN_PLAN.md section 6.1): this script refuses to run without
# MICHAEL_APPROVED_WEATHER_DEPLOY=yes. It creates NO scheduler, never resumes one, and never touches the execution control (PL-18). Deploying
# does not make the Brain run: the control manifest must also give it the weather-brain target and the owner must enable it in the
# execution control.
#
#   account  $SA_NAME: the job's OWN identity (identity split, Sector_Ops #19). It must already exist and hold write access to the Brain
#            RTDB (sector-brain); this script never creates it, never grants it anything and never falls back to brain-writer.
#   job      $JOB: one task, the whole lake directory, `run.py --write` (refused inside the job unless the knowledge release is APPROVED
#            and WEATHER_WRITE_APPROVED=1; the latter is set here only when the operator passes WEATHER_WRITE_APPROVED=1).
#
#   ./deploy-job.sh --stage-only DIR   assemble the build context into DIR and exit (no gcloud; used by the staged-layout test)
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
BRAIN_DIR="$(dirname "$DEPLOY_DIR")"
REPO_ROOT="$(cd "$BRAIN_DIR/../.." && pwd)"
stage_context() {
  local dest="$1"
  mkdir -p "$dest"
  cp "$DEPLOY_DIR/Dockerfile" "$BRAIN_DIR/runtime/run.py" "$dest/"
  cp -R "$BRAIN_DIR/runtime/sector_weather" "$dest/sector_weather"
  cp -R "$BRAIN_DIR/runtime/knowledge" "$dest/knowledge"
  cp -R "$REPO_ROOT/jobs/brain_platform/sector_brain_platform" "$dest/sector_brain_platform"
  find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +
}
if [[ "${1:-}" == "--stage-only" ]]; then
  stage_context "${2:?--stage-only needs a destination directory}"
  echo "staged weather-brain build context -> $2"
  exit 0
fi
if [[ "${MICHAEL_APPROVED_WEATHER_DEPLOY:-}" != "yes" ]]; then
  echo "Refusing: set MICHAEL_APPROVED_WEATHER_DEPLOY=yes only after Michael approves creating the weather-brain job (cost cap 2 USD/month)." >&2
  exit 2
fi
[[ -n "${SECTOR_WEATHER_USER_AGENT:-}" ]] || { echo "Refusing: SECTOR_WEATHER_USER_AGENT (the NWS contact User-Agent, docs/NWS_PROVIDER.md) is required." >&2; exit 2; }

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-weather-brain}"
SA_NAME="${SA_NAME:-brain-job-weather}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
INVOKER_SA="${INVOKER_SA_NAME:-brain-orchestrator}@$PROJECT_ID.iam.gserviceaccount.com"
RTDB_URL="${RTDB_URL:-https://sector-brain.firebaseio.com}"
WRITE_INTENT="${WEATHER_WRITE_APPROVED:-0}"
COMMIT="$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD)"

gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1 || { echo "✗ $SA does not exist: refusing (this script never creates or grants an identity)." >&2; exit 2; }
gcloud iam service-accounts describe "$INVOKER_SA" --project "$PROJECT_ID" >/dev/null 2>&1 || { echo "✗ $INVOKER_SA does not exist: refusing." >&2; exit 2; }

echo "▶ job $JOB (commit $COMMIT; write intent $WRITE_INTENT)"
CONTEXT="$(mktemp -d)"
trap 'rm -rf "$CONTEXT"' EXIT
stage_context "$CONTEXT"
cd "$CONTEXT"
gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --tasks 1 --max-retries 0 --cpu 1 --memory 512Mi --task-timeout 30m \
  --labels "commit=$COMMIT" \
  --args="--write,--point-cache,/tmp/weather-points.json" \
  --set-env-vars "^;^BRAIN_TOKEN_MODE=metadata;BRAIN_RTDB_URL=$RTDB_URL;WEATHER_WRITE_APPROVED=$WRITE_INTENT;SECTOR_WEATHER_USER_AGENT=$SECTOR_WEATHER_USER_AGENT;DEPLOYMENT_VERSION=weather-brain@$COMMIT"
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" --member "serviceAccount:$INVOKER_SA" --role roles/run.invoker
if gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  echo "⚠ a Cloud Scheduler job '$JOB' exists: this Brain is orchestrator-started only (PL-15); pause it."
fi
echo
echo "✅ $JOB deployed (no scheduler). It runs only when the manifest target is switched on AND the owner enables weather in the execution control."
echo "   rollback: gcloud run jobs delete $JOB --region $REGION (or redeploy the previous commit); stop: execution_control.py brain --brain weather --disable"
