#!/usr/bin/env python3
"""Fetch the OSM water multipolygon for the 5 pilot lakes (Overpass, out geom), assemble with shapely, compare to the Engine polygon + NHD.
Writes <DATA>/geometry/osm/pilots_osm.json (+ raw responses). Polite: one query at a time, UA set, cached."""
import gzip, json, os, sys, time, urllib.parse, urllib.request
import numpy as np, pyproj, shapely
from shapely.geometry import shape, LineString, Polygon, MultiPolygon, mapping
from shapely.ops import linemerge, polygonize, unary_union

DATA = os.environ.get("LAKE_BRAIN_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UA = "SectorEngine-LakeBrain-Research/1.0 (mgcather07@gmail.com)"
OUTD = os.path.join(DATA, "geometry", "osm")
PIL = {"Guntersville|AL": "Guntersville", "Wheeler|AL": "Wheeler", "Wilson|AL": "Wilson", "Pickwick Lake|TN": "Pickwick", "Lake Hartwell|SC": "Hartwell"}


def op(q):
    for url in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        for k in range(3):
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": UA})
                return json.load(urllib.request.urlopen(req, timeout=180))
            except Exception as e:  # noqa
                print("  retry", url, str(e)[:60]); time.sleep(8 * (k + 1))
    raise RuntimeError("overpass unavailable")


def assemble(rel):
    outer, inner = [], []
    for m in rel.get("members", []):
        if m["type"] != "way" or not m.get("geometry"):
            continue
        ls = LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
        (inner if m.get("role") == "inner" else outer).append(ls)
    o = list(polygonize(linemerge(outer))) if outer else []
    i = list(polygonize(linemerge(inner))) if inner else []
    if not o:
        return None
    g = unary_union(o)
    if i:
        g = g.difference(unary_union(i))
    return g


def main():
    polys = {f["properties"]["id"]: f for f in json.load(gzip.open(os.path.join(REPO, "jobs/lake-surface/polygons.geojson.gz"), "rt"))["features"]}
    out = {}
    for lid, key in PIL.items():
        e = shape(polys[lid]["geometry"]).buffer(0)
        w, s, ee, n = e.bounds
        q = f'[out:json][timeout:120];(relation["natural"="water"]["name"~"{key}"]({s},{w},{n},{ee});way["natural"="water"]["name"~"{key}"]({s},{w},{n},{ee}););out geom;'
        path = os.path.join(OUTD, f"{key}.raw.json")
        if os.path.exists(path):
            j = json.load(open(path))
        else:
            j = op(q); json.dump(j, open(path, "w")); time.sleep(5)
        t = pyproj.Transformer.from_crs(4326, f"+proj=laea +lat_0={e.centroid.y} +lon_0={e.centroid.x} +datum=WGS84 +units=m", always_xy=True)
        tr = lambda g: shapely.transform(g, lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1])))
        ep = tr(e)
        res = []
        for el in j.get("elements", []):
            g = assemble(el) if el["type"] == "relation" else (Polygon([(p["lon"], p["lat"]) for p in el["geometry"]]) if el.get("geometry") and el["geometry"][0] == el["geometry"][-1] else None)
            if g is None or g.is_empty:
                continue
            gp = tr(g.buffer(0))
            tags = el.get("tags", {})
            res.append({"osm": f"{el['type']}/{el['id']}", "name": tags.get("name"), "water": tags.get("water"), "wikidata": tags.get("wikidata"),
                        "source_tag": tags.get("source"), "area_km2": round(gp.area / 1e6, 3), "vertices": sum(len(p.exterior.coords) + sum(len(i.coords) for i in p.interiors) for p in (gp.geoms if hasattr(gp, "geoms") else [gp])),
                        "holes": sum(len(p.interiors) for p in (gp.geoms if hasattr(gp, "geoms") else [gp])),
                        "iou_vs_engine": round(gp.intersection(ep).area / gp.union(ep).area, 4), "cover_of_engine": round(gp.intersection(ep).area / ep.area, 4)})
        res.sort(key=lambda r: -r["area_km2"])
        out[lid] = {"engine_area_km2": round(ep.area / 1e6, 3), "osm": res[:6]}
        print(lid, json.dumps(out[lid]), flush=True)
    json.dump(out, open(os.path.join(OUTD, "pilots_osm.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
