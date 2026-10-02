"""Station read-outs from every Sentinel-2 L2A (C1) pass within +-1 day of a Guntersville
station-day. READ-ONLY: imports the production retrieval (engine jobs/lake-surface) and
never writes anywhere but this file's output.

Per (station-day, pass), on the 60 m disk round the station (10 m grid, 3.2 km context so
the cloud / haze gates see what production sees):
  fnu_prod        production-gated turbidity (median of valid pixels) - dws._s2_native_fields
  n_disk/n_valid  pixels in the disk / passing every production gate
  scl_*           SCL class counts in the disk
  drop_*          of the SCL-water pixels in the disk, how many each gate removes (not exclusive)
  rho_*_w         median reflectance over SCL-water pixels (ungated); rho_*_v over valid pixels
  fnu_w / fnu_wl  Dogliotti on SCL-water pixels / on water-like pixels (NDVI < 0) of any class
  aot_site / aot_ctx  Sen2Cor aerosol optical thickness at the station / median over the context
  wvp_site        water vapour
"""
import os, sys, csv, json, math, time, argparse, datetime as dt, threading
import concurrent.futures as cf
import urllib.request

sys.path.insert(0, os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/jobs/lake-surface"))
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF")
os.environ.setdefault("VSI_CACHE", "TRUE")
os.environ.setdefault("GDAL_CACHEMAX", "512")

import numpy as np
import rasterio
import rasterio.windows
import rasterio.warp
import pyproj
from scipy import ndimage
import derive_water_surface as dws

ES_SEARCH = "https://earth-search.aws.element84.com/v1/search"
CONTEXT_M = 1600.0
SITE_RADIUS_M = 60.0
TO_MERC = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
_lock = threading.Lock()
_search_cache = {}


def post(url, body, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def items_near(lat, lon, day, max_dt):
    d0 = (day - dt.timedelta(days=max_dt)).isoformat()
    d1 = (day + dt.timedelta(days=max_dt)).isoformat()
    body = {"collections": [dws.S2_COLLECTION], "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "datetime": f"{d0}T00:00:00Z/{d1}T23:59:59Z", "limit": 50}
    return post(ES_SEARCH, body).get("features", [])


def rho(dn):
    r = dn.astype("float32") * dws.S2_SCALE + dws.S2_OFFSET
    r[(dn == 0) | (dn == 65535)] = np.nan
    return r


def dogliotti(r):
    rr = np.clip(np.nan_to_num(r, nan=0), 0, None)
    return np.where(rr >= dws.TURB_SATURATED, dws.TURB_SATURATED_FNU,
                    dws.TURB_A * rr / np.maximum(1e-6, 1 - rr / dws.TURB_C))


def gate_masks(t):
    """The production gates of dws._s2_native_fields, kept separately (same arithmetic)."""
    h, w = t["red"].shape
    up = lambda x: np.repeat(np.repeat(x, 2, axis=0), 2, axis=1)[:h, :w]
    scl = up(t["scl"])
    r_red = rho(t["red"]); r_nir, r_sw = up(rho(t["nir08"])), up(rho(t["swir16"]))
    water = scl == dws.SCL_WATER
    with np.errstate(invalid="ignore", divide="ignore"):
        fai = r_nir - (r_red + (r_sw - r_red) * (865 - 665) / (1610 - 665))
        ndvi = (r_nir - r_red) / np.maximum(1e-6, r_nir + r_red)
        bright = np.nan_to_num(r_sw, nan=0) > dws.BRIGHT_SWIR
        veg = ndvi >= dws.GRASS_NDVI_MIN
        haze_px = water & (r_sw > dws.HAZE_SWIR) & ~veg
    structure = bright & (np.nan_to_num(ndvi, nan=1.0) < dws.S2_STRUCTURE_NDVI_MAX) & ~water
    haze = bright & water
    bank = np.isin(scl, dws.S2_SCL_BANK)
    px = dws.S2_NATIVE_PX
    E = dws._edge_dist_px
    to_bank, to_structure = E(bank), E(structure)
    cloudy = [c for c in dws.SCL_CLOUDY if c != 0]
    to_cloud = E(np.isin(scl, cloudy))
    clear = to_cloud >= dws.S2_CLOUD_STANDOFF_M / px
    cl20 = np.isin(t["scl"], cloudy)
    lab, n = ndimage.label(cl20)
    if n:
        sizes = ndimage.sum(cl20, lab, index=np.arange(1, n + 1))
        real20 = np.isin(lab, np.nonzero(sizes >= dws.S2_REAL_CLOUD_MIN_PX20)[0] + 1)
    else:
        real20 = cl20
    to_real = E(up(real20))
    near_cloud = to_real < dws.S2_CLOUD_EDGE_M / px
    under_cloud = to_real < dws.S2_REAL_CLOUD_STANDOFF_M / px
    offshore = (to_bank >= dws.S2_CLOUD_EDGE_OFFSHORE_M / px) & (to_structure >= dws.S2_CLOUD_EDGE_OFFSHORE_M / px)
    with np.errstate(invalid="ignore"):
        cloud_edge = near_cloud & offshore & (r_sw > dws.S2_CLOUD_EDGE_SWIR)
        haze_edge = (E(haze_px) < dws.HAZE_EDGE_M / px) & offshore & (r_sw > dws.HAZE_EDGE_SWIR)
    beside_bright = E(haze) < dws.S2_HAZE_STANDOFF_M / px
    with np.errstate(invalid="ignore"):
        g = {"cloud_standoff": ~clear, "under_cloud": under_cloud, "beside_bright": beside_bright,
             "cloud_edge": cloud_edge, "haze_edge": haze_edge,
             "bank": to_bank < dws.S2_BANK_STANDOFF_M / px, "structure": to_structure < dws.S2_STRUCTURE_STANDOFF_M / px,
             "swir": ~(r_sw <= dws.SWIR_MAX), "fai": ~(fai <= dws.FAI_MAX), "ndvi": ~(ndvi <= dws.NDVI_MAX),
             "red_le0": ~(r_red > 0)}
    ok = water.copy()
    for k in g:
        ok &= ~g[k]
    return scl, r_red, r_nir, r_sw, ndvi, water, g, ok


def sample(item, lat, lon):
    x, y = TO_MERC.transform(lon, lat)
    frame = (x - CONTEXT_M, y - CONTEXT_M, x + CONTEXT_M, y + CONTEXT_M)
    t = dws._read_s2_native(item, frame)
    if t["red"].size == 0:
        return None
    fnu_prod, gfrac, readable, hidden, near = dws._s2_native_fields(t)
    scl, r_red, r_nir, r_sw, ndvi, water, g, ok = gate_masks(t)
    to_tile = pyproj.Transformer.from_crs("EPSG:4326", t["crs"], always_xy=True)
    sx, sy = to_tile.transform(lon, lat)
    col, row = ~t["tr10"] * (sx, sy)
    h, w = r_red.shape
    rr = int(math.ceil(SITE_RADIUS_M / 10.0))
    r0, r1 = max(0, int(row) - rr), min(h, int(row) + rr + 1)
    c0, c1 = max(0, int(col) - rr), min(w, int(col) + rr + 1)
    if r0 >= r1 or c0 >= c1:
        return None
    yy, xx = np.mgrid[r0:r1, c0:c1]
    disk = ((yy - row) ** 2 + (xx - col) ** 2 <= (SITE_RADIUS_M / 10.0) ** 2) & (scl[r0:r1, c0:c1] > 0)
    if not disk.any():
        return None
    sl = (slice(r0, r1), slice(c0, c1))
    fp = fnu_prod[sl]; valid = disk & np.isfinite(fp)
    mine = disk & ok[sl]
    wat = disk & water[sl]
    wlike = disk & (np.nan_to_num(ndvi[sl], nan=1) < 0) & ~np.isin(scl[sl], list(dws.SCL_CLOUDY))
    out = {"n_disk": int(disk.sum()), "n_valid": int(valid.sum()), "n_valid_check": int(mine.sum()),
           "n_water": int(wat.sum()), "n_waterlike": int(wlike.sum()),
           "hidden": float(np.nanmean(np.where(disk, hidden[sl], np.nan)))}
    for c in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11):
        out[f"scl_{c}"] = int((disk & (scl[sl] == c)).sum())
    for k, m in g.items():
        out["drop_" + k] = int((wat & m[sl]).sum())
    if valid.any():
        out["fnu_prod"] = float(np.median(fp[valid]))
    rw = r_red[sl]
    if wat.any():
        out["fnu_w"] = float(np.median(dogliotti(rw[wat])))
        out["fnu_w_p90"] = float(np.percentile(dogliotti(rw[wat]), 90))
    if wlike.any():
        out["fnu_wl"] = float(np.median(dogliotti(rw[wlike])))
    a = item["assets"]
    rs = rasterio.open(a["red"]["href"])
    co, ro = ~rs.transform * (t["tr10"].c, t["tr10"].f)
    co, ro = int(round(co)), int(round(ro))
    def read10(key):
        return rho(rasterio.open(a[key]["href"]).read(1, window=rasterio.windows.Window(co + c0, ro + r0, c1 - c0, r1 - r0)))
    def read20(key, scale=None):
        src = rasterio.open(a[key]["href"])
        c20, r20 = (co + c0) // 2, (ro + r0) // 2
        c20e, r20e = (co + c1 + 1) // 2, (ro + r1 + 1) // 2
        raw = src.read(1, window=rasterio.windows.Window(c20, r20, c20e - c20, r20e - r20))
        v = raw.astype("float32") * scale if scale else rho(raw)
        v = np.repeat(np.repeat(v, 2, axis=0), 2, axis=1)
        oy, ox = (ro + r0) - 2 * r20, (co + c0) - 2 * c20
        return v[oy:oy + (r1 - r0), ox:ox + (c1 - c0)]
    bands = {"red": rw, "blue": read10("blue"), "green": read10("green"), "nir": read10("nir"),
             "rededge1": read20("rededge1"), "nir08": r_nir[sl], "swir16": r_sw[sl]}
    for k, v in bands.items():
        for tag, m in (("w", wat), ("v", valid)):
            vv = v[m] if v.shape == m.shape and m.any() else np.array([])
            out[f"rho_{k}_{tag}"] = float(np.nanmedian(vv)) if vv.size else ""
    # aerosol and water vapour (20 m? native 60 m resampled; scale 0.001)
    try:
        aot = read20("aot", 0.001); out["aot_site"] = float(np.nanmedian(aot[disk])) if aot.shape == disk.shape else ""
        wvp = read20("wvp", 0.001); out["wvp_site"] = float(np.nanmedian(wvp[disk])) if wvp.shape == disk.shape else ""
        src = rasterio.open(a["aot"]["href"])
        b = rasterio.warp.transform_bounds("EPSG:3857", src.crs, *frame, densify_pts=21)
        win = rasterio.windows.from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
        v = src.read(1, window=win).astype("float32") * 0.001
        out["aot_ctx"] = float(np.median(v[v > 0])) if (v > 0).any() else ""
    except Exception as e:
        out["aot_err"] = str(e)[:80]
    return out


def one(row, max_dt):
    lat, lon = float(row["lat"]), float(row["lon"])
    day = dt.date.fromisoformat(row["date"])
    try:
        items = items_near(lat, lon, day, max_dt)
    except Exception as e:
        return [{**row, "error": f"search: {e}"}]
    res = []
    for it in items:
        p = it["properties"]
        d = dt.date.fromisoformat(p["datetime"][:10])
        base = {**row, "item": it["id"], "pass_date": d.isoformat(), "pass_time": p["datetime"], "dt_days": (d - day).days,
                "platform": p.get("platform"), "tile": p.get("grid:code"), "baseline": p.get("s2:processing_baseline"),
                "scene_cloud": p.get("eo:cloud_cover"), "sun_elev": p.get("view:sun_elevation"),
                "view_inc": p.get("view:incidence_angle")}
        try:
            s = sample(it, lat, lon)
        except Exception as e:
            res.append({**base, "error": f"read: {str(e)[:120]}"})
            continue
        if s is None:
            continue
        res.append({**base, **s})
    return res or [{**row, "error": "no pass"}]


COLS = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--max-dt", type=int, default=1)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.inp)))
    done = set()
    if os.path.exists(a.out):
        done = {r["id"] for r in csv.DictReader(open(a.out))}
    rows = [r for r in rows if r["id"] not in done]
    base_cols = list(rows[0].keys()) if rows else []
    extra = ["item", "pass_date", "pass_time", "dt_days", "platform", "tile", "baseline", "scene_cloud", "sun_elev", "view_inc",
             "n_disk", "n_valid", "n_valid_check", "n_water", "n_waterlike", "hidden"] + \
            [f"scl_{c}" for c in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)] + \
            ["drop_" + k for k in ("cloud_standoff", "under_cloud", "beside_bright", "cloud_edge", "haze_edge", "bank", "structure",
                                   "swir", "fai", "ndvi", "red_le0")] + \
            ["fnu_prod", "fnu_w", "fnu_w_p90", "fnu_wl"] + \
            [f"rho_{k}_{t}" for k in ("red", "blue", "green", "nir", "rededge1", "nir08", "swir16") for t in ("w", "v")] + \
            ["aot_site", "aot_ctx", "wvp_site", "aot_err", "error"]
    new = not os.path.exists(a.out)
    fh = open(a.out, "a", newline="")
    wr = csv.DictWriter(fh, fieldnames=base_cols + extra, extrasaction="ignore")
    if new:
        wr.writeheader()
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(one, r, a.max_dt): r for r in rows}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            try:
                out = fut.result()
            except Exception as e:
                out = [{**futs[fut], "error": f"crash: {str(e)[:120]}"}]
            with _lock:
                for o in out:
                    wr.writerow(o)
                fh.flush()
            if i % 25 == 0:
                print(f"{i}/{len(rows)} in {time.time() - t0:.0f}s", flush=True)
    fh.close()
    print("finished", flush=True)


if __name__ == "__main__":
    main()
