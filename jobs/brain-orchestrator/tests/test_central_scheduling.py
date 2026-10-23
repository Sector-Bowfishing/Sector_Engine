"""Central Brain scheduling and cost shutdown (owner directive 2026-10-23; Rehtac Cortex 2.7.0 PL-15..PL-18, BR-21), on the LIVE execution manifest:
one scheduling authority, a fail-closed global execution control, per-Brain enablement, no catch-up burst, limits, duplicate protection,
explicit admin runs, and deploy scripts that can never reactivate a schedule."""
import glob
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR          # noqa: E402
from test_control_plane import FakeDb, tree, ago, NOW, enabled_control, ALL_BRAINS   # noqa: E402,F401
from sector_brain_platform import orchestration as O, execution_control as EC, brain_operations as BOPS   # noqa: E402

pytestmark = pytest.mark.live_manifest


@pytest.fixture
def world(monkeypatch):
    calls = {"start": [], "inproc": [], "shadow": [], "plan": []}

    def setup(t, executions=None):
        db = FakeDb(t)
        monkeypatch.setattr(OR, "BrainRtdb", lambda *a, **k: db)
        monkeypatch.setattr(OR, "TokenProvider", lambda *a, **k: object())
        monkeypatch.setattr(OR, "check_schema", lambda d: None)
        monkeypatch.setattr(OR, "sync_jobs", lambda *a, **k: ({}, executions or {}, 0))
        monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: calls["plan"].append(b) or {"action": "PUBLISH", "reasons": ["inputs changed"]})
        monkeypatch.setattr(OR, "start_job", lambda b, tokens: calls["start"].append(b) or {"brainId": b, "how": "cloud-run-job", "ok": True,
                                                                                          "execution": f"x/{b}-e1", "startedAt": OR.iso(NOW)})
        monkeypatch.setattr(OR, "run_in_process", lambda b, timeout=1800: calls["inproc"].append(b) or {"brainId": b, "how": "in-process", "ok": True, "seconds": 1, "tail": ""})
        monkeypatch.setattr(OR.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})())
        monkeypatch.setattr(OR, "run_shadow", lambda b, timeout=900: calls["shadow"].append(b) or {"brainId": b, "ok": False, "exit": 2, "seconds": 0, "output": None})
        return db
    return setup, calls


def stale_world(control):
    """Everything stale: without the control every due Brain would start."""
    t = tree()
    t["brains"]["wind"]["lastSuccessfulRun"] = ago(9)
    t["brains"]["water-clarity"] = {"lastSuccessfulRun": ago(200), "staleAfterHours": 26, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"}
    t["brains"]["lake-brain"]["lastSuccessfulRun"] = ago(40)
    if control is None:
        t.pop("control", None)
    else:
        t["control"] = {"executionControlV1": control}
    return t


# 1, 12 ---------------------------------------------------------------- global PAUSED fails closed; no work at all
@pytest.mark.parametrize("control", [None, {"schema": "brain-execution-control-v1", "state": "PAUSED"}, {"schema": "nope", "state": "ENABLED"},
                                     {"schema": "brain-execution-control-v1", "state": "ENABLED"},              # ENABLED without approvalRef
                                     {"schema": "brain-execution-control-v1", "state": "RUNNING", "approvalRef": "x"}, "garbage"])
def test_global_paused_or_unverifiable_control_starts_nothing(world, control):
    setup, calls = world
    setup(stale_world(control))
    assert OR.main(["--run-shadow-lane"]) == 0
    assert calls == {"start": [], "inproc": [], "shadow": [], "plan": []}          # no worker, no plan check (providers), no SHADOW lane


def test_unreadable_control_is_paused(world, monkeypatch):
    setup, calls = world
    db = setup(stale_world(enabled_control()))
    real = db.get
    monkeypatch.setattr(db, "get", lambda path, *a, **k: (_ for _ in ()).throw(OSError("rtdb down")) if path == EC.NODE else real(path, *a, **k))
    assert OR.main([]) == 0 and calls["start"] == [] and calls["inproc"] == []


# 2, 3, 9 -------------------------------------------------------------- Wind and Lake cannot schedule themselves; deployments never resume
def test_wind_and_lake_have_no_independent_schedule():
    m = O.load_manifest()
    for bid in ("wind", "lake-brain"):
        sch = m["brains"][bid]["schedule"]
        assert sch["owner"] == "ORCHESTRATOR" and sch["scheduler"] == "brain-orchestrator" and sch["deprecatedScheduler"]["state"] == "PAUSED"
        assert m["brains"][bid]["executionTarget"]["startedByOrchestrator"] is True
    assert OR.EXECUTORS["wind"]["job"] == "wind-hourly" and OR.EXECUTORS["lake-brain"]["job"] == "lake-brain"


def test_no_deploy_script_can_create_or_resume_a_schedule():
    scripts = glob.glob(os.path.join(ROOT, "**", "deploy-job.sh"), recursive=True) + glob.glob(os.path.join(ROOT, "jobs", "*", "*.sh"))
    assert scripts
    for f in set(scripts):
        src = "\n".join(l for l in open(f).read().split("\n") if not l.lstrip().startswith("#"))   # executable lines only
        assert "scheduler jobs resume" not in src and "SCHEDULE_STATE" not in src, f
        if "scheduler jobs create" in src or "scheduler jobs update" in src:
            assert f.endswith(os.path.join("brain-orchestrator", "deploy-job.sh")), f"{f} manages a scheduler (only the central trigger's definition may be)"
            tail = src[src.index("scheduler jobs create"):]
            assert "scheduler jobs pause" in tail and "refusing to report success" in tail      # created/updated, then ALWAYS paused and verified
    resume = open(os.path.join(ROOT, "tools", "ops", "resume-orchestrator.sh")).read()
    assert "OWNER_APPROVAL_REF:?" in resume and "executionControlV1" in resume and "--dry-run" in resume   # the only resume path is owner-gated


# 4 -------------------------------------------------------------------- all eight Brains are registered with the one authority
def test_all_eight_brains_are_registered_with_the_orchestrator():
    m = O.load_manifest()
    assert set(m["brains"]) == set(ALL_BRAINS)
    for bid, b in m["brains"].items():
        runs_here = bid in OR.EXECUTORS or (b.get("shadowLane") or {}).get("enabled")
        assert runs_here, f"{bid} has no orchestrator execution path"
        bj = json.load(open(os.path.join(ROOT, "brains", {"biological-state": "fish", "lake-brain": "lake", "water-temp": "water-temperature"}.get(bid, bid), "brain.json")))
        ex = bj["operations"]["execution"]
        assert ex["authority"] == "brain-orchestrator" and ex["independentSchedule"] is False and ex["trigger"] in ("TIME", "EVENT", "SHADOW")


# 5, 6 ----------------------------------------------------------------- only eligible, changed Brains run when ENABLED
def test_enabled_runs_only_due_and_enabled_brains(world):
    setup, calls = world
    ctl = enabled_control()
    ctl["brains"]["water-temp"]["enabled"] = False                                 # per-Brain pause beneath the global control
    t = stale_world(ctl)
    t["brains"]["water-clarity"]["lastSuccessfulRun"] = ago(1)                     # fresh: unchanged, not due
    t["brains"]["lake-brain"]["lastSuccessfulRun"] = ago(1)
    setup(t)
    assert OR.main([]) == 0
    assert "water-temp" not in calls["start"] and "water-clarity" not in calls["start"] and "lake-brain" not in calls["start"]
    assert calls["start"] == ["wind"]


def test_unchanged_inputs_start_nothing(world):
    setup, calls = world
    t = tree()
    for b in ("water-temp", "lake-brain", "wind"):
        t["brains"][b]["lastSuccessfulRun"] = ago(0.2)
    t["brains"]["water-clarity"] = {"lastSuccessfulRun": ago(1), "staleAfterHours": 26, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"}
    setup(t)
    assert OR.main([]) == 0 and calls["start"] == []


# 12, 13 --------------------------------------------------------------- no catch-up burst; per-Brain limits
def test_resuming_after_a_long_pause_starts_at_most_max_starts_per_cycle(world):
    setup, calls = world
    setup(stale_world(enabled_control(limits={"maxStartsPerCycle": 2})))
    assert OR.main([]) == 0
    assert len(calls["start"]) + len(calls["inproc"]) == 2                          # the rest wait for later cycles; nothing is replayed


def test_runs_per_day_and_cost_per_day_limits_hold_a_brain():
    ctl = EC.parse(enabled_control())
    ctl["brains"]["wind"]["limits"].update({"maxRunsPerDay": 3, "maxCostPerDay": 0.5})
    assert EC.gate(ctl, "wind", "SCHEDULE", admin=None, starts_this_cycle=0, runs_today=3)[0] is False
    ok, why = EC.gate(ctl, "wind", "SCHEDULE", admin=None, starts_this_cycle=0, runs_today=0, cost_today=0.6)
    assert not ok and "maxCostPerDay" in why
    assert EC.gate(ctl, "wind", "SCHEDULE", admin=None, starts_this_cycle=0, runs_today=0, cost_today=0.1)[0] is True


# 7 -------------------------------------------------------------------- duplicates: single-flight and no overlapping cycles
def test_an_overlapping_orchestrator_cycle_starts_nothing(world, monkeypatch):
    setup, calls = world
    running = {"metadata": {"name": "brain-orchestrator-other"}, "status": {"runningCount": 1}}
    setup(stale_world(enabled_control()), executions={"brain-orchestrator": [running]})
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "brain-orchestrator-me")
    monkeypatch.setattr(OR.gcp, "running_executions", lambda ex: [e for e in ex if (e.get("status") or {}).get("runningCount")])
    assert OR.main([]) == 0 and calls["start"] == [] and calls["inproc"] == []


def test_a_brain_already_running_is_not_started_twice(world, monkeypatch):
    setup, calls = world
    running = {"metadata": {"name": "wind-hourly-x"}, "status": {"runningCount": 1}}
    t = stale_world(enabled_control())
    t["control"]["orchestrator"] = {"locks": {"wind": {"lockedUntil": OR.iso(NOW.replace(year=NOW.year + 1)), "execution": "x/wind-hourly-x"}}}
    setup(t, executions={"wind-hourly": [running]})
    monkeypatch.setattr(OR.gcp, "running_executions", lambda ex: [e for e in ex if (e.get("status") or {}).get("runningCount")])
    assert OR.main([]) == 0 and "wind" not in calls["start"]


# admin runs ------------------------------------------------------------ explicit, recorded, allowed while PAUSED, never re-enable
def test_admin_run_needs_a_reason_and_is_recorded(world):
    setup, calls = world
    db = setup(stale_world({"schema": "brain-execution-control-v1", "state": "PAUSED"}))
    OR.main(["--run-now", "biological-state", "--scope", "guntersville", "--trigger", "MANUAL"])
    assert calls["inproc"] == []                                                   # no reason: refused
    OR.main(["--run-now", "biological-state", "--scope", "guntersville", "--trigger", "MANUAL", "--requested-by", "owner", "--admin-reason", "pilot evidence"])
    assert calls["inproc"] == ["biological-state"] and calls["start"] == []       # only that Brain, nothing automatic
    rec = next(e for e in db.tree["control"]["orchestratorV1"]["executions"].values() if e["brainId"] == "biological-state")
    assert rec["admin"] == {"requestedBy": "owner", "reason": "pilot evidence"}
    assert db.tree["control"]["executionControlV1"]["state"] == "PAUSED"         # the orchestrator never writes the control


# 10, 11 --------------------------------------------------------------- shadow stays experimental and paused; gates intact
def test_shadow_lane_runs_only_when_enabled_and_stays_experimental(world):
    setup, calls = world
    setup(stale_world({"schema": "brain-execution-control-v1", "state": "PAUSED"}))
    OR.main(["--run-shadow-lane", "--force-shadow-lane"])
    assert calls["shadow"] == []
    setup(stale_world(enabled_control()))
    OR.main(["--run-shadow-lane", "--force-shadow-lane"])
    assert sorted(calls["shadow"]) == ["depth", "vegetation"]
    m = O.load_manifest()
    assert m["brains"]["depth"]["activityState"] == m["brains"]["vegetation"]["activityState"] == "PARKED"     # approved path still abstains
    assert all(b["customerPublication"] is False and O.publish_allowed(m["engineMode"], b) is False for b in m["brains"].values())


# status ----------------------------------------------------------------- a paused Brain is never reported running
def test_status_reports_paused_not_active_while_the_control_is_paused():
    row = {"lastSuccessfulRun": "2026-10-23T02:00:00Z", "lastExecution": {"at": "2026-10-23T02:00:00Z", "status": "SUCCEEDED"}}
    b = O.load_manifest()["brains"]["wind"]
    import datetime as dt
    now = dt.datetime(2026, 10, 23, 2, 30, tzinfo=dt.timezone.utc)
    live = BOPS.live("wind", b, row, scheduler_states={"brain-orchestrator": "ENABLED"}, shadow_doc=None, plan=None, now=now)
    assert live["internalOperation"]["status"] == "ACTIVE"                          # evidence alone would say ACTIVE ...
    paused = BOPS.apply_control(live, "wind", EC.parse({"schema": "brain-execution-control-v1", "state": "PAUSED"}))
    assert paused["internalOperation"]["status"] == "PAUSED" and paused["internalOperation"]["executionControl"]["global"] == "PAUSED"
    assert paused["runtimeReadiness"]["status"] == "READY" and paused["internalOperation"]["lastExecutionResult"] == "SUCCEEDED"   # evidence kept
    off = BOPS.apply_control(live, "wind", EC.parse({**enabled_control(), "brains": {"wind": {"enabled": False}}}))
    assert off["internalOperation"]["status"] == "PAUSED"
    failed = dict(live, internalOperation={**live["internalOperation"], "status": "FAILED"})
    assert BOPS.apply_control(failed, "wind", EC.parse(None))["internalOperation"]["status"] == "FAILED"   # a real failure is never hidden


def test_execution_control_documents_refuse_enabled_without_approval():
    with pytest.raises(ValueError):
        EC.document("ENABLED", brains={}, changed_by="x", changed_at="t", approval_ref=None, reason="r")
    d = EC.document("PAUSED", brains={}, changed_by="x", changed_at="t", approval_ref=None, reason="r")
    assert EC.parse(d)["state"] == "PAUSED" and EC.parse(d)["valid"] is True
    assert re.search(r"never", d["note"])
