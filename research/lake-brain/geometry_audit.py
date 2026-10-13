#!/usr/bin/env python3
"""Lake Brain / geometry thread: audit of the Engine-shipped lake polygons against national references.

Read-only research tool. Reads:
  * jobs/lake-surface/polygons.geojson.gz        (599 Engine polygons, in Git)
  * <DATA>/directory_lakes_2026-10-13.json        (621-lake production directory snapshot)
Queries (GET only, cached on disk so a re-run is cheap and polite):
  * USGS NHD High Resolution waterbodies   https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12
  * USGS 3DHP_all waterbodies              https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/MapServer/60
  * OpenStreetMap via Overpass (names/bboxes of water relations/ways near each lake point)
Writes (never to Git):  <DATA>/geometry/lake_geometry_flags.csv, caches under <DATA>/geometry/cache/
Writes (small, to Git): docs/research/lake-brain/data/geometry_summary.json

Stages (run in order, or --stage all):  local  nhd  tdhp  osm  classify
  python research/lake-brain/geometry_audit.py --stage all
Nothing here writes to any database, bucket or API.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pyproj
import shapely
from shapely.geometry import shape, mapping, Point, MultiPolygon, Polygon
from shapely.ops import unary_union

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.environ.get("LAKE_BRAIN_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
GEO = os.path.join(DATA, "geometry")
CACHE = os.path.join(GEO, "cache")
POLYGONS = os.path.join(REPO, "jobs", "lake-surface", "polygons.geojson.gz")
DIRECTORY = os.path.join(DATA, "directory_lakes_2026-10-13.json")
OUT_CSV = os.path.join(GEO, "lake_geometry_flags.csv")
OUT_SUMMARY = os.path.join(REPO, "docs", "research", "lake-brain", "data", "geometry_summary.json")
UA = "SectorEngine-LakeBrain-Research/1.0 (mgcather07@gmail.com)"

NHD_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12/query"
TDHP_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/MapServer/60/query"
OVERPASS = ["https://overpass-api.de/api/interpreter"]  # overpass.kumi.systems: connection failures from this network (2026-10-13)

PILOTS = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"]

# ---------------------------------------------------------------- helpers


def load_directory():
    return json.load(open(DIRECTORY))["lakes"]


def load_polygons():
    fc = json.load(gzip.open(POLYGONS, "rt"))
    return {f["properties"]["id"]: f for f in fc["features"]}


def laea(lat, lon):
    """Local Lambert azimuthal equal-area transformer (metres) centred on the lake."""
    return pyproj.Transformer.from_crs(
        4326, f"+proj=laea +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m", always_xy=True)


def tr(geom, t):
    return shapely.transform(geom, lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1])))


def parts_of(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    if g.geom_type in ("MultiPolygon", "GeometryCollection"):
        out = []
        for p in g.geoms:
            out.extend(parts_of(p))
        return out
    return []


def nverts(g):
    return sum(len(p.exterior.coords) + sum(len(i.coords) for i in p.interiors) for p in parts_of(g))


def norm_name(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    stop = {"lake", "lakes", "reservoir", "res", "pond", "the", "of", "dam", "river", "impoundment", "bay", "flowage"}
    return {w for w in s.split() if w not in stop}


def name_match(a, b):
    A, B = norm_name(a), norm_name(b)
    if not A or not B:
        return 0.0
    return len(A & B) / max(1, min(len(A), len(B)))


def http_json(url, params=None, data=None, timeout=90, retries=4):
    q = url + ("?" + urllib.parse.urlencode(params) if params else "")
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    err = None
    for k in range(retries):
        try:
            req = urllib.request.Request(q, data=body, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(1.5 * (k + 1))
    raise RuntimeError(f"{url}: {err}")


def cached(key, fn):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, hashlib.sha1(key.encode()).hexdigest()[:20] + ".json")
    if os.path.exists(p):
        return json.load(open(p))
    v = fn()
    json.dump(v, open(p, "w"))
    return v


def rd(x, n=4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), n)


# ---------------------------------------------------------------- stage: local


def coord_decimals(lake):
    def dec(x):
        t = repr(float(x))
        return len(t.split(".")[1]) if "." in t else 0
    return max(dec(lake["lat"]), dec(lake["lon"]))


def point_tolerance_m(lake):
    """The directory coordinates are rounded (1-4 decimals): a point legitimately lands up to ~0.71 cell off the water."""
    return max(300.0, 0.71 * 111_000.0 * 10 ** -coord_decimals(lake))


def local_metrics(lake, feat):
    lat, lon = lake["lat"], lake["lon"]
    r = {"id": lake["id"], "name": lake["name"], "state": lake["state"], "lat": lat, "lon": lon,
         "coord_decimals": coord_decimals(lake), "point_tolerance_m": rd(point_tolerance_m(lake), 0),
         "has_polygon": feat is not None}
    if feat is None:
        return r
    props = feat["properties"]
    g = shape(feat["geometry"])
    t = laea(lat, lon)
    gp = tr(g, t)
    ps = parts_of(g)
    pa = sorted([tr(p, t).area for p in ps], reverse=True)
    total = sum(pa) or 1.0
    holes = [Polygon(i).area for p in parts_of(gp) for i in map(lambda x: list(x.coords), p.interiors)]
    pt = tr(Point(lon, lat), t)
    r.update({
        "source": props.get("source"), "trimmed": props.get("trimmed"),
        "attr_area_km2": props.get("areaKm2"),
        "geom_area_km2": rd(total / 1e6, 3),
        "geom_type": g.geom_type, "n_parts": len(ps),
        "n_parts_lt_1pct": sum(1 for a in pa if a / total < 0.01),
        "n_parts_ge_1pct": sum(1 for a in pa if a / total >= 0.01),
        "sliver_area_km2": rd(sum(a for a in pa if a / total < 0.01) / 1e6, 4),
        "largest_part_share": rd(pa[0] / total, 4) if pa else None,
        "n_holes": len(holes), "hole_area_km2": rd(sum(holes) / 1e6, 3),
        "max_hole_km2": rd(max(holes) / 1e6, 4) if holes else 0,
        "holes_lt_100m2": sum(1 for h in holes if h < 100),
        "n_vertices": nverts(g), "valid": bool(g.is_valid),
        "has_geometrycollection": g.geom_type == "GeometryCollection",
        "bbox_w": g.bounds[0], "bbox_s": g.bounds[1], "bbox_e": g.bounds[2], "bbox_n": g.bounds[3],
        "contains_point": bool(g.buffer(0).contains(Point(lon, lat))),
        "dist_point_to_polygon_m": rd(gp.distance(pt), 0),
        "point_within_tolerance": bool(gp.distance(pt) <= point_tolerance_m(lake)),
        "point_in_bbox": g.bounds[0] <= lon <= g.bounds[2] and g.bounds[1] <= lat <= g.bounds[3],
        "attr_vs_geom_area_ratio": rd((props.get("areaKm2") or 0) / (total / 1e6), 4),
        # mean vertex spacing along exteriors (m): a resolution proxy
        "mean_seg_m": rd(sum(p.exterior.length for p in parts_of(gp)) / max(1, sum(len(p.exterior.coords) - 1 for p in parts_of(gp))), 1),
    })
    return r


# ---------------------------------------------------------------- stage: national hydro references (NHD / 3DHP)

NHD_FIELDS = "OBJECTID,PERMANENT_IDENTIFIER,GNIS_NAME,AREASQKM,FTYPE,FCODE,FDATE,RESOLUTION"
TDHP_FIELDS = "OBJECTID,id3dhp,gnisidlabel,areasqkm,featuretype,featuretypelabel,featuredate,workunitid"


def ref_query(kind, lake, poly_feat, rows):
    """Candidate waterbodies from NHD/3DHP near a lake. Two calls: attributes (cheap) then geometry of the bigger ones."""
    url, fields, area_f, where_t = (NHD_URL, NHD_FIELDS, "AREASQKM", "FTYPE IN (390,436) AND AREASQKM>={a}") if kind == "nhd" \
        else (TDHP_URL, TDHP_FIELDS, "areasqkm", "areasqkm>={a}")
    if poly_feat is not None:
        w, s, e, n = shape(poly_feat["geometry"]).bounds
        eng = poly_feat["properties"].get("areaKm2") or 1.0
        minarea = max(0.02, 0.03 * eng)
    else:
        w, s, e, n = lake["lon"] - 0.08, lake["lat"] - 0.08, lake["lon"] + 0.08, lake["lat"] + 0.08
        minarea = 0.01
    env = f"{w - 0.002},{s - 0.002},{e + 0.002},{n + 0.002}"
    key = f"{kind}|{lake['id']}|{env}|{minarea}"

    def attrs():
        return http_json(url, {"geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                               "spatialRel": "esriSpatialRelIntersects", "where": where_t.format(a=minarea),
                               "outFields": fields, "returnGeometry": "false",
                               "orderByFields": f"{area_f} DESC", "resultRecordCount": 60, "f": "json"})

    a = cached("A|" + key, attrs)
    feats = [f["attributes"] for f in a.get("features", [])]
    if a.get("error"):
        return {"error": str(a["error"]), "cands": []}
    # which to fetch geometry for: the biggest 10, plus name matches, plus (no polygon) the first few
    pick = []
    for f in feats:
        nm = f.get("GNIS_NAME") or f.get("gnisidlabel")
        if len(pick) < 10 or name_match(nm, lake["name"]) >= 0.99:
            pick.append(f)
    oidf = "OBJECTID"
    ids = ",".join(str(f[oidf]) for f in pick[:14])
    cands = []
    if ids:
        def geo():
            return http_json(url, {"objectIds": ids, "outFields": fields, "returnGeometry": "true", "outSR": 4326,
                                   "maxAllowableOffset": 0.00008, "f": "geojson"})
        gj = cached("G|" + key + "|" + ids, geo)
        byid = {f["properties"][oidf]: f for f in gj.get("features", [])}
        for f in pick[:14]:
            gf = byid.get(f[oidf])
            if gf and gf.get("geometry"):
                cands.append({"attrs": f, "geom": gf["geometry"]})
    return {"cands": cands, "n_attr": len(feats), "truncated": len(feats) >= 60}


def compare_ref(kind, lake, poly_feat, res):
    """Area ratio / IoU / containment of the Engine polygon against the matched reference waterbodies."""
    r = {}
    p = f"{kind}_"
    cands = res.get("cands", [])
    r[p + "n_candidates"] = len(cands)
    if res.get("error"):
        r[p + "error"] = res["error"][:80]
    if not cands:
        r[p + "matched"] = False
        return r
    t = laea(lake["lat"], lake["lon"])
    pt = tr(Point(lake["lon"], lake["lat"]), t)
    eng = None
    if poly_feat is not None:
        eng = tr(shape(poly_feat["geometry"]).buffer(0), t)
    rows = []
    for c in cands:
        g = shape(c["geom"])
        if g.is_empty:
            continue
        g = g.buffer(0)
        gp = tr(g, t)
        a = c["attrs"]
        nm = a.get("GNIS_NAME") or a.get("gnisidlabel")
        row = {"attrs": a, "name": nm, "g": gp, "area": gp.area, "contains_pt": gp.contains(pt),
               "dist": gp.distance(pt), "nm": name_match(nm, lake["name"])}
        row["cover"] = (gp.intersection(eng).area / gp.area) if eng is not None and gp.area > 0 else None
        rows.append(row)
    if eng is not None:
        matched = [x for x in rows if (x["cover"] or 0) >= 0.30 or x["contains_pt"]]
    else:
        # no Engine polygon: take the water containing the point, else the nearest big one within 1.5 km with a name match
        matched = [x for x in rows if x["contains_pt"]] or \
                  [x for x in sorted(rows, key=lambda z: z["dist"]) if x["dist"] < 1500 and x["nm"] > 0][:1]
    r[p + "matched"] = bool(matched)
    r[p + "point_in_water"] = any(x["contains_pt"] for x in rows)
    if not matched:
        near = sorted(rows, key=lambda z: z["dist"])[:1]
        r[p + "nearest_dist_m"] = rd(near[0]["dist"], 0) if near else None
        return r
    matched.sort(key=lambda z: -z["area"])
    u = unary_union([x["g"] for x in matched])
    top = matched[0]
    # Pieces of the same water the name-based pick may have dropped: unnamed (or same-named) reference features that
    # touch the Engine polygon (<=100 m) but are not matched. Large ones mean the polygon is a partial reservoir.
    if eng is not None:
        miss = [x for x in rows if x not in matched and x["g"].distance(eng) <= 100
                and (not x["name"] or x["nm"] >= 0.99) and x["area"] >= 0.02 * eng.area]
        r[p + "adjacent_unmatched_n"] = len(miss)
        r[p + "adjacent_unmatched_km2"] = rd(sum(x["area"] for x in miss) / 1e6, 2)
        r[p + "adjacent_unmatched_ids"] = ";".join(str(x["attrs"].get("PERMANENT_IDENTIFIER") or x["attrs"].get("id3dhp")) for x in miss[:4])
    r[p + "matched_ids"] = ";".join(str(x["attrs"].get("PERMANENT_IDENTIFIER") or x["attrs"].get("id3dhp")) for x in matched[:6])
    r[p + "top_name"] = top["name"]
    r[p + "top_ftype"] = top["attrs"].get("FTYPE") or top["attrs"].get("featuretypelabel")
    r[p + "top_attr_area_km2"] = rd(top["attrs"].get("AREASQKM") or top["attrs"].get("areasqkm"), 3)
    r[p + "union_area_km2"] = rd(u.area / 1e6, 3)
    fd = top["attrs"].get("FDATE") or top["attrs"].get("featuredate")
    r[p + "feature_date"] = time.strftime("%Y-%m-%d", time.gmtime(fd / 1000)) if fd else None
    r[p + "workunit"] = top["attrs"].get("workunitid")
    r[p + "resolution"] = top["attrs"].get("RESOLUTION")
    r[p + "name_match"] = rd(max(x["nm"] for x in matched), 2)
    if eng is not None:
        inter = eng.intersection(u).area
        union = eng.union(u).area
        r[p + "area_ratio"] = rd(eng.area / u.area, 4) if u.area else None
        r[p + "iou"] = rd(inter / union, 4) if union else None
        r[p + "engine_outside_ref_km2"] = rd((eng.area - inter) / 1e6, 3)
        r[p + "ref_outside_engine_km2"] = rd((u.area - inter) / 1e6, 3)
        r[p + "ref_features_matched"] = len(matched)
    return r


def run_ref_stage(kind, lakes, polys, workers=4):
    out = {}

    def one(lake):
        feat = polys.get(lake["id"])
        try:
            res = ref_query(kind, lake, feat, None)
            return lake["id"], compare_ref(kind, lake, feat, res)
        except Exception as e:  # noqa: BLE001
            return lake["id"], {f"{kind}_error": str(e)[:100], f"{kind}_matched": False}

    with ThreadPoolExecutor(workers) as ex:
        for i, (lid, row) in enumerate(ex.map(one, lakes)):
            out[lid] = row
            if (i + 1) % 50 == 0:
                print(f"  {kind}: {i + 1}/{len(lakes)}", flush=True)
    return out


# ---------------------------------------------------------------- stage: OSM names/bbox (Overpass)
# One Overpass query PER STATE (name-token regex of that state's directory lakes) instead of one per lake: the public
# instances throttle/504 hundreds of small "around" queries (measured: 4 results in 10 min), a state query is ~1 request.

STATE_ISO = lambda st: f"US-{st}"  # noqa: E731


def lake_tokens(name):
    words = [w for w in re.sub(r"[^A-Za-z0-9 ]", " ", re.sub(r"\(.*?\)", " ", name)).split() if len(w) >= 4]
    stop = {"lake", "lakes", "reservoir", "pond", "ponds", "river", "dam"}
    return [w for w in words if w.lower() not in stop]


def osm_state(st, toks):
    toks = sorted(set(toks))
    rx = "|".join(re.escape(t) for t in toks)
    q = (f'[out:json][timeout:180];area["ISO3166-2"="{STATE_ISO(st)}"]->.a;'
         f'(relation["natural"="water"]["name"~"{rx}",i](area.a);way["natural"="water"]["name"~"{rx}",i](area.a););out tags bb;')

    def go():
        last = None
        for url in OVERPASS:
            try:
                return http_json(url, data={"data": q}, timeout=150, retries=3)
            except Exception as e:  # noqa: BLE001
                last = e
        raise RuntimeError(str(last))

    return cached(f"osmstate|{st}|{rx}", go)


def run_osm_stage(lakes, polys, workers=1):
    by_state = {}
    for l in lakes:
        for st in set(l.get("states") or [l["state"]]):
            by_state.setdefault(st, []).extend(lake_tokens(l["name"]))
    els_by_state = {}
    for i, (st, toks) in enumerate(sorted(by_state.items())):
        try:
            els_by_state[st] = [e for e in osm_state(st, toks).get("elements", []) if e.get("bounds")]
        except Exception as e:  # noqa: BLE001
            els_by_state[st] = None
            print(f"  osm {st}: {str(e)[:80]}", flush=True)
        time.sleep(2)
        print(f"  osm state {st} ({i + 1}/{len(by_state)}): {None if els_by_state[st] is None else len(els_by_state[st])} elements", flush=True)
    out = {}
    for lake in lakes:
        sts = set(lake.get("states") or [lake["state"]])
        if all(els_by_state.get(st) is None for st in sts):
            out[lake["id"]] = {"osm_error": "overpass unavailable for state"}
            continue
        els = [e for st in sts for e in (els_by_state.get(st) or [])]
        out[lake["id"]] = osm_row(lake, polys.get(lake["id"]), els)
    return out


def osm_row(lake, poly_feat, els):
    pbox = shapely.geometry.box(*shape(poly_feat["geometry"]).bounds) if poly_feat is not None else None
    pt = Point(lake["lon"], lake["lat"])
    r = {}
    best, n = None, 0
    for e in els:
        b = e["bounds"]
        bb = shapely.geometry.box(b["minlon"], b["minlat"], b["maxlon"], b["maxlat"])
        if pbox is not None:
            if not bb.intersects(pbox):
                continue
            iou = bb.intersection(pbox).area / bb.union(pbox).area
        else:
            if bb.distance(pt) > 0.05:
                continue
            iou = 1.0 if bb.contains(pt) else 0.0
        n += 1
        nm = e.get("tags", {}).get("name")
        nmv = name_match(nm, lake["name"])
        score = nmv * 2 + iou
        if best is None or score > best[0]:
            best = (score, e, nmv, iou, bb)
    r["osm_n_features"] = n
    if best:
        _, e, nmv, iou, bb = best
        r.update({"osm_best_name": e.get("tags", {}).get("name"), "osm_best_type": f"{e['type']}/{e['id']}",
                  "osm_water_tag": e.get("tags", {}).get("water"), "osm_name_match": rd(nmv, 2),
                  "osm_bbox_iou": rd(iou, 3), "osm_wikidata": e.get("tags", {}).get("wikidata")})
    return r


# ---------------------------------------------------------------- stage: USACE reservoirs (operator, "maximum conservation pool or a reasonable representation")

USACE_FS = "https://services7.arcgis.com/n1YM8pTrFmm7L4hs/arcgis/rest/services/usace_rez/FeatureServer/0/query"
USACE_FILE = os.path.join(GEO, "sources", "usace_rez.geojson")


def fetch_usace():
    if os.path.exists(USACE_FILE):
        return
    os.makedirs(os.path.dirname(USACE_FILE), exist_ok=True)
    q = USACE_FS + "?" + urllib.parse.urlencode({"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson"})
    req = urllib.request.Request(q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(USACE_FILE, "wb") as fh:
        fh.write(r.read())


def run_usace_stage(lakes, polys):
    from shapely.strtree import STRtree
    fetch_usace()
    fc = json.load(open(USACE_FILE))
    feats = [f for f in fc["features"] if f.get("geometry")]
    geoms = [shape(f["geometry"]).buffer(0) for f in feats]
    tree = STRtree(geoms)
    out = {}
    for lake in lakes:
        pf = polys.get(lake["id"])
        t = laea(lake["lat"], lake["lon"])
        tol_deg = point_tolerance_m(lake) / 111_000.0
        probe = shape(pf["geometry"]).buffer(0) if pf is not None else Point(lake["lon"], lake["lat"]).buffer(tol_deg)
        idx = tree.query(probe)
        rows = []
        for i in idx:
            g = geoms[i]
            nm = name_match(feats[i]["properties"]["NAME"], lake["name"])
            near_pt = g.distance(Point(lake["lon"], lake["lat"])) <= tol_deg
            if pf is not None:
                inter = tr(g.intersection(probe), t).area
                ga = tr(g, t).area
                cover = inter / ga if ga else 0
                if cover < 0.30 and not (near_pt and nm > 0):
                    continue
            elif not (near_pt and nm > 0):
                continue
            rows.append((nm, i))
        if not rows:
            out[lake["id"]] = {"usace_matched": False}
            continue
        rows.sort(key=lambda r: -r[0])
        sel = [i for nm, i in rows if nm > 0] or [rows[0][1]]
        u = unary_union([geoms[i] for i in sel])
        ua = tr(u, t).area
        pr = feats[sel[0]]["properties"]
        r = {"usace_matched": True, "usace_name": pr["NAME"], "usace_nidid": (pr.get("NIDID") or "").strip(),
             "usace_district": pr.get("DISTRICT"), "usace_dry": pr.get("DRY"), "usace_n_polygons": len(sel),
             "usace_area_km2": rd(ua / 1e6, 3), "usace_name_match": rd(rows[0][0], 2)}
        if pf is not None:
            e = tr(probe, t)
            inter = e.intersection(tr(u, t)).area
            r["usace_area_ratio"] = rd(e.area / ua, 4) if ua else None
            r["usace_iou"] = rd(inter / e.union(tr(u, t)).area, 4)
        out[lake["id"]] = r
    return out


# ---------------------------------------------------------------- stage: NID normal-pool surface area (USACE National Inventory of Dams)
# NID SURFACE_AREA is acres at normal pool (owner-reported). It is a point dataset - used here only as an independent
# check on how much of the reservoir the polygon covers. Source: the NID v1 subset the 'context' thread pulled (read-only).

NID_FILE = os.path.join(DATA, "context", "nid", "nid_v1_subset.json")


def run_nid_stage(lakes, polys):
    if not os.path.exists(NID_FILE):
        return {}
    nid = json.load(open(NID_FILE))
    pts = [(r["LATITUDE"], r["LONGITUDE"], r) for r in nid if r.get("LATITUDE") and r.get("LONGITUDE") and r.get("SURFACE_AREA")]
    lat = np.array([p[0] for p in pts]); lon = np.array([p[1] for p in pts])
    out = {}
    for lake in lakes:
        d_km = np.hypot((lat - lake["lat"]) * 111.0, (lon - lake["lon"]) * 111.0 * math.cos(math.radians(lake["lat"])))
        tol = max(25.0, point_tolerance_m(lake) / 1000 * 3)
        best = None
        for i in np.where(d_km <= tol)[0]:
            r = pts[i][2]
            nm = name_match(r["NAME"], lake["name"])
            if nm >= 0.5 and (best is None or r["SURFACE_AREA"] > best["SURFACE_AREA"]):
                best = dict(r)
                best["_d"] = float(d_km[i])
        if best:
            out[lake["id"]] = {"nid_id": best["NIDID"], "nid_name": best["NAME"], "nid_dist_km": rd(best["_d"], 1),
                               "nid_surface_km2": rd(best["SURFACE_AREA"] * 0.00404686, 2)}
            pf = polys.get(lake["id"])
            if pf is not None:
                ea = pf["properties"].get("areaKm2")
                out[lake["id"]]["nid_area_ratio"] = rd(ea / out[lake["id"]]["nid_surface_km2"], 3) if out[lake["id"]]["nid_surface_km2"] else None
    return out


# ---------------------------------------------------------------- stage: JRC GSW (computed by geometry_gsw.py in the rasterio venv)


def run_hl_stage():
    p = os.path.join(GEO, "hydrolakes_metrics.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def run_gsw_stage():
    p = os.path.join(GEO, "gsw_metrics.json")
    return json.load(open(p)) if os.path.exists(p) else {}


# ---------------------------------------------------------------- stage: classify

# Rules (documented in LAKE_BRAIN_GEOMETRY_RESEARCH.md). Evidence in each row: NHD HR / 3DHP waterbody match (provenance check -
# the Engine polygons ARE NHD-derived, so this proves the right feature was picked, not that the extent is right), plus the
# independent checks: USACE reservoir polygon, NID normal-pool surface area, JRC GSW occurrence, OSM name+bbox.
#  MISSING  no Engine polygon
#  LOW      geometry present but contradicted or unverifiable: invalid; or no NHD/USACE match and no OSM agreement; or NHD
#           area ratio outside 0.5..2 / IoU < 0.5; or BOTH independent pool-area sources (NID, USACE) put the polygon outside
#           0.5..2x (one alone is soft: NID has 10x unit errors, e.g. Bull Shoals); or < 20% of the polygon was ever water in
#           GSW; or identity risk: the directory point is farther from the polygon than max(3 km, 3x rounding tolerance,
#           0.6*sqrt(area_km2) km)
#  HIGH     source == NHD name pick; valid, not a GeometryCollection; NHD ratio 0.93..1.07, IoU >= 0.93, name match >= 0.5;
#           directory point within the identity allowance; one substantial part; no large unmatched adjacent NHD piece (< 5% of area);
#           NID and USACE ratios (when present) within 0.80..1.25; GSW >= 50% of polygon was water >= half the time (when present)
#  MEDIUM   everything else (plausible polygon with at least one soft defect: repaired/trimmed/osm source, multi-part,
#           extent 0.5..0.8 or 1.25..2 of the pool, partial-piece suspicion, point drift, weak name)
def _f(row, k):
    v = row.get(k)
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def classify(row):
    reasons = []
    if not row.get("has_polygon") in (True, "True"):
        return "MISSING", ["no Engine polygon"]
    src = row.get("source") or ""
    valid = row.get("valid") in (True, "True")
    pok = row.get("point_within_tolerance") in (True, "True")
    tol = _f(row, "point_tolerance_m") or 300
    dist = _f(row, "dist_point_to_polygon_m") or 0
    nhd_m = row.get("nhd_matched") in (True, "True")
    usace_m = row.get("usace_matched") in (True, "True")
    ratio, iou, nm = _f(row, "nhd_area_ratio"), _f(row, "nhd_iou"), _f(row, "nhd_name_match") or 0.0
    osm_ok = (_f(row, "osm_name_match") or 0) >= 0.5 and (_f(row, "osm_bbox_iou") or 0) >= 0.5
    subst = int(_f(row, "n_parts_ge_1pct") or 1)
    gc = row.get("has_geometrycollection") in (True, "True")
    garea = _f(row, "geom_area_km2") or 1.0
    adj = _f(row, "nhd_adjacent_unmatched_km2") or 0.0
    nid_r, us_r = _f(row, "nid_area_ratio"), _f(row, "usace_area_ratio")
    gsw_in = _f(row, "gsw_inside_ge50_pct")
    low, soft = [], []
    if not valid:
        low.append("invalid geometry")
    if gc:
        soft.append("GeometryCollection (LineString member)")
    if not nhd_m and not usace_m and not osm_ok:
        low.append("no NHD / USACE / OSM corroboration")
    elif not nhd_m:
        soft.append("no NHD waterbody overlap")
    if ratio is not None:
        if ratio < 0.5 or ratio > 2.0:
            low.append(f"NHD area ratio {ratio:.2f}")
        elif not 0.93 <= ratio <= 1.07:
            soft.append(f"NHD area ratio {ratio:.2f}")
    if iou is not None:
        if iou < 0.5:
            low.append(f"NHD IoU {iou:.2f}")
        elif iou < 0.93:
            soft.append(f"NHD IoU {iou:.2f}")
    allowed = max(3000.0, 3 * tol, 600.0 * math.sqrt(garea))   # a big reservoir's registry point may sit on the dam/town, km from water
    if dist > allowed:
        low.append(f"identity risk: directory point {dist:.0f} m from polygon (allowed {allowed:.0f} m)")
    # dist within `allowed` but beyond the rounding tolerance is a DIRECTORY coordinate defect (reported in point_flag), not a polygon defect
    if subst > 1:
        soft.append(f"{subst} substantial parts")
    if adj and adj / garea >= 0.05:
        soft.append(f"unmatched adjacent NHD piece(s) {adj:.1f} km2 ({100 * adj / garea:.0f}% of polygon)")
    bad_extent = 0
    for lab, r in (("NID", nid_r), ("USACE", us_r)):
        if r is None:
            continue
        if r < 0.5 or r > 2.0:
            bad_extent += 1
            soft.append(f"{lab} pool-area ratio {r:.2f}")
        elif not 0.80 <= r <= 1.25:
            soft.append(f"{lab} pool-area ratio {r:.2f}")
    if bad_extent >= 2:
        low.append("NID and USACE both disagree with polygon area by >2x")
    if gsw_in is not None:
        if gsw_in < 20:
            low.append(f"only {gsw_in:.0f}% of polygon was water >=50% of the time (GSW)")
        elif gsw_in < 50:
            soft.append(f"{gsw_in:.0f}% of polygon water >=50% of time (GSW)")
    if src != "name":
        soft.append(f"source {src}")
    if row.get("trimmed") not in (None, "", "None", False, "False"):
        soft.append("trimmed to nearest piece")
    if nhd_m and nm < 0.5:
        soft.append("NHD name differs from directory name")
    if low:
        return "LOW", low + soft
    if soft:
        return "MEDIUM", soft
    return "HIGH", []


def repair_hint(row):
    """If adding the unmatched adjacent (unnamed / same-named) NHD pieces brings the area in line with an independent
    pool-area source (NID / USACE), the polygon is a PARTIAL reservoir and the fix is mechanical (union the pieces)."""
    adj, g = _f(row, "nhd_adjacent_unmatched_km2") or 0.0, _f(row, "geom_area_km2") or 0.0
    if not adj or not g or adj / g < 0.05:
        return ""
    full = g + adj
    hits = []
    for lab, ref in (("NID", _f(row, "nid_surface_km2")), ("USACE", _f(row, "usace_area_km2"))):
        if ref and 0.85 <= full / ref <= 1.15 and not 0.85 <= g / ref <= 1.15:
            hits.append(f"{lab} {ref:.0f}")
    row["area_with_adjacent_km2"] = round(full, 2)
    return ("add_adjacent_pieces (+%.1f km2 -> %.0f; matches %s)" % (adj, full, ", ".join(hits))) if hits else "review_adjacent_pieces (+%.1f km2)" % adj


def point_flag(row):
    if row.get("has_polygon") not in (True, "True"):
        return ""
    dist, tol = _f(row, "dist_point_to_polygon_m") or 0, _f(row, "point_tolerance_m") or 300
    garea = _f(row, "geom_area_km2") or 1.0
    allowed = max(3000.0, 3 * tol, 600.0 * math.sqrt(garea))
    return "identity_risk" if dist > allowed else ("off_water" if dist > tol else "ok")


def stage_classify(rows):
    for r in rows:
        c, why = classify(r)
        r["confidence"] = c
        r["why"] = "; ".join(why)
        r["point_flag"] = point_flag(r)
        r["repair_hint"] = repair_hint(r)
    return rows


# ---------------------------------------------------------------- driver


def read_csv():
    if not os.path.exists(OUT_CSV):
        return {}
    with open(OUT_CSV, newline="") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def write_csv(rows):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    os.makedirs(GEO, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def summary(rows):
    from collections import Counter

    def num(r, k):
        try:
            return float(r[k])
        except (KeyError, TypeError, ValueError):
            return None

    S = {"generated": time.strftime("%Y-%m-%d", time.gmtime()), "directory_lakes": len(rows),
         "with_polygon": sum(1 for r in rows if str(r.get("has_polygon")) == "True"),
         "confidence": dict(Counter(r["confidence"] for r in rows)),
         "source": dict(Counter(r.get("source") or "(none)" for r in rows)),
         "geom_type": dict(Counter(r.get("geom_type") or "(none)" for r in rows))}
    S["missing_ids"] = sorted(r["id"] for r in rows if r["confidence"] == "MISSING")
    S["invalid_ids"] = sorted(r["id"] for r in rows if str(r.get("valid")) == "False")
    S["directory_point_flag"] = dict(Counter(r.get("point_flag") or "(none)" for r in rows))
    S["identity_risk_ids"] = sorted(r["id"] for r in rows if r.get("point_flag") == "identity_risk")
    S["geometrycollection_ids"] = sorted(r["id"] for r in rows if str(r.get("has_geometrycollection")) == "True")
    S["point_outside_polygon"] = sum(1 for r in rows if r.get("contains_point") == "False")
    S["point_outside_beyond_rounding_tolerance"] = sum(1 for r in rows if r.get("point_within_tolerance") == "False")
    ratios = [num(r, "nhd_area_ratio") for r in rows]
    ratios = [x for x in ratios if x is not None]
    ious = [num(r, "nhd_iou") for r in rows]
    ious = [x for x in ious if x is not None]
    if ratios:
        S["nhd_area_ratio"] = {"n": len(ratios), "median": rd(float(np.median(ratios)), 4),
                               "p05": rd(float(np.percentile(ratios, 5)), 4), "p95": rd(float(np.percentile(ratios, 95)), 4)}
    if ious:
        S["nhd_iou"] = {"n": len(ious), "median": rd(float(np.median(ious)), 4), "p05": rd(float(np.percentile(ious, 5)), 4)}
    S["nhd_matched"] = sum(1 for r in rows if r.get("nhd_matched") == "True")
    S["tdhp_matched"] = sum(1 for r in rows if r.get("tdhp_matched") == "True")
    S["tdhp_workunits"] = dict(Counter((r.get("tdhp_workunit") or "(none)") for r in rows if r.get("tdhp_matched") == "True").most_common(12))
    S["usace_matched"] = sum(1 for r in rows if r.get("usace_matched") == "True")
    ur = [num(r, "usace_area_ratio") for r in rows]
    ur = [x for x in ur if x is not None]
    if ur:
        S["usace_area_ratio"] = {"n": len(ur), "median": rd(float(np.median(ur)), 4), "p05": rd(float(np.percentile(ur, 5)), 4),
                                 "p95": rd(float(np.percentile(ur, 95)), 4)}
    S["osm_name_ok"] = sum(1 for r in rows if (num(r, "osm_name_match") or 0) >= 0.5)
    S["with_sliver_parts"] = sum(1 for r in rows if (num(r, "n_parts_lt_1pct") or 0) > 0)
    S["with_multiple_substantial_parts"] = sum(1 for r in rows if (num(r, "n_parts_ge_1pct") or 0) > 1)
    S["total_vertices"] = int(sum(num(r, "n_vertices") or 0 for r in rows))
    w = [r for r in rows if str(r.get("has_polygon")) == "True"]
    nh = [int(num(r, "n_holes") or 0) for r in w]
    S["holes"] = {"lakes_with_holes": sum(1 for x in nh if x), "total_holes": sum(nh), "holes_lt_100m2": int(sum(num(r, "holes_lt_100m2") or 0 for r in w)),
                  "hole_area_km2_total": rd(sum(num(r, "hole_area_km2") or 0 for r in w), 1)}
    S["slivers"] = {"lakes_with_sliver_parts": S["with_sliver_parts"], "sliver_area_km2_total": rd(sum(num(r, "sliver_area_km2") or 0 for r in w), 2)}
    S["repair_hints"] = dict(Counter((r.get("repair_hint") or "").split(" ")[0] or "none" for r in w))
    S["adjacent_unmatched_lakes"] = sum(1 for r in w if (num(r, "nhd_adjacent_unmatched_km2") or 0) > 0)
    S["nid_matched_with_polygon"] = sum(1 for r in w if num(r, "nid_area_ratio") is not None)
    S["nid_ratio_within_20pct"] = sum(1 for r in w if num(r, "nid_area_ratio") is not None and 0.8 <= num(r, "nid_area_ratio") <= 1.25)
    S["hydrolakes_matched"] = sum(1 for r in rows if r.get("hl_matched") == "True")
    S["gsw_inside_ge50_median_pct"] = rd(float(np.median([num(r, "gsw_inside_ge50_pct") for r in w if num(r, "gsw_inside_ge50_pct") is not None])), 1)
    S["nhd_feature_year"] = dict(sorted(Counter((r.get("nhd_feature_date") or "")[:4] for r in w if r.get("nhd_feature_date")).items()))
    S["median_vertices"] = int(np.median([num(r, "n_vertices") or 0 for r in w]))
    S["median_segment_m"] = rd(float(np.median([num(r, "mean_seg_m") or 0 for r in w])), 1)
    for name, fn in (("simplify_sizes_pilots", "simplify_sizes.json"), ("fleet_delivery_sizes", "fleet_delivery_sizes.json")):
        fp = os.path.join(GEO, fn)
        if os.path.exists(fp):
            S[name] = json.load(open(fp))
    for name, rel in (("holes_vs_gsw_pilots", "gsw/holes_pilots.json"), ("osm_polygons_pilots", "osm/pilots_osm.json")):
        fp = os.path.join(GEO, rel)
        if os.path.exists(fp):
            S[name] = json.load(open(fp))
    S["pilots"] = {r["id"]: {k: r.get(k) for k in ("confidence", "geom_type", "n_parts", "n_holes", "n_vertices", "geom_area_km2",
                                                  "nhd_area_ratio", "nhd_iou", "contains_point")} for r in rows if r["id"] in PILOTS}
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "local", "nhd", "tdhp", "osm", "usace", "nid", "gsw", "hl", "classify"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="debug: only the first N lakes")
    ap.add_argument("--only", default="", help="comma-separated lake ids")
    a = ap.parse_args()
    lakes = load_directory()
    polys = load_polygons()
    if a.only:
        want = set(a.only.split(","))
        lakes = [l for l in lakes if l["id"] in want]
    if a.limit:
        lakes = lakes[: a.limit]
    prev = read_csv()
    rows = {l["id"]: dict(prev.get(l["id"], {})) for l in lakes}
    stages = ["local", "nhd", "tdhp", "osm", "usace", "nid", "gsw", "hl", "classify"] if a.stage == "all" else [a.stage]
    for st in stages:
        t0 = time.time()
        print(f"== stage {st}", flush=True)
        if st in ("nhd", "tdhp", "osm", "usace", "nid", "gsw", "hl"):   # drop stale columns of this stage (e.g. an old *_error)
            for r in rows.values():
                for k in [k for k in r if k.startswith(st + "_")]:
                    del r[k]
        if st == "local":
            for l in lakes:
                rows[l["id"]].update(local_metrics(l, polys.get(l["id"])))
        elif st in ("nhd", "tdhp"):
            for lid, d in run_ref_stage(st, lakes, polys, a.workers).items():
                rows[lid].update(d)
        elif st == "usace":
            for lid, d in run_usace_stage(lakes, polys).items():
                rows[lid].update(d)
        elif st == "hl":
            for lid, d in run_hl_stage().items():
                if lid in rows:
                    rows[lid].update(d)
        elif st == "gsw":
            for lid, d in run_gsw_stage().items():
                if lid in rows:
                    rows[lid].update(d)
        elif st == "nid":
            for lid, d in run_nid_stage(lakes, polys).items():
                rows[lid].update(d)
        elif st == "osm":
            for lid, d in run_osm_stage(lakes, polys, 2).items():
                rows[lid].update(d)
        elif st == "classify":
            stage_classify(list(rows.values()))
        print(f"   {time.time() - t0:.0f}s", flush=True)
        # keep complete CSV (merge with rows not in this run)
        merged = {**prev, **{k: v for k, v in rows.items()}}
        write_csv(list(merged.values()))
    if "classify" in stages or a.stage == "all":
        allrows = list(read_csv().values())
        S = summary(allrows)
        os.makedirs(os.path.dirname(OUT_SUMMARY), exist_ok=True)
        json.dump(S, open(OUT_SUMMARY, "w"), indent=1, sort_keys=True)
        print(json.dumps(S, indent=1)[:1500])


if __name__ == "__main__":
    main()
