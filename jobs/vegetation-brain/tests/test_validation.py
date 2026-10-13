import os
import re

from vegetation_brain import validation as V

DOC = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "brains", "vegetation", "VEGETATION_VALIDATION_PREREGISTRATION.md")


def good():
    return {"production_code_scored": True, "independent_truth_sets": 3, "calibration_disjoint": True, "truth_lakes": 12,
            "cell_precision": 0.85, "cell_recall": 0.75,
            "per_lake": [{"lake": "a", "positives": 50, "precision": 0.86, "recall": 0.74}, {"lake": "b", "positives": 40, "precision": 0.82, "recall": 0.71},
                         {"lake": "c", "positives": 35, "precision": 0.9, "recall": 0.8}],
            "fpr": 0.01, "nla_auc": 0.85, "nla_spearman": 0.6, "nla_lakes": 18, "nla_regions": 4, "neg_control_share": 0.01, "f1_ci_lower": 0.7}


def test_starts_not_validated():
    assert V.evaluate_ladder({})["state"] == "NOT_VALIDATED"


def test_research_needs_production_code_and_two_truth_sets():
    assert V.evaluate_ladder({"production_code_scored": True, "independent_truth_sets": 1})["state"] == "NOT_VALIDATED"
    assert V.evaluate_ladder({"production_code_scored": True, "independent_truth_sets": 2})["state"] == "RESEARCH"


def test_partial_requires_every_gate():
    ev = good()
    assert V.evaluate_ladder(ev)["state"] == "PARTIAL"
    for key, bad in (("fpr", 0.05), ("nla_auc", 0.7), ("neg_control_share", 0.1), ("f1_ci_lower", 0.5), ("cell_recall", 0.6)):
        e = good()
        e[key] = bad
        assert V.evaluate_ladder(e)["state"] == "CALIBRATION", key


def test_missing_measurement_is_not_testable_never_a_pass():
    e = good()
    e["nla_auc"] = None
    g = V.evaluate_ladder(e)
    assert g["gates"]["c_nla"] == "NOT_TESTABLE" and g["state"] == "CALIBRATION"


def test_each_truth_lake_must_pass_not_only_the_pool():
    e = good()
    e["per_lake"][2]["precision"] = 0.6
    assert V.evaluate_ladder(e)["state"] == "CALIBRATION"


def test_too_few_positive_cells_is_not_testable():
    e = good()
    e["per_lake"] = [{"lake": "a", "positives": 54, "precision": 0.9, "recall": 0.9}, {"lake": "b", "positives": 6, "precision": 1, "recall": 1}]
    assert V.evaluate_ladder(e)["gates"]["a_cell_pr"] == "NOT_TESTABLE"


def test_validated_needs_breadth_and_review():
    e = {**good(), "truth_lakes": 30, "regions": 6, "has_turbid_reservoir": True, "has_southern_hydrilla": True,
         "persistence_validated": True, "two_seasons": True, "independent_review": True}
    assert V.evaluate_ladder(e)["state"] == "VALIDATED"
    e["independent_review"] = False
    assert V.evaluate_ladder(e)["state"] == "PARTIAL"


def test_density_and_seasonal_gates():
    assert not V.density_gate(10, 0.5, 0.95) and V.density_gate(15, 0.4, 0.9) and not V.density_gate(15, 0.39, 0.95)
    assert not V.seasonal_gate(3, 20, 0.9) and V.seasonal_gate(4, 10.0, 0.85) and not V.seasonal_gate(5, 5, 0.9)


def test_gate_constants_match_the_frozen_preregistration():
    txt = open(DOC).read()
    for needle in ("precision ≥ 0.80", "recall ≥ 0.70", "≤ 2 %", "AUC ≥ 0.80", "Spearman ≥ 0.50", "≥ 15 eligible lakes", "≥ 0.65",
                   "≥ 25 truth lakes", "weighted kappa ≥ 0.40", "within-one-class agreement ≥ 90 %", "≥ 10 points above", "within-one ≥ 85 %"):
        assert needle in txt, needle
    assert (V.PARTIAL_MIN_PRECISION, V.PARTIAL_MIN_RECALL, V.PARTIAL_MAX_FPR, V.PARTIAL_NLA_MIN_AUC, V.PARTIAL_NLA_MIN_SPEARMAN) == (0.8, 0.7, 0.02, 0.8, 0.5)
    assert (V.DENSITY_MIN_KAPPA, V.DENSITY_MIN_WITHIN_ONE, V.SEASONAL_MIN_GAIN_POINTS, V.SEASONAL_MIN_WITHIN_ONE) == (0.4, 0.9, 10.0, 0.85)


def test_seasonal_gate_must_beat_every_baseline_amendment_a2():
    ok = {"calendar": 30, "most_common_state": 12, "persistence_le_30d": 11}
    assert V.seasonal_gate(5, ok, 0.9)
    assert not V.seasonal_gate(5, {**ok, "most_common_state": 6}, 0.9)          # the real back-test: +6 over the mode guess
    assert not V.seasonal_gate(5, {"calendar": 40}, 0.9)                        # missing baselines never pass
    assert not V.seasonal_gate(5, ok, 0.9, max_belt_share=0.003)                # no measurable signal => UNKNOWN
