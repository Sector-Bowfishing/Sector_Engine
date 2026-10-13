#!/usr/bin/env bash
#
# Build the Engine image (Dockerfile at the repo root: SectorEngineServer + WaterTempBrainJob + LakeBrainJob) with
# Cloud Build and push it as the Brain JOBS image. It never touches the customer-serving `sector-engine` service:
# no `gcloud run deploy`, no traffic, no tags. jobs/lake-brain/deploy-job.sh and jobs/water-temp-brain/deploy-job.sh
# deploy Cloud Run JOBS from it.
#
#   ./jobs/brain-image-build.sh            → prints IMAGE=us-central1-docker.pkg.dev/<project>/cloud-run-source-deploy/brain-jobs:<commit>
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
cd "$(dirname "$0")/.."
if [[ -n "$(git status --porcelain)" && "${ALLOW_DIRTY:-0}" != "1" ]]; then
  echo "✗ uncommitted changes: commit first so the image maps to a commit (ALLOW_DIRTY=1 to override)"; exit 1
fi
COMMIT="$(git rev-parse --short=12 HEAD)"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/brain-jobs:$COMMIT"
echo "▶ Cloud Build → $IMAGE"
gcloud builds submit . --project "$PROJECT_ID" --region "$REGION" --tag "$IMAGE" --timeout 3600 --quiet
echo "IMAGE=$IMAGE"
