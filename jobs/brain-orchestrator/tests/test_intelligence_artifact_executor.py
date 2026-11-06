"""SI-A2 (SECTOR_INTELLIGENCE_JOB_PLAN_V1): Sector Intelligence as a lease-only artifact job, behind SI_ARTIFACT_JOB (default off).
FAKE clients only: no production database, Cloud Run, credential or service is touched."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR                                                     # noqa: E402
from test_control_plane import cycle, tree                                   # noqa: E402,F401  (fixture)
from sector_brain_platform import runner_lease as RL                         # noqa: E402
from sector_brain_platform.publisher.storage import MemoryObjectStore        # noqa: E402

import pytest                                                                # noqa: E402

SI = "sector-intelligence"
RUN_NOW = ["--run-now", SI, "--scope", "pilots", "--requested-by", "test", "--trigger", "MANUAL", "--admin-reason", "SI-A2 test"]
CLOUD = {"schema": "sector-runner-policy-v1", "defaultPrimary": "cloud", "primary": {}, "failover": {"enabled": False, "brains": []}}
PULSE = {**CLOUD, "primary": {SI: "pulse"}}


def test_off_by_default_intelligence_stays_in_process():
    assert OR.intelligence_executor({}) == {"kind": "in-process", "dir": OR._intelligence_runtime_dir(), "jobId": "sector-intelligence-brain"}
    assert OR.intelligence_executor({"SI_ARTIFACT_JOB": "0"})["kind"] == "in-process"
    if os.environ.get("SI_ARTIFACT_JOB") != "1":
        assert OR.EXECUTORS[SI]["kind"] == "in-process"


def test_the_switch_makes_it_a_lease_only_artifact_job():
    ex = OR.intelligence_executor({"SI_ARTIFACT_JOB": "1"})
    assert ex["kind"] == "cloud-run-job" and ex["job"] == "sector-intelligence-brain"
    assert ex["leaseOnly"] and ex["artifactMode"] and ex["planInProcess"]


@pytest.fixture
def artifact_mode(monkeypatch):
    monkeypatch.setitem(OR.EXECUTORS, SI, OR.intelligence_executor({"SI_ARTIFACT_JOB": "1"}))


def test_baseline_a_manual_run_is_in_process(cycle):
    setup, calls = cycle
    setup(tree())
    assert OR.main(RUN_NOW) == 0
    assert calls["inproc"] == [SI] and calls["start"] == []


def test_artifact_mode_never_runs_in_process_nor_starts_a_cloud_job(cycle, artifact_mode, capsys):
    setup, calls = cycle
    db = setup(tree())
    assert OR.main(RUN_NOW) == 0
    assert calls["inproc"] == [] and calls["start"] == []
    assert "artifact job: lease-only, not started" in capsys.readouterr().out
    assert any(d["brainId"] == SI and "lease-only" in d["why"] for d in db.tree["control"]["orchestrator"]["deferred"])


def lease_run(cycle, monkeypatch, policy, store, extra=()):
    setup, calls = cycle
    monkeypatch.setattr(OR, "build_publication_store", lambda d, b=None: store if (d or b) else None)
    monkeypatch.setattr(RL, "load_policy", lambda path=None: policy)
    setup(tree())
    assert OR.main(RUN_NOW + ["--runner-leases", "--artifact-store-dir", "x", *extra]) == 0
    return calls


def test_with_pulse_as_primary_the_cycle_is_leased_to_pulse(cycle, artifact_mode, monkeypatch, capsys):
    store = MemoryObjectStore()
    calls = lease_run(cycle, monkeypatch, PULSE, store)
    assert calls["inproc"] == [] and calls["start"] == []
    assert f"LEASE {SI}" in capsys.readouterr().out
    lease, _ = RL.read(store, SI)
    assert lease["holder"] == "pulse" and lease["grantedBy"] == "orchestrator"


def test_with_the_cloud_as_primary_it_holds(cycle, artifact_mode, monkeypatch, capsys):
    store = MemoryObjectStore()
    calls = lease_run(cycle, monkeypatch, CLOUD, store)
    assert calls["inproc"] == [] and calls["start"] == []
    assert "artifact job: lease-only, not started" in capsys.readouterr().out
    assert RL.read(store, SI)[0] is None


def test_the_shipped_runner_policy_gives_pulse_nothing():
    """Making Pulse Intelligence's primary is an owner decision recorded in runner-policy.json (SI-A5); this change does not make it."""
    assert SI not in (RL.load_policy().get("primary") or {})


def test_artifact_mode_still_asks_intelligence_for_its_plan(cycle, monkeypatch):
    """Review of #123: the plan verdict is still computed in-process (planInProcess), so the decision inputs are the same in both modes (SI-P2 not decided)."""
    real = OR.O.effective_activity
    monkeypatch.setattr(OR.O, "effective_activity", lambda m, o: {**real(m, o), SI: "ACTIVE"})
    asked = {}
    for mode in ("0", "1"):
        monkeypatch.setitem(OR.EXECUTORS, SI, OR.intelligence_executor({"SI_ARTIFACT_JOB": mode}))
        setup, calls = cycle
        setup(tree())
        got = []
        monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: got.append(b) or {"action": "SKIP", "reasons": ["test"]})
        assert OR.main(RUN_NOW) == 0
        asked[mode] = got
    assert SI in asked["0"] and asked["0"] == asked["1"]


# -- SI-P2 option (b): the plan runs in the job (SI_JOB_PLAN, default off) ---------------------------------------------------------------------------
def test_si_job_plan_is_off_by_default_and_needs_the_artifact_job():
    assert OR.intelligence_executor({"SI_ARTIFACT_JOB": "1"})["planInProcess"] is True
    assert OR.intelligence_executor({"SI_ARTIFACT_JOB": "1", "SI_JOB_PLAN": "0"})["planInProcess"] is True
    assert OR.intelligence_executor({"SI_JOB_PLAN": "1"})["kind"] == "in-process"                 # alone it changes nothing
    ex = OR.intelligence_executor({"SI_ARTIFACT_JOB": "1", "SI_JOB_PLAN": "1"})
    assert ex["planInProcess"] is False and ex["leaseOnly"] and ex["artifactMode"]
    if os.environ.get("SI_JOB_PLAN") != "1":
        assert OR.EXECUTORS[SI].get("planInProcess", True) is not False


def test_with_si_job_plan_the_orchestrator_never_asks_for_the_plan_and_still_leases(cycle, monkeypatch, capsys):
    real = OR.O.effective_activity
    monkeypatch.setattr(OR.O, "effective_activity", lambda m, o: {**real(m, o), SI: "ACTIVE"})
    monkeypatch.setitem(OR.EXECUTORS, SI, OR.intelligence_executor({"SI_ARTIFACT_JOB": "1", "SI_JOB_PLAN": "1"}))
    asked = []
    monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: asked.append(b) or {"action": "SKIP", "reasons": ["test"]})
    store = MemoryObjectStore()
    calls = lease_run(cycle, monkeypatch, PULSE, store)
    assert SI not in asked                                                   # no Brain code of Intelligence runs in the Orchestrator
    assert calls["inproc"] == [] and calls["start"] == []
    assert f"LEASE {SI}" in capsys.readouterr().out
    assert RL.read(store, SI)[0]["holder"] == "pulse"


def test_a_skipped_runner_record_is_reconciled_as_a_skip_not_a_failure(cycle, artifact_mode, monkeypatch, capsys, tmp_path):
    """The job's SKIP (runner.py skip) for a cycle the Orchestrator granted: the next cycle counts it under skipped runs, never failed or missing."""
    import datetime as dt
    store = MemoryObjectStore()
    now = dt.datetime.now(dt.timezone.utc)
    RL.grant(RL.orchestrator_view(store), PULSE, SI, "pulse", "si-c1", now)
    RL.record_execution(RL.runner_view(store, "pulse"), "pulse", SI, "si-c1-skip", status="SKIPPED", artifact=None, cycle_id="si-c1",
                        started_at=(now - dt.timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"), ended_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        engine_commit="abc", decision={"action": "SKIP", "reasons": ["no material change"]})
    lease_run(cycle, monkeypatch, PULSE, store, extra=["--coordinate-publication", "--publication-ledger", str(tmp_path / "ledger.json")])
    out = capsys.readouterr().out
    assert "failed runs 0, skipped runs 1;" in out and "missing 0" in out
    assert '"sector-intelligence": {"failed": 0, "missingArtifacts": 0, "notRequested": 0, "published": 0, "runs": 1}' in out
