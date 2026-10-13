#!/usr/bin/env python3
"""Depth Brain run entry for the shared Brain orchestrator (in-process, scale-to-zero). SHADOW: not registered, not scheduled.

  python run.py --plan        # orchestrator question: is a publish warranted? (GET-only; prints one JSON verdict)
  python run.py --dry-run     # build every write from live reads (GET only) and print the report; writes nothing
  python run.py --write       # publish pilot-scope shadow state; requires DEPTH_SHADOW_WRITE_APPROVED=1

Reads only the Brain RTDB (Lake Brain `states/lake`, one `lakeFleet` read to prefilter). It never fetches raw level feeds, never calls the Engine
request path, and a customer or Ops page view can never reach it. Freshness is the input FINGERPRINT: it publishes only when a Lake observation, a
reference/datum record, the manifest or the Depth version changed."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import depth_brain  # noqa: E402,F401  (bootstraps the platform path)
from depth_brain.__main__ import DEFAULT_MANIFEST, load_lake_states  # noqa: E402
from depth_brain.publish import publish  # noqa: E402
from depth_brain.state import brain_plan  # noqa: E402
from depth_brain import contract as C  # noqa: E402
from depth_brain.writer import DryRunWriter, RtdbWriter  # noqa: E402

RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")


def plan_verdict(rtdb_url: str = RTDB_URL, manifest_path: str = DEFAULT_MANIFEST) -> dict:
    from sector_brain_platform import BrainRtdb, lake_key
    manifest = json.load(open(manifest_path))
    db = BrainRtdb(rtdb_url, brain_id="depth")
    states = load_lake_states(f"rtdb:{rtdb_url}", manifest)
    published = {}
    for c in manifest["candidates"]:
        if c["lakeId"] in states or c.get("rollout") == "PILOT_VERIFIED":
            fp = db.get(f"lakes/{lake_key(c['lakeId'])}/states/depth/provenance/inputFingerprint")
            if fp:
                published[c["lakeId"]] = fp
    reg = db.get("brains/depth") or {}
    # a first run (no registry) is a PUBLISH by definition; otherwise the fingerprint verdict decides
    verdict = brain_plan(published, manifest, states, reg.get("version"))
    verdict.update({"brainId": "depth", "scope": "pilots", "liveLakeStates": len(states)})
    return verdict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    if a.plan:
        print(json.dumps(plan_verdict()))
        return 0
    manifest = json.load(open(DEFAULT_MANIFEST))
    states = load_lake_states(f"rtdb:{RTDB_URL}", manifest)
    if a.write:
        if os.environ.get("DEPTH_SHADOW_WRITE_APPROVED") != "1":
            print("refusing: --write needs DEPTH_SHADOW_WRITE_APPROVED=1 (pilot-scope shadow write approved by Michael 2026-10-14)", file=sys.stderr)
            return 3
        writer = RtdbWriter(RTDB_URL)
    else:
        writer = DryRunWriter()
    rep = publish(manifest, states, writer, mode="shadow", scope="pilots")
    print(json.dumps({k: rep.get(k) for k in ("ok", "scope", "evaluated", "skippedUnchanged", "unavailable", "readinessCounts", "errors", "writes")}, default=str))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
