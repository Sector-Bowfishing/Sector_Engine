#!/usr/bin/env python3
"""Generation Brain run entry (CALIBRATION). Registered in the control manifest PARKED with no execution target; never scheduled.

  python run.py --plan                         # which bound dams are due? reads published states only (GET). BLOCKED while the release is not approved
  python run.py --dry-run [--allow-unapproved-release] [--fixtures DIR] [--scope bound|fleet] [--lake ID]
                                               # read the sources (or a fixture directory), build every write in memory, print the report
  python run.py --write                        # publish: needs an APPROVED knowledge release AND GENERATION_WRITE_APPROVED=1 (operator intent)

Knowledge comes ONLY from the verified release in runtime/knowledge/ (generation_brain.knowledge). Live inputs come ONLY from the official
sources the release binds and allows (generation_brain.http: access-gated, retried, at most one read per URL per run). A missing or tampered
release refuses the run (exit 2); an unapproved release is never published from (exit 2, BLOCKED_AWAITING_APPROVED_RELEASE)."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generation_brain  # noqa: E402,F401  (bootstraps the platform path)
from generation_brain import contract as C, knowledge as K  # noqa: E402
from generation_brain.fixtures import fixture_transport  # noqa: E402
from generation_brain.freshness import due  # noqa: E402
from generation_brain.http import Fetcher  # noqa: E402
from generation_brain.publish import publish  # noqa: E402
from generation_brain.state import readiness_of  # noqa: E402
from generation_brain.writer import DryRunWriter, RtdbWriter  # noqa: E402

RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")


def plan_verdict(k: "K.Knowledge", rtdb_url: str = RTDB_URL) -> dict:
    if not k.approved:
        return {"brainId": C.BRAIN_ID, "action": "SKIP", "status": K.BLOCKED, "knowledgeRelease": k.summary(),
                "reason": "no APPROVED knowledge release: Generation abstains (nothing is published from unapproved knowledge)"}
    from datetime import datetime, timezone
    from sector_brain_platform import BrainRtdb, lake_key
    db = BrainRtdb(rtdb_url, brain_id=C.BRAIN_ID)
    access, now = k.access(), datetime.now(timezone.utc)
    readable = [d for d in k.catalog()["dams"] if readiness_of(d, access) == "CALIBRATION"]
    due_ids = [d["lakeId"] for d in readable if due(db.get(f"lakes/{lake_key(d['lakeId'])}/states/{C.SLOT}"), now)]
    return {"brainId": C.BRAIN_ID, "action": "PUBLISH" if due_ids else "SKIP", "due": due_ids, "readable": len(readable),
            "knowledgeRelease": k.summary()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--allow-unapproved-release", action="store_true", help="--dry-run only: exercise an unapproved release locally (never publishes)")
    ap.add_argument("--fixtures", default=None, help="--dry-run only: answer every request from a fixture directory (no network)")
    ap.add_argument("--scope", default="bound", choices=("bound", "fleet"))
    ap.add_argument("--lake", default=None, help="--dry-run only: one lakeId")
    a = ap.parse_args(argv)
    k = K.load()                                                                  # verify first: missing/tampered -> KnowledgeReleaseError
    if a.plan:
        print(json.dumps(plan_verdict(k)))
        return 0
    if a.write:
        K.require_approved(k)                                                     # unapproved -> KnowledgeNotApproved (BLOCKED)
        if os.environ.get("GENERATION_WRITE_APPROVED") != "1":
            print("refusing: --write needs GENERATION_WRITE_APPROVED=1 (owner approval of the Generation release and its first write)", file=sys.stderr)
            return 3
        if a.fixtures or a.lake or a.scope != "bound":
            print("refusing: --fixtures, --lake and --scope fleet are dry-run options", file=sys.stderr)
            return 3
    elif not (k.approved or a.allow_unapproved_release):
        K.require_approved(k)
    catalog = k.catalog()
    if a.lake:
        catalog = {**catalog, "dams": [d for d in catalog["dams"] if d["lakeId"] == a.lake]}
    fetcher = Fetcher(k.access(), **({"transport": fixture_transport(a.fixtures)} if a.fixtures else {}), log=lambda s: print(s, file=sys.stderr))
    writer = RtdbWriter(RTDB_URL) if a.write else DryRunWriter()
    rep = publish(catalog, k.access(), fetcher, writer, scope=a.scope, release=k.summary())
    print(json.dumps({**{k_: rep.get(k_) for k_ in ("ok", "scope", "evaluated", "notDue", "changed", "unavailable", "readinessCounts", "kinds",
                                                     "statuses", "tiers", "requests", "errors", "writes")},
                      "knowledgeRelease": k.summary(), "published": bool(a.write)}, default=str))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except K.KnowledgeReleaseError as e:                                          # includes KnowledgeNotApproved
        print(f"REFUSED (nothing published): {e}", file=sys.stderr)
        sys.exit(2)
