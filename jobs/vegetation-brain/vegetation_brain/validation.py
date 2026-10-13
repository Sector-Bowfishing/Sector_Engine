"""Pre-registered validation gates as code (docs/brains/vegetation/VEGETATION_VALIDATION_PREREGISTRATION.md section 5-7).

The numbers here MUST match the document; tests/test_validation.py pins them. Changing a gate means adding a dated amendment
to the document first. `evaluate_ladder` never returns a state above what the supplied evidence demonstrates, and
Vegetation starts NOT_VALIDATED."""
from __future__ import annotations

# --- PARTIAL gate (presence), prereg section 5
PARTIAL_MIN_PRECISION = 0.80
PARTIAL_MIN_RECALL = 0.70
PARTIAL_MIN_TRUTH_LAKES = 3
PARTIAL_MIN_POSITIVE_CELLS_PER_LAKE = 30
PARTIAL_MAX_FPR = 0.02
PARTIAL_NLA_MIN_AUC = 0.80
PARTIAL_NLA_MIN_SPEARMAN = 0.50
PARTIAL_NLA_MIN_LAKES = 15
PARTIAL_NLA_MIN_REGIONS = 3
PARTIAL_MAX_NEG_CONTROL_SHARE = 0.02
PARTIAL_MIN_F1_LOWER = 0.65
# --- VALIDATED extras
VALIDATED_MIN_LAKES = 25
VALIDATED_MIN_REGIONS = 5
# --- density gate, prereg section 6
DENSITY_MIN_LAKES = 15
DENSITY_MIN_KAPPA = 0.40
DENSITY_MIN_WITHIN_ONE = 0.90
# --- seasonal gate, prereg section 7
SEASONAL_MIN_YEARS = 4
SEASONAL_MIN_GAIN_POINTS = 10.0
SEASONAL_MIN_WITHIN_ONE = 0.85
CALIBRATION_MIN_LAKES = 10


def _ge(v, t):
    return v is not None and v >= t


def partial_gates(ev: dict) -> dict:
    """ev keys (None = not measured => NOT_TESTABLE, which is NOT a pass):
    cell_precision, cell_recall, per_lake [{lake, positives, precision, recall}], fpr, nla_auc, nla_spearman, nla_lakes, nla_regions,
    neg_control_share, f1_ci_lower"""
    out = {}
    per = [p for p in (ev.get("per_lake") or []) if (p.get("positives") or 0) >= PARTIAL_MIN_POSITIVE_CELLS_PER_LAKE]
    if len(per) < PARTIAL_MIN_TRUTH_LAKES or ev.get("cell_precision") is None:
        out["a_cell_pr"] = "NOT_TESTABLE"
    else:
        ok = _ge(ev["cell_precision"], PARTIAL_MIN_PRECISION) and _ge(ev["cell_recall"], PARTIAL_MIN_RECALL) and all(
            _ge(p.get("precision"), PARTIAL_MIN_PRECISION) and _ge(p.get("recall"), PARTIAL_MIN_RECALL) for p in per)
        out["a_cell_pr"] = "PASS" if ok else "FAIL"
    out["b_open_water_fpr"] = "NOT_TESTABLE" if ev.get("fpr") is None else ("PASS" if ev["fpr"] <= PARTIAL_MAX_FPR else "FAIL")
    if ev.get("nla_auc") is None or ev.get("nla_spearman") is None:
        out["c_nla"] = "NOT_TESTABLE"
    elif (ev.get("nla_lakes") or 0) < PARTIAL_NLA_MIN_LAKES or (ev.get("nla_regions") or 0) < PARTIAL_NLA_MIN_REGIONS:
        out["c_nla"] = "NOT_TESTABLE"
    else:
        out["c_nla"] = "PASS" if (ev["nla_auc"] >= PARTIAL_NLA_MIN_AUC and ev["nla_spearman"] >= PARTIAL_NLA_MIN_SPEARMAN) else "FAIL"
    nc = ev.get("neg_control_share")
    out["d_negative_controls"] = "NOT_TESTABLE" if nc is None else ("PASS" if nc <= PARTIAL_MAX_NEG_CONTROL_SHARE else "FAIL")
    f1 = ev.get("f1_ci_lower")
    out["e_f1_lower_bound"] = "NOT_TESTABLE" if f1 is None else ("PASS" if f1 >= PARTIAL_MIN_F1_LOWER else "FAIL")
    return out


def evaluate_ladder(ev: dict) -> dict:
    """-> {state, gates, why}. States: NOT_VALIDATED < RESEARCH < CALIBRATION < PARTIAL < VALIDATED."""
    state, why = "NOT_VALIDATED", []
    if ev.get("production_code_scored") and (ev.get("independent_truth_sets") or 0) >= 2:
        state = "RESEARCH"
    else:
        why.append("RESEARCH needs the observer reproduced from production code and scored on >= 2 independent truth sets")
    if state == "RESEARCH" and ev.get("calibration_disjoint") and (ev.get("truth_lakes") or 0) >= CALIBRATION_MIN_LAKES:
        state = "CALIBRATION"
    elif state == "RESEARCH":
        why.append("CALIBRATION needs thresholds fixed on a disjoint calibration subset and >= 10 truth lakes")
    gates = partial_gates(ev)
    if state == "CALIBRATION" and all(v == "PASS" for v in gates.values()):
        state = "PARTIAL"
    elif state == "CALIBRATION":
        why.append("PARTIAL needs every gate PASS: " + ", ".join(f"{k}={v}" for k, v in gates.items() if v != "PASS"))
    if state == "PARTIAL":
        full = ((ev.get("truth_lakes") or 0) >= VALIDATED_MIN_LAKES and (ev.get("regions") or 0) >= VALIDATED_MIN_REGIONS
                and ev.get("has_turbid_reservoir") and ev.get("has_southern_hydrilla") and ev.get("persistence_validated")
                and ev.get("two_seasons") and ev.get("independent_review"))
        if full:
            state = "VALIDATED"
        else:
            why.append("VALIDATED needs >= 25 lakes, >= 5 regions, turbid reservoir, southern hydrilla system, validated persistence, 2 seasons, independent review")
    return {"state": state, "gates": gates, "why": why}


def density_gate(lakes: int | None, weighted_kappa: float | None, within_one: float | None) -> bool:
    return bool((lakes or 0) >= DENSITY_MIN_LAKES and _ge(weighted_kappa, DENSITY_MIN_KAPPA) and _ge(within_one, DENSITY_MIN_WITHIN_ONE))


def seasonal_gate(years: int | None, gain_points: float | None, within_one: float | None) -> bool:
    return bool((years or 0) >= SEASONAL_MIN_YEARS and _ge(gain_points, SEASONAL_MIN_GAIN_POINTS) and _ge(within_one, SEASONAL_MIN_WITHIN_ONE))
