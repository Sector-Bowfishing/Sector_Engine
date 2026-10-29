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
#   ./deploy-job.sh                 stage, build, deploy, bind IAM, create/update the scheduler definition (always PAUSED)
#   DRY_RUN=1 ./deploy-job.sh       print the commands only
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-brain-orchestrator}"
SA_NAME="${SA_NAME:-brain-writer}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
CRON="${CRON:-50 * * * *}"
# Wind three measurements (wind-specialist-capability-v2, adopted 2026-10-19): OFF unless the deploy is approved with WIND_MEASUREMENTS=on.
WIND_MEASUREMENTS="${WIND_MEASUREMENTS:-off}"
[[ "$WIND_MEASUREMENTS" == "on" || "$WIND_MEASUREMENTS" == "off" ]] || { echo "WIND_MEASUREMENTS must be on or off"; exit 1; }
# Publication coordination (Cortex PL-19). OFF unless the deploy is approved with PUBLICATION_COORDINATION=on. Observation only: it reads sealed artifacts and keeps its own records under
# exports/orchestrator/ of the private artifact bucket; the live Publisher is never constructed by this job; every Brain stays on its direct writer unless a cutover document says otherwise.
PUBLICATION_COORDINATION="${PUBLICATION_COORDINATION:-off}"
[[ "$PUBLICATION_COORDINATION" == "on" || "$PUBLICATION_COORDINATION" == "off" ]] || { echo "PUBLICATION_COORDINATION must be on or off"; exit 1; }
PUBLICATION_ARTIFACT_BUCKET="${PUBLICATION_ARTIFACT_BUCKET:-sector-9393c-brain-artifacts}"
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
for j in lake-brain water-temp-brain water-clarity-brain wind-hourly; do
  if gcloud run jobs describe "$j" --project "$PROJECT_ID" --region "$REGION" >/dev/null 2>&1; then
    run gcloud run jobs add-iam-policy-binding "$j" --project "$PROJECT_ID" --region "$REGION" --member "serviceAccount:$SA" --role roles/run.invoker
  else
    echo "  (job $j not deployed yet — bind roles/run.invoker when it is: its brains/*/deploy/deploy-job.sh does it)"
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
# Fish Biological Capability V2 inputs for the scorer (fish_capability.attach_capability). Attached only when fish-capability-publication.json is ACTIVE.
mkdir -p stage/docs/brains/scoring/evidence
for f in fish-biological-capability-v2.json fish-capability-cohorts-v2.json fish-capability-publication.json; do cp "$ROOT/docs/brains/scoring/$f" stage/docs/brains/scoring/; done
cp "$ROOT/docs/brains/scoring/evidence/fish-capability-evidence.json" stage/docs/brains/scoring/evidence/
for d in biological-brain sector-intelligence-brain brain-scores brain-orchestrator; do
  mkdir -p "stage/jobs/$d"
  src="$ROOT/jobs/$d"
  [[ "$d" == "biological-brain" ]] && src="$ROOT/brains/fish/runtime"     # Fish Brain canonical home; staged under the legacy job layout the image expects
  [[ "$d" == "sector-intelligence-brain" ]] && src="$ROOT/brains/sector-intelligence/runtime"   # Sector Intelligence canonical home; same legacy layout
  cp "$src"/*.py "stage/jobs/$d/" 2>/dev/null || true
  [[ -f "$src/catalog.json" ]] && cp "$src/catalog.json" "stage/jobs/$d/"
  [[ -f "$src/knowledge-release.json" ]] && cp "$src/knowledge-release.json" "stage/jobs/$d/"     # packaged knowledge release (verified on load)
  cp -R "$src/schemas" "stage/jobs/$d/" 2>/dev/null || true
  [[ "$d" == "biological-brain" && -d "$src/tools" ]] && cp -R "$src/tools" "stage/jobs/$d/" || true
done
cp "$ROOT/docs/brains/scoring/frozen-scores.json" stage/docs/brains/scoring/
# brain-health-v1 (control/healthV1) discovers declared dependencies from brains/*/brain.json and the platform registries / provider
# catalog (read-only inputs; no Brain runtime is staged). Without them the health plane reports declarations UNKNOWN, never invented.
for b in "$ROOT"/brains/*/; do
  [[ -f "$b/brain.json" ]] || continue
  mkdir -p "stage/brains/$(basename "$b")" && cp "$b/brain.json" "stage/brains/$(basename "$b")/"
  # brain-score-explanation-v1 links improvements to research gap ids/status (metadata only; the register holds no data).
  if [[ -f "$b/research/GAPS.json" ]]; then mkdir -p "stage/brains/$(basename "$b")/research" && cp "$b/research/GAPS.json" "stage/brains/$(basename "$b")/research/"; fi
done
# internal SHADOW lane (2026-10-22): Depth and Vegetation runtimes with their packaged CANDIDATE knowledge releases, run by shadow_run.py
# from brains/<dir>/runtime (their package bootstrap resolves the platform at ../../../jobs/brain_platform). Never their write path.
for b in depth vegetation; do cp -R "$ROOT/brains/$b/runtime" "stage/brains/$b/runtime"; done
mkdir -p stage/platform/registries/signals stage/providers
cp "$ROOT/platform/registries/signals/signals.json" stage/platform/registries/signals/
cp "$ROOT/providers/PROVIDERS.json" stage/providers/
# Wind measurements inputs (read by sector_brain_platform.wind_measurements only when WIND_MEASUREMENTS=on; metadata, no data)
mkdir -p stage/docs/brains/scoring/evidence
cp "$ROOT/docs/brains/scoring/wind-specialist-capability-v2.json" stage/docs/brains/scoring/
cp "$ROOT/docs/brains/scoring/evidence/wind-measurements-evidence.json" stage/docs/brains/scoring/evidence/
# Sector Ops engineering status (engineering-status-ops-v1): the SANITIZED projection of exactly this commit, published only with
# --publish-engineering-status (decision O-1). A stale or invalid report stages nothing: the orchestrator then publishes an explicit UNAVAILABLE
# instead of an older status. The full internal report never enters the image.
ES_STATE=UNMERGED_BRANCH
git -C "$ROOT" merge-base --is-ancestor HEAD origin/main 2>/dev/null && ES_STATE=MAIN_COMMIT
if python3 "$ROOT/tools/cortex_status/build_engineering_status.py" --emit stage/es-full.json --commit "$(git -C "$ROOT" rev-parse HEAD)" \
   && python3 "$ROOT/tools/cortex_status/ops_projection.py" --report stage/es-full.json --code-state "$ES_STATE" \
        --branch "$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)" --generated-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --out stage/jobs/brain-orchestrator/engineering-status-ops.json; then
  echo "engineering status: staged ($ES_STATE)"
else
  echo "engineering status: NOT staged (stale or invalid report); the orchestrator will publish UNAVAILABLE"
  rm -f stage/jobs/brain-orchestrator/engineering-status-ops.json
fi
rm -f stage/es-full.json
find stage -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find stage -name 'tests' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find stage -name 'test_*.py' -delete
trap 'rm -rf stage' EXIT

echo "▶ job $JOB"
run gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --tasks 1 --max-retries 0 --cpu 1 --memory 512Mi --task-timeout 30m \
  --labels "commit=$COMMIT" \
  --set-env-vars "BRAIN_TOKEN_MODE=metadata,BRAIN_RTDB_URL=$RTDB_URL,ENGINE_URL=$ENGINE_URL,LAKE_BRAIN_ARCHIVE=$LAKE_BRAIN_ARCHIVE,BIOLOGY_BUCKET=$BIOLOGY_BUCKET,DEPLOYMENT_VERSION=brain-orchestrator@$COMMIT,ORCHESTRATOR_SCOPE=pilots,WATER_TEMP_SCOPE=pilots,WIND_MEASUREMENTS=$WIND_MEASUREMENTS,PUBLICATION_COORDINATION=$PUBLICATION_COORDINATION,PUBLICATION_ARTIFACT_BUCKET=$PUBLICATION_ARTIFACT_BUCKET"
run gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" --member "serviceAccount:$SA" --role roles/run.invoker

echo "▶ schedule $JOB ($CRON UTC): definition only, always left PAUSED"
# Central scheduling (owner directive 2026-10-23; Rehtac Cortex 2.7.0 PL-15..PL-18): brain-orchestrator is the ONE scheduling authority, and a
# deployment NEVER enables it. The definition is created or updated, then PAUSED. Resuming is owner-only: tools/ops/resume-orchestrator.sh,
# which requires /control/executionControlV1 ENABLED with an owner approvalRef and passing preflight checks. There is no SCHEDULE_STATE switch.
RUN_URI="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$JOB:run"
if gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  run gcloud scheduler jobs update http "$JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone UTC --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA" \
    --max-retry-attempts 0 --attempt-deadline 180s
else
  run gcloud scheduler jobs create http "$JOB" --project "$PROJECT_ID" --location "$REGION" \
    --schedule "$CRON" --time-zone UTC --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA" \
    --max-retry-attempts 0 --attempt-deadline 180s
fi
run gcloud scheduler jobs pause "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1 || true
state=$(gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" --format 'value(state)' 2>/dev/null || echo UNKNOWN)
echo "  scheduler $JOB: $state (a deployment never resumes it; owner resumption: tools/ops/resume-orchestrator.sh)"
if [[ "${DRY_RUN:-0}" != "1" && "$state" != "PAUSED" ]]; then echo "  !! scheduler is $state after deploy: refusing to report success"; exit 1; fi
echo "✅ $JOB deployed. Dry cycle: gcloud run jobs execute $JOB --region $REGION --args=--dry-run"
