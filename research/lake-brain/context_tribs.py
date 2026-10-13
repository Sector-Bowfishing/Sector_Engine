#!/usr/bin/env python3
"""Track 7: tributary-mouth proxy from NHDPlus HR flowlines.  For a lake polygon, fetch NetworkNHDFlowline (layer 3) with totdasqkm >= 5 in 0.05 deg tiles around
the polygon; a 'mouth' is a stream/river flowline (ftype 460) whose geometry meets the lake (within 60 m of the polygon boundary or inside the polygon) while its upstream
part lies outside.  Counts mouths by catchment size class (>=5, >=50, >=500 km2) and per shoreline km.  Output <DATA>/context/tribs.json (rebuildable)."""
import gzip, json, sys, time
from pathlib import Path
import numpy as np, requests, shapely
from pyproj import Transformer
from shapely.geometry import shape, box
from shapely.ops import unary_union, linemerge

DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
U = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer/3/query"
STEP = 0.05


def fetch(bb):
    out = []; off = 0
    while True:
        r = None
        for a in range(4):
            try:
                r = requests.get(U, params=dict(where="totdasqkm>=5", geometry=f"{bb[0]},{bb[1]},{bb[2]},{bb[3]}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects",
                                                outFields="nhdplusid,ftype,totdasqkm,streamorde,gnis_name", returnGeometry="true", outSR=4326, geometryPrecision=5, maxAllowableOffset=0.0001,
                                                resultOffset=off, resultRecordCount=1000, f="geojson"), timeout=180).json(); break
            except Exception: time.sleep(4 * (a + 1))
        if not r or "features" not in r: raise RuntimeError(f"tribs fetch failed {bb} {str(r)[:150]}")
        out += r["features"]
        if len(r["features"]) < 1000 and not r.get("exceededTransferLimit"): break
        off += 1000; time.sleep(0.5)
    return out


def lake(lid, geom):
    c = geom.centroid
    fw = Transformer.from_crs("EPSG:4326", f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", always_xy=True)
    P = lambda g: shapely.transform(g, lambda a: np.column_stack(fw.transform(a[:, 0], a[:, 1])))
    gm = P(geom).buffer(0)
    gs = geom.simplify(0.0002); b = gs.bounds
    feats = {}
    for x in np.arange(np.floor(b[0] / STEP) * STEP, b[2], STEP):
        for y in np.arange(np.floor(b[1] / STEP) * STEP, b[3], STEP):
            if not box(x, y, x + STEP, y + STEP).buffer(0.004).intersects(gs): continue
            for f in fetch((x, y, x + STEP, y + STEP)): feats[f["properties"]["nhdplusid"]] = f
            time.sleep(0.6)
    shore = gm.boundary; per_km = shore.length / 1e3
    zone = shore.buffer(60)
    mouths = []
    for f in feats.values():
        p = f["properties"]
        if p["ftype"] != 460 or not f.get("geometry"): continue
        g = P(shape(f["geometry"]))
        if g.is_empty or not g.intersects(zone): continue
        # upstream start point must be outside the lake polygon (a stream coming in), end in/at the zone
        pts = list(g.geoms[0].coords) if g.geom_type == "MultiLineString" else list(g.coords)
        if not (shapely.geometry.Point(pts[0]).distance(gm) > 20): continue
        mouths.append(p["totdasqkm"])
    m = np.array(mouths)
    return dict(n_flowlines=len(feats), n_mouth_ge5=int((m >= 5).sum()), n_mouth_ge50=int((m >= 50).sum()), n_mouth_ge500=int((m >= 500).sum()),
                mouths_per_shore_km=float(len(m) / per_km), largest_mouth_km2=float(m.max()) if len(m) else 0.0, shore_km=float(per_km))


if __name__ == "__main__":
    ids = sys.argv[1:] or ["Wilson|AL", "Pickwick Lake|TN", "Wheeler|AL", "Guntersville|AL", "Lake Hartwell|SC"]
    pg = json.load(gzip.open(DATA / "geometry/engine_polygons_599.geojson.gz"))
    pm = {f["properties"]["id"]: shape(f["geometry"]) for f in pg["features"]}
    outp = DATA / "context/tribs.json"
    out = json.load(open(outp)) if outp.exists() else {}
    for lid in ids:
        t = time.time(); out[lid] = lake(lid, pm[lid]); outp.write_text(json.dumps(out, indent=1))
        print(lid, round(time.time() - t), out[lid], flush=True)
