#!/usr/bin/env bash
#
# Deploy the Sector conditions engine to Cloud Run — gated, traceable, reversible.
#
# Builds from source with Cloud Build (no local Docker needed — Google builds the
# Dockerfile), then deploys to Cloud Run in the same GCP project as Firebase.
# Both phones pick up the new numbers on their next call — no App Store release.
#
# Traffic is PINNED to a named revision (since the 2026-09-14 outage rollback), so
# a plain `gcloud run deploy` builds a new revision and then serves none of it —
# "✅ Deployed" while the phones keep getting the old numbers (bit us twice in
# September). This script instead:
#
#   0. refuses a dirty tree, and a HEAD that is not on `main` (production policy,
#      docs/production/PRODUCTION_LINEAGE.md) — every revision maps to a main commit,
#   1. deploys the new revision with NO traffic behind a `candidate` tag, labeled
#      with the commit it was built from,
#   2. smoke-tests the candidate (health, a real Guntersville render, validation),
#   3. moves 100% of traffic to it only if the smoke test passed,
#   4. re-runs the smoke test against prod and rolls back automatically if it fails,
#   5. prints the tag command and the one-line rollback.
#
# One-time setup (run these yourself, they need your Google login):
#   gcloud auth login
#   gcloud config set project sector-9393c
#   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
#
# Usage:
#   ./deploy.sh                       deploy HEAD (must be a clean checkout of main)
#   ./deploy.sh --rollback REVISION   put 100% of traffic back on REVISION
#   SKIP_SMOKE=1 ./deploy.sh          deploy without the smoke test (emergencies only)
#   ALLOW_BRANCH_DEPLOY=1 ./deploy.sh deploy from a non-main branch (emergencies only;
#                                     the revision is still labeled with its commit)
#
# History: the candidate/smoke/promote flow is from fix/forecast-rain-gate (2c53d64c);
# the traceability gate, probes, prod verification and auto-rollback are from
# feat/engine-hardening (0df27076, a396a6cb); reconciled 2026-10-12 (consolidation
# Phase 2) with the sizing production actually runs (sector-engine-00080-wes).
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-sector-engine}"
GC=(--project "$PROJECT_ID" --region "$REGION")

# ── Sizing ─────────────────────────────────────────────────────────────────────
# These match the LIVE revision (00080-wes, 2026-10-12 cost right-sizing): cpu 2,
# memory 1Gi, min 1, max 30. 00072-way ran cpu 4 / 2Gi on the same source.
# Per-instance concurrency stays at 1 — do NOT raise it without understanding the
# 2026-09-14 outage: under Foundation's URLSession on Linux, two or more concurrent
# cold renders on one instance starved Swift's cooperative thread pool and froze the
# instance (504s, even /health). The engine now fetches with AsyncHTTPClient, but
# nothing above 1 has been proven in production. Raise only with a cold-coordinate
# load test, then record the new value in the deployed/* tag message.
CPU="${CPU:-2}"
MEMORY="${MEMORY:-1Gi}"
CONCURRENCY="${CONCURRENCY:-1}"
MIN_INSTANCES="${MIN_INSTANCES:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-30}"

# Health probes. Startup: HTTP /health (the default is a bare TCP check, which
# passes before the server can answer). Liveness: a frozen instance is restarted
# after ~1 minute — in the outage one stayed in rotation for 35+ minutes. Probes go
# straight to the container and don't count against request concurrency.
STARTUP_PROBE="httpGet.path=/health,httpGet.port=8080,periodSeconds=2,timeoutSeconds=2,failureThreshold=30"
LIVENESS_PROBE="httpGet.path=/health,httpGet.port=8080,periodSeconds=15,timeoutSeconds=5,failureThreshold=4"

# A lake the smoke test renders (Guntersville, AL: weather, USGS, TVA).
SMOKE_LAT="${SMOKE_LAT:-34.35}"
SMOKE_LON="${SMOKE_LON:--86.30}"

smoke_test() {   # smoke_test URL LABEL
  local url="$1" label="$2"
  if [[ "${SKIP_SMOKE:-0}" == "1" ]]; then
    echo "▶ Smoke test of $label SKIPPED (SKIP_SMOKE=1)"
    return 0
  fi
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

# /health first — a cold instance answers this as soon as it's up.
status = 0
for attempt in range(5):
    status, _ = get("/health", 20)
    if status == 200: break
    time.sleep(5)
if status != 200: failures.append(f"/health -> {status}")

render = f"/conditions?lat={os.environ['SMOKE_LAT']}&lon={os.environ['SMOKE_LON']}"
started = time.time()
status, body = get(render, 90)
if status != 200:
    # One retry: a brand-new instance's first render fans out to every upstream
    # cold, and a single upstream blip shouldn't block a good build.
    print(f"  render -> {status}, retrying once in 10s")
    time.sleep(10)
    started = time.time()
    status, body = get(render, 90)
elapsed = time.time() - started
if status != 200:
    failures.append(f"/conditions -> {status} {body[:120]!r}")
else:
    d = json.loads(body)
    # Fields every production response has carried since 2026-08 (score, band,
    # weather, tonight, nights). Don't require fields prod doesn't emit yet.
    if not (0 <= d.get("score", -1) <= 100): failures.append(f"score out of range: {d.get('score')}")
    if d.get("band") not in ("Poor", "Fair", "Good", "Prime"): failures.append(f"band: {d.get('band')!r}")
    if not d.get("weather"): failures.append("render has no weather")
    if not d.get("tonight"): failures.append("render has no Tonight window")
    if len(d.get("nights", [])) != 7: failures.append(f"render has {len(d.get('nights', []))} nights, want 7")
    print(f"  render: score {d.get('score')} {d.get('band')}, {elapsed:.1f}s")

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

# ── 0. Traceability ────────────────────────────────────────────────────────────
# `--source .` uploads the working directory, untracked files included, so
# those count as uncommitted too.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "✗ Uncommitted or untracked changes. Commit first so this revision maps to a commit."
  git status --short
  exit 1
fi
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" && "${ALLOW_BRANCH_DEPLOY:-0}" != "1" ]]; then
  echo "✗ HEAD is on '$BRANCH', not main. Production deploys are built from main"
  echo "  (docs/production/PRODUCTION_LINEAGE.md). Merge first, or ALLOW_BRANCH_DEPLOY=1 for an emergency."
  exit 1
fi
if [[ "$BRANCH" == "main" ]] && ! git diff --quiet HEAD origin/main 2>/dev/null; then
  echo "⚠ local main differs from origin/main — push first so the deployed commit is on the remote."
fi
SHA="$(git rev-parse --short=12 HEAD)"
PREVIOUS="$(serving_revision)"
echo "▶ Deploying '$SERVICE' @ $SHA ($BRANCH)  (project=$PROJECT_ID region=$REGION cpu=$CPU mem=$MEMORY concurrency=$CONCURRENCY)"
echo "  currently serving: ${PREVIOUS:-none}"
trap remove_candidate_tag EXIT

# ── 1. Candidate: build + deploy with NO traffic ───────────────────────────────
# Env vars already on the service are kept (no --set-env-vars / --clear-env-vars).
gcloud run deploy "$SERVICE" \
  --source . \
  "${GC[@]}" \
  --platform managed \
  --allow-unauthenticated \
  --no-traffic \
  --tag candidate \
  --labels "commit=$SHA" \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --concurrency "$CONCURRENCY" \
  --timeout 60 \
  --min-instances "$MIN_INSTANCES" \
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

# ── 2. Smoke test the candidate ────────────────────────────────────────────────
if ! smoke_test "$CANDIDATE_URL" "the candidate"; then
  echo "✗ Candidate $CANDIDATE did NOT pass. Prod is still on ${PREVIOUS:-its previous revision}."
  echo "  Logs: gcloud logging read 'resource.labels.revision_name=\"$CANDIDATE\"' --project $PROJECT_ID --limit 50"
  exit 1
fi

# ── 3. Promote ─────────────────────────────────────────────────────────────────
echo "▶ Promoting $CANDIDATE to 100% of traffic"
gcloud run services update-traffic "$SERVICE" "${GC[@]}" --to-revisions "$CANDIDATE=100" --quiet
remove_candidate_tag

# ── 4. Verify prod, roll back automatically if it fails ────────────────────────
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
echo "   Tag it:   git tag -a deployed/$CANDIDATE $SHA -m 'Production $(date -u +%Y-%m-%dT%H:%MZ): <what changed>' && git push origin deployed/$CANDIDATE"
echo "   Rollback: ./deploy.sh --rollback ${PREVIOUS:-<previous-revision>}"
