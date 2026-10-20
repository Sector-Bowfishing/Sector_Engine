#!/usr/bin/env bash
#
# brain-orchestrator: the hourly scale-to-zero executor (docs/brains/ORCHESTRATOR_DESIGN.md; cost work 2026-10-13).
# 1 vCPU / 512 Mi, single task, hourly Cloud Scheduler wake-up at :50 UTC (after wind-hourly at :05 and the
# TVA archive at :20, so a cycle sees the hour's Brain publishes).
#
# Service account `brain-writer` (shared by lake-brain, water-temp-brain and this job):
#   roles/firebasedatabase.admin   project-wide (RTDB IAM is project-wide; the client refuses the app databases)
#   roles/run.viewer               read jobs / executions / services for /jobs
#   roles/cloudscheduler.viewer    read schedules for /jobs
#   roles/run.invoker              on jobs lake-brain and water-temp-brain only (job-level)
#   roles/storage.objectViewer     on gs://sector-biology-private (Biological bundle pointer / bundle)
#
#   ./deploy-job.sh                 stage, build, deploy, bind IAM, create/update the scheduler
#   DRY_RUN=1 ./deploy-job.sh       print the commands only
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-brain-orchestrator}"
SA_NAME="${SA_NAME:-brain-writer}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
CRON="${CRON:-50 * * * *}"
RTDB_URL="${RTDB_URL:-https://sector-brain.firebaseio.com}"
ENGINE_URL="${ENGINE_URL:-https://sector-engine-e43utajroa-uc.a.run.app}"
LAKE_BRAIN_ARCHIVE="${LAKE_BRAIN_ARCHIVE:-gs://sector-lake-brain}"
BIOLOGY_BUCKET="${BIOLOGY_BUCKET:-sector-biology-private}"
run() { if [[ "${DRY_RUN:-0}" == "1" ]]; then echo "+ $*"; else "$@"; fi; }
cd "$(dirname "$0")"
ROOT="$(git rev-parse --show-toplevel)"
COMMIT="$(git rev-parse --short=12 HEAD)"

echo "▶ service account $SA"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  run gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Sector Brain RTDB writer (Brain jobs + orchestrator)"
fi
for role in roles/firebasedatabase.admin roles/run.viewer roles/cloudscheduler.viewer; do
  run gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" --role "$role" --condition=None --quiet
done
run gcloud storage buckets add-iam-policy-binding "gs://$BIOLOGY_BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectViewer
for j in lake-brain water-temp-brain; do
  if gcloud run jobs describe "$j" --project "$PROJECT_ID" --region "$REGION" >/dev/null 2>&1; then
    run gcloud run jobs add-iam-policy-binding "$j" --project "$PROJECT_ID" --region "$REGION" --member "serviceAccount:$SA" --role roles/run.invoker
  else
    echo "  (job $j not deployed yet — bind roles/run.invoker when it is: jobs/$j/deploy-job.sh does it)"
  fi
done

echo "▶ lineage preflight (the deployed commit must be an ancestor of HEAD; no durability protection may be removed)"
if ! python3 "$ROOT/jobs/brain-orchestrator/preflight_lineage.py" --job "$JOB"; then
  echo "  refusing to deploy: rebase/merge onto the deployed shared lineage first (docs/brains/platform/BRAIN_MIGRATION_CHECKLIST.md section 6); override only with a recorded decision: ALLOW_BACKWARD_LINEAGE=1"; exit 1
fi

echo "▶ stale-score guard (generated Brain score blocks must not be older than their Brain's branch)"
if ! python3 "$ROOT/jobs/brain-scores/check_score_artifacts.py"; then
  if [[ "${ALLOW_STALE_SCORES:-0}" == "1" ]]; then echo "  !! ALLOW_STALE_SCORES=1: deploying with a stale score artifact (record the decision)"; else echo "  refusing to deploy: carry the newer generated score block first (docs/brains/scoring/SCORE_ARTIFACT_DURABILITY.md)"; exit 1; fi
fi

echo "▶ stage the repo layout (commit $COMMIT)"
rm -rf stage && mkdir -p stage/jobs stage/docs/brains/scoring
cp -R "$ROOT/jobs/brain_platform" stage/jobs/brain_platform
for d in biological-brain sector-intelligence-brain brain-scores brain-orchestrator; do
  mkdir -p "stage/jobs/$d"
  src="$ROOT/jobs/$d"
  [[ "$d" == "biological-brain" ]] && src="$ROOT/brains/fish/runtime"     # Fish Brain canonical home; staged under the legacy job layout the image expects
  cp "$src"/*.py "stage/jobs/$d/" 2>/dev/null || true
  [[ -f "$src/catalog.json" ]] && cp "$src/catalog.json" "stage/jobs/$d/"
  cp -R "$src/schemas" "stage/jobs/$d/" 2>/dev/null || true
  [[ "$d" == "biological-brain" && -d "$src/tools" ]] && cp -R "$src/tools" "stage/jobs/$d/" || true
done
cp "$ROOT/docs/brains/scoring/frozen-scores.json" stage/docs/brains/scoring/
# brain-health-v1 (control/healthV1) discovers declared dependencies from brains/*/brain.json and the platform registries / provider
# catalog (read-only inputs; no Brain runtime is staged). Without them the health plane reports declarations UNKNOWN, never invented.
for b in "$ROOT"/brains/*/; do
  [[ -f "$b/brain.json" ]] || continue
  mkdir -p "stage/brains/$(basename "$b")" && cp "$b/brain.json" "stage/brains/$(basename "$b")/"
done
mkdir -p stage/platform/registries/signals stage/providers
cp "$ROOT/platform/registries/signals/signals.json" stage/platform/registries/signals/
cp "$ROOT/providers/PROVIDERS.json" stage/providers/
# Fish Biological Capability V2 inputs for the scorer (fish_capability.attach_capability). Attached only when fish-capability-publication.json is ACTIVE.
mkdir -p stage/docs/brains/scoring/evidence
for f in fish-biological-capability-v2.json fish-capability-cohorts-v2.json fish-capability-publication.json; do cp "$ROOT/docs/brains/scoring/$f" stage/docs/brains/scoring/; done
cp "$ROOT/docs/brains/scoring/evidence/fish-capability-evidence.json" stage/docs/brains/scoring/evidence/
find stage -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find stage -name 'tests' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find stage -name 'test_*.py' -delete
trap 'rm -rf stage' EXIT

echo "▶ job $JOB"
run gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --tasks 1 --max-retries 0 --cpu 1 --memory 512Mi --task-timeout 30m \
  --labels "commit=$COMMIT" \
  --set-env-vars "BRAIN_TOKEN_MODE=metadata,BRAIN_RTDB_URL=$RTDB_URL,ENGINE_URL=$ENGINE_URL,LAKE_BRAIN_ARCHIVE=$LAKE_BRAIN_ARCHIVE,BIOLOGY_BUCKET=$BIOLOGY_BUCKET,DEPLOYMENT_VERSION=brain-orchestrator@$COMMIT,ORCHESTRATOR_SCOPE=pilots,WATER_TEMP_SCOPE=fleet"
run gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" --member "serviceAccount:$SA" --role roles/run.invoker

echo "▶ schedule $JOB ($CRON UTC)"
RUN_URI="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$JOB:run"
if gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  run gcloud scheduler jobs update http "$JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone UTC --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA"
else
  run gcloud scheduler jobs create http "$JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone UTC --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA"
fi
# Cost freeze (2026-10-14): pre-production Brains are OFF by default. The scheduler is left PAUSED unless SCHEDULE_STATE=enabled is given,
# and enabling needs a recorded gate (docs/brains/platform/cost-freeze/PREPRODUCTION_PAUSED_JOBS.md section 3).
if [[ "${SCHEDULE_STATE:-paused}" != "enabled" ]]; then
  run gcloud scheduler jobs pause "$JOB" --project "$PROJECT_ID" --location "$REGION"
  echo "  scheduler left PAUSED (cost freeze). Run manually: gcloud run jobs execute $JOB --region $REGION --wait"
fi
echo "✅ $JOB deployed. Dry cycle: gcloud run jobs execute $JOB --region $REGION --args=--dry-run"
