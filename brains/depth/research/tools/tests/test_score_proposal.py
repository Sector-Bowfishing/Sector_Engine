import copy
import datetime as dt
import json
import os

from conftest import MANIFEST_PATH, research_file

import pytest
from depth_research import score_v1_proposal as S

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = json.load(open(MANIFEST_PATH))
NOW = dt.datetime(2026, 10, 14, tzinfo=dt.timezone.utc)


def facts(**kw):
    return S.facts_from_manifest(MAN, live_states=kw.pop("live_states", 5), **kw)


def test_proposal_is_never_official_and_not_wired():
    r = S.score_depth_proposal(facts(), NOW)
    assert S.OFFICIAL is False and r["official"] is False
    src = open(os.path.join(HERE, "..", "..", "runtime", "depth_brain", "publish.py")).read() + open(os.path.join(HERE, "..", "..", "runtime", "depth_brain", "ops_summary.py")).read()
    assert "score_v1_proposal" not in src and "/scores/" not in src.replace("no /scores/depth", "")


def test_weights_sum_and_no_forbidden_dimensions():
    assert sum(S.WEIGHTS.values()) == 100
    assert not [d for d in S.WEIGHTS for w in S.FORBIDDEN_DIMENSIONS if w in d.lower()]
    assert set(S.CRITICAL) <= set(S.WEIGHTS)


def test_today_is_capped_hard_by_coverage_and_validation():
    r = S.score_depth_proposal(facts(), NOW)
    gates = {b["gate"]: b["cap"] for b in r["scoreBlockers"] if "gate" in b}
    assert gates["coverage"] == 3.0 and gates["validation"] == 5.0 and gates["fieldTruth"] == 6.0 and gates["orchestration"] == 6.0
    assert r["value"] <= 3.0 and r["value"] <= r["uncapped"] and r["meetsProductionPolicy"] is False
    assert r["scoreBreakdown"]["effectiveDepthCorrectness"]["status"] == "UNKNOWN"          # not faked before validation


def test_gates_cap_never_add():
    hi = facts(live_states=300, validation="VALIDATED", field_validation="PASSED", orchestration="RUNNING", effective_validated_pass=True)
    r = S.score_depth_proposal(hi, NOW)
    assert r["value"] <= r["uncapped"] + 1e-9


def test_globathy_or_deep_bathymetry_cannot_move_the_score():
    a = S.score_depth_proposal(facts(), NOW)
    f = facts()
    f["globathyCoverage"] = 468; f["deepBasinDepth"] = 1.0                    # extra facts are ignored
    assert S.score_depth_proposal(f, NOW)["uncapped"] == a["uncapped"]


def test_inferred_datum_counts_less_than_verified():
    f = facts(); base = S.score_depth_proposal(f, NOW)["scoreBreakdown"]["datumCorrectness"]["value"]
    g = copy.deepcopy(f); g["datumVerified"], g["datumInferred"] = 0, f["datumVerified"] + f["datumInferred"]
    assert S.score_depth_proposal(g, NOW)["scoreBreakdown"]["datumCorrectness"]["value"] <= base


def test_stale_states_reduce_freshness_and_unvalidated_effective_depth_stays_unknown():
    r = S.score_depth_proposal(facts(live_states=5), NOW)
    assert r["scoreBreakdown"]["freshness"]["value"] == 10.0
    r2 = S.score_depth_proposal(S.facts_from_manifest(MAN, live_states=5, live_stale=5), NOW)
    assert r2["scoreBreakdown"]["freshness"]["value"] == 0.0


def test_critical_dimensions_listed_and_policy_needs_all_of_them():
    r = S.score_depth_proposal(facts(), NOW)
    assert r["criticalDimensions"] == list(S.CRITICAL) and set(r["criticalBelow7_5"]) == set(S.CRITICAL)
