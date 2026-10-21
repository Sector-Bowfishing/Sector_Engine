"""Vegetation Brain OFFLINE research CLI. Nothing here is deployed, scheduled or able to write; the only run entry is brains/vegetation/runtime/run.py.

  python -m vegetation_research.cli fleet --registry lakes.v1.json [--truth truth.json] --version V [--out fleet.json]
  python -m vegetation_research.cli report [--manifest fleet.json]          # research maturity (NOT a score)

`fleet` writes the release's fleet manifest by default: regenerate runtime/knowledge/knowledge-release.json with a NEW release id
(tools/knowledge/build_release_manifest.py). Promotion of a release to APPROVED is a separate, gated scientific decision.
"""
import argparse
import json
import os
import sys

from . import KNOWLEDGE_DIR
from . import fleet as F
from . import maturity as M

DEFAULT_MANIFEST = os.path.join(KNOWLEDGE_DIR, "fleet.json")      # writing it changes the knowledge release: regenerate the manifest with a NEW release id


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="vegetation_research")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fleet")
    f.add_argument("--registry", required=True)
    f.add_argument("--truth", help="JSON {lakeId: [flags]} produced by the validation reports")
    f.add_argument("--version", required=True)
    f.add_argument("--out", default=DEFAULT_MANIFEST)
    r = sub.add_parser("report")
    r.add_argument("--manifest", default=DEFAULT_MANIFEST)
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
    raise SystemExit(f"unknown command {a.cmd!r}")

if __name__ == "__main__":
    sys.exit(main())
