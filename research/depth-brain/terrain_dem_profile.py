#!/usr/bin/env python3
"""Depth Brain / terrain: extended 3DEP shoreline profile. For each lake polygon, N shore points (evenly along every ring > 300 m), outward normal,
DEM sampled (USGS 3DEP ImageServer getSamples) at OFFS metres outside the shoreline.  Raw per-point arrays are saved (npz) so per-segment analysis
can be done without re-querying.  Extends research/lake-brain/context_shore_dem.py (4 offsets to 100 m) to 10 offsets to 200 m.
Usage: terrain_dem_profile.py <polys.json>   # {lake_id: path-to-geojson-or-'engine'} ; polygons in EPSG:4326
Output: <RAW>/dem/<safe_id>.npz.  Polite: 1 request/s, <= 800 points per request."""
import gzip, json, math, re, sys, time
from pathlib import Path
import numpy as np, requests, shapely
from pyproj import Transformer
from shapely.geometry import shape, Point, Polygon

RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/getSamples"
import os
OFFS = [int(x) for x in os.environ.get("DEM_OFFS", "5,10,20,30,45,60,80,100,150,200").split(",")]
NPTS = int(os.environ.get("DEM_N", "600"))
SPACING = float(os.environ.get("DEM_SPACING_M", "0"))      # >0: one shore point per SPACING metres (capped at 9000 points)
OUTSUB = os.environ.get("DEM_OUT", "dem")

def rings(g):
    for p in (g.geoms if hasattr(g, "geoms") else [g]):
        if isinstance(p, Polygon):
            yield p.exterior
            for i in p.interiors: yield i

def shore_points(g, n):
    rs = [r for r in rings(g) if r.length > 300]
    tot = sum(r.length for r in rs); step = tot / n; pts = []
    for ri, r in enumerate(rs):
        k = max(1, int(r.length / step))
        for i in range(k):
            s = (i + 0.5) * r.length / k
            a = r.interpolate(s); b = r.interpolate(min(s + 20, r.length)); c = r.interpolate(max(s - 20, 0))
            tx, ty = b.x - c.x, b.y - c.y; L = math.hypot(tx, ty)
            if L == 0: continue
            pts.append((a.x, a.y, -ty / L, tx / L, ri, s))
    return pts

def _chunk(chunk):
    for attempt in range(6):
        try:
            r = requests.post(URL, data=dict(geometry=json.dumps({"points": chunk, "spatialReference": {"wkid": 4326}}), geometryType="esriGeometryMultipoint",
                                             returnFirstValueOnly="true", f="json"), timeout=180).json()
            byid = {x["locationId"]: x for x in r["samples"]}; out = []
            for j in range(len(chunk)):
                x = byid.get(j)
                try: out.append((float(x["value"]), float(x.get("resolution") or np.nan)))
                except Exception: out.append((np.nan, np.nan))
            return out
        except Exception: time.sleep(3 * (attempt + 1))
    raise RuntimeError("DEM sampling failed")

def sample(points_ll):
    """latency-bound service (~7 s/request): 6 concurrent requests of <= 800 points"""
    from concurrent.futures import ThreadPoolExecutor
    chunks = [points_ll[i:i + 800] for i in range(0, len(points_ll), 800)]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(_chunk, chunks))
    return [v for r in res for v in r]

def profile(geom, n=None):
    n = n or NPTS
    c = geom.centroid
    prj = f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m"
    fw = Transformer.from_crs("EPSG:4326", prj, always_xy=True); bw = Transformer.from_crs(prj, "EPSG:4326", always_xy=True)
    g = shapely.transform(geom, lambda a: np.column_stack(fw.transform(a[:, 0], a[:, 1]))).buffer(0)
    gs_ = g.simplify(15)
    if SPACING > 0:
        n = int(min(9000, max(200, sum(r.length for r in rings(gs_) if r.length > 300) / SPACING)))
    sp = shore_points(gs_, n); P = []
    for x, y, nx, ny, ri, s in sp:
        if g.contains(Point(x + 30 * nx, y + 30 * ny)): nx, ny = -nx, -ny
        if g.contains(Point(x + 30 * nx, y + 30 * ny)): continue
        P.append((x, y, nx, ny, ri, s))
    ll = []
    for x, y, nx, ny, ri, s in P:
        for d in OFFS: ll.append(list(bw.transform(x + d * nx, y + d * ny)))
    v = sample(ll)
    z = np.array([a[0] for a in v]).reshape(len(P), len(OFFS)); res = np.array([a[1] for a in v]).reshape(len(P), len(OFFS))
    xy = np.array([[p[0], p[1]] for p in P]); ring = np.array([p[4] for p in P]); sarc = np.array([p[5] for p in P])
    lon, lat = bw.transform(xy[:, 0], xy[:, 1])
    return dict(z=z, res=res, x=xy[:, 0], y=xy[:, 1], lon=np.array(lon), lat=np.array(lat), ring=ring, s=sarc, offs=np.array(OFFS), clon=c.x, clat=c.y)

def safe(i): return re.sub(r"[^A-Za-z0-9]+", "_", i).strip("_")

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1])); outd = RAW / OUTSUB; outd.mkdir(exist_ok=True)
    eng = None
    for lid, src in spec.items():
        fp = outd / (safe(lid) + ".npz")
        if fp.exists(): continue
        t = time.time()
        try:
            if src == "engine":
                if eng is None:
                    pg = json.load(gzip.open("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/geometry/engine_polygons_599.geojson.gz"))
                    eng = {f["properties"]["id"]: shape(f["geometry"]) for f in pg["features"]}
                geom = eng[lid]
            else:
                geom = shape(json.load(open(src)))
            np.savez_compressed(fp, **profile(geom)); print(lid, round(time.time() - t), flush=True)
        except Exception as e:
            print(lid, "FAIL", repr(e)[:120], flush=True)
