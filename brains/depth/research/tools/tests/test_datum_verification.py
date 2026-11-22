"""Datum verification records (records/datum_verification.json) and how the manifest builder consumes them. Runs on committed files only."""
import copy
import json

import pytest
from conftest import MANIFEST_PATH

from depth_brain import contract as C
from depth_research.candidates import (VERIFICATION_RECORDS, assess_candidate, load_datum_verification, load_provider_table,
                                       verification_problems, verified_conversion, verified_same_source)

RECORDS = load_datum_verification()
TABLE = load_provider_table()
CANDS = {c["lakeId"]: c for c in json.load(open(MANIFEST_PATH))["candidates"]}
TOLEDO = "Toledo Bend Reservoir|TX"
PERCY = "Percy Priest Lake|TN"


def usgs(param):
    return {"provider": "usgs", "series_or_param": param, "capability_class": "DIRECT_LAKE_GAUGE"}


def test_every_record_satisfies_the_verification_rule():
    assert RECORDS, f"{VERIFICATION_RECORDS} missing or empty"
    for lid, rec in RECORDS.items():
        assert lid in CANDS, f"{lid} is not a manifest lake"
        assert verification_problems(lid, rec) == [], (lid, verification_problems(lid, rec))
        assert rec["status"] in ("VERIFIED", "SAME_SOURCE", "SINGLE_SOURCE", "CONFLICT", "NONE")


def test_only_verified_converted_records_enable_a_conversion():
    enabled = {lid for lid, rec in RECORDS.items() if verified_conversion(rec)}
    assert enabled == {TOLEDO}


def test_toledo_bend_conversion_with_verified_inputs():
    """The same lake with both datums verified as the manifest records them (NAVD88 level by parameter, NGVD29 pool)."""
    table = {"providers": {}, "referencePoolSources": {"waterdatafortexas.org": {"datum": "NGVD29", "basis": "verified_doc"}}}
    a = assess_candidate(TOLEDO, {}, usgs("62615"), "https://www.waterdatafortexas.org/reservoirs/individual/toledo-bend", table, {}, {}, None, RECORDS)[0]
    assert a.status == "CONVERTED" and a.conversion_ft == pytest.approx(0.2) and a.sigma_ft > 0
    # without the record it stays INCOMPATIBLE: never converted silently
    assert assess_candidate(TOLEDO, {}, usgs("62615"), "https://www.waterdatafortexas.org/x", table, {}, {})[0].status == "INCOMPATIBLE"
    # a record for a different lake does not leak
    assert assess_candidate("Other|TX", {}, usgs("62615"), "https://www.waterdatafortexas.org/x", table, {}, {}, None, RECORDS)[0].status == "INCOMPATIBLE"


def test_offset_outside_vdatum_tolerance_or_one_publisher_blocks_conversion():
    rec = copy.deepcopy(RECORDS[TOLEDO])
    rec["relationship"]["vdatumCheckFt"] = -0.35
    assert verified_conversion(rec) is None and verification_problems(TOLEDO, rec)
    rec = copy.deepcopy(RECORDS[TOLEDO])
    rec["sides"]["reference"]["evidence"] = rec["sides"]["reference"]["evidence"][:1]
    assert verified_conversion(rec) is None
    rec = copy.deepcopy(RECORDS[TOLEDO])
    rec["relationship"]["empirical"]["passed"] = False
    assert verified_conversion(rec) is None
    rec = copy.deepcopy(RECORDS[TOLEDO])
    rec["passes"] = 3
    assert verified_conversion(rec) is None


def test_conflict_and_single_source_never_carry_a_relationship():
    for lid, rec in RECORDS.items():
        if rec["status"] not in ("VERIFIED", "SAME_SOURCE"):
            assert not (rec.get("relationship") or {}).get("status"), lid
    assert RECORDS["Cross Lake|LA"]["status"] == "CONFLICT" and RECORDS["Cross Lake|LA"]["conflict"]


def test_toledo_bend_level_basis_is_recorded_as_owner_accepted():
    lvl = RECORDS[TOLEDO]["sides"]["level"]
    assert lvl["basis"] == "parameter-definition+empirical" and "owner" in lvl["basisDecision"]


def test_percy_priest_pool_and_level_are_one_cwms_record():
    sr = verified_same_source(RECORDS[PERCY])
    assert sr and sr["referencePoolFt"] == 490.5 and sr["location"] == "JPHT1"
    a2w = {"provider": "a2w", "series_or_param": "Elev-Pool", "capability_class": "DIRECT_OPERATOR_POOL"}
    out = assess_candidate(PERCY, {}, a2w, "USACE published pool, inside TVA summer zone 489.5-490.5 (JPHT1)", TABLE, {}, {}, None, RECORDS)
    a, rd, rd_ver = out[0], out[4], out[5]
    assert a.status == "SAME_SOURCE" and a.usable and a.sigma_ft == C.SIGMA_DATUM["SAME_SOURCE"]
    assert (rd, rd_ver) == ("NGVD29", True) and a.evidence_urls == ["https://cwms-data.usace.army.mil/cwms-data/locations/JPHT1?office=LRN"]
    # without the record the lake stays unknown (no silent same-source)
    assert assess_candidate(PERCY, {}, a2w, "USACE published pool, inside TVA summer zone 489.5-490.5 (JPHT1)", TABLE, {}, {})[0].status == "UNKNOWN"


def test_same_source_record_needs_one_location_and_an_owner_decision():
    rec = copy.deepcopy(RECORDS[PERCY])
    rec["sameRecord"]["referenceLevelId"] = "OTHER.Elev.Inst.0.Bottom of Flood"
    assert verified_same_source(rec) is None
    rec = copy.deepcopy(RECORDS[PERCY])
    rec["sameRecord"]["ownerDecision"] = ""
    assert verified_same_source(rec) is None


def test_ross_barnett_stays_unconverted():
    rec = RECORDS["Ross Barnett Reservoir|MS"]
    assert rec["status"] == "SINGLE_SOURCE" and verified_conversion(rec) is None and verified_same_source(rec) is None
