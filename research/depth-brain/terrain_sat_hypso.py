#!/usr/bin/env python3
"""Depth Brain / terrain: satellite hypsometry from Landsat water masks vs a known daily pool-level series ('drawdown-exposed terrain').
Step 1 (fetch): STAC search Landsat C2 L2 (L5/7/8/9) on Microsoft Planetary Computer for one path/row covering the lake, read green + swir16 + QA_PIXEL
  windows, MNDWI > 0 => wet, QA cloud/shadow/snow/fill => invalid.  Cube saved to <RAW>/sat/<key>.npz (never git).
Step 2 (analyze): per-scene level (waterdatafortexas daily series) -> (a) lake-wide A_sat(level) and dA/dz near pool vs the TWDB table truth;
  (b) per-pixel inundation threshold elevation e_i (best split of wet/dry vs level) -> satellite depth map = pool - e_i, compared with the TWDB
  contour-derived depth grid (Spearman, MAE) over pixels whose threshold lies inside the observed level range.
Usage: terrain_sat_hypso.py fetch <key> <txslug> [y0] | analyze <key> <txslug>      Run with the venv python."""
import io, json, sys, time, math, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd, requests, rasterio
from rasterio.windows import Window, from_bounds
from rasterio.features import rasterize
from rasterio.warp import transform_bounds
from shapely.geometry import shape, box
from pyproj import Transformer
import shapely

RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAT = RAW / "sat"; SAT.mkdir(exist_ok=True)
_tok = {}


def token():
    if not _tok or _tok["exp"] < time.time() + 120:
        j = requests.get("https://planetarycomputer.microsoft.com/api/sas/v1/token/landsateuwest/landsat-c2", timeout=60).json()
        _tok.update(tok=j["token"], exp=time.time() + 1800)
    return _tok["tok"]


def level_series(slug):
    t = requests.get(f"https://www.waterdatafortexas.org/reservoirs/individual/{slug}.csv", timeout=120).text
    d = pd.read_csv(io.StringIO("\n".join(l for l in t.splitlines() if not l.startswith("#"))), parse_dates=["date"])
    d = d.dropna(subset=["water_level"]).set_index("date")["water_level"]
    return d


def search(bbox, y0):
    feats, page = [], None
    body = dict(collections=["landsat-c2-l2"], bbox=bbox, datetime=f"{y0}-01-01/2026-10-01", limit=200,
                query={"eo:cloud_cover": {"lt": 60}, "platform": {"in": ["landsat-5", "landsat-7", "landsat-8", "landsat-9"]}})
    while True:
        r = requests.post(STAC, json=body, timeout=120).json()
        feats += r["features"]
        nxt = [l for l in r.get("links", []) if l["rel"] == "next"]
        if not nxt or len(feats) > 3000: break
        body = nxt[0].get("body") or body
        if "token" in (nxt[0].get("body") or {}): pass
    return feats


def read_scene(it, win_ll, tr_info):
    """return (date, uint8 wet/dry/invalid array) on the item's own grid window"""
    try:
        a = it["assets"]
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2"):
            qa = rasterio.open(a["qa_pixel"]["href"] + "?" + token())
            w = from_bounds(*transform_bounds("EPSG:4326", qa.crs, *win_ll), transform=qa.transform).round_offsets().round_lengths()
            Q = qa.read(1, window=w)
            G = rasterio.open(a["green"]["href"] + "?" + token()).read(1, window=w).astype("float32")
            S = rasterio.open(a["swir16"]["href"] + "?" + token()).read(1, window=w).astype("float32")
            tr = qa.window_transform(w)
        g = G * 0.0000275 - 0.2; s = S * 0.0000275 - 0.2
        m = (g - s) / np.maximum(g + s, 1e-6)
        bad = ((Q >> 0) & 1) | ((Q >> 1) & 1) | ((Q >> 2) & 1) | ((Q >> 3) & 1) | ((Q >> 4) & 1) | ((Q >> 5) & 1) | (G == 0)
        out = np.where(bad > 0, 255, (m > 0).astype("uint8")).astype("uint8")
        return it["id"], it["properties"]["datetime"][:10], out, tr, str(qa.crs)
    except Exception as e:
        return it["id"], None, repr(e)[:80], None, None


def fetch(key, slug, y0=2000):
    d = RAW / "twdb" / key; poly = shape(json.load(open(d / "pool_polygon.geojson")))
    b = poly.bounds; pad = 0.004
    bbox = [b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad]
    feats = search(bbox, y0)
    # one path/row with most scenes that fully cover the bbox
    full = [f for f in feats if f["bbox"][0] <= bbox[0] and f["bbox"][1] <= bbox[1] and f["bbox"][2] >= bbox[2] and f["bbox"][3] >= bbox[3]]
    from collections import Counter
    c = Counter((f["properties"]["landsat:wrs_path"], f["properties"]["landsat:wrs_row"]) for f in full)
    pr = c.most_common(1)[0][0]; its = [f for f in full if (f["properties"]["landsat:wrs_path"], f["properties"]["landsat:wrs_row"]) == pr]
    print(key, "scenes", len(feats), "covering", len(full), "path/row", pr, "chosen", len(its), flush=True)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda it: read_scene(it, bbox, None), its))
    ok = [r for r in res if r[1]]
    print("read ok", len(ok), "failed", len(res) - len(ok), [r[2] for r in res if not r[1]][:2], flush=True)
    # same grid? keep the modal shape/transform
    shp = Counter((r[2].shape, tuple(r[3])[:6]) for r in ok).most_common(1)[0][0]
    ok = [r for r in ok if (r[2].shape, tuple(r[3])[:6]) == shp]
    dates = np.array([r[1] for r in ok]); cube = np.stack([r[2] for r in ok])
    o = np.argsort(dates)
    np.savez_compressed(SAT / f"{key}.npz", dates=dates[o], cube=cube[o], transform=np.array(ok[0][3])[:6], crs=ok[0][4], slug=slug, ids=np.array([r[0] for r in ok])[o])
    print("saved", cube.shape, flush=True)


def analyze(key, slug):
    from scipy import stats
    sys.path.insert(0, str(Path(__file__).parent)); from terrain_stats import Isotonic
    from rasterio.transform import Affine
    z = np.load(SAT / f"{key}.npz", allow_pickle=True); cube = z["cube"]; dates = pd.to_datetime(z["dates"]); crs = str(z["crs"]); tr = Affine(*z["transform"])
    N, H, W = cube.shape
    lvl = level_series(slug); lv = lvl.reindex(dates, method="nearest", tolerance=pd.Timedelta("2D")).values
    tt = json.load(open(RAW / "twdb_truth.json"))[key]; pool = tt["pool_ft"]
    tab = np.array([[abs(float(a)) for a in l.split(",")[:3]] for l in open(RAW / "twdb" / key / "table.txt") if l.strip() and l[0] in "-0123456789"])
    poly = shape(json.load(open(RAW / "twdb" / key / "pool_polygon.geojson")))
    T = Transformer.from_crs(4326, crs, always_xy=True)
    polym = shapely.transform(poly, lambda a: np.column_stack(T.transform(a[:, 0], a[:, 1])))
    inside = rasterize([(polym, 1)], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    aoi = rasterize([(polym.buffer(150), 1)], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    inval = (cube == 255)
    inval_frac = inval[:, aoi].mean(axis=1)
    good = (inval_frac <= 0.03) & np.isfinite(lv)
    cube, lv, dates = cube[good], lv[good], dates[good]
    wet = (cube == 1)
    res = dict(key=key, scenes_total=int(N), scenes_used=int(good.sum()), level_min=float(lv.min()), level_max=float(lv.max()), pool_ft=pool, years=[int(dates.year.min()), int(dates.year.max())])
    res["scenes_with_level_ge_pool_minus"] = {str(d): int((lv >= pool - d).sum()) for d in (1, 3, 6, 10)}
    unit = 4046.856 if tab[:, 1].max() < 2e6 else 0.09290304
    ac = lambda m: m * 900.0 / 4046.856
    Asat = np.array([ac(wet[i][aoi].sum()) for i in range(len(lv))])
    # (a) lake-wide: monotone fit of A_sat(level), compare slopes and shallow shares to the table
    iso = Isotonic().fit(lv, Asat)
    Atab = lambda zz: np.interp(zz, tab[:, 0], tab[:, 1] * (unit / 4046.856))
    res["area_sat_at_pool_ac"] = float(iso.predict([pool])[0]); res["area_table_at_pool_ac"] = float(Atab(pool))
    for d in (1, 2, 3, 4, 6):
        if lv.min() <= pool - d:
            res[f"S{d}_sat"] = float(1 - iso.predict([pool - d])[0] / iso.predict([pool])[0])
            res[f"S{d}_table"] = float(1 - Atab(pool - d) / Atab(pool))
    # linear dA/dz over [pool-6, pool+1]
    m = (lv >= pool - 6) & (lv <= pool + 1)
    if m.sum() >= 15 and np.ptp(lv[m]) > 2:
        sl = stats.theilslopes(Asat[m], lv[m])[0]
        res["dAdz_sat_ac_per_ft"] = float(sl); res["dAdz_table_ac_per_ft"] = float((Atab(pool) - Atab(pool - 6)) / 6)
    # (b) per-pixel threshold elevation
    P = np.nonzero(aoi.ravel())[0]
    X = wet.reshape(len(lv), -1)[:, P]; V = (~inval).reshape(len(lv), -1)[:, P]
    o = np.argsort(lv); X = X[o]; V = V[o]; ls = lv[o]
    wc = np.cumsum(X & V, axis=0); dc = np.cumsum((~X) & V, axis=0); dtot = dc[-1]; nv = V.sum(0)
    # error if threshold placed after scene k (k = -1 .. N-1): wet below + dry above
    err = np.vstack([dtot[None, :], wc + (dtot[None, :] - dc)])        # row j: threshold above first j scenes
    j = err.argmin(0); emin = err.min(0)
    lo = np.concatenate([[ls[0] - 1], ls]); hi = np.concatenate([ls, [ls[-1] + 1]])
    thr = 0.5 * (lo[j] + hi[j])
    n_below = np.cumsum(V, axis=0); nb = np.where(j > 0, n_below[np.clip(j - 1, 0, None), np.arange(len(P))], 0); na = nv - nb
    info = (nv >= 40) & (emin <= 0.1 * nv) & (nb >= 5) & (na >= 5)
    # truth depth at pixel centres
    gz = np.load(RAW / "depthgrid" / f"{key}.npz"); dg = gz["depth_ft"]; a_, b_, c_, d_, e_, f_ = gz["transform"]
    rr, cc = np.divmod(P, W); xs = tr.c + (cc + .5) * tr.a; ys = tr.f + (rr + .5) * tr.e
    T2 = Transformer.from_crs(crs, 5070, always_xy=True); x5, y5 = T2.transform(xs, ys)
    ci = np.floor((x5 - c_) / a_).astype(int); ri = np.floor((y5 - f_) / e_).astype(int)
    okp = (ci >= 0) & (ci < dg.shape[1]) & (ri >= 0) & (ri < dg.shape[0])
    dtruth = np.full(len(P), np.nan); dtruth[okp] = dg[ri[okp], ci[okp]]
    dsat = pool - thr
    cmp = info & np.isfinite(dtruth) & (dtruth <= pool - ls[0])             # truth depth inside the observed level range
    res["pixels_in_aoi"] = int(len(P)); res["pixels_informative"] = int(info.sum()); res["pixels_compared"] = int(cmp.sum())
    reach = np.isfinite(dtruth) & (dtruth <= pool - ls[0])
    res["truth_cells_within_observed_range"] = int(reach.sum()); res["recall_of_in_range_cells"] = float(cmp.sum() / max(reach.sum(), 1))
    if cmp.sum() > 100:
        res["spearman_depth"] = float(stats.spearmanr(dsat[cmp], dtruth[cmp])[0]); res["mae_ft"] = float(np.abs(dsat[cmp] - dtruth[cmp]).mean()); res["bias_ft"] = float((dsat[cmp] - dtruth[cmp]).mean())
        res["within_1ft"] = float((np.abs(dsat[cmp] - dtruth[cmp]) <= 1).mean()); res["within_2ft"] = float((np.abs(dsat[cmp] - dtruth[cmp]) <= 2).mean())
        res["truth_depth_range_compared"] = [float(np.percentile(dtruth[cmp], 5)), float(np.percentile(dtruth[cmp], 95))]
        # shallow classification: truth <= 3 ft among truth cells within range
        rs = reach & (dtruth <= 3)
        res["truth_le3ft_cells_in_range"] = int(rs.sum()); res["le3_recovered_as_informative"] = float((info & rs).sum() / max(rs.sum(), 1))
        sat_sh = info & (dsat <= 3); res["le3_precision"] = float((sat_sh & (dtruth <= 3)).sum() / max(sat_sh.sum(), 1))
    (RAW / "sat" / f"{key}_analysis.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 2000)
    elif sys.argv[1] == "analyze":
        analyze(sys.argv[2], sys.argv[3])
