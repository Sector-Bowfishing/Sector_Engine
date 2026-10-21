"""Depth Brain OFFLINE research CLI. Nothing here publishes, is deployed or scheduled; the only publish route is brains/depth/runtime/run.py.

  python -m depth_research.cli refresh [--check] [--version V]       # rebuild the candidate manifest from the research dataset snapshot
  python -m depth_research.cli build-manifest --paths P.json --version V
  python -m depth_research.cli report [--log]                        # fleet metrics + research maturity (NOT a score)
  python -m depth_research.cli promote-proposals [--apply]           # datum evidence proposals -> overrides (research dataset)

Inputs come from $DEPTH_RESEARCH_DATA (depth_research.paths); reviewed lakes from Lake's contract reviewed-lake-bindings-v1. Writing the
manifest changes the knowledge release: regenerate runtime/knowledge/knowledge-release.json with a NEW release id
(tools/knowledge/build_release_manifest.py). Promotion of a release to APPROVED is a separate, gated scientific decision."""
import argparse
import json
import os
import sys

from . import candidates as cand
from .paths import LAKE_BINDINGS, MANIFEST as DEFAULT_MANIFEST, research_data, write_manifest


def refresh_paths() -> dict:
    """Input paths from the research snapshot's manifest_inputs.json. The reviewed-lake list is always Lake's contract (never its Swift source)."""
    spec = json.load(open(research_data("manifest_inputs.json")))["paths"]
    out = {k: research_data(v) for k, v in spec.items() if not v.startswith("@repo/")}
    out["reviewed_bindings"] = LAKE_BINDINGS
    return out


def run_refresh(a) -> int:
    cur = json.load(open(DEFAULT_MANIFEST))
    version = a.version or cur.get("manifestVersion")
    new = cand.build(refresh_paths(), version)
    strip = lambda m: json.dumps({**m, "manifestVersion": "x"}, sort_keys=True)
    same = strip(new) == strip(cur)
    if a.check:
        print(json.dumps({"reproducible": same, "lakes": new["summary"]["lakes"], "shiftPossible": new["summary"]["shiftPossible"]}))
        return 0 if same else 1
    write_manifest(new, DEFAULT_MANIFEST)
    print(json.dumps({"version": version, "changed": not same, **{k: new["summary"][k] for k in ("lakes", "shiftPossible", "rollout", "datumStatus")}}, indent=1))
    return 0


def progress_log() -> str | None:
    return research_data("depth_progress_log.jsonl", required=False)


def last_log_entry(path=None):
    path = path or progress_log()
    if not path or not os.path.exists(path):
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
        with open(research_data("depth_progress_log.jsonl"), "a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="depth_research")
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
    f = sub.add_parser("refresh", help="rebuild candidates.json from the committed input snapshots (data/manifest_inputs.json); --check only verifies it reproduces")
    f.add_argument("--version", default=None)
    f.add_argument("--check", action="store_true")
    q = sub.add_parser("promote-proposals", help="validate evidence proposals and (with --apply) add accepted ones to datum_lake_overrides.json")
    q.add_argument("--manifest", default=DEFAULT_MANIFEST)
    q.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "refresh":
        return run_refresh(a)
    if a.cmd == "build-manifest":
        m = cand.build(json.load(open(a.paths)), a.version)
        write_manifest(m, a.out)
        print(json.dumps(m["summary"], indent=1))
        return 0
    if a.cmd == "promote-proposals":
        from . import proposals as PR
        res = PR.promote(json.load(open(a.manifest)), research_data("datum_lake_overrides.json"), apply=a.apply)
        print(json.dumps({"rulesVersion": res["rulesVersion"], "accepted": len(res["accepted"]), "newOverrides": res["newOverrides"], "applied": a.apply,
                          "rejected": res["rejected"][:60], "rejectedCount": len(res["rejected"])}, indent=1))
        return 0
    if a.cmd == "report":
        return run_report(a)
    raise SystemExit(f"unknown command {a.cmd!r}")

if __name__ == "__main__":
    sys.exit(main())
