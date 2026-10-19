"""Wind's three measurements (platform scorer): BI v2 is evidence-based and versioned, certification and BWIS v1 are carried verbatim,
Scientific Confidence and Production Readiness carry no number, and nothing here can move the certification score."""
import copy
import datetime as dt
import json
import os

import pytest

from sector_brain_platform import wind_measurements as W

NOW = dt.datetime(2026, 10, 19, 22, 0, tzinfo=dt.timezone.utc)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FROZEN = json.load(open(os.path.join(ROOT, "docs", "brains", "scoring", "frozen-scores.json")))


@pytest.fixture(scope="module")
def inputs():
    rubric, ev, brain = W.load_all()
    assert ev is not None, "committed evidence file missing"
    return rubric, ev, brain


def m(inputs, ev=None, cert=None):
    rubric, e, brain = inputs
    return W.measurements(copy.deepcopy(cert or FROZEN["wind"]), copy.deepcopy(e if ev is None else ev), rubric, brain, NOW)


def test_certification_score_preserved_verbatim(inputs):
    before = json.dumps(FROZEN["wind"], sort_keys=True)
    out = m(inputs)
    assert out["certification"]["value"] == 3.3 and out["certification"]["scoreVersion"] == "wind-certification-rubric-v1"
    assert json.dumps(FROZEN["wind"], sort_keys=True) == before
    assert out["bowfishingIntelligenceV1"]["value"] == 5.4 and "21e2a326" in out["bowfishingIntelligenceV1"]["definition"]


def test_bi_v2_is_versioned_proposed_and_reproducible(inputs):
    bi = m(inputs)["bowfishingIntelligence"]
    assert bi["scoreVersion"] == "wind-bowfishing-intelligence-v2" and bi["rubricStatus"] == "PROPOSED_PENDING_OWNER_REVIEW"
    assert set(bi["notComparableWith"]) == {"wind-certification-rubric-v1", "bwis-v1"}
    assert round(sum(i["points"] for i in bi["items"].values()), 2) == bi["rawPoints"] and bi["value"] == round(bi["rawPoints"] / 10, 1)
    assert sum(c["max"] for c in bi["categories"].values()) == 100
    s = bi["split"]
    assert s["measuredSkill"]["max"] + s["modelCapability"]["max"] == 100
    assert abs(s["measuredSkill"]["points"] + s["modelCapability"]["points"] - bi["rawPoints"]) < 0.02


def test_bi_v2_current_values(inputs):
    """Pins today's evaluation so any change is deliberate (evidence regenerated, rubric reviewed)."""
    bi = m(inputs)["bowfishingIntelligence"]
    assert bi["value"] == 6.7 and bi["split"]["measuredSkillOnlyView"] == 4.6
    assert bi["items"]["WI4"]["points"] == 0.0              # strong-wind detection: deterministic POD 0
    assert bi["items"]["TI3"]["points"] == 0.0              # no promoted wave memory
    assert bi["items"]["DI1"]["points"] < 4                  # decision accuracy 0.614 symmetric
    assert bi["explanation"]["pathTo7"]["reached"] is False
    assert all(x["class"] == "MEASURED_SKILL" for x in bi["explanation"]["howToImprove"])


def test_field_validation_is_not_in_bi(inputs):
    rubric, _, _ = inputs
    facts = " ".join(str(it.get("fact", "")) for c in rubric["categories"] for it in c["items"])
    assert "field" not in facts and "overwater" not in facts       # no item reads field-validation or over-water evidence
    assert all(it["class"] in ("MEASURED_SKILL", "MODEL_CAPABILITY") for c in rubric["categories"] for it in c["items"])


def test_exploratory_flag_never_credited(inputs):
    _, ev, _ = inputs
    e = copy.deepcopy(ev)
    e["strongWind"]["probabilisticFlag"] = {"status": "EXPLORATORY", "pod": 0.99, "far": 0.01}
    assert m(inputs, e)["bowfishingIntelligence"]["items"]["WI4"]["points"] == 0.0


def test_capability_credit_requires_every_lake(inputs):
    _, ev, _ = inputs
    e = copy.deepcopy(ev)
    del e["scenarios"]["lakes"]["Wilson|AL"]
    bi = m(inputs, e)["bowfishingIntelligence"]
    assert bi["items"]["GI3"]["credit"] == 0.75 and "missing lakes" in bi["items"]["GI3"]["evidence"]
    e = copy.deepcopy(ev)
    e["scenarios"]["lakes"]["Wheeler|AL"]["results"]["S11"] = False
    assert m(inputs, e)["bowfishingIntelligence"]["items"]["DI3"]["credit"] == 0.75


def test_unmeasured_earns_zero(inputs):
    _, ev, _ = inputs
    e = copy.deepcopy(ev)
    e["atmospheric"]["nightSpeedMaeMS"] = None
    e["strongWind"]["observedNight15mphEvents"] = 0
    bi = m(inputs, e)["bowfishingIntelligence"]
    assert bi["items"]["WI1"]["points"] == 0 and bi["items"]["WI4"]["points"] == 0


@pytest.mark.parametrize("mutate,why", [
    (lambda e: e.update(schema="other"), "evidence schema"),
    (lambda e: e["atmospheric"].update(h2Read=True), "H2"),
    (lambda e: e["scenarios"].update(suite="x"), "scenario suite"),
    (lambda e: e["scenarios"].update(evidenceClass="OBSERVED"), "MODEL_CAPABILITY"),
    (lambda e: e.update(note="/Users/someone/Desktop/x"), "local path"),
])
def test_inadmissible_evidence_is_held(inputs, mutate, why):
    _, ev, _ = inputs
    e = copy.deepcopy(ev); mutate(e)
    bi = m(inputs, e)["bowfishingIntelligence"]
    assert bi["value"] is None and bi["basis"] == "HELD" and any(why in x for x in bi["heldBecause"])


def test_scientific_confidence_is_status_not_number(inputs):
    sc = m(inputs)["scientificConfidence"]
    assert sc["value"] is None and sc["basis"] == "EVIDENCE_STATUS" and sc["overall"] == "LIMITED"
    st = {i["id"]: i["status"] for i in sc["items"]}
    assert st["bankExposureField"] == st["surfaceField"] == "NOT_VALIDATED"
    assert st["strongWindForecast"] == "FAILS" and st["strongWindProbabilisticFlag"] == "EXPLORATORY"
    assert st["fetchGeometry"] == "VALIDATED"
    assert sc["certificationScore"]["fieldValidationPoints"] == {"earned": 0.0, "possible": 40}


def test_capability_scenarios_never_count_as_validation(inputs):
    _, ev, _ = inputs
    e = copy.deepcopy(ev)
    for lk in e["scenarios"]["lakes"].values():
        lk["results"] = {k: True for k in lk["results"]}
    sc = m(inputs, e)["scientificConfidence"]
    assert {i["id"]: i["status"] for i in sc["items"]}["bankExposureField"] == "NOT_VALIDATED"


def test_production_readiness_separate_and_gated(inputs):
    pr = m(inputs)["productionReadiness"]
    assert pr["value"] is None and pr["overall"] == "NOT_READY"
    g = {x["gate"]: x for x in pr["gates"]}
    assert g["customerIntegration"]["status"] == "BLOCKED" and g["bowfishingDecisionActivation"]["status"] == "BLOCKED"
    assert "5/30" in g["liveReliability"]["detail"]
    assert "water-clarity -> biological-state -> wind" in g["publisherCutover"]["detail"]


def test_readiness_does_not_leak_into_intelligence(inputs):
    rubric, _, _ = inputs
    ids = {it["id"] for c in rubric["categories"] for it in c["items"]}
    assert not any("reliab" in it["label"].lower() or "uptime" in it["label"].lower() for c in rubric["categories"] for it in c["items"])
    assert len(ids) == 18


def test_envelope_consistency(inputs):
    out = m(inputs)
    assert out["consistency"] == []
    bad = copy.deepcopy(out); bad["bowfishingIntelligence"]["value"] = 9.9
    assert "BI value does not reproduce from raw points" in W.consistency(bad)
    bad = copy.deepcopy(out); bad["scientificConfidence"]["value"] = 5
    assert "scientificConfidence carries a number" in W.consistency(bad)
    bad = copy.deepcopy(out); bad["certification"]["scoreVersion"] = "wind-bowfishing-intelligence-v2"
    assert W.consistency(bad)


def test_rubric_items_have_gaps_where_measured(inputs):
    gaps = {g["id"] for g in json.load(open(W.GAPS_PATH))["gaps"]}
    assert set(W.ITEM_GAP.values()) <= gaps


def test_gaps_file_is_schema_valid():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
    from jsonschema_lite import iter_errors
    schema = json.load(open(os.path.join(ROOT, "contracts", "schemas", "research-gaps.schema.json")))
    assert list(iter_errors(json.load(open(W.GAPS_PATH)), schema)) == []


def test_evidence_has_no_local_paths():
    txt = open(W.EVIDENCE_PATH).read()
    for bad in ("/Users/", "Desktop/", "Library/Caches", "Sector Research"):
        assert bad not in txt
