"""plan_writes: a score node is rewritten when its CONTENT changes (breakdown/uncapped behind a gate cap), the activity event
only when the displayed value/version/basis changes; identical content (ignoring the refresh timestamp) writes nothing."""
import json
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_brains  # noqa: E402
from score_brains import UPSTREAM, plan_writes  # noqa: E402

NOW = dt.datetime(2026, 10, 13, 19, 0, tzinfo=dt.timezone.utc)


def block(value=3.0, uncapped=4.3, hist=2.0, at="2026-10-13T03:53:11Z"):
    return {"value": value, "uncapped": uncapped, "scale": 10, "basis": "COMPUTED", "scoreVersion": "v1", "scoreUpdatedAt": at,
            "scoreBreakdown": {"historyQuality": {"value": hist, "weight": 15, "status": "SCORED", "evidence": "x"}}, "scoreBlockers": []}


def all_scores(**kw):
    return {b: block(**kw) for b in UPSTREAM}


def brains():
    return {b: {} for b in UPSTREAM}


def test_identical_content_writes_nothing_even_with_a_new_timestamp():
    old = all_scores()
    new = {b: block(at="2026-10-13T19:00:00Z") for b in UPSTREAM}
    updates, changed = plan_writes(new, brains(), NOW, None, None, old)
    assert updates == {} and changed == []


def test_breakdown_change_behind_a_gate_cap_rewrites_the_node_without_an_event():
    old = all_scores()
    new = dict(old); new["lake-brain"] = block(value=3.0, uncapped=6.3, hist=10.0, at="2026-10-13T19:00:00Z")
    updates, changed = plan_writes(new, brains(), NOW, None, None, old)
    assert list(updates) == ["scores/lake-brain"]                                   # node refreshed
    assert not any(k.startswith("activity/") for k in updates)                      # no score.changed event: displayed value is the same
    assert "breakdown refreshed" in changed[0] and "4.3 → 6.3" in changed[0]


def test_value_change_writes_node_and_event():
    old = all_scores()
    new = dict(old); new["lake-brain"] = block(value=5.0, uncapped=6.3, hist=10.0)
    updates, changed = plan_writes(new, brains(), NOW, None, None, old)
    assert "scores/lake-brain" in updates and sum(k.startswith("activity/") for k in updates) == 1
    assert changed == ["lake-brain: 3.0 → 5.0"]


def test_engine_timestamp_alone_never_rewrites():
    eng_old = {"engineScore": 6.4, "engineScoreVersion": "e1", "dimensions": {"a": 1}, "updatedAt": "t0"}
    eng_new = dict(eng_old, updatedAt="t1")
    updates, changed = plan_writes(all_scores(), brains(), NOW, eng_new, eng_old, all_scores())
    assert updates == {} and changed == []


def test_engine_node_follows_the_same_rule():
    eng_old = {"engineScore": 6.4, "engineScoreVersion": "e1", "dimensions": {"a": 1}, "updatedAt": "t0"}
    eng_new = {"engineScore": 6.4, "engineScoreVersion": "e1", "dimensions": {"a": 2}, "updatedAt": "t1"}
    updates, changed = plan_writes(all_scores(), brains(), NOW, eng_new, eng_old, all_scores())
    assert "scores/engine" in updates and "engine/score" in updates and not any(k.startswith("activity/") for k in updates)
    assert "breakdown refreshed" in changed[0]


def test_empty_containers_read_back_from_rtdb_do_not_trigger_a_rewrite():
    """RTDB drops empty objects/arrays: a frozen block computed with scoreBreakdown {} is published WITHOUT the key. That must not look like a change every cycle."""
    computed = {b: {"value": 3.0, "scale": 10, "basis": "FROZEN", "scoreVersion": "v1", "scoreUpdatedAt": "2026-10-13T19:00:00Z", "scoreBreakdown": {}, "scoreBlockers": [{"gate": "g", "why": "w"}]} for b in UPSTREAM}
    published = {b: {k: v for k, v in blk.items() if k != "scoreBreakdown"} for b, blk in computed.items()}          # what a read-back looks like
    updates, changed = plan_writes(computed, brains(), NOW, None, None, published)
    assert updates == {} and changed == []
    # a real change in a populated breakdown still rewrites
    computed["wind"]["scoreBreakdown"] = {"x": {"value": 1}}
    updates, changed = plan_writes(computed, brains(), NOW, None, None, published)
    assert "scores/wind" in updates and all(k == "scores/wind" for k in updates)


def test_frozen_block_with_rtdb_illegal_dimension_keys_is_publishable():
    """Incident 2026-10-13 21:50Z: the Wind block's 'Freshness/reliability' key made the whole scores update fail (IllegalKey)."""
    from sector_brain_platform.keys import check_keys
    sb = score_brains.rtdb_safe({"wind": {"scoreBreakdown": {"Freshness/reliability": {"value": 1}, "Provenance/Unknown": {"value": 0}}}})
    check_keys(sb)
    assert "Freshness-reliability" in sb["wind"]["scoreBreakdown"]


def test_committed_frozen_scores_are_publishable_after_sanitising():
    from sector_brain_platform.keys import check_keys
    check_keys(score_brains.rtdb_safe(json.load(open(score_brains.FROZEN))))


class _FakeDb:
    """A Brain RTDB with N profiled Lake Brain lakes: the scorer must read ALL of them (no silent first-200 cap)."""
    def __init__(self, n):
        self.n = n
        self.keys = [f"Lake_{i:04d}_XX" for i in range(n)]

    def get(self, path):
        if path == "lakeFleet":
            return {k: {"slots": {"lake": True}} for k in self.keys}
        if path == "brains":
            return {"lake-brain": {"directoryLakeCount": 621}}
        if path.startswith("lakes/") and path.endswith("/brain"):
            return {"sourceCapability": {"level": "DIRECT_OPERATOR_POOL"}, "historicalCoverage": {"baselineStatus": "SUFFICIENT"}}
        if path.startswith("lakes/") and path.endswith("/states/lake"):
            return {"kind": "OBSERVED", "floodPoolState": "UNKNOWN"}
        return None


def test_fetch_facts_reads_every_profiled_lake_not_just_the_first_200():
    from score_brains import fetch_facts
    f = fetch_facts(_FakeDb(327))["lake"]
    assert len(f["profiles"]) == 327 and len(f["states"]) == 327 and f["profiledCount"] == 327
