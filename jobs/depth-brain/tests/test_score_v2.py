import copy
import datetime as dt
import json
import os

from depth_brain import score_v2_proposal as S

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = json.load(open(os.path.join(HERE, "depth_brain", "data", "candidates.json")))
CL = json.load(open(os.path.join(HERE, "depth_brain", "data", "claim_levels.json")))
NOW = dt.datetime(2026, 10, 14, tzinfo=dt.timezone.utc)


def facts(**kw):
    return S.facts_from_manifest(MAN, CL, **{"live_states": 5, **kw})


def test_v2_is_never_official_and_not_wired():
    r = S.score_depth_proposal(facts(), NOW)
    assert S.OFFICIAL is False and r["official"] is False
    for fn in ("publish.py", "ops_summary.py", "state.py", "maturity.py"):
        src = open(os.path.join(HERE, "depth_brain", fn)).read()
        assert "score_v2_proposal" not in src and "score_v1_proposal" not in src, fn
    assert "/scores/" not in open(os.path.join(HERE, "depth_brain", "publish.py")).read().replace("no /scores/depth", "")


def test_weights_sum_and_nothing_out_of_mission_is_rewarded():
    assert sum(S.WEIGHTS.values()) == 100
    assert not [d for d in S.WEIGHTS for w in S.FORBIDDEN_DIMENSIONS if w in d.lower()]
    assert set(S.CRITICAL) <= set(S.WEIGHTS)


def test_extra_facts_about_globathy_or_deep_bathymetry_cannot_move_the_score():
    a = S.score_depth_proposal(facts(), NOW)["uncapped"]
    f = facts(); f["globathyCoverage"] = 468; f["deepBasinDepth"] = 1.0; f["absoluteDepthAccuracy"] = 9.0
    assert S.score_depth_proposal(f, NOW)["uncapped"] == a


def test_today_interpretation_validity_stays_unknown_and_policy_fails():
    r = S.score_depth_proposal(facts(), NOW)
    assert r["scoreBreakdown"]["interpretationValidity"]["status"] == "UNKNOWN"            # never faked before field truth
    assert "interpretationValidity" in r["criticalBelow7_5"] and r["meetsProductionPolicy"] is False


def test_coverage_counts_defensible_profiled_lakes_not_live_states():
    a = S.score_depth_proposal(facts(live_states=5), NOW)["scoreBreakdown"]["fleetCoverage"]["value"]
    b = S.score_depth_proposal(facts(live_states=200), NOW)["scoreBreakdown"]["fleetCoverage"]["value"]
    assert a == b                                                                            # liveness is scored in operationalReliability, not here
    assert S.score_depth_proposal(facts(live_states=200, orchestration="RUNNING"), NOW)["scoreBreakdown"]["operationalReliability"]["value"] > \
        S.score_depth_proposal(facts(live_states=5), NOW)["scoreBreakdown"]["operationalReliability"]["value"]


def test_field_validation_is_the_only_thing_that_unlocks_interpretation_validity():
    base = S.score_depth_proposal(facts(), NOW)["uncapped"]
    passed = S.score_depth_proposal(facts(field_validation="PASSED", interpretation_claims_published=True), NOW)
    assert passed["scoreBreakdown"]["interpretationValidity"]["value"] == 9.0 and passed["uncapped"] > base
    assert "interpretationValidity" not in passed["criticalBelow7_5"]


def test_publishing_interpretation_classes_without_field_truth_is_capped():
    r = S.score_depth_proposal(facts(interpretation_claims_published=True, field_validation="NOT_STARTED"), NOW)
    assert any(b.get("gate") == "fieldTruth" and b["cap"] == 5.0 for b in r["scoreBlockers"]) and r["value"] <= 5.0


def test_gates_cap_never_add_and_coverage_gate_fires_below_ten_percent():
    r = S.score_depth_proposal(facts(health="FAILED"), NOW)
    assert r["value"] <= 2.0 <= r["uncapped"] or r["value"] <= r["uncapped"]
    low = copy.deepcopy(MAN)
    for c in low["candidates"]:
        c["shiftPossible"] = False
    z = S.score_depth_proposal(S.facts_from_manifest(low, CL, live_states=0), NOW)
    assert any(b.get("gate") == "coverage" and b["cap"] == 3.0 for b in z["scoreBlockers"]) and z["value"] <= 3.0


def test_inferred_datum_counts_less_than_verified_and_stale_states_reduce_freshness():
    f = facts(); base = S.score_depth_proposal(f, NOW)["scoreBreakdown"]["datumCorrectness"]["value"]
    g = copy.deepcopy(f); g["datumVerified"], g["datumInferred"] = 0, f["datumVerified"] + f["datumInferred"]
    assert S.score_depth_proposal(g, NOW)["scoreBreakdown"]["datumCorrectness"]["value"] <= base
    assert S.score_depth_proposal(facts(live_stale=5), NOW)["scoreBreakdown"]["freshness"]["value"] == 0.0


def test_the_production_policy_needs_coverage_of_at_least_75_percent_of_the_addressable_fleet():
    f = facts(live_states=400, orchestration="RUNNING", field_validation="PASSED", interpretation_claims_published=True)
    f["shiftPossible"], f["datumVerified"], f["datumInferred"] = int(0.74 * f["addressable"]), int(0.74 * f["addressable"]), 0
    f["evidenceLakes"], f["zonesActive"] = int(0.9 * f["shiftPossible"]), int(0.9 * f["evidenceLakes"])
    r = S.score_depth_proposal(f, NOW)
    assert "fleetCoverage" in r["criticalBelow7_5"]                                           # 74 % -> ladder 7 -> below 7.5
    f["shiftPossible"] = f["datumVerified"] = int(0.76 * f["addressable"])
    assert "fleetCoverage" not in S.score_depth_proposal(f, NOW)["criticalBelow7_5"]
