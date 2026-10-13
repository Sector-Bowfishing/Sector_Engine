#!/usr/bin/env python3
"""POST-HOC descriptive summaries of docs/brains/depth/data/twdb_validation_rows.csv (NOT preregistered; no pass/fail, nothing is re-graded).
Per-level breakdown of the dry share, band bounds width by level, and a same-subset fleet-mean baseline for S2. Run with the lake-brain venv python, -I."""
import csv, json
from pathlib import Path
import numpy as np
D = Path(__file__).resolve().parents[2] / "docs/brains/depth/data"
rows = list(csv.DictReader(open(D / "twdb_validation_rows.csv")))
for r in rows:
    for k in ("truth", "lo", "hi", "mid", "err", "width", "d"): r[k] = float(r[k])
    r["inside"] = int(r["inside"])
V = lambda **k: [r for r in rows if r["status"] == "VERIFIED" and all(r[a] == v for a, v in k.items())]
out = {"note": "post-hoc, descriptive only", "dryByLevel": {}, "bandWidthByLevel": {}, "sameSubsetBaseline": {}}
for pn in ("S1", "S2"):
    for sm in ("production", "zero"):
        for d in (1.5, 3.0, 4.5, 6.0, 8.0):
            rs = V(predictor=pn, sigmaMode=sm, band="dry", d=d)
            out["dryByLevel"][f"{pn}|{sm}|{d}"] = dict(n=len(rs), mae=round(float(np.mean([abs(r["err"]) for r in rs])), 4), bias=round(float(np.mean([r["err"] for r in rs])), 4),
                                                       coverage=round(float(np.mean([r["inside"] for r in rs])), 2), widthMedian=round(float(np.median([r["width"] for r in rs])), 3))
for band in ("under3", "threeToSix", "sixToTen", "deeper"):
    for d in (1.5, 3.0, 4.5, 6.0, 8.0):
        rs = V(predictor="S1", sigmaMode="production", band=band, d=d)
        out["bandWidthByLevel"][f"{band}|{d}"] = dict(widthMedian=round(float(np.median([r["width"] for r in rs])), 3), mae=round(float(np.mean([abs(r["err"]) for r in rs])), 3))
s2l = sorted({r["lakeId"] for r in V(predictor="S2")})
tr = {(r["lakeId"], r["d"]): r["truth"] for r in V(predictor="S1", sigmaMode="zero", band="dry")}
for pn, lakes in (("S1_allVerified", sorted({l for l, _ in tr})), ("S2_subset", s2l)):
    e = []
    for l in lakes:
        for d in (1.5, 3.0, 4.5, 6.0, 8.0):
            oth = [tr[(o, d)] for o in lakes if o != l]; e.append(abs(np.mean(oth) - tr[(l, d)]))
    out["sameSubsetBaseline"][pn] = dict(lakes=lakes, maeLeaveOneLakeOutMean=round(float(np.mean(e)), 4), n=len(e))
(D / "twdb_validation_posthoc.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
