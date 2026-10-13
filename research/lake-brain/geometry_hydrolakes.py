#!/usr/bin/env python3
"""HydroLAKES v10 (2016; polygons from SRTM Water Body Data ~2000 + other sources) coverage/area check for the 621 directory lakes.
Needs pyogrio+shapely+pyproj (venv at <DATA>/geometry/venv) and the extracted shapefile in <DATA>/geometry/hydrolakes/extracted/.
Writes <DATA>/geometry/hydrolakes_metrics.json."""
import gzip, json, os
import numpy as np, pyproj, shapely
from pyogrio.raw import read as ogr_read
from shapely import wkb
from shapely.geometry import shape, Point
from shapely.ops import unary_union

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.environ.get("LAKE_BRAIN_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
SHP = os.path.join(DATA, "geometry", "hydrolakes", "extracted", "HydroLAKES_polys_v10_shp", "HydroLAKES_polys_v10.shp")


def laea(lat, lon):
    return pyproj.Transformer.from_crs(4326, f"+proj=laea +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m", always_xy=True)


def tr(g, t):
    return shapely.transform(g, lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1])))


def main():
    lakes = json.load(open(os.path.join(DATA, "directory_lakes_2026-10-13.json")))["lakes"]
    polys = {f["properties"]["id"]: f for f in json.load(gzip.open(os.path.join(REPO, "jobs/lake-surface/polygons.geojson.gz"), "rt"))["features"]}
    out = {}
    for l in lakes:
        pf = polys.get(l["id"])
        t = laea(l["lat"], l["lon"])
        if pf is not None:
            e = shape(pf["geometry"]).buffer(0)
            bbox = e.bounds
        else:
            e = None
            bbox = (l["lon"] - 0.1, l["lat"] - 0.1, l["lon"] + 0.1, l["lat"] + 0.1)
        meta, _idx, geoms, fields = ogr_read(SHP, bbox=bbox, columns=["Hylak_id", "Lake_name", "Lake_area", "Lake_type", "Grand_id", "Poly_src", "Dam_avg"])
        rows = []
        pt = Point(l["lon"], l["lat"])
        for i in range(len(geoms)):
            g = wkb.loads(bytes(geoms[i])) if geoms[i] is not None else None
            if g is None:
                continue
            g = g.buffer(0)
            if e is not None:
                inter = tr(g.intersection(e), t).area
                ga = tr(g, t).area
                if ga <= 0 or inter / ga < 0.3:
                    continue
            elif not g.buffer(0.03).contains(pt):
                continue
            rows.append((g, fields[0][i], fields[1][i], fields[2][i], fields[3][i], fields[4][i], fields[5][i]))
        if not rows:
            out[l["id"]] = {"hl_matched": False}
            continue
        u = unary_union([r[0] for r in rows])
        up = tr(u, t)
        top = max(rows, key=lambda r: r[3])
        d = {"hl_matched": True, "hl_n": len(rows), "hl_area_km2": round(up.area / 1e6, 2), "hl_top_id": int(top[1]),
             "hl_top_name": top[2], "hl_top_type": int(top[4]), "hl_grand_id": int(top[5]) if top[5] and top[5] > 0 else None,
             "hl_poly_src": str(top[6])}
        if e is not None:
            ep = tr(e, t)
            d["hl_area_ratio"] = round(ep.area / up.area, 3) if up.area else None
            d["hl_iou"] = round(ep.intersection(up).area / ep.union(up).area, 3)
        out[l["id"]] = d
    json.dump(out, open(os.path.join(DATA, "geometry", "hydrolakes_metrics.json"), "w"))
    print("matched", sum(1 for v in out.values() if v["hl_matched"]), "of", len(out))


if __name__ == "__main__":
    main()
