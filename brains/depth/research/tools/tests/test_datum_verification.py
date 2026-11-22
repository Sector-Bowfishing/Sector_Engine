"""Datum verification records (records/datum_verification.json) and how the manifest builder consumes them. Runs on committed files only."""
import copy
import json
from datetime import timedelta

import pytest
from conftest import MANIFEST_PATH

from depth_brain import contract as C
from depth_brain.datum import DatumAssessment
from depth_brain.shift import LevelObservation, ReferencePool, compute_shift
from depth_research.candidates import (SINGLE_OFFICIAL, SINGLE_OFFICIAL_LABEL, VERIFICATION_RECORDS, assess_candidate, empirical_problems,
                                       is_official_root, root_key, live_source_location, load_datum_verification,
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


SRA = "Sabine River Authority (TX/LA)"
USGS_SITE = "https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=08025350&siteOutput=expanded"


def single_official():
    """Synthetic qualifying record: Toledo Bend with a pool-side empirical check that does NOT exist today (corroborates includes 'reference'),
    and only official-host evidence on the reference side."""
    rec = copy.deepcopy(RECORDS[TOLEDO])
    rec["relationship"] = {**copy.deepcopy(rec["conversionCandidate"]), "status": "CONVERTED"}
    rec["relationship"]["empirical"]["corroborates"] = ["level", "reference"]
    ref = rec["sides"]["reference"]
    ref["status"] = SINGLE_OFFICIAL
    ref["evidence"] = [e for e in ref["evidence"] if "usgs.gov" in e["url"] or "noaa.gov" in e["url"]]
    rec.update(status=SINGLE_OFFICIAL, singleOfficialSource=True, label=SINGLE_OFFICIAL_LABEL)
    return rec


def convert(rec, operator=SRA):
    return assess_candidate(TOLEDO, {"operatorName": operator}, usgs("62615"), TWDB_SRC, NGVD_POOL_TABLE, {}, {}, None, {TOLEDO: rec})[0]


# ── the committed records ─────────────────────────────────────────────────────────────────────────────────
def test_every_record_satisfies_the_verification_rule():
    assert RECORDS, f"{VERIFICATION_RECORDS} missing or empty"
    for lid, rec in RECORDS.items():
        assert lid in CANDS, f"{lid} is not a manifest lake"
        assert verification_problems(lid, rec, CANDS[lid].get("operator")) == [], (lid, verification_problems(lid, rec, CANDS[lid].get("operator")))


def test_no_committed_record_enables_a_conversion_or_claims_single_official():
    assert {lid for lid, rec in RECORDS.items() if verified_conversion(rec, CANDS[lid].get("operator"))} == set()
    assert not any(rec["status"] == SINGLE_OFFICIAL for rec in RECORDS.values())


def test_toledo_bend_stays_off_because_no_check_corroborates_the_pool_datum():
    rec = RECORDS[TOLEDO]
    assert rec["status"] == "SINGLE_SOURCE" and not rec["relationship"]["status"]
    emp = rec["conversionCandidate"]["empirical"]
    assert emp["corroborates"] == ["level"] and "pool" in emp["scope"]
    assert empirical_problems(emp, rec["conversionCandidate"]) == []          # the level-side check itself passes against the -0.2 ft conversion
    vd = {**emp, "expectedFt": -0.285}
    assert any("2 SE" in x for x in empirical_problems(vd, rec["conversionCandidate"]))   # against VDatum it would not
    assert convert(rec).status == "INCOMPATIBLE"
    as_single = copy.deepcopy(rec)                                                         # labelling it single-official today is refused
    as_single["relationship"] = {**as_single["conversionCandidate"], "status": "CONVERTED"}
    as_single["sides"]["reference"]["status"] = SINGLE_OFFICIAL
    as_single.update(status=SINGLE_OFFICIAL, singleOfficialSource=True, label=SINGLE_OFFICIAL_LABEL)
    probs = verification_problems(TOLEDO, as_single, SRA)
    assert any("does not corroborate the reference side" in x for x in probs)
    assert any("refused as evidence" in x and "waterdatafortexas" in x for x in probs)


# ── single official source tier, on a synthetic record ───────────────────────────────────────────────────
def test_single_official_qualifies_and_the_label_reaches_the_manifest():
    rec = single_official()
    assert verification_problems(TOLEDO, rec, SRA) == []
    a = convert(rec)
    assert a.status == "CONVERTED" and a.conversion_ft == pytest.approx(0.2)
    d = a.as_dict()
    assert "single-official-source" in d["basis"] and d["evidenceConfidence"] == "medium"
    assert any(r.startswith(SINGLE_OFFICIAL_LABEL) for r in d["reasons"])
    assert any("usgs.gov" in u for u in d["evidenceUrls"]) and len(d["evidenceUrls"]) == 2       # one level-side and one reference-side URL


def test_non_official_root_refused():
    rec = single_official()
    rec["sides"]["reference"]["evidence"].append({"publisher": "TWDB", "url": TWDB_SRC, "quote": "172.00 ft above NGVD29"})
    probs = verification_problems(TOLEDO, rec, SRA)
    assert any("not an official authority" in x for x in probs) and any("refused as evidence" in x for x in probs)
    assert convert(rec).status == "INCOMPATIBLE"


def test_supporting_item_from_a_non_official_host_is_refused():
    rec = single_official()
    rec["sides"]["reference"]["evidence"].append({"publisher": "USGS (reprint)", "url": "https://texashistory.unt.edu/x.pdf", "quote": "q",
                                                  "derivedFrom": "USGS-08025350", "supportingOnly": True})
    assert any("refused as evidence" in x for x in verification_problems(TOLEDO, rec, SRA)) and convert(rec).status == "INCOMPATIBLE"


def test_dam_operator_comes_from_the_directory_not_the_record():
    rec = single_official()
    rec["sides"]["reference"]["evidence"] = [{"publisher": "Sabine River Authority", "url": "https://www.sratx.org/datum.pdf", "quote": "172 ft NGVD 29",
                                              "derivedFrom": f"OPERATOR:{SRA}"}]
    rec["damOperator"] = SRA                                                           # ignored
    assert verification_problems(TOLEDO, rec, SRA) == [] and convert(rec, SRA).status == "CONVERTED"
    assert any("not an official authority" in x for x in verification_problems(TOLEDO, rec, "Someone Else"))
    assert convert(rec, "Someone Else").status == "INCOMPATIBLE" and convert(rec, None).status == "INCOMPATIBLE"
    assert is_official_root("USGS-08025350") and is_official_root("NOAA NWPS") and not is_official_root("USGSX") and not is_official_root("TWDB")


def test_one_agency_is_one_root_even_without_supporting_only():
    rec = verified_toledo()
    rec["sides"]["reference"]["evidence"] = [e for e in rec["sides"]["reference"]["evidence"] if "usgs.gov" in e["url"]]
    for e in rec["sides"]["reference"]["evidence"]:
        e.pop("supportingOnly", None)                                                  # OFR 79-678 (USGS) + USGS-08025350: still one root
    assert {root_key(e.get("derivedFrom") or e["publisher"]) for e in rec["sides"]["reference"]["evidence"]} == {"USGS"}
    assert verified_conversion(rec) is None and any("independent roots" in x for x in verification_problems(TOLEDO, rec))


@pytest.mark.parametrize("mutate,why", [
    (lambda r: r["relationship"]["empirical"].clear(), "missing"),
    (lambda r: r["relationship"]["empirical"].update(passed=False), "flag"),
    (lambda r: r["relationship"]["empirical"].update(expectedFt=-0.05), "expected is not the conversion"),
    (lambda r: r["relationship"]["empirical"].update(expectedFt=0.2), "opposite sign"),
    (lambda r: r["relationship"]["empirical"].update(corroborates=["level"]), "does not corroborate the single-official side"),
    (lambda r: r["relationship"]["empirical"].pop("residualsFt"), "no stored residuals"),
    (lambda r: r["relationship"]["empirical"].update(residualsFt=[0.05, -0.05, 0.02, -0.02, 0.0, 0.04, -0.04, 0.01, -0.01], meanFt=0.0), "no offset detected"),
    (lambda r: r["relationship"]["empirical"].update(toleranceFt=0.5), "tolerance too loose"),
    (lambda r: r["relationship"]["empirical"].update(n=3), "n too small"),
])
def test_single_official_refused_without_a_bound_passing_empirical_check(mutate, why):
    rec = single_official()
    mutate(rec)
    assert verification_problems(TOLEDO, rec, SRA), why
    assert convert(rec).status == "INCOMPATIBLE", why


@pytest.mark.parametrize("mutate,why", [
    (lambda r: r.update(singleOfficialSource=False), "not labelled"),
    (lambda r: r.pop("label"), "no label"),
    (lambda r: r["sides"]["reference"].update(status="VERIFIED"), "no side marked single-official"),
    (lambda r: r["sides"]["reference"].update(datum=None), "unnamed datum"),
    (lambda r: r["relationship"].update(navd88MinusNgvd29Ft=0.05, vdatumCheckFt=0.04), "offset under 0.1 ft is untestable"),
    (lambda r: (r["sides"]["reference"].update(offsetToNAVD88Ft=0.2, vdatumCheckFt=-0.285), r.update(offsetConflict="recorded")), "offsetConflict"),
])
def test_single_official_refused_for_rule_violations(mutate, why):
    rec = single_official()
    mutate(rec)
    assert verification_problems(TOLEDO, rec, SRA), why
    assert verified_conversion(rec, SRA) is None, why


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
        if rec["status"] not in ("VERIFIED", SINGLE_OFFICIAL, "SAME_SOURCE"):
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


def test_expected_offset_is_bound_to_the_conversion_by_value_and_sign():
    emp = copy.deepcopy(RECORDS[TOLEDO]["conversionCandidate"]["empirical"])
    rel = {"navd88MinusNgvd29Ft": -0.2, "vdatumCheckFt": -0.285}
    assert not any("is not the conversion" in x for x in empirical_problems(emp, rel))
    assert any("is not the conversion" in x for x in empirical_problems({**emp, "expectedFt": -0.45}, rel))          # mismatched value
    small = {"navd88MinusNgvd29Ft": 0.04, "vdatumCheckFt": 0.05}
    assert any("is not the conversion" in x for x in empirical_problems({**emp, "expectedFt": -0.04}, small))        # within 0.10 but opposite sign
