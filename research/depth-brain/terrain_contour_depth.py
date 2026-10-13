#!/usr/bin/env python3
"""Depth Brain / terrain: build a depth-below-pool raster (15 m, EPSG:5070) for a TWDB-surveyed lake from its published 1-ft / 2-ft bathymetric
contours (fetched by HTTP range from the survey zip), the conservation-pool polygon (depth 0 on the shoreline) and linear interpolation of contour
vertices (TIN).  This is REAL-contour truth for spatial tests.  Output <RAW>/depthgrid/<key>.npz (depth_ft, transform, crs).
Usage: terrain_contour_depth.py <key> [<key> ...]      (keys are twdb dir names e.g. conroe_2020-10).  Run with the venv python."""
import io, json, re, sys, zipfile
from pathlib import Path
import numpy as np, geopandas as gpd, shapely
from shapely.geometry import shape
from scipy.interpolate import LinearNDInterpolator
from rasterio.features import rasterize
from rasterio.transform import from_origin
sys.path.insert(0, str(Path(__file__).parent))
from terrain_twdb_fetch import RangeFile, RAW

RES = 15.0


def densify(coords, step=25.0):
    """points every ~step metres along a polyline given as an (n,2) array (numpy; shapely.line_interpolate_point is O(n^2) on long lines)"""
    c = np.asarray(coords)[:, :2]
    seg = np.hypot(*np.diff(c, axis=0).T); cum = np.concatenate([[0], np.cumsum(seg)])
    if cum[-1] < 1e-6: return c[:1]
    d = np.arange(0, cum[-1], step); d = np.append(d, cum[-1])
    return np.column_stack([np.interp(d, cum, c[:, 0]), np.interp(d, cum, c[:, 1])])


def choose_member(members):
    names = [(n, s) for n, s in members if n.lower().endswith(".shp")]
    def rank(n):
        b = n.lower()
        if "cont" not in b or "topo" in b or "land" in b or "lake" in b: return None
        if re.search(r"\d+p\d+ft?cont|\d{3}ft29cont|cont_edi", b) and not re.search(r"(^|[^p\d])[125]ft", b): return None
        m = re.search(r"(?:^|[^\d])(\d+)ft", b)
        if "p5ft" in b: return None
        if m: return int(m.group(1))
        m = re.search(r"cont_(\d)", b)
        return int(m.group(1)) if m else 9
    c = [(rank(n), s, n) for n, s in names if rank(n) is not None]
    return sorted(c)[0][2] if c else None


def fetch_contour(key):
    d = RAW / "twdb" / key; info = json.load(open(d / "zip_members.json"))
    mem = choose_member(info["members"])
    if mem is None: return None
    out = d / "contours"; out.mkdir(exist_ok=True)
    base = mem[:-4]
    z = zipfile.ZipFile(io.BufferedReader(RangeFile(info["url"]), 1 << 16))
    for ext in (".shp", ".dbf", ".shx", ".prj", ".cpg"):
        try: (out / (Path(base).name + ext)).write_bytes(z.read(base + ext))
        except KeyError: pass
    return out / (Path(base).name + ".shp")


def elev_col(g):
    for c in g.columns:
        if c.lower() in ("contour", "elevation", "elev", "z", "value", "level", "cont", "contour_ft", "elev_ft"): return c
    num = [c for c in g.columns if c != "geometry" and np.issubdtype(g[c].dtype, np.number)]
    return num[0] if num else None


def build(key):
    d = RAW / "twdb" / key
    truth = json.load(open(RAW / "twdb_truth.json"))[key]; pool = truth["pool_ft"]
    shp = fetch_contour(key) or None
    if shp is None: print(key, "no contour layer"); return
    g = gpd.read_file(shp); ec = elev_col(g)
    if ec is None: print(key, "no elev col", list(g.columns)); return
    g = g.to_crs(5070); poly = gpd.GeoSeries([shape(json.load(open(d / "pool_polygon.geojson")))], crs=4326).to_crs(5070).iloc[0]
    e = g[ec].abs().values            # TWDB files sometimes store negative elevations
    pts, vals = [], []
    for geom, z in zip(g.geometry, e):
        if geom is None or geom.is_empty: continue
        for ln in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            if ln.length < 5: continue
            xy = densify(ln.coords, 25.0); pts.append(xy); vals.append(np.full(len(xy), z))
    # shoreline: depth 0 at pool
    rb = poly.boundary
    for ln in (rb.geoms if hasattr(rb, "geoms") else [rb]):
        xy = densify(ln.coords, 25.0); pts.append(xy); vals.append(np.full(len(xy), pool))
    P = np.vstack(pts); V = np.concatenate(vals)
    inside = shapely.contains_xy(poly, P[:, 0], P[:, 1]) | (np.abs(V - pool) < 1e-6)
    P, V = P[inside], V[inside]
    f = LinearNDInterpolator(P, V)
    minx, miny, maxx, maxy = poly.bounds
    W = int((maxx - minx) / RES) + 2; H = int((maxy - miny) / RES) + 2
    tr = from_origin(minx, maxy, RES, RES)
    mask = rasterize([(poly, 1)], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    xs = minx + (np.arange(W) + .5) * RES; ys = maxy - (np.arange(H) + .5) * RES
    X, Y = np.meshgrid(xs, ys); Z = np.full((H, W), np.nan)
    Z[mask] = f(X[mask], Y[mask])
    depth = pool - Z
    depth[depth < 0] = 0
    out = RAW / "depthgrid"; out.mkdir(exist_ok=True)
    np.savez_compressed(out / f"{key}.npz", depth_ft=depth.astype("float32"), transform=np.array(tr)[:6], pool=pool, contour_layer=shp.name)
    v = depth[np.isfinite(depth)]
    print(key, shp.name, "n_contour_pts", len(P), "share<3ft %.3f <6ft %.3f (table S3 %.3f S6 %.3f)" % ((v < 3).mean(), (v < 6).mean(), truth["S3"], truth["S6"]), flush=True)


if __name__ == "__main__":
    for k in sys.argv[1:]:
        try: build(k)
        except Exception as ex: print(k, "ERR", repr(ex)[:200], flush=True)
