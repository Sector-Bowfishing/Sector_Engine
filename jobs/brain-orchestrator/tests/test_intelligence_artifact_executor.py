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


def lease_run(cycle, monkeypatch, policy, store):
    setup, calls = cycle
    monkeypatch.setattr(OR, "build_publication_store", lambda d, b=None: store if (d or b) else None)
    monkeypatch.setattr(RL, "load_policy", lambda path=None: policy)
    setup(tree())
    assert OR.main(RUN_NOW + ["--runner-leases", "--artifact-store-dir", "x"]) == 0
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
