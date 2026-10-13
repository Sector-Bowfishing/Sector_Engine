#!/usr/bin/env bash
# One-time setup of the public Lake Registry bucket (idempotent). Public read is deliberate: the data is derived from the
# public-domain USGS NHD and contains nothing private. Writers are the project's default principals only (nothing added).
set -euo pipefail
B=gs://sector-lake-registry
P=sector-9393c
HERE="$(cd "$(dirname "$0")" && pwd)"
gcloud storage buckets describe "$B" --project "$P" >/dev/null 2>&1 || \
  gcloud storage buckets create "$B" --project="$P" --location=us-central1 --uniform-bucket-level-access --default-storage-class=STANDARD
gcloud storage buckets add-iam-policy-binding "$B" --member=allUsers --role=roles/storage.objectViewer >/dev/null
gcloud storage buckets update "$B" --cors-file="$HERE/cors.json"
gcloud storage buckets describe "$B" --format="yaml(name,location,uniform_bucket_level_access,cors_config)"
