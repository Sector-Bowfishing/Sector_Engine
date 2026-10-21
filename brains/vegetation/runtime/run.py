#!/usr/bin/env python3
"""Vegetation Brain run entry (SHADOW). Not scheduled, no executor (control manifest executionTarget kind none) and NO live writer.

  python run.py --plan                                        # one JSON verdict; BLOCKED while the knowledge release is not approved
  python run.py --dry-run OUT.json [--allow-unapproved-release]
                                                              # build every write into an in-memory store and dump it; writes nothing remote

Knowledge comes ONLY from the verified release in runtime/knowledge/ (vegetation_brain.knowledge): the fleet manifest and the Level-1 agency
records. A missing or tampered release refuses the run (exit 2); an unapproved release is exercised only with explicit intent and is never
published (there is no live writer to publish with). Research evidence and the maturity rubric are never read."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vegetation_brain  # noqa: E402,F401  (bootstraps the platform path)
from vegetation_brain import contract as C, knowledge as K  # noqa: E402
from vegetation_brain.publish import publish  # noqa: E402
from vegetation_brain.writer import DryRunWriter  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--dry-run", metavar="OUT.json")
    ap.add_argument("--allow-unapproved-release", action="store_true", help="--dry-run only: exercise an unapproved release locally (never publishes)")
    a = ap.parse_args(argv)
    k = K.load()                                                                  # verify first: missing/tampered -> KnowledgeReleaseError
    if a.plan:
        status = "READY_FOR_SHADOW_DRY_RUN" if k.approved else K.BLOCKED
        print(json.dumps({"brainId": C.BRAIN_ID, "action": "SKIP", "status": status, "knowledgeRelease": k.summary(),
                          "reason": "no live writer exists; publication is not approved" if k.approved else
                                    "no APPROVED knowledge release: Vegetation abstains (nothing is published from unapproved knowledge)"}))
        return 0
    if not (k.approved or a.allow_unapproved_release):
        K.require_approved(k)
    w = DryRunWriter()
    rep = publish(k.json("fleet.json"), w, agency=k.json("agency_fwc_pacpvi.json")["records"],
                  littoral=k.json("agency_sfwmd_okeechobee.json")["records"], release=k.summary())
    w.dump(a.dry_run)
    print(json.dumps({**{k_: rep.get(k_) for k_ in ("ok", "evaluated", "observed", "unavailable", "skippedUnchanged", "readinessCounts", "errors", "writes")},
                      "dryRunFile": a.dry_run, "knowledgeRelease": k.summary(), "published": False}, default=str))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except K.KnowledgeReleaseError as e:                                          # includes KnowledgeNotApproved
        print(f"REFUSED (nothing published): {e}", file=sys.stderr)
        sys.exit(2)
