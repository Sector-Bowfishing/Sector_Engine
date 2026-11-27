"""Manifest builder: the seriesMedian and lowWaterDatum reference bases (owner decision, Michael, 2026-11-22, Sector_Ops #51 comment 7075545102).
Runs on the committed release and research records only (no research dataset needed)."""
import json

import pytest

from conftest import MANIFEST_PATH

from depth_brain import contract as C
from depth_research.candidates import GREAT_LAKES_LWD, alternative_reference, history_is_live_series, level_datum_for, load_lake_bindings, load_lwd

LWD = load_lwd()
LB = load_lake_bindings()
SAME = {"live": [{"provider": "usgs", "station": "05000000", "series": "62614", "datumOffsetFt": 0.0}],
        "history": [{"kind": "usgsDaily", "site": "05000000", "param": "62614", "stat": "dv", "offsetFt": 0.0}]}
MANIFEST = json.load(open(MANIFEST_PATH))


def test_lwd_record_covers_the_fourteen_coops_great_lakes_with_noaa_values():
    d = json.load(open(GREAT_LAKES_LWD))
    assert d["datum"] == "IGLD85" and {e["publisher"] for e in d["evidence"]} == {"NOAA CO-OPS", "Canadian Hydrographic Service"}
    assert {k: v["lwdFt"] for k, v in d["lakes"].items()} == {"superior": 601.1, "michigan-huron": 577.5, "st-clair": 572.3, "erie": 569.2, "ontario": 243.3}
    coops = {c["lakeId"] for c in MANIFEST["candidates"] if c["levelSource"]["provider"] == "coops"}
    assert coops == set(LWD) and len(coops) == 14
    assert LWD["Green Bay|WI"]["lwdFt"] == 577.5 and LWD["Lake St. Clair|MI"]["lwdFt"] == 572.3


def test_coops_igld85_series_is_a_verified_igld85_level():
    assert level_datum_for({"provider": "coops", "series_or_param": "water_level_IGLD85"}, {})[:2] == ("IGLD85", True)
    assert level_datum_for({"provider": "coops", "series_or_param": "water_level"}, {})[:2] == (None, False)


def test_great_lake_with_igld85_level_gets_the_low_water_datum():
    basis, a, blocked = alternative_reference("Lake Erie|OH", ["REFERENCE_NOT_A_POOL_ELEVATION", "REFERENCE_POOL_CONFIDENCE_LOW", "DATUM_UNKNOWN"],
                                              "IGLD85", True, 3, LWD)
    assert basis == "lowWaterDatum" and blocked == [] and a.status == "SAME_DATUM" and a.basis == "great-lakes-lwd:erie"
    assert a.evidence_urls and all(u.startswith("https://") for u in a.evidence_urls)
    # an unverified or different level datum never gets the LWD (falls through to the series rule)
    assert alternative_reference("Lake Erie|OH", ["DATUM_UNKNOWN"], "PROJECT", True, 30, LWD, SAME)[0] == "seriesMedian"
    assert alternative_reference("Lake Erie|OH", ["DATUM_UNKNOWN"], "IGLD85", False, 3, LWD)[0] is None


def test_series_median_needs_enough_history_and_refuses_otherwise():
    reasons = ["REFERENCE_NOT_A_POOL_ELEVATION", "REFERENCE_POOL_CONFIDENCE_LOW", "DATUM_UNKNOWN"]
    basis, a, blocked = alternative_reference("Natural|MN", reasons, None, False, C.SERIES_MEDIAN_MIN_YEARS, LWD, SAME, "naturalSurface")
    assert basis == "seriesMedian" and a.status == "SAME_SERIES" and a.usable and blocked == []
    for years in (None, 0, C.SERIES_MEDIAN_MIN_YEARS - 1):
        basis, a, blocked = alternative_reference("Natural|MN", reasons, None, False, years, LWD, SAME, "naturalSurface")
        assert basis is None and a is None and blocked == reasons + ["SERIES_HISTORY_TOO_SHORT"]


def _b(live, *history):
    return {"live": [live], "history": list(history)}


def test_same_series_guard_matches_lakes_history_to_its_live_series():
    ok = [
        SAME,
        _b({"provider": "nwps", "station": "INDN6", "series": "HPIRZ"}, {"kind": "hadsDaily", "lid": "INDN6", "pe": "HP", "offsetFt": 0.0}),
        _b({"provider": "a2w", "station": "SPA:Abiquiu", "series": "Abiquiu.Elev.Inst.15Minutes.0.DCP-rev", "datumOffsetFt": 0.0},
           {"kind": "cwmsDaily", "office": "SPA", "series": "Abiquiu.Elev.Inst.~1Day.0.MRS"}),
        _b({"provider": "cwms", "station": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS"},
           {"kind": "cwmsDaily", "office": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS"}),
    ]
    bad = [
        None, {"live": [], "history": []},
        _b({"provider": "usgs", "station": "05000000", "series": "62614"}, {"kind": "usgsDaily", "site": "05000000", "param": "62615", "offsetFt": 0.0}),   # param
        _b({"provider": "usgs", "station": "05000000", "series": "62614"}, {"kind": "usgsDaily", "site": "05000001", "param": "62614", "offsetFt": 0.0}),   # site
        _b({"provider": "usgs", "station": "05000000", "series": "00065", "datumOffsetFt": 0.0},
           {"kind": "usgsDaily", "site": "05000000", "param": "00065", "offsetFt": 512.3}),                                                               # offset
        _b({"provider": "nwps", "station": "INDN6", "series": "HPIRZ"}, {"kind": "hadsDaily", "lid": "OTHR6", "pe": "HP", "offsetFt": 0.0}),           # lid
        _b({"provider": "nwps", "station": "INDN6", "series": "HGIRZ"}, {"kind": "hadsDaily", "lid": "INDN6", "pe": "HG", "offsetFt": 0.0}),           # stage pe
        _b({"provider": "a2w", "station": "SPA:Abiquiu", "series": "Abiquiu.Elev.Inst.15Minutes.0.DCP-rev"},
           {"kind": "cwmsDaily", "office": "SPK", "series": "Abiquiu.Elev.Inst.~1Day.0.MRS"}),                                                            # office
        _b({"provider": "cwms", "station": "SAS", "series": "Hartwell.Elev.Inst.1Hour.0.Raw"}, {"kind": "cwmsDaily", "office": "SAS", "series": "Russell.Elev.Inst.1Day.0.Raw"}),
        _b({"provider": "rise", "station": "1", "series": "x"}, {"kind": "riseDaily", "item": "x"}),                                                    # provider not covered
        {"live": SAME["live"], "history": SAME["history"] * 2},                                                                                      # two sources
    ]
    assert all(history_is_live_series(b) for b in ok)
    assert not any(history_is_live_series(b) for b in bad)


def test_indian_lake_oh_62614_live_vs_62615_history_is_blocked():
    b = LB["Indian Lake|OH"]
    assert b["live"][0]["series"] == "62614" and b["history"][0]["param"] == "62615"
    basis, _, blocked = alternative_reference("Indian Lake|OH", ["DATUM_UNKNOWN"], None, False, 30, LWD, b, "fullPool")
    assert basis is None and blocked == ["DATUM_UNKNOWN", "SERIES_HISTORY_NOT_LIVE_SERIES"]


def test_full_pool_reservoir_switch(monkeypatch):
    assert C.SERIES_MEDIAN_ALLOW_FULL_POOL_RESERVOIRS is True                       # default ON pending Michael (Sector_Ops #51)
    assert alternative_reference("R|AL", ["DATUM_UNKNOWN"], None, False, 30, LWD, SAME, "fullPool")[0] == "seriesMedian"
    monkeypatch.setattr(C, "SERIES_MEDIAN_ALLOW_FULL_POOL_RESERVOIRS", False)
    assert alternative_reference("R|AL", ["DATUM_UNKNOWN"], None, False, 30, LWD, SAME, "fullPool") == (None, None, ["DATUM_UNKNOWN", "SERIES_MEDIAN_FULL_POOL_RESERVOIR_OFF"])
    assert alternative_reference("N|MN", ["REFERENCE_NOT_A_POOL_ELEVATION"], None, False, 30, LWD, SAME, "naturalSurface")[0] == "seriesMedian"


def test_level_side_and_known_datum_failures_get_no_substitute_reference():
    for reasons in (["NO_VERIFIED_LEVEL_BINDING", "REFERENCE_NOT_A_POOL_ELEVATION"], ["LEVEL_SOURCE_NOT_DIRECT", "DATUM_UNKNOWN"],
                    ["DATUM_INCOMPATIBLE"], ["DATUM_CONVERSION_NOT_ENABLED"], ["DUKE_LOCAL_SCALE_NOT_ENABLED"]):
        assert alternative_reference("X|AL", reasons, None, False, 40, LWD, SAME) == (None, None, reasons)


def test_existing_shift_possible_lakes_are_untouched():
    """Every lake the committed release already defends keeps its fullPool route: no blocked reason -> no alternative."""
    ok = [c for c in MANIFEST["candidates"] if c["shiftPossible"]]
    assert ok and all(c["reference"]["basis"] == "fullPool" for c in ok)
    for c in ok:
        assert alternative_reference(c["lakeId"], c["blockedReasons"], c["levelSource"]["datum"], c["levelSource"]["datumVerified"],
                                     c["history"]["completeYears"], LWD, LB.get(c["lakeId"]), c["reference"]["basis"]) == (None, None, [])


def test_counts_on_the_committed_release():
    """What the rules would unlock at the next refresh, computed from the committed release (the rebuild itself needs DEPTH_RESEARCH_DATA)."""
    if MANIFEST["manifestVersion"] != "2026-10-14.6":
        pytest.skip("counts are pinned to release manifest 2026-10-14.6")
    n = {"fullPool": 0, "seriesMedian": 0, "lowWaterDatum": 0, "short": 0, "notLive": 0}
    for c in MANIFEST["candidates"]:
        ls = c["levelSource"]
        ld, lv = (level_datum_for({"provider": "coops", "series_or_param": ls["series"]}, {})[:2] if ls["provider"] == "coops" else (ls["datum"], ls["datumVerified"]))
        basis, _, blocked = alternative_reference(c["lakeId"], c["blockedReasons"], ld, lv, c["history"]["completeYears"], LWD, LB.get(c["lakeId"]), c["reference"]["basis"])
        if not c["blockedReasons"]:
            n["fullPool"] += 1
        elif basis:
            n[basis] += 1
        elif "SERIES_HISTORY_TOO_SHORT" in blocked:
            n["short"] += 1
        elif "SERIES_HISTORY_NOT_LIVE_SERIES" in blocked:
            n["notLive"] += 1
    assert n == {"fullPool": 225, "seriesMedian": 20, "lowWaterDatum": 14, "short": 45, "notLive": 112}  # Moses Lake WA moved to its history gauge (USGS 12471000), 2026-11-25 rebind


# ── end-to-end through build() on a tiny synthetic research snapshot ──────────────────────────────────
def _csv(path, header, rows):
    import csv
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return str(path)


def _build(tmp_path):
    from depth_research.candidates import build
    lakes = [("Full|AL", "fullPool", "high", 595.0), ("Natural|MN", "naturalSurface", "low", 1200.0), ("Short|MN", "naturalSurface", "low", 1100.0),
             ("Lake Erie|OH", "naturalSurface", "low", 571.0)]
    (tmp_path / "dir.json").write_text(json.dumps({"lakes": [{"id": i, "name": i, "state": i[-2:], "poolBasis": b, "poolConfidence": c, "fullPoolFt": p}
                                                               for i, b, c, p in lakes]}))
    (tmp_path / "prov.json").write_text(json.dumps({"providers": {}, "referencePoolSources": {}}))
    (tmp_path / "rev.json").write_text(json.dumps({"schema": "reviewed-lake-bindings-v1", "reviewed": []}))
    usgs = lambda site, hp: {"live": [{"provider": "usgs", "station": site, "series": "00062", "datumOffsetFt": 0.0}],
                             "history": [{"kind": "usgsDaily", "site": site, "param": hp, "stat": "dv", "offsetFt": 0.0}]}
    (tmp_path / "lb.json").write_text(json.dumps({"bindings": [{"lakeId": "Natural|MN", **usgs("01", "00062")}, {"lakeId": "Short|MN", **usgs("02", "00062")}]}))
    paths = {
        "directory": str(tmp_path / "dir.json"), "providers": str(tmp_path / "prov.json"), "reviewed_bindings": str(tmp_path / "rev.json"), "lake_proposed_bindings": str(tmp_path / "lb.json"),
        "bindings": _csv(tmp_path / "b.csv", ["lake_id", "binding_status", "capability_class", "provider", "series_or_param", "complete_years"], [
            ["Full|AL", "VERIFIED", "DIRECT_OPERATOR_POOL", "tva", "ReservoirElevation", 20],
            ["Natural|MN", "VERIFIED", "DIRECT_LAKE_GAUGE", "usgs", "00062", 30],
            ["Short|MN", "VERIFIED", "DIRECT_LAKE_GAUGE", "usgs", "00062", 4],
            ["Lake Erie|OH", "VERIFIED_FLAG", "DIRECT_LAKE_GAUGE", "coops", "water_level_IGLD85", 3]]),
        "full_pool": _csv(tmp_path / "fp.csv", ["id", "source", "winterPoolFt"], [["Full|AL", "TVA top of summer operating zone", ""]]),
        "matrix": _csv(tmp_path / "m.csv", ["lakeId", "evidenceTier", "bestDepthSource", "contourSources"], [["Natural|MN", "A", "MN DNR contours", "MNDNR"]]),
        "contour_truth": _csv(tmp_path / "t.csv", ["lakeId", "interval_ft", "shr_0_3", "shr_3_6", "shr_6_10", "cov_raster", "src"],
                              [["Natural|MN", "2", "0.1", "0.1", "0.1", "0.95", "MNDNR"]]),
        "operating_range": _csv(tmp_path / "o.csv", ["lake", "full_years", "p05_p95_range_ft"], []),
        "datum_shift": _csv(tmp_path / "d.csv", ["id", "shift_ft_ngvd29_to_navd88"], []),
    }
    return {c["lakeId"]: c for c in build(paths, "test")["candidates"]}, build(paths, "test")["summary"]


def test_build_applies_the_bases_and_leaves_full_pool_lakes_alone(tmp_path):
    c, summary = _build(tmp_path)
    full = c["Full|AL"]
    assert full["shiftPossible"] and full["reference"]["basis"] == "fullPool" and full["reference"]["poolFt"] == 595.0
    assert full["datum"]["status"] == "SAME_OPERATOR_SYSTEM" and full["rollout"] == "HIGH_CONFIDENCE" and "directory" not in full["reference"]

    nat = c["Natural|MN"]
    assert nat["shiftPossible"] and nat["blockedReasons"] == [] and nat["rollout"] == "MEDIUM_CONFIDENCE"
    assert nat["reference"]["basis"] == "seriesMedian" and nat["reference"]["poolFt"] is None and nat["datum"]["status"] == "SAME_SERIES"
    assert nat["reference"]["seriesMedian"] == {"statistic": "p50", "windowDays": 7, "minBasisYears": 10, "minSampleCount": 100, "manifestHistoryYears": 30}
    assert nat["reference"]["directory"]["basis"] == "naturalSurface" and "7075545102" in nat["reference"]["decision"]
    assert "referenceZones" not in nat and nat["referenceZonesWithheld"] == "REFERENCE_NOT_FULL_POOL"

    short = c["Short|MN"]
    assert not short["shiftPossible"] and short["rollout"] == "BLOCKED" and short["blockedReasons"][-1] == "SERIES_HISTORY_TOO_SHORT"
    assert short["reference"]["basis"] == "naturalSurface"

    erie = c["Lake Erie|OH"]
    assert erie["shiftPossible"] and erie["reference"]["basis"] == "lowWaterDatum" and erie["reference"]["poolFt"] == 569.2
    assert erie["reference"]["datum"] == "IGLD85" and erie["levelSource"]["datum"] == "IGLD85" and erie["datum"]["status"] == "SAME_DATUM"
    assert erie["rollout"] == "MEDIUM_CONFIDENCE"
    assert summary["referenceBasis"] == {"fullPool": 1, "seriesMedian": 1, "lowWaterDatum": 1}


def test_cwms_guard_compares_the_parameter_segment():
    live = {"provider": "cwms", "station": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS"}
    assert history_is_live_series(_b(live, {"kind": "cwmsDaily", "office": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS"}))
    assert not history_is_live_series(_b(live, {"kind": "cwmsDaily", "office": "SAS", "series": "Hartwell.Elev-GC.Inst.1Day.0.ARCHIVE-DAILY"}))
    assert not history_is_live_series(_b(live, {"kind": "cwmsDaily", "office": "SAS", "series": "Hartwell"}))


def test_pilot_copy_matches_lakes_hand_written_rows():
    """LAKE_PILOT_BINDINGS restates Lake's hand-written pilots as data; this reads Lake's source text so the copy cannot drift silently."""
    import os
    import re
    from depth_research.candidates import LAKE_PILOT_BINDINGS
    from depth_research.paths import REPO
    src = open(os.path.join(REPO, "brains", "lake", "runtime", "LakeBrain", "LakeSourceBindings.swift"), encoding="utf-8").read()
    body = src[src.index("static let handWritten"):src.index("public static let pilots")]
    parsed = {}
    for lid, loc in re.findall(r'tvaPilot\("([^"]+)",\s*"([^"]+)"', body):
        parsed[lid] = {"live": [{"provider": "tva", "station": loc, "series": None}],
                       "history": [{"kind": "sharedTVAArchive", "locationId": loc}, {"kind": "tvaOperatingGuide", "locationId": loc}]}
    fn = src[src.index("private static func tvaPilot"):src.index("static let handWritten")]   # the TVA row shape the copy assumes
    assert re.search(r"live:\s*\[LevelSeriesRef\(provider:\s*\.tva,[^\]]*station:\s*loc,\s*series:\s*nil", fn)
    assert re.search(r"history:\s*\[\.sharedTVAArchive\([^)]*locationId:\s*loc\),\s*\.tvaOperatingGuide\(locationId:\s*loc\)\]", fn)
    for m in re.finditer(r'LakeSourceBinding\(\s*lakeId:\s*"([^"]+)"(.*?)reviewedAt:', body, re.S):
        lid, row = m.group(1), m.group(2)
        live0 = re.search(r'live:\s*\[\s*LevelSeriesRef\(provider:\s*\.(\w+),.*?station:\s*"([^"]*)",\s*series:\s*"([^"]*)"', row, re.S)
        hist = re.search(r"history:\s*\[(.*?)\],\s*guide:", row, re.S).group(1)
        entries = re.findall(r"\.(\w+)\(([^)]*)\)", hist)
        parsed[lid] = {"live": [{"provider": live0.group(1), "station": live0.group(2), "series": live0.group(3)}],
                       "history": [{"kind": k, **dict(re.findall(r'(\w+):\s*"([^"]*)"', args))} for k, args in entries]}
    assert len(parsed) == 5
    assert parsed == LAKE_PILOT_BINDINGS
