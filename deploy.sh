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

gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 2 \
  --concurrency 40 \
  --timeout 60 \
  --min-instances 0 \
  --max-instances 4

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
