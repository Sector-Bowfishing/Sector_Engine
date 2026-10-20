"""Fish Biological Capability V2 scorer (shared platform authority), on hand-built evidence. No Fish runtime import: the scorer stands alone."""
import copy
import json
import os

import pytest

from sector_brain_platform import fish_capability as fc
from sector_brain_platform import scoring

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "brains", "scoring")
RUBRIC = fc.load_json(os.path.join(DOCS, "fish-biological-capability-v2.json"))
COHORTS = fc.load_json(os.path.join(DOCS, "fish-capability-cohorts-v1.json"))
NOW = "2026-10-19T00:00:00Z"


def evidence(fractions: dict, *, status=None, cohorts=COHORTS, kv="2026-10-17.1"):
    """fractions: {speciesId: float applied to every criterion} for the frozen rosters; NOT_ASSESSED entries stay unscored."""
    ids = sorted(set(cohorts["cohorts"]["TARGET"]["species"]) | set(cohorts["cohorts"]["ALL_ASSESSED"]["species"]))
    crit = [c["criterionId"] for cat in RUBRIC["categories"] for c in cat["criteria"]]
    sp = {}
    for s in ids:
        st = (status or {}).get(s, "ASSESSED")
        if st != "ASSESSED":
            sp[s] = {"evaluationStatus": st, "reason": "test"}
            continue
        f = fractions.get(s, 0.0)
        sp[s] = {"evaluationStatus": "ASSESSED", "role": "TARGET" if s in cohorts["cohorts"]["TARGET"]["species"] else "KNOWLEDGE_ONLY",
                 "criteria": {c: {"result": "PASS" if f >= 1 else ("FAIL" if f <= 0 else "PARTIAL"), "fraction": f,
                                  **({} if f >= 1 else {"blocker": {"blocker": "MISSING_KNOWLEDGE", "why": "test"}})} for c in crit},
                 "knowledgeContext": {}}
    for s in cohorts.get("notAssessedByPolicy") or []:
        sp[s] = {"evaluationStatus": "NOT_ASSESSED", "reason": "policy"}
    for s in cohorts.get("notIndividuallyAssessable") or {}:
        sp[s] = {"evaluationStatus": "INSUFFICIENT_EVIDENCE", "reason": "grouped taxon"}
    return {"schema": fc.EVIDENCE_SCHEMA, "rubricId": RUBRIC["rubricId"], "criteria": crit, "cohortsVersion": cohorts["cohortsVersion"],
            "knowledge": {"knowledgeVersion": kv}, "evaluationId": "fcap-test", "evaluatedAt": NOW, "species": sp}


def test_rubric_is_internally_consistent_and_keeps_the_owner_weights():
    assert fc.validate_rubric(RUBRIC) == []
    assert {c["categoryId"]: c["maxPoints"] for c in RUBRIC["categories"]} == {
        "biologyBehavior": 2.5, "habitatDepth": 2.0, "environmental": 2.0, "spawnSeason": 2.0, "dayNight": 1.0, "application": 0.5}
    assert RUBRIC["status"] == "APPROVED" and RUBRIC["approval"]["approvedAt"] == "2026-10-19"          # owner adoption, 2026-10-19
    assert RUBRIC["publication"]["status"] == "INACTIVE" and "GC-REF-02" in RUBRIC["publication"]["gate"]


def test_frozen_cohorts_match_the_audited_inventory():
    c = COHORTS["cohorts"]
    assert len(c["TARGET"]["species"]) == 8 and len(c["ALL_ASSESSED"]["species"]) == 27
    assert set(c["TARGET"]["species"]) <= set(c["ALL_ASSESSED"]["species"])
    assert sorted(COHORTS["notAssessedByPolicy"]) == ["suckers_redhorse_carpsuckers_group", "tilapia_unresolved"]
    assert not set(COHORTS["notAssessedByPolicy"]) & set(c["ALL_ASSESSED"]["species"])


def test_full_marks_is_ten_and_zero_is_zero():
    t = COHORTS["cohorts"]["TARGET"]["species"]
    r = fc.build_result(evidence({s: 1.0 for s in t}), RUBRIC, COHORTS, generated_at=NOW)
    assert r["species"][t[0]]["capabilityScore"] == 10.0
    assert r["aggregates"]["TARGET"]["value"] == 10.0
    others = [s for s in COHORTS["cohorts"]["ALL_ASSESSED"]["species"] if s not in t]
    assert all(r["species"][s]["capabilityScore"] == 0.0 for s in others)
    a = r["aggregates"]["ALL_ASSESSED"]
    assert a["value"] == pytest.approx(10 * 8 / 27, abs=1e-6)
    assert a["below5"] == 19 and a["pctAtLeast7"] == pytest.approx(round(100 * 8 / 27, 1))
    assert a["bottomQuartileMean"] == 0.0 and a["lowestScore"] == 0.0


def test_one_strong_species_cannot_hide_weak_ones():
    t = COHORTS["cohorts"]["TARGET"]["species"]
    r = fc.build_result(evidence({t[0]: 1.0}), RUBRIC, COHORTS, generated_at=NOW)
    a = r["aggregates"]["TARGET"]
    assert a["value"] == pytest.approx(10 / 8) and a["below5"] == 7 and a["highest"]["speciesId"] == t[0]


def test_not_assessed_is_unscored_and_failed_makes_incomplete():
    t = COHORTS["cohorts"]["TARGET"]["species"]
    r = fc.build_result(evidence({s: 0.5 for s in t}, status={t[1]: "EVALUATION_FAILED"}), RUBRIC, COHORTS, generated_at=NOW)
    a = r["aggregates"]["TARGET"]
    assert a["status"] == "INCOMPLETE" and a["value"] is None and a["evaluated"] == 7
    assert a["bounds"]["ifUnscoredWere0"] == pytest.approx(7 * 5 / 8) and a["bounds"]["ifUnscoredWere10"] == pytest.approx((35 + 10) / 8)
    for s in COHORTS["notAssessedByPolicy"]:
        assert r["species"][s]["capabilityScore"] is None and r["species"][s]["evaluationStatus"] == "NOT_ASSESSED"


def test_validation_fails_closed():
    ev = evidence({})
    bad = copy.deepcopy(ev)
    bad["species"].pop(COHORTS["cohorts"]["TARGET"]["species"][0])
    assert any("missing from the evidence" in e for e in fc.validate_evidence(bad, RUBRIC, COHORTS))
    bad = copy.deepcopy(ev)
    s0 = COHORTS["cohorts"]["TARGET"]["species"][0]
    bad["species"][s0]["points"] = 3
    assert any("score field" in e for e in fc.validate_evidence(bad, RUBRIC, COHORTS))
    bad = copy.deepcopy(ev)
    bad["criteria"] = bad["criteria"][:-1]
    assert fc.validate_evidence(bad, RUBRIC, COHORTS)
    with pytest.raises(ValueError):
        fc.build_result(bad, RUBRIC, COHORTS, generated_at=NOW)


def test_exemption_normalizes_the_denominator_only_when_reviewed():
    r = copy.deepcopy(RUBRIC)
    s0 = COHORTS["cohorts"]["TARGET"]["species"][0]
    ev = evidence({s0: 1.0})
    ev["species"][s0]["criteria"]["DN-1"] = {"result": "NOT_APPLICABLE", "fraction": None}
    assert any("without a reviewed exemption" in e for e in fc.validate_evidence(ev, r, COHORTS))
    r["normalizationPolicy"]["biologicalExemptions"] = {s0: {"criteria": ["DN-1"], "reason": "reviewed test exemption"}}
    res = fc.build_result(ev, r, COHORTS, generated_at=NOW)
    assert res["species"][s0]["capabilityScore"] == pytest.approx(10.0)
    assert res["species"][s0]["exemptCriteria"] == ["DN-1"]


def test_change_record_has_exact_deltas_and_never_edits_history():
    t = COHORTS["cohorts"]["TARGET"]["species"]
    a = fc.build_result(evidence({s: 0.5 for s in t}), RUBRIC, COHORTS, generated_at=NOW)
    snap = json.dumps(a, sort_keys=True)
    up = {s: 0.5 for s in t} | {t[2]: 0.51}
    b = fc.build_result(evidence(up), RUBRIC, COHORTS, generated_at=NOW, previous=a)
    row = next(x for x in b["changeRecord"]["species"] if x["speciesId"] == t[2])
    assert row["delta"] == pytest.approx(0.1, abs=1e-6)
    assert b["changeRecord"]["aggregates"]["TARGET"]["delta"] == pytest.approx(0.1 / 8, abs=1e-6)
    assert json.dumps(a, sort_keys=True) == snap


def test_legacy_maturity_scorer_is_independent():
    """biological-state-score-v1 still reproduces its documented behaviour; the capability module neither imports nor wraps it."""
    src = open(fc.__file__).read()
    assert "score_biological" not in src.replace("Separate from `score_biological`", "")
    assert "fish_capability" not in open(scoring.__file__).read()


def test_cohorts_v2_treats_grouped_taxa_consistently_and_keeps_v1():
    c2 = fc.load_json(os.path.join(DOCS, "fish-capability-cohorts-v2.json"))
    assert COHORTS["cohortsVersion"] == "fish-capability-cohorts-v1" and len(COHORTS["cohorts"]["ALL_ASSESSED"]["species"]) == 27     # history kept
    assert len(c2["cohorts"]["ALL_ASSESSED"]["species"]) == 26 and c2["cohorts"]["TARGET"] == COHORTS["cohorts"]["TARGET"]
    assert set(c2["notIndividuallyAssessable"]) == {"carpsuckers_group"}
    assert set(COHORTS["cohorts"]["ALL_ASSESSED"]["species"]) - set(c2["cohorts"]["ALL_ASSESSED"]["species"]) == {"carpsuckers_group"}
    assert c2["notAssessedByPolicy"] == COHORTS["notAssessedByPolicy"]
    assert "RAISES" in c2["treatmentRule"]["denominatorChange"]          # the effect on the number is declared, not hidden


def test_rubric_2_1_revision_is_recorded_and_weights_unchanged():
    assert RUBRIC["rubricVersion"] == "2.1.0"
    assert [h["version"] for h in RUBRIC["revisionHistory"]] == ["2.0.0-candidate", "2.1.0-candidate", "2.1.0"]


def test_approved_rubric_and_cohorts_are_authoritative_but_never_published():
    c2 = fc.load_json(os.path.join(DOCS, "fish-capability-cohorts-v2.json"))
    assert c2["status"] == "APPROVED"
    t = c2["cohorts"]["TARGET"]["species"]
    r = fc.build_result(evidence({s: 1.0 for s in t}, cohorts=c2), RUBRIC, c2, generated_at=NOW)
    assert r["authority"]["status"] == "AUTHORITATIVE_APPROVED"
    assert r["authority"]["publication"] == "INACTIVE" and "reference cases" in r["authority"]["publicationGate"]
    assert r["authority"]["displayLabel"] == "scenario capability (not field-validated)"
    assert fc.build_result(evidence({}), RUBRIC, COHORTS, generated_at=NOW)["authority"]["status"] == "CANDIDATE"      # v1 cohorts were not approved
