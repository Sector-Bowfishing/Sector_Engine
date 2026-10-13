"""Depth Brain CLI (SHADOW). Nothing here is deployed or scheduled.

  python -m depth_brain build-manifest --out depth_brain/data/candidates.json          # offline, from research artifacts
  python -m depth_brain publish --lake-states rtdb:https://sector-brain.firebaseio.com --dry-run OUT.json
  python -m depth_brain publish --lake-states file:states.json --dry-run OUT.json
  python -m depth_brain publish --lake-states rtdb:URL --rtdb URL --yes-write-shadow    # live shadow write: explicit operator intent only

`--dry-run` builds every write and applies it to an in-memory tree with the same ownership/key checks as the live client.
Lake Brain states are only ever READ (HTTP GET)."""
import argparse
import json
import os
import sys

from . import candidates as cand
from .publish import publish
from .writer import DryRunWriter, RtdbWriter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MANIFEST = os.path.join(HERE, "data", "candidates.json")


def load_lake_states(spec: str, manifest: dict) -> dict:
    kind, _, val = spec.partition(":")
    if kind == "file":
        return json.load(open(val))
    if kind == "rtdb":
        from sector_brain_platform import BrainRtdb, TokenProvider, lake_key
        db = BrainRtdb(val, brain_id="depth")
        out = {}
        for c in manifest["candidates"]:
            if not c.get("shiftPossible"):
                continue
            s = db.get(f"lakes/{lake_key(c['lakeId'])}/states/lake")
            if s:
                out[c["lakeId"]] = s
        return out
    raise SystemExit(f"unknown --lake-states {spec!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="depth_brain")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-manifest")
    b.add_argument("--paths", required=True, help="JSON file of input paths (see candidates.build)")
    b.add_argument("--version", required=True)
    b.add_argument("--out", default=DEFAULT_MANIFEST)
    p = sub.add_parser("publish")
    p.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p.add_argument("--lake-states", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", metavar="OUT.json")
    g.add_argument("--rtdb", metavar="URL")
    p.add_argument("--yes-write-shadow", action="store_true", help="required with --rtdb")
    a = ap.parse_args(argv)
    if a.cmd == "build-manifest":
        m = cand.build(json.load(open(a.paths)), a.version)
        json.dump(m, open(a.out, "w"), indent=1, sort_keys=True)
        print(json.dumps(m["summary"], indent=1))
        return 0
    manifest = json.load(open(a.manifest))
    states = load_lake_states(a.lake_states, manifest)
    if a.rtdb and not a.yes_write_shadow:
        raise SystemExit("a live shadow write needs --yes-write-shadow")
    writer = DryRunWriter() if a.dry_run else RtdbWriter(a.rtdb)
    rep = publish(manifest, states, writer, mode="shadow")
    if a.dry_run:
        writer.dump(a.dry_run)
        rep["dryRunFile"] = a.dry_run
        rep["patches"] = len(writer.patches)
    print(json.dumps(rep, indent=1, default=str)[:6000])
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
