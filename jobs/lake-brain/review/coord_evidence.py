"""Evidence and recommendation logic for the coordinate review pack (pure functions, no I/O, no network).

PRE-REGISTERED RULES (docs/brains/LAKE_BRAIN_COORDINATE_REVIEW_PROTOCOL.md section 3; thresholds were fixed before the pack was built and are
not tuned on results):

  geometry class (pin against the canonical registry polygon):
      NO_GEOMETRY      the registry has no polygon for the lake
      IN_POLYGON       the pin is inside the polygon
      OFF_WATER_NEAR   outside, but within  allowed = max(3000 m, 3 x rounding tolerance, 600 m x sqrt(area km2))  (same rule as the registry pointFlag)
      OFF_WATER_FAR    outside by more than `allowed`  (identity risk: the pin or the lake is wrong)

  identity signals (positive):  name (a registry/NHD/USACE/OSM name matches the directory name, token overlap >= 0.5),
      area (NID or USACE pool area within 0.80 to 1.25 of the polygon area), dam (the lake's NID dam sits within 2 km of the polygon),
      binding (a candidate binding's gauge sits within 3 km of the polygon), osm (registry says OSM corroborates).
  contradictions (any one blocks PASS):  name differs (a known canonical name matches nothing and the registry says "name differs"),
      area outside 0.5 to 2.0 of every reference, NID dam more than 5 km from the polygon, binding gauge more than 5 km from the polygon,
      a competing waterbody (a different water within the 6 km scan that carries the lake's name, that the pin sits inside, or - for an off-water pin -
      a different named / 1 km2+ lake or directory lake that is NEARER to the pin than the canonical outline),
      polygon itself unreliable (registry geometry confidence LOW for a reason other than the point distance), binding that would change target.

  The scan of other waters near the pin (USGS NHD within 6 km, plus other Sector directory lakes) must have completed, otherwise FLAG.

  recommendation:
      NO_GEOMETRY      FLAG
      IN_POLYGON       PASS (keep) when there is no contradiction, else FLAG
      OFF_WATER_NEAR   PASS when no contradiction and enough positive signals (1 if the move is <= max(1000 m, tolerance), else 2) and
                       (the name signal or >= 3 signals); else FLAG
      OFF_WATER_FAR    PASS only when no contradiction, the pin is within 15 km of the water, the name signal, >= 3 signals and a dam or binding signal; else FLAG
  A PASS is never a decision: Michael accepts or keeps for every row. Identity ambiguity is always FLAG.
"""
import math

import coord_geo as G

NEAR_BASE_M = 3000.0
AREA_OK = (0.80, 1.25)
AREA_BAD = (0.5, 2.0)
DAM_OK_M = 2000.0
DAM_BAD_M = 5000.0
STATION_OK_M = 3000.0
STATION_BAD_M = 5000.0
NAME_OK = 0.5
FAR_MAX_PASS_M = 15000.0     # a pin more than 15 km from the water is more likely a different lake than a rounding / dam offset: never PASS
COMPETITOR_MIN_AREA = 0.05      # km2: a same-named water at least this big within the window competes
NEARER_UNNAMED_MIN_AREA = 1.0     # km2: an unnamed water this big that is nearer to the pin than the canonical outline competes
PIN_INSIDE_OTHER_MIN_AREA = 0.2  # km2: the pin sits inside a different water at least this big
SAME_WATER_M = 150.0            # a neighbour whose outline lies mostly (>= 40% of its vertices) inside or within this distance of the canonical outline is the same water
SAME_WATER_SHARE = 0.4


def coord_decimals(x):
    t = repr(float(x))
    return len(t.split(".")[1].rstrip("0")) if "." in t else 0


def point_tolerance_m(lat, lon):
    """Directory coordinates are rounded: a pin legitimately lands up to ~0.71 cell off the water (same rule as the geometry audit)."""
    dec = max(coord_decimals(lat), coord_decimals(lon), 1)
    return max(300.0, 0.71 * 111000.0 * 10 ** -dec)


def allowed_m(area_km2, tol_m):
    return max(NEAR_BASE_M, 3 * tol_m, 600.0 * math.sqrt(max(area_km2 or 0.0, 0.0)))


def _bbox_center(geom):
    polys = G.polygons_of(geom)
    xs = [p[0] for rings in polys for p in rings[0]] if polys else []
    ys = [p[1] for rings in polys for p in rings[0]] if polys else []
    if not xs:
        return None
    return round((min(ys) + max(ys)) / 2, 5), round((min(xs) + max(xs)) / 2, 5)


def _vertices_sample(polys, cap=80):
    pts = [p for rings in polys for p in rings[0]]
    step = max(1, len(pts) // cap)
    return pts[::step]


def same_water(polys, canonical_polys):
    """True when most of this outline lies on or against the canonical outline (the same water seen by another dataset, or an adjoining piece of it)."""
    pts = _vertices_sample(polys, 40)
    if not pts:
        return False
    hit = 0
    for p in pts:
        if G.point_in_polygons(p[1], p[0], canonical_polys) or G.nearest_boundary(p[1], p[0], canonical_polys)[0] <= SAME_WATER_M:
            hit += 1
    return hit / len(pts) >= SAME_WATER_SHARE


def nearby_alternatives(cur, canonical_polys, canonical_ids, nhd, lake_name, registry_alts=()):
    """Other waterbodies near the pin, nearest first: neighbour waters from the scan (HydroLAKES / NHD; outlines that coincide with or adjoin the canonical outline are the same water and are dropped) plus
    other Sector directory lakes whose outline is near the pin (`registry_alts`, already shaped like the output). An NHD piece fetched
    without a polygon keeps distanceM None (it is somewhere within the search radius)."""
    out = []
    for w in nhd or []:
        if str(w["id"]) in canonical_ids:
            continue
        polys = G.polygons_of(w.get("geometry"))
        nm = G.name_match(lake_name, w.get("name"))
        if polys:
            if canonical_polys and same_water(polys, canonical_polys):
                continue
            d = G.distance_to_polygons_m(cur[0], cur[1], polys)
            inside = d == 0.0
        else:
            d, inside = None, bool(w.get("pinInside"))
            if inside:
                d = 0.0
        out.append(dict(id=str(w["id"]), name=w.get("name"), gnisId=w.get("gnisId"), areaKm2=w.get("areaKm2"), distanceM=None if d is None else round(d),
                        nameMatch=round(nm, 2), pinInside=inside, center=_bbox_center(w.get("geometry")) if polys else None, source=w.get("source") or "USGS NHD HR waterbody"))
    out.extend(dict(a) for a in registry_alts)
    out.sort(key=lambda a: (a["distanceM"] is None, a["distanceM"] if a["distanceM"] is not None else 0, -(a["areaKm2"] or 0)))
    return out


def competitor_of(alts, canonical_distance_m=None):
    """First alternative that competes for the identity of the pin: a same-name water nearby, a water the pin sits inside, or (for a pin that is off the
    canonical water) a different substantial lake that is nearer to the pin than the canonical outline is. None otherwise."""
    for a in alts:
        area = a["areaKm2"] or 0
        if a["nameMatch"] >= NAME_OK and area >= COMPETITOR_MIN_AREA:
            return a, "a different water with the lake's name"
        if a["pinInside"] and (area >= PIN_INSIDE_OTHER_MIN_AREA or a["source"].startswith("Sector")):
            return a, "the pin sits inside a different directory lake" if a["source"].startswith("Sector") else "the pin sits inside a different water"
    if canonical_distance_m:
        for a in alts:
            if a["distanceM"] is None or a["distanceM"] >= canonical_distance_m:
                continue
            area = a["areaKm2"] or 0
            if a["source"].startswith("Sector") or (a.get("name") and area >= COMPETITOR_MIN_AREA) or area >= NEARER_UNNAMED_MIN_AREA:
                return a, f"a different lake is nearer to the pin ({a['distanceM']} m) than this lake's outline ({canonical_distance_m} m)"
    return None, None


def name_evidence(lake, research):
    """-> (best match 0..1 or None, list of (source, name, match), canonical NHD name or None)."""
    dname = lake.get("name") or ""
    names = []
    for a in lake.get("aliases") or []:
        names.append(("registry alias", a))
    if research:
        for src, k in (("NHD name", "nhd_top_name"), ("USACE name", "usace_name"), ("OSM name", "osm_best_name"), ("HydroLAKES name", "hl_top_name")):
            if research.get(k):
                names.append((src, research[k]))
    scored = [(s, n, round(G.name_match(dname, n), 2)) for s, n in names]
    best = max((m for _, _, m in scored), default=None)
    canon = (research or {}).get("nhd_top_name") or None
    return best, scored, canon


def build_evidence(ctx):
    """ctx: lake (registry entry), geom (GeoJSON geometry or None), research (flags row dict or None), directory (dict or None), nhd (list or None),
    nid (dict: linked record or None; near: list), bindings (list of dicts). Returns the evidence dict for one lake."""
    lake = ctx["lake"]
    loc = lake["location"]
    cur = (float(loc["lat"]), float(loc["lon"]))
    polys = G.polygons_of(ctx.get("geom"))
    tol = point_tolerance_m(*cur)
    area = lake.get("areaKm2")
    allowed = allowed_m(area, tol)
    ev = dict(lakeId=lake["lakeId"], name=lake.get("name"), state=lake.get("state"), current=dict(lat=cur[0], lon=cur[1]), toleranceM=round(tol),
              allowedM=round(allowed), registryFlag=lake.get("pointFlag"), registryDistanceM=loc.get("distanceToShorelineM"),
              memberIds=lake.get("memberIds") or [lake["lakeId"]], geometryLevel=(lake.get("geometryConfidence") or {}).get("level"),
              geometryReasons=list((lake.get("geometryConfidence") or {}).get("reasons") or []), areaKm2=area,
              nhdIds=(lake.get("externalIds") or {}).get("nhd") or [])
    rs = ctx.get("research")
    ev["researchFlag"] = (rs or {}).get("point_flag") or None
    # --- geometry class
    if not polys:
        ev.update(geometryClass="NO_GEOMETRY", inPolygon=None, distanceM=None, nearestWater=None)
    else:
        inside = G.point_in_polygons(cur[0], cur[1], polys)
        if inside:
            ev.update(geometryClass="IN_POLYGON", inPolygon=True, distanceM=0, nearestWater=None)
        else:
            d, qlat, qlon, _ = G.nearest_boundary(cur[0], cur[1], polys)
            ev.update(geometryClass="OFF_WATER_NEAR" if d <= allowed else "OFF_WATER_FAR", inPolygon=False, distanceM=round(d),
                      nearestWater=dict(lat=round(qlat, 5), lon=round(qlon, 5)))
    # --- alternatives
    alts = nearby_alternatives(cur, polys, {str(i) for i in ev["nhdIds"]} | {str(i) for i in (lake.get("geometry") or {}).get("sourceIds", [])},
                               ctx.get("nhd"), lake.get("name"), ctx.get("registryAlts") or ())
    ev["scanAvailable"] = ctx.get("nhd") is not None
    ev["alternatives"] = alts[:4]
    comp, comp_why = competitor_of(alts, ev.get("distanceM") if ev.get("geometryClass") in ("OFF_WATER_NEAR", "OFF_WATER_FAR") else None)
    ev["competitor"] = None if comp is None else dict(comp, why=comp_why)
    # --- names
    best, scored, canon = name_evidence(lake, rs)
    ev["nameBest"] = best
    ev["nameSources"] = [dict(source=s, name=n, match=m) for s, n, m in scored]
    ev["canonicalName"] = canon
    differs = any("name differs" in r.lower() for r in ev["geometryReasons"])
    ev["nameSignal"] = (best is not None and best >= NAME_OK)
    ev["nameContradiction"] = (not ev["nameSignal"]) and (differs or (canon is not None and best is not None and best < NAME_OK))
    # --- area
    ratios = [(p.get("source"), p.get("ratioToShoreline")) for p in (lake.get("poolExtents") or []) if p.get("ratioToShoreline") is not None]
    ev["areaRatios"] = [dict(source=s, ratio=r) for s, r in ratios]
    ev["areaSignal"] = any(AREA_OK[0] <= r <= AREA_OK[1] for _, r in ratios)
    ev["areaContradiction"] = bool(ratios) and (not ev["areaSignal"]) and all(r < AREA_BAD[0] or r > AREA_BAD[1] for _, r in ratios)
    # --- NID dam
    nid = ctx.get("nid") or {}
    link = nid.get("linked")
    dam = None
    if link and polys:
        dd = G.distance_to_polygons_m(link["lat"], link["lon"], polys)
        dam = dict(id=link["id"], name=link.get("name"), lat=link["lat"], lon=link["lon"], toWaterM=round(dd),
                   toPinM=round(G.haversine_m(cur[0], cur[1], link["lat"], link["lon"])), surfaceKm2=link.get("surfaceKm2"))
    elif link:
        dam = dict(id=link["id"], name=link.get("name"), lat=link["lat"], lon=link["lon"], toWaterM=None,
                   toPinM=round(G.haversine_m(cur[0], cur[1], link["lat"], link["lon"])), surfaceKm2=link.get("surfaceKm2"))
    ev["nidDam"] = dam
    ev["nidNearPin"] = [dict(n, toPinM=round(G.haversine_m(cur[0], cur[1], n["lat"], n["lon"]))) for n in nid.get("near", [])][:3]
    ev["damSignal"] = bool(dam and dam["toWaterM"] is not None and dam["toWaterM"] <= DAM_OK_M)
    ev["damContradiction"] = bool(dam and dam["toWaterM"] is not None and dam["toWaterM"] > DAM_BAD_M)
    ev["osmSignal"] = bool(((lake.get("geometryConfidence") or {}).get("evidence") or {}).get("osmCorroborated"))
    ev["operator"] = (ctx.get("directory") or {}).get("operatorName")
    ev["usaceName"] = (rs or {}).get("usace_name") or None
    ev["gnisId"] = (lake.get("externalIds") or {}).get("gnisId")
    if ev["gnisId"] is None and ctx.get("nhd") and ev["nhdIds"]:
        for w in ctx["nhd"]:
            if str(w["id"]) in {str(i) for i in ev["nhdIds"]} and w.get("gnisId"):
                ev["gnisId"] = str(w["gnisId"])
                if not ev["canonicalName"]:
                    ev["canonicalName"] = w.get("name")
    # --- proposal
    prop = None
    if ev["geometryClass"] == "IN_POLYGON":
        prop = dict(lat=cur[0], lon=cur[1], basis="keep: the pin is already inside the canonical water", moveM=0)
    elif ev["geometryClass"] == "OFF_WATER_NEAR":
        ip = G.inland_point(cur[0], cur[1], polys)
        if ip:
            prop = dict(lat=ip[0], lon=ip[1], basis=f"nearest point of the canonical water (at least {ip[2]} m from the shore)", moveM=round(G.haversine_m(cur[0], cur[1], ip[0], ip[1])))
    elif ev["geometryClass"] == "OFF_WATER_FAR":
        lp = lake.get("labelPoint")
        if lp and G.point_in_polygons(lp[1], lp[0], polys):
            prop = dict(lat=round(lp[1], 5), lon=round(lp[0], 5), basis="label point of the canonical water (the pin is too far from it to nudge)",
                        moveM=round(G.haversine_m(cur[0], cur[1], lp[1], lp[0])))
        else:
            ip = G.inland_point(cur[0], cur[1], polys)
            if ip:
                prop = dict(lat=ip[0], lon=ip[1], basis=f"nearest point of the canonical water (at least {ip[2]} m from the shore)", moveM=round(G.haversine_m(cur[0], cur[1], ip[0], ip[1])))
    if prop and polys and not G.point_in_polygons(prop["lat"], prop["lon"], polys):
        prop = None                       # never propose a point that is not on the canonical water
    ev["proposed"] = prop
    lp = lake.get("labelPoint")
    ev["labelPoint"] = None if not lp else dict(lat=round(lp[1], 5), lon=round(lp[0], 5), fromPinM=round(G.haversine_m(cur[0], cur[1], lp[1], lp[0])))
    ev["alsoNearest"] = None
    if ev["geometryClass"] == "OFF_WATER_FAR" and polys:
        ip = G.inland_point(cur[0], cur[1], polys)
        if ip:
            ev["alsoNearest"] = dict(lat=ip[0], lon=ip[1], moveM=round(G.haversine_m(cur[0], cur[1], ip[0], ip[1])))
    # --- bindings
    ev["bindings"] = [binding_implication(b, cur, prop, polys, ev["geometryClass"]) for b in ctx.get("bindings") or []]
    return ev


def binding_implication(b, cur, prop, polys, geometry_class):
    """How a pin correction touches one candidate binding. Station coordinates come from the research candidate files; a binding without
    coordinates is UNVERIFIED (never assumed fine)."""
    out = dict(provider=b.get("provider"), station=b.get("station"), stationName=b.get("stationName"), status=b.get("status"),
               capability=b.get("capability"), held=bool(b.get("held")), distFromPinM=b.get("distM"), stationLat=b.get("lat"), stationLon=b.get("lon"))
    if b.get("lat") is None or b.get("lon") is None:
        out.update(code="UNVERIFIED", changes=None, text="station coordinates not available, so the effect of moving the pin cannot be tested")
        return out
    slat, slon = float(b["lat"]), float(b["lon"])
    to_pin = G.haversine_m(slat, slon, cur[0], cur[1])
    to_poly = G.distance_to_polygons_m(slat, slon, polys) if polys else None
    to_prop = G.haversine_m(slat, slon, prop["lat"], prop["lon"]) if prop else None
    out.update(toPinM=round(to_pin), toWaterM=None if to_poly is None else round(to_poly), toProposedM=None if to_prop is None else round(to_prop))
    if to_poly is None:
        out.update(code="UNVERIFIED", changes=None, text="no canonical polygon, so the gauge cannot be placed on the water")
        return out
    before = to_pin <= STATION_OK_M
    after = (to_poly <= STATION_OK_M) or (to_prop is not None and to_prop <= STATION_OK_M)
    on_water = to_poly <= STATION_OK_M
    if on_water:
        changes = (before != after)
        out.update(code="UNCHANGED_ON_WATER", changes=False,
                   text=f"the gauge is {to_poly / 1000:.1f} km from the canonical water; the correction does not change which lake the binding points at")
    elif to_poly > STATION_BAD_M:
        out.update(code="AT_RISK", changes=(before != after),
                   text=f"the gauge is {to_poly / 1000:.1f} km from the canonical water; it may belong to a different lake (or the polygon is wrong): review the binding too")
    else:
        out.update(code="AMBIGUOUS", changes=(before != after),
                   text=f"the gauge is {to_poly / 1000:.1f} km from the canonical water (between 3 and 5 km): cannot tell whether it is this lake's gauge")
    if out["changes"]:
        out["text"] += "; the correction CHANGES which lake the binding sits near"
    return out


def recommend(ev):
    """-> (PASS|FLAG, one-sentence why, list of reasons). Deterministic, no side effects."""
    cls = ev["geometryClass"]
    if cls == "NO_GEOMETRY":
        return "FLAG", "The registry has no canonical polygon for this lake, so the pin cannot be tested or corrected automatically.", ["no geometry"]
    if ev["proposed"] is None:
        return "FLAG", "No safe corrected point could be placed inside the canonical water.", ["no proposal"]
    against, pos = [], []
    if ev["nameContradiction"]:
        against.append("the canonical water's name does not match the directory name")
    if ev["areaContradiction"]:
        against.append("the NID/USACE pool area disagrees with the polygon by more than 2x")
    if ev["damContradiction"]:
        against.append(f"the lake's NID dam is {ev['nidDam']['toWaterM'] / 1000:.1f} km from the polygon")
    if ev["competitor"]:
        c = ev["competitor"]
        against.append(f"competing water: {c.get('name') or 'unnamed water'} ({c['distanceM']} m from the pin; {c['why']})")
    non_point_low = [r for r in ev["geometryReasons"] if not r.lower().startswith("identity risk")]
    if ev["geometryLevel"] == "LOW" and non_point_low:
        against.append("the polygon itself is low confidence (" + non_point_low[0] + ")")
    for b in ev["bindings"]:
        if b["code"] == "AT_RISK":
            against.append(f"binding gauge {b['provider']} {b['station']} is {b['toWaterM'] / 1000:.1f} km from the canonical water")
        elif b.get("changes"):
            against.append(f"the correction changes which lake binding {b['provider']} {b['station']} sits near")
    if ev["geometryLevel"] == "MISSING":
        against.append("registry geometry confidence is MISSING")
    if not ev["scanAvailable"]:
        against.append("the national water map could not be scanned for other lakes near the pin")
    if ev["nameSignal"]:
        pos.append("name")
    if ev["areaSignal"]:
        pos.append("area")
    if ev["damSignal"]:
        pos.append("dam")
    if ev["osmSignal"]:
        pos.append("osm")
    if any(b["code"] == "UNCHANGED_ON_WATER" for b in ev["bindings"]):
        pos.append("binding")
    n = len(pos)
    ev["positiveSignals"] = pos
    ev["contradictions"] = against
    sigtxt = ", ".join(pos) if pos else "none"
    if against:
        return "FLAG", "Needs a human look: " + against[0] + (f" (+{len(against) - 1} more concern{'s' if len(against) > 2 else ''})" if len(against) > 1 else "") + ".", against
    if cls == "IN_POLYGON":
        return "PASS", "The pin is already inside the canonical water and nothing contradicts the identity; keep it.", []
    move = ev["proposed"]["moveM"]
    if cls == "OFF_WATER_NEAR":
        need = 1 if move <= max(1000, ev["toleranceM"]) else 2
        if n >= need and (ev["nameSignal"] or n >= 3):
            return "PASS", f"The pin is {ev['distanceM']} m off the canonical water and the identity is corroborated by {sigtxt}; the proposed point is {move} m away on the same water.", []
        return "FLAG", f"The pin is {ev['distanceM']} m off the canonical water but only {n} independent identity signal(s) ({sigtxt}); not enough to be sure it is the same lake.", ["weak identity evidence"]
    # OFF_WATER_FAR
    if ev["distanceM"] > FAR_MAX_PASS_M:
        return "FLAG", f"The pin is {ev['distanceM'] / 1000:.0f} km from the canonical water, too far to call it a simple offset; it may be a different lake entirely.", ["pin more than 15 km away"]
    if ev["nameSignal"] and n >= 3 and (ev["damSignal"] or "binding" in pos):
        return "PASS", f"The pin is {ev['distanceM'] / 1000:.1f} km from the canonical water, but name, dam/gauge and {n} signals agree on the polygon, so the pin looks like the error.", []
    return "FLAG", f"The pin is {ev['distanceM'] / 1000:.1f} km from the canonical water (identity risk) and the evidence ({sigtxt}) is not strong enough to say the pin rather than the lake is wrong.", ["identity ambiguity"]
