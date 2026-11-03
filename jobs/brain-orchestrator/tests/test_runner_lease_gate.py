"""--runner-leases in the real orchestrate.main() cycle (Sector_Ops #50): the cloud never starts a Brain another runner holds, nor one whose primary is Pulse
while failover is off; a missing store fails closed. Off by default: the cycle is unchanged."""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR                                                     # noqa: E402
from test_central_scheduling import world, stale_world                      # noqa: E402,F401  (fixture)
from test_control_plane import enabled_control, ago                          # noqa: E402
from sector_brain_platform import runner_lease as RL                         # noqa: E402
from sector_brain_platform.publisher.storage import MemoryObjectStore        # noqa: E402

import pytest                                                                # noqa: E402

pytestmark = pytest.mark.live_manifest                                       # the live board, as test_central_scheduling

CLOUD = {"schema": "sector-runner-policy-v1", "defaultPrimary": "cloud", "primary": {}, "failover": {"enabled": False, "brains": []}}
PULSE = {**CLOUD, "primary": {"wind": "pulse"}}
ARGV = ["--runner-leases", "--artifact-store-dir", "x"]


def run(world, monkeypatch, argv, policy=CLOUD, store=None, lease_holder=None):
    setup, calls = world
    store = store if store is not None else MemoryObjectStore()
    monkeypatch.setattr(OR, "build_publication_store", lambda d, b=None: store if (d or b) else None)
    monkeypatch.setattr(RL, "load_policy", lambda path=None: policy)
    if lease_holder:
        RL.grant(RL.orchestrator_view(store), {**policy, "primary": {"wind": lease_holder}}, "wind", lease_holder, "c0", dt.datetime.now(dt.timezone.utc))
    ctl = enabled_control()
    ctl["brains"]["water-temp"]["enabled"] = False                           # same world as test_enabled_runs_only_due_and_enabled_brains: only Wind is due
    t = stale_world(ctl)
    t["brains"]["water-clarity"]["lastSuccessfulRun"] = ago(1)
    t["brains"]["lake-brain"]["lastSuccessfulRun"] = ago(1)
    setup(t)
    assert OR.main(argv) == 0
    return calls["start"]


def test_off_by_default_the_cycle_is_unchanged(world, monkeypatch):
    monkeypatch.setattr(RL, "cloud_may_start", lambda *a, **k: (_ for _ in ()).throw(AssertionError("lease consulted without --runner-leases")))
    assert "wind" in run(world, monkeypatch, [])


def test_cloud_primary_without_a_lease_starts(world, monkeypatch):
    assert "wind" in run(world, monkeypatch, ARGV)


def test_a_fresh_pulse_lease_keeps_the_cloud_job_from_starting(world, monkeypatch, capsys):
    assert "wind" not in run(world, monkeypatch, ARGV, lease_holder="pulse")
    assert "runner lease: HELD_BY_PULSE" in capsys.readouterr().out


def test_pulse_primary_is_granted_the_lease_and_never_started_in_the_cloud(world, monkeypatch, capsys):
    """#51 C1: the Orchestrator grants the policy primary its cycle instead of starting a Cloud Run job; a fresh lease is not granted twice."""
    store = MemoryObjectStore()
    assert "wind" not in run(world, monkeypatch, ARGV, policy=PULSE, store=store)
    assert "LEASE wind" in capsys.readouterr().out
    lease, _ = RL.read(store, "wind")
    assert lease["holder"] == "pulse" and lease["grantedBy"] == "orchestrator"
    assert "wind" not in run(world, monkeypatch, ARGV, policy=PULSE, store=store)
    assert "CYCLE_IN_PROGRESS:pulse" in capsys.readouterr().out


def test_dry_run_grants_nothing(world, monkeypatch, capsys):
    store = MemoryObjectStore()
    run(world, monkeypatch, ARGV + ["--dry-run"], policy=PULSE, store=store)
    assert "WOULD_GRANT:pulse" in capsys.readouterr().out and RL.read(store, "wind")[0] is None


def test_local_mode_makes_no_cloud_call_and_starts_no_cloud_job(world, monkeypatch, capsys, tmp_path):
    """#51 C1: --runner-mode local never syncs /jobs, never starts a Cloud Run job (a cloud-primary Brain waits) and every Cloud API call is refused."""
    from sector_brain_platform import gcp
    monkeypatch.setattr(gcp, "_DISABLED", None)                               # restored after the test (the switch is process-wide)
    synced = []
    setup, calls = world
    real_setup = setup

    def setup_local(t, executions=None):
        db = real_setup(t, executions)
        monkeypatch.setattr(OR, "sync_jobs", lambda *a, **k: synced.append(1) or ({}, {}, 0))
        return db
    argv = ["--runner-mode", "local", "--artifact-store-dir", "x", "--local-lock", str(tmp_path / "cycle.lock")]
    assert "wind" not in run((setup_local, calls), monkeypatch, argv)                  # cloud primary: held, not started
    out = capsys.readouterr().out
    assert "local runner mode: cloud primary, not started" in out and synced == []
    with pytest.raises(gcp.CloudCallsDisabled):
        gcp.list_run_jobs(object())


def test_local_cycle_lock_refuses_an_overlapping_cycle(tmp_path):
    a, b = OR.LocalCycleLock(str(tmp_path / "l")), OR.LocalCycleLock(str(tmp_path / "l"))
    assert a.acquire() and not b.acquire()


def test_local_publisher_pass_is_a_dry_run_unless_live(monkeypatch):
    seen = []
    monkeypatch.setattr(OR.subprocess, "run", lambda cmd, **k: seen.append(cmd) or type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})())
    res = OR.run_publisher_locally({"pending": 1}, auto_ok=True, may_start=True, bucket="b", live=False)
    assert res["started"] and res["ok"] and "--live" not in seen[-1] and seen[-1][1].endswith("publish_job.py")
    OR.run_publisher_locally({"pending": 1}, auto_ok=True, may_start=True, bucket="b", live=True)
    assert "--live" in seen[-1]
    assert OR.run_publisher_locally({"pending": 1}, auto_ok=False, may_start=True, bucket="b", live=True)["reason"] == "EXECUTION_PAUSED"
    assert OR.run_publisher_locally({"pending": 0}, auto_ok=True, may_start=True, bucket="b", live=False)["reason"] == "NOTHING_PENDING"


def test_no_store_fails_closed(world, monkeypatch, capsys):
    assert "wind" not in run(world, monkeypatch, ["--runner-leases"])
    assert "NO_ARTIFACT_STORE" in capsys.readouterr().out



def test_runner_execution_without_its_lease_is_not_reconciled():
    """The publication-stage filter orchestrate.py uses: only executions whose runner holds the granted cycle are passed on; the rest are skipped."""
    store = MemoryObjectStore()
    pol = {**CLOUD, "primary": {"water-clarity": "pulse"}}
    RL.grant(RL.orchestrator_view(store), pol, "water-clarity", "pulse", "c2", dt.datetime.now(dt.timezone.utc))
    kw = dict(status="SUCCEEDED", started_at="2026-11-02T12:00:00Z", ended_at="2026-11-02T12:01:00Z", artifact=None, engine_commit=None)
    pulse = RL.runner_view(store, "pulse")
    RL.record_execution(pulse, "pulse", "water-clarity", "ok", cycle_id="c2", **kw)
    RL.record_execution(pulse, "pulse", "water-clarity", "old", cycle_id="c1", **kw)
    RL.record_execution(pulse, "pulse", "water-clarity", "seen", cycle_id="c2", **kw)
    kept, skipped = RL.reconcilable_executions(RL.orchestrator_view(store), {"water-clarity"}, exclude={"seen"})
    assert [e["executionId"] for e in kept] == ["ok"] and [e["executionId"] for e in skipped] == ["old"]
