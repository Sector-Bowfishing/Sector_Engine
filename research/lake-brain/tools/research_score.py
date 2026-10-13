#!/usr/bin/env python3
"""Research re-scoring for Lake Brain — runs the UNMODIFIED production rubric (score_lake, lake-brain-score-v1).

  python3 research_score.py ladder                      score ladder: what must be true for 4..9 (uniform-quality model)
  python3 research_score.py scenario scenario.json      score a research scenario (facts built from research evidence)
  python3 research_score.py baseline                    reproduce the published 3.0 from the published facts shape

A scenario is {"directory": 621, "profiled": N, "shares": {src, plan, hist, base, obs, flood}, "validation": "...",
"health": "WARNING"}: N synthetic profiles/states are built so that exactly round(share*N) satisfy each rubric predicate.
Nothing here writes anywhere; nothing here edits the rubric. A research score is a *conditional* number: it holds only if
the evidence behind each share is accepted under the review criteria in LAKE_BRAIN_VALIDATION_STRATEGY.md.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"))
from sector_brain_platform.scoring import score_lake, COVERAGE_LADDER  # noqa: E402

NOW = dt.datetime(2026, 10, 13, 12, 0, tzinfo=dt.timezone.utc)
SHARES = ("src", "plan", "hist", "base", "obs", "flood")


def facts(directory: int, profiled: int, shares: dict, validation: str, health: str = "WARNING") -> dict:
    k = lambda s: round(shares.get(s, 0.0) * profiled)  # noqa: E731
    profiles, states = {}, {}
    for i in range(profiled):
        src_ok = i < k("src")
        plan_ok = i < k("plan")
        hist_ok = i < k("hist")
        base_ok = i < max(k("base"), k("hist"))               # SUFFICIENT counts toward baseline (SUFFICIENT/LIMITED)
        base_status = "SUFFICIENT" if hist_ok else ("LIMITED" if base_ok else "INSUFFICIENT")
        profiles[f"L{i}"] = {
            "sourceCapability": {"level": "DIRECT_OPERATOR_POOL" if src_ok else "PROXY"},
            "operatingPools": {"guideCurve": {"available": plan_ok}},
            "historicalCoverage": {"baselineStatus": base_status},
        }
        states[f"L{i}"] = {"kind": "OBSERVED" if i < k("obs") else "PROXY",
                           "floodPoolState": "IN_CONSERVATION" if i < k("flood") else "UNKNOWN"}
    return {"registry": {"directoryLakeCount": directory, "health": health}, "validation": {"status": validation},
            "health": {"status": health}, "profiles": profiles, "states": states, "directoryLakeCount": directory}


def score(directory: int, profiled: int, shares: dict, validation: str, health: str = "WARNING") -> dict:
    return score_lake(facts(directory, profiled, shares, validation, health), NOW)


def ladder_table(directory: int = 621) -> list[dict]:
    rows = []
    for target in (4, 5, 6, 7, 8, 9):
        best = []
        for floor, _ in sorted(COVERAGE_LADDER, key=lambda x: x[0]):
            n = max(1, int(-(-floor * directory // 1)))          # smallest profiled count reaching this ladder floor
            for v in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"):
                lo, hi, found = 0.0, 1.0, None
                for _ in range(24):                            # minimal uniform quality share q (src/plan/hist/base/flood), obs = 1
                    q = (lo + hi) / 2
                    s = score(directory, n, {"src": q, "plan": q, "hist": q, "base": q, "obs": 1.0, "flood": q}, v)["value"]
                    if s >= target:
                        found, hi = q, q
                    else:
                        lo = q
                if found is not None:
                    best.append({"target": target, "profiled": n, "profiledPct": round(100 * n / directory, 1), "validation": v, "minQuality": round(found, 3)})
        rows += best
    return rows


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 1
    cmd = argv[1]
    if cmd == "baseline":
        s = score(621, 5, {"src": 1.0, "plan": 1.0, "hist": 0.2, "base": 0.2, "obs": 1.0, "flood": 0.2}, "NOT_VALIDATED")
        print(json.dumps({"value": s["value"], "uncapped": s["uncapped"], "gates": s["scoreBlockers"]}, indent=1))
    elif cmd == "ladder":
        rows = ladder_table()
        for t in (4, 5, 6, 7, 8, 9):
            print(f"\n=== target >= {t}.0  (uniform quality q over src/plan/hist/base/flood; trend observed = 100 %)")
            sub = [r for r in rows if r["target"] == t]
            seen = set()
            for r in sorted(sub, key=lambda r: (r["validation"] != "NOT_VALIDATED", r["validation"] != "PARTIAL", r["profiled"])):
                key = (r["validation"], r["profiled"])
                if key in seen:
                    continue
                seen.add(key)
                print(f"  validation={r['validation']:13s} profiled>={r['profiled']:3d} ({r['profiledPct']:5.1f} %)  min quality share = {r['minQuality']:.2f}")
        json.dump(rows, open(os.path.join(HERE, "..", "..", "..", "docs", "research", "lake-brain", "data", "score_ladder.json"), "w"), indent=1) if os.path.isdir(os.path.join(HERE, "..", "..", "..", "docs", "research", "lake-brain", "data")) else None
    elif cmd == "scenario":
        sc = json.load(open(argv[2]))
        s = score(sc.get("directory", 621), sc["profiled"], sc["shares"], sc["validation"], sc.get("health", "WARNING"))
        print(json.dumps({"value": s["value"], "uncapped": s["uncapped"], "dims": {k: v.get("value") for k, v in s["scoreBreakdown"].items()}, "gates": s["scoreBlockers"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
