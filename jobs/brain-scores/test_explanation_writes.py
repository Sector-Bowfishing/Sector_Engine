"""plan_writes(explain=True): the explanation rides INSIDE the score block it explains, in the same update; it never creates a
score.changed event, never makes unchanged content look changed, and is backfilled once onto a block that lacks it."""
import copy
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_brains  # noqa: E402
from score_brains import UPSTREAM, load_gaps, plan_writes  # noqa: E402
from sector_brain_platform.score_explanation import evaluation_id, is_current  # noqa: E402

NOW = dt.datetime(2026, 10, 19, 19, 0, tzinfo=dt.timezone.utc)
LIVE = {k: v for k, v in json.load(open(os.path.join(os.path.dirname(__file__), "..", "brain_platform", "tests",
                                                     "score_explanation_live_2026-10-19.json"))).items() if not k.startswith("_")}


def published(explained=True):
    out = copy.deepcopy(LIVE)
    if explained:
        for bid, b in out.items():
            b["explanation"] = score_brains.explain_score(bid, b, None)
    return out


def brains():
    return {b: {"version": f"{b}-1", "researchVersion": "2026-10-17.1" if b == "biological-state" else None} for b in UPSTREAM}


def test_explain_off_is_the_previous_behaviour():
    updates, changed = plan_writes(copy.deepcopy(LIVE), brains(), NOW, None, None, published(explained=False))
    assert updates == {} and changed == []


def test_backfill_attaches_one_explanation_per_block_without_any_score_event():
    updates, changed = plan_writes(copy.deepcopy(LIVE), brains(), NOW, None, None, published(explained=False), explain=True)
    assert sorted(updates) == sorted(f"scores/{b}" for b in UPSTREAM)
    assert not any(k.startswith("activity/") for k in updates)
    for bid in UPSTREAM:
        node = updates[f"scores/{bid}"]
        assert node["value"] == LIVE[bid]["value"] and node["scoreUpdatedAt"] == LIVE[bid]["scoreUpdatedAt"]   # the PUBLISHED evaluation
        assert is_current(node)
    assert updates["scores/biological-state"]["explanation"]["knowledge"]["researchVersion"] == "2026-10-17.1"


def test_current_explanations_and_unchanged_content_write_nothing():
    pub = published()
    fresh = {b: {**copy.deepcopy(LIVE[b]), "scoreUpdatedAt": "2026-10-19T19:00:00Z"} if LIVE[b]["basis"] == "COMPUTED" else copy.deepcopy(LIVE[b])
             for b in UPSTREAM}
    updates, changed = plan_writes(fresh, brains(), NOW, None, None, pub, explain=True)
    assert updates == {} and changed == []


def test_a_new_evaluation_carries_its_own_explanation_and_the_change_from_the_old_one():
    pub = published()
    new = copy.deepcopy(LIVE)
    nb = new["biological-state"]
    nb["scoreBreakdown"]["biologicalStateValidation"]["value"] = 5.0
    nb["uncapped"] = nb["value"] = 5.6
    nb["scoreUpdatedAt"] = "2026-10-19T19:00:00Z"
    updates, _ = plan_writes(new, brains(), NOW, None, None, pub, explain=True)
    assert list(k for k in updates if k.startswith("scores/")) == ["scores/biological-state"]
    node = updates["scores/biological-state"]
    ex = node["explanation"]
    assert ex["forScore"] == {"value": 5.6, "uncapped": 5.6, "scale": 10, "basis": "COMPUTED", "scoreVersion": "biological-state-score-v1",
                              "scoreUpdatedAt": "2026-10-19T19:00:00Z"}
    assert ex["evaluationId"] == evaluation_id(node) != pub["biological-state"]["explanation"]["evaluationId"]
    assert ex["change"]["previousEvaluationId"] == pub["biological-state"]["explanation"]["evaluationId"]
    assert ex["change"]["direction"] == "UP" and ex["target"]["gap"] == 1.4
    assert any(k.startswith("activity/") for k in updates)                               # the value changed: the usual event


def test_gap_register_is_read_from_the_repository():
    gaps = load_gaps()
    assert "FISH-EVI-001" in gaps.get("biological-state", {}) and "CLARITY-VAL-001" in gaps.get("water-clarity", {})
