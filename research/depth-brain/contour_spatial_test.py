#!/usr/bin/env python3
"""Depth Brain / contour truth, task 4(d): WITHIN-lake spatial test on fleet lakes with REAL contours (this thread's rasters) AND 3DEP shoreline profiles (terrain thread, read-only).
Question: does distance-from-shore + shoreline slope predict WHERE the 0-6 ft zone is?
  T1  segment level (~500 m of shoreline): Spearman(shoreline slope, truth) over segments, truth = (i) share of the 0-100 m near-shore band with depth <= 6 ft, (ii) median shore->6 ft width
      (distance from the shore point to the nearest >= 6 ft cell).  Pooled over lakes and per lake (every lake with >= 8 segments is reported; no lake dropped).
  T2  mask level: predicted shallow zone = water within W of shore, W = const (fit leave-one-lake-out for max IoU) vs W = 6 ft / tan(slope_10_60) clipped (slope-aware) vs random-segment slopes;
      truth = depth <= 6 ft.  IoU and AUC.
  T3  cell level ranking: AUC(depth <= 6 ft) of distance-only vs distance+slope (logistic fit on the other lakes, leave-one-lake-out).
Output data/contour_spatial_test.json."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats, ndimage
from scipy.spatial import cKDTree
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).parent))
from terrain_stats import Logit

REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/depth-brain/data"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
T = RAW / "depth-brain/terrain"
GR = RAW / "depth-brain/contour/grids"
RNG = np.random.default_rng(3)
MN = {"MN_Gull": "Gull Lake|MN", "MN_Bemidji": "Lake Bemidji|MN", "MN_Minnetonka": "Lake Minnetonka|MN", "MN_Winnibigoshish": "Lake Winnibigoshish|MN", "MN_Leech": "Leech Lake|MN",
      "MN_Mille_Lacs": "Mille Lacs Lake|MN", "MN_Otter_Tail": "Otter Tail Lake|MN", "MN_White_Bear": "White Bear Lake|MN", "MN_Pepin": "Lake Pepin|MN"}


def safe(s): return "".join(ch if ch.isalnum() else "_" for ch in s)


def auc(score, pos):
    pos = np.asarray(pos, bool); s = np.asarray(score, float)
    ok = np.isfinite(s); s, pos = s[ok], pos[ok]
    if pos.sum() < 20 or (~pos).sum() < 20: return np.nan
    r = stats.rankdata(s); return float((r[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def load(lid, src):
    g = np.load(GR / f"{safe(lid)}__{src}.npz"); depth = g["depth_ft"].astype(np.float32)
    a, b, c, d_, e, f = g["transform"]; cell = float(g["cell"])
    water = np.isfinite(depth)
    dist = ndimage.distance_transform_edt(water) * cell
    deep6 = water & (depth >= 6)
    d6 = ndimage.distance_transform_edt(~deep6) * cell if deep6.any() else np.full(depth.shape, np.nan)
    return dict(depth=depth, water=water, dist=dist, d6=d6, a=a, c=c, e=e, f=f, cell=cell)


def seg_feats(d, seg_len=500.0):
    """own segment features (works for the sparse fleet profile with offsets [10, 60] and for the dense 10-offset profile)."""
    offs = [int(o) for o in d["offs"]]; ix = {o: i for i, o in enumerate(offs)}
    z = d["z"].astype(float); ok = np.isfinite(z).all(axis=1) & (z > -100).all(axis=1)
    ring, sarc = d["ring"], d["s"]
    seg = np.full(len(z), -1); n = 0
    for r in np.unique(ring):
        m = (ring == r) & ok
        if not m.any(): continue
        k = np.floor(sarc[m] / seg_len).astype(int); u, inv = np.unique(k, return_inverse=True)
        seg[np.where(m)[0]] = n + inv; n += len(u)
    sl = lambda zz, a, b: np.degrees(np.arctan((zz[:, ix[b]] - zz[:, ix[a]]) / (b - a)))
    tab = {}
    for g in range(n):
        m = seg == g
        if m.sum() < 2: continue
        zz = z[m]; row = dict(seg=g, n=int(m.sum()), slope_10_60=float(np.median(sl(zz, 10, 60))))
        row["slope_30_100"] = float(np.median(sl(zz, 30, 100))) if 30 in ix and 100 in ix else np.nan
        row["slope_60_200"] = float(np.median(sl(zz, 60, 200))) if 60 in ix and 200 in ix else np.nan
        row["rise200"] = float(np.median(zz[:, ix[200]] - zz[:, ix[10]])) if 200 in ix else np.nan
        tab[g] = row
    return tab, seg


def dem_file(lid):
    inv = {v: k for k, v in MN.items()}
    if lid in inv and (T / "dem_dense" / f"{inv[lid]}.npz").exists(): return T / "dem_dense" / f"{inv[lid]}.npz"
    p = T / "dem_fleet" / f"{safe(lid)}.npz"
    return p if p.exists() else None


def run_lake(lid, src):
    L = load(lid, src); f = dem_file(lid)
    d = dict(np.load(f))
    tr = Transformer.from_crs(4326, 5070, always_xy=True); px, py = tr.transform(d["lon"], d["lat"])
    tab, segid = seg_feats(d, 500.0)
    valid = segid >= 0
    if valid.sum() < 30: return None
    tree = cKDTree(np.column_stack([px, py])[valid]); idxmap = np.nonzero(valid)[0]
    H, W = L["depth"].shape
    rows_, cols_ = np.nonzero(L["water"])
    xs = L["c"] + (cols_ + .5) * L["a"]; ys = L["f"] + (rows_ + .5) * L["e"]
    dd, ni = tree.query(np.column_stack([xs, ys]))
    cell_seg = segid[idxmap[ni]]
    depth = L["depth"][rows_, cols_]; dist = L["dist"][rows_, cols_]
    sp_ = cKDTree(np.column_stack([px, py])[valid]).query(np.column_stack([px, py])[valid], k=2)[0][:, 1]
    reach = max(400.0, 1.5 * float(np.median(sp_)))
    near = (dist <= 100) & (dd <= reach)
    # shore point -> truth width (distance to >=6 ft cell) sampled at the shore points' raster cell
    pcol = np.floor((px - L["c"]) / L["a"]).astype(int); prow = np.floor((py - L["f"]) / L["e"]).astype(int)
    w6 = np.full(len(px), np.nan)
    okp = (pcol >= 0) & (pcol < W) & (prow >= 0) & (prow < H)
    w6[okp] = L["d6"][prow[okp], pcol[okp]]
    # shore points lie on the polygon edge (outside/inside by < 1 cell): fall back to nearest water cell via max over a 3x3 neighbourhood
    segrows = []
    for sid, s in tab.items():
        m = near & (cell_seg == sid)
        if m.sum() < 30: continue
        mm = (segid == sid) & np.isfinite(w6)
        segrows.append(dict(seg=sid, n=int(m.sum()), sh6=float((depth[m] <= 6).mean()), sh3=float((depth[m] <= 3).mean()), w6_med=float(np.median(w6[mm])) if mm.sum() else np.nan,
                            slope_10_60=s["slope_10_60"], slope_30_100=s["slope_30_100"], slope_60_200=s["slope_60_200"], rise200=s["rise200"]))
    r = dict(lakeId=lid, src=src, n_seg=len(segrows), reach_m=reach, lake_sh6=float((depth <= 6).mean()))
    if len(segrows) >= 8:
        S = pd.DataFrame(segrows)
        for p in ("slope_10_60", "slope_30_100", "slope_60_200", "rise200"):
            if S[p].notna().sum() < 8: continue
            if S.sh6.std() > 1e-6: r[f"sp_{p}_vs_sh6"] = float(stats.spearmanr(S[p], S.sh6)[0])
            if S.w6_med.notna().sum() >= 8 and S.w6_med.std() > 1e-6 and S[p].notna().sum() >= 8: r[f"sp_{p}_vs_w6"] = float(stats.spearmanr(S[p], S.w6_med, nan_policy="omit")[0])
    slope_cell = np.array([tab.get(s, {}).get("slope_10_60", np.nan) for s in cell_seg])
    return r, segrows, (dist, slope_cell, depth)


def iou(pred, truth): return float((pred & truth).sum() / max((pred | truth).sum(), 1))


def main():
    t = pd.read_csv(D / "contour_truth_lakes.csv"); t = t[t.tier.isin(["A", "B"]) & (t.is_duplicate == 0) & (t.method == "contour_interp")]
    res, segall, cells = [], [], {}
    for r in t.itertuples():
        if dem_file(r.lakeId) is None or not (GR / f"{safe(r.lakeId)}__{r.src}.npz").exists(): continue
        try: out = run_lake(r.lakeId, r.src)
        except Exception as e:
            print(r.lakeId, "ERR", repr(e)[:150]); continue
        if out is None: continue
        rr, rows, arr = out
        rr["tier"] = r.tier; res.append(rr); cells[r.lakeId] = arr
        for x in rows: x["lakeId"] = r.lakeId; segall.append(x)
        print(r.lakeId, rr["n_seg"], round(rr.get("sp_slope_10_60_vs_sh6", np.nan), 3), flush=True)
    S = pd.DataFrame(segall)
    summ = {"n_lakes": len(res), "lakes": [r["lakeId"] for r in res], "n_segments": int(len(S))}
    # T1 pooled and per-lake
    def agg(col):
        v = np.array([r.get(col, np.nan) for r in res], float); v = v[np.isfinite(v)]
        return dict(n=int(len(v)), mean=float(v.mean()) if len(v) else None, median=float(np.median(v)) if len(v) else None, n_neg=int((v < 0).sum()), n_pos=int((v > 0).sum()),
                    ci_mean=[float(np.percentile([RNG.choice(v, len(v)).mean() for _ in range(2000)], q)) for q in (2.5, 97.5)] if len(v) > 3 else None)
    summ["T1_per_lake_spearman"] = {c: agg(c) for c in ("sp_slope_10_60_vs_sh6", "sp_slope_30_100_vs_sh6", "sp_slope_60_200_vs_sh6", "sp_rise200_vs_sh6", "sp_slope_10_60_vs_w6", "sp_slope_30_100_vs_w6", "sp_slope_60_200_vs_w6", "sp_rise200_vs_w6")}
    # pooled within-lake (segments rank-normalised per lake so only within-lake variation counts)
    for tgt in ("sh6", "w6_med"):
        for p in ("slope_10_60", "slope_30_100", "rise200"):
            Z = S.dropna(subset=[tgt, p]).copy()
            Z["pr"] = Z.groupby("lakeId")[p].rank(pct=True); Z["tr"] = Z.groupby("lakeId")[tgt].rank(pct=True)
            summ.setdefault("T1_pooled_within_lake_rank_corr", {})[f"{p}_vs_{tgt}"] = dict(n=int(len(Z)), spearman=float(stats.spearmanr(Z.pr, Z.tr)[0]))
    # T2 / T3
    keys = list(cells)
    def sample(k, n=60000):
        dist, sl, dep = cells[k]; m = np.isfinite(sl) & (dist <= 300); idx = np.nonzero(m)[0]
        if len(idx) > n: idx = RNG.choice(idx, n, replace=False)
        return dist[idx], sl[idx], dep[idx]
    sam = {k: sample(k) for k in keys}
    Ws = np.array([15, 30, 45, 60, 90, 120, 180, 250, 350.0])
    t2, t3 = [], {}
    ff = lambda d, s: np.column_stack([np.log1p(d), np.log1p(np.clip(s, 0, None)), np.log1p(d) * np.log1p(np.clip(s, 0, None))])
    for k in keys:
        d, s_, z = sam[k]; truth = z <= 6
        if truth.sum() < 50 or (~truth).sum() < 50: continue
        tr = [j for j in keys if j != k]
        # best constant W on training lakes
        best = max(Ws, key=lambda W: np.mean([iou(sam[j][0] <= W, sam[j][2] <= 6) for j in tr]))
        # slope-aware: W = a*6ft/tan(slope); a fit on training lakes
        def pred_slope(dd, ss, a): return dd <= np.clip(a * 6 * 0.3048 / np.tan(np.radians(np.clip(ss, 0.3, 60))), 10, 600)
        As = np.array([0.25, 0.5, 1, 2, 4, 8.0])
        bestA = max(As, key=lambda a: np.mean([iou(pred_slope(sam[j][0], sam[j][1], a), sam[j][2] <= 6) for j in tr]))
        shuf = RNG.permutation(s_)
        t2.append(dict(lakeId=k, truth_frac=float(truth.mean()), iou_const=iou(d <= best, truth), W=float(best), iou_slope=iou(pred_slope(d, s_, bestA), truth), a=float(bestA),
                       iou_shuffled_slope=iou(pred_slope(d, shuf, bestA), truth)))
        D_ = np.concatenate([sam[j][0] for j in tr]); S_ = np.concatenate([sam[j][1] for j in tr]); Z_ = np.concatenate([sam[j][2] for j in tr])
        row = {}
        for thr in (3, 6, 10):
            y = Z_ <= thr; yk = z <= thr
            m1 = Logit().fit(np.column_stack([np.log1p(D_)]), y); m2 = Logit().fit(ff(D_, S_), y)
            row[f"d{thr}"] = dict(auc_dist=auc(m1.decision_function(np.column_stack([np.log1p(d)])), yk), auc_dist_plus_slope=auc(m2.decision_function(ff(d, s_)), yk), auc_slope_only=auc(-s_, yk))
        t3[k] = row
    T2 = pd.DataFrame(t2)
    summ["T2_masks_le6ft"] = dict(n=int(len(T2)), iou_const_mean=float(T2.iou_const.mean()), iou_slope_mean=float(T2.iou_slope.mean()), iou_shuffled_slope_mean=float(T2.iou_shuffled_slope.mean()),
                                  n_lakes_slope_better_than_const=int((T2.iou_slope > T2.iou_const).sum()), n_lakes_slope_better_than_shuffled=int((T2.iou_slope > T2.iou_shuffled_slope).sum()),
                                  delta_iou_ci=[float(np.percentile([RNG.choice((T2.iou_slope - T2.iou_const).values, len(T2)).mean() for _ in range(2000)], q)) for q in (2.5, 97.5)], mean_delta=float((T2.iou_slope - T2.iou_const).mean()))
    summ["T3_loo_auc"] = {thr: {m: dict(mean=float(np.nanmean([t3[l][thr][m] for l in t3])), median=float(np.nanmedian([t3[l][thr][m] for l in t3]))) for m in ("auc_dist", "auc_dist_plus_slope", "auc_slope_only")} for thr in ("d3", "d6", "d10")}
    summ["T3_lakes_slope_improves_auc"] = {thr: [int(sum(t3[l][thr]["auc_dist_plus_slope"] > t3[l][thr]["auc_dist"] for l in t3)), len(t3)] for thr in ("d3", "d6", "d10")}
    summ["T3_mean_delta_auc_d6_ci"] = [float(np.percentile([RNG.choice(np.array([t3[l]["d6"]["auc_dist_plus_slope"] - t3[l]["d6"]["auc_dist"] for l in t3]), len(t3)).mean() for _ in range(2000)], q)) for q in (2.5, 97.5)]
    json.dump(dict(summary=summ, per_lake=res, t2=t2, t3=t3), open(D / "contour_spatial_test.json", "w"), indent=1, default=float)
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
