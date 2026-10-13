"""Field-validation analysis for effective depth (tooling only; no field data exists yet).

Reads observations (CSV) and the frozen preregistration (data/field_validation_prereg.json), computes the preregistered metrics, and
returns pass/fail per criterion. The preregistration's sha256 is pinned here: changing a threshold after the fact makes
`verify_prereg()` fail. CSV columns: lake,flat,obsAt,observedDepthFt,poolFt,predictedDepthFt,sigmaFt[,excluded,excludeReason]."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os

PREREG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "field_validation_prereg.json")
PREREG_SHA256 = "b73f528ceb01a8df834ef0e2c1db8c0745095899acdb7e39e8ca682476ff0fa0"
CLASSES = ("DRY", "TOO_SHALLOW", "SHOOTABLE", "GOOD", "DEEP")


def verify_prereg(path: str = PREREG) -> bool:
    return hashlib.sha256(open(path, "rb").read()).hexdigest() == PREREG_SHA256


def depth_class(d: float) -> str:
    if d <= 0:
        return "DRY"
    if d < 1:
        return "TOO_SHALLOW"
    if d < 3:
        return "SHOOTABLE"
    return "GOOD" if d <= 5 else "DEEP"


def read_obs(path: str) -> list[dict]:
    rows = []
    for r in csv.DictReader(open(path, newline="")):
        r["observedDepthFt"], r["predictedDepthFt"], r["sigmaFt"] = float(r["observedDepthFt"]), float(r["predictedDepthFt"]), float(r["sigmaFt"])
        rows.append(r)
    return rows


def analyze(rows: list[dict]) -> dict:
    if not verify_prereg():
        raise RuntimeError("preregistration changed after freeze: refusing to analyse")
    pre = json.load(open(PREREG))["criteria"]
    use = [r for r in rows if str(r.get("excluded", "")).lower() not in ("1", "true", "yes")]
    n = len(use)
    err = [r["predictedDepthFt"] - r["observedDepthFt"] for r in use]
    mae = sum(abs(e) for e in err) / n if n else None
    cls = [(depth_class(r["observedDepthFt"]), depth_class(r["predictedDepthFt"])) for r in use]
    acc = sum(1 for o, p in cls if o == p) / n if n else None
    forbidden = sum(1 for o, p in cls if o == "DRY" and p in ("SHOOTABLE", "GOOD"))
    within = sum(1 for r, e in zip(use, err) if abs(e) <= r["sigmaFt"]) / n if n else None
    lakes = len({r["lake"] for r in use})
    dry = [(o, p) for o, p in cls if o == "DRY"]
    out = {"n": n, "lakes": lakes, "excluded": len(rows) - n, "maeFt": mae, "biasFt": (sum(err) / n if n else None), "classAccuracy": acc,
           "forbiddenDryAsShootableOrGood": forbidden, "withinOneSigma": within,
           "dryRecall": (sum(1 for o, p in dry if p in ("DRY", "TOO_SHALLOW")) / len(dry) if dry else None)}
    c = pre
    out["criteria"] = {
        "shiftVsObservedMaeFt": None if mae is None else (mae <= c["shiftVsObservedMaeFt"]["max"] and n >= c["shiftVsObservedMaeFt"]["n_min_pairs"] and lakes >= c["shiftVsObservedMaeFt"]["lakes_min"]),
        "classAccuracy": None if acc is None else (acc >= c["classAccuracy"]["min"] and n >= c["classAccuracy"]["n_min_obs"]),
        "forbiddenErrors": None if not n else forbidden <= c["forbiddenErrors"]["max_count"],
        "withinOneSigma": None if within is None else (c["withinOneSigma"]["min"] <= within <= c["withinOneSigma"]["max"]),
    }
    out["passed"] = bool(n) and all(v is True for v in out["criteria"].values())
    out["status"] = "PASSED" if out["passed"] else ("INSUFFICIENT_DATA" if not n or any(v is None for v in out["criteria"].values()) else "FAILED")
    return out
