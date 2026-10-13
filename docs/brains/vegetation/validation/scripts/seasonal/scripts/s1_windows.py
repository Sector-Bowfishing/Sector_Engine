"""Fetch canonical analysis polygons and choose a <=WIN_KM analysis window per lake (max shoreline length, >=25 % water)."""
import json, gzip, math, requests, numpy as np
from shapely.geometry import shape, box
from shapely import make_valid
from common import *
reg = {l["lakeKey"]: l for l in json.load(open(R/"registry/lakes.v1.json"))["lakes"]}
(H/"geom").mkdir(exist_ok=True); out = {}
for k, cls, lab in LAKES:
    l = reg[k]; f = H/"geom"/f"{k}.geojson.gz"
    if not f.exists():
        r = requests.get(f"https://storage.googleapis.com/sector-lake-registry/lakes/{k}/geometry.v1.analysis.geojson.gz", timeout=120); r.raise_for_status(); f.write_bytes(r.content)
    b = f.read_bytes(); g = json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)
    geom = shape(g["features"][0]["geometry"] if g.get("type") == "FeatureCollection" else g.get("geometry", g)); geom = make_valid(geom)
    x0, y0, x1, y1 = geom.bounds; lat = (y0+y1)/2; kx = 111.32*math.cos(math.radians(lat)); ky = 110.57
    dx = WIN_KM/kx; dy = WIN_KM/ky
    wx = min(dx, x1-x0); wy = min(dy, y1-y0)
    best = None; step_x = 1.0/kx; step_y = 1.0/ky
    xs = np.arange(x0, max(x0, x1-wx)+1e-9, step_x*1.0) if x1-x0 > dx else [x0]
    ys = np.arange(y0, max(y0, y1-wy)+1e-9, step_y*1.0) if y1-y0 > dy else [y0]
    bnd = geom.boundary
    for x in xs:
        for y in ys:
            bx = box(x, y, x+wx, y+wy)
            if not bx.intersects(geom): continue
            wa = geom.intersection(bx).area/bx.area
            if wa < 0.25: continue
            sl = bnd.intersection(bx).length*kx   # deg-ish length scaled by kx (approx)
            if best is None or sl > best[0]: best = (sl, x, y, wa)
    sl, x, y, wa = best
    out[k] = dict(lakeKey=k, cls=cls, label=lab, name=l["name"], state=l["state"], areaKm2=l["areaKm2"],
                  fullBbox=[x0, y0, x1, y1], window=[x, y, x+wx, y+wy], windowWaterFrac=round(wa, 3),
                  windowKm=[round(wx*kx, 2), round(wy*ky, 2)], lat=lat, lon=(x0+x1)/2, fullKm=[round((x1-x0)*kx, 1), round((y1-y0)*ky, 1)])
    print(k, out[k]["fullKm"], "->", out[k]["windowKm"], "water", out[k]["windowWaterFrac"], "window", [round(v, 4) for v in out[k]["window"]], flush=True)
json.dump(out, open(H/"out/windows.json", "w"), indent=1)
