#!/usr/bin/env python3
"""Depth Brain / terrain Question A, within-lake: does shoreline slope (per segment) predict WHERE shallow water is?
Truth: depth-below-pool rasters (15 m) interpolated from real TWDB 1-ft / 2-ft bathymetric contours (terrain_contour_depth.py).
Predictors: 3DEP shore profile per ~500 m segment (terrain_dem_profile.py), polygon-only geometry (distance to shore, local openness).
Tests per lake (then pooled over lakes, no cherry-picking: every lake with a depth grid and a DEM profile is reported):
  T1 segment level: Spearman(segment slope, share of the near-shore water band (0-100 m from shore, assigned to nearest shore point) with depth <= 3 ft).
  T2 raster level: mask 'predicted shallow' = water within 100 m of shore on segments flatter than a slope threshold, vs truth depth <= 3 ft -> precision / recall / IoU,
     against baselines (all water within 100 m of shore regardless of slope; flat-segment mask with random segment labels).
  T3 cell-level ranking: AUC for depth <= 3 ft and <= 6 ft of (a) distance-to-shore alone, (b) distance + segment slope, logistic fit on the OTHER lakes (leave-one-lake-out).
Output docs/research/depth-brain/data/shallow_spatial_validation.json (+ per-lake rows).  Run with venv python."""
import json, re, sys
from pathlib import Path
import numpy as np
from scipy import stats, ndimage
from scipy.spatial import cKDTree
from pyproj import Transformer
from terrain_stats import Logit
sys.path.insert(0, str(Path(__file__).parent))
from terrain_features import segment_features

REPO = Path(__file__).resolve().parents[2]
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
OUT = REPO / "docs/research/depth-brain/data"
RES = 15.0


def safe(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def auc(score, pos):
    pos = np.asarray(pos, bool)
    if pos.sum() < 20 or (~pos).sum() < 20: return np.nan
    r = stats.rankdata(score); return float((r[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def load_lake(key):
    g = np.load(RAW / "depthgrid" / f"{key}.npz"); d = dict(np.load(RAW / "dem_dense" / f"{safe(key)}.npz"))
    depth = g["depth_ft"]; a, b, c, dd, e, f = g["transform"]       # affine a,b,c,d,e,f ; north-up: a=RES, e=-RES
    H, W = depth.shape
    water = np.isfinite(depth)
    dist = ndimage.distance_transform_edt(water) * RES                 # distance to nearest non-water cell
    yy, xx = np.ogrid[-10:11, -10:11]; disk = (xx ** 2 + yy ** 2) <= 100          # 150 m radius at 15 m cells
    narrow = water & ~ndimage.binary_opening(water, structure=disk)                  # arms / coves narrower than ~300 m
    rows, cols = np.nonzero(water)
    xs = c + (cols + .5) * a; ys = f + (rows + .5) * e
    t = Transformer.from_crs(4326, 5070, always_xy=True); px, py = t.transform(d["lon"], d["lat"])
    segs, segid = segment_features(d, 500.0)
    seg_tab = {s["seg"]: s for s in segs}
    return dict(depth=depth[rows, cols], narrow=narrow[rows, cols], dist=dist[rows, cols], xs=xs, ys=ys, shore=np.column_stack([px, py]), segid=segid, seg_tab=seg_tab, d=d)


def run_lake(key):
    L = load_lake(key)
    shore, segid = L["shore"], L["segid"]
    valid = segid >= 0
    tree = cKDTree(shore[valid]); idxmap = np.where(valid)[0]
    dd, ni = tree.query(np.column_stack([L["xs"], L["ys"]]))
    cell_seg = segid[idxmap[ni]]
    near = (L["dist"] <= 100) & (dd <= 400)
    rows = []
    for sid, s in L["seg_tab"].items():
        m = near & (cell_seg == sid)
        if m.sum() < 30: continue
        dep = L["depth"][m]
        # local openness: share of water cells within 300 m of the segment centre that lie further than 100 m from shore
        rows.append(dict(seg=sid, n_cells=int(m.sum()), sh3=float((dep <= 3).mean()), sh6=float((dep <= 6).mean()), sh10=float((dep <= 10).mean()), mean_depth=float(dep.mean()),
                         slope_10_60=s["slope_10_60"], slope_30_100=s["slope_30_100"], slope_60_200=s["slope_60_200"], slope_5_20=s["slope_5_20"], rise200=s["rise200"], x=s["x"], y=s["y"]))
    r = dict(key=key, region="MN" if key.startswith("MN_") else "TX", n_seg=len(rows), lake_sh3=float((L["depth"] <= 3).mean()), lake_sh6=float((L["depth"] <= 6).mean()), lake_sh10=float((L["depth"] <= 10).mean()))
    if len(rows) >= 8:
        for N in (3, 6, 10):
            sh = np.array([x[f"sh{N}"] for x in rows])
            if sh.std() < 1e-6: continue
            for p in ("slope_10_60", "slope_30_100", "slope_60_200", "slope_5_20", "rise200"):
                v = np.array([x[p] for x in rows]); r[f"spearman_{p}_vs_sh{N}"] = float(stats.spearmanr(v, sh)[0])
            top = sh >= np.quantile(sh, 2 / 3)
            for p in ("slope_10_60", "slope_30_100", "slope_60_200", "rise200"):
                v = -np.array([x[p] for x in rows]); r[f"auc_{p}_top_tercile_sh{N}"] = auc(v, top)
            r[f"seg_sh{N}_sd"] = float(sh.std())
        md = np.array([x["mean_depth"] for x in rows])
        for p in ("slope_10_60", "rise200"):
            r[f"spearman_{p}_vs_meandepth"] = float(stats.spearmanr(np.array([x[p] for x in rows]), md)[0])
    # T2: masks over near-shore band
    slope_cell = np.array([L["seg_tab"].get(s, {}).get("slope_10_60", np.nan) for s in cell_seg])
    band = (L["dist"] <= 100) & np.isfinite(slope_cell)
    r["masks"] = {}
    for N in (3, 10):
        truth = L["depth"] <= N; om = {}
        for thr in (1.0, 2.0, 4.0):
            pred = band & (slope_cell < thr)
            tp = (pred & truth).sum(); om[f"slope<{thr}"] = dict(pred_frac_of_band=float(pred.sum() / max(band.sum(), 1)), precision=float(tp / max(pred.sum(), 1)), recall=float(tp / max(truth.sum(), 1)), iou=float(tp / max((pred | truth).sum(), 1)))
        pred = band; tp = (pred & truth).sum()
        om["all_band_100m"] = dict(precision=float(tp / max(pred.sum(), 1)), recall=float(tp / max(truth.sum(), 1)), iou=float(tp / max((pred | truth).sum(), 1)))
        r["masks"][f"le{N}"] = om
    r["cells"] = dict(n=int(len(L["depth"])))
    r["_cell_arrays"] = (L["dist"], slope_cell, L["depth"], L["narrow"]); r["narrow_share_of_water"] = float(L["narrow"].mean())
    return r, rows


def main():
    keys = [p.stem for p in sorted((RAW / "depthgrid").glob("*.npz")) if (RAW / "dem" / f"{safe(p.stem)}.npz").exists()]
    res, segrows, cells = [], {}, {}
    for k in keys:
        try:
            r, rows = run_lake(k)
        except Exception as e:
            print(k, "ERR", repr(e)[:120]); continue
        cells[k] = r.pop("_cell_arrays"); segrows[k] = rows; res.append(r); print(k, r["n_seg"], round(r.get("spearman_slope_10_60_vs_sh3", np.nan), 3), flush=True)
    # T3 leave-one-lake-out logistic ranking (thresholds 3, 6, 10 ft)
    rng = np.random.default_rng(0)
    def feats(k, sub=None):
        dist, sl, dep, nar = cells[k]; m = np.isfinite(sl) & (dist <= 300)
        idx = np.nonzero(m)[0]
        if sub and len(idx) > sub: idx = rng.choice(idx, sub, replace=False)
        return dist[idx], sl[idx], dep[idx], nar[idx].astype(float)
    sam = {k: feats(k, 60000) for k in cells}
    t3 = {}
    ff = lambda d, s: np.column_stack([np.log1p(d), np.log1p(np.clip(s, 0, None)), np.log1p(d) * np.log1p(np.clip(s, 0, None))])
    for k in cells:
        tr = [j for j in cells if j != k]
        D = np.concatenate([sam[j][0] for j in tr]); S = np.concatenate([sam[j][1] for j in tr]); Z = np.concatenate([sam[j][2] for j in tr]); NR = np.concatenate([sam[j][3] for j in tr])
        d, s_, z, nr_ = sam[k]; row = {}
        for thr in (3, 6, 10):
            y = Z <= thr; yk = z <= thr
            m1 = Logit().fit(np.column_stack([np.log1p(D)]), y); m2 = Logit().fit(ff(D, S), y)
            m3 = Logit().fit(np.column_stack([np.log1p(D), NR]), y); m4 = Logit().fit(np.column_stack([ff(D, S), NR]), y)
            row[f"d{thr}"] = dict(auc_dist=auc(m1.decision_function(np.column_stack([np.log1p(d)])), yk), auc_dist_plus_slope=auc(m2.decision_function(ff(d, s_)), yk), auc_slope_only=auc(-s_, yk),
                                  auc_dist_plus_narrow=auc(m3.decision_function(np.column_stack([np.log1p(d), nr_])), yk), auc_dist_slope_narrow=auc(m4.decision_function(np.column_stack([ff(d, s_), nr_])), yk), auc_narrow_only=auc(nr_, yk))
        t3[k] = row
    def agg(f, sel=None):
        v = np.array([f(r) for r in res if (sel is None or sel(r)) and f(r) is not None], float); v = v[np.isfinite(v)]
        return dict(n=int(len(v)), mean=round(float(v.mean()), 3) if len(v) else None, median=round(float(np.median(v)), 3) if len(v) else None, n_neg=int((v < 0).sum()))
    summ = {"n_lakes": len(res), "lakes": [r["key"] for r in res]}
    for grp, sel in (("TX", lambda r: r["region"] == "TX"), ("MN", lambda r: r["region"] == "MN"), ("ALL", None)):
        g = {}
        for N in (3, 6, 10):
            for p in ("slope_10_60", "slope_30_100", "slope_60_200", "rise200"):
                g[f"spearman_{p}_vs_sh{N}"] = agg(lambda r, p=p, N=N: r.get(f"spearman_{p}_vs_sh{N}"), sel)
                g[f"auc_{p}_top_tercile_sh{N}"] = agg(lambda r, p=p, N=N: r.get(f"auc_{p}_top_tercile_sh{N}"), sel)
        g["spearman_slope_10_60_vs_meandepth"] = agg(lambda r: r.get("spearman_slope_10_60_vs_meandepth"), sel)
        for N in (3, 10):
            rr = [r for r in res if sel is None or sel(r)]
            for thr in ("slope<1.0", "slope<2.0", "slope<4.0", "all_band_100m"):
                g[f"mask_le{N}_{thr}"] = {k: round(float(np.nanmean([r["masks"][f"le{N}"][thr][k] for r in rr])), 3) for k in (("pred_frac_of_band", "precision", "recall", "iou") if thr != "all_band_100m" else ("precision", "recall", "iou"))}
        keys = [k for k in t3 if sel is None or sel(next(r for r in res if r["key"] == k))]
        g["T3_leave_one_lake_out_auc"] = {thr: {m: round(float(np.nanmean([t3[l][thr][m] for l in keys])), 3) for m in ("auc_dist", "auc_dist_plus_slope", "auc_slope_only", "auc_dist_plus_narrow", "auc_dist_slope_narrow", "auc_narrow_only")} for thr in ("d3", "d6", "d10")}
        g["T3_lakes_where_slope_helps"] = {thr: [int(sum(t3[l][thr]["auc_dist_plus_slope"] > t3[l][thr]["auc_dist"] for l in keys)), len(keys)] for thr in ("d3", "d6", "d10")}
        summ[grp] = g
    (OUT / "shallow_spatial_validation.json").write_text(json.dumps(dict(summary=summ, per_lake=res, t3=t3), indent=1, default=float))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
