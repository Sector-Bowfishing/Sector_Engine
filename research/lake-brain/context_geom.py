#!/usr/bin/env python3
"""Lake Brain context track: cheap polygon-derived morphometry for every directory lake.

Inputs : directory snapshot + engine polygons (see README) -- read-only.
Output : <DATA>/context/geom_features.json  (rebuildable; merged by context_features.py)
All geometry maths is done in a per-lake Lambert azimuthal equal-area projection.
"""
import gzip, json, math, sys, time
from pathlib import Path
import numpy as np
from pyproj import Transformer
from shapely.geometry import shape, Polygon, MultiPolygon
import shapely
from shapely.ops import unary_union

DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
POLY = DATA / "geometry/engine_polygons_599.geojson.gz"
OUT = DATA / "context/geom_features.json"


def load_polys():
    g = json.load(gzip.open(POLY))
    return {f["properties"]["id"]: (shape(f["geometry"]), f["properties"]) for f in g["features"]}


def parts(g):
    if isinstance(g, Polygon):
        return [g] if not g.is_empty else []
    return [q for x in getattr(g, "geoms", []) for q in parts(x)]


def feats(geom, props):
    c = geom.centroid
    tr = Transformer.from_crs("EPSG:4326", f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", always_xy=True)
    g = shapely.transform(geom, lambda a: np.column_stack(tr.transform(a[:, 0], a[:, 1])))
    if not g.is_valid:
        g = g.buffer(0)
    g = unary_union(parts(g))
    A = g.area
    P = g.length                      # exterior + interior rings (islands included)
    ps = sorted(parts(g), key=lambda p: -p.area)
    big = ps[0]
    holes = sum(len(p.interiors) for p in ps)
    Pext = sum(p.exterior.length for p in ps)
    hull = g.convex_hull
    mrr = g.minimum_rotated_rectangle
    xs, ys = mrr.exterior.coords.xy
    e1 = math.hypot(xs[1] - xs[0], ys[1] - ys[0]); e2 = math.hypot(xs[2] - xs[1], ys[2] - ys[1])
    L, W = max(e1, e2), min(e1, e2)
    out = dict(
        area_km2=A / 1e6, perim_km=P / 1e3, sdi=P / (2 * math.sqrt(math.pi * A)), sdi_ext=Pext / (2 * math.sqrt(math.pi * A)),
        n_parts=len(ps), n_islands=holes, big_part_frac=big.area / A,
        solidity=A / hull.area, elong=L / max(W, 1.0), bbox_len_km=L / 1e3,
    )
    # distance-to-shore bands (shore = all rings, islands included): fraction of area within d of any shore
    bnd = g.boundary
    for d in (50, 100, 250):
        inner = g.buffer(-d, quad_segs=2)
        out[f"frac_within_{d}m"] = 1 - inner.area / A
    # arm / narrow-water fraction: area lost by morphological opening with radius r (water narrower than 2r)
    for r in (150, 400):
        opened = g.buffer(-r, quad_segs=2).buffer(r, quad_segs=2)
        out[f"frac_narrow_{2*r}m"] = max(0.0, 1 - opened.intersection(g).area / A)
    # arm count at 300 m: components of (g - opened150) with area > 0.05 km2 and elongated
    opened = g.buffer(-150, quad_segs=2).buffer(150, quad_segs=2)
    resid = g.difference(opened.buffer(2))
    arms = [p for p in parts(resid) if p.area > 50_000 and p.length ** 2 / max(p.area, 1) > 40]
    out["n_narrow_arms"] = len(arms)
    out["narrow_arm_len_km"] = sum(p.length / 2 for p in arms) / 1e3
    return out


def main():
    polys = load_polys(); res = {}
    t = time.time()
    for i, (k, (g, p)) in enumerate(sorted(polys.items(), key=lambda kv: kv[0])):
        try:
            r = feats(g, p); r["poly_source"] = p.get("source"); r["poly_trimmed"] = bool(p.get("trimmed")); res[k] = r
        except Exception as e:
            res[k] = {"error": repr(e)}
        if i % 50 == 0: print(i, k, round(time.time() - t, 1), file=sys.stderr)
    OUT.write_text(json.dumps(res))
    print("wrote", OUT, len(res))


if __name__ == "__main__":
    main()
