"""Tests for the 2026-10 geometry recovery: okina-safe name matching and the index merge that adds recovered lakes
without touching any published lake (jobs/lake-geometry/merge_registry.py)."""
import copy
import json
import os

import pytest

import build_geometry as bg
import lake_geometry as lg
import merge_registry as mr
from test_lake_geometry import synthetic_entry


# ------------------------------------------------------------------ name matching (Wilson Lake / Kaelepulu Pond)


def test_okina_is_part_of_the_word_not_a_separator():
    assert lg.norm_name("Kaʻelepulu Pond") == {"kaelepulu"}
    assert lg.norm_name("Ka‘elepulu Pond") == {"kaelepulu"}                       # left single quote used as okina
    assert lg.name_match("Kaʻelepulu Pond", "Wilson Lake / Kaelepulu Pond") == 1.0
    assert lg.name_match("Nuʻupia Pond", "Wilson Lake / Kaelepulu Pond") == 0.0   # a different pond is still a different pond


def test_diacritics_are_folded():
    assert lg.norm_name("Café Lake") == lg.norm_name("Cafe Lake") == {"cafe"}
    assert lg.norm_name("Waiāhole Reservoir") == {"waiahole"}


def test_ascii_apostrophe_behaviour_is_unchanged():
    # existing behaviour kept on purpose: changing it would move name matches of already published lakes
    assert lg.norm_name("Devil's Kitchen Lake") == {"devil", "s", "kitchen"}
    assert lg.norm_name("Lake o' the Cherokees") == {"o", "cherokees"}


def test_okina_pond_is_picked_by_name_near_the_point():
    from shapely.geometry import box
    pond = {"g": box(0, 0, 600, 550), "area": 0.33e6, "name": "Kaʻelepulu Pond", "nm": lg.name_match("Kaʻelepulu Pond", "Wilson Lake / Kaelepulu Pond"),
            "cover": None, "contains_pt": False, "dist": 250.0}
    other = dict(pond, name="Nuʻupia Pond", nm=lg.name_match("Nuʻupia Pond", "Wilson Lake / Kaelepulu Pond"), dist=2200.0, area=0.36e6)
    seed, how = lg.match_seed([other, pond], False)
    assert seed == [pond] and how == "point-name-fallback"


# ------------------------------------------------------------------ merge: adds geometry to null lakes, changes nothing else


def build_inputs(tmp_path):
    """live: three lakes (A published, B null, C null). partial: B built. Returns (live, partial, partial_dir)."""
    lake, plan, geom = synthetic_entry("Pub Lake|AL")
    live_entries = []
    files = []
    a = bg.registry_entry(lake, {}, plan, geom, None, None, "2026-10-13T00:00:00Z", str(tmp_path / "live_out"), files)
    a["geometry"]["seedIds"] = ["99999999"]                                    # a different NHD water than the target's
    live_entries.append(a)
    for name, st in (("Null B", "AL"), ("Null C", "AL")):
        l = {"id": f"{name}|{st}", "name": name, "state": st, "states": [st], "lat": 34.5, "lon": -86.0}
        live_entries.append(bg.registry_entry(l, {"confidence": "LOW"}, {"status": "query-error", "reason": "geometry pending: x", "engine_source": ""},
                                               None, None, None, "2026-10-13T00:00:00Z", str(tmp_path / "live_out"), []))
    live_entries.sort(key=lambda e: e["lakeId"])
    live = {"schema": bg.SCHEMA, "geometryVersion": "v1", "generatedAt": "2026-10-13T00:00:00Z", "count": 3, "baseUrl": bg.BASE_URL,
            "license": bg.LICENSE, "lakes": live_entries}
    # partial build of "Null B|AL": reuse the synthetic NHD shape under B's identity
    lb, pb, gb = synthetic_entry("Null B|AL")
    pdir = tmp_path / "partial"
    eb = bg.registry_entry(lb, {}, pb, gb, None, None, "2026-10-14T00:00:00Z", str(pdir), [])
    partial = dict(live, count=1, lakes=[eb])
    (pdir / "registry").mkdir(parents=True, exist_ok=True)
    (pdir / "registry" / "lakes.v1.json").write_text(json.dumps(partial))
    return live, partial, str(pdir)


def test_merge_adds_target_and_leaves_everything_else_identical(tmp_path):
    live, partial, pdir = build_inputs(tmp_path)
    merged, rep = mr.merge(live, partial, ["Null B|AL"], pdir, "2026-10-14T01:00:00Z")
    assert merged["count"] == 3 and merged["generatedAt"] == "2026-10-14T01:00:00Z"
    by_live = {e["lakeId"]: e for e in live["lakes"]}
    by_new = {e["lakeId"]: e for e in merged["lakes"]}
    assert by_new["Pub Lake|AL"] == by_live["Pub Lake|AL"] and by_new["Null C|AL"] == by_live["Null C|AL"]
    assert by_new["Null B|AL"]["geometry"] is not None and by_new["Null B|AL"]["geometryConfidence"]["level"] != "MISSING"
    assert [e["lakeId"] for e in merged["lakes"]] == [e["lakeId"] for e in live["lakes"]]
    assert rep["targets"] == ["Null B|AL"] and rep["unchanged"] == 2
    assert by_live["Null B|AL"]["geometry"] is None                                                    # the input was not mutated


def test_merge_refuses_to_replace_a_published_geometry(tmp_path):
    live, partial, pdir = build_inputs(tmp_path)
    partial_pub = copy.deepcopy(partial)
    partial_pub["lakes"][0] = dict(partial["lakes"][0], lakeId="Pub Lake|AL", lakeKey="Pub_Lake_AL")
    with pytest.raises(mr.MergeError, match="already has geometry"):
        mr.merge(live, partial_pub, ["Pub Lake|AL"], pdir, "t")


def test_merge_refuses_unknown_target_or_missing_geometry(tmp_path):
    live, partial, pdir = build_inputs(tmp_path)
    with pytest.raises(mr.MergeError, match="not in the live index"):
        mr.merge(live, partial, ["Nope|AL"], pdir, "t")
    with pytest.raises(mr.MergeError, match="no geometry"):
        mr.merge(live, partial, ["Null C|AL"], pdir, "t")                     # C is null in the partial too (absent)


def test_merge_refuses_a_corrupted_or_missing_object(tmp_path):
    live, partial, pdir = build_inputs(tmp_path)
    p = os.path.join(pdir, "lakes", "Null_B_AL", "geometry.v1.display.geojson.gz")
    with open(p, "ab") as fh:
        fh.write(b"x")
    with pytest.raises(mr.MergeError, match="sha256"):
        mr.merge(live, partial, ["Null B|AL"], pdir, "t")
    os.remove(p)
    with pytest.raises(mr.MergeError, match="missing"):
        mr.merge(live, partial, ["Null B|AL"], pdir, "t")


def test_merge_refuses_when_the_target_shares_an_nhd_feature_with_a_published_lake(tmp_path):
    live, partial, pdir = build_inputs(tmp_path)
    pub = next(e for e in live["lakes"] if e["lakeId"] == "Pub Lake|AL")
    pub["geometry"]["seedIds"] = list(partial["lakes"][0]["geometry"]["seedIds"])      # same NHD id as the target
    with pytest.raises(mr.MergeError, match="shares an NHD feature"):
        mr.merge(live, partial, ["Null B|AL"], pdir, "t")


def test_stage_writes_only_new_objects_and_a_valid_manifest(tmp_path):
    live, partial, pdir = build_inputs(tmp_path)
    (tmp_path / "live.json").write_text(json.dumps(live))
    (tmp_path / "man.json").write_text(json.dumps({"counts": {"lakes": 3}, "objectCount": 2, "files": {}}))

    import types
    a = types.SimpleNamespace(live=str(tmp_path / "live.json"), live_manifest=str(tmp_path / "man.json"), partial=pdir, targets="Null B|AL",
                              refresh_null="", out=str(tmp_path / "stage"), built_at="2026-10-14T01:00:00Z")
    rep = mr.stage(a)
    staged = sorted(os.path.relpath(os.path.join(d, f), a.out) for d, _s, fs in os.walk(os.path.join(a.out, "lakes")) for f in fs)
    assert staged == ["lakes/Null_B_AL/geometry.v1.analysis.geojson.gz", "lakes/Null_B_AL/geometry.v1.display.geojson.gz"]
    man = json.load(open(os.path.join(a.out, "registry", "manifest.v1.json")))
    assert man["counts"]["withGeometry"] == 2 and man["counts"]["geometryNull"] == 1 and man["objectCount"] == 4
    assert man["amendments"][0]["lakes"] == ["Null B|AL"]
    idx = json.load(open(os.path.join(a.out, "registry", "lakes.v1.json")))
    assert idx["count"] == 3 and rep["indexSha256"] == lg.sha256(open(os.path.join(a.out, "registry", "lakes.v1.json"), "rb").read())


def test_refresh_null_replaces_a_pending_status_with_the_final_no_nhd_result(tmp_path):
    live, partial, pdir = build_inputs(tmp_path)
    l = {"id": "Null C|AL", "name": "Null C", "state": "AL", "states": ["AL"], "lat": 34.5, "lon": -86.0}
    fresh = bg.registry_entry(l, {"confidence": "LOW"}, {"status": "no-nhd", "reason": "no NHD lake/reservoir polygon matches", "engine_source": ""},
                              None, None, None, "2026-10-14T00:00:00Z", pdir, [])
    partial["lakes"].append(fresh)
    merged, rep = mr.merge(live, partial, ["Null B|AL"], pdir, "2026-10-14T01:00:00Z", ["Null C|AL"])
    c = next(e for e in merged["lakes"] if e["lakeId"] == "Null C|AL")
    assert c["geometry"] is None and c["geometryMissingStatus"] == "no-nhd" and rep["refreshedNull"] == ["Null C|AL"]
    assert next(e for e in live["lakes"] if e["lakeId"] == "Null C|AL")["geometryMissingStatus"] == "pending"      # input untouched


def test_refresh_null_refuses_published_lakes_and_still_pending_results(tmp_path):
    live, partial, pdir = build_inputs(tmp_path)
    with pytest.raises(mr.MergeError, match="null and `pending`"):
        mr.merge(live, partial, ["Null B|AL"], pdir, "t", ["Pub Lake|AL"])
    l = {"id": "Null C|AL", "name": "Null C", "state": "AL", "states": ["AL"], "lat": 34.5, "lon": -86.0}
    still = bg.registry_entry(l, {}, {"status": "query-error", "reason": "geometry pending: x", "engine_source": ""}, None, None, None, "t", pdir, [])
    partial["lakes"].append(still)
    with pytest.raises(mr.MergeError, match="final"):
        mr.merge(live, partial, ["Null B|AL"], pdir, "t", ["Null C|AL"])
