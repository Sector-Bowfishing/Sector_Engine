#!/usr/bin/env python3
"""Depth Brain / terrain Question A, lake level: validate bathymetry-free predictors of 'how much of a lake is shallow' against REAL hypsometry.
Truth sets
  CWMS  : 33 USACE lakes, rel_per_ft = (dA/dz)/A from CWMS storage vs pool (research/lake-brain; top 15 ft).   (prior set, re-used)
  TWDB  : Texas hydrographic-survey area-capacity tables; S3 / S6 = share of the pool surface whose water depth is <= 3 / 6 ft  (A_pool - A_(pool-d))/A_pool,
          rel_per_ft_15 / rel_per_ft_5 = area change per ft of pool near the top.
Predictors (all bathymetry-free): shoreline slope from 3DEP (10-60 m and 30-100 m and 60-200 m slope; 200 m rise), polygon geometry, JRC GSW (SE tile only).
Outputs: docs/research/depth-brain/data/shallow_proxy_validation.json, shallow_proxy_lake_table.csv.  Run with the venv python."""
import gzip, json, re, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
from shapely.geometry import shape
sys.path.insert(0, str(Path(__file__).parent))
from terrain_features import lake_features, geom_features

REPO = Path(__file__).resolve().parents[2]
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
LBD = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data")
OUT = REPO / "docs/research/depth-brain/data"; OUT.mkdir(parents=True, exist_ok=True)
FT = 3.28084


def safe(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def rows():
    out = []
    eng = {f["properties"]["id"]: shape(f["geometry"]) for f in json.load(gzip.open("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/geometry/engine_polygons_599.geojson.gz"))["features"]}
    cw = json.load(open(LBD / "hypso_validation.json"))["table"]
    for r in cw:
        out.append(dict(set="CWMS", lake=r["lake"], npz=RAW / "dem" / (safe(r["lake"]) + ".npz"), geom=eng[r["lake"]], rel_per_ft=r["truth_rel_per_ft"], S3=np.nan, S6=np.nan, A_ref_ac=r["A_ref_ac"]))
    tt = json.load(open(RAW / "twdb_truth.json"))
    for k, v in tt.items():
        if v.get("status") != "ok": continue
        p = RAW / "twdb" / k / "pool_polygon.geojson"
        out.append(dict(set="TWDB", lake=k, npz=RAW / "dem" / (safe(k) + ".npz"), geom=shape(json.load(open(p))), rel_per_ft=v["rel_per_ft_5"], rel_per_ft_15=v["rel_per_ft_15"],
                        S1=v["S1"], S2=v["S2"], S3=v["S3"], S4=v["S4"], S6=v["S6"], S10=v["S10"], A_ref_ac=v["area_pool_ac"], pool_ft=v["pool_ft"], max_depth_ft=v["max_depth_ft"]))
    mp = OUT / "mn_dnr_truth.json"
    if mp.exists():
        for k, v in json.load(open(mp)).items():
            out.append(dict(set="MN", lake="MN_" + k, npz=RAW / "dem" / (safe("MN_" + k) + ".npz"), geom=shape(json.load(open(v["polygon"]))), rel_per_ft=np.nan,
                            S3=v["S3"], S6=v["S6"], S10=v["S10"], A_ref_ac=v["area_ac"], max_depth_ft=v["max_depth_ft"]))
    return out


def metrics(pred, truth, name=""):
    d = pd.DataFrame(dict(p=pred, t=truth)).replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) < 5: return dict(n=len(d))
    r = dict(n=int(len(d)), spearman=round(float(stats.spearmanr(d.p, d.t)[0]), 3))
    lp, lt = np.log10(d.p.clip(lower=1e-4)), np.log10(d.t.clip(lower=1e-4))
    r["pearson_log"] = round(float(np.corrcoef(lp, lt)[0, 1]), 3)
    r["log10_rmse"] = round(float(np.sqrt(((lp - lt) ** 2).mean())), 3)
    r["median_ratio"] = round(float(np.median(d.p / d.t)), 3)
    r["within_x2"] = round(float((np.abs(lp - lt) <= np.log10(2)).mean()), 3)
    r["mae"] = round(float((d.p - d.t).abs().mean()), 4); r["bias"] = round(float((d.p - d.t).mean()), 4)
    return r


def loo_calibrated(x, y):
    """log10 y = a + b log10 x, leave-one-out"""
    d = pd.DataFrame(dict(x=x, y=y)).replace([np.inf, -np.inf], np.nan).dropna(); d = d[(d.x > 0) & (d.y > 0)]
    lx, ly = np.log10(d.x.values), np.log10(d.y.values); pred = np.zeros(len(d))
    for i in range(len(d)):
        m = np.arange(len(d)) != i
        b, a = np.polyfit(lx[m], ly[m], 1); pred[i] = a + b * lx[i]
    return d.index, 10 ** pred, d.y.values


def auc(score, positive):
    s, p = np.asarray(score, float), np.asarray(positive, bool)
    if p.sum() == 0 or (~p).sum() == 0: return np.nan
    r = stats.rankdata(s); return float((r[p].sum() - p.sum() * (p.sum() + 1) / 2) / (p.sum() * (~p).sum()))


def main():
    recs = rows(); tab = []
    for r in recs:
        if not r["npz"].exists(): continue
        d = dict(np.load(r["npz"])); f = lake_features(d)
        if not f: continue
        g = geom_features(r["geom"])
        row = {k: v for k, v in r.items() if k not in ("npz", "geom")}; row.update(f); row.update(g)
        ft_p = g["perim_km"] * 1000 * FT; ft_a = g["area_km2"] * 1e6 * 10.7639
        row["P_dem"] = ft_p * f["run_per_ft_med"] / ft_a                      # prior proxy: rel change per ft (10-60 m slope)
        row["P_dem_30_100"] = ft_p * f["run_per_ft_med_30_100"] / ft_a
        row["P_dem_200"] = ft_p * f["run_per_ft_200"] / ft_a
        row["P_shape"] = g["perim_km"] / g["area_km2"]
        row["P_slope_neg"] = -f["slope_10_60_med"]
        row["P_flatshore"] = f["frac_lt2"] * g["perim_km"] / g["area_km2"]    # flat-shore perimeter density
        tab.append(row)
    T = pd.DataFrame(tab)
    T.to_csv(OUT / "shallow_proxy_lake_table.csv", index=False)
    res = {"n_rows": {s: int((T.set == s).sum()) for s in T.set.unique()}}
    preds = ["P_dem", "P_dem_30_100", "P_dem_200", "P_flatshore", "P_shape", "P_slope_neg", "frac_within_100m", "frac_narrow_300m"]
    # --- (1) rel_per_ft
    res["rel_per_ft"] = {}
    for s, D in list(T.groupby("set")) + [("POOLED", T)]:
        D = D[D.area_km2 >= 1] if s != "CWMS" else D
        res["rel_per_ft"][s] = {p: metrics(D[p], D.rel_per_ft) for p in preds if p.startswith("P_dem") or p in ("P_shape", "P_flatshore")}
        for p in ("P_slope_neg", "frac_within_100m", "frac_narrow_300m"):
            res["rel_per_ft"][s][p] = {"n": int(D[p].notna().sum()), "spearman": round(float(stats.spearmanr(D[p], D.rel_per_ft, nan_policy="omit")[0]), 3)}
        res["rel_per_ft"][s]["constant_median"] = metrics(np.full(len(D), D.rel_per_ft.median()), D.rel_per_ft)
    # --- (2) S3 / S6 on TWDB
    W = T[(T.set == "TWDB") & (T.area_km2 >= 1)].copy()
    res["twdb_lakes_used"] = int(len(W))
    res["twdb_truth_quantiles"] = {k: [round(float(W[k].quantile(q)), 3) for q in (.1, .25, .5, .75, .9)] for k in ("S3", "S6", "S10", "rel_per_ft")}
    res["shallow_share"] = {}
    for tgt, depth in (("S3", 3), ("S6", 6), ("S10", 10)):
        out = {}
        for p in ("P_dem", "P_dem_30_100", "P_dem_200"):
            raw = (W[p] * depth).clip(upper=1.0)
            out[p + "_raw"] = metrics(raw, W[tgt])
            idx, cal, y = loo_calibrated(W[p], W[tgt]); out[p + "_loo_loglinear"] = metrics(cal, y)
        for p in ("frac_within_100m", "frac_within_200m", "frac_narrow_300m", "P_shape"):
            out[p] = {"spearman": round(float(stats.spearmanr(W[p], W[tgt])[0]), 3)}
            idx, cal, y = loo_calibrated(W[p], W[tgt]); out[p + "_loo_loglinear"] = metrics(cal, y)
        out["constant_median"] = metrics(np.full(len(W), W[tgt].median()), W[tgt])
        res["shallow_share"][tgt] = out
    # --- (2b) transfer: calibrate on Texas (TWDB), predict Minnesota (MN DNR contours), S10 and S6
    M = T[T.set == "MN"].copy()
    if len(M) >= 4:
        tr_ = {}
        for tgt in ("S6", "S10"):
            for p in ("P_dem", "P_dem_30_100", "P_dem_200"):
                d_ = W[[p, tgt]].dropna(); d_ = d_[(d_[p] > 0) & (d_[tgt] > 0)]
                b, a = np.polyfit(np.log10(d_[p]), np.log10(d_[tgt]), 1)
                pred = 10 ** (a + b * np.log10(M[p].clip(lower=1e-3)))
                tr_[f"{p}->{tgt}"] = dict(metrics(pred, M[tgt]), coef=[round(float(a), 3), round(float(b), 3)])
            tr_[f"constant_TX_median->{tgt}"] = metrics(np.full(len(M), W[tgt].median()), M[tgt])
            tr_[f"spearman_P_dem_vs_{tgt}_MNonly"] = round(float(stats.spearmanr(M["P_dem"], M[tgt])[0]), 3)
            tr_[f"spearman_frac_within_100m_vs_{tgt}_MNonly"] = round(float(stats.spearmanr(M["frac_within_100m"], M[tgt])[0]), 3)
        res["transfer_TX_to_MN"] = tr_; res["mn_lakes"] = list(M.lake)
    # --- (3) class accuracy: broad-shallow lake = S3 in top tercile of the TWDB set
    cls = {}
    for tgt in ("S3", "S6"):
        thr = float(W[tgt].quantile(2 / 3)); pos = W[tgt] >= thr
        c = {"threshold": round(thr, 3), "n_pos": int(pos.sum()), "n": int(len(W))}
        for p in ("P_dem", "P_dem_30_100", "P_dem_200", "P_shape", "frac_within_100m", "frac_narrow_300m", "slope_10_60_med", "frac_lt2"):
            sc = -W[p] if p == "slope_10_60_med" else W[p]
            c[f"auc_{p}"] = round(auc(sc, pos), 3)
            top = sc >= sc.quantile(2 / 3); c[f"acc_top_tercile_{p}"] = round(float((top == pos).mean()), 3)
        cls[tgt] = c
    res["class_broad_shallow"] = cls
    # --- JRC GSW (SE tile only)
    gsw = json.load(open("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/context/gsw_features.json"))
    C = T[T.set == "CWMS"].copy(); C["gsw_fluct"] = C.lake.map(lambda l: gsw.get(l, {}).get("gsw_fluct_in_frac", np.nan)); C["gsw_ring"] = C.lake.map(lambda l: gsw.get(l, {}).get("gsw_fluct_ring_to_poly", np.nan))
    g_ = C.dropna(subset=["gsw_fluct"])
    res["gsw_vs_cwms"] = {"n": int(len(g_)), "lakes": list(g_.lake), "spearman_fluct_in_frac": round(float(stats.spearmanr(g_.gsw_fluct, g_.rel_per_ft)[0]), 3) if len(g_) > 4 else None,
                          "spearman_ring_to_poly": round(float(stats.spearmanr(g_.gsw_ring, g_.rel_per_ft)[0]), 3) if len(g_) > 4 else None,
                          "spearman_P_dem_same_lakes": round(float(stats.spearmanr(g_.P_dem, g_.rel_per_ft)[0]), 3) if len(g_) > 4 else None}
    (OUT / "shallow_proxy_validation.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1)[:6000])


if __name__ == "__main__":
    main()
