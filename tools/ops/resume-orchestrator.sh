#!/usr/bin/env bash
#
# OWNER-ONLY: resume the single central Brain trigger (brain-orchestrator Cloud Scheduler). Rehtac Cortex 2.7.0 PL-15..PL-18.
# Never run by a deployment. Resuming recurring Brain execution starts recurring cloud spending, which needs the owner's explicit authorization.
#
#   OWNER_APPROVAL_REF=<ref> bash tools/ops/resume-orchestrator.sh
#
# Preflight (all must pass, else nothing is resumed):
#   1. /control/executionControlV1 is ENABLED with exactly this approvalRef (set first with tools/ops/execution_control.py enable)
#   2. check_preproduction_schedules.py passes (no deprecated per-Brain scheduler is ENABLED)
#   3. no brain-orchestrator execution is running
#   4. one --dry-run orchestrator cycle succeeds in Cloud Run (writes nothing, starts nothing)
# Stop at any time: gcloud scheduler jobs pause brain-orchestrator --location us-central1
#                   python3 tools/ops/execution_control.py pause --changed-by <name> --reason "<why>"
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
JOB=brain-orchestrator
: "${OWNER_APPROVAL_REF:?set OWNER_APPROVAL_REF to the recorded owner authorization}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "▶ 1. execution control"
python3 - "$OWNER_APPROVAL_REF" <<'EOF'
import json, subprocess, sys, urllib.request
ref = sys.argv[1]
tok = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()
raw = json.loads(urllib.request.urlopen(urllib.request.Request("https://sector-brain.firebaseio.com/control/executionControlV1.json",
                 headers={"Authorization": f"Bearer {tok}"}), timeout=20).read() or b"null")
ok = isinstance(raw, dict) and raw.get("schema") == "brain-execution-control-v1" and raw.get("state") == "ENABLED" and raw.get("approvalRef") == ref
print("  ", (raw or {}).get("state"), "approvalRef", (raw or {}).get("approvalRef"))
sys.exit(0 if ok else 1)
EOF
echo "▶ 2. schedule audit"
python3 "$ROOT/jobs/brain-orchestrator/check_preproduction_schedules.py" || { echo "refusing: schedule audit failed"; exit 1; }
if gcloud scheduler jobs list --location "$REGION" --project "$PROJECT_ID" --format='value(name.basename(),state)' | grep -E '^(wind-hourly|lake-brain-ledger-daily)\s+ENABLED'; then
  echo "refusing: a deprecated per-Brain scheduler is ENABLED"; exit 1
fi
echo "▶ 3. no running cycle"
if gcloud run jobs executions list --job "$JOB" --region "$REGION" --project "$PROJECT_ID" --limit 5 --format='value(status.runningCount)' | grep -qE '^[1-9]'; then
  echo "refusing: a $JOB execution is running"; exit 1
fi
echo "▶ 4. dry cycle in Cloud Run"
gcloud run jobs execute "$JOB" --region "$REGION" --project "$PROJECT_ID" --args=--dry-run --wait
echo "▶ resume $JOB (approvalRef $OWNER_APPROVAL_REF)"
gcloud scheduler jobs resume "$JOB" --location "$REGION" --project "$PROJECT_ID"
gcloud scheduler jobs describe "$JOB" --location "$REGION" --project "$PROJECT_ID" --format='value(state,schedule)'
echo "rollback: gcloud scheduler jobs pause $JOB --location $REGION; python3 tools/ops/execution_control.py pause --changed-by <name> --reason \"<why>\""
