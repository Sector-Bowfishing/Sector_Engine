#!/usr/bin/env python3
"""Size/fidelity of a lake polygon at several simplification tolerances (delivery-path sizing: RTDB node vs static GeoJSON).
Reads the full-resolution NHD HR polygons fetched by geometry_audit notes (<DATA>/geometry/nhd_full/pilots_nhd_full.geojson).
Writes <DATA>/geometry/simplify_sizes.json and prints a table. Uses an equal-area-ish local projection for tolerances in metres."""
import gzip, json, os, sys
import numpy as np, pyproj, shapely
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

DATA = os.environ.get("LAKE_BRAIN_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
SRC = os.path.join(DATA, "geometry", "nhd_full", "pilots_nhd_full.geojson")
GROUPS = {"Guntersville": ["139326855"], "Wheeler": ["88572193"], "Wilson": ["87864655"], "Pickwick": ["147604857"],
          "Hartwell": ["136157939", "120024414"]}
TOLS = [0, 5, 10, 25, 50, 100, 250]


def tr(g, t):
    return shapely.transform(g, lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1])))


def nv(g):
    ps = list(g.geoms) if hasattr(g, "geoms") else [g]
    return sum(len(p.exterior.coords) + sum(len(i.coords) for i in p.interiors) for p in ps)


def rings(g):
    ps = list(g.geoms) if hasattr(g, "geoms") else [g]
    return sum(1 + len(p.interiors) for p in ps)


def polyline_len(g, prec=5):
    """Google encoded-polyline length (chars) of all rings: a compact wire format baseline."""
    def enc(ring):
        out = []; plat = plon = 0
        for x, y in ring:
            la, lo = round(y * 10**prec), round(x * 10**prec)
            for d in (la - plat, lo - plon):
                d = ~(d << 1) if d < 0 else d << 1
                while d >= 0x20:
                    out.append(chr((0x20 | (d & 0x1f)) + 63)); d >>= 5
                out.append(chr(d + 63))
            plat, plon = la, lo
        return "".join(out)
    ps = list(g.geoms) if hasattr(g, "geoms") else [g]
    return sum(len(enc(p.exterior.coords)) + sum(len(enc(i.coords)) for i in p.interiors) for p in ps)


def geojson_bytes(g, dec):
    def rnd(c):
        return [round(v, dec) for v in c]
    m = mapping(g)
    def walk(x):
        return rnd(x) if isinstance(x[0], (int, float)) else [walk(i) for i in x]
    m = {"type": m["type"], "coordinates": walk(m["coordinates"])}
    b = json.dumps({"type": "Feature", "properties": {}, "geometry": m}, separators=(",", ":")).encode()
    return len(b), len(gzip.compress(b, 6))


def main():
    fc = json.load(open(SRC))
    by = {f["properties"]["PERMANENT_IDENTIFIER"]: shape(f["geometry"]) for f in fc["features"]}
    res = {}
    for name, ids in GROUPS.items():
        g = unary_union([by[i] for i in ids]).buffer(0)
        c = g.centroid
        t = pyproj.Transformer.from_crs(4326, f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", always_xy=True)
        ti = pyproj.Transformer.from_crs(f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", 4326, always_xy=True)
        gp = tr(g, t); A0 = gp.area
        rows = []
        for tol in TOLS:
            sp = gp if tol == 0 else gp.simplify(tol, preserve_topology=True)
            # drop holes smaller than tol^2 (islands too small to see at this scale) for a 'display' variant
            sg = tr(sp, ti)
            b6, z6 = geojson_bytes(sg, 6); b5, z5 = geojson_bytes(sg, 5); b4, z4 = geojson_bytes(sg, 4)
            hd = None if tol == 0 else round(float(shapely.hausdorff_distance(gp.boundary, sp.boundary)), 1)
            rows.append({"tol_m": tol, "vertices": nv(sg), "rings": rings(sg), "area_km2": round(sp.area / 1e6, 3),
                         "area_delta_pct": round((sp.area - A0) / A0 * 100, 3), "hausdorff_m": hd,
                         "geojson_bytes_6dp": b6, "gz_6dp": z6, "geojson_bytes_5dp": b5, "gz_5dp": z5,
                         "geojson_bytes_4dp": b4, "gz_4dp": z4, "polyline5_chars": polyline_len(sg)})
        res[name] = rows
        print(name, "area", round(A0 / 1e6, 2))
        print("tol_m  verts  rings  area_d%  hausd_m  geojson6dp  gz6   geojson5dp  gz5   polyline5")
        for r in rows:
            print(f"{r['tol_m']:>5} {r['vertices']:>7} {r['rings']:>5} {r['area_delta_pct']:>8} {str(r['hausdorff_m']):>8} {r['geojson_bytes_6dp']:>10} {r['gz_6dp']:>7} {r['geojson_bytes_5dp']:>10} {r['gz_5dp']:>7} {r['polyline5_chars']:>9}")
    json.dump(res, open(os.path.join(DATA, "geometry", "simplify_sizes.json"), "w"), indent=1)


if __name__ == "__main__" and not (len(sys.argv) > 1 and sys.argv[1] == "--fleet"):
    main()


def fleet():
    """Total delivery size of all Engine polygons (already ~10-15 m simplified NHD) at display tolerances."""
    REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    feats = json.load(gzip.open(os.path.join(REPO, "jobs", "lake-surface", "polygons.geojson.gz"), "rt"))["features"]
    out = {}
    for tol in (0, 25, 50, 100):
        raw = gz = verts = 0
        per = []
        for f in feats:
            g = shape(f["geometry"])
            if g.geom_type == "GeometryCollection":
                g = unary_union([x for x in g.geoms if x.geom_type in ("Polygon", "MultiPolygon")])
            c = g.centroid
            t = pyproj.Transformer.from_crs(4326, f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", always_xy=True)
            ti = pyproj.Transformer.from_crs(f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m", 4326, always_xy=True)
            sg = g if tol == 0 else tr(tr(g, t).simplify(tol, preserve_topology=True), ti)
            b, z = geojson_bytes(sg, 5)
            raw += b; gz += z; verts += nv(sg); per.append(z)
        per.sort()
        out[tol] = {"vertices": verts, "geojson_5dp_bytes_total": raw, "gz_total": gz, "gz_median": per[len(per) // 2], "gz_p95": per[int(len(per) * .95)], "gz_max": per[-1]}
        print("fleet tol", tol, out[tol], flush=True)
    json.dump(out, open(os.path.join(DATA, "geometry", "fleet_delivery_sizes.json"), "w"), indent=1)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--fleet":
    fleet()
