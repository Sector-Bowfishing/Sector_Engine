#!/usr/bin/env bash
#
# Deploy the Sector conditions engine to Cloud Run.
#
# Builds from source with Cloud Build (no local Docker needed — Google builds the
# Dockerfile), then deploys to Cloud Run in the same GCP project as Firebase.
# Re-run this any time you change the engine: it redeploys, and both phones pick
# up the new numbers on their next call — no App Store release required.
#
# One-time setup (run these yourself, they need your Google login):
#   gcloud auth login
#   gcloud config set project sector-9393c
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
#
# Then just: ./deploy.sh
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-sector-engine}"

echo "▶ Deploying '$SERVICE' to Cloud Run  (project=$PROJECT_ID  region=$REGION)"

# Scaling config — do NOT lower these without understanding the 2026-09-14 outage.
# The conditions fan-out (My Lakes preload hits /conditions per lake every launch)
# launches ~9 blocking Linux URLSession fetches per request. Swift's cooperative
# thread pool is sized to CPU count, so under a burst the pool starves, the
# withDeadline timers can't fire, and every request rides to the 60s timeout (504,
# even /health). cpu=4 (more pool threads), concurrency=8 (fewer simultaneous
# blockers/instance), max=15 (throughput), min=1 (warm, no cold-start pileup).
gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 4 \
  --concurrency 8 \
  --timeout 60 \
  --min-instances 1 \
  --max-instances 15

echo
echo "✅ Deployed. Service URL:"
gcloud run services describe "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --format 'value(status.url)'

echo
echo "Smoke test (Guntersville):"
URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format 'value(status.url)')
echo "  curl \"$URL/health\""
echo "  curl \"$URL/conditions?lat=34.35&lon=-86.30\""
