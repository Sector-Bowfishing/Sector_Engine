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


def test_pulse_primary_with_failover_off_never_starts_in_the_cloud(world, monkeypatch, capsys):
    assert "wind" not in run(world, monkeypatch, ARGV, policy=PULSE)
    assert "PRIMARY_PULSE_FAILOVER_OFF" in capsys.readouterr().out


def test_no_store_fails_closed(world, monkeypatch, capsys):
    assert "wind" not in run(world, monkeypatch, ["--runner-leases"])
    assert "NO_ARTIFACT_STORE" in capsys.readouterr().out
