"""EXPLORATORY (CAL+H1 only, already-consumed data; nothing here is a validated claim and no product rule changes):
which customer-safe strong-wind formulations behave best, and does the confidence label answer the strong-wind question?
Any candidate rule that looks better needs a NEW pre-registration and NEW data before it can ship; the shipped rule (P90 >= 10 mph) is frozen by the H2 pre-reg.
  python research/strong_wind_formulation.py OUT.json"""
import json, os, pickle, sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import provider_shadow as PS
from sector_wind.brain import tonight as TN
CACHE = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/wind-brain/rows_tonight_p10p50.pkl")
R = pickle.load(open(CACHE, "rb")) if os.path.exists(CACHE) else PS.build()
if not os.path.exists(CACHE): pickle.dump(R, open(CACHE, "wb"))
S = [x for x in R if x["obsMph"] is not None and x["nbmMph"] is not None and x["nbmP90Mph"] is not None and x["nbmP50Mph"] is not None]
ev10 = lambda x: x["obsMph"] >= 10
def night_level(flag):
    n = defaultdict(lambda: [False, False])
    for x in S:
        k = (x["station"], x["init"].date()); n[k][0] |= bool(flag(x)); n[k][1] |= ev10(x)
    v = list(n.values()); hit = sum(a and b for a, b in v); fl = sum(a for a, _ in v); ev = sum(b for _, b in v)
    return {"nights": len(v), "breezyNights": ev, "flaggedNights": fl, "POD": round(hit / max(ev, 1), 3), "precision": round(hit / max(fl, 1), 3), "baseRate": round(ev / len(v), 3),
            "P(breezy|unflagged)": round((ev - hit) / max(len(v) - fl, 1), 4)}
def hour_level(flag):
    f = [flag(x) for x in S]; e = [ev10(x) for x in S]; h = sum(a and b for a, b in zip(f, e)); n = sum(f)
    return {"flagShare": round(n / len(S), 4), "POD": round(h / max(sum(e), 1), 3), "precision": round(h / max(n, 1), 3), "lift": round((h / max(n, 1)) / max((sum(e) - h) / max(len(S) - n, 1), 1e-9), 1)}
cands = {
  "shipped: P90>=10": lambda x: x["nbmP90Mph"] >= 10,
  "P90>=9": lambda x: x["nbmP90Mph"] >= 9,
  "P90>=12 (high tier)": lambda x: x["nbmP90Mph"] >= 12,
  "mean>=8": lambda x: x["nbmMph"] >= 8,
  "P50>=8": lambda x: x["nbmP50Mph"] >= 8,
  "spread(P90-P10)>=6 and P90>=8": lambda x: (x["nbmP90Mph"] - x["nbmP10Mph"]) >= 6 and x["nbmP90Mph"] >= 8,
  "P90>=10 OR mean>=8": lambda x: x["nbmP90Mph"] >= 10 or x["nbmMph"] >= 8,
  "P90>=10 OR HRRR proxy>=10": lambda x: x["nbmP90Mph"] >= 10 or (x["omMph"] or 0) >= 10,
  "P90>=10 AND HRRR proxy>=8": lambda x: x["nbmP90Mph"] >= 10 and (x["omMph"] or 0) >= 8,
}
res = {"rows": len(S), "note": "EXPLORATORY on consumed CAL+H1 data; the shipped rule stays frozen; candidates need a new pre-registration + new data", "events": sum(map(ev10, S)),
       "candidates": {k: {"hourLevel": hour_level(f), "nightLevel": night_level(f)} for k, f in cands.items()}}
# two-tier risk (shipped threshold + a higher tier)
def tier(x): return "HIGH" if x["nbmP90Mph"] >= 12 else "ELEVATED" if x["nbmP90Mph"] >= 10 else "NONE"
tt = defaultdict(lambda: [0, 0])
for x in S: tt[tier(x)][0] += 1; tt[tier(x)][1] += ev10(x)
res["twoTier(hour)"] = {k: {"rows": v[0], "P(obs>=10)": round(v[1] / v[0], 3)} for k, v in tt.items()}
# does the confidence label answer the strong-wind question?
lab = defaultdict(lambda: [0, 0])
for x in S:
    fl = TN.breezy_flag(x["nbmP90Mph"]); c = TN.confidence(x["nbmMph"], fl, False)[0]
    lab[(c, "flag" if fl else "noflag")][0] += 1; lab[(c, "flag" if fl else "noflag")][1] += ev10(x)
res["confidenceXflag(hour) P(obs>=10)"] = {f"{k[0]}|{k[1]}": {"rows": v[0], "rate": round(v[1] / max(v[0], 1), 4)} for k, v in sorted(lab.items())}
# direction reliability by label (what the label actually predicts)
from sector_wind.sample import circular_error
dl = defaultdict(list)
for x in S:
    if x["nbmDir"] is not None and x["obsDir"] is not None and x["obsMph"] * 0.44704 >= 2.6 and x["obsMph"] >= 3:
        c = TN.confidence(x["nbmMph"], TN.breezy_flag(x["nbmP90Mph"]), False)[0]
        dl[c].append(circular_error(x["nbmDir"], x["obsDir"]) <= 22.5)
res["directionWithin22_5ByLabel"] = {k: {"n": len(v), "rate": round(float(np.mean(v)), 3)} for k, v in sorted(dl.items())}
json.dump(res, open(sys.argv[1], "w"), indent=1); print(json.dumps(res, indent=1))
