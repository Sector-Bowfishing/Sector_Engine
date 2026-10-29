"""Cortex 3.1: the Orchestrator recognizes the nine target Brains, preserves the combined biological-state, and dispatches each task only to its owner (M08)."""
import json
import os

import pytest

from sector_brain_platform import data_ownership as DO
from sector_brain_platform import task_routing as TR
from sector_brain_platform.orchestrator import DEFAULT_ORDER, plan

_DEV = os.path.expanduser("~/Desktop/Development/Rehtac/Cortex")
if not os.environ.get("CORTEX_HOME") and os.path.exists(os.path.join(_DEV, "tools", "cortex.py")):
    os.environ["CORTEX_HOME"] = _DEV                                      # tests only: use the developer's checkout when CORTEX_HOME is unset
CORTEX = TR.cortex_tool()
needs_cortex = pytest.mark.skipif(CORTEX is None, reason="Cortex checkout not present")


def test_all_nine_target_brains_are_recognized_with_their_deployed_identity():
    assert len(DO.target_ids()) == 9 and set(DO.target_ids()) == {"fish-knowledge", "fish-behavior", "wind", "water-clarity", "lake-brain", "water-temp", "depth", "vegetation", "sector-intelligence"}
    assert DO.recognize("wind")["kind"] == "TARGET" and DO.recognize("fish-behavior")["deployedAs"] == "biological-state"
    assert DO.recognize("nonsense")["kind"] == "UNREGISTERED"


def test_biological_state_stays_the_frozen_combined_identity_and_is_never_reassigned():
    r = DO.recognize("biological-state")
    assert r["kind"] == "LEGACY_COMBINED" and r["targets"] == ["fish-knowledge", "fish-behavior"] and r["frozen"] is True
    assert DO.recognize("fish")["kind"] == "ALIAS" and DO.recognize("biological-brain")["canonical"] == "biological-state"          # aliases are names, never Brain identities


def test_target_dependency_order_runs_specialists_and_fish_then_biological_then_intelligence():
    o = DO.execution_order()
    assert o.index("fish-knowledge") < o.index("fish-behavior") < o.index("sector-intelligence")
    for env in ("wind", "water-clarity", "lake-brain", "water-temp", "depth", "vegetation"):
        assert o.index(env) < o.index("fish-behavior")
    assert o.index("lake-brain") < o.index("depth") < o.index("vegetation") and o[-1] == "sector-intelligence"
    d = DO.deployed_execution_order(["sector-intelligence", "biological-state", "vegetation", "wind", "depth", "lake-brain", "water-temp", "water-clarity"])
    assert d[-2:] == ["biological-state", "sector-intelligence"] and d.index("vegetation") < d.index("biological-state")


def test_the_legacy_planner_orders_all_eight_deployed_brains_by_the_target_order_when_nothing_else_decides():
    assert list(DEFAULT_ORDER) == DO.deployed_execution_order(list(DO.BRAINS))
    now = __import__("datetime").datetime(2026, 10, 28, tzinfo=__import__("datetime").timezone.utc)
    p = plan({b: {"dependsOn": []} for b in DO.BRAINS}, {}, now)
    assert p["order"][-2:] == ["biological-state", "sector-intelligence"]


def test_the_engine_mirror_matches_cortex_when_cortex_is_present():
    if CORTEX is None:
        pytest.skip("Cortex checkout not present")
    root = os.path.join(os.path.dirname(os.path.dirname(CORTEX)), "projects", "sector", "shared", "data")
    reg = json.load(open(os.path.join(root, "firebase-data-contracts.json")))
    arch = json.load(open(os.path.join(root, "brain-architecture.json")))
    mine = DO.mirror()
    assert [(f["id"], f["pattern"], f["writer"], f.get("targetWriter"), f["status"]) for f in reg["families"]] == [(f["id"], f["pattern"], f["writer"], f["targetWriter"], f["status"]) for f in mine["families"]]
    assert [(b["id"], b["deployedAs"], b["authorizedInputs"]) for b in arch["brains"]] == [(b["id"], b["deployedAs"], b["authorizedInputs"]) for b in mine["targetBrains"]]


def audit_report(*findings):
    return {"findings": list(findings)}


def test_wrong_owner_tasks_are_rerouted_blocked_or_dispatched_and_unaudited_work_never_runs():
    tasks = [{"id": "T1", "brain": "fish-knowledge", "title": "forecast reservoir water levels"}, {"id": "T2", "brain": "wind", "title": "wind exposure"}, {"id": "T3", "brain": "ghost", "title": "x"},
             {"id": "T4", "brain": "depth", "title": "y"}]
    rep = audit_report({"kind": "WRONG_OWNER", "subject": "task T1", "correctOwner": "lake-brain", "correction": "belongs to Lake", "id": "MA-1"},
                       {"kind": "UNAUTHORIZED_INPUT", "subject": "task T4", "correction": "depth may not consume sector-intelligence", "id": "MA-2"})
    g = TR.dispatch_gate(tasks, audit=rep)
    assert [t["id"] for t in g["dispatch"]] == ["T2"] and g["rerouted"][0]["to"] == "lake-brain" and g["rerouted"][0]["task"]["brain"] == "lake-brain"
    assert {b["id"]: b["kind"] for b in g["blocked"]} == {"T3": "UNREGISTERED_BRAIN", "T4": "UNAUTHORIZED_INPUT"}
    none = TR.dispatch_gate(tasks[:2], audit=None, tool=None, runner=lambda *a, **k: None)
    assert none["unverified"] is True or none["dispatch"] == []                                       # without Cortex nothing is dispatched


def test_without_a_cortex_tool_nothing_is_dispatched(monkeypatch):
    monkeypatch.setattr(TR, "cortex_tool", lambda env=None: None)
    g = TR.dispatch_gate([{"id": "T1", "brain": "wind", "title": "wind exposure"}])
    assert g["unverified"] is True and g["dispatch"] == [] and g["blocked"][0]["kind"] == "UNVERIFIED"


@needs_cortex
def test_real_cortex_mission_audit_reroutes_a_wrong_owner_task():
    g = TR.dispatch_gate([{"id": "T1", "brain": "fish-knowledge", "title": "forecast reservoir water levels for Lake Hartwell"}, {"id": "T2", "brain": "wind", "title": "measure shoreline wind exposure"}])
    assert g["rerouted"] and g["rerouted"][0]["to"] == "lake-brain" and [t["id"] for t in g["dispatch"]] == ["T2"]
