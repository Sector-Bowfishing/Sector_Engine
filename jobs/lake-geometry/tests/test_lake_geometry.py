"""Tests for the Lake Registry geometry builder (jobs/lake-geometry): repair, lakeKey parity, determinism, index schema."""
import gzip
import importlib.util
import json
import math
import os

import pytest
import shapely
from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon, box

import build_geometry as bg
import lake_geometry as lg

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
IDS = json.load(open(os.path.join(HERE, "directory_ids_621.json")))["ids"]


# ------------------------------------------------------------------ helpers


def lake_shape(lon0=-86.0, lat0=34.5, w_km=12.0, h_km=3.0, n=400, islands=()):
    """A wiggly lake outline (degrees) with optional island holes given as (dx_km, dy_km, r_m)."""
    kx = 111.32 * math.cos(math.radians(lat0))
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n
        r = 1 + 0.06 * math.sin(7 * a) + 0.03 * math.sin(23 * a)
        ring.append((lon0 + (w_km / 2) * r * math.cos(a) / kx, lat0 + (h_km / 2) * r * math.sin(a) / 110.57))
    holes = []
    for dx, dy, rm in islands:
        c = (lon0 + dx / kx, lat0 + dy / 110.57)
        holes.append([(c[0] + rm * math.cos(2 * math.pi * k / 16) / (kx * 1000), c[1] + rm * math.sin(2 * math.pi * k / 16) / (110.57 * 1000))
                      for k in range(16)])
    return Polygon(ring, holes)


def metric(g, lon0=-86.0, lat0=34.5):
    return lg.project(g, lg.transformers(lon0, lat0)[0])


# ------------------------------------------------------------------ lakeKey parity


def _brain_keys():
    p = os.path.join(REPO, "jobs", "brain_platform", "sector_brain_platform", "keys.py")
    spec = importlib.util.spec_from_file_location("brain_keys", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_lake_key_examples():
    assert lg.lake_key("Guntersville|AL") == "Guntersville_AL"
    assert lg.lake_key("Pickwick Lake|TN") == "Pickwick_Lake_TN"
    assert lg.lake_key("Lake Hartwell|SC") == "Lake_Hartwell_SC"
    assert lg.lake_key("Grand Lake o' the Cherokees|OK") == "Grand_Lake_o_the_Cherokees_OK"   # a run of non-alphanumerics is ONE underscore
    assert lg.lake_key("Flat River Res. (Johnson's Pond)|RI") == "Flat_River_Res_Johnson_s_Pond_RI"


def test_lake_key_parity_with_brain_platform_for_all_621_directory_ids():
    assert len(IDS) == 621 and len(set(IDS)) == 621
    keys = _brain_keys()
    mine = {i: lg.lake_key(i) for i in IDS}
    assert mine == {i: keys.lake_key(i) for i in IDS}
    assert len(set(mine.values())) == 621                       # no slug collision
    assert keys.lake_keys(IDS) == mine                          # the platform's own collision check agrees
    for k in mine.values():                                     # safe as a GCS path segment and an RTDB key
        assert k and all(c.isalnum() or c == "_" for c in k) and k.isascii()


# ------------------------------------------------------------------ repair


def test_geometry_collection_with_linestring_becomes_multipolygon():
    # Devils Lake|ND shipped as 4 polygons + 1 LineString
    gc = GeometryCollection([box(0, 0, 1, 1), box(2, 0, 3, 1), LineString([(0, 0), (3, 3)]), box(4, 0, 5, 1), box(6, 0, 7, 1)])
    g = lg.repair(gc)
    assert g.geom_type == "MultiPolygon" and len(g.geoms) == 4 and g.is_valid
    assert lg.repair(GeometryCollection([LineString([(0, 0), (1, 1)])])) is None


def test_invalid_bowtie_is_repaired_and_area_is_kept():
    bow = Polygon([(0, 0), (2, 2), (2, 0), (0, 2)])
    assert not bow.is_valid
    g = lg.repair(bow)
    assert g.is_valid and g.geom_type in ("Polygon", "MultiPolygon") and g.area == pytest.approx(2.0)


def test_degenerate_polygons_are_detected():
    # Lake Shafer: 4 vertices, zero area; Buckeye: 6 vertices; Waiau: 6 vertices
    assert lg.is_degenerate(Polygon([(-86.77, 40.8), (-86.77, 40.8), (-86.77, 40.8), (-86.77, 40.8)]))
    tiny = box(-82.5, 39.9, -82.4995, 39.9004)
    assert lg.is_degenerate(tiny)
    assert not lg.is_degenerate(lake_shape())


def test_drop_small_holes_keeps_islands_at_or_above_100_m2():
    outer = box(0, 0, 1000, 1000)
    holes = [box(10, 10, 20, 20),     # 100 m2: kept
             box(30, 30, 39, 39),     # 81 m2: dropped
             box(100, 100, 400, 400)]  # 90,000 m2: kept
    p = Polygon(outer.exterior, [h.exterior.coords for h in holes])
    q = lg.drop_small_holes(p, 100.0)
    assert len(q.interiors) == 2
    assert sorted(round(Polygon(r).area) for r in q.interiors) == [100, 90000]
    assert q.exterior.equals(p.exterior)


def test_drop_small_parts_keeps_the_largest_and_clean_metric_composes():
    mp = MultiPolygon([box(0, 0, 1000, 1000), box(2000, 0, 2005, 5), box(3000, 0, 3100, 100)])
    out = lg.drop_small_parts(mp, 100.0)
    assert len(out.geoms) == 2 and out.area == pytest.approx(1_000_000 + 10_000)
    solo = lg.drop_small_parts(MultiPolygon([box(0, 0, 5, 5), box(10, 0, 12, 2)]), 100.0)
    assert solo.geom_type == "Polygon" and solo.area == pytest.approx(25)       # the largest part survives even when tiny
    assert lg.clean_metric(GeometryCollection([mp, LineString([(0, 0), (1, 1)])])).is_valid


# ------------------------------------------------------------------ pieces and union rule


def test_choose_variant_rule():
    use, _ = lg.choose_variant(136.7, 217.3, [226.4, 233.6])          # Hartwell: the union is much closer
    assert use
    use, why = lg.choose_variant(40.0, 140.0, [44.0])                 # union overshoots the reference by 3x: leave the pieces out
    assert not use and "further" in why
    use, _ = lg.choose_variant(100.0, 108.0, [])                      # no reference: connected pieces are included
    assert use


def test_match_seed_never_takes_a_neighbour_lake_that_merely_contains_the_point():
    big = {"g": box(0, 0, 5000, 5000), "area": 25e6, "name": "Saylorville Lake", "nm": 0.0, "cover": 0.0, "contains_pt": True, "dist": 0.0}
    own = {"g": box(8000, 0, 9000, 3500), "area": 3.5e6, "name": "Big Creek Lake", "nm": 1.0, "cover": 0.99, "contains_pt": False, "dist": 782.0}
    seed, how = lg.match_seed([big, own], True)
    assert seed == [own] and how == "engine-overlap"
    seed, how = lg.match_seed([big], False)                       # no polygon, different name, no reference: nothing is picked
    assert seed == [] and how == "none"
    seed, how = lg.match_seed([big], False, [24.0])               # ... unless an independent pool area confirms it (Buckeye / Crane Lake)
    assert seed == [big] and how == "point-area-fallback"
    seed, how = lg.match_seed([dict(own, cover=None)], False)     # named, near the point
    assert seed and how == "point-name-fallback"


def test_adjacent_pieces_rule():
    main = box(0, 0, 10000, 5000)
    near_unnamed = box(10050, 0, 12000, 3000)       # 50 m away, 6 % of main
    far = box(11000, 0, 13000, 3000).difference(box(11000, 0, 13000, 3000)) if False else box(30000, 0, 32000, 3000)
    tiny = box(10050, 4000, 10100, 4050)
    named_other = box(0, 5100, 4000, 7000)
    rows = [{"g": g, "area": g.area, "name": n, "nm": m} for g, n, m in
            [(main, "Big Lake", 1.0), (near_unnamed, None, 0.0), (far, None, 0.0), (tiny, None, 0.0), (named_other, "Other Pond", 0.0)]]
    adj = lg.adjacent_pieces(rows, [rows[0]])
    assert [r["g"] for r in adj] == [near_unnamed]


# ------------------------------------------------------------------ simplification


def test_display_and_analysis_variants_are_valid_ordered_and_shrink():
    g = lake_shape(islands=[(0, 0, 40), (1.5, 0.2, 12), (-2, 0.1, 5), (-1, -0.3, 80)])    # 5 m island is < 100 m2: dropped
    ana, a_area, a_tol = lg.make_variant(g, lg.ANALYSIS_TOL_M)
    dis, d_area, d_tol = lg.make_variant(g, lg.DISPLAY_TOL_M)
    assert (a_tol, d_tol) == (25.0, 50.0)
    for v in (ana, dis):
        assert v.is_valid and v.geom_type in ("Polygon", "MultiPolygon")
        for p in lg.parts_of(v):
            assert p.exterior.is_ccw and all(not i.is_ccw for i in p.interiors)          # RFC 7946
    assert lg.nverts(dis) < lg.nverts(ana) < lg.nverts(g)
    assert abs(d_area - a_area) / a_area < 0.03
    assert lg.n_holes(ana) == 3 and lg.n_holes(dis) <= 3                                 # the sub-100 m2 island is gone, the big ones stay
    xs = [c for p in lg.parts_of(ana) for c in p.exterior.coords]
    assert all(round(x, 5) == x and round(y, 5) == y for x, y in xs)                     # 5-decimal grid


def test_simplification_is_deterministic_to_the_byte():
    g = lake_shape(islands=[(0, 0, 40)])
    props = {"lakeId": "T|AL", "variant": "display"}
    outs = []
    for _ in range(3):
        v, _a, _t = lg.make_variant(g, lg.DISPLAY_TOL_M)
        outs.append(lg.gzip_bytes(lg.feature_bytes(v, props)))
    assert outs[0] == outs[1] == outs[2]
    assert lg.sha256(outs[0]) == lg.sha256(outs[1])
    # order of input rings/parts does not change the result
    mp = MultiPolygon([lake_shape(lon0=-86.0), lake_shape(lon0=-85.9, w_km=3)])
    mp2 = MultiPolygon(list(reversed(list(mp.geoms))))
    a, _, _t = lg.make_variant(mp, 25.0, center=(-85.95, 34.5))
    b, _, _t = lg.make_variant(mp2, 25.0, center=(-85.95, 34.5))
    assert a.equals(b)
    raw = gzip.decompress(outs[0])
    f = json.loads(raw)
    assert f["type"] == "Feature" and f["geometry"]["type"] in ("Polygon", "MultiPolygon") and f["properties"]["lakeId"] == "T|AL"
    assert outs[0][4:8] == b"\x00\x00\x00\x00"                                           # gzip mtime 0


def test_tolerance_is_capped_for_tiny_lakes():
    assert lg.effective_tolerance(50.0, 266e6) == 50.0                    # Guntersville
    assert lg.effective_tolerance(25.0, 266e6) == 25.0
    assert lg.effective_tolerance(50.0, 0.1e6) == pytest.approx(7.91, abs=0.01)   # a 0.1 km2 pond
    assert lg.effective_tolerance(50.0, 100.0) == lg.TOL_MIN_M            # never below 2 m
    pond = lake_shape(w_km=0.4, h_km=0.25)
    v, a, tol = lg.make_variant(pond, lg.DISPLAY_TOL_M)
    assert tol < 10 and abs(a - metric(pond).area / 1e6) / a < 0.03


def test_simplified_shape_stays_close_to_the_source():
    g = lake_shape()
    v, _, _t = lg.make_variant(g, lg.DISPLAY_TOL_M)
    ga, va = metric(g), metric(v)
    assert shapely.hausdorff_distance(ga.boundary, va.boundary) < 3 * lg.DISPLAY_TOL_M
    assert ga.symmetric_difference(va).area / ga.area < 0.05


# ------------------------------------------------------------------ confidence


def base_facts(**kw):
    f = {"has_geometry": True, "engine_source": "name", "identity_pick": "engine-overlap", "name_match": 1.0, "point_flag": "ok",
         "dist_m": 0.0, "allowed_m": 3000.0, "n_substantial_parts": 1, "adjacent_rejected_km2": 0.0, "area_km2": 200.0,
         "nid_km2": 210.0, "usace_km2": None, "gsw_ge50_pct": 85.0, "osm_ok": True}
    f.update(kw)
    return f


def test_confidence_levels():
    assert lg.derive_confidence(base_facts())[0] == "HIGH"
    assert lg.derive_confidence(base_facts(has_geometry=False, missing_reason="no NHD"))[0] == "MISSING"
    lvl, why = lg.derive_confidence(base_facts(point_flag="identity-risk", dist_m=27600, allowed_m=3000))
    assert lvl == "LOW" and "identity risk" in why[0]
    assert lg.derive_confidence(base_facts(gsw_ge50_pct=5))[0] == "LOW"
    assert lg.derive_confidence(base_facts(nid_km2=60.0, usace_km2=70.0))[0] == "LOW"           # both references off by > 2x
    assert lg.derive_confidence(base_facts(engine_source="repaired:contains-point"))[0] == "MEDIUM"
    assert lg.derive_confidence(base_facts(n_substantial_parts=2))[0] == "MEDIUM"
    assert lg.derive_confidence(base_facts(point_flag="off-water", dist_m=800))[0] == "HIGH"   # a coordinate defect is not a shoreline defect


def test_union_that_matches_pool_area_moves_medium_to_high():
    partial = base_facts(area_km2=136.7, nid_km2=226.4, usace_km2=233.6)      # Hartwell before: E/NID 0.60
    union = base_facts(area_km2=218.7, nid_km2=226.4, usace_km2=233.6)
    l0, w0 = lg.derive_confidence(partial)
    l1, w1 = lg.derive_confidence(union)
    assert l0 == "MEDIUM" and any("pool-area ratio" in w for w in w0)
    assert l1 == "HIGH" and w1 == []
    assert lg.confidence_score("HIGH", [], 3) > lg.confidence_score("MEDIUM", ["x"]) > lg.confidence_score("LOW", ["x", "y"]) > lg.confidence_score("MISSING", [])


def test_point_flag_matches_research_rule():
    assert lg.point_flag(0, 790, 100) == "ok"
    assert lg.point_flag(2000, 790, 100) == "off-water"
    assert lg.point_flag(27600, 790, 2.1) == "identity-risk"
    assert lg.point_flag(9000, 790, 266) == "ok" or lg.point_flag(9000, 790, 266) == "off-water"   # a big reservoir tolerates a dam coordinate
    assert lg.point_flag(9000, 790, 266) != "identity-risk"


# ------------------------------------------------------------------ index schema


def synthetic_entry(lake_id="Test Lake|AL", level_inputs=None, built="2026-10-13T00:00:00Z"):
    g = lake_shape(islands=[(0, 0, 40)])
    lon0, lat0 = -86.0, 34.5
    t, tinv = lg.transformers(lon0, lat0)
    gm = lg.repair(lg.project(g, t))
    attrs = {"OBJECTID": 1, "PERMANENT_IDENTIFIER": "12345678", "GNIS_NAME": "Test Lake", "AREASQKM": gm.area / 1e6, "FDATE": 1622000000000}
    row = {"g": gm, "g_deg": g, "area": gm.area, "name": "Test Lake", "nm": 1.0, "attrs": attrs}
    lake = {"id": lake_id, "name": "Test Lake", "state": "AL", "states": ["AL"], "lat": lat0, "lon": lon0, "fullPoolFt": 500.0,
            "poolBasis": "fullPool", "poolConfidence": "high"}
    plan = {"status": "ok", "members": [row], "seed": [row], "adj": [], "use_adj": True, "adj_why": "no adjacent pieces", "adj_area_km2": 0.0,
            "pick_method": "engine-overlap", "engine_source": "name"}
    geom = bg.make_geometry(lake, plan)
    return lake, plan, geom


def test_registry_entry_conforms_to_schema_and_files_match_hashes(tmp_path):
    lake, plan, geom = synthetic_entry()
    files = []
    flag = {"nid_surface_km2": "100", "nid_id": "AL00001", "nid_name": "Test Dam", "usace_matched": "False", "confidence": "MEDIUM",
            "source": "name", "osm_name_match": "1", "osm_bbox_iou": "0.9", "osm_best_type": "relation/1", "osm_wikidata": "Q1"}
    e = bg.registry_entry(lake, flag, plan, geom, {"lake_class": "R1_run_of_river_pool", "regime": "reservoir", "region": "SE", "size": "m",
                                                  "depth_class": "mid", "res_time_d": "10.5", "hasDam": "True"}, None,
                          "2026-10-13T00:00:00Z", str(tmp_path), files)
    assert lg.validate_entry(e, bg.BASE_URL) == []
    assert e["lakeKey"] == "Test_Lake_AL" and e["geometryConfidence"]["before"] == "MEDIUM"
    assert e["classification"]["residenceTimeDays"] == 10.5 and e["externalIds"]["nidId"] == "AL00001" and e["externalIds"]["osm"] == "relation/1"
    for variant in ("display", "analysis"):
        p = tmp_path / "lakes" / "Test_Lake_AL" / f"geometry.v1.{variant}.geojson.gz"
        b = p.read_bytes()
        assert lg.sha256(b) == e["geometry"]["sha256"][variant]
        assert len(b) == e["geometry"]["bytes"][variant + "Gzip"]
        f = json.loads(gzip.decompress(b))
        assert f["properties"]["sourceIds"] == ["12345678"] and f["properties"]["variant"] == variant
    w, s, e_, n = e["bbox"]
    assert w < e["centroid"][0] < e_ and s < e["centroid"][1] < n
    assert json.loads(json.dumps(e)) == e                                                   # JSON round trip (no NaN, no tuples)


def test_null_geometry_entry_requires_reason_and_missing_confidence(tmp_path):
    lake = {"id": "Koele ponds (Lanai)|HI", "name": "Koele ponds (Lanai)", "state": "HI", "states": ["HI"], "lat": 20.8, "lon": -156.9}
    plan = {"status": "no-nhd", "reason": "no NHD lake/reservoir polygon matches", "engine_source": ""}
    e = bg.registry_entry(lake, {"confidence": "MISSING"}, plan, None, None, None, "2026-10-13T00:00:00Z", str(tmp_path), [])
    assert e["geometry"] is None and e["geometryConfidence"]["level"] == "MISSING" and e["geometryMissingReason"]
    assert lg.validate_entry(e, bg.BASE_URL) == []
    e2 = dict(e, geometryMissingReason="")
    assert lg.validate_entry(e2)


def test_schema_rejects_bad_entries(tmp_path):
    lake, plan, geom = synthetic_entry()
    e = bg.registry_entry(lake, {}, plan, geom, None, None, "2026-10-13T00:00:00Z", str(tmp_path), [])
    assert lg.validate_entry(e) == []
    for mutate in (lambda x: x.update(lakeKey="Wrong"), lambda x: x["geometry"].update(displayUrl="https://x/y.gz"),
                   lambda x: x["geometry"]["sha256"].update(display="abc"), lambda x: x.update(bbox=[1, 2, 0, 3]),
                   lambda x: x["geometryConfidence"].update(level="GREAT"), lambda x: x.update(memberIds=["Other|AL"]),
                   lambda x: x.pop("poolExtents")):
        bad = json.loads(json.dumps(e))
        mutate(bad)
        assert lg.validate_entry(bad), mutate


def test_member_ids_group_lakes_that_share_nhd_features():
    mk = lambda i, nhd: {"lakeId": i, "geometry": {"seedIds": nhd} if nhd else None, "memberIds": [i]}   # noqa: E731
    idx = [mk("East Lake Tohopekaliga|FL", ["1", "2"]), mk("Tohopekaliga (Toho)|FL", ["2", "1"]), mk("Other|FL", ["9"]), mk("None|FL", [])]
    bg.link_members(idx)
    assert idx[0]["memberIds"] == idx[1]["memberIds"] == ["East Lake Tohopekaliga|FL", "Tohopekaliga (Toho)|FL"]
    assert idx[2]["memberIds"] == ["Other|FL"] and idx[3]["memberIds"] == ["None|FL"]


# ------------------------------------------------------------------ the produced registry (skipped when not built)

OUT = os.environ.get("REGISTRY_OUT", bg.DEFAULTS["out"])


@pytest.mark.skipif(not os.path.exists(os.path.join(OUT, "registry", "lakes.v1.json")), reason="registry not built")
def test_built_registry_is_complete_and_consistent():
    reg = json.load(open(os.path.join(OUT, "registry", "lakes.v1.json")))
    lakes = reg["lakes"]
    assert reg["count"] == len(lakes) == 621
    assert sorted(l["lakeId"] for l in lakes) == IDS
    problems = [p for e in lakes for p in lg.validate_entry(e, bg.BASE_URL)]
    assert problems == []
    for e in lakes:
        if e["geometry"]:
            for v in ("display", "analysis"):
                b = open(os.path.join(OUT, "lakes", e["lakeKey"], f"geometry.v1.{v}.geojson.gz"), "rb").read()
                assert lg.sha256(b) == e["geometry"]["sha256"][v]
