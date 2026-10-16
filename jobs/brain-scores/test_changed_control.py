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
