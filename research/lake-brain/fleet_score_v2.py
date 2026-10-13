#!/usr/bin/env python3
"""Fleet research score over the wave-1 + wave-2 binding table (docs/research/lake-brain/data/verified_bindings_v2.csv).

Three counting tiers, fixed before the numbers were computed (the order is by how little post-hoc judgement they contain):
  T1 STRICT      wave w1 + w2-v1, status VERIFIED / VERIFIED_CORROBORATED          binding-review-v1 as pre-registered   <- PRIMARY research score
                 minus rows that carry a v1.1 rule tag (Clinton Lake) and rows whose ONLY source is an undocumented operator web endpoint
                 (nipsco, njwsa, duke, wps-hydro, alliant: terms unreviewed, M-G02) -> 6 lakes excluded from the primary figure
  T2 +v1.1       T1 + wave w2-v1.1 VERIFIED                                         rules written after seeing wave-1 failures (labelled v1.1)
  T3 +R7h        T2 + VERIFIED_ENVELOPE (flagged lakes promoted by their own 5-y history envelope)   post-hoc rule, error rate unmeasured
Quality shares: history = recount of composite series where the plan thread built one, else the v2 table's class; plan / flood evidence
only where the plan thread verified it (wave-1 lakes); lakes that entered later get NO plan/flood credit (conservative).
usage: fleet_score_v2.py [--tier T1|T2|T3] [--min-years N]
"""
from __future__ import annotations

import argparse, collections, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "tools"))
import fleet_score as F  # noqa: E402
from research_score import score  # noqa: E402

V2 = os.path.join(HERE, "..", "..", "docs", "research", "lake-brain", "data", "verified_bindings_v2.csv")
TIERS = {"T1": ({"w1", "w2-v1"}, {"VERIFIED", "VERIFIED_CORROBORATED"}),
         "T2": ({"w1", "w2-v1", "w2-v1.1"}, {"VERIFIED", "VERIFIED_CORROBORATED"}),
         "T3": ({"w1", "w2-v1", "w2-v1.1"}, {"VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_ENVELOPE"})}


UNDOCUMENTED = {"nipsco", "njwsa", "duke", "wps-hydro", "alliant", "srp", "cnppid", "nppd", "utahlake", "aep", "eccc", "mncsg"}


def run(tier: str, min_years: int, plan_col="planStrict", flood_col="floodStrict") -> dict:
    waves, statuses = TIERS[tier]
    rows = [r for r in csv.DictReader(open(V2)) if r["wave"] in waves and r["binding_status"] in statuses]
    if tier == "T1":
        rows = [r for r in rows if "v1.1" not in r["checks_passed"] and r["provider"] not in UNDOCUMENTED]
    ov = F.overlay_tables(); ty = F.tva_years()
    cl = []
    for r in rows:
        row = {"lakeId": r["lake_id"], "capability": r["capability_class"], "provider": r["provider"], "historyClass": r["history_class"],
               "completeYears": r["complete_years"] or "0", "operatorPlan": ""}
        cl.append(F.classify(row, ty, min_years, ov, plan_col, flood_col))
    n = len(rows)
    sh = lambda k: sum(1 for c in cl if c[k]) / n  # noqa: E731
    shares = {"src": sh("src"), "plan": sh("plan"), "hist": sh("hist"), "base": sh("base"), "obs": 1.0, "flood": sh("flood")}
    out = {"tier": tier, "profiled": n, "profiledPct": round(100 * n / 621, 1), "shares": {k: round(v, 3) for k, v in shares.items()},
           "byProvider": dict(collections.Counter(r["provider"] for r in rows)), "scores": {}}
    for v in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"):
        s = score(621, n, shares, v)
        out["scores"][v] = {"displayed": s["value"], "uncapped": s["uncapped"], "gates": [g["gate"] for g in s["scoreBlockers"] if g.get("gate")]}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--tier", default=None); ap.add_argument("--min-years", type=int, default=5)
    ap.add_argument("--json", default=None); a = ap.parse_args()
    res = [run(t, a.min_years) for t in ([a.tier] if a.tier else TIERS)]
    for o in res:
        sc = o["scores"]
        print(f"{o['tier']}: {o['profiled']} lakes ({o['profiledPct']}%) shares {o['shares']}")
        print("     " + "  ".join(f"{k}: displayed {v['displayed']} (uncapped {v['uncapped']})" for k, v in sc.items()))
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
