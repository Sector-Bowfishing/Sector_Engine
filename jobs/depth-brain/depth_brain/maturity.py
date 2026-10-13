"""Research maturity + fleet metrics (RESEARCH rubric; NOT an official Engine score).

Depth Brain has no canonical scorer. This module evaluates the research rubric from (a) numbers computed from the candidate
manifest and (b) judgment scores in `data/maturity_inputs.json` that must carry evidence. It never writes a score into RTDB,
`official` is always False, and the progress log refuses a judgment-score increase that cites no new evidence (anti score-gaming).

  python -m depth_brain report            # print the table
  python -m depth_brain report --log      # append to docs progress log (fails on an unsupported increase)"""
from __future__ import annotations

import json
import os
from collections import Counter

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# Coverage anchors: share of the directory with a DEFENSIBLE shift (datum proven, direct level binding, acceptable pool).
# Mirrors the research rubric ("4 = ~15-30% of fleet ... 8 = >= 70% of demand"); evaluated on lakes, not on demand weights.
COVERAGE_ANCHORS = ((0.05, 1), (0.10, 2), (0.20, 3), (0.35, 4), (0.50, 5), (0.65, 6), (0.80, 7), (0.90, 8), (1.01, 9))


def coverage_score(shift_share: float) -> int:
    for ub, s in COVERAGE_ANCHORS:
        if shift_share < ub:
            return s
    return 9


def load_json(name, base=DATA):
    with open(os.path.join(base, name)) as f:
        return json.load(f)


def _g(d, *path, default=None):
    """Tolerant nested get: a malformed candidate must degrade a metric, never crash a publish."""
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return default if d is None else d


def fleet_metrics(manifest: dict) -> dict:
    c = manifest["candidates"]
    n = len(c)
    ok = [x for x in c if _g(x, "shiftPossible", default=False)]
    ds = Counter(_g(x, "datum", "status", default="UNKNOWN") for x in ok)
    tier_ab = [x for x in c if _g(x, "evidence", "tier") in ("A", "B")]
    return {
        "totalLakes": n,
        "shiftPossible": len(ok),
        "shiftPossibleShare": round(len(ok) / n, 4) if n else 0.0,
        "pilotVerified": sum(1 for x in c if x.get("rollout") == "PILOT_VERIFIED"),
        "highConfidence": sum(1 for x in c if x.get("rollout") == "HIGH_CONFIDENCE"),
        "mediumConfidence": sum(1 for x in c if x.get("rollout") == "MEDIUM_CONFIDENCE"),
        "blocked": sum(1 for x in c if x.get("rollout") == "BLOCKED"),
        "verifiedDatum": ds.get("SAME_SOURCE", 0) + ds.get("SAME_DATUM", 0),
        "inferredOperatorSystem": ds.get("SAME_OPERATOR_SYSTEM", 0),
        "convertedDatum": ds.get("CONVERTED", 0),
        "datumStatus": dict(ds),
        "plausibleBlockedByDatum": sum(1 for x in c if _g(x, "reference", "basis") == "fullPool" and _g(x, "reference", "confidence") in ("high", "medium")
                                       and _g(x, "levelSource", "status", default="NONE") != "NONE" and not _g(x, "shiftPossible", default=False)),
        "tierAB": len(tier_ab),
        "referenceZoneLakes": sum(1 for x in c if "referenceZones" in x),
        "effectiveZoneEligible": sum(1 for x in c if _g(x, "referenceZones", "referenceStatus") == "VERIFIED" and _g(x, "shiftPossible", default=False)),
        "licenceAllowedAB": sum(1 for x in tier_ab if _g(x, "licence", "customerDerivedMetricsAllowed") == "true"),
        "manifestVersion": manifest.get("manifestVersion"),
    }


def evaluate(manifest: dict, inputs: dict | None = None) -> dict:
    inputs = inputs or load_json("maturity_inputs.json")
    fm = fleet_metrics(manifest)
    dims, total_w, acc = {}, 0, 0.0
    for k, d in inputs["dimensions"].items():
        score = coverage_score(fm["shiftPossibleShare"]) if d["basis"] == "computed" else d["score"]
        dims[k] = {"label": d["label"], "weight": d["weight"], "critical": d["critical"], "score": score, "basis": d["basis"]}
        total_w += d["weight"]
        acc += d["weight"] * score
    overall = round(acc / total_w, 2)
    crit = {k: v["score"] for k, v in dims.items() if v["critical"]}
    return {"official": False, "scoreStatus": "NOT_ESTABLISHED", "rubricVersion": inputs["rubricVersion"], "overall": overall, "dimensions": dims,
            "criticalMin": min(crit.values()), "criticalBelowThreshold": sorted(k for k, v in crit.items() if v < inputs["criticalThreshold"]),
            "meetsProductionPolicy": overall >= inputs["overallThreshold"] and all(v >= inputs["criticalThreshold"] for v in crit.values()),
            "fleet": fm}


def check_increase(prev: dict | None, inputs: dict) -> list[str]:
    """Anti-gaming: a judgment dimension may only rise if `changeEvidence` lists at least one item not already cited at the previous log."""
    problems = []
    if not prev:
        return problems
    for k, d in inputs["dimensions"].items():
        if d["basis"] != "judgment":
            continue
        before = (prev.get("dimensions") or {}).get(k, {}).get("score")
        if before is not None and d["score"] > before:
            cited = set(d.get("changeEvidence") or []) - set((prev.get("citedEvidence") or {}).get(k, []))
            if not cited:
                problems.append(f"{k}: {before} -> {d['score']} with no new changeEvidence")
    return problems


def diff(prev: dict | None, cur: dict) -> dict:
    keys = ("shiftPossible", "verifiedDatum", "highConfidence", "mediumConfidence", "blocked", "pilotVerified", "inferredOperatorSystem",
            "referenceZoneLakes", "effectiveZoneEligible", "licenceAllowedAB")
    pf = (prev or {}).get("fleet") or {}
    out = {k: {"previous": pf.get(k), "new": cur["fleet"][k]} for k in keys}
    out["researchMaturity"] = {"previous": (prev or {}).get("overall"), "new": cur["overall"]}
    out["fleetCoverageShare"] = {"previous": pf.get("shiftPossibleShare"), "new": cur["fleet"]["shiftPossibleShare"]}
    return out
