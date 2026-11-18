"""Sector Ops shows the Pulse-era state: lastSuccessfulRun from the Publisher's live record, the runner lease, and the Pulse status view.
All display only: nothing here may change a decision."""
import datetime as dt
import json

from sector_brain_platform import control_state as CS
from sector_brain_platform import runner_status as PSV
from sector_brain_platform.publisher.storage import MemoryObjectStore
from sector_brain_platform import runner_lease as RL

NOW = dt.datetime(2026, 11, 18, 18, 0, tzinfo=dt.timezone.utc)


def pub(at, **kw):
    return {"publishId": "p1", "result": "PUBLISHED", "status": "COMPLETE", "live": True, "publishedAt": at, "artifactId": "a1", **kw}


def test_publication_newer_than_registry_wins():
    reg = {"lastSuccessfulRun": "2026-10-22T00:00:00Z", "lastSuccessfulRunBasis": "JOB", "publication": pub("2026-11-18T17:52:00Z")}
    assert CS.newest_success(reg) == ("2026-11-18T17:52:00Z", "PUBLICATION")


def test_registry_newer_than_publication_wins():
    reg = {"lastSuccessfulRun": "2026-11-18T17:59:00Z", "lastSuccessfulRunBasis": "JOB", "publication": pub("2026-11-18T10:00:00Z")}
    assert CS.newest_success(reg) == ("2026-11-18T17:59:00Z", "JOB")


def test_only_a_live_complete_published_record_counts():
    for bad in (pub("2026-11-18T17:52:00Z", live=False), pub("2026-11-18T17:52:00Z", result="SKIPPED"),
                pub("2026-11-18T17:52:00Z", status="FAILED"), pub("not a time")):
        reg = {"lastSuccessfulRun": "2026-10-22T00:00:00Z", "lastSuccessfulRunBasis": "JOB", "publication": bad}
        assert CS.newest_success(reg) == ("2026-10-22T00:00:00Z", "JOB"), bad


def test_no_timestamps_stays_unknown():
    assert CS.newest_success({}) == (None, None)
    assert CS.publication_view({}) is None
    assert CS.publication_view({"publication": "x"}) is None


def test_runner_view_held_and_expired():
    lease = {"holder": "pulse", "cycleId": "c", "grantedAt": "2026-11-18T17:50:00Z", "heartbeatAt": "2026-11-18T17:55:00Z",
             "leaseUntil": "2026-11-18T18:15:00Z"}
    assert CS.runner_view(lease, NOW)["held"] is True
    assert CS.runner_view({**lease, "leaseUntil": "2026-11-18T17:00:00Z"}, NOW)["held"] is False
    assert CS.runner_view(None, NOW) is None
    assert CS.runner_view({}, NOW) is None


def status(**kw):
    doc = {"schema": PSV.SCHEMA, "generatedAt": "2026-11-18T17:57:00Z", "pulseVersion": "1.4.0", "pulseCommit": "59f18b4", "state": "running",
           "paused": False, "uptimeSeconds": 3600,
           "jobs": [{"id": "water-temp-central", "enabled": True, "runPolicy": "WHILE_LEASE_HELD", "leaseHeld": False,
                     "lastStartedAt": "2026-11-18T12:50:10Z", "lastFinishedAt": "2026-11-18T12:52:00Z", "lastResult": "SUCCEEDED", "lastExitCode": 0}]}
    doc.update(kw)
    return json.dumps(doc).encode()


def test_pulse_view_fresh():
    v = PSV.build_view(status(), NOW)["pulse"]
    assert v["available"] and not v["stale"] and v["ageMinutes"] == 3.0
    assert v["jobs"]["water-temp-central"]["lastResult"] == "SUCCEEDED"


def test_pulse_view_stale_missing_unreadable_wrong_schema():
    assert PSV.build_view(status(generatedAt="2026-11-18T17:00:00Z"), NOW)["pulse"]["stale"] is True
    assert PSV.build_view(None, NOW)["pulse"] == {"available": False, "stale": True, "reason": "NO_STATUS", "checkedAt": "2026-11-18T18:00:00Z"}
    assert PSV.build_view(b"{not json", NOW)["pulse"]["reason"] == "UNREADABLE"
    assert PSV.build_view(json.dumps({"schema": "other"}), NOW)["pulse"]["reason"] == "WRONG_SCHEMA"
    assert PSV.build_view(status(generatedAt=None), NOW)["pulse"]["stale"] is True


def test_pulse_view_drops_paths_and_unknown_fields():
    v = PSV.build_view(status(state="/Users/someone/x", secret="tok", jobs=[{"id": "Bad/Id"}, {"id": "ok-job", "lastResult": "/etc/passwd",
                                                                                                        "token": "x", "enabled": True}]), NOW)["pulse"]
    assert "state" not in v and "secret" not in v
    assert list(v["jobs"]) == ["ok-job"] and v["jobs"]["ok-job"] == {"enabled": True}


def test_read_view_through_the_orchestrator_lease_view():
    store = MemoryObjectStore()
    view = RL.orchestrator_view(store)
    assert PSV.read_view(view, NOW)["pulse"]["reason"] == "NO_STATUS"
    store.put(PSV.KEY, status(), if_generation_match=0)
    assert PSV.read_view(view, NOW)["pulse"]["available"] is True


def test_runners_lives_in_summary_and_its_clock_fields_are_volatile():
    assert "runners" not in CS.SECTIONS                       # additive field inside summary: the contract's section list is unchanged
    a = {"summary": {"runners": {"pulse": {"available": True, "stale": False, "ageMinutes": 3.0, "checkedAt": "2026-11-18T18:00:00Z"}}}}
    b = {"summary": {"runners": {"pulse": {"available": True, "stale": False, "ageMinutes": 9.0, "checkedAt": "2026-11-18T19:00:00Z"}}}}
    assert CS.changed_paths(a, b) == {}
    c = {"summary": {"runners": {"pulse": {"available": True, "stale": True, "ageMinutes": 30.0}}}}
    assert "control/orchestratorV1/summary" in CS.changed_paths(c, b)


def test_pulse_view_drops_non_finite_numbers_so_the_rtdb_write_still_serializes():
    # json.loads reads NaN, Infinity and 1e999 (overflow -> inf); the RTDB client serializes with allow_nan=False, so any of them
    # reaching the control-plane write would lose the whole /control/orchestratorV1 update for every cycle.
    raw = (b'{"schema": "' + PSV.SCHEMA.encode() + b'", "generatedAt": "2026-11-18T17:57:00Z", "pulseVersion": "1.4.0", '
           b'"uptimeSeconds": NaN, "jobs": [{"id": "ok-job", "enabled": true, "lastExitCode": 1e999, "lastResult": "SUCCEEDED"}, '
           b'{"id": "neg-job", "lastExitCode": -Infinity}]}')
    v = PSV.build_view(raw, NOW)["pulse"]
    assert v["available"] is True and v["pulseVersion"] == "1.4.0"
    assert "uptimeSeconds" not in v
    assert v["jobs"]["ok-job"] == {"enabled": True, "lastResult": "SUCCEEDED"}
    assert v["jobs"]["neg-job"] == {}
    json.dumps({"runners": PSV.build_view(raw, NOW)}, allow_nan=False)   # would raise ValueError before the fix
    assert PSV.build_view(status(uptimeSeconds=12.5), NOW)["pulse"]["uptimeSeconds"] == 12.5   # finite floats still pass
