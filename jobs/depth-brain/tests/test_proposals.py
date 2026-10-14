import copy
import json
import os

import pytest
from depth_brain import proposals as P

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = json.load(open(os.path.join(HERE, "depth_brain", "data", "candidates.json")))
BLOCKED = [c["lakeId"] for c in MAN["candidates"] if not c["shiftPossible"] and c["levelSource"]["status"] != "NONE"]
OK_LAKE = next(c["lakeId"] for c in MAN["candidates"] if c["shiftPossible"])
BY = {c["lakeId"]: c for c in MAN["candidates"]}
EV = [{"url": "https://cwms-data.usace.army.mil/cwms-data/locations/X", "says": "NGVD29"}]


def rec(**kw):
    r = {"decision": "SAME_DATUM", "levelDatum": "NGVD29", "referenceDatum": "NGVD29", "sigmaFt": 0.15, "method": "hartwell-pairing", "confidence": "high",
         "offsetStats": {"n": 35, "meanFt": -0.12, "sdFt": 0.06, "minFt": -0.22, "maxFt": 0.07, "window": "x"}, "summary": "s", "evidence": EV}
    r.update(kw)
    return r


def ok(r, lid=None):
    return P.validate_pairing(lid or BLOCKED[0], r, BY)


def test_good_pairing_accepted():
    assert ok(rec())[0]


@pytest.mark.parametrize("change,why", [
    ({"decision": "UNKNOWN"}, "promotable"), ({"decision": "INCOMPATIBLE"}, "promotable"), ({"evidence": []}, "evidence"),
    ({"evidence": [{"url": "not-a-url"}]}, "evidence"), ({"confidence": "low"}, "confidence"), ({"method": "vibes"}, "method"),
    ({"sigmaFt": 0.05}, "sigma"), ({"sigmaFt": None}, "sigma"), ({"levelDatum": "NAVD88"}, "identical"), ({"levelDatum": "LOCAL", "referenceDatum": "LOCAL"}, "identical"),
    ({"levelDatum": None}, "identical"),
])
def test_bad_pairings_rejected(change, why):
    good, reason = ok(rec(**change))
    assert not good and why in reason


def test_pairing_statistics_gate():
    assert not ok(rec(offsetStats={"n": 10, "meanFt": 0.0, "sdFt": 0.05}))[0]                 # too few
    assert not ok(rec(offsetStats={"n": 50, "meanFt": -0.5, "sdFt": 0.05}))[0]                # looks like a datum shift
    assert not ok(rec(offsetStats={"n": 50, "meanFt": 0.0, "sdFt": 0.4}))[0]                  # too noisy
    assert not ok(rec(sigmaFt=0.15, offsetStats={"n": 50, "meanFt": -0.3, "sdFt": 0.05}))[0]  # sigma < offset
    assert ok(rec(sigmaFt=0.3, offsetStats={"n": 50, "meanFt": -0.3, "sdFt": 0.05}))[0]
    assert not ok(rec(offsetStats=None))[0]


def test_already_defensible_or_unknown_lake_rejected():
    assert not P.validate_pairing(OK_LAKE, rec(), BY)[0]
    assert not P.validate_pairing("No Such Lake|XX", rec(), BY)[0]


def test_same_source_may_be_local_but_same_datum_may_not():
    r = rec(decision="SAME_SOURCE", levelDatum="LOCAL", referenceDatum="LOCAL", method="cwms-location", offsetStats=None)
    assert ok(r)[0]


def test_provider_rule_validation():
    rule = {"provider": "x", "scope": "s", "decision": "SAME_DATUM", "levelDatum": "NGVD29", "referenceDatum": "NGVD29", "sigmaFt": 0.15, "lakes": BLOCKED[:3], "evidence": EV}
    assert P.validate_provider_rule(rule, BY)[0] and P.validate_provider_rule(rule, BY)[2] == BLOCKED[:3]
    for bad in ({"decision": "BLOCKED"}, {"evidence": []}, {"levelDatum": "NAVD88"}, {"sigmaFt": 0.01}, {"lakes": [OK_LAKE]}, {"lakes": []}):
        assert not P.validate_provider_rule({**rule, **bad}, BY)[0]


def test_plan_and_promote_do_not_overwrite_and_stamp_provenance(tmp_path):
    d = tmp_path / "p"; d.mkdir()
    (d / "datum_pairings.json").write_text(json.dumps({"lakes": {BLOCKED[0]: rec(), BLOCKED[1]: rec(decision="UNKNOWN"), OK_LAKE: rec()}}))
    ovp = tmp_path / "ov.json"; ovp.write_text(json.dumps({BLOCKED[0]: {"status": "SAME_DATUM", "sigmaFt": 0.15, "summary": "existing"}}))
    r = P.promote(MAN, str(ovp), apply=True, proposals_dir=str(d))
    assert list(r["accepted"]) == [BLOCKED[0]] and len(r["rejected"]) == 2 and r["newOverrides"] == 0
    assert json.load(open(ovp))[BLOCKED[0]]["summary"] == "existing"                      # reviewed record never overwritten
    ovp.write_text("{}")
    r2 = P.promote(MAN, str(ovp), apply=True, proposals_dir=str(d))
    saved = json.load(open(ovp))[BLOCKED[0]]
    assert saved["promotedFrom"].endswith("datum_pairings.json") and saved["rulesVersion"] == P.RULES_VERSION


def test_twdb_requires_verified_pool_datum_evidence_and_a_passed_validation(tmp_path):
    base = {"referenceStatus": "VERIFIED", "referencePoolFt": 617.0, "referencePoolDatum": "NGVD29", "surveyYear": 2017, "evidence": EV, "validation": {"passed": True}}
    f = tmp_path / "t.json"
    def run(**kw):
        f.write_text(json.dumps({"lakes": {"Lake X|TX": {**base, **kw}}})); return P.twdb_updates(str(f))
    assert "Lake X|TX" in run()
    for bad in ({"referenceStatus": "UNVERIFIED"}, {"referencePoolFt": None}, {"referencePoolDatum": None}, {"evidence": []},
                {"validation": {"passed": False}}, {"validation": {"passed": None}}, {"validation": {}}):
        assert run(**bad) == {}


def test_gitted_proposal_rules_are_the_strict_ones():
    assert (P.PAIRING_MIN_N, P.PAIRING_MAX_ABS_MEAN_FT, P.PAIRING_MAX_SD_FT, P.ALLOWED_SIGMA_MIN) == (20, 0.35, 0.25, 0.1)


def test_same_source_may_have_zero_sigma_but_same_datum_may_not():
    ss = rec(decision="SAME_SOURCE", method="cwms-location", sigmaFt=0.0, offsetStats=None, levelDatum="LOCAL (CWMS location datum unnamed)", referenceDatum="LOCAL (same CWMS location)")
    assert ok(ss)[0]
    assert not ok(rec(sigmaFt=0.0))[0]                                        # SAME_DATUM keeps the 0.1 floor
    assert not ok(rec(decision="SAME_SOURCE", method="cwms-location", sigmaFt=-0.1, offsetStats=None))[0]
    bad = rec(decision="SAME_SOURCE", method="cwms-location", sigmaFt=0.0, offsetStats=None, levelDatum="NGVD29", referenceDatum="NAVD88")
    assert not ok(bad)[0]                                                      # internally inconsistent


def test_verbose_datum_strings_are_reduced_to_their_token_and_stats_still_gate():
    assert P.datum_token("NGVD29 (USGS 62614 by parameter definition)") == "NGVD29"
    assert P.datum_token("LOCAL (same CWMS location)") == "LOCAL" and P.datum_token("weird text") is None
    r = rec(levelDatum="NGVD29 (00062 series; numerically equal to CWMS NGVD29 pool series)")
    assert ok(r)[0]
    assert not ok({**r, "offsetStats": {"n": 5, "meanFt": 0.0, "sdFt": 0.05}})[0]


def test_provider_rules_need_explicit_lead_acceptance(tmp_path):
    d = tmp_path / "p"; d.mkdir()
    rule = {"provider": "x", "scope": "Some scope", "decision": "SAME_DATUM", "levelDatum": "NAVD88", "referenceDatum": "NAVD88", "sigmaFt": 0.1, "lakes": BLOCKED[:2], "evidence": EV}
    (d / "provider_rules.json").write_text(json.dumps({"rules": [rule]}))
    r = P.plan(MAN, str(d))
    assert r["accepted"] == {} and "not accepted by lead" in r["rejected"][0]["reason"]
    (d / "accepted_provider_rules.json").write_text(json.dumps({"accepted": [{"provider": "x", "decision": "SAME_DATUM", "scopeStartsWith": "Some", "confidence": "high"}]}))
    r2 = P.plan(MAN, str(d))
    assert set(r2["accepted"]) == set(BLOCKED[:2]) and r2["accepted"][BLOCKED[0]]["status"] == "SAME_DATUM"
    (d / "accepted_provider_rules.json").write_text(json.dumps({"accepted": [{"provider": "x", "decision": "SAME_DATUM", "scopeStartsWith": "Some", "asStatus": "SAME_SOURCE", "confidence": "medium"}]}))
    r3 = P.plan(MAN, str(d))
    assert r3["accepted"][BLOCKED[0]]["status"] == "SAME_SOURCE" and r3["accepted"][BLOCKED[0]]["confidence"] == "medium"


def test_acceptance_never_relaxes_evidence_or_sigma(tmp_path):
    d = tmp_path / "p"; d.mkdir()
    (d / "accepted_provider_rules.json").write_text(json.dumps({"accepted": [{"provider": "x", "decision": "SAME_DATUM", "scopeStartsWith": "S", "asStatus": "SAME_SOURCE"}]}))
    for bad in ({"evidence": []}, {"sigmaFt": 0.01}, {"lakes": [OK_LAKE]}):
        rule = {"provider": "x", "scope": "S", "decision": "SAME_DATUM", "levelDatum": "LOCAL", "referenceDatum": "LOCAL", "sigmaFt": 0.1, "lakes": BLOCKED[:1], "evidence": EV, **bad}
        (d / "provider_rules.json").write_text(json.dumps({"rules": [rule]}))
        assert P.plan(MAN, str(d))["accepted"] == {}


def test_held_rules_are_not_in_the_accepted_file_as_promotable():
    acc = json.load(open(os.path.join(HERE, "depth_brain", "data", "proposals", "accepted_provider_rules.json")))
    assert {a["provider"] for a in acc["accepted"]} == {"sjrwmd", "srp", "nipsco", "tva"}
    assert {h["provider"] for h in acc["heldWithReason"]} == {"rise", "nwps", "duke"}


def test_held_pairings_are_not_promoted_and_usgs_d_datum_must_match_site(tmp_path):
    d = tmp_path / "p"; d.mkdir()
    (d / "datum_pairings.json").write_text(json.dumps({"lakes": {BLOCKED[0]: rec(), BLOCKED[1]: rec()}}))
    (d / "held_pairings.json").write_text(json.dumps({"held": {BLOCKED[0]: "reason"}}))
    r = P.plan(MAN, str(d))
    assert BLOCKED[0] not in r["accepted"] and BLOCKED[1] in r["accepted"]
    assert any("held by lead review" in x["reason"] for x in r["rejected"])


def test_repo_held_list_and_usgs_d_site_datums_exist():
    h = json.load(open(os.path.join(HERE, "depth_brain", "data", "proposals", "held_pairings.json")))["held"]
    assert {"Henrys Lake|ID", "C.J. Strike Reservoir|ID", "Lake McConaughy|NE", "Lake Winnipesaukee|NH", "Roosevelt|AZ"} <= set(h)
    sites = json.load(open(os.path.join(HERE, "depth_brain", "data", "usgs_d_site_datums.json")))["lakes"]
    assert sites["Henrys Lake|ID"]["altDatumCd"] == "NAVD88" and sites["C.J. Strike Reservoir|ID"]["altDatumCd"] == "NAVD88"


def test_non_twdb_contour_proposals_cannot_enable_effective_zones_until_validation_passes():
    path = os.path.join(HERE, "depth_brain", "data", "proposals", "contour_reference_pools.json")
    d = json.load(open(path))
    assert any(v.get("referenceStatus") == "VERIFIED" for v in d["lakes"].values())                # reference pools exist for some lakes ...
    assert P.twdb_updates(path) == {}                                                                # ... but none passed the preregistered validation
    assert all((v.get("validation") or {}).get("passed") is not True for v in d["lakes"].values())
    assert not any(c.get("referenceZones", {}).get("kind", "contour") == "contour" and c.get("referenceZones", {}).get("referenceStatus") == "VERIFIED" and "TWDB" not in c["evidence"]["contourSources"] for c in MAN["candidates"])
