#!/usr/bin/env bash
#
# The hourly hydrology-inputs job (Clarity Fusion Stage 1 item 3): rain over
# each arm's drainage, each arm's flow with provenance, TVA at both dams,
# published to gs://$BUCKET for the engine. Safe to re-run.
#
#   job        $JOB — Cloud Run Job, 1 task, runs as the lake-surface SA
#   schedule   $SCHEDULE_JOB — hourly at minute 15 (MRMS Pass 2 lags ~2 h)
#
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-sector-lake-surface}"
JOB="${JOB:-hydrology-hourly}"
SCHEDULE_JOB="${SCHEDULE_JOB:-hydrology-hourly}"
SA="${SA:-lake-surface-job@$PROJECT_ID.iam.gserviceaccount.com}"
CRON="${CRON:-15 * * * *}"
cd "$(dirname "$0")"

# The aggregator and the lake's data come from the repo, not a copy kept here.
cp ../../scripts/hydrology/catchment_rain.py .
cp ../../docs/data/hydrology/guntersville/guntersville.mrms_weights.json mrms_weights.json
cp ../../docs/data/hydrology/guntersville/guntersville.hydrology.json hydrology.json

echo "▶ job $JOB"
gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --tasks 1 --max-retries 1 --cpu 1 --memory 2Gi --task-timeout 90m \
  --set-env-vars "BUCKET=$BUCKET,LAKE_SLUG=Guntersville_AL,BACKFILL_HOURS=720"
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:$SA" --role roles/run.invoker >/dev/null

# Central scheduling (owner directive 2026-10-23; Rehtac Cortex 2.7.0 PL-15/PL-18): this deploy NEVER creates, updates or resumes a Cloud
# Scheduler job. Automatic Brain execution belongs to brain-orchestrator alone (and only while /control/executionControlV1 is ENABLED);
# this job's own scheduler is deprecated and stays PAUSED (or absent). The only scheduler action here is pausing one found ENABLED.
for S in "$SCHEDULE_JOB"; do
  if gcloud scheduler jobs describe "$S" --project "$PROJECT_ID" --location "$REGION" --format 'value(state)' 2>/dev/null | grep -q ENABLED; then
    gcloud scheduler jobs pause "$S" --project "$PROJECT_ID" --location "$REGION"
  fi
done
echo "scheduler: not managed by this deploy (central scheduling); "$SCHEDULE_JOB" stay PAUSED"
echo "✅ Run it now: gcloud run jobs execute $JOB --project $PROJECT_ID --region $REGION"
