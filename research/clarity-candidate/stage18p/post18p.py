"""Stage 18P post-scoring (pre-registered metrics not computed in dev18p.py): exact-feet error on the SAME rows, the
Stage 12 exact-feet capability, and harmful/severe by class. Reads dev18p_rows.json and dev16_rows.json only."""
import json, sys, numpy as np, collections
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage16/analysis", f"{S}/stage14/analysis"]
from lib16 import CONTAINS, CLASSES
from lib14 import hard_std
sel = json.load(open(f"{S}/stage18p/dev18p_rows.json")); base = {r["id"]: r for r in json.load(open(f"{S}/stage16/analysis/dev16_rows.json"))}
shown = lambda o: o["state"] in CONTAINS and o["authority"] == "full" and o.get("display") in ("exact", "approx")
pv = lambda r: r["o"].get("p") if r["o"].get("consensus") else base[r["id"]].get("p")
both = [r for r in sel if shown(r["o"]) and shown(base[r["id"]]["o"]) and pv(r) is not None and base[r["id"]].get("p") is not None]
out = {"same_rows": len(both),
       "feet_err_same_rows": {"stage16": float(np.median([abs(base[r["id"]]["p"] - r["y"]) for r in both])), "selected": float(np.median([abs(pv(r) - r["y"]) for r in both]))},
       "feet_err_same_rows_stained": {"n": sum(1 for r in both if r["c"] == 2),
                                      "stage16": float(np.median([abs(base[r["id"]]["p"] - r["y"]) for r in both if r["c"] == 2])),
                                      "selected": float(np.median([abs(pv(r) - r["y"]) for r in both if r["c"] == 2]))}}
out["harm_by_class"] = {CLASSES[c]: {"stage16": float(np.mean([base[r["id"]]["harmful"] for r in sel if r["c"] == c])), "selected": float(np.mean([r["harmful"] for r in sel if r["c"] == c])),
                                     "severe16": float(np.mean([base[r["id"]]["severe"] for r in sel if r["c"] == c])), "severe_sel": float(np.mean([r["severe"] for r in sel if r["c"] == c])), "n": sum(1 for r in sel if r["c"] == c)} for c in range(4)}
# where the extra harmful answers come from: rows harmful in the selected engine but not in Stage 16
newh = [r for r in sel if r["harmful"] and not base[r["id"]]["harmful"]]; goneh = [r for r in sel if not r["harmful"] and base[r["id"]]["harmful"]]
out["harm_flow"] = {"new_harmful": len(newh), "no_longer_harmful": len(goneh), "new_from_stage16_unknown": sum(1 for r in newh if base[r["id"]]["o"]["state"] not in CONTAINS),
                    "new_by_class": dict(collections.Counter(CLASSES[r["c"]] for r in newh))}
# Stage 12 exact-feet capability (the same capscore13 code Stages 13-17 used)
src = open(f"{S}/stage13/analysis/capscore13.py").read()
def capscore(rr):
    ns = {}; code = src.split("rows = [r for r in")[0].replace('M = json.load(open(f"{D13}/analysis/models13.json")); ENG = M["BEST"]', 'ENG = "dev18p"')
    code += "\nrows = RR\n" + "out = {" + src.split("out = {", 1)[1].split("json.dump(out")[0]; ns["RR"] = rr; exec(code, ns); return ns["out"]
def recs(rows, consensus):
    o_ = []
    for r in rows:
        o = r["o"]; p = pv(r) if consensus else r.get("p")
        pred = CLASSES[hard_std(p)] if (p is not None and r["tier"] in (1, 2)) else ("clear" if o["state"] == "Clear" else "unknown")
        o_.append({"true": CLASSES[r["c"]], "pred": pred, "ft": 10 ** p if (shown(o) and p is not None) else None, "secchi": r["secchi"], "feet": bool(shown(o) and p is not None),
                   "insitu_type": r["insitu_type"], "turb": r["turb"]})
    return o_
out["exact_feet_capability"] = {"stage16": capscore(recs(list(base.values()), False))["EXACT_FEET_CAPABILITY"], "selected": capscore(recs(sel, True))["EXACT_FEET_CAPABILITY"]}
json.dump(out, open(f"{S}/stage18p/post18p.json", "w"), indent=1)
print(json.dumps(out, indent=1))
