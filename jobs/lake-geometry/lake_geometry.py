"""Lake Registry geometry: pure functions (no network, no filesystem except where stated).

Everything here is deterministic: same inputs + same shapely/GEOS/pyproj versions -> same bytes.
`build_geometry.py` is the driver; the tests import this module.

Conventions
  * Stored geometry is WGS84 lon/lat (EPSG:4326), RFC 7946 ring orientation, 5-decimal coordinates (~1.1 m).
  * All tolerances and areas are computed in a lake-local Lambert azimuthal equal-area projection (metres).
  * Source of truth for the shoreline is the USGS National Hydrography Dataset (NHD) High Resolution waterbody layer
    (public domain). Nothing is ever invented: if no usable NHD shape exists the geometry is null with a reason.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import re

import numpy as np
import pyproj
import shapely
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

GEOMETRY_VERSION = "v1"
DISPLAY_TOL_M = 50.0
ANALYSIS_TOL_M = 25.0
MIN_HOLE_M2 = 100.0          # islands (holes) smaller than this are noise; Guntersville keeps 402 of 419
MIN_PART_M2 = 100.0          # water parts smaller than this are dropped (the largest part is always kept)
COORD_DECIMALS = 5
GRID = 10.0 ** -COORD_DECIMALS

_SLUG = re.compile(r"[^A-Za-z0-9]+")


# ------------------------------------------------------------------ identity


def lake_key(lake_id: str) -> str:
    """Brain RTDB lake key: every run of non-alphanumerics becomes one '_' (same as
    jobs/brain_platform/sector_brain_platform/keys.py::lake_key)."""
    return _SLUG.sub("_", lake_id)


_STOP = {"lake", "lakes", "reservoir", "res", "pond", "the", "of", "dam", "river", "impoundment", "bay", "flowage"}


def norm_name(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return {w for w in s.split() if w not in _STOP}


def name_match(a, b) -> float:
    """Token overlap of two lake names, 0..1 (1.0 = the shorter token set is contained in the longer)."""
    A, B = norm_name(a), norm_name(b)
    if not A or not B:
        return 0.0
    return len(A & B) / max(1, min(len(A), len(B)))


# ------------------------------------------------------------------ projection


_TR = {}


def local_crs(lon: float, lat: float) -> str:
    return f"+proj=laea +lat_0={round(lat, 3):.3f} +lon_0={round(lon, 3):.3f} +datum=WGS84 +units=m"


def transformers(lon: float, lat: float):
    """(to_metres, to_degrees) for a lake-local equal-area projection (cached; the centre is rounded to 0.001 deg so
    the same lake always gets the same projection)."""
    k = (round(lon, 3), round(lat, 3))
    if k not in _TR:
        crs = local_crs(*k)
        _TR[k] = (pyproj.Transformer.from_crs(4326, crs, always_xy=True),
                  pyproj.Transformer.from_crs(crs, 4326, always_xy=True))
    return _TR[k]


def project(geom, t):
    return shapely.transform(geom, lambda c: np.column_stack(t.transform(c[:, 0], c[:, 1])))


def center_of(geom):
    w, s, e, n = geom.bounds
    return (w + e) / 2.0, (s + n) / 2.0


# ------------------------------------------------------------------ repair


def parts_of(g):
    """All Polygon parts of any geometry (GeometryCollection members, MultiPolygon parts); lines and points are dropped."""
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


def as_polygonal(parts):
    """Polygon (one part) / MultiPolygon (several) / None (empty)."""
    parts = [p for p in parts if p is not None and not p.is_empty]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def repair(g):
    """Return a valid polygonal geometry from anything polygonal: GeometryCollection -> its polygons (a LineString member,
    as in Devils Lake|ND, is dropped), invalid rings (bow-ties, self-touching holes) are repaired with make_valid, and the
    result is a Polygon or MultiPolygon. Returns None when nothing polygonal is left."""
    if g is None or g.is_empty:
        return None
    if not g.is_valid:
        g = shapely.make_valid(g)
    ps = parts_of(g)
    if not ps:
        return None
    u = unary_union(ps) if len(ps) > 1 else ps[0]
    if not u.is_valid:
        u = shapely.make_valid(u)
    return as_polygonal(parts_of(u))


def drop_small_holes(g, min_hole_m2=MIN_HOLE_M2):
    """Remove interior rings (islands) with area < min_hole_m2. `g` must be in a METRIC projection. Larger islands are kept
    untouched (Guntersville: 419 holes, mostly real islands -> 402 kept)."""
    out = []
    for p in parts_of(g):
        keep = [r for r in p.interiors if Polygon(r).area >= min_hole_m2]
        out.append(Polygon(p.exterior, keep))
    return as_polygonal(out)


def drop_small_parts(g, min_part_m2=MIN_PART_M2):
    """Remove whole parts below min_part_m2 (metric projection). The largest part is always kept."""
    ps = parts_of(g)
    if not ps:
        return None
    big = max(ps, key=lambda p: p.area)
    return as_polygonal([p for p in ps if p.area >= min_part_m2 or p is big])


def clean_metric(g, min_hole_m2=MIN_HOLE_M2, min_part_m2=MIN_PART_M2):
    """repair -> drop tiny holes -> drop tiny parts, in metres."""
    g = repair(g)
    if g is None:
        return None
    g = drop_small_holes(g, min_hole_m2)
    g = drop_small_parts(g, min_part_m2)
    return repair(g)


def simplify_metric(g, tol_m):
    """Topology-preserving Douglas-Peucker in metres (never self-intersects, never merges rings), then re-clean."""
    if g is None:
        return None
    if tol_m and tol_m > 0:
        g = g.simplify(tol_m, preserve_topology=True)
    return clean_metric(g)


def finalize_degrees(g):
    """Snap to the 5-decimal grid (valid-output mode), repair, orient rings per RFC 7946 (exterior CCW, holes CW)."""
    if g is None:
        return None
    g = shapely.set_precision(g, GRID)
    g = repair(g)
    if g is None:
        return None
    return as_polygonal([orient(p, 1.0) for p in parts_of(g)])


def is_degenerate(g, min_area_km2=0.02, min_vertices=8):
    """A shape that cannot be a lake outline (Lake Shafer: 4 vertices / 0 km2; Buckeye Lake: 6 vertices / 0.003 km2).
    `g` in degrees; area measured in the lake-local equal-area projection."""
    ps = parts_of(g)
    if not ps:
        return True
    c = center_of(g)
    area = project(g, transformers(*c)[0]).area / 1e6
    return area < min_area_km2 or nverts(g) < min_vertices


def nverts(g) -> int:
    return sum(len(p.exterior.coords) + sum(len(i.coords) for i in p.interiors) for p in parts_of(g))


def n_holes(g) -> int:
    return sum(len(p.interiors) for p in parts_of(g))


# ------------------------------------------------------------------ variants


TOL_SIZE_FRACTION = 0.025   # a tolerance never exceeds 2.5 % of sqrt(area): a 0.1 km2 pond is not simplified to a 50 m blob
TOL_MIN_M = 2.0


def effective_tolerance(tol_m, area_m2):
    """Nominal tolerance, capped for very small lakes (applies below ~4 km2 for 50 m and ~1 km2 for 25 m)."""
    return round(min(tol_m, max(TOL_MIN_M, TOL_SIZE_FRACTION * math.sqrt(max(area_m2, 0.0)))), 2)


def make_variant(union_deg, tol_m, center=None):
    """Canonical variant of a lake shoreline.

    union_deg  the unioned NHD waterbody pieces, degrees.
    tol_m      nominal Douglas-Peucker tolerance in metres (ANALYSIS_TOL_M or DISPLAY_TOL_M), capped for tiny lakes.
    Returns (geometry_deg, area_km2, effective_tol_m) or (None, 0.0, tol). The area is the equal-area area of the variant
    before the 5-decimal snap (the snap moves vertices by < 0.6 m)."""
    center = center or center_of(union_deg)
    to_m, to_deg = transformers(*center)
    gm = clean_metric(project(union_deg, to_m))
    if gm is None:
        return None, 0.0, tol_m
    eff = effective_tolerance(tol_m, gm.area)
    gm = simplify_metric(gm, eff)
    if gm is None:
        return None, 0.0, eff
    area = gm.area / 1e6
    gd = finalize_degrees(project(gm, to_deg))
    return gd, area, eff


def area_km2(g_deg, center=None) -> float:
    if g_deg is None or g_deg.is_empty:
        return 0.0
    center = center or center_of(g_deg)
    return project(g_deg, transformers(*center)[0]).area / 1e6


# ------------------------------------------------------------------ serialisation


def _walk(x):
    if isinstance(x[0], (int, float)):
        return [round(float(v), COORD_DECIMALS) for v in x]
    return [_walk(i) for i in x]


def geometry_json(g) -> dict:
    ps = parts_of(g)
    if len(ps) == 1:
        return {"type": "Polygon", "coordinates": _walk([[list(c) for c in r] for r in _rings(ps[0])])}
    return {"type": "MultiPolygon", "coordinates": [_walk([[list(c) for c in r] for r in _rings(p)]) for p in ps]}


def _rings(p):
    return [p.exterior.coords] + [i.coords for i in p.interiors]


def feature_bytes(geom_deg, properties: dict) -> bytes:
    """Deterministic GeoJSON Feature bytes (sorted property keys, compact separators, no NaN)."""
    f = {"type": "Feature", "properties": properties, "geometry": geometry_json(geom_deg)}
    return json.dumps(f, separators=(",", ":"), sort_keys=True, allow_nan=False).encode()


def gzip_bytes(b: bytes, level=9) -> bytes:
    """gzip with mtime=0 and no file name: identical input -> identical output (for a given zlib)."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=level, mtime=0) as z:
        z.write(b)
    return buf.getvalue()


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ pieces: which NHD waterbodies make the lake

ADJ_DIST_M = 100.0       # an unnamed / same-named NHD piece within 100 m of the matched water is part of the same lake
ADJ_MIN_SHARE = 0.02     # ... if it is at least 2 % of the matched area (research/geometry_audit.py)
COVER_MIN = 0.30         # an NHD feature is "matched" by an Engine polygon when >= 30 % of it lies inside
LOG_TOL = 0.05           # adjacent pieces are rejected only if they move the area >= 5 % (log) further from the references


def match_seed(rows, engine_usable, refs=()):
    """rows: dicts with keys g (metric polygon), area, contains_pt, dist, nm, cover, name. Returns the seed rows (the NHD
    features that ARE the lake) and the method label.

    engine_usable:  the Engine polygon is a real outline -> the features it covers (>= 30 % of the feature inside it).
                    Containing the directory point is NOT enough: registry coordinates are rounded and often sit in a neighbouring
                    lake (Big Creek Lake IA is inside Saylorville, Truman Lake MO inside Lake of the Ozarks).
    otherwise (or when nothing is covered), by point, name and area, largest wins:
        (a) name match >= 0.5 and within max(3 km, 600 m x sqrt(area km2)) of the point;
        (b) an unnamed feature of >= 0.05 km2 that contains the point;
        (c) a feature of any name that contains the point and whose area is within 0.8-1.25 of an independent pool-area
            reference (NID / USACE), e.g. Buckeye Lake OH is NHD 'Crane Lake', 11.2 km2, NID 11.3 km2.
    A differently-named water that contains the point and is not confirmed by area is a different lake and is never picked."""
    if engine_usable:
        seed = [r for r in rows if (r["cover"] or 0) >= COVER_MIN]
        if seed:
            return seed, "engine-overlap"
    a = [r for r in rows if r["nm"] >= 0.5 and r["dist"] <= max(3000.0, 600.0 * math.sqrt(r["area"] / 1e6))]
    if a:
        return [max(a, key=lambda r: r["area"])], "point-name-fallback"
    b = [r for r in rows if r["contains_pt"] and not r["name"] and r["area"] >= 0.05e6]
    if b:
        return [max(b, key=lambda r: r["area"])], "point-unnamed-fallback"
    refs = [x for x in refs if x]
    c = [r for r in rows if r["contains_pt"] and any(0.8 <= (r["area"] / 1e6) / x <= 1.25 for x in refs)]
    if c:
        return [max(c, key=lambda r: r["area"])], "point-area-fallback"
    return [], "none"


def adjacent_pieces(rows, seed):
    """Unnamed or same-named NHD features within ADJ_DIST_M of the seed union that are >= 2 % of its area."""
    if not seed:
        return []
    u = unary_union([r["g"] for r in seed])
    out = []
    for r in rows:
        if r in seed:
            continue
        if (not r["name"] or r["nm"] >= 0.99) and r["area"] >= ADJ_MIN_SHARE * u.area and r["g"].distance(u) <= ADJ_DIST_M:
            out.append(r)
    return out


def choose_variant(base_km2, union_km2, refs):
    """Include the adjacent pieces unless an independent pool-area reference says they make it worse.

    refs = [NID normal-pool surface area, USACE reservoir area] (km2, those that exist). The closest reference to either
    candidate decides (two independent sources disagreeing is common; NID has unit errors, so the best-matching one is
    used). With no reference the pieces are included (NHD splits one water body at unit boundaries; they touch it).
    Returns (use_union: bool, why: str)."""
    refs = [r for r in refs if r and r > 0]
    if not refs:
        return True, "no pool-area reference: connected NHD pieces included"
    d_base = min(abs(math.log(base_km2 / r)) for r in refs)
    d_union = min(abs(math.log(union_km2 / r)) for r in refs)
    if d_union <= d_base + LOG_TOL:
        return True, "union is %s the pool-area reference" % ("closer to" if d_union < d_base else "as close as the base to")
    return False, "union moves further from the pool-area reference (%.2f vs %.2f log units)" % (d_union, d_base)


# ------------------------------------------------------------------ confidence (re-derived after the union)

TOL_NEAR = (0.80, 1.25)   # pool-area ratio considered consistent
TOL_FAR = (0.5, 2.0)      # beyond this the polygon is contradicted


def point_flag(dist_m, tol_m, area_km2_):
    """identity-risk / off-water / ok  (research rule: allowed = max(3 km, 3 x rounding tolerance, 600 m x sqrt(km2)))."""
    allowed = max(3000.0, 3 * tol_m, 600.0 * math.sqrt(max(area_km2_, 0.0)))
    if dist_m > allowed:
        return "identity-risk"
    return "off-water" if dist_m > tol_m else "ok"


def derive_confidence(f):
    """Mechanical HIGH / MEDIUM / LOW / MISSING + reasons from facts about the NEW geometry.

    f keys (None = not measured):
      has_geometry  bool
      identity_pick 'engine-overlap' | 'point-name-fallback' | 'point-unnamed-fallback'
      engine_source the Engine's own pick label ('name', 'repaired:...', 'osm', '' when it had none)
      name_match    best token match of the NHD piece names vs the directory name (0..1)
      point_flag    from point_flag()
      dist_m, allowed_m  directory point to polygon distance and the identity allowance
      n_substantial_parts   parts >= 1 % of the area
      adjacent_rejected_km2 adjacent NHD pieces left OUT of the union (0 when all were included)
      area_km2, nid_km2, usace_km2   shoreline area and the independent pool-area references
      gsw_ge50_pct  % of the polygon that was water >= half the time in JRC GSW 1984-2021 (None if unmeasured)
      osm_ok        OSM name + bbox corroboration (only used for a fallback pick)
    Rules (same thresholds as the research audit LAKE_BRAIN_GEOMETRY_RESEARCH.md section 4.2, re-evaluated on the union):
      LOW     identity risk; or NID AND USACE both off by > 2x; or GSW < 20 %
      HIGH    no soft reason: valid single substantial part, NHD name >= 0.5, Engine pick was name-based (or the pick is
              an overlap with a name-matched feature), no adjacent piece left out, NID and USACE ratios (when present)
              within 0.80-1.25, GSW >= 50 %
      MEDIUM  everything else.
    A union that brings the area into 0.80-1.25 of NID/USACE therefore removes the "pool-area ratio" soft reason and a
    MEDIUM lake with no other reason becomes HIGH; this is how MEDIUM -> HIGH happens, nothing is overridden by hand."""
    if not f.get("has_geometry"):
        return "MISSING", [f.get("missing_reason") or "no usable polygon"]
    low, soft = [], []
    if f.get("point_flag") == "identity-risk":
        low.append("identity risk: directory point %.0f m from the shoreline (allowed %.0f m)" % (f["dist_m"], f["allowed_m"]))
    garea = f.get("area_km2") or 0.0
    bad = 0
    for lab, ref in (("NID", f.get("nid_km2")), ("USACE", f.get("usace_km2"))):
        if not ref:
            continue
        r = garea / ref
        if r < TOL_FAR[0] or r > TOL_FAR[1]:
            bad += 1
            soft.append(f"{lab} pool-area ratio {r:.2f}")
        elif not TOL_NEAR[0] <= r <= TOL_NEAR[1]:
            soft.append(f"{lab} pool-area ratio {r:.2f}")
    if bad >= 2:
        low.append("NID and USACE both disagree with the shoreline area by > 2x")
    g = f.get("gsw_ge50_pct")
    if g is not None:
        if g < 20:
            low.append(f"only {g:.0f}% of the shoreline was water >= 50% of the time (JRC GSW)")
        elif g < 50:
            soft.append(f"{g:.0f}% of the shoreline water >= 50% of the time (JRC GSW)")
    pick = f.get("identity_pick")
    if pick != "engine-overlap":
        soft.append("NHD pick by point/name fallback (the Engine polygon was missing or unusable)"
                    + ("; OSM corroborates" if f.get("osm_ok") else ""))
    if f.get("engine_source") not in ("name",) and pick == "engine-overlap":
        soft.append(f"Engine pick was a fallback ({f.get('engine_source') or 'unknown'})")
    if (f.get("name_match") or 0.0) < 0.5:
        soft.append("NHD name differs from directory name")
    if (f.get("n_substantial_parts") or 1) > 1:
        soft.append(f"{f['n_substantial_parts']} substantial parts")
    if f.get("adjacent_rejected_km2"):
        soft.append(f"adjacent NHD piece(s) {f['adjacent_rejected_km2']:.1f} km2 left out (move area away from pool references)")
    if f.get("point_flag") == "off-water":
        pass   # a directory coordinate defect, reported in pointFlag, not a shoreline defect
    if low:
        return "LOW", low + soft
    if soft:
        return "MEDIUM", soft
    return "HIGH", []


def confidence_score(level, reasons, corroborations=0):
    """Ordinal 0..1 score (NOT a probability): HIGH 0.90 + 0.02 per independent corroboration (max 0.98); MEDIUM 0.80 minus
    0.05 per reason (floor 0.50); LOW 0.45 minus 0.05 per reason beyond the first (floor 0.10); MISSING 0."""
    if level == "HIGH":
        return round(min(0.98, 0.90 + 0.02 * corroborations), 2)
    if level == "MEDIUM":
        return round(max(0.50, 0.80 - 0.05 * len(reasons)), 2)
    if level == "LOW":
        return round(max(0.10, 0.45 - 0.05 * max(0, len(reasons) - 1)), 2)
    return 0.0


# ------------------------------------------------------------------ index schema

LEVELS = ("HIGH", "MEDIUM", "LOW", "MISSING")
POINT_FLAGS = ("ok", "off-water", "identity-risk")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ENTRY_KEYS = ("lakeId", "lakeKey", "name", "aliases", "memberIds", "state", "states", "location", "externalIds", "bbox", "centroid",
               "labelPoint", "areaKm2", "geometry", "poolExtents", "geometryVersion", "geometryUpdatedAt", "geometryConfidence",
               "pointFlag", "classification")
_GEOM_KEYS = ("extentKind", "source", "sourceIds", "seedIds", "sourceDate", "pickMethod", "pieces", "adjacentPieces", "islands", "areaKm2",
              "displayToleranceM", "analysisToleranceM", "displayUrl", "analysisUrl", "bytes", "sha256", "license")
_EXT_KEYS = ("gnisId", "nhd", "nidId", "osm", "wikidata", "hydrolakes", "grand")


def validate_entry(e, base_url=None):
    """Schema check of one Lake Registry index entry. Returns a list of problems (empty = valid)."""
    bad = []

    def need(cond, msg):
        if not cond:
            bad.append(f"{e.get('lakeId')}: {msg}")
    for k in _ENTRY_KEYS:
        need(k in e, f"missing key {k}")
    if bad:
        return bad
    need(isinstance(e["lakeId"], str) and e["lakeId"], "lakeId")
    need(e["lakeKey"] == lake_key(e["lakeId"]), "lakeKey != lake_key(lakeId)")
    need(isinstance(e["aliases"], list) and all(isinstance(a, str) for a in e["aliases"]), "aliases")
    need(isinstance(e["memberIds"], list) and e["lakeId"] in e["memberIds"] and e["memberIds"] == sorted(set(e["memberIds"])), "memberIds")
    need(all(k in e["externalIds"] for k in _EXT_KEYS) and isinstance(e["externalIds"]["nhd"], list), "externalIds")
    need(isinstance(e["location"], dict) and -90 <= e["location"].get("lat", 999) <= 90 and -180 <= e["location"].get("lon", 999) <= 180, "location")
    need(e["geometryVersion"] == GEOMETRY_VERSION, "geometryVersion")
    need(isinstance(e["geometryUpdatedAt"], str) and e["geometryUpdatedAt"].endswith("Z"), "geometryUpdatedAt")
    c = e["geometryConfidence"]
    need(isinstance(c, dict) and c.get("level") in LEVELS and isinstance(c.get("reasons"), list)
         and isinstance(c.get("score"), (int, float)) and 0 <= c["score"] <= 1, "geometryConfidence")
    need(e["pointFlag"] in POINT_FLAGS + (None,), "pointFlag")
    need(isinstance(e["poolExtents"], list), "poolExtents")
    need(e["classification"] is None or isinstance(e["classification"], dict), "classification")
    g = e["geometry"]
    if g is None:
        need(c and c.get("level") == "MISSING", "geometry null requires confidence MISSING")
        need(bool(e.get("geometryMissingReason")), "geometry null requires geometryMissingReason")
        need(e["bbox"] is None and e["areaKm2"] is None and e["centroid"] is None, "null geometry has bbox/area/centroid")
    else:
        need(c and c.get("level") != "MISSING", "geometry present but confidence MISSING")
        for k in _GEOM_KEYS:
            need(k in g, f"geometry.{k}")
        if all(k in g for k in _GEOM_KEYS):
            for v in ("display", "analysis"):
                need(isinstance(g["sha256"].get(v), str) and _HEX64.match(g["sha256"][v]), f"sha256.{v}")
            need(g["displayUrl"].endswith(f"/lakes/{e['lakeKey']}/geometry.{GEOMETRY_VERSION}.display.geojson.gz"), "displayUrl")
            need(g["analysisUrl"].endswith(f"/lakes/{e['lakeKey']}/geometry.{GEOMETRY_VERSION}.analysis.geojson.gz"), "analysisUrl")
            if base_url:
                need(g["displayUrl"].startswith(base_url + "/") and g["analysisUrl"].startswith(base_url + "/"), "url base")
            need(g["source"] == "usgs-nhd-hr" and g["extentKind"] == "shoreline-nhd-hr-union" and g["sourceIds"], "source")
            need(g["bytes"]["displayGzip"] > 0 and g["bytes"]["analysisGzip"] > 0, "bytes")
            need(g["displayToleranceM"] == DISPLAY_TOL_M and g["analysisToleranceM"] == ANALYSIS_TOL_M, "tolerances")
        b = e["bbox"]
        need(isinstance(b, list) and len(b) == 4 and -180 <= b[0] < b[2] <= 180 and -90 <= b[1] < b[3] <= 90, "bbox")
        need(isinstance(e["centroid"], list) and len(e["centroid"]) == 2, "centroid")
        need(isinstance(e["areaKm2"], (int, float)) and e["areaKm2"] > 0, "areaKm2")
        need(e["pointFlag"] in POINT_FLAGS, "pointFlag required with geometry")
    return bad
