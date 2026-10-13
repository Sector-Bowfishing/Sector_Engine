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
        from sector_brain_platform import BrainRtdb, lake_key
        db = BrainRtdb(val, brain_id="depth")
        fleet = db.get("lakeFleet") or {}                                   # one read: which lakes have a published Lake Brain slot
        has_lake = {k for k, v in fleet.items() if isinstance(v, dict) and (v.get("readiness") or {}).get("lake")}
        out = {}
        for c in manifest["candidates"]:
            k = lake_key(c["lakeId"])
            if not c.get("shiftPossible") or (has_lake and k not in has_lake):
                continue
            s = db.get(f"lakes/{k}/states/lake")
            if s:
                out[c["lakeId"]] = s
        return out
    raise SystemExit(f"unknown --lake-states {spec!r}")


PROGRESS_LOG = os.path.join(HERE, "..", "..", "..", "docs", "brains", "depth", "data", "depth_progress_log.jsonl")


def last_log_entry(path=PROGRESS_LOG):
    if not os.path.exists(path):
        return None
    rows = [json.loads(l) for l in open(path) if l.strip()]
    return rows[-1] if rows else None


def run_report(a) -> int:
    import datetime as dt
    from . import maturity as M
    manifest = json.load(open(a.manifest))
    inputs = M.load_json("maturity_inputs.json")
    cur = M.evaluate(manifest, inputs)
    prev = last_log_entry()
    problems = M.check_increase(prev, inputs)
    d = M.diff(prev, cur)
    out = {"research": {"overall": cur["overall"], "official": False, "scoreStatus": cur["scoreStatus"], "criticalBelowThreshold": cur["criticalBelowThreshold"],
                        "meetsProductionPolicy": cur["meetsProductionPolicy"], "dimensions": {k: v["score"] for k, v in cur["dimensions"].items()}},
           "fleet": cur["fleet"], "changes": d, "unsupportedIncreases": problems}
    print(json.dumps(out, indent=1))
    if problems:
        print("REFUSING: unsupported judgment-score increase(s) (cite new changeEvidence in maturity_inputs.json)", file=sys.stderr)
        return 2
    if a.log:
        entry = {"at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "cycle": a.cycle, "overall": cur["overall"],
                 "official": False, "dimensions": {k: {"score": v["score"]} for k, v in cur["dimensions"].items()}, "fleet": cur["fleet"],
                 "citedEvidence": {k: d_.get("changeEvidence") or [] for k, d_ in inputs["dimensions"].items()}, "note": a.note}
        with open(PROGRESS_LOG, "a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="depth_brain")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-manifest")
    b.add_argument("--paths", required=True, help="JSON file of input paths (see candidates.build)")
    b.add_argument("--version", required=True)
    b.add_argument("--out", default=DEFAULT_MANIFEST)
    r = sub.add_parser("report", help="fleet metrics + research maturity (NOT an official score); --log appends to the progress log")
    r.add_argument("--manifest", default=DEFAULT_MANIFEST)
    r.add_argument("--log", action="store_true")
    r.add_argument("--cycle", default="unnamed")
    r.add_argument("--note", default="")
    q = sub.add_parser("promote-proposals", help="validate evidence proposals and (with --apply) add accepted ones to datum_lake_overrides.json")
    q.add_argument("--manifest", default=DEFAULT_MANIFEST)
    q.add_argument("--apply", action="store_true")
    p = sub.add_parser("publish")
    p.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p.add_argument("--lake-states", required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", metavar="OUT.json")
    g.add_argument("--rtdb", metavar="URL")
    p.add_argument("--yes-write-shadow", action="store_true", help="required with --rtdb")
    p.add_argument("--scope", choices=["pilots", "fleet"], default="pilots", help="pilots (default): only lakes with a Lake Brain state; fleet is analysis/dry-run only")
    a = ap.parse_args(argv)
    if a.cmd == "build-manifest":
        m = cand.build(json.load(open(a.paths)), a.version)
        json.dump(m, open(a.out, "w"), indent=1, sort_keys=True)
        print(json.dumps(m["summary"], indent=1))
        return 0
    if a.cmd == "promote-proposals":
        from . import proposals as PR
        res = PR.promote(json.load(open(a.manifest)), os.path.join(HERE, "data", "datum_lake_overrides.json"), apply=a.apply)
        print(json.dumps({"rulesVersion": res["rulesVersion"], "accepted": len(res["accepted"]), "newOverrides": res["newOverrides"], "applied": a.apply,
                          "rejected": res["rejected"][:60], "rejectedCount": len(res["rejected"])}, indent=1))
        return 0
    if a.cmd == "report":
        return run_report(a)
    if a.rtdb and not a.yes_write_shadow:
        raise SystemExit("a live shadow write needs --yes-write-shadow")
    if a.rtdb and a.scope != "pilots":
        raise SystemExit("a live write is approved for scope=pilots only")
    manifest = json.load(open(a.manifest))
    states = load_lake_states(a.lake_states, manifest)
    writer = DryRunWriter() if a.dry_run else RtdbWriter(a.rtdb)
    rep = publish(manifest, states, writer, mode="shadow", scope=a.scope)
    if a.dry_run:
        writer.dump(a.dry_run)
        rep["dryRunFile"] = a.dry_run
        rep["patches"] = len(writer.patches)
    print(json.dumps(rep, indent=1, default=str)[:6000])
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
