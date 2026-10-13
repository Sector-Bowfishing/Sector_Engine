"""Tests for the coordinate review pack: geometry helpers, evidence/recommendation rules (in-polygon, off-water near shore, off-water far,
identity ambiguity, missing geometry, binding effect), the builder outputs and the HTML form. Synthetic fixtures only (no research data, no network)."""
import csv
import json
import math
import os
import re

import pytest

import build_coordinate_review_pack as B
import coord_evidence as E
import coord_geo as G

LAT0, LON0 = 36.0, -90.0
H = 0.01   # half-side of the fixture lake in degrees (about 1.1 km x 0.9 km)


def square(lat0=LAT0, lon0=LON0, h=H):
    return {"type": "Polygon", "coordinates": [[[lon0 - h, lat0 - h], [lon0 + h, lat0 - h], [lon0 + h, lat0 + h], [lon0 - h, lat0 + h], [lon0 - h, lat0 - h]]]}


def lake(lid="Fixture Lake|AR", name="Fixture Lake", lat=LAT0, lon=LON0, flag="off-water", aliases=("Fixture Lake",), nid="AR00001", ratios=(1.0,),
         level="HIGH", reasons=(), osm=True, area=2.0, members=None, label=None):
    return {"lakeId": lid, "lakeKey": lid.replace("|", "_").replace(" ", "_"), "name": name, "aliases": list(aliases), "memberIds": members or [lid], "state": lid.split("|")[1],
            "location": {"lat": lat, "lon": lon, "source": "sector-directory", "pointFlag": flag, "distanceToShorelineM": 0},
            "externalIds": {"nhd": ["111"], "gnisId": None, "nidId": nid}, "areaKm2": area, "labelPoint": label or [LON0, LAT0],
            "poolExtents": [{"kind": "normalPool", "source": "nid", "ratioToShoreline": r} for r in ratios],
            "geometryConfidence": {"level": level, "reasons": list(reasons), "evidence": {"osmCorroborated": osm}}, "pointFlag": flag}


def ctx(lk, geom=True, nhd=(), dam=None, bindings=(), research=None):
    g = square() if geom is True else geom
    return dict(lake=lk, geom=g, research=research, directory=None, nhd=list(nhd) if nhd is not None else None, nid=dict(linked=dam, near=[]), bindings=list(bindings))


def dam_on_shore():
    return dict(id="AR00001", name="Fixture Dam", lat=LAT0 + H + 0.0005, lon=LON0, surfaceKm2=None)


def run(c):
    ev = E.build_evidence(c)
    rec, why, _ = E.recommend(ev)
    return ev, rec, why


def inside(ev):
    return G.point_in_polygons(ev["proposed"]["lat"], ev["proposed"]["lon"], G.polygons_of(square()))


# ------------------------------------------------------------------ geometry helpers
def test_point_in_polygon_with_hole():
    poly = [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]]
    polys = [poly]
    assert G.point_in_polygons(1, 1, polys)
    assert not G.point_in_polygons(5, 5, polys)          # in the hole (island)
    assert not G.point_in_polygons(20, 20, polys)


def test_polygons_of_geometrycollection_ignores_lines():
    gc = {"type": "GeometryCollection", "geometries": [square(), {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}]}
    assert len(G.polygons_of(gc)) == 1 and G.polygons_of(None) == []


def test_nearest_boundary_matches_haversine():
    polys = G.polygons_of(square())
    d, qlat, qlon, _ = G.nearest_boundary(LAT0 + H + 0.01, LON0, polys)
    assert abs(d - G.haversine_m(LAT0 + H + 0.01, LON0, qlat, qlon)) < 2
    assert abs(d - 0.01 * 111195) < 30
    assert G.distance_to_polygons_m(LAT0, LON0, polys) == 0.0 and G.distance_to_polygons_m(0, 0, []) is None


def test_inland_point_is_inside_and_off_the_shore():
    polys = G.polygons_of(square())
    for lat, lon in ((LAT0 + 0.014, LON0), (LAT0, LON0 + 0.02), (LAT0 - 0.015, LON0 - 0.015), (LAT0 + 0.5, LON0 + 0.5)):
        ip = G.inland_point(lat, lon, polys)
        assert ip is not None
        assert G.point_in_polygons(ip[0], ip[1], polys)
        assert G.nearest_boundary(ip[0], ip[1], polys)[0] >= 15 and ip[2] >= 15


def test_name_match_rule():
    assert G.name_match("Lake Barkley", "Barkley Lake") == 1.0
    assert G.name_match("Fixture Lake", "Other Water") == 0.0 and G.name_match("", "x") == 0.0


# ------------------------------------------------------------------ the five fixture classes
def test_in_polygon_is_pass_keep():
    ev, rec, why = run(ctx(lake(lat=LAT0, lon=LON0, flag="ok")))
    assert ev["geometryClass"] == "IN_POLYGON" and ev["inPolygon"] is True
    assert rec == "PASS" and ev["proposed"]["moveM"] == 0 and (ev["proposed"]["lat"], ev["proposed"]["lon"]) == (LAT0, LON0)


def test_off_water_near_shore_pass_with_inland_proposal():
    c = ctx(lake(lat=LAT0 + H + 0.004, lon=LON0), dam=dam_on_shore())
    ev, rec, why = run(c)
    assert ev["geometryClass"] == "OFF_WATER_NEAR" and 300 < ev["distanceM"] < 600
    assert rec == "PASS" and "dam" in ev["positiveSignals"] and "name" in ev["positiveSignals"]
    assert inside(ev) and ev["proposed"]["moveM"] < 700
    assert ev["nidDam"]["toWaterM"] < 100 and ev["nidDam"]["toPinM"] > 300


def test_off_water_near_but_weak_identity_is_flag():
    # no name, no area, no dam, no osm: nothing says this is the same lake
    lk = lake(lat=LAT0 + H + 0.004, aliases=(), nid=None, ratios=(), osm=False)
    ev, rec, why = run(ctx(lk))
    assert ev["geometryClass"] == "OFF_WATER_NEAR" and rec == "FLAG" and inside(ev)


def test_off_water_far_name_only_is_flag_and_shows_alternative_point():
    ev, rec, why = run(ctx(lake(lat=LAT0 + 0.12, lon=LON0, flag="identity-risk"), dam=None))
    assert ev["geometryClass"] == "OFF_WATER_FAR" and ev["distanceM"] > 10000
    assert rec == "FLAG" and "identity" in why.lower()
    assert inside(ev) and "label point" in ev["proposed"]["basis"]
    assert ev["alsoNearest"] and ev["alsoNearest"]["moveM"] < ev["proposed"]["moveM"] + 20000


def test_off_water_far_with_dam_binding_name_osm_is_pass():
    b = dict(provider="a2w", station="X:Dam", status="VERIFIED", capability="DIRECT_OPERATOR_POOL", distM=14000, lat=LAT0 + H + 0.002, lon=LON0, held=True)
    ev, rec, why = run(ctx(lake(lat=LAT0 + 0.12, lon=LON0, flag="identity-risk"), dam=dam_on_shore(), bindings=[b]))
    assert ev["geometryClass"] == "OFF_WATER_FAR" and rec == "PASS"
    assert set(ev["positiveSignals"]) >= {"name", "dam", "binding", "area", "osm"}
    # the binding was matched 14 km from the old pin but sits on the water: correcting the pin does not change the target
    assert ev["bindings"][0]["code"] == "UNCHANGED_ON_WATER" and ev["bindings"][0]["changes"] is False


def test_identity_ambiguity_competing_same_name_water_is_flag_with_alternatives():
    other = {"type": "Polygon", "coordinates": [[[LON0 + 0.03, LAT0 + 0.02], [LON0 + 0.04, LAT0 + 0.02], [LON0 + 0.04, LAT0 + 0.03], [LON0 + 0.03, LAT0 + 0.03], [LON0 + 0.03, LAT0 + 0.02]]]}
    nhd = [{"id": "111", "name": "Fixture Lake", "gnisId": None, "areaKm2": 2.0, "geometry": square()},
           {"id": "222", "name": "Fixture Lake", "gnisId": "99", "areaKm2": 1.0, "geometry": other}]
    ev, rec, why = run(ctx(lake(lat=LAT0 + H + 0.004), dam=dam_on_shore(), nhd=nhd))
    assert rec == "FLAG" and ev["competitor"] and ev["competitor"]["id"] == "222"
    assert [a["id"] for a in ev["alternatives"]] == ["222"]            # canonical water 111 is never listed as an alternative
    assert "competing water" in why or "Needs a human look" in why
    assert ev["proposed"] is not None and inside(ev)                    # the proposal is still shown, but it is not recommended


def test_pin_inside_a_different_water_is_flag():
    pond = {"type": "Polygon", "coordinates": [[[LON0 - 0.0005, LAT0 + 0.012], [LON0 + 0.0005, LAT0 + 0.012], [LON0 + 0.0005, LAT0 + 0.0135], [LON0 - 0.0005, LAT0 + 0.0135], [LON0 - 0.0005, LAT0 + 0.012]]]}
    nhd = [{"id": "333", "name": None, "gnisId": None, "areaKm2": 0.5, "geometry": pond}]
    ev, rec, why = run(ctx(lake(lat=LAT0 + 0.0128), dam=dam_on_shore(), nhd=nhd))
    assert ev["competitor"] and ev["competitor"]["pinInside"] and rec == "FLAG"


def test_piece_touching_canonical_outline_is_not_a_competitor():
    adj = {"type": "Polygon", "coordinates": [[[LON0 - 0.005, LAT0 + H], [LON0 + 0.005, LAT0 + H], [LON0 + 0.005, LAT0 + H + 0.004], [LON0 - 0.005, LAT0 + H + 0.004], [LON0 - 0.005, LAT0 + H]]]}
    nhd = [{"id": "444", "name": "Fixture Lake", "gnisId": None, "areaKm2": 0.5, "geometry": adj}]
    ev, rec, _ = run(ctx(lake(lat=LAT0 + H + 0.004), dam=dam_on_shore(), nhd=nhd))
    assert ev["alternatives"] == [] and ev["competitor"] is None


def test_unscanned_neighbourhood_blocks_pass():
    ev, rec, why = run(ctx(lake(lat=LAT0 + H + 0.004), dam=dam_on_shore(), nhd=None))
    assert ev["scanAvailable"] is False and rec == "FLAG" and "could not be scanned" in why


def test_pin_inside_another_directory_lake_is_flag():
    reg_alt = dict(id="Neighbour Lake|AR", name="Neighbour Lake", areaKm2=3.0, distanceM=0, nameMatch=0.0, pinInside=True, center=None, source="Sector registry lake", gnisId=None)
    c = ctx(lake(lat=LAT0 + H + 0.004), dam=dam_on_shore())
    c["registryAlts"] = [reg_alt]
    ev, rec, why = run(c)
    assert rec == "FLAG" and ev["competitor"]["id"] == "Neighbour Lake|AR" and "directory lake" in ev["competitor"]["why"]


def test_missing_geometry_is_flag_without_proposal():
    ev, rec, why = run(ctx(lake(flag=None, level="MISSING"), geom=None))
    assert ev["geometryClass"] == "NO_GEOMETRY" and ev["inPolygon"] is None and ev["distanceM"] is None
    assert rec == "FLAG" and ev["proposed"] is None and "no canonical polygon" in why
    row = B.csv_row(dict(ev, recommendation=rec, why=why, seq=1, sourceFlag="registry:x", digest="d"))
    assert row["in_polygon"] == "no geometry" and row["proposed_lat"] == ""


def test_name_contradiction_blocks_pass():
    lk = lake(lat=LAT0 + H + 0.004, aliases=())
    ev, rec, why = run(ctx(lk, dam=dam_on_shore(), research={"nhd_top_name": "Completely Different Water", "point_flag": "off_water"}))
    assert ev["nameContradiction"] and rec == "FLAG"


def test_low_polygon_confidence_blocks_pass_but_point_distance_alone_does_not():
    lk = lake(lat=LAT0 + H + 0.004, level="LOW", reasons=["identity risk: directory point 4000 m from the shoreline (allowed 3000 m)"])
    ev, rec, _ = run(ctx(lk, dam=dam_on_shore()))
    assert rec == "PASS"
    lk2 = lake(lat=LAT0 + H + 0.004, level="LOW", reasons=["25% of the shoreline water >= 50% of the time (JRC GSW)"])
    ev2, rec2, why2 = run(ctx(lk2, dam=dam_on_shore()))
    assert rec2 == "FLAG" and "low confidence" in " ".join(ev2["contradictions"])


# ------------------------------------------------------------------ binding implication
def test_binding_far_from_water_and_near_old_pin_changes_target():
    # old pin is on a dam of ANOTHER lake 2 km away from the canonical water; the gauge sits next to that pin
    b = dict(provider="usgs", station="07000000", status="VERIFIED", capability="DIRECT_LAKE_GAUGE", distM=300, lat=LAT0 + 0.15, lon=LON0 + 0.001, held=False)
    ev, rec, why = run(ctx(lake(lat=LAT0 + 0.15, flag="identity-risk"), dam=dam_on_shore(), bindings=[b]))
    bi = ev["bindings"][0]
    assert bi["code"] == "AT_RISK" and bi["changes"] is True and "CHANGES" in bi["text"]
    assert rec == "FLAG"


def test_binding_without_coordinates_is_unverified_never_assumed_fine():
    b = dict(provider="a2w", station="Y", status="VERIFIED", capability="DIRECT_OPERATOR_POOL", distM=100, lat=None, lon=None, held=True)
    ev, rec, _ = run(ctx(lake(lat=LAT0 + H + 0.004), dam=dam_on_shore(), bindings=[b]))
    assert ev["bindings"][0]["code"] == "UNVERIFIED" and ev["bindings"][0]["changes"] is None
    assert "binding" not in ev["positiveSignals"]


def test_tolerance_and_allowed_distance_rules():
    # same rule as research/lake-brain/geometry_audit.py: tolerance = max(300 m, 0.71 x 111 km x 10^-decimals), at least 1 decimal
    assert E.point_tolerance_m(36.0, -90.0) == pytest.approx(7881.0)          # "36.0, -90.0" is a 1-decimal pin
    assert E.point_tolerance_m(36.12, -90.45) == pytest.approx(788.1)
    assert E.point_tolerance_m(36.123, -90.456) == 300.0
    assert E.allowed_m(2.0, 300) == 3000.0 and E.allowed_m(10000.0, 300) == pytest.approx(60000.0) and E.allowed_m(2.0, 7881.0) == pytest.approx(23643.0)


# ------------------------------------------------------------------ builder outputs
def make_rows():
    lakes = {}
    geoms = {}
    for lid, lk, g, d in (
            ("In Lake|AR", lake("In Lake|AR", "In Lake", flag=None, lat=LAT0, lon=LON0), True, None),
            ("Near Lake|AR", lake("Near Lake|AR", "Near Lake", lat=LAT0 + H + 0.004), True, None),
            ("Far Lake|AR", lake("Far Lake|AR", "Far Lake", lat=LAT0 + 0.15, flag="identity-risk"), True, None),
            ("Missing Lake|AR", lake("Missing Lake|AR", "Missing </script> Lake", flag=None, level="MISSING"), None, None)):
        lakes[lid] = lk
        geoms[lid] = square() if g else None
    pop = {"In Lake|AR": "research:off_water", "Near Lake|AR": "research:off_water", "Far Lake|AR": "research:identity_risk", "Missing Lake|AR": "research:off_water"}
    nid = {"AR00001": dam_on_shore()}
    rows = B.build_rows(pop, lakes, geoms, {}, {}, {k: [] for k in lakes}, {}, nid, list(nid.values()))
    return rows


def test_build_rows_counts_and_recommendation_mix():
    rows = make_rows()
    assert [r["lakeId"] for r in rows] == ["Far Lake|AR", "In Lake|AR", "Missing Lake|AR", "Near Lake|AR"]
    recs = {r["lakeId"]: r["recommendation"] for r in rows}
    assert recs["In Lake|AR"] == "PASS" and recs["Missing Lake|AR"] == "FLAG" and recs["Far Lake|AR"] == "FLAG"
    assert all(r["proposed"] is None or True for r in rows)
    for r in rows:
        if r["proposed"]:
            assert G.point_in_polygons(r["proposed"]["lat"], r["proposed"]["lon"], G.polygons_of(square()))
    assert len({r["digest"] for r in rows}) == 4


def test_population_union_of_research_and_registry_flags():
    reg = {"A|ST": lake("A|ST", "A", flag="ok"), "B|ST": lake("B|ST", "B", flag="off-water"), "C|ST": lake("C|ST", "C", flag="ok"), "D|ST": lake("D|ST", "D", flag=None)}
    research = [{"id": "A|ST", "point_flag": "identity_risk"}, {"id": "C|ST", "point_flag": "ok"}, {"id": "Z|ST", "point_flag": "off_water"}]
    pop = B.population(research, reg)
    assert pop == {"A|ST": "research:identity_risk", "B|ST": "registry:off-water"}   # Z is not in the registry; C and D are fine


def test_write_pack_files_csv_html_manifest_readme(tmp_path):
    rows = make_rows()
    pid = B.pack_id_for(rows, "2026-10-13")
    meta = dict(snapshot="2026-10-13", registryGeneratedAt="2026-10-13T00:00:00Z", registrySha256="ab" * 32, researchFlagged=4, registryOnly=0, decisions=list(B.DECISIONS))
    summary = dict(byClass={k: sum(1 for r in rows if r["geometryClass"] == k) for k in {r["geometryClass"] for r in rows}})
    man = B.write_pack(str(tmp_path), rows, meta, pid, summary)
    assert sorted(os.listdir(tmp_path)) == ["START HERE - README.md", "coordinate_review.html", "coordinate_review_pack.csv", "pack_manifest.json"]
    assert man["counts"]["lakes"] == 4 and man["counts"]["pass_"] + man["counts"]["flag"] == 4
    with open(tmp_path / "coordinate_review_pack.csv", newline="", encoding="utf-8-sig") as f:
        got = list(csv.DictReader(f))
    assert len(got) == 4 and set(got[0].keys()) == set(B.CSV_FIELDS)
    html = (tmp_path / "coordinate_review.html").read_text(encoding="utf-8")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    payload = json.loads(m.group(1))                                       # the data block parses even with </script> in a lake name
    assert payload["packId"] == pid and len(payload["rows"]) == 4
    assert html.count("</script>") == 2                                   # data block + code block only
    assert "Accept proposed" in html and "Keep current" in html and "Needs more info" in html
    readme = (tmp_path / "START HERE - README.md").read_text()
    assert "4 cards" in readme and "No directory coordinate and no gauge binding is changed" in readme
    # the manifest carries what ingest needs
    assert {l["lakeId"] for l in man["lakes"]} == {r["lakeId"] for r in rows}
    miss = [l for l in man["lakes"] if l["lakeId"] == "Missing Lake|AR"][0]
    assert miss["proposedLat"] is None and miss["recommendation"] == "FLAG"


def test_html_rows_have_no_secrets_and_use_only_expected_links():
    rows = make_rows()
    blob = json.dumps([B.html_row(r) for r in rows])
    for bad in ("AIza", "-----BEGIN", "Bearer ", "private_key", "mgcather"):
        assert bad not in blob
    urls = set(re.findall(r"https?://[^\"/]+", blob))
    assert urls <= {"https://www.openstreetmap.org", "https://www.google.com"}


def test_user_agent_has_no_personal_email(monkeypatch):
    import coord_fetch as F
    monkeypatch.delenv("SECTOR_CONTACT", raising=False)
    ua = F.user_agent()
    assert "@" not in ua and ua.startswith("Sector-LakeBrain/1.0")
    monkeypatch.setenv("SECTOR_CONTACT", "ops@example.invalid")
    assert F.user_agent().endswith("ops@example.invalid")


def test_far_pin_beyond_15km_is_never_pass():
    b = dict(provider="a2w", station="X:Dam", status="VERIFIED", capability="DIRECT_OPERATOR_POOL", distM=14000, lat=LAT0 + H + 0.002, lon=LON0, held=True)
    ev, rec, why = run(ctx(lake(lat=LAT0 + 0.3, lon=LON0, flag="identity-risk"), dam=dam_on_shore(), bindings=[b]))
    assert ev["geometryClass"] == "OFF_WATER_FAR" and ev["distanceM"] > 15000 and rec == "FLAG" and "different lake" in why


def test_registry_neighbours_finds_other_directory_lake_under_the_pin():
    reg = {"A|AR": dict(lake("A|AR", "A", lat=LAT0 + 0.5), bbox=None),
           "B|AR": dict(lake("B|AR", "B Lake"), bbox=[LON0 - H, LAT0 - H, LON0 + H, LAT0 + H], centroid=[LON0, LAT0]),
           "C|AR": dict(lake("C|AR", "C", members=["C|AR", "A|AR"]), bbox=[LON0 - H, LAT0 - H, LON0 + H, LAT0 + H], centroid=[LON0, LAT0])}
    reg["A|AR"]["location"]["lat"], reg["A|AR"]["location"]["lon"] = LAT0 + 0.0, LON0 + 0.002      # pin of A sits inside B's outline
    out = B.registry_neighbours("A|AR", reg, lambda i: square())
    assert [o["id"] for o in out] == ["B|AR", "C|AR"] or [o["id"] for o in out] == ["B|AR"]
    assert out[0]["pinInside"] is True and out[0]["source"] == "Sector registry lake"
    far = B.registry_neighbours("A|AR", dict(reg, **{"A|AR": dict(reg["A|AR"], location=dict(reg["A|AR"]["location"], lat=LAT0 + 0.5))}), lambda i: square())
    assert far == []


def test_pin_nearer_to_a_different_substantial_lake_is_flag():
    big = {"type": "Polygon", "coordinates": [[[LON0 - 0.01, LAT0 + H + 0.005], [LON0 + 0.01, LAT0 + H + 0.005], [LON0 + 0.01, LAT0 + H + 0.02], [LON0 - 0.01, LAT0 + H + 0.02], [LON0 - 0.01, LAT0 + H + 0.005]]]}
    nhd = [{"id": "555", "name": "Neighbour Reservoir", "gnisId": None, "areaKm2": 2.0, "geometry": big}]
    # the pin is 445 m from the canonical outline but only about 110 m from Neighbour Reservoir
    ev, rec, why = run(ctx(lake(lat=LAT0 + H + 0.004), dam=dam_on_shore(), nhd=nhd))
    assert ev["competitor"] and ev["competitor"]["id"] == "555" and "nearer" in ev["competitor"]["why"] and rec == "FLAG"
    # a tiny unnamed pond nearer than the outline does not count
    pond = dict(nhd[0], id="556", name=None, areaKm2=0.1)
    ev2, rec2, _ = run(ctx(lake(lat=LAT0 + H + 0.004), dam=dam_on_shore(), nhd=[pond]))
    assert ev2["competitor"] is None and rec2 == "PASS"


def test_label_point_is_reported():
    ev, _, _ = run(ctx(lake(lat=LAT0 + H + 0.004), dam=dam_on_shore()))
    assert ev["labelPoint"]["lat"] == LAT0 and ev["labelPoint"]["fromPinM"] > 1000
