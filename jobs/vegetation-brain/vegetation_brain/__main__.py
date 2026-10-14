"""Vegetation Brain CLI (SHADOW, offline). Nothing here is deployed, scheduled or able to write live.

  python -m vegetation_brain fleet --registry lakes.v1.json [--truth truth.json] --version V --out fleet.json
  python -m vegetation_brain report [--manifest fleet.json]
  python -m vegetation_brain publish --manifest fleet.json --dry-run OUT.json
"""
import argparse
import json
import os
import sys

from . import fleet as F
from . import maturity as M
from .publish import publish
from .writer import DryRunWriter

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MANIFEST = os.path.join(HERE, "data", "fleet.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="vegetation_brain")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fleet")
    f.add_argument("--registry", required=True)
    f.add_argument("--truth", help="JSON {lakeId: [flags]} produced by the validation reports")
    f.add_argument("--version", required=True)
    f.add_argument("--out", default=DEFAULT_MANIFEST)
    r = sub.add_parser("report")
    r.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p = sub.add_parser("publish")
    p.add_argument("--manifest", default=DEFAULT_MANIFEST)
    p.add_argument("--dry-run", metavar="OUT.json", required=True, help="the only mode: no live writer exists")
    a = ap.parse_args(argv)
    if a.cmd == "fleet":
        truth = json.load(open(a.truth)) if a.truth else None
        m = F.build_manifest(F.load_registry(a.registry), truth, a.version)
        json.dump(m, open(a.out, "w"), indent=1, sort_keys=True)
        print(json.dumps(m["summary"], indent=1))
        return 0
    m = json.load(open(a.manifest))
    if a.cmd == "report":
        print(json.dumps(M.evaluate(m), indent=1))
        return 0
    w = DryRunWriter()
    ag = json.load(open(os.path.join(HERE, "data", "agency_fwc_pacpvi.json")))["records"]
    rep = publish(m, w, agency=ag)
    w.dump(a.dry_run)
    rep["dryRunFile"], rep["patches"] = a.dry_run, len(w.patches)
    print(json.dumps(rep, indent=1, default=str)[:4000])
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
