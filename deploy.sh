#!/usr/bin/env bash
#
# Deploy the Sector conditions engine to Cloud Run — GATED.
#
# Nothing reaches users until it has proven itself:
#   1. Refuse to deploy uncommitted changes (every revision maps to a commit).
#   2. Cloud Build the Dockerfile and deploy it as a NO-TRAFFIC revision tagged
#      "candidate", labeled with the git commit.
#   3. Smoke-test the candidate's own URL: /health; a real /conditions render
#      that must carry weather, a Tonight window and 7 nights; and a 400 for a
#      bad coordinate.
#   4. Only then move 100% of traffic to it. If any step fails, prod stays on
#      the revision it was already serving.
#   5. Re-run the smoke test against the PROD URL. If prod fails it, traffic
#      goes straight back to the previous revision.
#
# The "candidate" tag is removed however the script exits, so a failed deploy
# doesn't leave a stray addressable revision behind.
#
# Why gated: until 2026-09-14 this script deployed straight to 100% with no
# check, and a later traffic pin meant a plain deploy silently created a
# revision that served nothing while printing "Deployed".
#
# Usage:
#   ./deploy.sh                       build, verify, promote
#   ./deploy.sh --rollback REVISION   move 100% of traffic back to REVISION
#   CONCURRENCY=8 ./deploy.sh         override per-instance concurrency
#
# One-time setup (needs your Google login):
#   gcloud auth login
#   gcloud config set project sector-9393c
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-sector-engine}"
GC=(--project "$PROJECT_ID" --region "$REGION")

# ── Scaling ────────────────────────────────────────────────────────────────────
# Per-instance concurrency. History (2026-09-14 outage): under Foundation's
# URLSession on Linux, two or more concurrent renders on one instance starved
# Swift's cooperative thread pool and froze the instance (504s, even /health)
# — measured: concurrency 8 froze, 2 hung 1 of 3, 1 was reliable. The engine
# now uses AsyncHTTPClient (validated at 8 and 16 renders on one instance) and
# is data-race free under Swift 6. The default stays at whatever was last
# proven in production; raise it only with a cold-coordinate load test.
CONCURRENCY="${CONCURRENCY:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-20}"   # matches the service-level cap; a higher
                                       # revision value is silently capped anyway

# Health probes. Startup: HTTP /health (was a bare TCP check, which passes
# before the server can answer). Liveness: a frozen instance is restarted after
# ~1 minute — in the outage one stayed in rotation for 35+ minutes. Probes go
# straight to the container and don't count against request concurrency.
STARTUP_PROBE="httpGet.path=/health,httpGet.port=8080,periodSeconds=2,timeoutSeconds=2,failureThreshold=30"
LIVENESS_PROBE="httpGet.path=/health,httpGet.port=8080,periodSeconds=15,timeoutSeconds=5,failureThreshold=4"

# A lake the smoke test renders (Guntersville, AL: weather, USGS, TVA).
SMOKE_LAT="${SMOKE_LAT:-34.35}"
SMOKE_LON="${SMOKE_LON:--86.30}"

smoke_test() {   # smoke_test URL LABEL
  local url="$1" label="$2"
  echo "▶ Smoke-testing $label"
  TARGET_URL="$url" SMOKE_LAT="$SMOKE_LAT" SMOKE_LON="$SMOKE_LON" python3 - <<'PY'
import json, os, sys, time, urllib.request, urllib.error

base = os.environ["TARGET_URL"]
def get(path, timeout):
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:                      # timeout, reset, DNS
        return 0, str(e).encode()

failures = []

status, _ = get("/health", 20)
if status != 200: failures.append(f"/health -> {status}")

render = f"/conditions?lat={os.environ['SMOKE_LAT']}&lon={os.environ['SMOKE_LON']}"
started = time.time()
status, body = get(render, 60)
if status != 200:
    # One retry: a brand-new instance's first render fans out to every upstream
    # cold, and a single upstream blip shouldn't block a good build.
    print(f"  render -> {status}, retrying once in 10s")
    time.sleep(10)
    started = time.time()
    status, body = get(render, 60)
elapsed = time.time() - started
if status != 200:
    failures.append(f"/conditions -> {status} {body[:120]!r}")
else:
    d = json.loads(body)
    if not d.get("weather"): failures.append("render has no weather")
    if not d.get("tonight"): failures.append("render has no Tonight window")
    if len(d.get("nights", [])) != 7: failures.append(f"render has {len(d.get('nights', []))} nights, want 7")
    if "degradedInputs" not in d: failures.append("render lacks degradedInputs")
    if not (0 <= d.get("score", -1) <= 100): failures.append(f"score out of range: {d.get('score')}")
    print(f"  render: score {d.get('score')} {d.get('band')}, degraded {d.get('degradedInputs')}, {elapsed:.1f}s")

status, _ = get("/conditions?lat=95&lon=0", 20)
if status != 400: failures.append(f"bad coordinate -> {status}, want 400")

if failures:
    print("✗ Smoke test failed:\n  - " + "\n  - ".join(failures))
    sys.exit(1)
print("  ✓ health, render, validation")
PY
}

remove_candidate_tag() {
  # Only if the tag is actually there; never fails the script.
  if gcloud run services describe "$SERVICE" "${GC[@]}" --format=json 2>/dev/null \
       | python3 -c 'import json,sys; sys.exit(0 if any(e.get("tag")=="candidate" for e in json.load(sys.stdin)["status"].get("traffic",[])) else 1)'; then
    gcloud run services update-traffic "$SERVICE" "${GC[@]}" --remove-tags candidate --quiet >/dev/null 2>&1 || true
  fi
}

serving_revision() {
  gcloud run services describe "$SERVICE" "${GC[@]}" --format=json | python3 -c '
import json, sys
t = json.load(sys.stdin)["status"]["traffic"]
print(max(t, key=lambda e: e.get("percent", 0)).get("revisionName", ""))'
}

# ── Rollback ───────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--rollback" ]]; then
  [[ -n "${2:-}" ]] || { echo "usage: ./deploy.sh --rollback REVISION"; exit 2; }
  echo "▶ Rolling '$SERVICE' back to $2"
  gcloud run services update-traffic "$SERVICE" "${GC[@]}" --to-revisions "$2=100"
  remove_candidate_tag
  echo "✅ 100% of traffic on $2"
  exit 0
fi

# ── 1. Traceability ────────────────────────────────────────────────────────────
# `--source .` uploads the working directory, untracked files included, so
# those count as uncommitted too.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "✗ Uncommitted or untracked changes. Commit first so this revision maps to a commit."
  git status --short
  exit 1
fi
SHA="$(git rev-parse --short=12 HEAD)"
PREVIOUS="$(serving_revision)"
echo "▶ Deploying '$SERVICE' @ $SHA  (project=$PROJECT_ID region=$REGION concurrency=$CONCURRENCY)"
echo "  currently serving: ${PREVIOUS:-none}"
trap remove_candidate_tag EXIT

# ── 2. Candidate: build + deploy with NO traffic ───────────────────────────────
gcloud run deploy "$SERVICE" \
  --source . \
  "${GC[@]}" \
  --platform managed \
  --allow-unauthenticated \
  --no-traffic \
  --tag candidate \
  --labels "commit=$SHA" \
  --memory 2Gi \
  --cpu 4 \
  --concurrency "$CONCURRENCY" \
  --timeout 60 \
  --min-instances 1 \
  --max-instances "$MAX_INSTANCES" \
  --startup-probe "$STARTUP_PROBE" \
  --liveness-probe "$LIVENESS_PROBE" \
  --quiet

# The revision this deploy just created, and the tag URL pointing at it. Both
# must agree — a leftover "candidate" tag on an older revision must never be
# what gets tested or promoted.
read -r CANDIDATE CANDIDATE_URL < <(gcloud run services describe "$SERVICE" "${GC[@]}" --format=json | python3 -c '
import json, os, sys
svc = json.load(sys.stdin)
latest = svc["status"].get("latestCreatedRevisionName", "")
url = next((e["url"] for e in svc["status"].get("traffic", [])
            if e.get("tag") == "candidate" and e.get("revisionName") == latest), "")
print(latest, url)')
[[ -n "${CANDIDATE:-}" && -n "${CANDIDATE_URL:-}" ]] || { echo "✗ Couldn't find the new revision behind the candidate tag."; exit 1; }
LABEL="$(gcloud run revisions describe "$CANDIDATE" "${GC[@]}" --format 'value(metadata.labels.commit)')"
[[ "$LABEL" == "$SHA" ]] || { echo "✗ Revision $CANDIDATE is labeled commit=$LABEL, expected $SHA."; exit 1; }
echo "  candidate: $CANDIDATE  $CANDIDATE_URL"

# ── 3. Smoke test the candidate ────────────────────────────────────────────────
if ! smoke_test "$CANDIDATE_URL" "the candidate"; then
  echo "✗ Candidate $CANDIDATE did NOT pass. Prod is still on ${PREVIOUS:-its previous revision}."
  exit 1
fi

# ── 4. Promote ─────────────────────────────────────────────────────────────────
echo "▶ Promoting $CANDIDATE to 100% of traffic"
gcloud run services update-traffic "$SERVICE" "${GC[@]}" --to-revisions "$CANDIDATE=100" --quiet
remove_candidate_tag

# ── 5. Verify prod, roll back automatically if it fails ────────────────────────
URL="$(gcloud run services describe "$SERVICE" "${GC[@]}" --format 'value(status.url)')"
if ! smoke_test "$URL" "prod"; then
  if [[ -n "$PREVIOUS" ]]; then
    echo "✗ Prod failed after promotion — rolling back to $PREVIOUS"
    gcloud run services update-traffic "$SERVICE" "${GC[@]}" --to-revisions "$PREVIOUS=100" --quiet
    echo "  100% of traffic back on $PREVIOUS. $CANDIDATE kept for inspection (0% traffic)."
  else
    echo "✗ Prod failed after promotion and there is no previous revision to roll back to."
  fi
  exit 1
fi

echo
echo "✅ $CANDIDATE serving 100% (commit $SHA), verified on prod."
echo "   Rollback: ./deploy.sh --rollback ${PREVIOUS:-<previous-revision>}"
