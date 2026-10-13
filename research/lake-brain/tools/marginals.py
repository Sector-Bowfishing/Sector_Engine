#!/usr/bin/env python3
"""Marginal value of each lever under the UNMODIFIED rubric, from the research-core scenario (258 lakes). Writes data/score_marginals.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from research_score import score  # noqa: E402

BASE = dict(profiled=258, shares={"src": 1.0, "plan": 0.198, "hist": 0.779, "base": 0.86, "obs": 1.0, "flood": 0.302})
LEVERS = [
    ("research core as measured", {}),
    ("+ promote the 57 flagged (315 lakes, shares per fleet_score --with-flagged)", dict(profiled=315, shares={"src": 1.0, "plan": 0.178, "hist": 0.765, "base": 0.835, "obs": 1.0, "flood": 0.27})),
    ("operatorPlan share 0.20 -> 0.50", dict(plan=0.50)),
    ("operatorPlan share 0.20 -> 0.80", dict(plan=0.80)),
    ("floodDroughtContext share 0.30 -> 0.60", dict(flood=0.60)),
    ("history share 0.78 -> 0.95 (deep history for the remaining lakes)", dict(hist=0.95, base=0.97)),
    ("coverage 41.5% -> 50% (311 lakes) at the same quality shares", dict(profiled=311)),
    ("coverage -> 75% (466 lakes) at the same quality shares", dict(profiled=466)),
    ("coverage -> 90% (559 lakes) at the same quality shares", dict(profiled=559)),
    ("coverage 75% AND plan 0.5 AND flood 0.5 AND history 0.95", dict(profiled=466, plan=0.5, flood=0.5, hist=0.95, base=0.97)),
    ("coverage 90% AND plan 0.8 AND flood 0.6 AND history 0.95", dict(profiled=559, plan=0.8, flood=0.6, hist=0.95, base=0.97)),
]
rows = []
for name, chg in LEVERS:
    sh = dict(BASE["shares"]); prof = BASE["profiled"]
    for k, v in chg.items():
        if k == "profiled": prof = v
        elif k == "shares": sh = dict(v)
        else: sh[k] = v
    row = {"lever": name, "profiled": prof, "shares": {k: round(v, 3) for k, v in sh.items()}}
    for val in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"):
        s = score(621, prof, sh, val)
        row[val] = {"displayed": s["value"], "uncapped": s["uncapped"]}
    rows.append(row)
    print(f"{name[:78]:78s} NV {row['NOT_VALIDATED']['displayed']}({row['NOT_VALIDATED']['uncapped']})  PARTIAL {row['PARTIAL']['displayed']}  VALIDATED {row['VALIDATED']['displayed']}")
out = os.path.join(HERE, "..", "..", "..", "docs", "research", "lake-brain", "data", "score_marginals.json")
json.dump(rows, open(out, "w"), indent=1)
