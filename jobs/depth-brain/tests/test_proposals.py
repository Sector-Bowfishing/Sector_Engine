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
