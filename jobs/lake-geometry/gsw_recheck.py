#!/usr/bin/env python3
"""Optional QA pass: JRC Global Surface Water (occurrence 1984-2021) inside-share on the NEW shorelines.

Needs rasterio (the research venv: <DATA>/geometry/venv) and the occurrence tiles in <DATA>/geometry/gsw/.
Reads <out>/lakes/*/geometry.v1.analysis.geojson.gz, writes <DATA>/geometry/gsw_registry_v1.json
({lakeId: {gsw_inside_ge50_pct, gsw_inside_mean, gsw_valid_px}}). build_geometry.py reads it on its next run so the
confidence re-derivation uses the measurement of the union, not of the old Engine polygon.
  <DATA>/geometry/venv/bin/python gsw_recheck.py [--out DIR]
"""
import argparse, glob, gzip, json, math, os
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import shape

DATA = os.environ.get("LAKE_BRAIN_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
TILES = os.path.join(DATA, "geometry", "gsw")


def tile_path(lon, lat):
    w = int(math.floor(lon / 10) * 10); n = int(math.ceil(lat / 10) * 10)
    return os.path.join(TILES, f"occurrence_{abs(w)}{'W' if w < 0 else 'E'}_{abs(n)}{'N' if n >= 0 else 'S'}v1_4_2021.tif")


def measure(g):
    w, s, e, n = g.bounds
    p = tile_path((w + e) / 2, (s + n) / 2)
    if not os.path.exists(p):
        return {"gsw_error": "tile missing"}
    pad = 0.002
    with rasterio.open(p) as ds:
        win = from_bounds(w - pad, s - pad, e + pad, n + pad, ds.transform).round_offsets().round_lengths()
        a = ds.read(1, window=win, boundless=True, fill_value=255)
        tf = ds.window_transform(win)
    inside = geometry_mask([g.__geo_interface__], out_shape=a.shape, transform=tf, invert=True)
    v = a[inside]; v = v[v != 255]
    if v.size == 0:
        return {"gsw_error": "no valid pixels"}
    return {"gsw_inside_ge50_pct": round(float((v >= 50).mean()) * 100, 1), "gsw_inside_mean": round(float(v.mean()), 1), "gsw_valid_px": int(v.size)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(DATA, "geometry", "registry_out"))
    a = ap.parse_args()
    res = {}
    for p in sorted(glob.glob(os.path.join(a.out, "lakes", "*", "geometry.v1.analysis.geojson.gz"))):
        f = json.load(gzip.open(p, "rt"))
        lid = f["properties"]["lakeId"]
        try:
            res[lid] = measure(shape(f["geometry"]))
        except Exception as ex:  # noqa: BLE001
            res[lid] = {"gsw_error": str(ex)[:80]}
    json.dump(res, open(os.path.join(DATA, "geometry", "gsw_registry_v1.json"), "w"))
    print("lakes", len(res), "errors", sum(1 for v in res.values() if "gsw_error" in v))


if __name__ == "__main__":
    main()
