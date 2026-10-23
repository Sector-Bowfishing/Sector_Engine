"""The executor's pure parts: single-flight from real executions / locks, job args per scope, plan → execution policy."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import orchestrate as o  # noqa: E402

NOW = dt.datetime(2026, 10, 13, 6, 50, tzinfo=dt.timezone.utc)


def test_running_execution_or_lock_means_wait():
    brains = {"lake-brain": {"staleAfterHours": 3, "lastSuccessfulRun": "2026-10-12T23:46:54Z"},
              "water-temp": {"staleAfterHours": 6, "lastSuccessfulRun": "2026-10-12T06:40:17Z"}}
    execs = {"lake-brain": [{"metadata": {"name": "lake-brain-x"}, "status": {"startTime": "2026-10-13T06:45:00Z"}}]}
    locks = {"water-temp": {"lockedUntil": "2026-10-13T07:00:00Z"}}
    merged = o.with_single_flight(brains, execs, locks, NOW)
    assert merged["lake-brain"]["schedule"]["running"] is True
    assert merged["water-temp"]["schedule"]["lockedUntil"] == "2026-10-13T07:00:00Z"
    plan = o.orchestrate(merged, {}, NOW)
    assert {w["brainId"] for w in plan["waiting"]} == {"lake-brain", "water-temp"} and plan["runs"] == []
    # expired lock, finished execution → both due
    merged = o.with_single_flight(brains, {"lake-brain": [{"metadata": {"name": "x"}, "status": {"completionTime": "2026-10-13T06:46:00Z"}}]},
                                  {"water-temp": {"lockedUntil": "2026-10-13T06:00:00Z"}}, NOW)
    plan = o.orchestrate(merged, {}, NOW)
    assert {r["brainId"] for r in plan["runs"]} == {"lake-brain", "water-temp"}


def test_job_args_follow_scope(monkeypatch):
    monkeypatch.delenv("ORCHESTRATOR_OVERRIDE_ARGS", raising=False)
    assert o.job_args("lake-brain") is None and o.job_args("water-temp") is None     # invoker-only by default
    monkeypatch.setenv("ORCHESTRATOR_OVERRIDE_ARGS", "1")
    monkeypatch.setenv("ORCHESTRATOR_SCOPE", "pilots")
    monkeypatch.setenv("LAKE_BRAIN_ARCHIVE", "gs://x")
    assert o.job_args("lake-brain") == ["--rtdb", o.RTDB_URL, "--scope", "pilots", "--archive", "gs://x"]
    monkeypatch.setenv("WATER_TEMP_SCOPE", "fleet")
    assert o.job_args("water-temp") == ["--rtdb", o.RTDB_URL]
    monkeypatch.setenv("WATER_TEMP_SCOPE", "pilots")
    assert o.job_args("water-temp").count("--lake") == 5


def test_wind_and_lake_are_started_only_by_the_orchestrator_and_clarity_is_the_scoped_c1_job():
    """Central scheduling 2026-10-23 (Cortex 2.7.0 PL-15): Wind and Lake are started by the orchestrator through their existing Cloud Run jobs (their own
    schedulers are deprecated and PAUSED). Clarity is the scoped C1 publisher job, never the heavy satellite pipeline (lake-surface-*)."""
    assert o.EXECUTORS["wind"] == {"kind": "cloud-run-job", "job": "wind-hourly"} and o.EXECUTORS["lake-brain"]["job"] == "lake-brain"
    assert o.NOT_STARTED_HERE == {}
    assert o.EXECUTORS["water-clarity"] == {"kind": "cloud-run-job", "job": "water-clarity-brain"}
    assert not any(e.get("job", "").startswith("lake-surface") for e in o.EXECUTORS.values())


def test_lock_is_spent_once_its_execution_completed():
    brains = {"water-temp": {"staleAfterHours": 6, "lastSuccessfulRun": "2026-10-12T06:40:17Z"}}
    lock = {"water-temp": {"execution": "projects/p/locations/r/jobs/water-temp-brain/executions/water-temp-brain-x", "lockedUntil": "2026-10-13T07:00:00Z"}}
    execs = {"water-temp-brain": [{"metadata": {"name": "water-temp-brain-x"}, "status": {"startTime": "2026-10-13T06:30:00Z", "completionTime": "2026-10-13T06:35:00Z"}}]}
    merged = o.with_single_flight(brains, execs, lock, NOW)
    assert "lockedUntil" not in merged["water-temp"]["schedule"]
    still = {"water-temp-brain": [{"metadata": {"name": "water-temp-brain-x"}, "status": {"startTime": "2026-10-13T06:30:00Z"}}]}
    merged = o.with_single_flight(brains, still, lock, NOW)
    assert merged["water-temp"]["schedule"]["running"] is True


def test_a_failed_brain_plan_is_marked_so_freshness_is_not_claimed(monkeypatch):
    import subprocess
    class R:
        returncode, stdout, stderr = 1, "", "boom"
    monkeypatch.setattr(o.subprocess, "run", lambda *a, **k: R())
    bid = "biological-state"                                  # in-process: the only kind with a --plan
    p = o.brain_plan(bid)
    assert p["action"] == "SKIP" and p["planError"] is True

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("run.py", 1)
    monkeypatch.setattr(o.subprocess, "run", slow)
    assert o.brain_plan(bid)["planError"] is True
