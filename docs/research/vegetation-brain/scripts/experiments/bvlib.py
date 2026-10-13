"""Submerged-vegetation test helpers: feature set (incl. band ratios and Lyzenga depth-invariant), shore-matched weighted AUC."""
import numpy as np
from sklearn.metrics import roc_auc_score

def features(X, idx, none_mask=None):
    """X: (K,H,W) one scene (or composite) in IDX_ORDER. none_mask: pixels used to fit the Lyzenga ki/kj (bare-bottom/no-veg water)."""
    g = {k: X[i] for i, k in enumerate(idx)}
    B, G, R = g["BLUE"], g["GREEN"], g["RED"]
    f = {k: g[k] for k in ["NDVI", "NDAVI", "FAI", "NDRE1", "NDRE2", "NDWI", "GNDVI", "NDII", "NIR", "SWIR", "RED", "GREEN", "BLUE"]}
    with np.errstate(invalid="ignore", divide="ignore"):
        f["lnG_B"] = np.log(np.where(G > 0.001, G, np.nan) / np.where(B > 0.001, B, np.nan))
        f["lnR_B"] = np.log(np.where(R > 0.001, R, np.nan) / np.where(B > 0.001, B, np.nan))
        f["lnG_R"] = np.log(np.where(G > 0.001, G, np.nan) / np.where(R > 0.001, R, np.nan))
        # Lyzenga (1981) depth-invariant index via the covariance method (no depth needed): X_i = ln(L_i - L_deep)
        m = none_mask if none_mask is not None else np.isfinite(G)
        def dii(bi, bj):
            deep_i, deep_j = np.nanpercentile(bi[m], 1), np.nanpercentile(bj[m], 1)
            xi = np.log(np.maximum(bi - deep_i, 1e-4)); xj = np.log(np.maximum(bj - deep_j, 1e-4))
            ok = m & np.isfinite(xi) & np.isfinite(xj)
            if ok.sum() < 50: return np.full(bi.shape, np.nan, "float32")
            C = np.cov(xi[ok], xj[ok]); a = (C[0, 0] - C[1, 1]) / (2 * C[0, 1]); r = a + np.sign(a if a != 0 else 1) * np.sqrt(a * a + 1)
            return (xi - r * xj).astype("float32")
        f["DII_G_B"] = dii(G, B)       # green/blue pair
        f["DII_G_R"] = dii(G, R)       # green/red pair
    return f

ORIENT = {"NDWI": -1, "RED": -1, "BLUE": -1, "lnG_B": 1, "lnR_B": 1, "lnG_R": 1, "DII_G_B": 1, "DII_G_R": 1}

def match_weights(y, dist, edges=(0, 15, 30, 45, 60, 90, 150, 300, 1e9)):
    w = np.ones(len(y)); b = np.digitize(dist, edges[1:-1])
    for k in np.unique(b):
        m = b == k; npos = (y & m).sum(); nneg = (~y & m).sum()
        w[m & ~y] = (npos / nneg) if (nneg > 0 and npos > 0) else 0.0
    return w

def auc(v, y, w=None):
    ok = np.isfinite(v)
    if w is not None: ok &= w > 0
    v, y = v[ok], y[ok]; w = None if w is None else w[ok]
    if y.sum() < 10 or (~y).sum() < 10: return None
    return float(roc_auc_score(y, v, sample_weight=w))
