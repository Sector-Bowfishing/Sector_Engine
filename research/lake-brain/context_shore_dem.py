#!/usr/bin/env python3
"""Track 7: shoreline slope proxy from the USGS 3DEP seamless DEM (ImageServer/getSamples), sampled along the polygon shoreline.
For N shore points (every perimeter/N along every ring), sample the DEM at outward offsets (10,30,60,100 m); outward = away from water.
Per lake: median / quartiles of the 10->60 m slope (deg), fraction of shoreline flatter than 2 deg and steeper than 8 deg,
median horizontal run per vertical foot of pool change (ft/ft = 1/tan(slope)), mean bank rise at 30 m.
Output: <DATA>/context/shore_dem.json (rebuildable). Polite: 1 request/s, <=1000 points/request."""
import gzip, json, math, sys, time
from pathlib import Path
import numpy as np, requests, shapely
from pyproj import Transformer
from shapely.geometry import shape, Point, MultiPolygon, Polygon
from shapely.ops import unary_union

DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/getSamples"
OFFS = [10, 30, 60, 100]


def rings(g):
    for p in (g.geoms if hasattr(g, "geoms") else [g]):
        if isinstance(p, Polygon):
            yield p.exterior
            for i in p.interiors: yield i


def shore_points(g, n):
    rs = [r for r in rings(g) if r.length > 300]
    tot = sum(r.length for r in rs); step = tot / n
    pts = []
    for r in rs:
        k = max(1, int(r.length / step))
        for i in range(k):
            s = (i + 0.5) * r.length / k
            a = r.interpolate(s); b = r.interpolate(min(s + 20, r.length)); c = r.interpolate(max(s - 20, 0))
            tx, ty = b.x - c.x, b.y - c.y; L = math.hypot(tx, ty)
            if L == 0: continue
            pts.append((a.x, a.y, -ty / L, tx / L))
    return pts


def sample(points_ll):
    out = []
    for i in range(0, len(points_ll), 800):
        chunk = points_ll[i:i + 800]
        for attempt in range(4):
            try:
                r = requests.post(URL, data=dict(geometry=json.dumps({"points": chunk, "spatialReference": {"wkid": 4326}}), geometryType="esriGeometryMultipoint",
                                                 returnFirstValueOnly="true", f="json"), timeout=120).json()
                s = r["samples"]; break
            except Exception as e:
                time.sleep(3 * (attempt + 1)); s = None
        if s is None: raise RuntimeError("DEM sampling failed")
        byid = {x["locationId"]: x for x in s}
        for j in range(len(chunk)):
            x = byid.get(j)
            try: out.append((float(x["value"]), x.get("resolution")))
            except Exception: out.append((np.nan, None))
        time.sleep(1.0)
    return out


def lake(lid, geom, n=700):
    c = geom.centroid
    fw = Transformer.from_crs("EPSG:4326", f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", always_xy=True)
    bw = Transformer.from_crs(f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", "EPSG:4326", always_xy=True)
    g = shapely.transform(geom, lambda a: np.column_stack(fw.transform(a[:, 0], a[:, 1]))).buffer(0)
    gs = g.simplify(15)
    sp = shore_points(gs, n)
    # orient outward: test a 30 m offset point is outside the (unsimplified) water polygon
    P = []
    for x, y, nx, ny in sp:
        if g.contains(Point(x + 30 * nx, y + 30 * ny)): nx, ny = -nx, -ny
        if g.contains(Point(x + 30 * nx, y + 30 * ny)): continue   # ambiguous (narrow channel / island): skip
        P.append((x, y, nx, ny))
    lonlat = []
    for x, y, nx, ny in P:
        for d in OFFS:
            lonlat.append(list(bw.transform(x + d * nx, y + d * ny)))
    vals = sample(lonlat)
    z = np.array([v[0] for v in vals]).reshape(len(P), len(OFFS)); res = [v[1] for v in vals]
    ok = np.isfinite(z).all(axis=1) & (z > -100).all(axis=1)
    z = z[ok]
    slope = np.degrees(np.arctan((z[:, 2] - z[:, 0]) / 50.0))     # 10 -> 60 m
    slope2 = np.degrees(np.arctan((z[:, 3] - z[:, 1]) / 70.0))    # 30 -> 100 m
    rise30 = z[:, 1] - z[:, 0]
    tanb = np.tan(np.radians(np.clip(slope, 0.2, 89)))
    run_ft_per_ft = 1.0 / tanb
    res_c = {}
    for r in res: res_c[str(r)] = res_c.get(str(r), 0) + 1
    return dict(n_points=int(ok.sum()), n_requested=len(P), slope_med=float(np.median(slope)), slope_p25=float(np.percentile(slope, 25)), slope_p75=float(np.percentile(slope, 75)),
                slope2_med=float(np.median(slope2)), frac_lt2deg=float((slope < 2).mean()), frac_2_8deg=float(((slope >= 2) & (slope < 8)).mean()), frac_gt8deg=float((slope >= 8).mean()),
                frac_neg=float((slope < 0).mean()), run_per_ft_med=float(np.median(np.clip(run_ft_per_ft, 0, 500))), run_per_ft_mean=float(np.mean(np.clip(run_ft_per_ft, 0, 500))),
                bank_rise30_med_m=float(np.median(rise30)), perim_km=float(sum(r.length for r in rings(g)) / 1e3), dem_resolution_counts=res_c)


if __name__ == "__main__":
    ids = json.load(open(sys.argv[1][1:])) if len(sys.argv) > 1 and sys.argv[1].startswith("@") else (sys.argv[1:] or ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"])
    pg = json.load(gzip.open(DATA / "geometry/engine_polygons_599.geojson.gz"))
    pm = {f["properties"]["id"]: shape(f["geometry"]) for f in pg["features"]}
    import os
    outp = DATA / ("context/" + os.environ.get("SHORE_OUT", "shore_dem.json"))
    out = json.load(open(outp)) if outp.exists() else {}
    for lid in ids:
        t = time.time(); out[lid] = lake(lid, pm[lid]); outp.write_text(json.dumps(out, indent=1))
        print(lid, round(time.time() - t), json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in out[lid].items()}), flush=True)
