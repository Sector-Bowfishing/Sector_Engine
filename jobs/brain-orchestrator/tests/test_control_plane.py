"""The orchestrator cycle with the PRE_PRODUCTION decision model, against an in-memory Brain RTDB (no network, nothing started)."""
import datetime as dt
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR          # noqa: E402
import control_plane as CP        # noqa: E402
from sector_brain_platform import orchestration as O, control_state as CS   # noqa: E402

NOW = dt.datetime.now(dt.timezone.utc)


def ago(h):
    return (NOW - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeDb:
    def __init__(self, tree):
        self.tree, self.writes = tree, []

    def get(self, path, shallow=False):
        node = self.tree
        for p in path.strip("/").split("/"):
            node = node.get(p) if isinstance(node, dict) else None
            if node is None:
                return None
        return node

    def update(self, updates):
        self.writes.append(dict(updates))
        for path, val in updates.items():
            parts = path.split("/"); node = self.tree
            for p in parts[:-1]:
                node = node.setdefault(p, {})
            if val is None:
                node.pop(parts[-1], None)
            else:
                node[parts[-1]] = val


def tree(**over):
    t = {"brains": {
            "lake-brain": {"lastSuccessfulRun": ago(7), "staleAfterHours": 3, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"},
            "water-temp": {"lastSuccessfulRun": ago(17), "staleAfterHours": 6, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"},
            "wind": {"lastSuccessfulRun": ago(0.5), "staleAfterHours": 1.5, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1", "readinessCounts": {"x": 1}},
            "biological-state": {"lastSuccessfulRun": ago(30), "status": "PROFILED", "stalenessModel": "VERSION", "version": "b1"},
            "sector-intelligence": {"lastSuccessfulRun": ago(20), "fingerprint": "f1", "status": "CALIBRATION", "stalenessModel": "FINGERPRINT"}},
         "health": {"brains": {"wind": {"status": "HEALTHY"}}}, "scores": {"wind": {"value": 3.3, "basis": "COMPUTED"}}, "jobs": {}}
    t.update(over)
    return t


@pytest.fixture
def cycle(monkeypatch):
    calls = {"start": [], "inproc": [], "score": 0}

    def setup(t, plans=None):
        db = FakeDb(t)
        monkeypatch.setattr(OR, "BrainRtdb", lambda *a, **k: db)
        monkeypatch.setattr(OR, "TokenProvider", lambda *a, **k: object())
        monkeypatch.setattr(OR, "check_schema", lambda d: None)
        monkeypatch.setattr(OR, "sync_jobs", lambda *a, **k: ({}, {}, 0))
        monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: (plans or {}).get(b, {"action": "SKIP", "reasons": ["nothing to do"]}))
        monkeypatch.setattr(OR, "start_job", lambda b, tokens: calls["start"].append(b) or {"brainId": b, "how": "cloud-run-job", "ok": True, "execution": f"x/{b}-e1", "startedAt": CP.iso(NOW)})
        monkeypatch.setattr(OR, "run_in_process", lambda b, timeout=1800: calls["inproc"].append(b) or {"brainId": b, "how": "in-process", "ok": True, "seconds": 1, "tail": ""})
        monkeypatch.setattr(OR.subprocess, "run", lambda *a, **k: calls.__setitem__("score", calls["score"] + 1) or type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})())
        return db
    return setup, calls


def test_pre_production_cycle_starts_nothing_even_when_everything_is_stale(cycle):
    setup, calls = cycle
    db = setup(tree())
    assert OR.main([]) == 0
    assert calls["start"] == [] and calls["inproc"] == []                    # lake / water-temp are stale but parked/maintenance: not woken
    cp = db.tree["control"]["orchestratorV1"]
    assert cp["summary"]["engineMode"] == "PRE_PRODUCTION"
    assert "queued" not in cp["summary"] and cp["summary"]["customerPublication"] is False
    assert cp["brains"]["wind"]["decisions"]["SCHEDULE"]["decision"] == "SKIP_LEGACY_OWNED"
    deferred = db.tree["control"]["orchestrator"]["deferred"]
    assert {d["brainId"] for d in deferred} >= {"lake-brain", "water-temp"} and all("decision model" in d["why"] for d in deferred if d["brainId"] in ("lake-brain", "water-temp"))


def test_legacy_execution_flag_restores_the_old_behaviour(cycle):
    setup, calls = cycle
    setup(tree())
    OR.main(["--legacy-execution"])
    assert set(calls["start"]) == {"lake-brain", "water-temp"}


def test_biological_input_change_runs_only_because_its_own_plan_says_so(cycle):
    setup, calls = cycle
    db = setup(tree(), plans={"biological-state": {"action": "PUBLISH", "reasons": ["researchVersion 1 -> 2"]}})
    OR.main([])
    assert calls["inproc"] == ["biological-state"]
    ex = db.tree["control"]["orchestratorV1"]["executions"]
    rec = next(e for e in ex.values() if e["brainId"] == "biological-state")
    assert rec["trigger"] == "INPUT_CHANGED" and "input fingerprint changed" in rec["reason"] and rec["status"] == "SUCCEEDED"
    assert "cost" in rec and rec["cost"]["basis"] == "ESTIMATED"


def test_parked_intelligence_is_not_asked_for_a_plan_or_run(cycle, monkeypatch):
    setup, calls = cycle
    asked = []
    db = setup(tree(), plans={"sector-intelligence": {"action": "PUBLISH", "reasons": ["x"]}})
    monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: asked.append(b) or {"action": "PUBLISH", "reasons": ["x"]})
    OR.main([])
    assert "sector-intelligence" not in asked and "sector-intelligence" not in calls["inproc"]


def test_run_now_is_scoped_and_recorded(cycle):
    setup, calls = cycle
    db = setup(tree())
    OR.main(["--run-now", "biological-state", "--scope", "guntersville", "--requested-by", "michael", "--trigger", "MANUAL"])
    assert calls["inproc"] == ["biological-state"]
    cp = db.tree["control"]["orchestratorV1"]
    rec = next(e for e in cp["executions"].values() if e["brainId"] == "biological-state")
    assert rec["trigger"] == "MANUAL" and rec["scope"] == "guntersville"
    assert cp["summary"]["lastCycle"]["trigger"] == "MANUAL"


def test_run_now_for_a_parked_cloud_job_is_only_reported_never_started_implicitly(cycle):
    setup, calls = cycle
    db = setup(tree())
    OR.main(["--run-now", "water-clarity", "--scope", "guntersville"])
    assert calls["start"] == []                                                # not startable by the orchestrator: manual command is reported
    d = db.tree["control"]["orchestrator"]["deferred"]
    assert any(x["brainId"] == "water-clarity" and "gcloud run jobs execute lake-surface-dispatch" in x["why"] for x in d)


def test_second_unchanged_cycle_writes_no_control_sections(cycle):
    setup, calls = cycle
    db = setup(tree())
    OR.main([])
    OR.main([])                                  # the second cycle establishes the baseline (UNKNOWN -> UNCHANGED) and may rewrite a few sections once
    db.writes.clear()
    OR.main([])
    cp_writes = [w for w in db.writes for p in w if p.startswith("control/orchestratorV1")]
    assert cp_writes == []                                                      # content-aware: nothing material changed


def test_dry_run_writes_nothing_to_the_database(cycle):
    setup, calls = cycle
    db = setup(tree())
    # dry-run reads through the fake and keeps writes in memory
    OR.main(["--dry-run"])
    assert db.writes == [] and calls["start"] == [] and "control" not in db.tree


def test_pending_control_requests_are_validated_and_stored(cycle):
    setup, calls = cycle
    t = tree(controlRequests={"pending": {"r1": {"requestId": "r1", "requestedBy": "michael", "action": "PAUSE", "brainId": "biological-state"},
                                          "r2": {"requestId": "r2", "requestedBy": "michael", "action": "PAUSE", "brainId": "wind"},
                                          "r3": {"requestId": "r3", "requestedBy": "ops", "action": "RUN_NOW", "brainId": "water-clarity", "scope": "fleet"}}})
    db = setup(t)
    OR.main([])
    cp = db.tree["control"]["orchestratorV1"]
    assert cp["requests"]["r1"]["decision"] == "ACCEPTED" and cp["overrides"]["biological-state"]["activityState"] == "PARKED"
    assert cp["requests"]["r2"]["decision"] == "NEEDS_CONFIRMATION" and "wind" not in cp["overrides"]       # validation capture is protected
    assert cp["requests"]["r3"]["decision"] == "REJECTED"
    OR.main([])
    assert "biological-state" in db.tree["control"]["orchestratorV1"]["summary"]["parkedBrains"]            # the accepted PAUSE now governs decisions


def test_control_plane_failure_never_breaks_the_cycle_or_scores(cycle, monkeypatch):
    setup, calls = cycle
    db = setup(tree())
    monkeypatch.setattr(CS, "build_control_state", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert OR.main([]) == 0
    assert calls["score"] >= 1 and "orchestrator" in db.tree["control"]


def test_control_only_publishes_only_the_v1_namespace(cycle):
    setup, calls = cycle
    db = setup(tree())
    assert OR.main(["--control-only", "--trigger", "MANUAL"]) == 0
    paths = {p for w in db.writes for p in w}
    assert paths and all(p.startswith("control/orchestratorV1") for p in paths)            # no /jobs, no scores, no legacy /control/orchestrator
    assert calls["start"] == [] and calls["inproc"] == [] and calls["score"] == 0
    assert db.tree["control"]["orchestratorV1"]["summary"]["lastCycle"]["trigger"] == "MANUAL"
