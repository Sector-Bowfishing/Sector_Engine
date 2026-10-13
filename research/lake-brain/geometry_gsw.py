#!/usr/bin/env python3
"""Independent per-lake check of each Engine polygon against JRC Global Surface Water 'occurrence' (30 m, 1984-2021).
For every Engine polygon:
  gsw_inside_ge50_pct   share of polygon pixels that were water in >=50% of valid observations (precision proxy)
  gsw_inside_lt10_pct   share that were water <10% of the time (polygon generous / land inside)
  gsw_ring_water_km2    pixels with occurrence >=75 in a 300 m ring OUTSIDE the polygon (what the polygon misses)
  gsw_miss_pct          ring water / (inside water + ring water)  (recall proxy; neighbours in the ring inflate it)
Needs rasterio (venv at <DATA>/geometry/venv) and the occurrence tiles in <DATA>/geometry/gsw/ (see tile list in the script;
download URL pattern https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_<lon>_<lat>v1_4_2021.tif).
Writes <DATA>/geometry/gsw_metrics.json (merged into the flags CSV by geometry_audit.py --stage gsw).
"""
import gzip, json, math, os, sys
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import shape

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.environ.get("LAKE_BRAIN_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
TILES = os.path.join(DATA, "geometry", "gsw")


def tile_path(lon, lat):
    w = int(math.floor(lon / 10) * 10); n = int(math.ceil(lat / 10) * 10)
    return os.path.join(TILES, f"occurrence_{abs(w)}{'W' if w < 0 else 'E'}_{abs(n)}{'N' if n >= 0 else 'S'}v1_4_2021.tif")


def lake_metrics(feat):
    g = shape(feat["geometry"]).buffer(0)
    if g.geom_type == "GeometryCollection":
        g = shapely_union_polys(g)
    w, s, e, n = g.bounds
    pad = 0.006
    p = tile_path((w + e) / 2, (s + n) / 2)
    if not os.path.exists(p):
        return {"gsw_error": "tile missing"}
    with rasterio.open(p) as ds:
        win = from_bounds(w - pad, s - pad, e + pad, n + pad, ds.transform).round_offsets().round_lengths()
        a = ds.read(1, window=win, boundless=True, fill_value=255)
        tf = ds.window_transform(win)
    lat0 = (s + n) / 2
    px_m2 = abs(tf.a) * 111320 * math.cos(math.radians(lat0)) * abs(tf.e) * 110540
    inside = geometry_mask([g.__geo_interface__], out_shape=a.shape, transform=tf, invert=True)
    ring_g = g.buffer(300 / 111000.0).difference(g)
    ring = geometry_mask([ring_g.__geo_interface__], out_shape=a.shape, transform=tf, invert=True) & ~inside
    v = a[inside]; v = v[v != 255]
    r = a[ring]; r = r[r != 255]
    if v.size == 0:
        return {"gsw_error": "no valid pixels"}
    iw = float((v >= 50).sum()) * px_m2 / 1e6
    rw = float((r >= 75).sum()) * px_m2 / 1e6
    return {"gsw_inside_ge50_pct": round(float((v >= 50).mean()) * 100, 1), "gsw_inside_lt10_pct": round(float((v < 10).mean()) * 100, 1),
            "gsw_inside_mean": round(float(v.mean()), 1), "gsw_ring_water_km2": round(rw, 3),
            "gsw_miss_pct": round(100 * rw / (iw + rw), 1) if iw + rw > 0 else None, "gsw_valid_px": int(v.size)}


def shapely_union_polys(gc):
    from shapely.ops import unary_union
    return unary_union([x for x in gc.geoms if x.geom_type in ("Polygon", "MultiPolygon")])


def main():
    feats = json.load(gzip.open(os.path.join(REPO, "jobs", "lake-surface", "polygons.geojson.gz"), "rt"))["features"]
    ids = set(sys.argv[1:])
    out = {}
    for i, f in enumerate(feats):
        lid = f["properties"]["id"]
        if ids and lid not in ids:
            continue
        try:
            out[lid] = lake_metrics(f)
        except Exception as ex:  # noqa: BLE001
            out[lid] = {"gsw_error": str(ex)[:80]}
        if (i + 1) % 50 == 0:
            print(i + 1, flush=True)
    json.dump(out, open(os.path.join(DATA, "geometry", "gsw_metrics.json"), "w"))
    print("done", len(out))


if __name__ == "__main__":
    main()
