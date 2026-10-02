"""Stage 13 section 1 (diagnostic): what explains poor Secchi in stained and limited water?
(a) In-situ models (lake-held-out): log S on log turbidity, log chlorophyll, log colour (true colour; DOC/TOC as a proxy
    where colour is absent), Shapley shares of held-out R^2, and the class recall an in-situ 'perfect retrieval' reaches.
(b) Satellite feature groups (C-lin): particles {F_red, F_re, F_bright}, colour {F_bg}, visibility ratio {F_gr},
    pigment {F_ndci}: Shapley shares of held-out R^2 overall and within stained+limited.
(c) Resolution: the expected class recall when the true value is blurred by the held-out error distribution of the best
    regressor (C-gbm), i.e. the ceiling a retrieval of that precision can reach on a band of each class's width.
Exploratory beyond the pre-registered list: (c). Writes mechanism13.json."""
import json, math, itertools, random, collections
import numpy as np
from common13 import *
R = {x["id"]: x for x in load12()}
P = json.load(open(f"{D13}/analysis/preds13.json"))
col = json.load(open(f"{D13}/insitu/color_matched.json"))
def cv_r2(rows, fx):
    """lake-held-out R^2 of OLS log S ~ fx(row)."""
    if len(rows) < 30: return None
    pred = {}
    for k in range(5):
        tr = [x for x in rows if fold(x["lake"]) != k]; te = [x for x in rows if fold(x["lake"]) == k]
        if len(tr) < 10 or not te: continue
        b = np.linalg.lstsq(np.array([[1.0] + fx(x) for x in tr]), np.array([x["y"] for x in tr]), rcond=None)[0]
        for x in te: pred[x["id"]] = float(np.dot(b, [1.0] + fx(x)))
    ys = np.array([x["y"] for x in rows if x["id"] in pred]); ps = np.array([pred[x["id"]] for x in rows if x["id"] in pred])
    return float(1 - ((ys - ps) ** 2).sum() / ((ys - ys.mean()) ** 2).sum()), pred
def shapley(rows, groups):
    names = list(groups); val = {}
    for r in range(len(names) + 1):
        for sub in itertools.combinations(names, r):
            if not sub: val[sub] = 0.0; continue
            fx = lambda x, sub=sub: [v for g in sub for v in groups[g](x)]
            out = cv_r2(rows, fx); val[sub] = max(out[0], 0.0) if out else 0.0
    n = len(names); sh = {}
    for g in names:
        s = 0.0
        for r in range(n):
            for sub in itertools.combinations([h for h in names if h != g], r):
                w = math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n)
                s += w * (val[tuple(sorted(sub + (g,), key=names.index))] - val[sub])
        sh[g] = round(s, 4)
    sh["_total"] = round(val[tuple(names)], 4); return sh
res = {}
# (a) in-situ
rows = []
for p in P:
    x = R[p["id"]]
    if x.get("turb") is None or x.get("chl") is None: continue
    c = col.get(p["id"], {})
    colour = c.get("true_color"); proxy = c.get("doc") or c.get("toc")
    rows.append({"id": p["id"], "lake": p["lake"], "y": math.log10(x["secchi"]), "c": p["c"], "lt": math.log10(max(x["turb"], 0.1)), "lc": math.log10(max(x["chl"], 0.1)),
                 "lcol": math.log10(max(colour, 1.0)) if colour is not None else None, "ldoc": math.log10(max(proxy, 0.1)) if proxy is not None else None})
G2 = {"particles (turbidity)": lambda x: [x["lt"]], "pigment (chlorophyll)": lambda x: [x["lc"]]}
res["insitu_turb_chl"] = {"n": len(rows), "all": shapley(rows, G2), "stained+limited": shapley([x for x in rows if x["c"] >= 2], G2)}
for key, name in (("lcol", "true colour"), ("ldoc", "DOC/TOC")):
    sub = [x for x in rows if x[key] is not None]
    G3 = {**G2, f"dissolved colour ({name})": (lambda x, key=key: [x[key]])}
    res[f"insitu_with_{key}"] = {"n": len(sub), "lakes": len({x['lake'] for x in sub}), "all": shapley(sub, G3) if len(sub) >= 30 else None,
                                 "stained+limited": shapley([x for x in sub if x["c"] >= 2], G3) if sum(x["c"] >= 2 for x in sub) >= 30 else None,
                                 "n_stained_limited": sum(x["c"] >= 2 for x in sub)}
# in-situ 'perfect retrieval' class recall (turbidity + chlorophyll, held-out)
out = cv_r2(rows, lambda x: [x["lt"], x["lc"]])
if out:
    pred = out[1]; tc = [x["c"] for x in rows if x["id"] in pred]; pc = [cls(10 ** pred[x["id"]]) for x in rows if x["id"] in pred]
    cm = class_metrics(tc, pc); res["insitu_class_recall_turb_chl"] = {n: (round(cm[n]["recall"], 3) if cm[n]["recall"] is not None else None, round(cm[n]["precision"] or 0, 3)) for n in CLASSES}
    res["insitu_class_recall_turb_chl"]["balanced"] = round(cm["balanced_accuracy"], 3)
    res["insitu_median_abs_log_turb_chl"] = round(float(np.median([abs(pred[x["id"]] - x["y"]) for x in rows if x["id"] in pred])), 4)
# (b) satellite groups
E = [{"id": p["id"], "lake": p["lake"], "y": math.log10(p["secchi"]), "c": p["c"], **p["F"]} for p in P]
GS = {"particles": lambda x: [x["F_red"], x["F_re"], x["F_bright"]], "dissolved colour": lambda x: [x["F_bg"]],
      "visibility ratio (green/red)": lambda x: [x["F_gr"]], "pigment": lambda x: [x["F_ndci"]]}
res["satellite_groups"] = {"all": shapley(E, GS), "stained+limited": shapley([x for x in E if x["c"] >= 2], GS)}
# (c) resolution ceiling from the C-gbm held-out error
e = np.array([p["P"]["C-gbm"] - math.log10(p["secchi"]) for p in P])
rng = np.random.default_rng(12); ceil = {}
for c, name in enumerate(CLASSES):
    ts = np.array([math.log10(p["secchi"]) for p in P if p["c"] == c])
    draws = ts[:, None] + rng.choice(e, size=(len(ts), 400))
    ceil[name] = round(float(np.mean([[cls(10 ** v) == c for v in row] for row in draws])), 3)
res["resolution_ceiling_recall (true value + C-gbm held-out error)"] = ceil
res["class_width_log10"] = {"clear": "open (>= 0.778)", "normal": round(math.log10(6 / 3), 3), "stained": round(math.log10(3 / 2), 3), "limited": "open (< 0.301)"}
res["cgbm_error_quantiles_log"] = {"median_abs": round(float(np.median(np.abs(e))), 3), "p25": round(float(np.percentile(e, 25)), 3), "p75": round(float(np.percentile(e, 75)), 3)}
json.dump(res, open(f"{D13}/analysis/mechanism13.json", "w"), indent=1)
print(json.dumps(res, indent=1))
