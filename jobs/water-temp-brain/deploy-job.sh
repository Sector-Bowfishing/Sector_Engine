#!/usr/bin/env bash
#
# water-temp-brain: the Water Temperature Brain as a scale-to-zero Cloud Run JOB (cost work 2026-10-13, Phase 11).
# NO scheduler: brain-orchestrator starts it only when the 6-h freshness rule (staleAfterHours 6) requires it —
# the earlier `25 */3 * * *` blind cron in this script is gone. A fleet run (621 lakes) takes ~4–5 min at 1 vCPU.
#
# Runs /app/WaterTempBrainJob from the Brain jobs image (jobs/brain-image-build.sh) — the same engine code as
# /conditions, built from the same commit — never from the serving service and never touching it.
# Service account `brain-writer` (created by jobs/brain-orchestrator/deploy-job.sh).
#
#   IMAGE=<from brain-image-build.sh> ./jobs/water-temp-brain/deploy-job.sh
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-water-temp-brain}"
SA_NAME="${SA_NAME:-brain-writer}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
RTDB_URL="${RTDB_URL:-https://sector-brain.firebaseio.com}"
[[ -n "${IMAGE:-}" ]] || { echo "✗ IMAGE=… required (output of jobs/brain-image-build.sh)"; exit 2; }
run() { if [[ "${DRY_RUN:-0}" == "1" ]]; then echo "+ $*"; else "$@"; fi; }
cd "$(dirname "$0")/../.."
COMMIT="${COMMIT:-$(git rev-parse --short=12 HEAD)}"

gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1 || { echo "✗ $SA missing: run jobs/brain-orchestrator/deploy-job.sh first"; exit 2; }
echo "▶ job $JOB from $IMAGE (commit $COMMIT)"
run gcloud run jobs deploy "$JOB" --image "$IMAGE" \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --command /app/WaterTempBrainJob \
  --args "--rtdb,$RTDB_URL" \
  --tasks 1 --max-retries 0 --cpu 1 --memory 1Gi --task-timeout 20m \
  --labels "commit=$COMMIT" \
  --set-env-vars "SECTOR_BRAIN_RTDB_URL=$RTDB_URL,SECTOR_ENGINE_COMMIT=$COMMIT"
run gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" --member "serviceAccount:$SA" --role roles/run.invoker
if gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  echo "⚠ a Cloud Scheduler job '$JOB' exists — this Brain is orchestrator-triggered; pause it: gcloud scheduler jobs pause $JOB --location $REGION"
fi
echo "✅ $JOB deployed (no scheduler: brain-orchestrator starts it when stale). Run once: gcloud run jobs execute $JOB --region $REGION"
