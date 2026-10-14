"""Small pure-Python geometry helpers for the coordinate review pack (no shapely / pyproj needed, so the review test suite runs anywhere).

Everything works on GeoJSON-style [lon, lat] coordinates. Distances are metres on a local equirectangular plane centred on the query
point; for the distances that matter here (a pin to its nearest shoreline, up to some tens of km) the error is far below the 25 m
simplification of the registry polygons.
"""
import math
import re

R_EARTH = 6371008.8


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(min(1.0, math.sqrt(a)))


def polygons_of(geom):
    """GeoJSON geometry -> list of polygons, each a list of rings (first = outer, rest = holes), rings as [[lon, lat], ...].
    Polygon, MultiPolygon and GeometryCollection (polygon members only; LineStrings are ignored) are supported."""
    if not geom:
        return []
    t = geom.get("type")
    if t == "Polygon":
        return [geom["coordinates"]]
    if t == "MultiPolygon":
        return list(geom["coordinates"])
    if t == "GeometryCollection":
        out = []
        for g in geom.get("geometries", []):
            out.extend(polygons_of(g))
        return out
    if t == "Feature":
        return polygons_of(geom.get("geometry"))
    if t == "FeatureCollection":
        out = []
        for f in geom.get("features", []):
            out.extend(polygons_of(f))
        return out
    return []


def _ring_contains(ring, x, y):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_polygons(lat, lon, polys):
    """True if the point is inside any polygon (and not in one of its holes). Boundary points count as outside, which is immaterial at 25 m."""
    for rings in polys:
        if rings and _ring_contains(rings[0], lon, lat) and not any(_ring_contains(h, lon, lat) for h in rings[1:]):
            return True
    return False


def _project(lat0, lon0):
    kx = math.cos(math.radians(lat0)) * math.pi / 180.0 * R_EARTH
    ky = math.pi / 180.0 * R_EARTH
    return kx, ky


def nearest_boundary(lat, lon, polys):
    """(distance_m, nearest_lat, nearest_lon, (segment dx, dy) in metres) from the point to the closest ring segment of any polygon, or None for no geometry."""
    if not polys:
        return None
    kx, ky = _project(lat, lon)
    best = None
    for rings in polys:
        for ring in rings:
            n = len(ring)
            if n < 2:
                continue
            px0 = (ring[0][0] - lon) * kx
            py0 = (ring[0][1] - lat) * ky
            for i in range(1, n):
                px1 = (ring[i][0] - lon) * kx
                py1 = (ring[i][1] - lat) * ky
                dx, dy = px1 - px0, py1 - py0
                L2 = dx * dx + dy * dy
                if L2 == 0.0:
                    t = 0.0
                else:
                    t = max(0.0, min(1.0, (-px0 * dx - py0 * dy) / L2))
                qx, qy = px0 + t * dx, py0 + t * dy
                d2 = qx * qx + qy * qy
                if best is None or d2 < best[0]:
                    best = (d2, qx, qy, dx, dy)
                px0, py0 = px1, py1
    d2, qx, qy, dx, dy = best
    return math.sqrt(d2), lat + qy / ky, lon + qx / kx, (dx, dy)


def distance_to_polygons_m(lat, lon, polys):
    """0.0 when inside, else metres to the nearest shoreline; None when there is no geometry."""
    if not polys:
        return None
    if point_in_polygons(lat, lon, polys):
        return 0.0
    return nearest_boundary(lat, lon, polys)[0]


def inland_point(lat, lon, polys, radii=(15.0, 30.0, 60.0, 120.0, 250.0, 500.0), clear_good=15.0, clear_min=6.0):
    """The point of the water nearest to (lat, lon) that is not on the shore, so rounding cannot put it back on the land.
    From the nearest shore point, probe 24 directions at each radius and keep, among probes inside the water, the one nearest to the original pin that is at
    least `clear_good` metres from every shore; if no probe clears that (a narrow arm), the nearest probe with at least `clear_min` metres.
    Returns (lat, lon, clearance_m) rounded to 5 decimals (about 1 m) and re-verified after rounding, or None."""
    nb = nearest_boundary(lat, lon, polys)
    if nb is None:
        return None
    _d, qlat, qlon, _seg = nb
    kx, ky = _project(qlat, qlon)
    good = fallback = None
    for r in radii:
        for k in range(24):
            a = 2 * math.pi * k / 24
            plat = round(qlat + (r * math.sin(a)) / ky, 5)
            plon = round(qlon + (r * math.cos(a)) / kx, 5)
            if not point_in_polygons(plat, plon, polys):
                continue
            clear = nearest_boundary(plat, plon, polys)[0]
            if clear < clear_min:
                continue
            dist = haversine_m(lat, lon, plat, plon)
            cand = (dist, plat, plon, clear)
            if clear >= clear_good:
                if good is None or dist < good[0]:
                    good = cand
            elif fallback is None or dist < fallback[0]:
                fallback = cand
        if good:
            break           # a probe at this radius already clears the shore; larger radii only move the point further from the pin
    best = good or fallback
    return None if best is None else (best[1], best[2], round(best[3]))


# ------------------------------------------------------------------ names (same token rule as research/lake-brain/geometry_audit.py)
_STOP = {"lake", "lakes", "reservoir", "res", "pond", "the", "of", "dam", "river", "impoundment", "bay", "flowage"}


def norm_name(s):
    s = (s or "").lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return {w for w in s.split() if w not in _STOP}


def name_match(a, b):
    A, B = norm_name(a), norm_name(b)
    if not A or not B:
        return 0.0
    return len(A & B) / max(1, min(len(A), len(B)))
