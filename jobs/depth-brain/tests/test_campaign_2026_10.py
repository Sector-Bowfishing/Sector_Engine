"""Regression tests for the long-run campaign: pool-confidence vocabulary and the RISE independent-gauge pairing."""
import json
import os

from depth_brain import contract as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = {c["lakeId"]: c for c in json.load(open(os.path.join(HERE, "depth_brain", "data", "candidates.json")))["candidates"]}
DIRECTORY = json.load(open(os.path.join(HERE, "depth_brain", "data", "inputs", "directory_lakes_2026-10-13.json")))["lakes"]


def test_directory_med_is_medium_not_low():
    assert C.norm_pool_conf("med") == "medium" and C.norm_pool_conf("high") == "high" and C.norm_pool_conf("low") == "low" and C.norm_pool_conf(None) is None
    for lk in DIRECTORY:
        if lk.get("poolConfidence") == "med" and lk["id"] in MAN:
            assert MAN[lk["id"]]["reference"]["confidence"] == "medium"          # the producer's vocabulary never leaks into the manifest
            assert "REFERENCE_POOL_CONFIDENCE_LOW" not in MAN[lk["id"]]["blockedReasons"]


def test_low_pool_confidence_still_blocks():
    lows = [c for c in MAN.values() if c["reference"].get("confidence") == "low"]
    assert lows and all(not c["shiftPossible"] for c in lows)


def test_medium_pool_never_high_confidence_rollout():
    for c in MAN.values():
        if c["reference"].get("confidence") == "medium":
            assert c["rollout"] != "HIGH_CONFIDENCE"


def test_cheney_unlocked_by_independent_gauge_pairing_not_by_assumption():
    c = MAN["Cheney Reservoir|KS"]
    assert c["shiftPossible"] and c["datum"]["status"] == "SAME_DATUM"
    assert c["datum"]["sigmaFt"] >= 0.15
    p = json.load(open(os.path.join(HERE, "depth_brain", "data", "proposals", "datum_pairings_3.json")))["lakes"]["Cheney Reservoir|KS"]
    assert p["offsetStats"]["n"] >= 20 and abs(p["offsetStats"]["meanFt"]) <= 0.35 and p["offsetStats"]["sdFt"] <= 0.25


RISE_UNLOCKED = {"Cheney Reservoir|KS", "Bighorn Lake|WY", "El Vado Lake|NM", "Elephant Butte Reservoir|NM", "Heron Lake|NM", "Navajo Reservoir|NM", "Swanson Reservoir|NE",
                 "Patterson Lake|ND", "Lake Tschida|ND", "Calamus Reservoir|NE",
                 "Angostura Reservoir|SD", "Boysen Reservoir|WY", "Fresno Reservoir|MT", "Keyhole Reservoir|WY", "Merritt Reservoir|NE", "Pactola Reservoir|SD", "Pathfinder Reservoir|WY"}


def test_only_rise_lakes_with_an_established_datum_chain_are_unlocked():
    rise = [c for c in MAN.values() if c["levelSource"].get("provider") == "rise"]
    assert rise
    for c in rise:
        assert (c["datum"]["status"] != "UNKNOWN") == (c["lakeId"] in RISE_UNLOCKED), c["lakeId"]


def test_every_unlocked_reclamation_lake_has_a_passing_storage_link_fit():
    link = json.load(open(os.path.join(HERE, "..", "..", "docs", "brains", "depth", "data", "rise_storage_link.json")))["results"]
    prop = json.load(open(os.path.join(HERE, "depth_brain", "data", "proposals", "datum_pairings_5.json")))["lakes"]
    assert len(prop) == 9
    for lid in prop:
        r = link[lid]
        assert r["passes"] and abs(r["bestOffsetFt"]) <= 0.10 and r["relRmsAtBest"] <= 0.005 and r["n"] >= 300, lid
    for lid in ("Flaming Gorge Reservoir|UT", "Jamestown Reservoir|ND", "Blue Mesa Reservoir|CO"):
        assert not link[lid]["passes"] and MAN[lid]["datum"]["status"] == "UNKNOWN", lid          # inconclusive fits unlock nothing


def test_every_diagram_unlocked_reclamation_lake_has_its_pool_on_the_diagram_and_a_passing_fit():
    link = json.load(open(os.path.join(HERE, "..", "..", "docs", "brains", "depth", "data", "rise_diagram_link.json")))["results"]
    prop = json.load(open(os.path.join(HERE, "depth_brain", "data", "proposals", "datum_pairings_6.json")))["lakes"]
    assert len(prop) == 7
    for lid in prop:
        r = link[lid]
        used = [p for p in r["pairs"] if "dEFt" in p]
        assert r["passes"] and used and all(abs(p["dEFt"]) <= 0.10 for p in used), lid
        assert MAN[lid]["reference"]["source"].startswith("https://www.usbr.gov/gp/aop/resaloc/"), lid
    for lid, r in link.items():                                    # the method must reproduce the lakes whose frame the survey tables already settled
        if r["control"]:
            assert r["passes"] or not any("dEFt" in p for p in r["pairs"]), lid
    assert link["Jamestown Reservoir|ND"]["passes"] is False       # a recent 0.145 ft disagreement is not waved through


# ---- Duke: two documented frames for one lake ----------------------------------------------------------------
from datetime import timedelta
from depth_brain.shift import ReferencePool, compute_shift, LevelObservation
from depth_brain.datum import DatumAssessment
from helpers import NOW


def _norman(level):
    ref = ReferencePool(pool_ft=760.0, basis="fullPool", confidence="high", datum="NGVD29", datum_verified=True, relative_scale_pool=100.0,
                        assessment=DatumAssessment("SAME_SOURCE", 0.1, 0.0, []))
    lv = LevelObservation(level, "ft", None, NOW - timedelta(hours=1), "DIRECT_LAKE_GAUGE", "OBSERVED")
    return compute_shift(lv, ref, NOW)


def test_duke_relative_scale_shift_is_scale_minus_100():
    r = _norman(98.5)
    assert r.mode == "shiftOnly" and abs(r.shift_ft - (-1.5)) < 1e-9 and "levelFrame:relativeScale100" in r.flags


def test_duke_absolute_frame_gives_the_same_shift():
    r = _norman(758.5)
    assert r.mode == "shiftOnly" and abs(r.shift_ft - (-1.5)) < 1e-9 and "levelFrame:relativeScale100" not in r.flags


def test_duke_value_in_neither_frame_is_refused():
    r = _norman(430.0)
    assert r.mode == "unknown" and r.reasons == ["IMPLAUSIBLE_SHIFT"]


def test_duke_lakes_in_manifest_carry_frame_and_cap_at_medium():
    duke = [c for c in MAN.values() if c["levelSource"].get("provider") == "duke"]
    assert len(duke) == 8 and all(c["shiftPossible"] and c["rollout"] == "MEDIUM_CONFIDENCE" for c in duke)
    assert sum(1 for c in duke if c["reference"].get("relativeScalePoolFt") == 100.0) == 7
    assert MAN["Lake Robinson|SC"]["levelSource"]["scale"] == "ABSOLUTE_FT" and "relativeScalePoolFt" not in MAN["Lake Robinson|SC"]["reference"]


def test_non_duke_lake_without_frame_is_unaffected():
    ref = ReferencePool(pool_ft=760.0, basis="fullPool", confidence="high", datum="NGVD29", datum_verified=True, assessment=DatumAssessment("SAME_SOURCE", 0.1, 0.0, []))
    lv = LevelObservation(98.5, "ft", None, NOW - timedelta(hours=1), "DIRECT_LAKE_GAUGE", "OBSERVED")
    assert compute_shift(lv, ref, NOW).reasons == ["IMPLAUSIBLE_SHIFT"]


def test_lake_delta_cross_check_is_skipped_on_the_relative_scale_but_kept_on_absolute_levels():
    ref = ReferencePool(pool_ft=760.0, basis="fullPool", confidence="high", datum="NGVD29", datum_verified=True, relative_scale_pool=100.0, assessment=DatumAssessment("SAME_SOURCE", 0.1, 0.0, []))
    rel = LevelObservation(98.5, "ft", None, NOW - timedelta(hours=1), "DIRECT_LAKE_GAUGE", "OBSERVED", lake_difference_ft=-661.5)      # Lake's number is against the absolute pool
    assert not any(f.startswith("lakeBrainDeltaDisagrees") for f in compute_shift(rel, ref, NOW).flags)
    ab = LevelObservation(758.5, "ft", None, NOW - timedelta(hours=1), "DIRECT_LAKE_GAUGE", "OBSERVED", lake_difference_ft=-5.0)
    assert any(f.startswith("lakeBrainDeltaDisagrees") for f in compute_shift(ab, ref, NOW).flags)
