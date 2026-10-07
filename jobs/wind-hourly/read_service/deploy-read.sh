#!/usr/bin/env bash
# wind-candidate-read — master-only read path for the Wind Candidate inspector.
# Approved by Michael with the Stage 3 shadow infrastructure (2026-10-07). Read-only account on the
# private Wind bucket; the endpoint returns data only for a verified Firebase ID token of a master uid.
set -euo pipefail
[[ "${MICHAEL_APPROVED_WIND_DEPLOY:-}" == "yes" ]] || { echo "Refusing without MICHAEL_APPROVED_WIND_DEPLOY=yes" >&2; exit 2; }
PROJECT_ID="${PROJECT_ID:-sector-9393c}"; REGION="${REGION:-us-central1}"; BUCKET="${BUCKET:-sector-wind-candidate}"
SVC="${SVC:-wind-candidate-read}"; SA_NAME="${SA_NAME:-wind-candidate-read}"; SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
MASTER_UIDS="${MASTER_UIDS:?set MASTER_UIDS}"
cd "$(dirname "$0")"
gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Wind Candidate read (master inspector)"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectViewer >/dev/null
gcloud run deploy "$SVC" --source . --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --allow-unauthenticated --min-instances 0 --max-instances 2 --memory 512Mi --cpu 1 \
  --set-env-vars "BUCKET=$BUCKET,PREFIX=wind/v1,FIREBASE_PROJECT=$PROJECT_ID,MASTER_UIDS=$MASTER_UIDS"
gcloud run services describe "$SVC" --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)'
