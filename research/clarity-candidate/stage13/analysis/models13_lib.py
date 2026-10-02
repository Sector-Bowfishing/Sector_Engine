"""Function library extracted from models13.py (no evaluation at import)."""
"""Stage 13 sections 3-7 (PREREGISTRATION_STAGE13.md): every candidate on E13 with whole-lake folds; class metrics;
bootstrap CIs vs benchmark A; CDOM ablation; red/NIR switch; region-held-out check. Writes models13.json, preds13.json."""
import json, math, collections, itertools, warnings
import numpy as np
from scipy.optimize import minimize
from sklearn.ensemble import HistGradientBoostingRegressor
from common13 import *
warnings.filterwarnings("ignore")
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
