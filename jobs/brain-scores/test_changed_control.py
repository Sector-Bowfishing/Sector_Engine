"""--if-changed: control nodes are rewritten only when their content changed (timestamps ignored)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_brains import changed_control


def test_unchanged_nodes_are_not_rewritten():
    pub = {"overview": {"updatedAt": "t0", "fleet": {"lakes": 2, "summarizedAt": "t0"}}, "fleet": {"A": {"rolledUpAt": "t0", "stale": False}}}
    new = {"control/overview": {"updatedAt": "t1", "fleet": {"lakes": 2, "summarizedAt": "t1"}}, "control/fleet/A": {"rolledUpAt": "t1", "stale": False}}
    assert changed_control(new, pub) == {}


def test_a_changed_rollup_rewrites_it_and_the_overview():
    pub = {"overview": {"updatedAt": "t0", "fleet": {"lakes": 2}}, "fleet": {"A": {"rolledUpAt": "t0", "stale": False}}}
    new = {"control/overview": {"updatedAt": "t1", "fleet": {"lakes": 2}}, "control/fleet/A": {"rolledUpAt": "t1", "stale": True}}
    assert set(changed_control(new, pub)) == {"control/fleet/A", "control/overview"}


def test_new_nodes_are_written():
    assert set(changed_control({"control/beta/X": {"betaReadiness": "NOT_READY"}}, {})) == {"control/beta/X"}


def test_freshness_age_alone_does_not_rewrite_the_overview():
    """BRAIN_OPERATIONAL_TRUTH_V1: ageHours moves every run; the verdict and its reason carry the decision and do not embed the age."""
    pub = {"overview": {"updatedAt": "t0", "brains": {"wind": {"freshness": {"verdict": "FRESH", "ageHours": 0.4, "reason": "last successful run within the 1.5 h limit"}}}}}
    new = {"control/overview": {"updatedAt": "t1", "brains": {"wind": {"freshness": {"verdict": "FRESH", "ageHours": 0.9, "reason": "last successful run within the 1.5 h limit"}}}}}
    assert changed_control(new, pub) == {}


def test_published_score_times_prefer_the_written_block_then_the_kept_one():
    from score_brains import published_score_times
    old = {"wind": {"scoreUpdatedAt": "2026-10-13T21:13:49Z"}, "lake-brain": {"scoreUpdatedAt": "2026-10-13T18:58:18Z"}}
    upd = {"scores/lake-brain": {"scoreUpdatedAt": "2026-10-20T04:31:50Z"}}
    t = published_score_times(upd, old)
    assert t["lake-brain"] == "2026-10-20T04:31:50Z" and t["wind"] == "2026-10-13T21:13:49Z"     # HELD/unchanged -> the published block's time
