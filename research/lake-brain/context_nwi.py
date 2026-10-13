#!/usr/bin/env python3
"""Track 7: National Wetlands Inventory proxies for the pilots, via the Esri-hosted NWI mirror (USA_Wetlands FeatureServer;
the FWS Wetlands MapServer returned HTTP 500 on 2026-10-13, ledger B-context-004).
Per lake (tile the buffered bbox in 0.05 deg tiles that touch the polygon + 300 m, fetch NWI polygons with geometry):
  - nwi_lake_l2_in_frac : share of the lake polygon whose NWI code is Lacustrine-Littoral (L2*) (~<2 m / to emergent limit)
  - nwi_aquatic_bed_in_frac : share of lake polygon coded Aquatic Bed (*AB*) (floating / submerged vegetation) any system
  - nwi_fringe_km2 / nwi_fringe_per_shore_km : emergent/scrub-shrub/forested palustrine wetland area within 200 m of the shoreline
  - nwi_fringe_pem_km2 : of which emergent (PEM)
Output <DATA>/context/nwi_features.json (rebuildable). 1 req/s."""
import gzip, json, sys, time
from pathlib import Path
import numpy as np, requests, shapely
from pyproj import Transformer
from shapely.geometry import shape, box
from shapely.ops import unary_union

DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Wetlands/FeatureServer/0/query"
STEP = 0.05


def fetch(bb):
    out = []; off = 0
    while True:
        for attempt in range(4):
            try:
                r = requests.get(URL, params=dict(where="1=1", geometry=f"{bb[0]},{bb[1]},{bb[2]},{bb[3]}", geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects",
                                                  outFields="ATTRIBUTE", returnGeometry="true", outSR=4326, geometryPrecision=5, maxAllowableOffset=0.00015, resultOffset=off, resultRecordCount=2000, f="geojson"), timeout=180).json()
                break
            except Exception:
                time.sleep(4 * (attempt + 1)); r = None
        if r is None or "features" not in r: raise RuntimeError(f"NWI fetch failed {bb} {str(r)[:200]}")
        out += r["features"]
        if len(r["features"]) < 2000 and not r.get("exceededTransferLimit"): break
        off += 2000; time.sleep(0.5)
    return out


def lake(lid, geom):
    c = geom.centroid
    fw = Transformer.from_crs("EPSG:4326", f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", always_xy=True)
    P = lambda g: shapely.transform(g, lambda a: np.column_stack(fw.transform(a[:, 0], a[:, 1])))
    gm = P(geom).buffer(0)
    gs = geom.simplify(0.0002)
    b = gs.bounds
    feats = []
    xs = np.arange(np.floor(b[0] / STEP) * STEP, b[2], STEP); ys = np.arange(np.floor(b[1] / STEP) * STEP, b[3], STEP)
    n = 0
    for x in xs:
        for y in ys:
            t = box(x, y, x + STEP, y + STEP)
            if not t.buffer(0.004).intersects(gs): continue
            feats += fetch((x, y, x + STEP, y + STEP)); n += 1; time.sleep(0.7)
    seen = {}
    for f in feats:
        try: seen[(f["properties"]["ATTRIBUTE"], round(shape(f["geometry"]).area, 12), round(shape(f["geometry"]).centroid.x, 6), round(shape(f["geometry"]).centroid.y, 6))] = f
        except Exception: pass
    L2 = []; AB = []; FR = {"PEM": [], "PSS": [], "PFO": [], "other": []}
    for (att, *_), f in seen.items():
        g = shape(f["geometry"])
        if not g.is_valid: g = g.buffer(0)
        gp = P(g)
        if att.startswith("L2"): L2.append(gp)
        if "AB" in att[:6] and not att.startswith("R"): AB.append(gp)
        if att.startswith("P") and not att.startswith("PUB") and not att.startswith("PAB") and not att.startswith("PUS") and not att.startswith("PUB"):
            k = att[:3] if att[:3] in ("PEM", "PSS", "PFO") else "other"
            FR[k].append(gp)
    A = gm.area; per = gm.boundary.length
    def inter(gl): return unary_union(gl).intersection(gm).area if gl else 0.0
    ring = gm.buffer(200, quad_segs=2).difference(gm)
    def inring(gl): return unary_union(gl).intersection(ring).area if gl else 0.0
    fr = {k: inring(v) for k, v in FR.items()}
    return dict(n_tiles=n, n_nwi_polys=len(seen), nwi_lake_l2_in_frac=inter(L2) / A, nwi_aquatic_bed_in_frac=inter(AB) / A,
                nwi_fringe_km2=sum(fr.values()) / 1e6, nwi_fringe_pem_km2=fr["PEM"] / 1e6, nwi_fringe_pss_km2=fr["PSS"] / 1e6, nwi_fringe_pfo_km2=fr["PFO"] / 1e6,
                nwi_fringe_frac_of_ring=sum(fr.values()) / max(ring.area, 1), nwi_fringe_per_shore_km=sum(fr.values()) / 1e6 / (per / 1e3))


if __name__ == "__main__":
    ids = sys.argv[1:] or ["Wilson|AL", "Pickwick Lake|TN", "Wheeler|AL", "Guntersville|AL", "Lake Hartwell|SC"]
    pg = json.load(gzip.open(DATA / "geometry/engine_polygons_599.geojson.gz"))
    pm = {f["properties"]["id"]: shape(f["geometry"]) for f in pg["features"]}
    outp = DATA / "context/nwi_features.json"
    out = json.load(open(outp)) if outp.exists() else {}
    for lid in ids:
        t = time.time(); out[lid] = lake(lid, pm[lid]); outp.write_text(json.dumps(out, indent=1))
        print(lid, round(time.time() - t), {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out[lid].items()}, flush=True)
