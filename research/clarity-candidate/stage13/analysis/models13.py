"""Stage 13 sections 3-7 (PREREGISTRATION_STAGE13.md): every candidate on E13 with whole-lake folds; class metrics;
bootstrap CIs vs benchmark A; CDOM ablation; red/NIR switch; region-held-out check. Writes models13.json, preds13.json."""
import json, math, collections, itertools, warnings
import numpy as np
from scipy.optimize import minimize
from sklearn.ensemble import HistGradientBoostingRegressor
from common13 import *
warnings.filterwarnings("ignore")
R = load12()
E = [x for x in R if x["aco_valid"] and not x["gunt"] and x["secchi"] and x["secchi"] > 0]
for x in E:
    x["F"], x["q"] = features(x["aco"], x["sun_elev"])
    x["y"] = math.log10(x["secchi"]); x["c"] = cls(x["secchi"])
    x["t_red"] = t_red(x["aco"]["B04"]); x["t_sw"], x["w_sw"] = t_switch(x["aco"]["B04"], x["aco"].get("B8A"))
    x["region"] = region(x.get("state"))
print("E13 rows", len(E), "lakes", len({x['lake'] for x in E}))
def c3f(x):   # exactly Stage 12 models12.py (0.001 floors), the pre-registered benchmark
    r = x["aco"]; red, re1 = max(r["B04"], 0.001), max(r["B05"], 0.001)
    lr = math.log10(red); a = 1.0 if (re1 - red) / (re1 + red) > 0 else 0.0
    return [1 - a, (1 - a) * lr, a, a * lr]
def ols(X, y): return np.linalg.lstsq(np.array(X), np.array(y), rcond=None)[0]
def f6(x, drop=()): return [1.0] + [x["F"][k] for k in FEATS6 if k not in drop]
def f7(x): return [x["F"][k] for k in FEATS6 + ["F_kd"]]
# ---------------- ordinal logit (proportional odds)
def ord_fit(X, yc):
    X = np.asarray(X); n, p = X.shape
    def nll(th):
        b, c0 = th[:p], th[p]; d = np.exp(th[p + 1:]); cut = np.concatenate([[c0], c0 + np.cumsum(d)])
        eta = X @ b; P = 1 / (1 + np.exp(-(cut[None, :] - eta[:, None])))          # P(y <= k)
        P = np.hstack([np.zeros((n, 1)), P, np.ones((n, 1))]); pr = np.clip(P[np.arange(n), yc + 1] - P[np.arange(n), yc], 1e-12, 1)
        return -np.log(pr).sum() + 1e-3 * (b @ b)
    th0 = np.zeros(p + 3); th0[p] = -1.0
    r = minimize(nll, th0, method="L-BFGS-B"); return r.x, p
def ord_pred(th, p, X):
    b, c0 = th[:p], th[p]; cut = np.concatenate([[c0], c0 + np.cumsum(np.exp(th[p + 1:]))])
    eta = np.asarray(X) @ b; P = 1 / (1 + np.exp(-(cut[None, :] - eta[:, None])))
    P = np.hstack([np.zeros((len(eta), 1)), P, np.ones((len(eta), 1))]); pr = np.diff(P, axis=1)
    return pr.argmax(1)
# class index convention: 0 clear ... 3 limited. Ordinal on "murkiness" order: use yc = class index (clear=0 < ... < limited=3)
def std_fit(X): X = np.asarray(X); mu, sd = X.mean(0), X.std(0) + 1e-9; return mu, sd
def cut_classes(pred_logft, cuts):   # cuts on log10 ft descending: [c6, c3, c2]
    return [0 if v >= cuts[0] else 1 if v >= cuts[1] else 2 if v >= cuts[2] else 3 for v in pred_logft]
def learn_cuts(pred, truec):
    base = [math.log10(6), math.log10(3), math.log10(2)]; best, bv = base, -1
    grid = np.arange(-0.15, 0.1501, 0.025)
    for d0, d1, d2 in itertools.product(grid, grid, grid):
        cuts = [base[0] + d0, base[1] + d1, base[2] + d2]
        if not (cuts[0] > cuts[1] > cuts[2]): continue
        cm = class_metrics(truec, cut_classes(pred, cuts))["balanced_accuracy"]
        if cm > bv + 1e-9: best, bv = cuts, cm
    return best
def gbm():
    return HistGradientBoostingRegressor(max_leaf_nodes=8, learning_rate=0.05, max_iter=300, min_samples_leaf=30, l2_regularization=1.0,
                                         early_stopping=True, validation_fraction=0.15, random_state=12,
                                         monotonic_cst=[-1, 0, 0, 1, 0, 0, -1])
def fit_predict(tr, te, inner_cuts=True):
    """All candidates fitted on tr, predicted on te -> {model: [log10 ft or None]} and class predictions {model: [idx or None]}."""
    P, C = {}, {}
    b3 = ols([c3f(x) for x in tr], [x["y"] for x in tr]); P["A"] = [float(np.dot(b3, c3f(x))) for x in te]
    P["B-pure"] = [math.log10(x["q"]["zsd_ft"]) if x["q"].get("zsd_ft") else None for x in te]
    trb = [x for x in tr if x["q"].get("zsd_ft")]
    bb = ols([[1.0, math.log10(x["q"]["zsd_ft"])] for x in trb], [x["y"] for x in trb])
    P["B-cal"] = [float(bb[0] + bb[1] * math.log10(x["q"]["zsd_ft"])) if x["q"].get("zsd_ft") else None for x in te]
    bl = ols([f6(x) for x in tr], [x["y"] for x in tr]); P["C-lin"] = [float(np.dot(bl, f6(x))) for x in te]
    bn = ols([f6(x, ("F_bg",)) for x in tr], [x["y"] for x in tr]); P["C-lin-noCDOM"] = [float(np.dot(bn, f6(x, ("F_bg",)))) for x in te]
    g = gbm().fit(np.array([f7(x) for x in tr]), np.array([x["y"] for x in tr])); P["C-gbm"] = [float(v) for v in g.predict(np.array([f7(x) for x in te]))]
    # champion form on T_red vs T_switch (section 3)
    for key, name in (("t_red", "champ-Tred"), ("t_sw", "champ-Tswitch")):
        bc = ols([[1.0, math.log10(max(x[key], 0.1))] for x in tr], [x["y"] for x in tr]); P[name] = [float(bc[0] + bc[1] * math.log10(max(x[key], 0.1))) for x in te]
    for m, v in P.items(): C[m] = [None if p is None else cut_classes([p], [math.log10(6), math.log10(3), math.log10(2)])[0] for p in v]
    # O1 ordinal logit on standardized 6 features (and without F_bg)
    for name, drop in (("O1", ()), ("O1-noCDOM", ("F_bg",))):
        Xtr = np.array([f6(x, drop)[1:] for x in tr]); mu, sd = std_fit(Xtr)
        th, p = ord_fit((Xtr - mu) / sd, np.array([x["c"] for x in tr]))
        C[name] = [int(v) for v in ord_pred(th, p, (np.array([f6(x, drop)[1:] for x in te]) - mu) / sd)]
    # O2 C-lin + cut-points from inner-fold predictions
    if inner_cuts:
        ip, ic = [], []
        for j in range(4):
            itr = [x for x in tr if (fold(x["lake"], 20) % 4) != j]; ite = [x for x in tr if (fold(x["lake"], 20) % 4) == j]
            bi = ols([f6(x) for x in itr], [x["y"] for x in itr]); ip += [float(np.dot(bi, f6(x))) for x in ite]; ic += [x["c"] for x in ite]
        cuts = learn_cuts(ip, ic)
        C["O2"] = cut_classes(P["C-lin"], cuts)
    return P, C
MODELS_REG = ["A", "B-pure", "B-cal", "C-lin", "C-lin-noCDOM", "C-gbm", "champ-Tred", "champ-Tswitch"]
MODELS_CLS = MODELS_REG + ["O1", "O1-noCDOM", "O2"]
for x in E: x["P"], x["C"] = {}, {}
for k in range(5):
    tr = [x for x in E if fold(x["lake"]) != k]; te = [x for x in E if fold(x["lake"]) == k]
    P, C = fit_predict(tr, te)
    for i, x in enumerate(te):
        for m in P: x["P"][m] = P[m][i]
        for m in C: x["C"][m] = C[m][i]
res = {"rows": len(E), "lakes": len({x["lake"] for x in E})}
S12 = {x["id"]: x["pred"].get("C3") for x in json.load(open(f"{S}/stage12/analysis/preds12.json"))}
dd = [abs(10 ** x["P"]["A"] - S12[x["id"]]) for x in E if S12.get(x["id"])]
res["A_matches_stage12_max_abs_ft"] = round(float(max(dd)), 6); print("A vs Stage 12 C3, max |diff| ft:", res["A_matches_stage12_max_abs_ft"])
true = [x["c"] for x in E]
res["class"] = {m: class_metrics(true, [x["C"][m] for x in E]) for m in MODELS_CLS}
def reg_stats(m):
    ok = [x for x in E if x["P"].get(m) is not None]
    e = [x["P"][m] - x["y"] for x in ok]
    return {"coverage": round(len(ok) / len(E), 3), "median_abs_log": round(float(np.median(np.abs(e))), 4), "median_signed_log": round(float(np.median(e)), 4)} if ok else None
res["regression"] = {m: reg_stats(m) for m in MODELS_REG}
# bootstrap CIs of class-metric differences vs A
def recall(rows, m, c):
    t = [x for x in rows if x["c"] == c]; return sum(1 for x in t if x["C"][m] == c) / len(t) if t else float("nan")
def precision(rows, m, c):
    p = [x for x in rows if x["C"][m] == c]; return sum(1 for x in p if x["c"] == c) / len(p) if p else float("nan")
def bal(rows, m): return float(np.nanmean([recall(rows, m, c) for c in range(4)]))
res["vs_A"] = {}
for m in MODELS_CLS:
    if m == "A": continue
    d = {}
    for c, name in ((2, "stained"), (3, "limited")):
        d[f"{name}_recall_diff"] = round(recall(E, m, c) - recall(E, "A", c), 4)
        d[f"{name}_recall_ci"] = lake_boot_diff(E, lambda rr, m=m, c=c: recall(rr, m, c) - recall(rr, "A", c))
    d["balanced_diff"] = round(bal(E, m) - bal(E, "A"), 4); d["balanced_ci"] = lake_boot_diff(E, lambda rr, m=m: bal(rr, m) - bal(rr, "A"))
    res["vs_A"][m] = d
# CDOM ablation (section 7): full minus no-F_bg
res["cdom_ablation"] = {}
for full, abl in (("C-lin", "C-lin-noCDOM"), ("O1", "O1-noCDOM")):
    res["cdom_ablation"][full] = {"stained_recall_drop": round(recall(E, full, 2) - recall(E, abl, 2), 4),
                                  "stained_recall_ci": lake_boot_diff(E, lambda rr, a=full, b=abl: recall(rr, a, 2) - recall(rr, b, 2)),
                                  "balanced_drop": round(bal(E, full) - bal(E, abl), 4),
                                  "balanced_ci": lake_boot_diff(E, lambda rr, a=full, b=abl: bal(rr, a) - bal(rr, b))}
cd = res["cdom_ablation"]
res["CDOM_USEFUL"] = any((v["stained_recall_drop"] >= 0.03 and v["stained_recall_ci"] and v["stained_recall_ci"][0] > 0) or
                         (v["balanced_drop"] >= 0.03 and v["balanced_ci"] and v["balanced_ci"][0] > 0) for v in cd.values())
# red/NIR switch (section 3)
sw = {"activation_share": round(float(np.mean([x["w_sw"] > 0 for x in E])), 4), "full_nir_share": round(float(np.mean([x["w_sw"] >= 1 for x in E])), 4)}
def et(x, key): return math.log10(max(x[key], 0.1) / max(x["turb"], 0.1))
for name, sel in (("stained", lambda x: x["c"] == 2), ("limited", lambda x: x["c"] == 3), ("sediment", lambda x: x["insitu_type"] == "sediment")):
    rr = [x for x in E if sel(x) and x.get("turb") is not None and x.get("dt") == 0]
    if len(rr) < 10: sw[name] = {"n": len(rr), "note": "INSUFFICIENT"}; continue
    a = float(np.median([abs(et(x, "t_red")) for x in rr])); b = float(np.median([abs(et(x, "t_sw")) for x in rr]))
    sw[name] = {"n": len(rr), "red_only": round(a, 3), "switch": round(b, 3), "rel_improvement": round((a - b) / a, 3) if a else None,
                "diff_ci": lake_boot_diff(rr, lambda q: float(np.median([abs(et(x, "t_sw")) for x in q]) - np.median([abs(et(x, "t_red")) for x in q])))}
sw["recall_gain"] = {n: round(recall(E, "champ-Tswitch", c) - recall(E, "champ-Tred", c), 4) for c, n in ((2, "stained"), (3, "limited"))}
imp = any(isinstance(sw.get(n), dict) and sw[n].get("rel_improvement") is not None and sw[n]["rel_improvement"] >= 0.10 and sw[n]["diff_ci"] and sw[n]["diff_ci"][1] < 0 for n in ("limited", "sediment"))
res["switch"] = sw; res["SWITCH_USEFUL"] = bool(imp and max(sw["recall_gain"].values()) >= 0.05)
# direct attenuation model B (section 4)
bres = {}
for m in ("B-pure", "B-cal"):
    cov = res["regression"][m]["coverage"]
    sl = (recall(E, m, 2) + recall(E, m, 3)) / 2 - (recall(E, "A", 2) + recall(E, "A", 3)) / 2
    ci = lake_boot_diff(E, lambda rr, m=m: (recall(rr, m, 2) + recall(rr, m, 3)) / 2 - (recall(rr, "A", 2) + recall(rr, "A", 3)) / 2)
    common = [x for x in E if x["P"].get(m) is not None]
    dlog = lake_boot_diff(common, lambda rr, m=m: float(np.median([abs(x["P"][m] - x["y"]) for x in rr]) - np.median([abs(x["P"]["A"] - x["y"]) for x in rr])))
    ok = cov >= 0.85 and ((sl >= 0.05 and ci and ci[0] > 0) or (dlog and dlog[1] <= 0.010 and sl >= 0.05))
    bres[m] = {"coverage": cov, "stained_limited_gain": round(sl, 4), "gain_ci": ci, "median_log_diff_ci_vs_A": dlog, "useful": bool(ok)}
bres["qaa_refusals"] = dict(collections.Counter(x["q"].get("why", "ok") for x in E)); bres["qaa_reference_band"] = dict(collections.Counter(x["q"].get("ref") for x in E))
res["B"] = bres; res["ATTENUATION_USEFUL"] = any(v["useful"] for k, v in bres.items() if k in ("B-pure", "B-cal"))
# success criteria (section 7) and region-held-out
A = res["class"]["A"]
def success(m):
    c = res["class"][m]; v = res["vs_A"].get(m, {})
    ok1 = (c["stained"]["recall"] or 0) >= 0.45 and (c["stained"]["precision"] or 0) >= 0.40
    ok2 = (c["limited"]["recall"] or 0) >= 0.50 and (c["limited"]["precision"] or 0) >= 0.60
    ok3 = bool(v and v["stained_recall_ci"] and v["stained_recall_ci"][0] > 0 and v["limited_recall_ci"] and v["limited_recall_ci"][0] > 0)
    ok4 = all((c[n]["recall"] or 0) >= (A[n]["recall"] or 0) - 0.05 and (c[n]["precision"] or 0) >= (A[n]["precision"] or 0) - 0.05 for n in ("clear", "normal"))
    return {"1_stained": ok1, "2_limited": ok2, "3_ci": ok3, "4_clear_normal": ok4}
res["success_1to4"] = {m: success(m) for m in ["B-pure", "B-cal", "C-lin", "O1", "O2", "C-gbm"]}
# region-held-out for every candidate passing 1-4 (and for the best balanced accuracy one)
cand = [m for m, s in res["success_1to4"].items() if all(s.values())]
bestbal = max(["B-pure", "B-cal", "C-lin", "O1", "O2", "C-gbm"], key=lambda m: res["class"][m]["balanced_accuracy"])
check = sorted(set(cand + [bestbal, "A"]))
reg = {}
for x in E: x["CR"] = {}
for rg in range(5):
    tr = [x for x in E if x["region"] != rg]; te = [x for x in E if x["region"] == rg]
    if not te: continue
    P, C = fit_predict(tr, te)
    for i, x in enumerate(te):
        for m in check: x["CR"][m] = C[m][i]
for m in check:
    cr = class_metrics(true, [x["CR"].get(m) for x in E]); reg[m] = {n: cr[n]["recall"] for n in CLASSES}
    reg[m]["ratio_stained"] = (cr["stained"]["recall"] or 0) / (res["class"][m]["stained"]["recall"] or 1e-9)
    reg[m]["ratio_limited"] = (cr["limited"]["recall"] or 0) / (res["class"][m]["limited"]["recall"] or 1e-9)
res["region_heldout"] = reg
res["region_counts"] = dict(collections.Counter(x["region"] for x in E))
ORDER = ["A", "B-pure", "B-cal", "C-lin", "O1", "O2", "C-gbm"]
succ = [m for m in ORDER[1:] if m in cand and reg[m]["ratio_stained"] >= 0.8 and reg[m]["ratio_limited"] >= 0.8]
if succ:
    res["BEST"] = succ[0]; res["BEST_success"] = True
else:
    b = bestbal; v = res["vs_A"][b]
    res["BEST"] = b if (v["balanced_diff"] >= 0.03 and v["balanced_ci"] and v["balanced_ci"][0] > 0) else "A"; res["BEST_success"] = False
json.dump(res, open(f"{D13}/analysis/models13.json", "w"), indent=1, default=str)
json.dump([{k: x[k] for k in ("id", "lake", "set", "state", "region", "secchi", "c", "insitu_type", "platform", "sun_elev")} | {"P": x["P"], "C": x["C"], "F": x["F"], "q": {k: v for k, v in x["q"].items()}} for x in E],
          open(f"{D13}/analysis/preds13.json", "w"), default=str)
print(json.dumps({k: res[k] for k in ("BEST", "BEST_success", "CDOM_USEFUL", "SWITCH_USEFUL", "ATTENUATION_USEFUL")}, indent=1))
for m in MODELS_CLS:
    c = res["class"][m]; print(f"{m:14s} bal {c['balanced_accuracy']:.3f} ans {c['answered']:.2f} | " + " ".join(f"{n[:4]} {c[n]['recall']:.2f}/{(c[n]['precision'] or 0):.2f}" for n in CLASSES))
