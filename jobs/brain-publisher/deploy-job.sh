#!/usr/bin/env bash
#
# brain-publisher: the recurring central Publisher job (Cortex 3.1 PL-19, FD-15). PREPARED 2026-10-31; deploying needs Michael's explicit go
# (Sector_Ops 19) and this script refuses without MICHAEL_APPROVED_BRAIN_PUBLISHER_DEPLOY=yes.
#
#   job        $JOB: Cloud Run Job, one task, one bounded pass per execution (publish_job.py). NO scheduler: brain-orchestrator starts it (PL-15).
#   account    $SA: the Publisher identity. It must already exist with its approved grants; this script creates no identity and binds no role
#              (the identity split is its own approved step with a tested denial, Sector_Ops 19).
#   mode       PUBLISHER_MODE=dry-run (default): the identical preparation, nothing written. PUBLISHER_MODE=live passes --live and needs its own approval.
#
#   ./deploy-job.sh --stage-only DIR   assemble the build context into DIR and exit (no gcloud; used by tests and review)
#
set -euo pipefail
JOB_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$JOB_DIR/../.." && pwd)"
CUTOVER="$REPO_ROOT/jobs/brain-orchestrator/publication-cutover.json"      # the ONE reviewed cutover document; the Orchestrator image stages the same file

stage_context() {
  local dest="$1"
  mkdir -p "$dest/releases"
  cp "$JOB_DIR/Dockerfile" "$JOB_DIR/publish_job.py" "$dest/"
  cp "$CUTOVER" "$dest/publication-cutover.json"
  cp -R "$REPO_ROOT/jobs/brain_platform/sector_brain_platform" "$dest/sector_brain_platform"
  # each CENTRAL Brain's packaged knowledge release (knowledge-release.json + the files it lists), under releases/<brainId>/
  python3 - "$CUTOVER" "$REPO_ROOT" "$dest/releases" <<'PY'
import json, os, shutil, sys
cut, root, out = sys.argv[1], sys.argv[2], sys.argv[3]
central = [b for b, e in json.load(open(cut))["brains"].items() if e.get("state") == "CENTRAL"]
dirs = {}
for d in sorted(os.listdir(os.path.join(root, "brains"))):
    p = os.path.join(root, "brains", d, "brain.json")
    if os.path.exists(p):
        dirs[json.load(open(p))["brainId"]] = os.path.join(root, "brains", d, "runtime")
for b in central:
    rel = os.path.join(dirs[b], "knowledge-release.json")
    if not os.path.exists(rel):
        sys.exit(f"{b} is CENTRAL but has no packaged knowledge release")
    os.makedirs(os.path.join(out, b))
    shutil.copy(rel, os.path.join(out, b))
    for f in json.load(open(rel))["files"]:
        shutil.copy(os.path.join(dirs[b], f["path"]), os.path.join(out, b, f["path"]))
PY
  find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +
}
if [[ "${1:-}" == "--stage-only" ]]; then
  stage_context "${2:?--stage-only needs a destination directory}"
  echo "staged brain-publisher build context -> $2"
  exit 0
fi
if [[ "${MICHAEL_APPROVED_BRAIN_PUBLISHER_DEPLOY:-}" != "yes" ]]; then
  echo "Refusing: set MICHAEL_APPROVED_BRAIN_PUBLISHER_DEPLOY=yes only after Michael approves the brain-publisher deploy (Sector_Ops 19)." >&2
  exit 2
fi

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-brain-publisher}"
SA_NAME="${SA_NAME:-sector-publisher}"
SA="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
ARTIFACT_BUCKET="${PUBLICATION_ARTIFACT_BUCKET:?set PUBLICATION_ARTIFACT_BUCKET to the private artifact bucket}"
PUBLISHER_MODE="${PUBLISHER_MODE:-dry-run}"
[[ "$PUBLISHER_MODE" == "dry-run" || "$PUBLISHER_MODE" == "live" ]] || { echo "PUBLISHER_MODE must be dry-run or live" >&2; exit 2; }
ARGS="--max-artifacts;${MAX_ARTIFACTS:-4}"
[[ "$PUBLISHER_MODE" == "live" ]] && ARGS="$ARGS;--live"
COMMIT="$(git -C "$REPO_ROOT" rev-parse --short=12 HEAD)"

gcloud iam service-accounts describe "$SA" --project "$PROJECT_ID" >/dev/null || { echo "service account $SA missing (create it in the approved identity step)" >&2; exit 2; }

echo "▶ job $JOB (mode $PUBLISHER_MODE; commit $COMMIT)"
CONTEXT="$(mktemp -d)"
trap 'rm -rf "$CONTEXT"' EXIT
stage_context "$CONTEXT"
cd "$CONTEXT"
gcloud run jobs deploy "$JOB" --source . \
  --project "$PROJECT_ID" --region "$REGION" \
  --service-account "$SA" \
  --tasks 1 --max-retries 0 --cpu 1 --memory 1Gi --task-timeout 20m \
  --labels "commit=$COMMIT,mode=$PUBLISHER_MODE" \
  --args="^;^$ARGS" \
  --set-env-vars "BRAIN_TOKEN_MODE=metadata,BRAIN_RTDB_URL=https://sector-brain.firebaseio.com,PUBLICATION_ARTIFACT_BUCKET=$ARTIFACT_BUCKET,DEPLOYMENT_VERSION=brain-publisher@$COMMIT"

echo
echo "✅ deployed (no scheduler: brain-orchestrator starts it). Admin run (needs its own approval): gcloud run jobs execute $JOB --project $PROJECT_ID --region $REGION --args=--admin-ref,<approval> --wait"
echo "   rollback: gcloud run jobs delete $JOB --region $REGION (or redeploy the previous commit); the Publisher's history and heads are never rewritten by a rollback of this job"
