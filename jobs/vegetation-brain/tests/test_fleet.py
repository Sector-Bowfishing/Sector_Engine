from vegetation_brain import fleet as F


def entry(lid, area, conf="HIGH", geom=True):
    return {"lakeId": lid, "name": lid, "state": "XX", "lakeKey": lid, "areaKm2": area if geom else None,
            "geometry": {"x": 1} if geom else None, "geometryConfidence": {"level": conf if geom else "MISSING"},
            "classification": {"region": "SE", "lakeClass": "R1"}, "geometryVersion": "v1"}


def test_tiers_follow_canonical_geometry_not_legacy_polygons():
    reg = {"generatedAt": "t", "geometryVersion": "v1", "lakes": [entry("a", 100), entry("b", 2.0), entry("c", 0.2), entry("d", None, geom=False)]}
    m = F.build_manifest(reg)
    t = {r["lakeId"]: r for r in m["candidates"]}
    assert t["a"]["tier"] == "HIGH" and t["b"]["tier"] == "MEDIUM" and t["c"]["tier"] == "LOW" and t["d"]["tier"] == "UNKNOWN"
    assert t["d"]["readiness"] == "BLOCKED" and t["d"]["reasons"] == ["NO_GEOMETRY"]
    assert t["c"]["readiness"] == "BLOCKED" and "TOO_NARROW" in t["c"]["reasons"]
    assert m["summary"]["totalLakes"] == 4


def test_low_geometry_confidence_downgrades_one_tier():
    reg = {"lakes": [entry("a", 100, "LOW"), entry("b", 2.0, "LOW"), entry("c", 100, "MEDIUM")]}
    t = {r["lakeId"]: r for r in F.build_manifest(reg)["candidates"]}
    assert t["a"]["tier"] == "MEDIUM" and "GEOMETRY_LOW" in t["a"]["reasons"]
    assert t["b"]["tier"] == "LOW"
    assert t["c"]["tier"] == "HIGH"


def test_observability_says_nothing_about_submerged():
    m = F.build_manifest({"lakes": [entry("a", 100)]})
    assert "submerged" in m["note"].lower() and "no tier" in m["note"].lower()
