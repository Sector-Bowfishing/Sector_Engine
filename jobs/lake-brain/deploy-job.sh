#!/usr/bin/env bash
#
# lake-brain: the Lake Brain as a scale-to-zero Cloud Run JOB (cost work 2026-10-13, Phase 10). No scheduler —
# brain-orchestrator starts it when the Lake Brain is due or stale (staleAfterHours 3) and the job's own plan()
# skips lakes whose state is current. Pilot scope (5 lakes) by default: `--scope pilots`.
#
# Runs /app/LakeBrainJob from the Brain jobs image (jobs/brain-image-build.sh), never from the serving service.
# Service account `brain-writer` (created by jobs/brain-orchestrator/deploy-job.sh) additionally gets
#   roles/storage.objectAdmin   on gs://sector-lake-brain (history, baselines; presence is read there too)
#   roles/storage.objectViewer  on gs://sector-water-temp-archive (shared TVA archive, read-only)
#
#   IMAGE=<from brain-image-build.sh> ./jobs/lake-brain/deploy-job.sh
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-lake-brain}"
SA_NAME="${SA_NAME:-brain-writer}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
RTDB_URL="${RTDB_URL:-https://sector-brain.firebaseio.com}"
ARCHIVE_BUCKET="${ARCHIVE_BUCKET:-sector-lake-brain}"
TVA_BUCKET="${TVA_BUCKET:-sector-water-temp-archive}"
[[ -n "${IMAGE:-}" ]] || { echo "✗ IMAGE=… required (output of jobs/brain-image-build.sh)"; exit 2; }
run() { if [[ "${DRY_RUN:-0}" == "1" ]]; then echo "+ $*"; else "$@"; fi; }
cd "$(dirname "$0")/../.."
COMMIT="${COMMIT:-${IMAGE##*:}}"      # the image tag is the commit it was built from (jobs/brain-image-build.sh)

gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1 || { echo "✗ $SA missing: run jobs/brain-orchestrator/deploy-job.sh first"; exit 2; }
run gcloud storage buckets add-iam-policy-binding "gs://$ARCHIVE_BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectAdmin
run gcloud storage buckets add-iam-policy-binding "gs://$TVA_BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectViewer

echo "▶ job $JOB from $IMAGE (commit $COMMIT)"
run gcloud run jobs deploy "$JOB" --image "$IMAGE" \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --command /app/LakeBrainJob \
  --args="--rtdb,$RTDB_URL,--archive,gs://$ARCHIVE_BUCKET,--scope,pilots" \
  --tasks 1 --max-retries 0 --cpu 1 --memory 1Gi --task-timeout 15m \
  --labels "commit=$COMMIT" \
  --set-env-vars "SECTOR_BRAIN_RTDB_URL=$RTDB_URL,SECTOR_ENGINE_COMMIT=$COMMIT"
run gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" --member "serviceAccount:$SA" --role roles/run.invoker
echo "✅ $JOB deployed (no scheduler: brain-orchestrator starts it). Run once: gcloud run jobs execute $JOB --region $REGION"
