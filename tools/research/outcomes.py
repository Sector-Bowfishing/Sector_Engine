#!/usr/bin/env python3
"""Record what actually happened so the next research cycle can test the Brains against it (owner directive 2026-10-26).

  python3 tools/research/outcomes.py record --home H --lake Guntersville_AL --when 2026-11-02T21:30 --observer name \
      --observed '{"surfaceTempC": 17.5, "calmNight": true, "windMph": 3, "clarityFt": 3.5, "speciesSeen": ["common carp"], "notes": "..."}' [--snapshot assessment.json]
  python3 tools/research/outcomes.py evaluate --home H

Records are append-only JSON lines in <home>/shared/pilot/outcomes/<lake>.jsonl, each carrying the sha256 of the integration assessment that was on screen (when given).
`evaluate` compares them with the Brains' stated values and the calm-night prior: it reports counts and errors only, and never changes a score or an approval.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys

FIELDS = {"surfaceTempC": float, "calmNight": bool, "windMph": float, "clarityFt": float, "speciesSeen": list, "notes": str}


def _path(home, lake):
    return os.path.join(home, "shared", "pilot", "outcomes", f"{lake}.jsonl")


def record(home: str, lake: str, when: str, observer: str, observed: dict, snapshot: str | None = None) -> dict:
    bad = [k for k, v in observed.items() if k not in FIELDS or not isinstance(v, FIELDS[k]) or (FIELDS[k] is float and isinstance(v, bool))]
    if bad or not observed:
        raise ValueError(f"unknown or mistyped observation fields: {bad or 'empty'}")
    rec = {"schema": "sector-outcome-v1", "lake": lake, "observedAt": when, "recordedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "observer": observer, "observed": observed}
    if snapshot:
        rec["assessmentSha256"] = hashlib.sha256(open(snapshot, "rb").read()).hexdigest()
        rec["assessment"] = json.load(open(snapshot, encoding="utf-8"))
    p = _path(home, lake)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def evaluate(home: str, lake: str | None = None) -> dict:
    d = os.path.join(home, "shared", "pilot", "outcomes")
    recs = []
    for fn in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if lake and fn != f"{lake}.jsonl":
            continue
        recs += [json.loads(x) for x in open(os.path.join(d, fn), encoding="utf-8") if x.strip()]
    temp_err, calm, clar = [], [], []
    for r in recs:
        o, a = r["observed"], r.get("assessment") or {}
        f = {(x["brain"], x["factor"]): x for x in a.get("factors") or []}
        t = f.get(("water-temp", "modeledSurfaceTemp"))
        if "surfaceTempC" in o and t and t.get("value") is not None and t["status"] == "FRESH":
            temp_err.append(t["value"] - o["surfaceTempC"])
        pr = (a.get("seasonalPrior") or {}).get("probabilityOfCalmNight")
        if "calmNight" in o and pr is not None:
            calm.append((pr, 1.0 if o["calmNight"] else 0.0))
        c = f.get(("water-clarity", "modeledClarity"))
        if "clarityFt" in o and c and c.get("value") is not None and c["status"] == "FRESH":
            clar.append(c["value"] - o["clarityFt"])
    out = {"records": len(recs), "tempComparisons": len(temp_err), "calmComparisons": len(calm), "clarityComparisons": len(clar)}
    if temp_err:
        out["tempBiasC"] = round(sum(temp_err) / len(temp_err), 3)
        out["tempRmseC"] = round((sum(e * e for e in temp_err) / len(temp_err)) ** 0.5, 3)
    if calm:
        out["calmBrier"] = round(sum((p - y) ** 2 for p, y in calm) / len(calm), 4)
        out["calmBrierNaive"] = round(sum((sum(y for _, y in calm) / len(calm) - y) ** 2 for _, y in calm) / len(calm), 4)
    if clar:
        out["clarityBiasFt"] = round(sum(clar) / len(clar), 3)
    out["note"] = "counts and errors only; feeds the next research campaign; changes no score and no approval"
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("record", "evaluate"))
    ap.add_argument("--home", required=True)
    ap.add_argument("--lake", default="Guntersville_AL")
    ap.add_argument("--when")
    ap.add_argument("--observer", default="")
    ap.add_argument("--observed", default="{}")
    ap.add_argument("--snapshot")
    a = ap.parse_args(argv)
    if a.cmd == "record":
        print(json.dumps(record(a.home, a.lake, a.when, a.observer, json.loads(a.observed), a.snapshot), indent=1)[:600])
    else:
        print(json.dumps(evaluate(a.home, a.lake), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
