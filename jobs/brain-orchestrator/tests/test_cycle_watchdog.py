"""The cycle watchdog (Sector_Ops #51, O6.3 moved into the system): each check trips on its halt condition and ignores history before `since`; an
unreadable store never passes silently; the latch holds every later cycle (nothing granted, started or published) until the owner clears it; a new
trip latches, tries to pause the scheduler and grants nothing."""
import datetime as dt
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR                                                     # noqa: E402
from test_central_scheduling import world, stale_world                      # noqa: E402,F401  (fixture)
from test_control_plane import enabled_control, ago                          # noqa: E402
from sector_brain_platform import cycle_watchdog as WD                       # noqa: E402
from sector_brain_platform import runner_lease as RL                         # noqa: E402
from sector_brain_platform.publisher.storage import MemoryObjectStore        # noqa: E402
from sector_brain_platform.publisher_live import locks as LK                 # noqa: E402

pytestmark = [pytest.mark.watchdog, pytest.mark.live_manifest]   # the live board, as test_runner_lease_gate

NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.timezone.utc)
POLICY = {"schema": WD.POLICY_SCHEMA, "enabled": True, "since": "2026-11-06T15:44:00Z", "allowedJobs": ["brain-orchestrator", "brain-publisher"],
          "brains": {"water-clarity": {"holder": "pulse", "lakes": ["Guntersville_AL", "Lake_Hartwell_SC"]}}, "lockHeldMaxMinutes": 30,
          "pauseSchedulerJob": "brain-orchestrator"}
CTL = {"state": "ENABLED", "brains": {"water-clarity": {"enabled": True}, "wind": {"enabled": False}}}


def put(store, key, doc):
    store.put(key, json.dumps(doc).encode())


def ex(name, at):
    return {"metadata": {"name": name, "creationTimestamp": at}}


def healthy():
    s = MemoryObjectStore()
    put(s, "exports/runners/leases/water-clarity.json", {"holder": "pulse", "cycleId": "c1"})
    put(s, "exports/runners/grants/water-clarity/c1.json", {"grantedAt": "2026-11-06T15:51:08Z"})
    put(s, "artifacts/water-clarity/sha256-a/artifact.json", {"lineage": {"generatedAt": "2026-11-06T15:51:53Z"}})
    put(s, "artifacts/water-clarity/sha256-old/artifact.json", {"lineage": {"generatedAt": "2026-10-31T18:22:00Z"}})
    put(s, "publishes/water-clarity/p1/record.json", {"mode": "LIVE", "result": "PUBLISHED", "status": "COMPLETE", "live": True,
                                                       "publishedAt": "2026-11-06T17:18:18Z",
                                                       "pathSha256": {"lakes/Guntersville_AL/states/waterClarity": "x", "snapshots/Lake_Hartwell_SC/latest/waterClarity": "y"}})
    put(s, LK.lock_key("water-clarity"), {"state": "RELEASED", "at": "2026-11-06T17:18:18Z"})
    return s


EXECS = {"brain-orchestrator": [ex("brain-orchestrator-a", "2026-11-06T15:50:01Z")], "brain-publisher": [ex("brain-publisher-b", "2026-11-06T17:17:19Z")],
         "water-clarity-brain": [ex("water-clarity-brain-old", "2026-10-29T16:57:00Z")]}


def kinds(store=None, executions=EXECS, control=CTL, policy=POLICY):
    res = WD.evaluate(policy, store=store or healthy(), executions=executions, control=control, now=NOW)
    return sorted({t.kind for t in res.trips}), res


def test_the_live_system_today_is_clean_and_history_before_since_is_ignored():
    k, res = kinds()
    assert k == [] and not res.tripped and len(res.checked) == 7


def test_a_cloud_water_clarity_start_trips():
    k, _ = kinds(executions={**EXECS, "water-clarity-brain": [ex("water-clarity-brain-x", "2026-11-07T11:50:00Z")]})
    assert k == ["EXECUTION_OUTSIDE_POLICY"]


def test_a_lease_for_another_brain_or_another_holder_trips():
    s = healthy()
    put(s, "exports/runners/leases/wind.json", {"holder": "pulse"})
    assert kinds(s)[0] == ["LEASE_OUTSIDE_POLICY"]
    s = healthy()
    put(s, "exports/runners/leases/water-clarity.json", {"holder": "cloud"})
    assert kinds(s)[0] == ["LEASE_OUTSIDE_POLICY"]


def test_two_artifacts_for_one_granted_cycle_trips():
    s = healthy()
    put(s, "artifacts/water-clarity/sha256-b/artifact.json", {"lineage": {"generatedAt": "2026-11-06T16:10:00Z"}})
    assert kinds(s)[0] == ["MORE_ARTIFACTS_THAN_GRANTS"]


def test_grants_or_artifacts_for_another_brain_trip():
    s = healthy()
    put(s, "exports/runners/grants/lake-brain/c9.json", {"grantedAt": "2026-11-07T11:00:00Z"})
    put(s, "artifacts/lake-brain/sha256-l/artifact.json", {"lineage": {"generatedAt": "2026-11-07T11:10:00Z"}})
    assert kinds(s)[0] == ["ARTIFACT_OUTSIDE_POLICY", "GRANT_OUTSIDE_POLICY"]


def test_publishes_outside_the_brain_the_lakes_or_not_complete_trip():
    s = healthy()
    put(s, "publishes/lake-brain/q1/record.json", {"mode": "LIVE", "result": "PUBLISHED", "status": "COMPLETE", "live": True, "publishedAt": "2026-11-07T10:00:00Z"})
    put(s, "publishes/water-clarity/p2/record.json", {"mode": "LIVE", "result": "READBACK_MISMATCH", "status": "COMPLETE", "live": False,
                                                       "publishedAt": "2026-11-07T10:00:00Z"})
    put(s, "publishes/water-clarity/p3/record.json", {"mode": "LIVE", "result": "PUBLISHED", "status": "COMPLETE", "live": True,
                                                       "publishedAt": "2026-11-07T11:00:00Z", "pathSha256": {"/lakes/Wheeler_AL/states/waterClarity": "z"}})
    assert kinds(s)[0] == ["PUBLISH_NOT_COMPLETE", "PUBLISH_OUTSIDE_LAKES", "PUBLISH_OUTSIDE_POLICY"]


def test_a_quarantine_or_a_stuck_lock_trips():
    s = healthy()
    put(s, LK.quarantine_key("water-clarity"), {"state": "QUARANTINED"})
    put(s, LK.lock_key("water-clarity"), {"state": "HELD", "at": "2026-11-07T10:00:00Z"})
    assert kinds(s)[0] == ["LOCK_STUCK", "QUARANTINED"]


def test_the_execution_control_enabling_another_brain_trips():
    assert kinds(control={"state": "ENABLED", "brains": {"water-clarity": {"enabled": True}, "wind": {"enabled": True}}})[0] == ["CONTROL_OUTSIDE_POLICY"]
    assert kinds(control={"state": "PAUSED", "brains": {"wind": {"enabled": True}}})[0] == []      # a PAUSED control enables nothing


def test_a_pulse_fault_record_trips():
    s = healthy()
    RL.record_fault(RL.runner_view(s, "pulse"), "pulse", "water-clarity", "LEASE_RENEWAL_REFUSED", "renew exit 3", NOW)
    k, res = kinds(s)
    assert k == ["RUNNER_FAULT"] and "LEASE_RENEWAL_REFUSED" in res.trips[0].detail


def test_an_unreadable_store_is_never_a_silent_pass_and_never_latches_by_itself():
    class Broken(MemoryObjectStore):
        def list(self, prefix):
            raise OSError("bucket unreachable")
    k, res = kinds(Broken())
    assert k == ["CHECK_FAILED"] and res.unreadable and not res.tripped
    assert WD.log_line(res).startswith("[watchdog] UNREADABLE")


def test_the_latch_keeps_the_first_evidence_and_only_the_owner_clears_it():
    s = MemoryObjectStore()
    assert not WD.is_halted(WD.read_latch(s))
    first = WD.write_halt(s, [WD.Trip("RUNNER_FAULT", "a")], cycle="c1", now=NOW, scheduler_pause="PAUSED")
    again = WD.write_halt(s, [WD.Trip("QUARANTINED", "b")], cycle="c2", now=NOW, scheduler_pause="PAUSED")
    assert WD.is_halted(WD.read_latch(s)) and again == first and first["trips"][0]["kind"] == "RUNNER_FAULT"
    with pytest.raises(ValueError):
        WD.clear(s, changed_by="michael", approval_ref="", reason="x", now=NOW)
    doc = WD.clear(s, changed_by="michael", approval_ref="owner/ok", reason="fixed", now=NOW)
    assert not WD.is_halted(WD.read_latch(s)) and doc["previous"]["state"] == "HALTED"


def test_the_lock_paths_are_the_publishers_own():
    assert WD.lock_key("water-clarity") == LK.lock_key("water-clarity")
    assert WD.quarantine_key("water-clarity") == LK.quarantine_key("water-clarity")


def test_the_committed_policy_matches_the_approved_o6_scope():
    pol = WD.load_policy()
    assert pol["enabled"] and pol["allowedJobs"] == ["brain-orchestrator", "brain-publisher"]
    assert pol["brains"] == {"water-clarity": {"holder": "pulse", "lakes": ["Guntersville_AL", "Lake_Hartwell_SC"]}}
    assert pol["approvalRef"].startswith("owner-approval-")


# --------------------------------------------------------------------------------------------------------- through the real cycle (orchestrate.main)
PULSE = {"schema": "sector-runner-policy-v1", "defaultPrimary": "cloud", "primary": {"wind": "pulse"}, "failover": {"enabled": False, "brains": []}}
ARGV = ["--runner-leases", "--artifact-store-dir", "x"]


def cycle(world, monkeypatch, store, policy):
    setup, calls = world
    paused = []
    monkeypatch.setattr(OR, "build_publication_store", lambda d, b=None: store if (d or b) else None)
    monkeypatch.setattr(RL, "load_policy", lambda path=None: PULSE)
    monkeypatch.setattr(WD, "load_policy", lambda path=None: policy)
    monkeypatch.setattr(OR.gcp, "pause_scheduler_job", lambda tokens, job: paused.append(job) or {})
    ctl = enabled_control()
    ctl["brains"]["water-temp"]["enabled"] = False                           # as in test_runner_lease_gate: only Wind is due
    t = stale_world(ctl)
    t["brains"]["water-clarity"]["lastSuccessfulRun"] = ago(1)
    t["brains"]["lake-brain"]["lastSuccessfulRun"] = ago(1)
    setup(t)
    assert OR.main(ARGV) == 0
    return calls, paused


def wind_policy():
    """The scenario's execution control enables every Brain, so the test policy names them all (otherwise CONTROL_OUTSIDE_POLICY, correctly)."""
    every = ["biological-state", "depth", "lake-brain", "sector-intelligence", "vegetation", "water-clarity", "water-temp"]
    return {**POLICY, "since": "2000-01-01T00:00:00Z", "brains": {"wind": {"holder": "pulse", "lakes": []}, **{b: {"holder": "cloud"} for b in every}}}


def test_without_a_trip_the_cycle_grants_as_before(world, monkeypatch, capsys):
    store = MemoryObjectStore()
    calls, paused = cycle(world, monkeypatch, store, wind_policy())
    out = capsys.readouterr().out
    assert "[watchdog] OK" in out and paused == []
    assert RL.read(RL.orchestrator_view(store), "wind")[0]["holder"] == "pulse"          # the grant still happens


def test_a_latched_halt_holds_the_cycle_grants_nothing_and_starts_nothing(world, monkeypatch, capsys):
    store = MemoryObjectStore()
    WD.write_halt(store, [WD.Trip("RUNNER_FAULT", "earlier")], cycle="c0", now=NOW, scheduler_pause="FAILED: 403")
    calls, paused = cycle(world, monkeypatch, store, wind_policy())
    out = capsys.readouterr().out
    assert "[watchdog] HALTED since" in out and calls["start"] == [] and paused == []
    assert RL.read(RL.orchestrator_view(store), "wind")[0] is None                       # no grant


def test_a_new_trip_latches_pauses_the_scheduler_and_grants_nothing(world, monkeypatch, capsys):
    store = MemoryObjectStore()
    RL.record_fault(RL.runner_view(store, "pulse"), "pulse", "wind", "HANDOFF_FAILED_REPEATEDLY", "2 runs", NOW)
    calls, paused = cycle(world, monkeypatch, store, wind_policy())
    out = capsys.readouterr().out
    assert "[watchdog] HALT RUNNER_FAULT" in out and paused == ["brain-orchestrator"] and calls["start"] == []
    latch = WD.read_latch(store)
    assert WD.is_halted(latch) and latch["schedulerPause"] == "PAUSED" and latch["trips"][0]["kind"] == "RUNNER_FAULT"
    assert RL.read(RL.orchestrator_view(store), "wind")[0] is None


def test_a_failed_scheduler_pause_still_latches(world, monkeypatch, capsys):
    store = MemoryObjectStore()
    RL.record_fault(RL.runner_view(store, "pulse"), "pulse", "wind", "UNEXPECTED_CREDENTIAL", "x", NOW)

    def denied(tokens, job):
        raise OR.gcp.GcpError("POST ...:pause -> 403: PERMISSION_DENIED")
    setup, calls = world
    monkeypatch.setattr(OR, "build_publication_store", lambda d, b=None: store if (d or b) else None)
    monkeypatch.setattr(RL, "load_policy", lambda path=None: PULSE)
    monkeypatch.setattr(WD, "load_policy", lambda path=None: wind_policy())
    monkeypatch.setattr(OR.gcp, "pause_scheduler_job", denied)
    ctl = enabled_control()
    t = stale_world(ctl)
    setup(t)
    assert OR.main(ARGV) == 0
    latch = WD.read_latch(store)
    assert WD.is_halted(latch) and latch["schedulerPause"].startswith("FAILED") and calls["start"] == []
