"""A scoped, orchestrator-started job's own last success counts for `due()` (internal operation 2026-10-22): a pilot-scoped Water Temp run
refreshes 5 lakes without restating the 621-lake registry, so the registry time alone would make the job due every hourly cycle."""
import datetime as dt

from sector_brain_platform import orchestration as O

NOW = dt.datetime(2026, 10, 22, 12, tzinfo=dt.timezone.utc)
M = {"brains": {
    "water-temp": {"executionTarget": {"kind": "cloud-run-job", "job": "water-temp-brain", "startedByOrchestrator": True, "scoped": True},
                   "freshness": {"staleAfterHours": 6}},
    "lake-brain": {"executionTarget": {"kind": "cloud-run-job", "job": "lake-brain", "startedByOrchestrator": False}, "freshness": {"staleAfterHours": 3}},
    "biological-state": {"executionTarget": {"kind": "in-process"}},
}}
REGS = {"water-temp": {"lastSuccessfulRun": "2026-10-14T01:57:32Z"}, "lake-brain": {"lastSuccessfulRun": "2026-10-21T12:00:00Z"}}


def test_scoped_job_success_counts_and_is_labelled():
    s = O.with_job_success(M, REGS, {"water-temp-brain": {"lastSuccessfulAt": "2026-10-22T10:00:00Z"}})
    assert s["water-temp"]["lastSuccessfulRun"] == "2026-10-22T10:00:00Z" and "scoped run" in s["water-temp"]["lastSuccessfulRunBasis"]
    assert O.due(M["brains"]["water-temp"], s["water-temp"], NOW) is False                     # 2 h old: not due (no hourly re-run)
    assert O.due(M["brains"]["water-temp"], REGS["water-temp"], NOW) is True                   # the registry alone would say due
    late = O.with_job_success(M, REGS, {"water-temp-brain": {"lastSuccessfulAt": "2026-10-22T05:00:00Z"}})
    assert O.due(M["brains"]["water-temp"], late["water-temp"], NOW) is True                  # 7 h old: due again


def test_nothing_changes_without_evidence_or_for_other_targets():
    assert O.with_job_success(M, REGS, {}) == REGS and O.with_job_success(M, REGS, None) == REGS
    s = O.with_job_success(M, REGS, {"lake-brain": {"lastSuccessfulAt": "2026-10-22T11:00:00Z"}})     # not started by the orchestrator
    assert s["lake-brain"] == REGS["lake-brain"]
    older = O.with_job_success(M, {"water-temp": {"lastSuccessfulRun": "2026-10-22T11:00:00Z"}}, {"water-temp-brain": {"lastSuccessfulAt": "2026-10-22T09:00:00Z"}})
    assert older["water-temp"] == {"lastSuccessfulRun": "2026-10-22T11:00:00Z"}                     # the later time wins; no basis label
    assert REGS["water-temp"] == {"lastSuccessfulRun": "2026-10-14T01:57:32Z"}                       # input not mutated
