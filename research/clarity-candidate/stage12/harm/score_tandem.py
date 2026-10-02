"""Stage 12 Part 2 scoring, ACOLITE path (section 2 + addendum A). Per held-out pair: frozen P2 route on ACOLITE rhow
(B02-B05, B11) for S2A vs raw S2C, V-full, V-op (TOA, leave-one-pair-out) and V-rho_w (rhow-level fit on the other
pairs' A vs raw C pixels, same form and trimming as section 2). Flip rate = share of pixels whose decision differs;
mean over pairs (equal weight). Residual band ratios/differences. Optional: an engine's class decision (--engine).
Writes harm/score_tandem.json (and adds the Sen2Cor-path results from validate_npz.json)."""
import json, math, sys, glob, os, collections, numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage10/frozen"); sys.path.insert(0, f"{S}/stage12/analysis")
import p2 as P2
BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12"]
P = {os.path.basename(f)[:-4]: dict(np.load(f)) for f in sorted(glob.glob(f"{S}/stage12/harm/tandem_acolite/*.npz"))}
def get(d, tag): return {b: d[f"{tag}_{b}"].astype("float64") for b in BANDS if f"{tag}_{b}" in d}
def fit(pairs):
    coef = {}
    for b in BANDS:
        Xs, ys, ws = [], [], []
        for p in pairs:
            A, C = get(P[p], "A"), get(P[p], "C")
            if b not in A or b not in C: continue
            cols = [C[b], np.ones_like(C[b])] + ([C["B06"] - C["B04"]] if b == "B05" else [])
            X = np.stack(cols, 1); y = A[b]; ok = np.all(np.isfinite(X), 1) & np.isfinite(y)
            d = (y - C[b])[ok]
            if d.size < 50: continue
            med = np.median(d); rsd = 1.4826 * np.median(np.abs(d - med)) or 1e-6
            keep = np.zeros_like(ok); keep[np.flatnonzero(ok)] = np.abs(d - med) <= 5 * rsd
            Xs.append(X[keep]); ys.append(y[keep]); ws.append(np.full(keep.sum(), 1.0 / keep.sum()))
        if not Xs: continue
        X, y, w = np.vstack(Xs), np.concatenate(ys), np.concatenate(ws); sw = np.sqrt(w)
        be = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
        coef[b] = {"g": float(be[0]), "o": float(be[1]), **({"k": float(be[2])} if b == "B05" else {})}
    return coef
def apply(C, coef):
    out = dict(C)
    for b, c in coef.items():
        v = c["g"] * C[b] + c["o"]
        if b == "B05": v = v + c["k"] * (C["B06"] - C["B04"])
        out[b] = v
    return out
def p2path(D, i, sun):
    raw = {"blue": float(D["B02"][i]), "green": float(D["B03"][i]), "red": float(D["B04"][i]), "re1": float(D["B05"][i])}
    if not all(math.isfinite(v) for v in raw.values()): return None
    sw = float(D["B11"][i]) if "B11" in D and math.isfinite(D["B11"][i]) else 0.0
    return P2.route(raw, sun, sw)["path"]
ENGINE = None
if "--engine" in sys.argv:
    import engine12 as ENG            # written after Part 4 freezes: ENG.classify(rho_dict, sun) -> (class, ft)
    ENGINE = ENG
def resid(A, X):
    r = {}
    for b in BANDS:
        if b not in A or b not in X: continue
        ok = np.isfinite(A[b]) & np.isfinite(X[b]) & (np.abs(A[b]) > 0.0005)
        if ok.sum() < 20: continue
        r[b] = {"ratio": float(np.median(X[b][ok] / A[b][ok])), "diff": float(np.median(X[b][ok] - A[b][ok]))}
    return r
out = {"pairs": {}}
for p in P:
    d = P[p]; sun = float(d["sun"][0])
    A, C, F, O = get(d, "A"), get(d, "C"), get(d, "F"), get(d, "O")
    R = apply(C, fit([q for q in P if q != p]))
    n = len(A["B04"]); rec = {"n": n, "water_px": int(d["water_px"][0]), "flip": {}, "resid": {}, "engine_flip": {}, "engine_dft": {}}
    pa = [p2path(A, i, sun) for i in range(n)]
    for tag, X in (("raw", C), ("vfull", F), ("vop", O), ("vrhow", R)):
        px = [p2path(X, i, sun) for i in range(n)]
        ok = [i for i in range(n) if pa[i] is not None and px[i] is not None]
        rec["flip"][tag] = float(np.mean([pa[i] != px[i] for i in ok])) if ok else None
        rec["resid"][tag] = resid(A, X)
        if ENGINE:
            ea = [ENGINE.classify({b: float(A[b][i]) for b in A}, sun) for i in range(n)]
            ex = [ENGINE.classify({b: float(X[b][i]) for b in X}, sun) for i in range(n)]
            rec["engine_flip"][tag] = float(np.mean([ea[i][0] != ex[i][0] for i in range(n)])) if n else None
            dd = [ex[i][1] - ea[i][1] for i in range(n) if ea[i][1] is not None and ex[i][1] is not None]
            rec["engine_dft"][tag] = float(np.median(np.abs(dd))) if dd else None
    out["pairs"][p] = rec
    print(p, {k: (round(v, 3) if v is not None else None) for k, v in rec["flip"].items()}, rec.get("engine_flip"), flush=True)
for tag in ("raw", "vfull", "vop", "vrhow"):
    v = [r["flip"][tag] for r in out["pairs"].values() if r["flip"][tag] is not None]
    out[f"mean_flip_{tag}"] = float(np.mean(v)) if v else None; out[f"median_flip_{tag}"] = float(np.median(v)) if v else None
    if ENGINE:
        e = [r["engine_flip"][tag] for r in out["pairs"].values() if r["n"] > 0]
        out[f"engine_mean_flip_{tag}"] = float(np.mean(e)); out[f"engine_median_abs_dft_{tag}"] = float(np.median([r["engine_dft"][tag] for r in out["pairs"].values() if r["n"] > 0 and r["engine_dft"][tag] is not None]))
    out[f"resid_{tag}"] = {b: {"ratio": float(np.median([r["resid"][tag][b]["ratio"] for r in out["pairs"].values() if b in r["resid"][tag]])),
                               "diff": float(np.median([r["resid"][tag][b]["diff"] for r in out["pairs"].values() if b in r["resid"][tag]]))} for b in BANDS
                           if any(b in r["resid"][tag] for r in out["pairs"].values())}
mo, mr = out["mean_flip_vop"], out["mean_flip_vrhow"]
out["adopted_operational_method"] = "vrhow" if (mr is not None and (mo is None or mr <= mo + 0.005)) else "vop"
out["production_vrhow_coef"] = fit(list(P))
json.dump(out, open(f"{S}/stage12/harm/score_tandem.json" if not ENGINE else f"{S}/stage12/harm/score_tandem_engine.json", "w"), indent=1)
print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in out.items() if k.startswith(("mean_flip", "median_flip", "engine_", "adopted"))})
