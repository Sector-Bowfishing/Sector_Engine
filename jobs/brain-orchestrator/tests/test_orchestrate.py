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
    monkeypatch.setenv("ORCHESTRATOR_SCOPE", "pilots")
    monkeypatch.setenv("LAKE_BRAIN_ARCHIVE", "gs://x")
    assert o.job_args("lake-brain") == ["--rtdb", o.RTDB_URL, "--scope", "pilots", "--archive", "gs://x"]
    monkeypatch.setenv("WATER_TEMP_SCOPE", "fleet")
    assert o.job_args("water-temp") == ["--rtdb", o.RTDB_URL]
    monkeypatch.setenv("WATER_TEMP_SCOPE", "pilots")
    assert o.job_args("water-temp").count("--lake") == 5


def test_wind_and_clarity_are_never_started_here():
    assert "wind" not in o.EXECUTORS and "water-clarity" not in o.EXECUTORS
    assert set(o.NOT_STARTED_HERE) == {"wind", "water-clarity"}
