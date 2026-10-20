#!/usr/bin/env python3
"""Fish Capability V2 publication prerequisites (docs/brains/scoring/FISH_CAPABILITY_ACTIVATION.md). Edits ONLY the local repository record
docs/brains/scoring/fish-capability-publication.json (changes reach production through a reviewed PR + an approved orchestrator redeploy).
It never approves anything itself: every decision needs a named human (`--reviewer`, `--approved-by`).

  python3 fish_capability_publication.py status [--published-release 2026-10-17.1 | --read-published]   # readiness, read-only
  python3 fish_capability_publication.py record-review --case GC-REF-02 --decision REJECTED --reviewer "Name" [--note "..."]
  python3 fish_capability_publication.py activate --approved-by "Name"
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
from sector_brain_platform import fish_capability as fc      # noqa: E402


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_published_release() -> str | None:
    """GET /brains/biological-state/researchVersion with the operator's gcloud token (read-only)."""
    tok = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True).stdout.strip()
    req = urllib.request.Request("https://sector-brain.firebaseio.com/brains/biological-state/researchVersion.json", headers={"Authorization": f"Bearer {tok}"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"null")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")
    st.add_argument("--published-release")
    st.add_argument("--read-published", action="store_true")
    rv = sub.add_parser("record-review")
    rv.add_argument("--case", required=True)
    rv.add_argument("--decision", required=True, choices=fc.DECISIONS)
    rv.add_argument("--reviewer", required=True)
    rv.add_argument("--note")
    ac = sub.add_parser("activate")
    ac.add_argument("--approved-by", required=True)
    a = ap.parse_args(argv)
    pub = fc.load_json(fc.PUBLICATION_PATH)
    if a.cmd == "status":
        rel = read_published_release() if a.read_published else a.published_release
        ev = fc.load_json(fc.EVIDENCE_PATH) if os.path.exists(fc.EVIDENCE_PATH) else None
        cohorts = {v: fc.load_json(p) for v, p in fc.COHORT_FILES.items()}
        r = fc.activation_readiness(pub, fc.load_json(fc.RUBRIC_PATH), cohorts, ev, rel)
        print(json.dumps(r, indent=1))
        return 0 if r["ready"] else 3
    try:
        new = fc.record_review(pub, a.case, a.decision, a.reviewer, _now(), a.note) if a.cmd == "record-review" else fc.activate(pub, a.approved_by, _now())
    except ValueError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    with open(fc.PUBLICATION_PATH, "w") as fh:
        json.dump(new, fh, indent=1)
        fh.write("\n")
    print(f"recorded in {os.path.relpath(fc.PUBLICATION_PATH)} (commit it on a branch and open a PR; nothing is published until merge + approved redeploy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
