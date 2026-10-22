#!/usr/bin/env python3
"""Shadow-lane runner (internal operation, 2026-10-22). Run by the orchestrator as a subprocess inside the Brain's runtime directory:

    python shadow_run.py depth        # cwd = <image>/brains/depth/runtime
    python shadow_run.py vegetation   # cwd = <image>/brains/vegetation/runtime

It calls the Brain's OWN runtime (its verified knowledge loader and its own publish()) against the CANDIDATE release, into the Brain's own
in-memory DryRunWriter: nothing is written anywhere. It prints one JSON object {brainId, slot, patches, report, release, approvedPath}. The
approved serving path is untouched: with an unapproved release `run.py --write` still refuses (BLOCKED_AWAITING_APPROVED_RELEASE). A missing or
tampered release still refuses here (exit 2). No science lives in this file."""
from __future__ import annotations

import json
import os
import sys

RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")


def _approved_path(k, blocked: str) -> dict:
    if k.approved:
        return {"status": "APPROVED_RELEASE_PRESENT", "reason": "the approved serving path should run instead of the shadow lane"}
    return {"status": "ABSTAIN", "reason": f"{blocked}: release {k.release['releaseId']} approval is {k.release['approvalStatus']} (G-1)"}


def run_depth() -> dict:
    sys.path.insert(0, os.getcwd())
    import depth_brain  # noqa: F401  (platform bootstrap)
    from depth_brain import contract as C, knowledge as K
    from depth_brain.inputs import load_lake_states
    from depth_brain.publish import publish
    from depth_brain.writer import DryRunWriter
    k = K.load()                                                         # verified release; missing/tampered -> KnowledgeReleaseError
    manifest = k.json("candidates.json")
    states = load_lake_states(f"rtdb:{RTDB_URL}", manifest)             # live Lake Brain states (GET only)
    w = DryRunWriter()
    rep = publish(manifest, states, w, mode="shadow", scope="pilots", release=k.summary())
    return {"brainId": C.BRAIN_ID, "slot": C.SLOT, "patches": w.patches, "report": rep, "release": k.summary(),
            "approvedPath": _approved_path(k, K.BLOCKED), "inputs": {"liveLakeStates": len(states)}}


def run_vegetation() -> dict:
    sys.path.insert(0, os.getcwd())
    import vegetation_brain  # noqa: F401
    from vegetation_brain import contract as C, knowledge as K
    from vegetation_brain.publish import publish
    from vegetation_brain.writer import DryRunWriter
    k = K.load()
    w = DryRunWriter()
    rep = publish(k.json("fleet.json"), w, agency=k.json("agency_fwc_pacpvi.json")["records"],
                  littoral=k.json("agency_sfwmd_okeechobee.json")["records"], release=k.summary())
    return {"brainId": C.BRAIN_ID, "slot": C.SLOT, "patches": w.patches, "report": rep, "release": k.summary(),
            "approvedPath": _approved_path(k, K.BLOCKED), "inputs": {"liveObservations": 0, "note": "no live surface-observation feed is wired"}}


RUNNERS = {"depth": run_depth, "vegetation": run_vegetation}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in RUNNERS:
        print(f"usage: shadow_run.py {{{','.join(RUNNERS)}}}", file=sys.stderr)
        return 64
    try:
        out = RUNNERS[argv[0]]()
    except Exception as e:                                               # KnowledgeReleaseError (missing/tampered) included
        print(f"REFUSED: {type(e).__name__}: {e}"[:500], file=sys.stderr)
        return 2
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
