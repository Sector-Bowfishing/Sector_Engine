#!/usr/bin/env bash
#
# Linux smoke test for the Cloud Run image. deploy.sh runs it before every
# deploy.
#
# Builds the SAME Dockerfile Cloud Build uses, runs it with the Stage 2
# routes switched on, calls every route, and fails if any call gets no answer
# or the container dies. On 2026-09-27 three revisions (00041-00043) passed
# `swift build` and `swift test` on macOS, and then aborted the Linux Swift
# runtime on their first request ("freed pointer was not the last
# allocation", signal 6). Only running the Linux image catches that.
#
#   ./scripts/linux-smoke.sh              build, run, check (exit 1 on failure)
#   SMOKE_PORT=8093 IMAGE=… ./scripts/linux-smoke.sh
#
# Upstream feeds can be down (Open-Meteo black-holes from some networks), so a
# /conditions 503 counts as an answer; a dead container, a dropped
# connection, or a runtime abort in the logs never does.
#
set -uo pipefail
cd "$(dirname "$0")/.."
IMAGE="${IMAGE:-sector-engine-smoke}"
PORT="${SMOKE_PORT:-8093}"
NAME="sector-engine-smoke-$$"
LAKE="Guntersville%7CAL"
FAIL=0

if ! docker info >/dev/null 2>&1; then
  echo "✗ Docker is not running. Start Docker Desktop (open -a Docker) or set SKIP_LINUX_SMOKE=1 knowingly." >&2
  exit 2
fi

echo "▶ building the Cloud Run image on Linux ($IMAGE)"
if ! docker build -q -t "$IMAGE" . >/dev/null; then
  echo "✗ docker build failed" >&2; exit 1
fi
docker run -d --name "$NAME" -p "$PORT:8080" -e SECTOR_STAGE2_ROUTES=1 -e SECTOR_CURRENT_CLARITY_ROUTES=1 "$IMAGE" >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT

for _ in $(seq 1 30); do
  curl -sf "http://localhost:$PORT/health" >/dev/null && break
  sleep 1
done

# check <label> <accepted statuses> <curl args...>
check() {
  local label="$1" ok="$2"; shift 2
  local out code
  out=$(mktemp)
  code=$(curl -s -o "$out" -w "%{http_code}" --max-time 90 "$@")
  if [[ " $ok " != *" $code "* ]]; then
    echo "✗ $label → HTTP $code"; FAIL=1
  elif [[ "$code" == 200 && "$label" == *cells* ]]; then
    # the map's composite is a binary file: its magic, not JSON
    if [[ "$(head -c 4 "$out")" == SCCC ]]; then echo "✓ $label → $code"; else echo "✗ $label → 200 but not a composite"; FAIL=1; fi
  elif [[ "$code" == 200 ]] && ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$out" 2>/dev/null \
       && [[ "$label" != health ]]; then
    echo "✗ $label → 200 but not JSON"; FAIL=1
  else
    echo "✓ $label → $code"
  fi
  rm -f "$out"
  if [[ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" != "true" ]]; then
    echo "✗ the container died during: $label"; FAIL=1
    docker logs "$NAME" 2>&1 | tail -5
    exit 1
  fi
}

B="http://localhost:$PORT"
check health                              "200"     "$B/health"
check "conditions, South Sauty (gauged)"  "200 503" "$B/conditions?lat=34.52741&lon=-86.10789&fresh=1"
check "conditions, Town Creek (gauged)"   "200 503" "$B/conditions?lat=34.40823&lon=-86.21072&fresh=1"
check "conditions, main stem"             "200 503" "$B/conditions?lat=34.38555&lon=-86.32488&fresh=1"
check "conditions, lake with no graph"    "200 503" "$B/conditions?lat=30.42&lon=-97.93&fresh=1"
check "conditions/batch"                  "200 503" -X POST -H "Content-Type: application/json" \
      -d '{"points":[{"lat":34.41,"lon":-86.21},{"lat":34.53,"lon":-86.11}]}' "$B/conditions/batch"
check lakes                               "200"     "$B/lakes"
check "hydrology/graph"                   "200"     "$B/hydrology/graph?lake=$LAKE"
check "hydrology (cold)"                  "200"     "$B/hydrology?lake=$LAKE"
check "hydrology (cached)"                "200"     "$B/hydrology?lake=$LAKE"
check "clarity/state, an arm"             "200"     "$B/clarity/state?lake=$LAKE&lat=34.40823&lon=-86.21072"
check "clarity/state, the main stem"      "200"     "$B/clarity/state?lake=$LAKE&lat=34.38555&lon=-86.32488"
check "clarity/state, land"               "200"     "$B/clarity/state?lake=$LAKE&lat=34.30&lon=-86.25"
check "clarity/states"                    "200"     "$B/clarity/states?lake=$LAKE"
check "clarity/current/lake"              "200"     "$B/clarity/current/lake?lake=$LAKE"
check "clarity/current/cells"             "200"     "$B/clarity/current/cells?lake=$LAKE"
check "clarity/current, an arm"           "200"     "$B/clarity/current?lake=$LAKE&lat=34.40823&lon=-86.21072"
check "clarity/current, land"             "200"     "$B/clarity/current?lake=$LAKE&lat=34.3585&lon=-86.2945"
check "clarity/current/change"            "200"     "$B/clarity/current/change?lake=$LAKE&region=town-creek-marshall&since=2026-09-27T00:00:00Z"

if docker logs "$NAME" 2>&1 | grep -E "freed pointer|Fatal error|Uncaught signal|Illegal instruction" >/dev/null; then
  echo "✗ runtime abort in the container log:"; docker logs "$NAME" 2>&1 | grep -E "freed pointer|Fatal error|Uncaught signal" | head -3
  FAIL=1
fi
if [[ "$(docker inspect -f '{{.RestartCount}}' "$NAME")" != "0" ]]; then echo "✗ the container restarted"; FAIL=1; fi

if [[ $FAIL -ne 0 ]]; then echo "✗ Linux smoke test FAILED"; exit 1; fi
echo "✅ Linux smoke test passed"
