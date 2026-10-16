#!/usr/bin/env bash
#
# Warm-tag cost guard (cost work 2026-10-13, Phase 16). A Cloud Run revision with a traffic TAG and revision-level
# minScale >= 1 keeps a warm instance billed around the clock even at 0 % traffic — the 2026-10 "446.9 server-hours"
# were exactly this (fusion / clarity tags on minScale-1 revisions). This prints every such revision and exits 1
# when one exists, so deploy.sh and a human can see it. It changes nothing (tags are public URLs; removing one is a
# decision): fix with  gcloud run services update-traffic SERVICE --remove-tags TAG  or re-tag a minScale-0 revision.
#
#   ./ops/check_warm_tags.sh [SERVICE]        default sector-engine
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-sector-9393c}"
REGION="${REGION:-us-central1}"
SERVICE="${1:-sector-engine}"
gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format json | python3 -c '
import json, subprocess, sys
svc = json.load(sys.stdin)
project, region = sys.argv[1], sys.argv[2]
bad = []
for t in svc["status"].get("traffic", []):
    rev, pct, tag = t.get("revisionName"), t.get("percent") or 0, t.get("tag")
    if not tag or pct:
        continue
    r = json.loads(subprocess.run(["gcloud", "run", "revisions", "describe", rev, "--project", project, "--region", region, "--format", "json"],
                                  capture_output=True, text=True, check=True).stdout)
    ms = (r["metadata"].get("annotations") or {}).get("autoscaling.knative.dev/minScale")
    if ms and int(ms) >= 1:
        bad.append((tag, rev, ms))
if bad:
    for tag, rev, ms in bad:
        print(f"✗ tag {tag!r} → {rev} has minScale {ms} at 0 % traffic: one warm instance billed 24 h/day")
    print("  fix: gcloud run services update-traffic SERVICE --remove-tags TAG   (or tag a minScale-0 revision)")
    sys.exit(1)
print("✓ no tagged 0 %-traffic revision keeps a warm instance")
' "$PROJECT_ID" "$REGION"
