"""Nonproduction entry points (local files only; never touches the Brain RTDB, the archive bucket or any customer path).

  python -m sector_wind.assessment assess --fetch FETCH.json.gz --lake "Guntersville|AL" --mph 12 --dir 225 [--hours 6] [--bank ID ...] [--top 5]
  python -m sector_wind.assessment scenarios --fetch FETCH.json.gz --lake "Guntersville|AL" [--json OUT]

FETCH is a runtime fetch object (archive `fetch/<lake>.json.gz` layout: banks + tableBase64). Wind given here is SYNTHETIC.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime, timezone

from . import build as B
from . import ranking as R
from . import scenarios as SC
from ..brain.lakes import WIND_LAKE_IDS


def _load(path, lake_id):
    raw = open(path, "rb").read()
    obj = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
    return R.geometry(obj, lake_id)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sector_wind.assessment")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("assess"); s = sub.add_parser("scenarios")
    for p in (d, s):
        p.add_argument("--fetch", required=True); p.add_argument("--lake", required=True); p.add_argument("--json")
    d.add_argument("--mph", type=float, required=True); d.add_argument("--dir", type=float); d.add_argument("--hours", type=float, default=6.0)
    d.add_argument("--bank", action="append", default=[]); d.add_argument("--top", type=int, default=R.DEFAULT_TOP)
    a = ap.parse_args(argv)
    L = _load(a.fetch, a.lake)
    if a.cmd == "assess":
        out = B.build(a.lake, B.synthetic_wind(a.mph, a.dir, a.hours, label="CLI"), L, datetime.now(timezone.utc),
                      supported=a.lake in WIND_LAKE_IDS.values(), top=a.top, bank_ids=tuple(a.bank))
    else:
        out = SC.run(L)
        for r in out["scenarios"]:
            print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['id']} {r['title']}", file=sys.stderr)
            for c in r["checks"]:
                if not c["pass"]:
                    print(f"        x {c['check']}: {c['detail']}", file=sys.stderr)
        print(f"{out['passed']}/{out['total']} scenarios passed ({out['evidenceClass']})", file=sys.stderr)
    txt = json.dumps(out, indent=1)
    if a.json:
        open(a.json, "w").write(txt)
    else:
        print(txt)
    return 0 if a.cmd == "assess" or out["passed"] == out["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
