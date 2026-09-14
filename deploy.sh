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

# Scaling config — do NOT raise concurrency without understanding the 2026-09-14 outage.
# A /conditions render fans out ~9 Linux URLSession fetches. ONE render per instance
# is reliable (~7-8s). TWO OR MORE concurrent cold renders on one instance starve
# Swift's cooperative thread pool: the withDeadline timers can't fire, requests ride
# to the 60s timeout (504), and the instance stays wedged — even /health — until it's
# replaced. Verified 2026-09-14: concurrency=8 wedged, concurrency=2 hung 1 of 3,
# concurrency=1 served 3 concurrent cold renders at ~7.5s with /health instant.
# So: concurrency=1 (one render per instance), scale out horizontally (max=30),
# min=1 warm. Raise concurrency only after the fan-out stops blocking the pool
# (AsyncHTTPClient, or an in-app render semaphore).
gcloud run deploy "$SERVICE" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 4 \
  --concurrency 1 \
  --timeout 60 \
  --min-instances 1 \
  --max-instances 30

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
