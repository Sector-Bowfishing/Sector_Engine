"""Stage 11 supplementary read-out for a chosen pass: the bands and geometry the frozen extractor does not record.
Same 60 m disk and the same production valid-pixel mask as stage6/extract.sample (imported read-only; this file
never changes it). Adds: B01, B06, B07, B12 medians over valid pixels; the glint angle from the item's mean solar and
viewing geometry; the distance from the station to the nearest non-water pixel of the scene's own SCL within 2 km;
and the pass's time. Used by the Stage 11 corpus only."""
import os, sys, math, json
import numpy as np, rasterio, pyproj
from scipy import ndimage
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage6"); _argv = sys.argv; sys.argv = ["x"]
import extract as EX
sys.argv = _argv
dws = EX.dws


def glint_angle(sun_elev, sun_az, view_inc, view_az):
    if None in (sun_elev, sun_az, view_inc, view_az):
        return None
    ts, tv = math.radians(90 - sun_elev), math.radians(view_inc)
    c = math.cos(ts) * math.cos(tv) - math.sin(ts) * math.sin(tv) * math.cos(math.radians(sun_az - view_az))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def item_by_id(iid):
    d = EX.post(EX.ES_SEARCH, {"collections": [dws.S2_COLLECTION], "ids": [iid], "limit": 1})
    f = d.get("features", [])
    return f[0] if f else None


def sample_plus(item, lat, lon):
    x, y = EX.TO_MERC.transform(lon, lat)
    frame = (x - EX.CONTEXT_M, y - EX.CONTEXT_M, x + EX.CONTEXT_M, y + EX.CONTEXT_M)
    t = dws._read_s2_native(item, frame)
    if t["red"].size == 0:
        return None
    scl, r_red, r_nir, r_sw, ndvi, water, g, ok = EX.gate_masks(t)
    to_tile = pyproj.Transformer.from_crs("EPSG:4326", t["crs"], always_xy=True)
    sx, sy = to_tile.transform(lon, lat)
    col, row = ~t["tr10"] * (sx, sy)
    h, w = r_red.shape
    rr = int(math.ceil(EX.SITE_RADIUS_M / 10.0))
    r0, r1 = max(0, int(row) - rr), min(h, int(row) + rr + 1)
    c0, c1 = max(0, int(col) - rr), min(w, int(col) + rr + 1)
    if r0 >= r1 or c0 >= c1:
        return None
    yy, xx = np.mgrid[r0:r1, c0:c1]
    disk = ((yy - row) ** 2 + (xx - col) ** 2 <= (EX.SITE_RADIUS_M / 10.0) ** 2) & (scl[r0:r1, c0:c1] > 0)
    fp = dws._s2_native_fields(t)[0]
    sl = (slice(r0, r1), slice(c0, c1))
    valid = disk & np.isfinite(fp[sl])
    out = {"n_valid_plus": int(valid.sum())}
    # distance to the nearest non-water (SCL != 6, excluding no-data) pixel, capped at the 3.2 km context
    nonwater = (scl != dws.SCL_WATER) & (scl > 0)
    if nonwater.any():
        dist = ndimage.distance_transform_edt(~nonwater) * 10.0
        out["dist_nonwater_m"] = float(min(dist[int(row), int(col)] if 0 <= int(row) < h and 0 <= int(col) < w else np.nan, 2000.0))
    else:
        out["dist_nonwater_m"] = 2000.0
    a = item["assets"]
    rs = rasterio.open(a["red"]["href"])
    co, ro = ~rs.transform * (t["tr10"].c, t["tr10"].f)
    co, ro = int(round(co)), int(round(ro))
    def readN(key, f):
        src = rasterio.open(a[key]["href"])
        cN, rN = (co + c0) // f, (ro + r0) // f
        cNe, rNe = (co + c1 + f - 1) // f, (ro + r1 + f - 1) // f
        raw = src.read(1, window=rasterio.windows.Window(cN, rN, cNe - cN, rNe - rN))
        v = EX.rho(raw)
        v = np.repeat(np.repeat(v, f, axis=0), f, axis=1)
        oy, ox = (ro + r0) - f * rN, (co + c0) - f * cN
        return v[oy:oy + (r1 - r0), ox:ox + (c1 - c0)]
    for key, f in (("coastal", 6), ("rededge2", 2), ("rededge3", 2), ("swir22", 2), ("nir09", 6)):
        try:
            v = readN(key, f)
            vv = v[valid] if v.shape == valid.shape and valid.any() else np.array([])
            out[f"rho_{key}_v"] = float(np.nanmedian(vv)) if vv.size else None
        except Exception as e:
            out[f"rho_{key}_v"] = None
    p = item["properties"]
    out.update({"pass_time": p["datetime"], "sun_az": p.get("view:sun_azimuth"), "sun_elev": p.get("view:sun_elevation"),
                "view_inc": p.get("view:incidence_angle"), "view_az": p.get("view:azimuth"),
                "glint_deg": glint_angle(p.get("view:sun_elevation"), p.get("view:sun_azimuth"), p.get("view:incidence_angle"), p.get("view:azimuth")),
                "baseline": p.get("s2:processing_baseline"), "platform": p.get("platform")})
    return out
