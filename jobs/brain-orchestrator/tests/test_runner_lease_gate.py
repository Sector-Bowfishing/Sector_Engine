"""--runner-leases in the real orchestrate.main() cycle (Sector_Ops #50): the cloud never starts a Brain another runner holds, nor one whose primary is Pulse
while failover is off; a missing store fails closed. Off by default: the cycle is unchanged."""
import datetime as dt
import json
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


def run(world, monkeypatch, argv, policy=CLOUD, store=None, lease_holder=None, ctl_edit=None):
    setup, calls = world
    store = store if store is not None else MemoryObjectStore()
    monkeypatch.setattr(OR, "build_publication_store", lambda d, b=None: store if (d or b) else None)
    monkeypatch.setattr(RL, "load_policy", lambda path=None: policy)
    if lease_holder:
        RL.grant(RL.orchestrator_view(store), {**policy, "primary": {"wind": lease_holder}}, "wind", lease_holder, "c0", dt.datetime.now(dt.timezone.utc))
    ctl = enabled_control()
    ctl["brains"]["water-temp"]["enabled"] = False                           # same world as test_enabled_runs_only_due_and_enabled_brains: only Wind is due
    if ctl_edit:
        ctl_edit(ctl)
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


@pytest.mark.parametrize("edit, why", [
    (lambda c: c["brains"]["wind"].update(enabled=False), "wind is not enabled in the execution control"),
    (lambda c: c["brains"].pop("wind"), "wind is not enabled in the execution control"),
    (lambda c: c.update(state="PAUSED", reason="owner pause"), "global execution control is PAUSED"),
])
def test_a_pulse_primary_brain_not_enabled_in_the_execution_control_is_held_and_never_granted(world, monkeypatch, capsys, edit, why):
    """The invariant the Lake flip (Sector_Ops #51, 2026-11-12) relies on: EC.gate runs before grant_to_primary, so a Pulse-primary Brain that the
    owner has not enabled (or a PAUSED control) gets no lease and no cloud start."""
    store = MemoryObjectStore()
    assert "wind" not in run(world, monkeypatch, ARGV, policy=PULSE, store=store, ctl_edit=edit)
    out = capsys.readouterr().out
    assert "LEASE wind" not in out and RL.read(store, "wind")[0] is None
    assert why in out or "PAUSED" in out


def test_dry_run_grants_nothing(world, monkeypatch, capsys):
    store = MemoryObjectStore()
    run(world, monkeypatch, ARGV + ["--dry-run"], policy=PULSE, store=store)
    assert "WOULD_GRANT:pulse" in capsys.readouterr().out and RL.read(store, "wind")[0] is None


def test_local_mode_makes_no_cloud_call_and_starts_no_cloud_job(world, monkeypatch, capsys, tmp_path):
    """#51 C1: --runner-mode local never syncs /jobs, never starts a Cloud Run job (a cloud-primary Brain waits) and every Cloud API call is refused."""
    from sector_brain_platform import gcp
    monkeypatch.setattr(gcp, "_DISABLED", None)                               # restored after the test (the switch is process-wide)
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "test-token")
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
    seen, envs = [], []
    monkeypatch.setattr(OR.subprocess, "run", lambda cmd, **k: seen.append(cmd) or envs.append(k.get("env")) or type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})())
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "orchestrator-token")
    monkeypatch.delenv("PUBLISHER_ACCESS_TOKEN", raising=False)
    assert OR.run_publisher_locally({"pending": 1}, auto_ok=True, may_start=True, bucket="b", live=True)["reason"] == "NO_PUBLISHER_TOKEN"
    assert seen == []                                                          # never with the orchestrator's token or a gcloud fallback
    monkeypatch.setenv("PUBLISHER_ACCESS_TOKEN", "publisher-token")
    res = OR.run_publisher_locally({"pending": 1}, auto_ok=True, may_start=True, bucket="b", live=False)
    assert envs[-1]["BRAIN_ACCESS_TOKEN"] == "publisher-token" and "PUBLISHER_ACCESS_TOKEN" not in envs[-1]
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


def test_local_mode_never_runs_an_in_process_writer(world, monkeypatch, capsys, tmp_path):
    """#51 C1 review: Sector Intelligence / Fish run in process with `run.py --write` (direct database writes). A local cycle never runs them."""
    from sector_brain_platform import gcp
    monkeypatch.setattr(gcp, "_DISABLED", None)
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "test-token")
    setup, calls = world
    ctl = enabled_control()
    t = stale_world(ctl)
    t["brains"]["wind"]["lastSuccessfulRun"] = ago(0)
    t["brains"]["water-clarity"]["lastSuccessfulRun"] = ago(1)
    t["brains"]["lake-brain"]["lastSuccessfulRun"] = ago(1)
    setup(t)
    monkeypatch.setattr(OR, "build_publication_store", lambda d, b=None: MemoryObjectStore())
    monkeypatch.setattr(RL, "load_policy", lambda path=None: CLOUD)
    assert OR.main(["--runner-mode", "local", "--artifact-store-dir", "x", "--local-lock", str(tmp_path / "l"), "--legacy-execution"]) == 0
    assert calls["inproc"] == [] and calls["plan"] == []


def test_local_mode_refuses_without_an_explicit_token(monkeypatch, capsys):
    """Review of #102: a local cycle never falls back to the gcloud login of whoever runs it."""
    monkeypatch.delenv("BRAIN_ACCESS_TOKEN", raising=False)
    assert OR.main(["--runner-mode", "local"]) == 2
    assert "needs BRAIN_ACCESS_TOKEN" in capsys.readouterr().err


def test_a_recent_grant_is_not_repeated_and_counts_against_the_daily_cap(world, monkeypatch, capsys):
    """Review of #102: until the Brain publishes, the primary gets at most one cycle per staleness window, and today's grants count as runs."""
    store = MemoryObjectStore()
    run(world, monkeypatch, ARGV, policy=PULSE, store=store)
    capsys.readouterr()
    lease = json.loads(store.get(RL.lease_key("wind")))
    store.put(RL.lease_key("wind"), json.dumps({**lease, "leaseUntil": "2000-01-01T00:00:00Z"}).encode())   # the lease expired, nothing was published
    assert "wind" not in run(world, monkeypatch, ARGV, policy=PULSE, store=store)
    assert "GRANTED_RECENTLY:pulse" in capsys.readouterr().out
    assert OR.runner_grants_today(type("A", (), {"artifact_store_dir": "x", "artifact_bucket": None})(), "wind", dt.datetime.now(dt.timezone.utc)) == 1


def test_regrant_cooldown_reads_the_staleness_window_from_the_control_manifest():
    """Sector_Ops #51 prep: the control manifest keeps staleAfterHours under `freshness`. Reading it at the top level gave every Brain the 6 h default, so
    Water Clarity (26 h) would have been granted up to four cycles a day while nothing was published."""
    man = OR.O.load_manifest()
    assert OR.regrant_cooldown_minutes(man, "water-clarity") == 26 * 60
    assert OR.regrant_cooldown_minutes(man, "lake-brain") == 26 * 60
    assert OR.regrant_cooldown_minutes(man, "water-temp") == 6 * 60
    assert OR.regrant_cooldown_minutes(man, "wind") == 90                                      # 1.5 h, above the 20 min lease TTL


def test_regrant_cooldown_defaults_and_floor():
    assert OR.regrant_cooldown_minutes({"brains": {"x": {}}}, "x") == 360                     # no window: 6 h
    assert OR.regrant_cooldown_minutes({"brains": {}}, "missing") == 360
    assert OR.regrant_cooldown_minutes({"brains": {"x": {"staleAfterHours": 3}}}, "x") == 180   # a top-level value is still honoured
    assert OR.regrant_cooldown_minutes({"brains": {"x": {"freshness": {"staleAfterHours": 0.1}}}}, "x") == RL.DEFAULT_TTL_MINUTES   # never below the lease TTL
