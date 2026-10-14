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
                 "Patterson Lake|ND", "Lake Tschida|ND", "Calamus Reservoir|NE"}


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
    for lid in ("Flaming Gorge Reservoir|UT", "Jamestown Reservoir|ND", "Fresno Reservoir|MT", "Blue Mesa Reservoir|CO"):
        assert not link[lid]["passes"] and MAN[lid]["datum"]["status"] == "UNKNOWN", lid          # inconclusive fits unlock nothing
