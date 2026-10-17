"""Actual consumption lineage through the orchestrator: a Brain's --write summary carries `consumed`; the execution record stores it (validated,
never repaired); the health plane evaluates RECORDED_CONSUMPTION for it and CURRENT_STATE for executions without lineage; recorded lineage
survives re-observation. In-memory RTDB, nothing started for real, no network."""
import datetime as dt
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR          # noqa: E402
import control_plane as CP        # noqa: E402
from sector_brain_platform import brain_health as BH, orchestration as O   # noqa: E402
from test_control_plane import FakeDb, tree, ago, NOW   # noqa: E402


def test_json_output_reads_the_summary_a_brain_prints():
    assert OR.json_output('progress...\n{"published": true, "consumed": []}')["consumed"] == []
    assert OR.json_output('{\n "a": 1,\n "consumed": [{"dependencyId": "brain:x"}]\n}')["consumed"][0]["dependencyId"] == "brain:x"
    assert OR.json_output("not json") is None and OR.json_output("") is None and OR.json_output("[1,2]") is None


class _Run:
    def __init__(self, out, rc=0):
        self.stdout, self.stderr, self.returncode = out, "", rc


def test_run_in_process_passes_valid_lineage_through_and_reports_invalid(monkeypatch):
    good = {"published": True, "consumed": [{"dependencyId": "brain:wind", "stateVersion": "1", "consumedAt": ago(0)}, {"dependencyId": "brain:lake-brain", "consumedAt": ago(0)}]}
    monkeypatch.setattr(OR.subprocess, "run", lambda *a, **k: _Run(json.dumps(good)))
    res = OR.run_in_process("biological-state")
    assert [c["dependencyId"] for c in res["consumed"]] == ["brain:lake-brain", "brain:wind"] and res["consumed"][0]["dependencyType"] == "BRAIN"
    bad = {"published": True, "consumed": [{"dependencyId": "wind?"}]}
    monkeypatch.setattr(OR.subprocess, "run", lambda *a, **k: _Run(json.dumps(bad)))
    res = OR.run_in_process("biological-state")
    assert "consumed" not in res and "dependencyId" in res["consumptionIssue"]
    monkeypatch.setattr(OR.subprocess, "run", lambda *a, **k: _Run(json.dumps({"published": False, "decision": {"action": "SKIP"}})))
    res = OR.run_in_process("biological-state")
    assert "consumed" not in res and res["skipped"] is True
    monkeypatch.setattr(OR.subprocess, "run", lambda *a, **k: _Run("boom", rc=1))
    assert OR.run_in_process("biological-state")["ok"] is False


@pytest.fixture
def cycle(monkeypatch):
    calls = {"inproc": []}

    def setup(t, summary):
        db = FakeDb(t)
        monkeypatch.setattr(OR, "BrainRtdb", lambda *a, **k: db)
        monkeypatch.setattr(OR, "TokenProvider", lambda *a, **k: object())
        monkeypatch.setattr(OR, "check_schema", lambda d: None)
        monkeypatch.setattr(OR, "sync_jobs", lambda *a, **k: ({}, {}, 0))
        monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: {"action": "PUBLISH", "reasons": ["researchVersion 1 -> 2"]} if b == "biological-state" else {"action": "SKIP", "reasons": []})
        monkeypatch.setattr(OR, "start_job", lambda b, tokens: None)
        monkeypatch.setattr(OR.subprocess, "run", lambda cmd, **k: _Run(json.dumps(summary)) if "run.py" in cmd else _Run("ok"))
        monkeypatch.setattr(CP, "scheduler_states", lambda tokens: {})
        return db
    return setup, calls


def test_execution_with_lineage_is_recorded_and_evaluated_as_recorded_consumption(cycle, tmp_path):
    setup, calls = cycle
    summary = {"published": True, "consumed": [{"dependencyId": "brain:wind", "ref": "/brains/wind", "stateVersion": "1", "generatedAt": ago(0.6), "evidenceObservedAt": ago(0.7),
                                                 "staleAfter": ago(-1), "freshnessStatus": "FRESH", "consumedAt": ago(0.01)}]}
    t = tree(); t["sources"] = {}
    db = setup(t, summary)
    out = tmp_path / "health.json"
    assert OR.main(["--emit-health-state", str(out)]) == 0
    ex = next(e for e in db.tree["control"]["orchestratorV1"]["executions"].values() if e["brainId"] == "biological-state")
    assert ex["status"] == "SUCCEEDED" and ex["consumed"][0]["dependencyId"] == "brain:wind" and ex["consumed"][0]["dependencyType"] == "BRAIN"
    st = json.load(open(out))
    bio = st["brains"]["biological-state"]
    assert bio["dependencies"]["basis"] == "RECORDED_CONSUMPTION" and bio["dependencies"]["declaredVsActual"]["consumptionRecorded"] is True
    assert bio["dependencies"]["declaredVsActual"]["declaredAndConsumed"] == ["brain:wind"]
    assert set(bio["dependencies"]["declaredVsActual"]["declaredNotConsumed"]) == {"brain:lake-brain", "brain:water-clarity", "brain:water-temp"}   # declared (legacy manifest), never read
    rows = {r["dependencyId"]: r for r in bio["dependencies"]["rows"]}
    assert rows["brain:wind"]["evaluationBasis"] == "RECORDED_CONSUMPTION" and rows["brain:wind"]["freshnessStatus"] == "FRESH" and rows["brain:wind"]["lineageRef"] == {"ref": "/brains/wind", "stateVersion": "1"}
    assert rows["brain:water-temp"]["evaluationBasis"] == "CURRENT_STATE"
    # the health plane also still contains a legacy, lineage-free view for Brains with no recorded execution
    wind = st["brains"]["wind"]
    assert wind["dependencies"]["basis"] == "CURRENT_STATE" and wind["dependencies"]["declaredVsActual"]["consumptionRecorded"] is False
    # a second cycle re-observes the execution without lineage: the record keeps it
    monkeypatch_summary = {"published": False}
    OR.main([])
    ex2 = next(e for e in db.tree["control"]["orchestratorV1"]["executions"].values() if e["executionId"] == ex["executionId"])
    assert ex2["consumed"] == ex["consumed"]


def test_invalid_lineage_from_a_brain_is_reported_on_the_execution_not_repaired(cycle):
    setup, calls = cycle
    db = setup(tree(), {"published": True, "consumed": [{"dependencyId": "brain:wind", "madeUp": True}]})
    OR.main([])
    ex = next(e for e in db.tree["control"]["orchestratorV1"]["executions"].values() if e["brainId"] == "biological-state")
    assert "consumed" not in ex and "unknown keys" in ex["consumptionIssue"]


def test_brain_without_lineage_output_stays_lineage_free(cycle):
    setup, calls = cycle
    db = setup(tree(), {"published": True})
    OR.main([])
    ex = next(e for e in db.tree["control"]["orchestratorV1"]["executions"].values() if e["brainId"] == "biological-state")
    assert "consumed" not in ex and "consumptionIssue" not in ex
