#!/usr/bin/env python3
"""Hartwell exposed-area pilot (research only): does Landsat-8/9 water extent respond to the CWMS pool level the way the CWMS stage-area rating says?

fetch   : STAC search Microsoft Planetary Computer landsat-c2-l2 (L8/L9, path 18 row 36, cloud < 35 %), select up to N scenes stratified by pool level
          (all scenes with level <= 656 ft kept), read green + swir16 + QA_PIXEL windows (30 m), wet = MNDWI > 0, QA cloud/shadow/snow/fill -> invalid.
          Cube saved to ~/Desktop/Development/Sector_Research_Data/depth-brain/adoption/hartwell/sat/hartwell_cube.npz   (never git)
analyze : lake mask = largest connected component of pixels wet in >= 1 scene with level >= 658.5 ft, dilated 1 px; A_sat(scene) = wet pixels in mask (valid fraction >= 97 %).
          Compare dA/dz and A(650)/A(660) with the CWMS-rating-derived curve (hartwell_effective_depth_results.json).
Run: venv python, `-I` not usable here because it imports from the venv's own packages only (it does) -> use `-I`.
"""
import json, os, sys, time, warnings
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, requests, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
warnings.filterwarnings("ignore")
R = os.path.expanduser("~/Desktop/Development/Sector_Research_Data")
AD = R + "/depth-brain/adoption/hartwell"; os.makedirs(AD + "/sat", exist_ok=True)
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
OUTJ = os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption/docs/brains/depth/data/hartwell_landsat_pilot_results.json")
BBOX = [-83.28259 - 0.01, 34.33757 - 0.01, -82.80189 + 0.01, 34.64963 + 0.01]
_tok = {}


def token():
    if not _tok or _tok["exp"] < time.time() + 120:
        j = requests.get("https://planetarycomputer.microsoft.com/api/sas/v1/token/landsateuwest/landsat-c2", timeout=60).json()
        _tok.update(tok=j["token"], exp=time.time() + 1800)
    return _tok["tok"]


def level_series():
    s = pd.read_csv(f"{R}/lake-brain/history/lakebrain_gcs/Lake_Hartwell_SC.csv", parse_dates=["date"]).set_index("date")["elevationFt"].astype(float)
    return s


def search():
    feats, body = [], dict(collections=["landsat-c2-l2"], bbox=BBOX, datetime="2013-04-01/2026-10-10", limit=200,
                           query={"eo:cloud_cover": {"lt": 35}, "platform": {"in": ["landsat-8", "landsat-9"]}})
    while True:
        r = requests.post(STAC, json=body, timeout=120).json(); feats += r["features"]
        nxt = [l for l in r.get("links", []) if l["rel"] == "next"]
        if not nxt: break
        body = nxt[0].get("body") or body
    return feats


def read_scene(it):
    try:
        a = it["assets"]
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="2"):
            qa = rasterio.open(a["qa_pixel"]["href"] + "?" + token())
            w = from_bounds(*transform_bounds("EPSG:4326", qa.crs, *BBOX), transform=qa.transform).round_offsets().round_lengths()
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
        return it["id"], None, repr(e)[:100], None, None


def fetch(N=140):
    lv = level_series(); feats = search()
    rows = []
    for f in feats:
        p = f["properties"]
        if (p["landsat:wrs_path"], p["landsat:wrs_row"]) != ("018", "036"): continue
        d = pd.Timestamp(p["datetime"][:10])
        if d not in lv.index: continue
        rows.append((f, d, float(lv[d])))
    print("scenes path18/row36 with level:", len(rows), flush=True)
    low = [r for r in rows if r[2] <= 656]; hi = [r for r in rows if r[2] > 656]
    rng = np.random.default_rng(7); keep = low + [hi[i] for i in rng.permutation(len(hi))[: max(0, N - len(low))]]
    print("selected", len(keep), "(low-level kept:", len(low), ")", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(8) as ex: res = list(ex.map(lambda r: read_scene(r[0]), keep))
    ok = [r for r in res if r[1]]
    print("read ok", len(ok), "failed", len(res) - len(ok), [r[2] for r in res if not r[1]][:2], "secs", round(time.time() - t0), flush=True)
    from collections import Counter
    shp = Counter((r[2].shape, tuple(r[3])[:6]) for r in ok).most_common(1)[0][0]
    ok = [r for r in ok if (r[2].shape, tuple(r[3])[:6]) == shp]
    dates = np.array([r[1] for r in ok]); cube = np.stack([r[2] for r in ok]); o = np.argsort(dates)
    np.savez_compressed(AD + "/sat/hartwell_cube.npz", dates=dates[o], cube=cube[o], transform=np.array(ok[0][3])[:6], crs=ok[0][4], ids=np.array([r[0] for r in ok])[o])
    print("saved", cube.shape, flush=True)


def analyze():
    from scipy import stats, ndimage
    from rasterio.transform import Affine
    z = np.load(AD + "/sat/hartwell_cube.npz", allow_pickle=True); cube = z["cube"]; dates = pd.to_datetime(z["dates"]); tr = Affine(*z["transform"])
    lv = level_series(); L = np.array([lv.get(d, np.nan) for d in dates])
    px_ac = abs(tr.a * tr.e) / 4046.8564224
    inval = cube == 255; wet = cube == 1
    # lake mask from high-pool scenes
    hi = (L >= 658.5)
    union = wet[hi].any(axis=0) if hi.any() else wet.any(axis=0)
    lab, n = ndimage.label(union); sizes = ndimage.sum(union, lab, range(1, n + 1)); mask = lab == (1 + int(np.argmax(sizes)))
    mask = ndimage.binary_dilation(mask, iterations=1)
    vfrac = 1 - inval[:, mask].mean(axis=1)
    A = np.array([wet[i][mask].sum() for i in range(len(L))]) * px_ac
    # correct for invalid pixels by scaling (cloud holes are small by selection)
    good = (vfrac >= 0.97) & np.isfinite(L)
    Ac = A[good] / vfrac[good]; Lg = L[good]; dg = dates[good]
    print("scenes", len(L), "usable", int(good.sum()), "level range", Lg.min(), Lg.max(), "mask acres", mask.sum() * px_ac)
    res = dict(scenes_total=int(len(L)), scenes_used=int(good.sum()), level_min=float(Lg.min()), level_max=float(Lg.max()), mask_acres=float(mask.sum() * px_ac), pixel_acres=float(px_ac),
               date_first=str(dg.min().date()), date_last=str(dg.max().date()))
    # binned A_sat(z)
    bins = np.arange(644, 666, 2.0); lab_ = pd.cut(Lg, bins)
    tb = pd.DataFrame({"z": Lg, "A": Ac}).groupby(lab_, observed=True).agg(n=("A", "size"), zmean=("z", "mean"), A_med=("A", "median"), A_min=("A", "min"), A_max=("A", "max"))
    print(tb.round(0).to_string()); res["binned_2ft"] = {str(k): {c: float(v) for c, v in r.items()} for k, r in tb.iterrows()}
    # slope: Theil-Sen within [650, 661]
    m = (Lg >= 650) & (Lg <= 661)
    ts = stats.theilslopes(Ac[m], Lg[m]); res["dAdz_sat_theilsen_650_661_ac_per_ft"] = dict(slope=float(ts[0]), lo95=float(ts[2]), hi95=float(ts[3]), n=int(m.sum()))
    rho = stats.spearmanr(Lg, Ac); res["spearman_level_vs_area"] = dict(rho=float(rho[0]), p=float(rho[1]), n=int(len(Lg)))
    # bootstrap slope over scenes
    rng = np.random.default_rng(3); idx = np.nonzero(m)[0]; bs = []
    for _ in range(500):
        b = rng.choice(idx, len(idx)); bs.append(stats.theilslopes(Ac[b], Lg[b])[0])
    res["dAdz_sat_boot90"] = [float(np.percentile(bs, 5)), float(np.percentile(bs, 95))]
    # rating-derived reference
    rj = json.load(open(os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption/docs/brains/depth/data/hartwell_effective_depth_results.json")))
    ap = rj["area_per_ft"]; res["rating_ref"] = dict(dAdz_quad=ap["dAdz_ac_per_ft"], A650=ap["A_at_650"], A660=ap["A_at_660"], table_slope_650_660_2010=ap["table_slope_650_to_660_2010-2026"])
    # ratio of areas 650 vs 660 from fitted line through the scenes (linear in z)
    lf = np.polyfit(Lg[m], Ac[m], 1); res["sat_linear_fit_650_661"] = dict(slope=float(lf[0]), A_at_650=float(np.polyval(lf, 650)), A_at_660=float(np.polyval(lf, 660)), frac_lost_660_to_650=float(1 - np.polyval(lf, 650) / np.polyval(lf, 660)))
    res["rating_frac_lost_660_to_650"] = float(1 - ap["A_at_650"] / ap["A_at_660"])
    # month-of-year balance of scenes (shoreline vegetation/season confound)
    res["scene_month_counts"] = {int(k): int(v) for k, v in pd.Series(dg.month).value_counts().sort_index().items()}
    # exposed shore pixels: wet in a >=658.5 scene and dry in a scene with level <= 652 -> acres exposed (lower bound given cloud/mixed-pixel limits)
    lo = (L <= 652) & good
    if lo.sum() >= 3:
        wet_lo_frac = np.array([wet[i][mask].mean() for i in np.nonzero(lo)[0]])
        dry_in_low = (~wet[lo][:, mask]) & (~inval[lo][:, mask])
        persistent_dry = dry_in_low.mean(axis=0) >= 0.7  # dry in >= 70 % of the low-level scenes
        exposed_ac = float((persistent_dry & union[mask]).sum() * px_ac)
        res["pixels_wet_at_high_pool_but_dry_in_70pct_of_le652_scenes_acres"] = exposed_ac; res["n_low_scenes_le652"] = int(lo.sum())
    print(json.dumps({k: v for k, v in res.items() if k != "binned_2ft"}, indent=1))
    json.dump(res, open(OUTJ, "w"), indent=1)
    pd.DataFrame({"date": dg, "level_ft": Lg, "wet_acres": Ac}).to_csv(AD + "/sat/hartwell_scene_area.csv", index=False)


if __name__ == "__main__":
    {"fetch": fetch, "analyze": analyze}[sys.argv[1]]()
