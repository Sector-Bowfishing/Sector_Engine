"""EXPLORATORY: C3 on ACOLITE vs C3 on Sen2Cor, same rows and folds, lake-bootstrap CI (adds to explore12.json)."""
import json, math
from common12 import *
import explore12_lib as L
V = [x for x in L.R if x["aco_valid"]]
Cp = L.heldout(V, L.c3s_fit)
P = {x["id"]: x["pred"].get("C3") for x in json.load(open(f"{D12}/analysis/preds12.json")) if not x["gunt"]}
rows = [x for x in V if Cp.get(x["id"]) and P.get(x["id"])]
fn = lambda rr: float(np.median([abs(math.log10(P[x["id"]] / x["secchi"])) for x in rr]) - np.median([abs(math.log10(Cp[x["id"]] / x["secchi"])) for x in rr]))
res = {"n": len(rows), "aco_c3": round(float(np.median([abs(math.log10(P[x['id']] / x['secchi'])) for x in rows])), 4),
       "s2c_c3": round(float(np.median([abs(math.log10(Cp[x['id']] / x['secchi'])) for x in rows])), 4), "diff": round(fn(rows), 4), "ci95": lake_boot(rows, fn)}
ex = json.load(open(f"{D12}/analysis/explore12.json")); ex["attribution_same_rows"] = res
json.dump(ex, open(f"{D12}/analysis/explore12.json", "w"), indent=1); print(res)
