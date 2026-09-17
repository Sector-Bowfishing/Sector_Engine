#!/usr/bin/env bash
#
# Deploy the Sector conditions engine to Cloud Run.
#
# Builds from source with Cloud Build (no local Docker needed — Google builds the
# Dockerfile), then deploys to Cloud Run in the same GCP project as Firebase.
# Re-run this any time you change the engine: it redeploys, and both phones pick
# up the new numbers on their next call — no App Store release required.
#
# Traffic is PINNED to a named revision (since the 2026-09-14 outage rollback), so
# a plain `gcloud run deploy` builds a new revision and then serves none of it —
# "✅ Deployed" while the phones keep getting the old numbers. This script instead:
#
#   1. deploys the new revision with NO traffic, reachable at a `next` tag URL,
#   2. smoke-tests that URL (health + a real Guntersville render),
#   3. moves 100% of traffic to it only if the smoke test passed,
#   4. prints the one-line rollback to the revision that was serving before.
#
# One-time setup (run these yourself, they need your Google login):
#   gcloud auth login
#   gcloud config set project sector-9393c
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
#
# Then just: ./deploy.sh        (SKIP_SMOKE=1 ./deploy.sh to deploy without the check)
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-sector-engine}"
SMOKE_LAT="${SMOKE_LAT:-34.35}"
SMOKE_LON="${SMOKE_LON:--86.30}"

describe() {
  gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format "$1"
}

echo "▶ Deploying '$SERVICE' to Cloud Run  (project=$PROJECT_ID  region=$REGION)"

# What's serving right now — captured BEFORE the deploy so the rollback line at the
# end names the revision that was live, whatever happens next.
PREV_REV="$(describe 'value(spec.traffic[0].revisionName)' || true)"
echo "   currently serving: ${PREV_REV:-<latest>}"

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
  --max-instances 30 \
  --no-traffic \
  --tag next

NEW_REV="$(describe 'value(status.latestCreatedRevisionName)')"
URL="$(describe 'value(status.url)')"
# Cloud Run serves a tagged revision at <tag>---<service-host>.
NEXT_URL="https://next---${URL#https://}"

echo
echo "▶ Built revision: $NEW_REV  (no traffic yet)"
echo "   candidate URL: $NEXT_URL"

if [[ "${SKIP_SMOKE:-0}" == "1" ]]; then
  echo "   smoke test skipped (SKIP_SMOKE=1)"
else
  echo "▶ Smoke-testing the candidate before it takes traffic…"
  # /health first — a cold instance answers this instantly once it's up.
  for attempt in 1 2 3 4 5; do
    if curl -fsS -m 20 "$NEXT_URL/health" >/dev/null; then break; fi
    if [[ $attempt == 5 ]]; then
      echo "❌ /health never answered on $NEW_REV — traffic NOT moved."
      echo "   Logs: gcloud logging read 'resource.labels.revision_name=\"$NEW_REV\"' --project $PROJECT_ID --limit 50"
      exit 1
    fi
    sleep 5
  done
  # A real render — the thing the phones actually call. A cold render is ~8s.
  BODY="$(curl -fsS -m 90 "$NEXT_URL/conditions?lat=$SMOKE_LAT&lon=$SMOKE_LON" || true)"
  if ! grep -q '"score"' <<<"$BODY"; then
    echo "❌ /conditions did not return a score on $NEW_REV — traffic NOT moved."
    echo "   Response: $(head -c 300 <<<"$BODY")"
    exit 1
  fi
  echo "   ✅ health + a live Guntersville render both OK"
fi

echo
echo "▶ Moving 100% of traffic to $NEW_REV"
gcloud run services update-traffic "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --to-revisions "$NEW_REV=100" >/dev/null
# The tag has done its job; drop it so tags don't pile up on old revisions.
gcloud run services update-traffic "$SERVICE" \
  --project "$PROJECT_ID" --region "$REGION" \
  --remove-tags next >/dev/null || true

echo
echo "✅ Live: $(describe 'value(spec.traffic[0].revisionName)')"
echo "   $URL"
echo
echo "Roll back with:"
echo "  gcloud run services update-traffic $SERVICE --project $PROJECT_ID --region $REGION --to-revisions ${PREV_REV:-<previous-revision>}=100"
