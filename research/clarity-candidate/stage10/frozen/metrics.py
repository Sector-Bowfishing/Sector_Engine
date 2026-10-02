"""Stage 10 frozen metrics: verbatim copies of Stage 7 research.py (sp, auc, cls, PBINS, evaluate)
and Stage 8 c6_research.py (gates). Do not edit; frozen_manifest.json pins their hashes."""
import collections
import numpy as np
from scipy import stats as st


def sp(x, y):
    if len(x) < 5:
        return None
    r, p = st.spearmanr(x, y)
    return [round(float(r), 3), float(f"{p:.3g}"), len(x)]


def auc(pos, neg):
    if not pos or not neg: return None
    return round(float(np.mean([(p > q) + 0.5 * (p == q) for p in pos for q in neg])), 3)
def cls(ft): return 0 if ft >= 6 else 1 if ft >= 3 else 2 if ft >= 2 else 3
PBINS = [(0, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 8), (8, 99)]
def evaluate(rows, key):
    if not rows: return {"n": 0}
    p = np.array([r[key] for r in rows]); y = np.array([r["secchi"] for r in rows]); e = p - y
    per = collections.defaultdict(list)
    for r in rows: per[r["site"]].append(r[key] - r["secchi"])
    out = {"n": len(rows), "sites": len(per), "spearman": sp(list(p), list(y)), "medianSigned": round(float(np.median(e)), 2),
           "meanSigned": round(float(e.mean()), 2), "MAE": round(float(np.abs(e).mean()), 2), "medAE": round(float(np.median(np.abs(e))), 2),
           "stationBalancedMedianSigned": round(float(np.median([np.median(v) for v in per.values()])), 2),
           "stationBalancedMAE": round(float(np.median([np.mean(np.abs(v)) for v in per.values()])), 2),
           "predP10P90": [round(float(np.percentile(p, 10)), 2), round(float(np.percentile(p, 90)), 2)],
           "obsP10P90": [round(float(np.percentile(y, 10)), 2), round(float(np.percentile(y, 90)), 2)]}
    cal = []
    for lo, hi in PBINS:
        s = [r for r in rows if lo <= r[key] < hi]
        cal.append({"bin": f"{lo}-{hi if hi < 99 else '+'}", "n": len(s), "medianObs": round(float(np.median([r['secchi'] for r in s])), 2) if s else None})
    out["calibration"] = cal
    big = [b for b in cal if b["n"] >= 5]
    out["monotone"] = len(big) >= 3 and all(big[i + 1]["medianObs"] >= big[i]["medianObs"] - 0.5 for i in range(len(big) - 1))
    sub = {"stained 2-3 ft": [r for r in rows if 2 <= r["secchi"] < 3],
           "clear channel": [r for r in rows if r.get("kind") == "mainStem" and r["secchi"] >= 6],
           "algal arms": [r for r in rows if r.get("kind") == "arm" and ((r["chl"] is not None and r["chl"] >= 15) or (r["chl"] is None and r["ndci"] > 0))],
           "sediment turbid": [r for r in rows if ((r.get("turb") or 0) >= 8 or r["secchi"] <= 3) and r["chl"] is not None and r["chl"] < 10]}
    out["subsets"] = {k: ({"n": len(v), "medianSigned": round(float(np.median([r[key] - r['secchi'] for r in v])), 2),
                           "medianPred": round(float(np.median([r[key] for r in v])), 2), "medianObs": round(float(np.median([r['secchi'] for r in v])), 2)}
                          if v else {"n": 0}) for k, v in sub.items()}
    out["AUC_clearChannel_vs_stainedArm"] = auc([r[key] for r in rows if r.get("kind") == "mainStem" and r["secchi"] >= 6],
                                               [r[key] for r in rows if r.get("kind") == "arm" and r["secchi"] <= 3])
    yc = [cls(v) for v in y]; pc = [cls(v) for v in p]
    typical = cls(float(np.median(y)))
    out["classAcc"] = round(float(np.mean([a == b for a, b in zip(yc, pc)])), 3)
    out["classAccConstant"] = round(float(np.mean([a == typical for a in yc])), 3)
    return out


def gates(e, c0):
    return {"1 spearman>=0.5": (e["spearman"] or [0])[0] >= 0.5,
            "2 monotone": e["monotone"],
            "3 |stationBalancedMedianSigned|<=0.75": abs(e["stationBalancedMedianSigned"]) <= 0.75,
            "4 stained medianSigned<=+1.0": e["subsets"]["stained 2-3 ft"]["n"] > 0 and e["subsets"]["stained 2-3 ft"]["medianSigned"] <= 1.0,
            "5 clear channel medianSigned>=-1.5": e["subsets"]["clear channel"]["n"] > 0 and e["subsets"]["clear channel"]["medianSigned"] >= -1.5,
            "6 AUC>=0.8": (e["AUC_clearChannel_vs_stainedArm"] or 0) >= 0.8,
            "7 classAcc>=constant+0.10": e["classAcc"] >= e["classAccConstant"] + 0.10,
            "8 beats champion MAE and medAE": e["MAE"] < c0["MAE"] and e["medAE"] < c0["medAE"]}
