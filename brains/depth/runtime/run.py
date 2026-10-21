#!/usr/bin/env python3
"""Depth Brain run entry (SHADOW / PROFILED). Not registered with the orchestrator, not scheduled (control manifest executionTarget kind none).

  python run.py --plan                         # is a publish warranted? GET-only; one JSON verdict. BLOCKED while the release is not approved
  python run.py --dry-run [--allow-unapproved-release] [--lake-states file:PATH]
                                               # build every write in memory and print the report; writes nothing
  python run.py --write                        # publish pilot-scope shadow state: needs an APPROVED knowledge release
                                               # AND DEPTH_SHADOW_WRITE_APPROVED=1 (operator intent)

Knowledge comes ONLY from the verified release in runtime/knowledge/ (depth_brain.knowledge). Live inputs come ONLY from published Lake Brain
state (Brain RTDB GET). A missing or tampered release refuses the run (exit 2); an unapproved release is never published from (exit 2,
BLOCKED_AWAITING_APPROVED_RELEASE). Research data, docs and other Brains' source are never read."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import depth_brain  # noqa: E402,F401  (bootstraps the platform path)
from depth_brain import contract as C, knowledge as K  # noqa: E402
from depth_brain.inputs import load_lake_states  # noqa: E402
from depth_brain.publish import publish  # noqa: E402
from depth_brain.state import brain_plan  # noqa: E402
from depth_brain.writer import DryRunWriter, RtdbWriter  # noqa: E402

RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")


def plan_verdict(k: "K.Knowledge", rtdb_url: str = RTDB_URL) -> dict:
    if not k.approved:
        return {"brainId": C.BRAIN_ID, "action": "SKIP", "status": K.BLOCKED, "knowledgeRelease": k.summary(),
                "reason": "no APPROVED knowledge release: Depth abstains (nothing is published from unapproved knowledge)"}
    from sector_brain_platform import BrainRtdb, lake_key
    manifest = k.json("candidates.json")
    db = BrainRtdb(rtdb_url, brain_id="depth")
    states = load_lake_states(f"rtdb:{rtdb_url}", manifest)
    published = {}
    for c in manifest["candidates"]:
        if c["lakeId"] in states or c.get("rollout") == "PILOT_VERIFIED":
            fp = db.get(f"lakes/{lake_key(c['lakeId'])}/states/depth/provenance/inputFingerprint")
            if fp:
                published[c["lakeId"]] = fp
    reg = db.get("brains/depth") or {}
    verdict = brain_plan(published, manifest, states, reg.get("version"))      # a first run (no registry) is a PUBLISH by definition
    verdict.update({"brainId": C.BRAIN_ID, "scope": "pilots", "liveLakeStates": len(states), "knowledgeRelease": k.summary()})
    return verdict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--allow-unapproved-release", action="store_true", help="--dry-run only: exercise an unapproved release locally (never publishes)")
    ap.add_argument("--lake-states", default=None, help="file:PATH for an offline dry run (default: rtdb:$BRAIN_RTDB_URL)")
    a = ap.parse_args(argv)
    k = K.load()                                                                  # verify first: missing/tampered -> KnowledgeReleaseError
    if a.plan:
        print(json.dumps(plan_verdict(k)))
        return 0
    if a.write:
        K.require_approved(k)                                                     # unapproved -> KnowledgeNotApproved (BLOCKED)
        if os.environ.get("DEPTH_SHADOW_WRITE_APPROVED") != "1":
            print("refusing: --write needs DEPTH_SHADOW_WRITE_APPROVED=1 (pilot-scope shadow write approved by Michael 2026-10-14)", file=sys.stderr)
            return 3
    elif not (k.approved or a.allow_unapproved_release):
        K.require_approved(k)
    manifest = k.json("candidates.json")
    states = load_lake_states(a.lake_states or f"rtdb:{RTDB_URL}", manifest)
    writer = RtdbWriter(RTDB_URL) if a.write else DryRunWriter()
    rep = publish(manifest, states, writer, mode="shadow", scope="pilots", release=k.summary())
    print(json.dumps({**{k_: rep.get(k_) for k_ in ("ok", "scope", "evaluated", "skippedUnchanged", "unavailable", "readinessCounts", "errors", "writes")},
                      "knowledgeRelease": k.summary(), "published": bool(a.write)}, default=str))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except K.KnowledgeReleaseError as e:                                          # includes KnowledgeNotApproved
        print(f"REFUSED (nothing published): {e}", file=sys.stderr)
        sys.exit(2)
