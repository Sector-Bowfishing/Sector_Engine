"""Metrics for S2 indices vs ground truth. Usage: 04_metrics.py snoco|fwc"""
import sys, json, glob, datetime as dt, numpy as np, collections
from pathlib import Path
from scipy.ndimage import distance_transform_edt, binary_dilation
from sklearn.metrics import roc_auc_score
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); import s2lib
IDX = s2lib.IDX_ORDER
KEY = ["NDVI","NDAVI","FAI","NDRE1","NDRE2","NDWI","NDII","NIR","SWIR"]
CLS = {"snoco": {"surface": ["floating_leaf"], "submerged": ["submerged_assemblage","arrowhead"]},
       "fwc":   {"surface": ["floating","emergent"], "submerged": ["submersed"]}}
SECTOR = lambda f: (f["NDVI_sector"] >= 0.30)
SECTOR_FAI = lambda f: (f["NDVI_sector"] >= 0.30) | (f["FAI_sector"] > 0.005)

def prf(pred, truth, w=None):
    w = np.ones(len(truth)) if w is None else w
    tp = (w*(pred & truth)).sum(); fp = (w*(pred & ~truth)).sum(); fn = (w*(~pred & truth)).sum()
    p = tp / max(1, tp + fp); r = tp / max(1, tp + fn); f1 = 2*p*r/max(1e-9, p+r); iou = tp / max(1, tp+fp+fn)
    return dict(P=round(float(p),3), R=round(float(r),3), F1=round(float(f1),3), IoU=round(float(iou),3))

def best_thr(v, y, w=None):
    """threshold t maximizing (weighted) F1 for rule v >= t"""
    w = np.ones(len(y)) if w is None else w
    o = np.argsort(-v); ys = y[o]; ws = w[o]
    tp = np.cumsum(ws*ys); kk = np.cumsum(ws)
    f1 = 2*tp / (kk + (ws*ys).sum()); i = int(np.nanargmax(f1)); return float(v[o][i])

def match_weights(y, dist, edges=(0,15,30,45,60,90,150,300,1e9)):
    """weights so that negatives follow the positives' distance-to-shore histogram (positives weight 1)"""
    w = np.ones(len(y)); b = np.digitize(dist, edges[1:-1])
    for k in np.unique(b):
        m = b == k; npos = (y & m).sum(); nneg = (~y & m).sum()
        w[m & ~y] = (npos / nneg) if nneg > 0 else 0.0
        if npos == 0: w[m & ~y] = 0.0
    return w

MAX3 = "--max3" in sys.argv   # 3x3 max-filter the veg-direction indices (tolerates ~10 m GPS error of survey points)
def load(path, mode, variant):
    z = np.load(path, allow_pickle=True)
    X, V, dates, clear = z["X"], z["V"], z["dates"], z["clear"]
    survey = dt.date.fromisoformat(str(z["survey"]))
    dd = np.array([(dt.date.fromisoformat(str(d)) - survey).days for d in dates])
    lab = {k[4:]: z[k] for k in z.files if k.startswith("lab_")}
    lake = z["lake"]
    ok = clear >= 0.75
    if not ok.any(): return None
    if variant == "single":
        i = np.where(ok)[0][np.argmin(np.abs(dd[ok]))]
        F = {k: X[i, j] for j, k in enumerate(IDX)}; valid = V[i]; info = f"{dates[i]} (dt={dd[i]:+d} d)"
    elif variant == "composite":  # max over all clear scenes (+-45 d ~ 3 months); per-pixel valid only
        F = {}; valid = np.zeros(lake.shape, bool)
        for j, k in enumerate(IDX):
            A = np.where(V[ok], X[ok, j], np.nan)
            if k in ("NDVI","NDAVI","FAI","FAI_sector","NDVI_sector","NDRE1","NDRE2","NDRE3","RE_slope","GNDVI","NIR"): F[k] = np.nanmax(A, 0)
            elif k in ("NDWI","NDII","SWIR","RED","GREEN","BLUE"): F[k] = np.nanmedian(A, 0)  # not a veg-peak index
        valid = np.isfinite(F["NDVI"]); info = f"{ok.sum()} scenes {dates[ok][0]}..{dates[ok][-1]}"
    if MAX3:
        from scipy.ndimage import maximum_filter, minimum_filter
        for k in list(F):
            a = F[k]; fn = minimum_filter if k == "NDWI" else maximum_filter
            if k in ("RED","GREEN","BLUE","SWIR"): continue
            b = fn(np.nan_to_num(a, nan=-9 if k != "NDWI" else 9), size=3); b[~np.isfinite(a)] = np.nan; F[k] = b
    return dict(F=F, valid=valid, lab=lab, lake=lake, dist=z["dist"], dlab=z["dlab"] if "dlab" in z.files else None, info=info, survey=str(survey), nscenes=int(ok.sum()))

def pixels(d, mode, tight_neg_m=20, core=False):
    """-> feature dict (flat), class dict name->bool, universe mask info"""
    lab = d["lab"]; any_lab = np.zeros(d["lake"].shape, bool)
    for v in lab.values(): any_lab |= v
    distlab = d["dlab"] if d["dlab"] is not None else distance_transform_edt(~any_lab) * 10
    neg = d["lake"] & (distlab >= tight_neg_m)
    classes = {}
    for g, names in CLS[mode].items():
        m = np.zeros(d["lake"].shape, bool)
        for n in names:
            if n in lab: m |= lab[n]
        classes[g] = m
    # pixels labelled both surface & submerged: surface wins for the surface class, dropped from submerged
    if "surface" in classes and "submerged" in classes: classes["submerged"] &= ~classes["surface"]
    if core:  # polygon interiors only (>=1 px from unlabeled)
        for g in classes: classes[g] = classes[g] & ~binary_dilation(~(classes[g]) , iterations=1) if mode == "snoco" else classes[g]
    use = d["valid"] & (neg | classes["surface"] | classes["submerged"])
    return use, neg, classes

def run(mode):
    files = sorted(glob.glob(str(ROOT / "out" / f"stack_{mode}_*.npz")))
    res = {}; pool = {}
    for variant in ["single", "composite"]:
        pool[variant] = {"F": collections.defaultdict(list), "y": collections.defaultdict(list), "lake": [], "dist": []}
        for p in files:
            nm = Path(p).stem.split(f"stack_{mode}_")[1]
            d = load(p, mode, variant)
            if d is None: print("skip (no clear scene)", nm); continue
            use, neg, cl = pixels(d, mode)
            n_neg = int((neg & d["valid"]).sum())
            row = {"info": d["info"], "survey": d["survey"], "n_neg": n_neg, "n_pos": {g: int((m & d["valid"]).sum()) for g, m in cl.items()}, "auc": {}}
            for g in cl:
                sel = d["valid"] & (neg | cl[g])
                y = cl[g][sel]
                if y.sum() < 15 or (~y).sum() < 15: continue
                for k in KEY:
                    v = d["F"][k][sel]; ok = np.isfinite(v)
                    if k in ("NDWI",): v = -v  # water index: lower = more vegetation
                    wm_ = match_weights(y, d["dist"][sel])
                    row["auc"].setdefault(g, {})[k] = [round(float(roc_auc_score(y[ok], v[ok])), 3), round(float(roc_auc_score(y[ok], v[ok], sample_weight=wm_[ok])), 3)]
            # sector rule on this lake
            row["sector"] = {}
            for g in cl:
                sel = d["valid"] & (neg | cl[g]); y = cl[g][sel]
                if y.sum() < 15: continue
                row["sector"][g] = {"ndvi>=0.30": prf(SECTOR(d["F"])[sel], y), "ndvi>=0.30|FAI>0.005": prf(SECTOR_FAI(d["F"])[sel], y)}
            res.setdefault(nm, {})[variant] = row
            # pool
            for k in IDX: pool[variant]["F"][k].append(d["F"][k][use])
            for g in cl: pool[variant]["y"][g].append(cl[g][use])
            pool[variant].setdefault("sublist", []).append({n: (d["lab"][n] & ~(cl["surface"] if n in CLS[mode]["submerged"] else np.zeros_like(cl["surface"])))[use] for n in d["lab"]})
            pool[variant]["y"]["neg"].append((neg & ~cl["surface"] & ~cl["submerged"])[use])
            pool[variant]["lake"].append(np.full(int(use.sum()), nm)); pool[variant]["dist"].append(d["dist"][use])
    # pooled metrics
    pooled = {}
    for variant in pool:
        P = pool[variant]
        if not P["lake"]: continue
        F = {k: np.concatenate(v) for k, v in P["F"].items()}; Y = {k: np.concatenate(v) for k, v in P["y"].items()}
        lakes = np.concatenate(P["lake"]); dist = np.concatenate(P["dist"])
        out = {"n": int(len(lakes)), "classes": {}, "subclass": {}}
        names = sorted({n for dct in P["sublist"] for n in dct})
        for n in names:
            ys = np.concatenate([dct.get(n, np.zeros(len(dct[next(iter(dct))]) if dct else 0, bool)) for dct in P["sublist"]]); sel = ys | Y["neg"]
            if ys.sum() < 15: continue
            wm = match_weights(ys[sel], dist[sel]); r = {"n_pos": int(ys.sum())}
            for k in ["NDVI", "NDAVI", "FAI", "NDRE1"]:
                v = np.nan_to_num(F[k][sel], nan=-9); r["AUC_matched_" + k] = round(float(roc_auc_score(ys[sel], v, sample_weight=wm)), 3)
            sec = np.nan_to_num(F["NDVI_sector"], nan=0) >= 0.30; r["recall_sector_ndvi>=0.30"] = round(float(sec[ys].mean()), 3)
            sf = sec | (np.nan_to_num(F["FAI_sector"], nan=0) > 0.005); r["recall_sector_ndvi|fai"] = round(float(sf[ys].mean()), 3)
            out["subclass"][n] = r
        negm = Y["neg"]; sec = np.nan_to_num(F["NDVI_sector"], nan=0) >= 0.30; sf = sec | (np.nan_to_num(F["FAI_sector"], nan=0) > 0.005)
        out["sector_FPR_on_background"] = {"ndvi>=0.30": round(float(sec[negm].mean()), 4), "ndvi|fai": round(float(sf[negm].mean()), 4), "n_bg": int(negm.sum())}
        for g in ["surface", "submerged"]:
            sel = Y[g] | Y["neg"]; y = Y[g][sel]
            if y.sum() < 20: continue
            o = {"n_pos": int(y.sum()), "n_neg": int((~y).sum()), "prev": round(float(y.mean()), 4), "idx": {}}
            ds0 = dist[sel]; wm = match_weights(y, ds0)
            for k in KEY:
                v = F[k][sel]; sign = -1 if k == "NDWI" else 1
                ok = np.isfinite(v); v = sign * v
                auc = roc_auc_score(y[ok], v[ok]); aucm = roc_auc_score(y[ok], v[ok], sample_weight=wm[ok])
                t = best_thr(v[ok], y[ok]); m = prf((v >= t) & ok, y)
                tm = best_thr(v[ok], y[ok], wm[ok]); mm_ = prf((v >= tm) & ok, y, wm)
                ll = lakes[sel]; pr = np.zeros(len(y), bool)
                for L in np.unique(ll):
                    tr = (ll != L) & ok; te = (ll == L) & ok
                    if y[tr].sum() < 20 or y[te].sum() == 0: continue
                    tt = best_thr(v[tr], y[tr], wm[tr]); pr[te] = v[te] >= tt
                o["idx"][k] = {"AUC": round(float(auc), 3), "AUC_matched": round(float(aucm), 3), "thr_bestF1": round(float(sign * t), 4), **m,
                               "matched": {"thr": round(float(sign * tm), 4), **mm_}, "LOLO_matched": prf(pr, y, wm)}
            for nmr, rule in [("Sector NDVI>=0.30", SECTOR), ("Sector NDVI>=0.30 | FAI>0.005", SECTOR_FAI)]:
                pr = np.nan_to_num(rule({k: F[k][sel] for k in ("NDVI_sector", "FAI_sector")}), nan=0).astype(bool)
                o.setdefault("sector", {})[nmr] = {**prf(pr, y), "matched": prf(pr, y, wm)}
            # recall of sector rule by distance from shore
            bins = [0, 30, 60, 120, 1e9]; r = {}
            Fs = {k: F[k][sel] for k in ("NDVI_sector",)}; ds = dist[sel]
            for a, b in zip(bins[:-1], bins[1:]):
                mm = (ds >= a) & (ds < b); pos = mm & y
                if pos.sum() >= 10: r[f"{int(a)}-{int(b) if b < 1e8 else 'inf'} m"] = {"n_pos": int(pos.sum()), "recall_sector": round(float((Fs["NDVI_sector"][pos] >= 0.30).mean()), 3), "recall_sector_nanTo0": None,
                    "auc_NDVI": round(float(roc_auc_score(y[mm], np.nan_to_num(F["NDVI"][sel][mm]))), 3) if (mm & ~y).sum() > 10 else None}
            o["by_shore_dist"] = r
            out["classes"][g] = o
        pooled[variant] = out
    sfx = "_max3" if MAX3 else ""
    json.dump({"per_lake": res, "pooled": pooled}, open(ROOT / "out" / f"metrics_{mode}{sfx}.json", "w"), indent=1)
    print("wrote", f"metrics_{mode}{sfx}.json")

if __name__ == "__main__":
    run([a for a in sys.argv[1:] if not a.startswith("--")][0])
