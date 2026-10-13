#!/usr/bin/env python3
"""Depth Brain / terrain: Minnesota DNR lake bathymetry (MapServer water_lake_bathymetry: layer 0 contours, layer 1 outline) as a second REAL-contour truth source.
For each requested lake name: outline polygon (EPSG:4326) + contour lines, depth grid by TIN interpolation (same method as terrain_contour_depth.py; depth 0 on the outline),
truth shares <=3 / <=6 / <=10 ft.  Contour interval is whatever DNR digitised (reported).  Output <RAW>/mn/<key>/* and <RAW>/depthgrid/MN_<key>.npz,
docs/research/depth-brain/data/mn_dnr_truth.json.  venv python."""
import json, re, sys, time
from pathlib import Path
import numpy as np, requests, geopandas as gpd, shapely
from shapely.geometry import shape, mapping
from scipy.interpolate import LinearNDInterpolator
from rasterio.features import rasterize
from rasterio.transform import from_origin
sys.path.insert(0, str(Path(__file__).parent))
from terrain_contour_depth import densify, RES

REPO = Path(__file__).resolve().parents[2]
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
B = "https://enterprise.gisdata.mn.gov/aghost/rest/services/us_mn_state_dnr/water_lake_bathymetry/MapServer"


def q(layer, where, geom=True):
    out, off = [], 0
    while True:
        r = requests.get(f"{B}/{layer}/query", params=dict(where=where, outFields="*", outSR=4326, f="geojson", resultOffset=off, resultRecordCount=1000, returnGeometry="true" if geom else "false"), timeout=180).json()
        f = r.get("features", []); out += f
        if len(f) < 1000: break
        off += 1000
    return out


def build(name, dow=None):
    key = re.sub(r"[^A-Za-z0-9]+", "_", name)
    if dow is None:
        o = q(1, f"lake_name LIKE '{name.upper()}%' OR lake_name LIKE '{name}%'")
        if not o: print(name, "no outline"); return None
        o.sort(key=lambda f: -f["properties"].get("acres", 0)); dow = o[0]["properties"]["dowlknum"]; print(name, "->", o[0]["properties"]["lake_name"], dow, o[0]["properties"]["acres"], "ac;", len(o), "matches")
    out = q(1, f"dowlknum='{dow}'"); con = q(0, f"dowlknum='{dow}'")
    if not con: print(name, "no contours"); return None
    d = RAW / "mn" / key; d.mkdir(parents=True, exist_ok=True)
    og = gpd.GeoDataFrame.from_features(out, crs=4326); cg = gpd.GeoDataFrame.from_features(con, crs=4326)
    dep = sorted(set(np.round(cg["depth"].abs().astype(float), 2)))
    og.to_file(d / "outline.geojson", driver="GeoJSON"); cg.to_file(d / "contours.geojson", driver="GeoJSON")
    poly = og.to_crs(5070).geometry.union_all(); cg5 = cg.to_crs(5070)
    pts, vals = [], []
    for geom, z in zip(cg5.geometry, cg5["depth"].abs()):
        if geom is None or geom.is_empty: continue
        for ln in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            if ln.length < 5: continue
            xy = densify(ln.coords, 25.0); pts.append(xy); vals.append(np.full(len(xy), float(z)))
    rb = poly.boundary
    for ln in (rb.geoms if hasattr(rb, "geoms") else [rb]):
        xy = densify(ln.coords, 25.0); pts.append(xy); vals.append(np.zeros(len(xy)))
    P = np.vstack(pts); V = np.concatenate(vals)
    f = LinearNDInterpolator(P, V)
    minx, miny, maxx, maxy = poly.bounds; W = int((maxx - minx) / RES) + 2; H = int((maxy - miny) / RES) + 2
    tr = from_origin(minx, maxy, RES, RES)
    mask = rasterize([(poly, 1)], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    xs = minx + (np.arange(W) + .5) * RES; ys = maxy - (np.arange(H) + .5) * RES; X, Y = np.meshgrid(xs, ys)
    D = np.full((H, W), np.nan); D[mask] = f(X[mask], Y[mask]); D[D < 0] = 0
    np.savez_compressed(RAW / "depthgrid" / f"MN_{key}.npz", depth_ft=D.astype("float32"), transform=np.array(tr)[:6], pool=0.0, contour_layer="mn_dnr")
    v = D[np.isfinite(D)]
    # pool polygon for DEM profile
    pj = d / "pool_polygon.geojson"; pj.write_text(json.dumps(shapely.union_all(og.geometry.values).__geo_interface__))
    res = dict(name=name, dow=dow, area_ac=round(float(poly.area / 4046.856), 1), contour_depths_ft=dep[:12], n_contours=len(cg), max_depth_ft=float(v.max()),
               S3=round(float((v <= 3).mean()), 4), S5=round(float((v <= 5).mean()), 4), S6=round(float((v <= 6).mean()), 4), S10=round(float((v <= 10).mean()), 4), S15=round(float((v <= 15).mean()), 4),
               polygon=str(pj))
    print(json.dumps(res)); return key, res


if __name__ == "__main__":
    names = sys.argv[1:] or ["Gull", "Bemidji", "Minnetonka", "Vermilion", "Winnibigoshish", "Leech", "Mille Lacs", "Otter Tail", "White Bear", "Pepin"]
    (RAW / "depthgrid").mkdir(exist_ok=True)
    allr = {}
    for n in names:
        try:
            r = build(n)
            if r: allr[r[0]] = r[1]
        except Exception as e:
            print(n, "ERR", repr(e)[:160])
    p = REPO / "docs/research/depth-brain/data/mn_dnr_truth.json"; p.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(p.read_text()) if p.exists() else {}; old.update(allr); p.write_text(json.dumps(old, indent=1))
