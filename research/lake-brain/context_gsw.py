#!/usr/bin/env python3
"""Track 7: JRC Global Surface Water (v1.4, 1984-2021, 30 m) occurrence/seasonality statistics per lake polygon.
Tiles are 10x10 degrees; this run covers the tile(s) present in <DATA>/context/gsw (default 90W_40N: SE US).
Per lake: area with occurrence>=95 % (permanent water), 5-95 % (fluctuating) inside the polygon and in a 150 m outside ring,
and area that is open water <12 months/yr (seasonality 1-11).  Output <DATA>/context/gsw_features.json (rebuildable)."""
import gzip, json, sys
from pathlib import Path
import numpy as np, rasterio, shapely
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from pyproj import Transformer
from shapely.geometry import shape

DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
TILE = "90W_40N"; BOUNDS = (-90, 30, -80, 40)
PX = 30.0


def main():
    occ = rasterio.open(DATA / f"context/gsw/occurrence_{TILE}v1_4_2021.tif"); sea = rasterio.open(DATA / f"context/gsw/seasonality_{TILE}v1_4_2021.tif")
    pg = json.load(gzip.open(DATA / "geometry/engine_polygons_599.geojson.gz"))
    res = {}
    for f in pg["features"]:
        lid = f["properties"]["id"]; g = shape(f["geometry"])
        b = g.bounds
        if not (b[0] > BOUNDS[0] + 0.01 and b[2] < BOUNDS[2] - 0.01 and b[1] > BOUNDS[1] + 0.01 and b[3] < BOUNDS[3] - 0.01): continue
        c = g.centroid
        fw = Transformer.from_crs("EPSG:4326", f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", always_xy=True)
        bw = Transformer.from_crs(f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", "EPSG:4326", always_xy=True)
        gm = shapely.transform(g, lambda a: np.column_stack(fw.transform(a[:, 0], a[:, 1]))).buffer(0)
        ring = gm.buffer(150, quad_segs=2)
        ringll = shapely.transform(ring, lambda a: np.column_stack(bw.transform(a[:, 0], a[:, 1])))
        gll = g
        rb = ringll.bounds
        win = from_bounds(rb[0], rb[1], rb[2], rb[3], occ.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, occ.width, occ.height))
        O = occ.read(1, window=win); S = sea.read(1, window=win)
        tr = occ.window_transform(win)
        inside = geometry_mask([gll], O.shape, tr, invert=True)
        ringm = geometry_mask([ringll], O.shape, tr, invert=True) & ~inside
        # pixel area at this latitude
        pxa = (PX * np.cos(np.radians(c.y)) ** 0 ) ** 2  # ~0.00025deg = 27.8 m N-S; E-W scaled
        ew = 0.00025 * 111320 * np.cos(np.radians(c.y)); ns = 0.00025 * 110574
        pxk = ew * ns / 1e6
        A = inside.sum() * pxk
        r = dict(gsw_poly_km2=float(A), gsw_perm_km2=float(((O >= 95) & inside).sum() * pxk), gsw_fluct_in_frac=float(((O >= 5) & (O < 95) & inside).sum() / max(inside.sum(), 1)),
                 gsw_lowocc_in_frac=float(((O >= 1) & (O < 50) & inside).sum() / max(inside.sum(), 1)),
                 gsw_fluct_ring_km2=float(((O >= 5) & (O < 95) & ringm).sum() * pxk), gsw_ring_wet_km2=float(((O >= 5) & ringm).sum() * pxk),
                 gsw_seasonal_in_frac=float(((S >= 1) & (S <= 11) & inside).sum() / max(inside.sum(), 1)),
                 gsw_nodata_in_frac=float((O == 255).sum() / max(O.size, 1)))
        r["gsw_fluct_ring_to_poly"] = r["gsw_fluct_ring_km2"] / A if A else None
        res[lid] = r
        print(lid, {k: round(v, 3) for k, v in r.items()}, flush=True)
    (DATA / "context/gsw_features.json").write_text(json.dumps(res))
    print("lakes", len(res))


if __name__ == "__main__":
    main()
