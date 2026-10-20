"""Fish capability activation prerequisites: decisions need a named human, activation needs every gate case decided, nothing self-approves,
and the readiness report is read-only and truthful. Uses the committed (INACTIVE) publication record; never writes it."""
import copy
import json

import pytest

from sector_brain_platform import fish_capability as fc

PUB = fc.load_json(fc.PUBLICATION_PATH)
RUBRIC = fc.load_json(fc.RUBRIC_PATH)
COHORTS = {v: fc.load_json(p) for v, p in fc.COHORT_FILES.items()}
EV = fc.load_json(fc.EVIDENCE_PATH)
CASES = PUB["referenceCaseReview"]["required"]
T = "2026-10-20T15:00:00Z"


def test_committed_record_is_inactive_and_gated():
    assert PUB["status"] == "INACTIVE" and not PUB["activation"]["approvedBy"] and PUB["referenceCaseReview"]["decisions"] == {}
    assert len(fc.publication_gate(PUB)) == 2 + len(CASES)


@pytest.mark.parametrize("who", ["", "  ", "AI", "Claude Opus", "claude", "Automated reviewer", "review-bot", "LLM", "GPT 5", "Rehearsal", "system"])
def test_automated_or_blank_reviewers_are_refused(who):
    with pytest.raises(ValueError):
        fc.record_review(PUB, CASES[0], "APPROVED", who, T)
    with pytest.raises(ValueError):
        fc.activate(PUB, who, T)


@pytest.mark.parametrize("who", ["Michael Cather", "Dana Abbott", "Kai Bailey"])
def test_human_names_containing_lookalike_letters_are_accepted(who):
    assert fc.record_review(PUB, CASES[0], "APPROVED", who, T)["referenceCaseReview"]["decisions"][CASES[0]]["reviewer"] == who


def test_record_review_only_for_gate_cases_and_real_decisions_and_does_not_mutate():
    before = copy.deepcopy(PUB)
    with pytest.raises(ValueError):
        fc.record_review(PUB, "XX-REF-99", "APPROVED", "Dana Abbott", T)
    with pytest.raises(ValueError):
        fc.record_review(PUB, CASES[0], "MAYBE", "Dana Abbott", T)
    new = fc.record_review(PUB, CASES[1], "REJECTED", "Dana Abbott", T, note="season bound too wide")
    assert new["referenceCaseReview"]["decisions"][CASES[1]] == {"decision": "REJECTED", "reviewer": "Dana Abbott", "reviewedAt": T,
                                                                "note": "season bound too wide"}
    assert new["status"] == "INACTIVE" and PUB == before


def test_activation_refused_until_every_case_is_decided_then_gate_passes():
    p = PUB
    for c in CASES[:-1]:
        p = fc.record_review(p, c, "APPROVED", "Dana Abbott", T)
    with pytest.raises(ValueError, match=CASES[-1]):
        fc.activate(p, "Dana Abbott", T)
    assert fc.publication_gate(p)                                       # recording reviews never activates anything
    p = fc.record_review(p, CASES[-1], "APPROVED", "Dana Abbott", T)
    assert fc.publication_gate(p)                                       # still INACTIVE until the owner activates
    a = fc.activate(p, "Michael Cather", T)
    assert a["status"] == "ACTIVE" and a["activation"]["approvedBy"] == "Michael Cather" and fc.publication_gate(a) == []
    assert json.loads(json.dumps(a)) == a


def test_readiness_matches_production_today():
    r = fc.activation_readiness(PUB, RUBRIC, COHORTS, EV, EV["knowledge"]["researchVersion"])
    state = {i["item"]: i["state"] for i in r["items"]}
    assert r["ready"] is False
    assert state["rubric approved and frozen"] == state["cohorts approved and frozen"] == state["evidence reproduces the approved baseline"] == "READY"
    assert state["reference cases reviewed by a named human"] == state["owner activation recorded"] == "BLOCKED"
    assert state["orchestrator image contains the ACTIVE record"] == "UNKNOWN"          # only provable at deploy time: never claimed READY


def test_readiness_flags_release_drift_and_unread_release():
    r = fc.activation_readiness(PUB, RUBRIC, COHORTS, EV, "2099-01-01.1")
    assert {i["item"]: i["state"] for i in r["items"]}["evidence matches the published knowledge release"] == "BLOCKED"
    r = fc.activation_readiness(PUB, RUBRIC, COHORTS, EV, None)
    assert {i["item"]: i["state"] for i in r["items"]}["evidence matches the published knowledge release"] == "UNKNOWN"


def test_ops_condition_matches_engine_authority_after_activation():
    """Ops shows capability only when authority.status AUTHORITATIVE_APPROVED and publication ACTIVE; the scorer sets publication ACTIVE
    only past the gate (attach_capability), and the rubric's authority status comes from the approved rubric."""
    p = PUB
    for c in CASES:
        p = fc.record_review(p, c, "APPROVED", "Dana Abbott", T)
    p = fc.activate(p, "Michael Cather", T)
    facts = {"brains": {"biological-state": {"researchVersion": EV["knowledge"]["researchVersion"]}}}
    scores, line = fc.attach_capability({"biological-state": {"value": 5.1}}, facts, T, publication=p, rubric=RUBRIC, evidence=EV, cohorts_by_version=COHORTS)
    cap = scores["biological-state"]["capability"]
    assert line.startswith("fish capability attached") and cap["authority"]["publication"] == "ACTIVE"
    assert cap["authority"]["status"] == "AUTHORITATIVE_APPROVED" and scores["biological-state"]["value"] == 5.1
    held, line = fc.attach_capability({"biological-state": {"value": 5.1}}, facts, T, publication=PUB, rubric=RUBRIC, evidence=EV, cohorts_by_version=COHORTS)
    assert "capability" not in held["biological-state"] and "INACTIVE" in line
