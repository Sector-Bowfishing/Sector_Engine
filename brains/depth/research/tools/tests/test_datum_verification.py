"""Datum verification records (records/datum_verification.json) and how the manifest builder consumes them. Runs on committed files only."""
import copy
import json
from datetime import timedelta

import pytest
from conftest import MANIFEST_PATH

from depth_brain import contract as C
from depth_brain.datum import DatumAssessment
from depth_brain.shift import LevelObservation, ReferencePool, compute_shift
from depth_research.candidates import (VERIFICATION_RECORDS, assess_candidate, live_source_location, load_datum_verification,
                                       load_provider_table, reviewed_live_sources, verification_problems, verified_conversion,
                                       verified_same_source)
from tests.helpers import NOW

RECORDS = load_datum_verification()
TABLE = load_provider_table()
LIVE = reviewed_live_sources()
CANDS = {c["lakeId"]: c for c in json.load(open(MANIFEST_PATH))["candidates"]}
TOLEDO = "Toledo Bend Reservoir|TX"
PERCY = "Percy Priest Lake|TN"
TWDB_SRC = "https://www.waterdatafortexas.org/reservoirs/individual/toledo-bend"
NGVD_POOL_TABLE = {"providers": {}, "referencePoolSources": {"waterdatafortexas.org": {"datum": "NGVD29", "basis": "verified_doc"}}}
NAVD_POOL_TABLE = {"providers": {}, "referencePoolSources": {"waterdatafortexas.org": {"datum": "NAVD88", "basis": "verified_doc"}}}
A2W = {"provider": "a2w", "series_or_param": "Elev-Pool", "capability_class": "DIRECT_OPERATOR_POOL"}
PP_SRC = "USACE published pool, inside TVA summer zone 489.5-490.5 (JPHT1)"


def usgs(param):
    return {"provider": "usgs", "series_or_param": param, "capability_class": "DIRECT_LAKE_GAUGE"}


def verified_toledo():
    """Toledo Bend as it WOULD look with a second, independent root on the reference side (synthetic: no such source was found)."""
    rec = copy.deepcopy(RECORDS[TOLEDO])
    rec["sides"]["reference"]["status"] = "VERIFIED"
    rec["sides"]["reference"]["evidence"].append({"publisher": "Operator X", "url": "https://example.org/pool", "quote": "172 ft NGVD 29", "derivedFrom": "operator-survey"})
    rec["status"] = "VERIFIED"
    rec["relationship"] = {**rec["conversionCandidate"], "status": "CONVERTED"}
    return rec


# ── the committed records ─────────────────────────────────────────────────────────────────────────────────
def test_every_record_satisfies_the_verification_rule():
    assert RECORDS, f"{VERIFICATION_RECORDS} missing or empty"
    for lid, rec in RECORDS.items():
        assert lid in CANDS, f"{lid} is not a manifest lake"
        assert verification_problems(lid, rec) == [], (lid, verification_problems(lid, rec))


def test_no_committed_record_enables_a_conversion():
    assert {lid for lid, rec in RECORDS.items() if verified_conversion(rec)} == set()


def test_toledo_bend_reference_has_one_root_so_it_is_single_source():
    rec = RECORDS[TOLEDO]
    ref = rec["sides"]["reference"]
    assert {e["derivedFrom"] for e in ref["evidence"]} == {"USGS-08025350"} and ref["status"] == "SINGLE_SOURCE"
    assert rec["status"] == "SINGLE_SOURCE" and verified_conversion(rec) is None
    assert "owner" in rec["sides"]["level"]["basisDecision"]                       # the level-basis decision stays recorded
    a = assess_candidate(TOLEDO, {}, usgs("62615"), TWDB_SRC, NGVD_POOL_TABLE, {}, {}, None, RECORDS)[0]
    assert a.status == "INCOMPATIBLE"


def test_ross_barnett_stays_unconverted():
    rec = RECORDS["Ross Barnett Reservoir|MS"]
    assert rec["status"] == "SINGLE_SOURCE" and rec["offsetConflict"] and verified_conversion(rec) is None and verified_same_source(rec, LIVE.get("Ross Barnett Reservoir|MS")) is None


def test_carried_forward_citations_are_not_evidence():
    for lid, rec in RECORDS.items():
        for side in rec["sides"].values():
            for e in side.get("evidence") or []:
                if not str(e.get("url", "")).startswith("http"):
                    assert e.get("notEvidence") is True, (lid, e)


def test_only_verified_or_same_source_records_carry_a_relationship():
    for lid, rec in RECORDS.items():
        if rec["status"] not in ("VERIFIED", "SAME_SOURCE"):
            assert not (rec.get("relationship") or {}).get("status"), lid
    assert RECORDS["Cross Lake|LA"]["status"] == "CONFLICT" and RECORDS["Cross Lake|LA"]["conflict"]


# ── the rule, on a synthetic fully verified record ────────────────────────────────────────────────────────
def test_verified_conversion_with_matching_datums():
    recs = {TOLEDO: verified_toledo()}
    assert verification_problems(TOLEDO, recs[TOLEDO]) == []
    a = assess_candidate(TOLEDO, {}, usgs("62615"), TWDB_SRC, NGVD_POOL_TABLE, {}, {}, None, recs)[0]
    assert a.status == "CONVERTED" and a.conversion_ft == pytest.approx(0.2) and a.sigma_ft > 0
    assert assess_candidate(TOLEDO, {}, usgs("62615"), TWDB_SRC, NGVD_POOL_TABLE, {}, {})[0].status == "INCOMPATIBLE"          # no record: never silent
    assert assess_candidate("Other|TX", {}, usgs("62615"), TWDB_SRC, NGVD_POOL_TABLE, {}, {}, None, recs)[0].status == "INCOMPATIBLE"   # no leak


def test_reversed_datums_never_convert():
    """Record says level NAVD88 / pool NGVD29; a manifest with level NGVD29 / pool NAVD88 must not borrow it (the sign would flip)."""
    recs = {TOLEDO: verified_toledo()}
    a = assess_candidate(TOLEDO, {}, usgs("62614"), TWDB_SRC, NAVD_POOL_TABLE, {}, {}, None, recs)[0]
    assert a.status == "INCOMPATIBLE" and not a.usable


def test_two_publishers_with_one_root_count_once():
    rec = verified_toledo()
    rec["sides"]["reference"]["evidence"][-1]["derivedFrom"] = "USGS-08025350"
    assert verified_conversion(rec) is None and any("independent roots" in x for x in verification_problems(TOLEDO, rec))


def test_rule_failures_block_conversion():
    for mutate in (lambda r: r["relationship"].update(vdatumCheckFt=-0.35),
                   lambda r: r["relationship"]["empirical"].update(passed=False),
                   lambda r: r.update(passes=3),
                   lambda r: r["sides"]["reference"].update(evidence=r["sides"]["reference"]["evidence"][:1])):
        rec = verified_toledo()
        mutate(rec)
        assert verified_conversion(rec) is None


def test_side_offset_beyond_conflict_bound_must_be_recorded_and_blocks_verified():
    rec = verified_toledo()
    rec["sides"]["level"].update(offsetToNAVD88Ft=0.1, vdatumCheckFt=-0.285)                 # 0.385 ft apart > 0.25
    probs = verification_problems(TOLEDO, rec)
    assert any("offsetConflict" in x for x in probs) and any("cannot be VERIFIED" in x for x in probs)
    rec["offsetConflict"] = "recorded"
    assert any("cannot be VERIFIED" in x for x in verification_problems(TOLEDO, rec))


def test_a_record_above_none_needs_http_evidence():
    rec = copy.deepcopy(RECORDS["Lay|AL"])
    rec["sides"]["level"]["evidence"] = []
    assert verification_problems("Lay|AL", rec)


# ── Percy Priest: same CWMS record, tied to Lake's live binding ──────────────────────────────────────────
def test_percy_priest_same_source_while_the_live_binding_is_unchanged():
    assert all(live_source_location(s)[2] == "JPHT1" for s in LIVE[PERCY])
    sr = verified_same_source(RECORDS[PERCY], LIVE[PERCY])
    assert sr and sr["referencePoolFt"] == 490.5 and sr["lakeBrainPoolFt"] == 490.0
    out = assess_candidate(PERCY, {}, A2W, PP_SRC, TABLE, {}, {}, None, RECORDS, LIVE)
    assert out[0].status == "SAME_SOURCE" and out[0].sigma_ft == C.SIGMA_DATUM["SAME_SOURCE"] and (out[4], out[5]) == ("NGVD29", True)
    assert assess_candidate(PERCY, {}, A2W, PP_SRC, TABLE, {}, {})[0].status == "UNKNOWN"          # no record -> no silent same-source
    assert assess_candidate(PERCY, {}, A2W, PP_SRC, TABLE, {}, {}, None, RECORDS)[0].status == "UNKNOWN"   # no live binding -> refused


@pytest.mark.parametrize("live", [
    ["a2w:LRN:JPHT1:JPHT1-J_PERCY_PRIEST.Elev-Pool.Inst.1Hour.0.man-rev", "cwms:LRN:JPHT1-J_PERCY_PRIEST.Elev-Pool.Inst.15Minutes.0.dcp-rev", "nwps:JPHT1:HPIRG"],  # provider changed
    ["a2w:LRN:OLDH1:OLDH1-OLD_HICKORY.Elev-Pool.Inst.1Hour.0.man-rev", "cwms:LRN:JPHT1-J_PERCY_PRIEST.Elev-Pool.Inst.15Minutes.0.dcp-rev", "tva:JPHT1"],  # location changed
    ["a2w:LRN:JPHT1:JPHT1-J_PERCY_PRIEST.Elev-Pool.Inst.1Hour.0.man-rev", "cwms:LRN:JPHT1-J_PERCY_PRIEST.Elev-Pool.Inst.15Minutes.0.dcp-rev"],  # fallback dropped
    ["a2w:LRN:JPHT1X:JPHT1X-OTHER.Elev-Pool.Inst.1Hour.0.man-rev", "cwms:LRN:JPHT1-J_PERCY_PRIEST.Elev-Pool.Inst.15Minutes.0.dcp-rev", "tva:JPHT1"],  # prefix is not an exact match
])
def test_percy_priest_refused_when_the_live_binding_changes(live):
    assert verified_same_source(RECORDS[PERCY], live) is None
    assert assess_candidate(PERCY, {}, A2W, PP_SRC, TABLE, {}, {}, None, RECORDS, {PERCY: live})[0].status == "UNKNOWN"


def test_lake_delta_cross_check_is_rebased_on_the_recorded_reference():
    """Lake reports level - 490 (directory pool); Depth's reference is 490.5. With lakeBrainPoolFt the check agrees; without it, it would flag."""
    lvl = LevelObservation(489.0, "ft", None, NOW - timedelta(hours=1), "DIRECT_OPERATOR_POOL", "OBSERVED", -1.0)
    ss = DatumAssessment("SAME_SOURCE", 0.0)
    r = compute_shift(lvl, ReferencePool(490.5, "fullPool", "high", "NGVD29", True, "t", ss, lake_pool_ft=490.0), NOW)
    assert r.shift_ft == pytest.approx(-1.5) and not any(f.startswith("lakeBrainDeltaDisagrees") for f in r.flags)
    r2 = compute_shift(lvl, ReferencePool(490.5, "fullPool", "high", "NGVD29", True, "t", ss), NOW)
    assert any(f.startswith("lakeBrainDeltaDisagrees") for f in r2.flags)
    lvl_bad = LevelObservation(489.0, "ft", None, NOW - timedelta(hours=1), "DIRECT_OPERATOR_POOL", "OBSERVED", -0.2)   # a real disagreement still flags
    r3 = compute_shift(lvl_bad, ReferencePool(490.5, "fullPool", "high", "NGVD29", True, "t", ss, lake_pool_ft=490.0), NOW)
    assert any(f.startswith("lakeBrainDeltaDisagrees") for f in r3.flags)
