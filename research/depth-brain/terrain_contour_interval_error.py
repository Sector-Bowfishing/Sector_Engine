#!/usr/bin/env python3
"""Depth Brain / effective depth (sigma_ref): how much vertical error does a COARSE contour interval put into shallow-water depth?
On TWDB lakes with 1-ft contours, rebuild the depth grid from every k-th contour only (k = 2, 5, 10 ft, counted down from pool; shoreline = depth 0) and compare with the
1-ft grid (our best truth) over cells shallower than 10 ft: RMSE / MAE / bias of depth, error in the 0-3 ft share, IoU of the <=3 ft mask.
Model of what a state lake map with a 5- or 10-ft interval delivers when linearly interpolated.  Output docs/research/depth-brain/data/contour_interval_error.json.  venv python."""
import json, sys
from pathlib import Path
import numpy as np, geopandas as gpd, shapely
from shapely.geometry import shape
from scipy.interpolate import LinearNDInterpolator
from rasterio.features import rasterize
from rasterio.transform import from_origin
sys.path.insert(0, str(Path(__file__).parent))
from terrain_contour_depth import densify, RES, elev_col
REPO = Path(__file__).resolve().parents[2]
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
KEYS = ["Bardwell_2020-07", "Cherokee_2023-01", "granbury_2015-06", "Lavon_2021-07", "BobSandlin_2018-02", "Coleman_2006-08", "Bryan_2016-02", "Diversion_2013-06", "striker_2021-03", "Brownwood_2013-06"]


def run(key):
    d = RAW / "twdb" / key; pool = json.load(open(RAW / "twdb_truth.json"))[key]["pool_ft"]
    shp = next((d / "contours").glob("*.shp")); g = gpd.read_file(shp).to_crs(5070); ec = elev_col(g)
    poly = gpd.GeoSeries([shape(json.load(open(d / "pool_polygon.geojson")))], crs=4326).to_crs(5070).iloc[0]
    z = g[ec].abs().values
    pts, vals = [], []
    for geom, zz in zip(g.geometry, z):
        if geom is None or geom.is_empty: continue
        for ln in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            if ln.length < 5: continue
            xy = densify(ln.coords, 25.0); pts.append(xy); vals.append(np.full(len(xy), pool - zz))     # depth below pool
    P = np.vstack(pts); Dv = np.concatenate(vals)
    rb = poly.boundary; sh = []
    for ln in (rb.geoms if hasattr(rb, "geoms") else [rb]): sh.append(densify(ln.coords, 25.0))
    S = np.vstack(sh)
    minx, miny, maxx, maxy = poly.bounds; W = int((maxx - minx) / RES) + 2; H = int((maxy - miny) / RES) + 2
    tr = from_origin(minx, maxy, RES, RES)
    mask = rasterize([(poly, 1)], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    xs = minx + (np.arange(W) + .5) * RES; ys = maxy - (np.arange(H) + .5) * RES; X, Y = np.meshgrid(xs, ys)
    def grid(sel):
        PP = np.vstack([P[sel], S]); VV = np.concatenate([Dv[sel], np.zeros(len(S))])
        f = LinearNDInterpolator(PP, VV); out = np.full((H, W), np.nan); out[mask] = f(X[mask], Y[mask]); out[out < 0] = 0
        return out
    inside = shapely.contains_xy(poly, P[:, 0], P[:, 1])
    base = grid(inside)
    res = dict(key=key, contour_layer=shp.name)
    for k in (2, 5, 10):
        keep = inside & (np.round(Dv).astype(int) % k == 0)
        if keep.sum() < 100: continue
        gk = grid(keep)
        m = np.isfinite(base) & np.isfinite(gk) & (base <= 10)
        e = gk[m] - base[m]
        a = np.isfinite(base); b3 = base[a] <= 3; k3 = gk[a] <= 3
        res[f"k{k}"] = dict(rmse_ft=float(np.sqrt((e ** 2).mean())), mae_ft=float(np.abs(e).mean()), bias_ft=float(e.mean()), p90_abs_ft=float(np.percentile(np.abs(e), 90)),
                           S3_true=float(b3.mean()), S3_k=float(k3.mean()), iou_le3=float((b3 & k3).sum() / max((b3 | k3).sum(), 1)))
    return res


if __name__ == "__main__":
    out = []
    for k in KEYS:
        try:
            r = run(k); out.append(r); print(k, {kk: {m: round(v, 2) for m, v in vv.items() if m in ("rmse_ft", "mae_ft", "bias_ft", "iou_le3")} for kk, vv in r.items() if isinstance(vv, dict)}, flush=True)
        except Exception as e:
            print(k, "ERR", repr(e)[:120])
    summ = {}
    for kk in ("k2", "k5", "k10"):
        rr = [r[kk] for r in out if kk in r]
        summ[kk] = {m: round(float(np.mean([x[m] for x in rr])), 3) for m in rr[0]} | {"n_lakes": len(rr)} if rr else None
    (REPO / "docs/research/depth-brain/data/contour_interval_error.json").write_text(json.dumps(dict(summary=summ, per_lake=out), indent=1))
    print(json.dumps(summ, indent=1))
