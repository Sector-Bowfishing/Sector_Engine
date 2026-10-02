"""Guntersville historical rows (reported apart; never used for selection): production fits on all E13 rows applied to
the Guntersville rows with a valid ACOLITE disk. Writes gunt13.json."""
import json, math, numpy as np
from common13 import *
import models13_lib as L
R = load12()
E = [x for x in R if x["aco_valid"] and not x["gunt"] and x["secchi"] and x["secchi"] > 0]
G = [x for x in R if x["aco_valid"] and x["gunt"] and x["secchi"] and x["secchi"] > 0]
for x in E + G:
    x["F"], x["q"] = features(x["aco"], x["sun_elev"]); x["y"] = math.log10(x["secchi"]); x["c"] = cls(x["secchi"])
    x["t_red"] = t_red(x["aco"]["B04"]); x["t_sw"], x["w_sw"] = t_switch(x["aco"]["B04"], x["aco"].get("B8A"))
P, C = L.fit_predict(E, G)
out = {"n": len(G), "lakes": len({x["lake"] for x in G}), "classes": dict(zip(CLASSES, [sum(x["c"] == c for x in G) for c in range(4)]))}
for m in ("A", "C-lin", "C-gbm", "O2"):
    pm = "C-lin" if m == "O2" else m
    e = [p - x["y"] for p, x in zip(P[pm], G) if p is not None]
    cm = class_metrics([x["c"] for x in G], C[m])
    out[m] = {"median_abs_log": round(float(np.median(np.abs(e))), 3), "median_signed_ft": round(float(np.median([10 ** p - x["secchi"] for p, x in zip(P[pm], G) if p is not None])), 2),
              "class_accuracy": round(float(np.mean([a == b for a, b in zip(C[m], [x["c"] for x in G])])), 3),
              **{n: (cm[n]["recall"], cm[n]["precision"]) for n in CLASSES}}
json.dump(out, open(f"{D13}/analysis/gunt13.json", "w"), indent=1, default=str); print(json.dumps(out, indent=1, default=str))
