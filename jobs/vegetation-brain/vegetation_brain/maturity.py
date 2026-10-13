"""Research maturity (RESEARCH rubric; NOT an official Engine score). Vegetation has no canonical scorer and no /scores/vegetation.

Judgment dimensions live in data/maturity_inputs.json and must cite evidence. `report --log` appends to the progress log and refuses
an increase that cites no NEW evidence (anti score-gaming). Coverage is computed from the fleet manifest: the share of lakes with an
actual offline observation that is not UNKNOWN (observer output exists), via the shared coverage ladder. Overall >= 8.0 AND every
critical dimension >= 7.5 is the production policy; `meetsProductionPolicy` reports it."""
from __future__ import annotations

import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
POLICY_OVERALL = 8.0
POLICY_CRITICAL = 7.5
COVERAGE_LADDER = ((0.90, 10), (0.75, 9), (0.50, 7), (0.25, 5), (0.10, 3), (0.05, 2))


def coverage_score(share: float) -> int:
    if share <= 0:
        return 0
    for floor, pts in COVERAGE_LADDER:
        if share >= floor:
            return pts
    return 1


def load_inputs(path: str | None = None) -> dict:
    with open(path or os.path.join(DATA, "maturity_inputs.json")) as f:
        return json.load(f)


def fleet_metrics(manifest: dict, observed_lakes: int = 0) -> dict:
    c = manifest["candidates"]
    n = len(c)
    tiers = {t: sum(1 for x in c if x["tier"] == t) for t in ("HIGH", "MEDIUM", "LOW", "UNKNOWN")}
    return {"totalLakes": n, "observableLakes": tiers["HIGH"] + tiers["MEDIUM"], "tiers": tiers,
            "observedLakes": observed_lakes, "observedShare": round(observed_lakes / n, 4) if n else 0.0,
            "withIndependentTruth": sum(1 for x in c if x.get("groundTruth")), "manifestVersion": manifest.get("manifestVersion")}


def evaluate(manifest: dict, inputs: dict | None = None, *, observed_lakes: int = 0, exposed: tuple = ()) -> dict:
    inputs = inputs or load_inputs()
    fm = fleet_metrics(manifest, observed_lakes)
    dims, tw, acc = {}, 0, 0.0
    for k, d in inputs["dimensions"].items():
        score = coverage_score(fm["observedShare"]) if d["basis"] == "computed" else d["score"]
        crit = bool(d.get("critical")) or (k in exposed and bool(d.get("criticalIfExposed")))
        dims[k] = {"label": d["label"], "weight": d["weight"], "critical": crit, "score": score, "basis": d["basis"]}
        tw += d["weight"]
        acc += d["weight"] * score
    overall = round(acc / tw, 2)
    below = sorted(k for k, d in dims.items() if d["critical"] and d["score"] < POLICY_CRITICAL)
    return {"overall": overall, "dimensions": dims, "criticalBelowThreshold": below, "fleet": fm, "official": False,
            "rubricVersion": inputs["rubricVersion"], "meetsProductionPolicy": overall >= POLICY_OVERALL and not below,
            "policy": {"overall": POLICY_OVERALL, "critical": POLICY_CRITICAL}}


def _exists(repo_root: str, rel: str) -> bool:
    return os.path.exists(os.path.join(repo_root, rel))


def check_increase(prev: dict | None, new_inputs: dict, repo_root: str) -> list[str]:
    """Return the list of violations: any judgment increase must cite >= 1 evidence file that is NEW vs the previous inputs and exists."""
    bad = []
    if not prev:
        return bad
    for k, d in new_inputs["dimensions"].items():
        p = prev["dimensions"].get(k)
        if not p or d["basis"] != "judgment":
            continue
        if d["score"] > p["score"]:
            new_ev = [e for e in d.get("evidence", []) if e not in p.get("evidence", [])]
            if not new_ev:
                bad.append(f"{k}: {p['score']} -> {d['score']} without new evidence")
            elif not all(_exists(repo_root, e) for e in new_ev):
                bad.append(f"{k}: cited evidence file missing: {[e for e in new_ev if not _exists(repo_root, e)]}")
    return bad
