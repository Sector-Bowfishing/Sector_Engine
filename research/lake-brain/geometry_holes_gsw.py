#!/usr/bin/env python3
"""Are the interior rings ("holes") of an Engine lake polygon islands, or artifacts?
Independent check against JRC Global Surface Water 'occurrence' (30 m, 1984-2021, % of valid observations with water),
read by HTTP range request from the public tile (no download of the full tile).
usage: geometry_holes_gsw.py "Guntersville|AL" ...   (needs rasterio: use the venv under <DATA>/geometry/venv)
"""
import gzip, json, os, sys
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import shape, Polygon
from shapely import affinity  # noqa

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
POLY = os.path.join(REPO, "jobs", "lake-surface", "polygons.geojson.gz")
URL = "https://storage.googleapis.com/global-surface-water/downloads2021/occurrence/occurrence_{lon}_{lat}v1_4_2021.tif"


def tile(lon, lat):
    w = int(np.floor(lon / 10) * 10); n = int(np.ceil(lat / 10) * 10)
    return URL.format(lon=f"{abs(w)}{'W' if w < 0 else 'E'}", lat=f"{abs(n)}{'N' if n >= 0 else 'S'}")


def main(ids):
    feats = {f["properties"]["id"]: f for f in json.load(gzip.open(POLY, "rt"))["features"]}
    out = {}
    for lid in ids:
        g = shape(feats[lid]["geometry"]).buffer(0)
        w, s, e, n = g.bounds
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
            with rasterio.open(tile((w + e) / 2, (s + n) / 2)) as ds:
                win = from_bounds(w, s, e, n, ds.transform)
                a = ds.read(1, window=win, boundless=False)
                tf = ds.window_transform(win)
        polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
        holes = [Polygon(r) for p in polys for r in p.interiors]
        # coarse test: a hole is 'water-like' if its mean occurrence >= 50
        res = {"n_holes": len(holes), "px_m": 30, "classes": {"land(<20)": 0, "mixed(20-50)": 0, "water-like(>=50)": 0, "sub-pixel(<2 px)": 0}, "area_km2": {"land(<20)": 0, "mixed(20-50)": 0, "water-like(>=50)": 0, "sub-pixel(<2 px)": 0}}
        # occurrence 255 = no data; treat as missing
        lat0 = (s + n) / 2
        m2 = (111320 * np.cos(np.radians(lat0))) * 110540
        for h in holes:
            ar = h.area * m2
            m = geometry_mask([h.__geo_interface__], out_shape=a.shape, transform=tf, invert=True)
            if m.sum() < 2:
                k = "sub-pixel(<2 px)"
            else:
                v = a[m]; v = v[v != 255]
                mean = float(v.mean()) if v.size else -1
                k = "land(<20)" if 0 <= mean < 20 else ("mixed(20-50)" if mean < 50 else "water-like(>=50)")
            res["classes"][k] += 1; res["area_km2"][k] += ar / 1e6
        # control: lake interior (occurrence should be ~100)
        inside = geometry_mask([g.__geo_interface__], out_shape=a.shape, transform=tf, invert=True)
        v = a[inside]; v = v[v != 255]
        res["lake_mean_occurrence"] = round(float(v.mean()), 1); res["lake_pct_ge90"] = round(float((v >= 90).mean()) * 100, 1)
        res["area_km2"] = {k: round(x, 3) for k, x in res["area_km2"].items()}
        out[lid] = res
        print(lid, json.dumps(res), flush=True)
    return out


if __name__ == "__main__":
    r = main(sys.argv[1:])
    if os.environ.get("OUT"):
        json.dump(r, open(os.environ["OUT"], "w"), indent=1)
