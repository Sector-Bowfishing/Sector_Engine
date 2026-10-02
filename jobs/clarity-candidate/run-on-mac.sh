#!/usr/bin/env bash
#
# One shadow run on macOS arm64, the reference environment where the frozen candidate reproduces bit for bit (the
# Cloud Run image does not; see research/clarity-candidate/provenance/CROSS_PLATFORM_REPRODUCTION.md). Same job,
# same self-checks, same private bucket. Four tasks share the lakes; they start staggered so two never fetch the same
# golden L1C at once.
#
#   RESEARCH=<a bootstrapped research/clarity-candidate> ./jobs/clarity-candidate/run-on-mac.sh [LOOKBACK_DAYS]
set -u
J="$(cd "$(dirname "$0")" && pwd)"
R="${RESEARCH:-$J/../../research/clarity-candidate}"
LOG="${LOG:-${TMPDIR:-/tmp}/clarity-candidate-mac}"
LOOKBACK="${1:-10}"
[ -x "$R/geo/bin/python" ] || { echo "bootstrap the research environment first: $R/env/bootstrap.sh" >&2; exit 1; }
mkdir -p "$LOG"
EX="mac-$(date -u +%Y%m%dT%H%M%S)"; echo "$EX" > "$LOG/execution"
export CLARITY_RESEARCH_ROOT="$R" BUCKET="${BUCKET:-sector-clarity-candidate}" CLOUD_RUN_TASK_COUNT=4 CLOUD_RUN_EXECUTION="$EX"
export JOB_COMMIT="$(git -C "$J" rev-parse HEAD)+mac"
for k in 0 1 2 3; do
  CLOUD_RUN_TASK_INDEX=$k "$R/geo/bin/python" "$J/shadow.py" --lookback "$LOOKBACK" > "$LOG/task$k.log" 2>&1 &
  echo "task $k pid $!"
  if [ $k -eq 0 ]; then until grep -q "self-check" "$LOG/task0.log" 2>/dev/null; do sleep 10; done; else sleep 150; fi
done
wait
echo "done: $EX (logs in $LOG)"
