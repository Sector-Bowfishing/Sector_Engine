#!/usr/bin/env bash
#
# The Current Clarity candidate SHADOW job (uncertified): the frozen Stage 16 candidate and the Stage 17 challenger on
# new Sentinel-2 passes over the pilot lakes. It never touches production.
#
#   bucket     gs://$BUCKET — PRIVATE (public access prevention); shadow/v1/{scenes,log,latest,runs}/…
#   account    $SA — writes only that bucket; runs the job for the scheduler
#   job        $JOB — one task per pilot lake; every task self-checks against the frozen outputs first
#   schedule   $SCHEDULE_JOB — daily at $CRON ($SCHEDULE_TZ), after lake-surface-daily has published the day's layer
#   engine     the engine's runtime account may READ the bucket (the 0%-traffic tag's /clarity/candidate route)
#
# The image is staged here, not built from the repo root: research/clarity-candidate (as committed), ACOLITE fetched at
# its pinned commit, the LUTs from the private backup, and this folder. Safe to re-run.
#
#   ./jobs/clarity-candidate/deploy-job.sh
#   NO_SCHEDULE=1 ./jobs/clarity-candidate/deploy-job.sh        (job only)
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-sector-clarity-candidate}"
JOB="${JOB:-clarity-candidate-shadow}"
SCHEDULE_JOB="${SCHEDULE_JOB:-clarity-candidate-shadow}"
SA_NAME="${SA_NAME:-clarity-candidate-job}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
ENGINE_SA="${ENGINE_SA:-1021938854392-compute@developer.gserviceaccount.com}"
CRON="${CRON:-0 7 * * *}"
SCHEDULE_TZ="${SCHEDULE_TZ:-America/Chicago}"
LUT_FROM="${LUT_FROM:-gs://$BUCKET/acolite/f73cbe7/LUT}"
cd "$(dirname "$0")/../.."
REPO="$PWD"
COMMIT="$(git rev-parse HEAD)"
[ -z "$(git status --porcelain -- research/clarity-candidate jobs/clarity-candidate)" ] || { echo "commit research/ and jobs/clarity-candidate first" >&2; exit 1; }

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/clarity-candidate-build.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
echo "▶ staging $STAGE (commit $COMMIT)"
git archive HEAD research/clarity-candidate jobs/clarity-candidate | tar -x -C "$STAGE"
ACO="$STAGE/research/clarity-candidate/stage11/tools/acolite/src"
ACO_COMMIT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["commit"])' "$STAGE/research/clarity-candidate/env/acolite.lock.json")"
git init -q "$ACO" && git -C "$ACO" fetch -q --depth 1 https://github.com/acolite/acolite "$ACO_COMMIT" \
  && git -C "$ACO" -c advice.detachedHead=false checkout -q "$ACO_COMMIT"
CLOUDSDK_STORAGE_SLICED_OBJECT_DOWNLOAD_THRESHOLD=0 gcloud storage cp -r "$LUT_FROM" "$ACO/data/" --project "$PROJECT_ID" >/dev/null
cp jobs/clarity-candidate/Dockerfile "$STAGE/Dockerfile"
# An empty .gcloudignore uploads everything: gcloud's default one would drop ACOLITE's .git (the image checks the commit)
# and everything research/clarity-candidate/.gitignore lists (the ACOLITE tree itself).
: > "$STAGE/.gcloudignore"

echo "▶ bucket gs://$BUCKET (private)"
gcloud storage buckets describe "gs://$BUCKET" --project "$PROJECT_ID" --format "value(name)" >/dev/null

echo "▶ service account $SA"
if ! gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name "Clarity candidate shadow job"
fi
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectAdmin >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$ENGINE_SA" --role roles/storage.objectViewer >/dev/null

TASKS="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["lakes"]))' jobs/clarity-candidate/pilot_lakes.json)"
echo "▶ job $JOB ($TASKS tasks)"
gcloud run jobs deploy "$JOB" --source "$STAGE" \
  --project "$PROJECT_ID" --region "$REGION" --service-account "$SA" \
  --tasks "$TASKS" --parallelism 9 --max-retries 1 \
  --cpu 2 --memory 8Gi --task-timeout 6h \
  --set-env-vars "BUCKET=$BUCKET,LOOKBACK_DAYS=10,JOB_COMMIT=$COMMIT"
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:$SA" --role roles/run.invoker >/dev/null

if [ -z "${NO_SCHEDULE:-}" ]; then
  echo "▶ schedule $SCHEDULE_JOB ($CRON $SCHEDULE_TZ)"
  RUN_URI="https://run.googleapis.com/v2/projects/$PROJECT_ID/locations/$REGION/jobs/$JOB:run"
  if gcloud scheduler jobs describe "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" \
      --schedule "$CRON" --time-zone "$SCHEDULE_TZ" --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA"
  else
    gcloud scheduler jobs create http "$SCHEDULE_JOB" --project "$PROJECT_ID" --location "$REGION" \
      --schedule "$CRON" --time-zone "$SCHEDULE_TZ" --uri "$RUN_URI" --http-method POST --oauth-service-account-email "$SA"
  fi
fi

echo
echo "✅ Run now (first run: a 20-day backfill):"
echo "   gcloud run jobs execute $JOB --project $PROJECT_ID --region $REGION --update-env-vars LOOKBACK_DAYS=20"
echo "   Results (private): gcloud storage ls gs://$BUCKET/shadow/v1/latest/"
