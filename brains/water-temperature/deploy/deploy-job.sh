#!/usr/bin/env bash
#
# water-temp-brain: the Water Temperature Brain as a scale-to-zero Cloud Run JOB (cost work 2026-10-13, Phase 11).
# NO scheduler: brain-orchestrator starts it only when the 6-h freshness rule (staleAfterHours 6) requires it —
# the earlier `25 */3 * * *` blind cron in this script is gone. A fleet run (621 lakes) takes ~4–5 min at 1 vCPU.
#
# Runs /app/WaterTempBrainJob from the Brain jobs image (jobs/brain-image-build.sh) — the same engine code as
# /conditions, built from the same commit — never from the serving service and never touching it.
# Service account `brain-job-water-temp` (its own; created by the identity-split scripts, Sector_Ops #19). brain-orchestrator gets run.invoker on it.
#
#   IMAGE=<from brain-image-build.sh> ./brains/water-temperature/deploy/deploy-job.sh
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-water-temp-brain}"
SA_NAME="${SA_NAME:-brain-job-water-temp}"      # its OWN account (identity split, Sector_Ops #19, owner approval 2026-11-18); never brain-writer by default
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
INVOKER_SA_NAME="${INVOKER_SA_NAME:-brain-orchestrator}"   # brain-orchestrator starts this job
INVOKER_SA="$INVOKER_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
RTDB_URL="${RTDB_URL:-https://sector-brain.firebaseio.com}"
[[ -n "${IMAGE:-}" ]] || { echo "✗ IMAGE=… required (output of jobs/brain-image-build.sh)"; exit 2; }
run() { if [[ "${DRY_RUN:-0}" == "1" ]]; then echo "+ $*"; else "$@"; fi; }
cd "$(dirname "$0")/../../.."      # repo root (brains/<dir>/deploy/)
COMMIT="${COMMIT:-${IMAGE##*:}}"      # the image tag is the commit it was built from (jobs/brain-image-build.sh)

gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1 || { echo "✗ $SA does not exist (or cannot be read): refusing to deploy. Create it with the identity-split scripts (Sector_Ops #19) first; this script never falls back to brain-writer."; exit 2; }
gcloud iam service-accounts describe "$INVOKER_SA" --project "$PROJECT_ID" >/dev/null 2>&1 || { echo "✗ $INVOKER_SA (the account that starts this job) does not exist: refusing to deploy"; exit 2; }
# Live-identity guard (Sector_Ops #19 review): never move a job that still runs as the shared brain-writer account onto a new account
# by accident (a routine redeploy). The identity-split scripts switch it; set ALLOW_SA_SWITCH=1 only to do that switch on purpose.
# Fail closed: a describe error other than NOT_FOUND (the job's first deploy) stops the deploy; it is never read as "no account".
CUR_SA=""
if [[ "${DRY_RUN:-0}" != "1" ]]; then
  _sa_err="$(mktemp)"
  if ! CUR_SA="$(gcloud run jobs describe "$JOB" --project "$PROJECT_ID" --region "$REGION" --format='value(spec.template.spec.template.spec.serviceAccountName)' 2>"$_sa_err")"; then
    if grep -qiE 'NOT_FOUND|Cannot find job|could not be found|cannot be found|was not found' "$_sa_err"; then
      CUR_SA=""   # first deploy of this job: nothing to protect yet
    else
      echo "✗ cannot read which account $JOB runs as ($(tail -1 "$_sa_err")): refusing to deploy. The live-identity guard fails closed."; rm -f "$_sa_err"; exit 2
    fi
  fi
  rm -f "$_sa_err"
fi
if [[ "${DRY_RUN:-0}" != "1" && "$CUR_SA" == "brain-writer@$PROJECT_ID.iam.gserviceaccount.com" && "$SA" != "$CUR_SA" && "${ALLOW_SA_SWITCH:-0}" != "1" ]]; then
  echo "✗ $JOB still runs as brain-writer: refusing to move it to $SA_NAME on a routine deploy. Run the identity-split script (Sector_Ops #19), or set ALLOW_SA_SWITCH=1 to switch on purpose."; exit 2
fi
echo "▶ job $JOB from $IMAGE (commit $COMMIT)"
run gcloud run jobs deploy "$JOB" --image "$IMAGE" \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --command /app/WaterTempBrainJob \
  --args="--rtdb,$RTDB_URL" \
  --tasks 1 --max-retries 0 --cpu 1 --memory 1Gi --task-timeout 20m \
  --labels "commit=$COMMIT" \
  --set-env-vars "SECTOR_BRAIN_RTDB_URL=$RTDB_URL,SECTOR_ENGINE_COMMIT=$COMMIT"
run gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" --member "serviceAccount:$INVOKER_SA" --role roles/run.invoker
if gcloud scheduler jobs describe "$JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  echo "⚠ a Cloud Scheduler job '$JOB' exists — this Brain is orchestrator-triggered; pause it: gcloud scheduler jobs pause $JOB --location $REGION"
fi
echo "✅ $JOB deployed (no scheduler: brain-orchestrator starts it when stale). Run once: gcloud run jobs execute $JOB --region $REGION"
