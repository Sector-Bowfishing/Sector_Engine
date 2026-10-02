"""Stage 11 Parts D and E (PREREGISTRATION_STAGE11.md sections 6 and 7).
D: the satellite-only optical-water-type classifier against in-situ types (chl + turbidity, same day).
E: champion, P1, P1-NIR, C3 and C6 (both refitted on training lakes only) inside each optical state, 5 lake-group folds;
   nested routing (inner lake-group CV chooses each state's model; a state whose best inner median |log error| > 0.25
   refuses; C3 serves algal water only if it wins there). Writes part_de.json."""
import json, math, collections, random
import numpy as np
from common import *

rows = [x for x in load() if x["secchi"] and x["secchi"] > 0]
res = {}
# ---------------------------------------------------------------- Part D
T = [x for x in rows if x["insitu_type"] is not None]
labs = ["clear", "algal", "sediment", "mixed"]
conf = {a: {b: 0 for b in labs + ["unsupported"]} for a in labs}
for x in T: conf[x["insitu_type"]][x["owt"]] += 1
sup = [x for x in T if x["owt"] != "unsupported"]
recall = {a: (conf[a][a] / sum(conf[a].values())) if sum(conf[a].values()) else None for a in labs}
prec = {a: (conf[a][a] / sum(conf[t][a] for t in labs)) if sum(conf[t][a] for t in labs) else None for a in labs}
bal = float(np.mean([v for v in recall.values() if v is not None]))
maj = collections.Counter(x["insitu_type"] for x in T).most_common(1)[0][0]
res["D"] = {"rows": len(T), "lakes": len({x["lake"] for x in T}), "unsupported_share": round(1 - len(sup) / len(T), 3) if T else None,
            "confusion (rows = in-situ, cols = satellite)": conf, "recall": {k: (round(v, 3) if v is not None else None) for k, v in recall.items()},
            "precision": {k: (round(v, 3) if v is not None else None) for k, v in prec.items()}, "balanced_accuracy": round(bal, 3),
            "constant_baseline_balanced_accuracy": 0.25, "majority_class": maj,
            "insitu_class_counts": dict(collections.Counter(x["insitu_type"] for x in T)),
            "satellite_class_counts_all_rows": dict(collections.Counter(x["owt"] for x in rows))}
res["D"]["useful"] = bool(bal >= 0.50 and all((recall[k] or 0) >= 0.40 for k in ("algal", "sediment", "clear")))
res["D"]["balanced_accuracy_ci"] = lake_boot(T, lambda R: float(np.mean([sum(1 for x in R if x["insitu_type"] == a and x["owt"] == a) / max(1, sum(1 for x in R if x["insitu_type"] == a)) for a in labs])))

# ---------------------------------------------------------------- Part E
def c3_feats(x):
    lr = math.log10(max(x["raw"]["red"], 0.001)); a = 1.0 if ndci(x["raw"]) > 0 else 0.0
    return [1 - a, (1 - a) * lr, a, a * lr]
def c6_feats(x):
    lr = math.log10(max(x["raw"]["red"], 0.001)); nd = ndci(x["raw"])
    return [1.0, lr, nd, nd * lr]
def fit(tr, fe):
    X = np.array([fe(x) for x in tr]); y = np.array([math.log10(x["secchi"]) for x in tr])
    return np.linalg.lstsq(X, y, rcond=None)[0]
def predict_all(tr, te):
    """-> {model: [pred or None per te row]} with C3/C6 fitted on tr only."""
    b3, b6 = fit(tr, c3_feats), fit(tr, c6_feats)
    out = collections.defaultdict(list)
    for x in te:
        out["champion"].append(x["champ"])
        z, _, _ = P1({"blue": x["raw"]["blue"], "green": x["raw"]["green"], "red": x["raw"]["red"], "re1": x["raw"]["re1"]}, x["sun_elev"])
        out["P1"].append(z)
        zn, _ = p1nir({"blue": x["raw"]["blue"], "green": x["raw"]["green"], "red": x["raw"]["red"], "re1": x["raw"]["re1"], "re3": x["raw"].get("rededge3")}, x["sun_elev"])
        out["P1-NIR"].append(zn)
        out["C3"].append(10 ** float(np.dot(b3, c3_feats(x))))
        out["C6"].append(10 ** float(np.dot(b6, c6_feats(x))))
    return out
MODELS = ["champion", "P1", "P1-NIR", "C3", "C6"]
STATES = ["clear", "algal", "sediment", "mixed", "unsupported"]
E = [x for x in rows if x["raw"].get("red") and x["raw"].get("re1")]
for x in E: x["pred"] = {}
for k in range(5):
    tr = [x for x in E if fold(x["lake"]) != k]; te = [x for x in E if fold(x["lake"]) == k]
    P = predict_all(tr, te)
    for i, x in enumerate(te):
        x["pred"] = {m: P[m][i] for m in MODELS}
def le(x, m):
    v = x["pred"].get(m)
    return None if v is None or v <= 0 else math.log10(v / x["secchi"])
def st(R, m):
    e = [le(x, m) for x in R]; ok = [(x, v) for x, v in zip(R, e) if v is not None]
    if len(ok) < 10 or len({x['lake'] for x, _ in ok}) < 3:
        return {"n": len(ok), "note": "INSUFFICIENT"}
    ft = [x["pred"][m] - x["secchi"] for x, _ in ok]
    return {"n": len(ok), "lakes": len({x['lake'] for x, _ in ok}), "coverage": round(len(ok) / len(R), 3),
            "median_abs_log": round(float(np.median(np.abs([v for _, v in ok]))), 3), "median_signed_ft": round(float(np.median(ft)), 2),
            "MAE_ft": round(float(np.mean(np.abs(ft))), 2), "class_acc": round(float(np.mean([cls(x["pred"][m]) == cls(x["secchi"]) for x, _ in ok])), 3)}
res["E_by_state"] = {s: {m: st([x for x in E if x["owt"] == s], m) for m in MODELS} for s in STATES}
res["E_all"] = {m: st(E, m) for m in MODELS}
res["E_state_counts"] = dict(collections.Counter(x["owt"] for x in E))
# nested routing
def inner_choice(tr):
    for x in tr: x["ipred"] = {}
    for j in range(4):
        itr = [x for x in tr if (fold(x["lake"], 20) % 4) != j]; ite = [x for x in tr if (fold(x["lake"], 20) % 4) == j]
        if len(itr) < 30 or not ite: continue
        P = predict_all(itr, ite)
        for i, x in enumerate(ite): x["ipred"] = {m: P[m][i] for m in MODELS}
    choice = {}
    for s in STATES:
        R = [x for x in tr if x["owt"] == s and x["ipred"]]
        best, bv = None, None
        for m in MODELS:
            e = [math.log10(x["ipred"][m] / x["secchi"]) for x in R if x["ipred"].get(m) and x["ipred"][m] > 0]
            if len(e) < 10 or len(e) < 0.5 * len(R): continue
            v = float(np.median(np.abs(e)))
            if bv is None or v < bv: best, bv = m, v
        choice[s] = best if (best is not None and bv <= 0.25) else None
        if choice[s] == "C3" and s == "algal" and best != "C3":
            choice[s] = None
    return choice
routed, choices = [], {}
for k in range(5):
    tr = [x for x in E if fold(x["lake"]) != k]; te = [x for x in E if fold(x["lake"]) == k]
    ch = inner_choice(tr); choices[k] = ch
    for x in te:
        m = ch.get(x["owt"])
        x["routed"] = x["pred"].get(m) if m else None
        x["routed_model"] = m
for x in E: x["pred"]["routed"] = x["routed"]
res["E_routing_choices_by_fold"] = choices
res["E_routed"] = st(E, "routed")
res["E_routed_coverage"] = round(sum(1 for x in E if x["routed"] is not None) / len(E), 3)
best_single = min(MODELS, key=lambda m: res["E_all"][m].get("median_abs_log", 9))
res["E_best_single"] = best_single
def diff_fn(R):
    a = [abs(le(x, "routed")) for x in R if le(x, "routed") is not None and le(x, best_single) is not None]
    b = [abs(le(x, best_single)) for x in R if le(x, "routed") is not None and le(x, best_single) is not None]
    return float(np.median(a) - np.median(b)) if a else None
routed_rows = [x for x in E if x["routed"] is not None]
res["E_routed_vs_best_single_same_rows"] = {"routed": round(float(np.median([abs(le(x, "routed")) for x in routed_rows])), 3),
                                            "best_single": round(float(np.median([abs(le(x, best_single)) for x in routed_rows if le(x, best_single) is not None])), 3),
                                            "diff_ci": lake_boot(routed_rows, diff_fn)}
stable = {}
for s in STATES:
    picks = [choices[k].get(s) for k in choices]
    c = collections.Counter(p for p in picks if p)
    stable[s] = {"picks": picks, "stable": bool(c and c.most_common(1)[0][1] >= 4)}
res["E_choice_stability"] = stable
rv, bv = res["E_routed_vs_best_single_same_rows"]["routed"], res["E_routed_vs_best_single_same_rows"]["best_single"]
ci = res["E_routed_vs_best_single_same_rows"]["diff_ci"]
nonref = [s for s in STATES if any(choices[k].get(s) for k in choices)]
res["E_routing_supported"] = bool(bv and (bv - rv) / bv >= 0.10 and ci and ci[1] < 0 and all(stable[s]["stable"] for s in nonref) and res["E_routed_coverage"] >= 0.70)
json.dump(res, open(f"{D11}/analysis/part_de.json", "w"), indent=1, default=str)
print(json.dumps({k: res[k] for k in ("D",)}, indent=0, default=str)[:3000])
print(json.dumps({k: res[k] for k in ("E_all", "E_state_counts", "E_routing_choices_by_fold", "E_routed", "E_routed_coverage", "E_best_single", "E_routed_vs_best_single_same_rows", "E_choice_stability", "E_routing_supported")}, indent=0, default=str))
for s in STATES:
    print(s, {m: (v.get("median_abs_log"), v.get("median_signed_ft"), v.get("n")) for m, v in res["E_by_state"][s].items()})
