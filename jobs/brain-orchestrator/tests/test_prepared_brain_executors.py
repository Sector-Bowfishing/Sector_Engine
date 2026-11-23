"""Weather, Moon and Generation: executors PREPARED but INERT (2026-11-23).

On the live manifest none of the three has an executor, so the orchestrator never plans, starts or leases them, even under an execution control
that (wrongly) enables them. Turning one on is configuration only: the manifest target switched to its planned Cloud Run job. Moon runs after
each Weather run: DEPENDENCY_CHANGED on the weather edge, which opts out of the same-cycle deferral (Weather is due on every grant)."""
import copy
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR          # noqa: E402
from test_central_scheduling import world, stale_world   # noqa: E402,F401  (fixture)
from test_control_plane import ago, enabled_control, ALL_BRAINS   # noqa: E402
from sector_brain_platform import orchestration as O, execution_control as EC, data_ownership as DO   # noqa: E402

NEW = ("weather", "moon", "generation")
pytestmark = pytest.mark.live_manifest


def control_enabling_everything():
    c = enabled_control()
    c["brains"].update({b: {"enabled": True, "limits": {"maxRunsPerDay": 99}} for b in NEW})
    return c


def switched_on(manifest, brains=("weather", "moon")):
    """The configuration change the owner checklist makes (MOON/WEATHER plan): ACTIVE + the planned Cloud Run job, started by the orchestrator."""
    m = copy.deepcopy(manifest)
    for b in brains:
        t = m["brains"][b]["executionTarget"]
        m["brains"][b]["activityState"] = "ACTIVE"
        m["brains"][b]["executionTarget"] = {"kind": "cloud-run-job", "job": t["plannedJob"], "startedByOrchestrator": True, "scoped": False}
    return m


# ---------------------------------------------------------------------------------------------------------------- inert today
def test_the_live_manifest_gives_none_of_the_three_an_executor():
    m = O.load_manifest()
    assert OR.planned_executors(m) == {}
    for b in NEW:
        t = m["brains"][b]["executionTarget"]
        assert b not in OR.EXECUTORS and t["kind"] == "none" and t["startedByOrchestrator"] is False and m["brains"][b]["activityState"] == "PARKED"
        assert t["plannedJob"] == OR.PLANNED_EXECUTORS[b]["job"]                 # the manifest and the prepared executor name the same job
        assert not any(j.get("brainId") == b for j in m["jobs"].values())         # no job registered, nothing created
        assert m["brains"][b]["customerPublication"] is False


def test_absent_from_the_execution_control_means_disabled():
    ctl = EC.parse(enabled_control())
    for b in NEW:
        ok, why = EC.gate(ctl, b, "SCHEDULE", admin=None, starts_this_cycle=0, runs_today=0)
        assert not ok, why


def test_parked_brains_are_never_due_on_any_automatic_trigger():
    m = O.load_manifest()
    ctx = {"manifest": m, "mode": "PRE_PRODUCTION", "now": O.parse_time(ago(0)), "states": {}, "activity": O.effective_activity(m), "running": {}}
    for b in NEW:
        for trig in ("SCHEDULE", "DEPENDENCY_CHANGED", "INPUT_CHANGED"):
            d = O.decide_brain(b, trig, ctx, upstream={"brainId": "weather", "change": "CHANGED"})
            assert d["decision"] != "RUN", (b, trig, d)


def test_a_full_cycle_starts_none_of_them_even_if_the_control_enables_them(world):
    setup, calls = world
    t = stale_world(control_enabling_everything())
    t["brains"]["weather"] = {"lastSuccessfulRun": ago(5), "version": "w1", "readinessCounts": {"CALIBRATION": 2}}
    setup(t)
    assert OR.main([]) == 0
    assert not set(calls["start"]) & set(NEW) and not set(calls["inproc"]) & set(NEW) and not set(calls["plan"]) & set(NEW)


def test_dispatch_also_refuses_them_until_cortex_registers_them():
    """A second, independent lock: the Cortex identity mirror (data_ownership.json) does not know them, so M08 dispatch never runs them."""
    deferred = []
    assert OR.gate_dispatch(set(NEW), deferred) == set()
    assert {d["brainId"] for d in deferred} == set(NEW) and all("UNREGISTERED_BRAIN" in d["why"] for d in deferred)


def test_a_partial_switch_does_not_add_an_executor():
    m = copy.deepcopy(O.load_manifest())
    m["brains"]["weather"]["executionTarget"]["kind"] = "cloud-run-job"         # kind alone: no job, startedByOrchestrator still false
    assert OR.planned_executors(m) == {}
    m["brains"]["weather"]["executionTarget"].update({"job": "some-other-job", "startedByOrchestrator": True})
    assert OR.planned_executors(m) == {}


# ---------------------------------------------------------------------------------------------------------------- configuration turns it on
def test_switching_the_manifest_target_on_is_all_the_executor_needs():
    on = OR.planned_executors(switched_on(O.load_manifest(), NEW))
    assert on == OR.PLANNED_EXECUTORS


def _cycle(monkeypatch, setup, manifest, weather_last, control, prev=None):
    monkeypatch.setattr(O, "load_manifest", lambda *a, **k: manifest)
    real = DO.recognize                                                         # as after the Cortex release that registers them (turn-on step)
    monkeypatch.setattr(DO, "recognize", lambda b: {"id": b, "kind": "TARGET", "deployedAs": b, "authorizedInputs": []} if b in NEW else real(b))
    for b, ex in OR.planned_executors(manifest).items():
        monkeypatch.setitem(OR.EXECUTORS, b, ex)
    t = stale_world(control)
    t["brains"]["weather"] = {"lastSuccessfulRun": weather_last, "version": "w1", "readinessCounts": {"CALIBRATION": 2}}
    if prev is not None:
        t["control"]["orchestratorV1"] = prev
    db = setup(t)
    assert OR.main([]) == 0
    return db.get("control/orchestratorV1")


@pytest.mark.parametrize("opt_out", [True, False])
def test_moon_runs_after_each_weather_run_once_switched_on(world, monkeypatch, opt_out):
    setup, calls = world
    m = switched_on(O.load_manifest())
    if not opt_out:                                                             # the platform default: a consumer waits while its upstream runs
        for d in m["brains"]["moon"]["dependencies"]:
            d.pop("deferIfUpstreamStarted", None)
    ctl = control_enabling_everything()
    prev = _cycle(monkeypatch, setup, m, ago(0.9), ctl)                         # cycle 1: the first observation records Weather's baseline
    assert "weather" in calls["start"] and "moon" not in calls["start"] and "generation" not in calls["start"]
    calls["start"].clear()
    _cycle(monkeypatch, setup, m, ago(0.8), ctl, prev=prev)                    # cycle 2: Weather completed a new run (and is due again)
    assert "weather" in calls["start"]
    assert ("moon" in calls["start"]) is opt_out                               # without the opt-out an hourly Weather would defer Moon forever


# ---------------------------------------------------------------------------------------------------------------- job definitions
@pytest.mark.parametrize("brain", NEW)
def test_the_job_definition_refuses_without_the_owner_approval_and_creates_no_schedule(brain, tmp_path):
    import subprocess
    script = os.path.join(ROOT, "brains", brain, "deploy", "deploy-job.sh")
    r = subprocess.run(["bash", script], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, timeout=60)
    assert r.returncode == 2 and f"MICHAEL_APPROVED_{brain.upper()}_DEPLOY=yes" in r.stderr          # refuses before any gcloud call
    src = "\n".join(l for l in open(script).read().split("\n") if not l.lstrip().startswith("#"))
    for forbidden in ("scheduler jobs create", "scheduler jobs update", "scheduler jobs resume", "executionControlV1", "execution_control.py enable",
                      "add-iam-policy-binding --member serviceAccount:$SA", "iam service-accounts create", "projects add-iam-policy-binding"):
        assert forbidden not in src, forbidden
    assert f"{brain.upper()}_WRITE_APPROVED=$WRITE_INTENT" in src and 'WRITE_INTENT="${' + brain.upper() + '_WRITE_APPROVED:-0}"' in src   # off unless passed
    assert f'JOB="${{JOB:-{OR.PLANNED_EXECUTORS[brain]["job"]}}}"' in src                          # the job the prepared executor starts
    out = tmp_path / "ctx"
    r = subprocess.run(["bash", script, "--stage-only", str(out)], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, timeout=60)
    assert r.returncode == 0 and (out / "run.py").exists() and (out / "sector_brain_platform").is_dir() and (out / "knowledge" / "knowledge-release.json").exists()
    r = subprocess.run([sys.executable, "-I", "run.py", "--write"], cwd=str(out), capture_output=True, text=True, timeout=120,
                       env={"PATH": "/usr/bin:/bin", "BRAIN_RTDB_URL": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", f"{brain.upper()}_WRITE_APPROVED": "1"})
    assert r.returncode == 2 and "BLOCKED_AWAITING_APPROVED_RELEASE" in r.stderr                    # the staged image refuses: release NOT_RECORDED
