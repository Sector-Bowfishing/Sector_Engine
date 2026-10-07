#!/usr/bin/env bash
# Mirror the private Wind shadow archive locally (gcloud user credentials; read-only) and run the
# Stage 3 milestone checks and the validation suite on the mirror.
#   ./check-live.sh 2026-10-07 2026-10-20      # Milestone A (14 days)
#   ./check-live.sh 2026-10-07 2026-11-05      # Milestone B (30 days)
set -euo pipefail
START="${1:?start YYYY-MM-DD}"; END="${2:?end YYYY-MM-DD}"
MIRROR="${MIRROR:-$HOME/Library/Caches/sector-wind/live-mirror}"
PY="${PY:-$HOME/Library/Caches/sector-wind/venv/bin/python}"
cd "$(dirname "$0")"
mkdir -p "$MIRROR"
gcloud storage rsync --recursive gs://sector-wind-candidate/wind/v1 "$MIRROR" --quiet
"$PY" main.py milestone --store "local:$MIRROR" --start "$START" --end "$END" | tee "$MIRROR/milestone_${START}_${END}.json"
"$PY" main.py validate  --store "local:$MIRROR" --start "$START" --end "$END" > "$MIRROR/validation_${START}_${END}.json"
echo "validation -> $MIRROR/validation_${START}_${END}.json"
