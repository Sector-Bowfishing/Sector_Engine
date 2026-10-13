"""Upper bound: multi-band gradient-boosted classifier, leave-one-lake-out, shore-distance-matched weighting. Usage: 08_ml_lolo.py snoco|fwc"""
import sys, glob, json, numpy as np
from pathlib import Path
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
import importlib; M = importlib.import_module("04_metrics")
FEATS = ["NDVI","NDAVI","FAI","NDRE1","NDRE2","NDWI","NDII","NIR","SWIR","RED","GREEN","BLUE"]
mode = sys.argv[1]; res = {}
for variant in ["single", "composite"]:
    D = {}
    for p in sorted(glob.glob(str(ROOT/"out"/f"stack_{mode}_*.npz"))):
        nm = Path(p).stem.split(f"stack_{mode}_")[1]; d = M.load(p, mode, variant)
        if d is None: continue
        use, neg, cl = M.pixels(d, mode)
        X = np.stack([d["F"][k][use] for k in FEATS], 1); X = np.nan_to_num(X, nan=-9)
        D[nm] = dict(X=X, surf=cl["surface"][use], sub=cl["submerged"][use], neg=(neg & ~cl["surface"] & ~cl["submerged"])[use], dist=d["dist"][use])
    for g in ["surface", "submerged"]:
        key = "surf" if g == "surface" else "sub"; out = {}
        for held in D:
            tr = [k for k in D if k != held]
            def stack(ks):
                X = np.concatenate([D[k]["X"] for k in ks]); y = np.concatenate([D[k][key] for k in ks]); n = np.concatenate([D[k]["neg"] for k in ks])
                dist = np.concatenate([D[k]["dist"] for k in ks]); s = y | n; return X[s], y[s], dist[s]
            Xt, yt, dt_ = stack(tr); Xh, yh, dh = stack([held])
            if yt.sum() < 50 or yh.sum() < 15 or (~yh).sum() < 15: continue
            wt = M.match_weights(yt, dt_); wh = M.match_weights(yh, dh)
            clf = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.08, max_leaf_nodes=15).fit(Xt, yt, sample_weight=np.where(yt, 1, wt) * 1.0)
            pr = clf.predict_proba(Xh)[:, 1]
            out[held] = {"AUC_matched": round(float(roc_auc_score(yh, pr, sample_weight=wh)), 3), "AUC": round(float(roc_auc_score(yh, pr)), 3), "n_pos": int(yh.sum())}
        res[f"{variant}/{g}"] = out
json.dump(res, open(ROOT/"out"/f"ml_lolo_{mode}.json", "w"), indent=1); print(json.dumps(res, indent=1))
