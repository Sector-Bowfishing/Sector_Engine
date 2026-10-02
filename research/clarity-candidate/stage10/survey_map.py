"""Stage 10 survey targeting: where the frozen models disagree on Guntersville (imagery only; no truth).
For each recent usable Sentinel-2 pass: every tile over the lake, a simplified production gate set at 20 m
(SCL water, 60 m from cloud/shadow/cirrus, SWIR <= 0.0215, NDVI <= 0.10, FAI <= 0.005, one pixel off the
bank, 40 m off bright structure), valid pixels binned into 3x3 blocks of the engine's 29.6 m lake grid
(~89 m), band medians per block (>= 5 valid pixels), then the frozen champion, C3, P1 and P2 on each block.
Targeting only: these maps select WHERE to measure; they are never evidence."""
import os, sys, json, math, collections
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR"); os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5"); os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF"); os.environ.setdefault("VSI_CACHE", "TRUE")
import csv
import numpy as np, rasterio, rasterio.windows, pyproj
from rasterio.warp import transform_bounds
from rasterio.enums import Resampling
from scipy import ndimage

S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage10/frozen")
sys.path.insert(0, os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/jobs/lake-surface"))
import regions, models, p2 as P2
from p1 import p1 as P1
import derive_water_surface as dws

BBOX = (-86.4075, 34.2775, -85.6094, 35.0452)
DATES = sys.argv[1:] or ["2026-09-13", "2026-09-20", "2026-09-28"]
items = json.load(open(f"{S}/stage10/es_items_aug_sep.json"))["features"]
B = 3  # block = 3x3 lake-grid cells


def rho(dn):
    r = dn.astype("float32") * dws.S2_SCALE + dws.S2_OFFSET
    r[(dn == 0) | (dn == 65535)] = np.nan
    return r


def tile_pixels(it):
    a = it["assets"]
    src = rasterio.open(a["scl"]["href"])
    b = transform_bounds("EPSG:4326", src.crs, *BBOX, densify_pts=21)
    win = rasterio.windows.from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
    win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
    scl = src.read(1, window=win); tr = src.window_transform(win); h, w = scl.shape
    r20 = lambda k: rho(rasterio.open(a[k]["href"]).read(1, window=win))
    def r10(k):
        s = rasterio.open(a[k]["href"])
        w10 = rasterio.windows.Window(2 * win.col_off, 2 * win.row_off, 2 * win.width, 2 * win.height)
        return rho(s.read(1, window=w10, out_shape=(h, w), resampling=Resampling.average))
    re1, sw, nir = r20("rededge1"), r20("swir16"), r20("nir08")
    blue, green, red = r10("blue"), r10("green"), r10("red")
    water = scl == dws.SCL_WATER
    cloud = np.isin(scl, [3, 8, 9, 10])
    near_cloud = ndimage.binary_dilation(cloud, iterations=3)
    bank = ndimage.binary_erosion(water, iterations=1)
    bright = ndimage.binary_dilation(np.nan_to_num(sw, nan=0) > dws.BRIGHT_SWIR, iterations=2)
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = (nir - red) / np.maximum(1e-6, nir + red)
        fai = nir - (red + (sw - red) * (865 - 665) / (1610 - 665))
        ok = water & bank & ~near_cloud & ~bright & (sw <= dws.SWIR_MAX) & (ndvi <= dws.NDVI_MAX) & (fai <= dws.FAI_MAX) & (red > 0)
    rr, cc = np.nonzero(ok)
    xs, ys = rasterio.transform.xy(tr, rr, cc)
    lon, lat = pyproj.Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True).transform(np.array(xs), np.array(ys))
    return {"lat": np.asarray(lat), "lon": np.asarray(lon), "blue": blue[rr, cc], "green": green[rr, cc], "red": red[rr, cc],
            "re1": re1[rr, cc], "swir": sw[rr, cc]}


def lake_cells(d):
    mx = np.radians(d["lon"]); my = np.log(np.tan(np.pi / 4 + np.radians(d["lat"]) / 2))
    W0, E0 = math.radians(regions._W), math.radians(regions._E)
    N0, S0 = regions._my(regions._N), regions._my(regions._S)
    c = ((mx - W0) / (E0 - W0) * regions.W).astype(int); r = ((N0 - my) / (N0 - S0) * regions.H).astype(int)
    keep = (r >= 0) & (r < regions.H) & (c >= 0) & (c < regions.W)
    keep[keep] = regions.LAKE[r[keep], c[keep]]
    d = {k: v[keep] for k, v in d.items()}
    d["key"] = (r[keep] // B) * 100000 + (c[keep] // B)
    return d


def scene(date):
    its = [f for f in items if f["properties"]["datetime"][:10] == date]
    best = {}
    for f in its:   # one item per tile: the least cloudy
        t = f["properties"]["grid:code"]
        if t not in best or f["properties"]["eo:cloud_cover"] < best[t]["properties"]["eo:cloud_cover"]:
            best[t] = f
    per_tile = {}
    for t, f in sorted(best.items()):
        per_tile[t] = (lake_cells(tile_pixels(f)), f["properties"].get("view:sun_elevation"))
        print(date, t, len(per_tile[t][0]["key"]), flush=True)
    # one tile per block (the one with most pixels), so a block never mixes two tiles' atmospheres
    count = {}
    for t, (d, _) in per_tile.items():
        u, n = np.unique(d["key"], return_counts=True)
        for k, m in zip(u.tolist(), n.tolist()):
            if m > count.get(k, (0, None))[0]:
                count[k] = (m, t)
    rows = []
    for t, (d, sun) in per_tile.items():
        mine = np.array([count[k][1] == t for k in d["key"].tolist()], bool)
        keys = d["key"][mine]; order = np.argsort(keys, kind="stable"); keys = keys[order]
        cols = {k: d[k][mine][order] for k in ("blue", "green", "red", "re1", "swir")}
        u, start, n = np.unique(keys, return_index=True, return_counts=True)
        for k, a0, m in zip(u.tolist(), start.tolist(), n.tolist()):
            if m < 5:
                continue
            rows.append({"br": k // 100000, "bc": k % 100000, "n": m, "sun": sun, "tile": t,
                         **{b: float(np.nanmedian(cols[b][a0:a0 + m])) for b in cols}})
    out = []
    for row in rows:
        row = type('R', (), row)
        raw = {"blue": float(row.blue), "green": float(row.green), "red": float(row.red), "re1": float(row.re1)}
        z, why, _ = P1(raw, row.sun)
        rt = P2.route(raw, row.sun, float(row.swir))
        c3 = models.c3(raw)
        rr_, re_ = max(raw["red"], 0.001), max(raw["re1"], 0.001)
        fnu = float(dws.TURB_A * raw["red"] / max(1e-6, 1 - raw["red"] / dws.TURB_C)) if raw["red"] < dws.TURB_SATURATED else dws.TURB_SATURATED_FNU
        r0, c0 = row.br * B + B // 2, row.bc * B + B // 2
        lat, lon = regions.center(r0, c0)
        wh = regions.where(lat, lon)
        out.append({"date": date, "br": row.br, "bc": row.bc, "lat": round(lat, 6), "lon": round(lon, 6), "n": row.n, "tile": row.tile,
                    "kind": wh["kind"], "arm": wh["arm"], "zone": wh["zone"], "zoneName": wh["zoneName"],
                    "ndci": (re_ - rr_) / (re_ + rr_), "swir": float(row.swir), "re1": raw["re1"], "fnu": fnu,
                    "C0": models.champion(fnu), "C3": c3, "C3dom": models.c3_in_domain(raw, c3),
                    "P1": z, "P1why": why, "P2": rt["ft"], "P2path": rt["path"], "S": rt["S"]})
    with open(f"{S}/stage10/survey/blocks_{date}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print(date, "blocks", len(out), dict(collections.Counter(o["P2path"] for o in out)), flush=True)


os.makedirs(f"{S}/stage10/survey", exist_ok=True)
for d in DATES:
    scene(d)
