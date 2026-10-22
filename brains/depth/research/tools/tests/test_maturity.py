import json
import os

from conftest import MANIFEST_PATH, research_file

import pytest
from depth_research import maturity as M

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = json.load(open(MANIFEST_PATH))
INP = M.load_json("maturity_inputs.json")


def test_never_official():
    r = M.evaluate(MAN, INP)
    assert r["official"] is False and r["scoreStatus"] == "NOT_ESTABLISHED" and INP["official"] is False


def test_weights_sum_to_100_and_critical_set():
    assert sum(d["weight"] for d in INP["dimensions"].values()) == 100
    assert {k for k, d in INP["dimensions"].items() if d["critical"]} == {"authority", "coverage", "relative", "effective", "validation"}


def test_coverage_anchors_are_monotone_and_computed_not_typed():
    scores = [M.coverage_score(x / 100) for x in range(0, 101)]
    assert scores == sorted(scores) and scores[0] == 1 and scores[-1] == 9
    assert M.coverage_score(0.148) == 3 and M.coverage_score(0.20) == 4 and M.coverage_score(0.50) == 6
    assert INP["dimensions"]["coverage"]["basis"] == "computed" and INP["dimensions"]["coverage"]["score"] is None


def test_overall_is_weighted_mean_and_gates_fail_today():
    r = M.evaluate(MAN, INP)
    manual = sum(d["weight"] * d["score"] for d in r["dimensions"].values()) / 100
    assert r["overall"] == pytest.approx(manual, abs=0.01)
    assert r["meetsProductionPolicy"] is False and r["criticalBelowThreshold"]


def test_every_judgment_dimension_has_evidence():
    for k, d in INP["dimensions"].items():
        assert d["evidence"], k


def test_fleet_metrics_match_manifest():
    f = M.fleet_metrics(MAN)
    assert f["totalLakes"] == 621 and f["shiftPossible"] == f["pilotVerified"] + f["highConfidence"] + f["mediumConfidence"]
    assert f["blocked"] == 621 - f["shiftPossible"]
    assert f["verifiedDatum"] + f["inferredOperatorSystem"] + f["convertedDatum"] == f["shiftPossible"]


def test_anti_gaming_unsupported_increase_is_flagged():
    prev = {"dimensions": {"validation": {"score": 5}}, "citedEvidence": {"validation": ["field-2026-10-01"]}}
    inp = json.loads(json.dumps(INP))
    inp["dimensions"]["validation"]["score"] = 6
    assert M.check_increase(prev, inp)                                   # no new evidence
    inp["dimensions"]["validation"]["changeEvidence"] = ["field-2026-10-01"]
    assert M.check_increase(prev, inp)                                   # same evidence already cited
    inp["dimensions"]["validation"]["changeEvidence"] = ["field-2026-10-01", "twdb-validation-2026-10-14"]
    assert not M.check_increase(prev, inp)
    inp["dimensions"]["validation"]["score"] = 4                         # decreases never need justification
    assert not M.check_increase(prev, inp)


def test_diff_reports_previous_and_new():
    prev = {"overall": 4.5, "fleet": {"shiftPossible": 90, "verifiedDatum": 70, "highConfidence": 60, "mediumConfidence": 20, "blocked": 531, "shiftPossibleShare": 0.145}}
    d = M.diff(prev, M.evaluate(MAN, INP))
    assert d["shiftPossible"]["previous"] == 90 and d["shiftPossible"]["new"] == M.fleet_metrics(MAN)["shiftPossible"] and d["researchMaturity"]["previous"] == 4.5


def test_baseline_matches_the_foundation_handoff():
    r = M.evaluate(MAN, INP)
    log = [json.loads(l) for l in open(research_file("depth_progress_log.jsonl")) if l.strip()]
    assert log[0]["overall"] == 4.5 and log[0]["fleet"]["shiftPossible"] == 92
