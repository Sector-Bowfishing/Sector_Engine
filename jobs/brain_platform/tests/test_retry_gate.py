"""Bounded retry on the default execution path (Cortex PL-02, architecture completion 2026-10-20). The gate applies the manifest retry policy
(defaults.retry: 3 attempts, 5/15/45 min) to a Brain's CONSECUTIVE failures from the previous cycle's execution ledger. It only holds automatic
runs back (WAITING during backoff, MANUAL_APPROVAL when retries are exhausted or the failure is not retryable); explicit runs always proceed."""
import datetime as dt

from sector_brain_platform import orchestration as O
from test_orchestration import NOW, ctx, manifest

FISH = "biological-state"            # accepts INPUT_CHANGED automatically and is ACTIVE in the manifest


def ex(status, minutes_ago, failure_class=None, brain=FISH):
    t = NOW - dt.timedelta(minutes=minutes_ago)
    e = {"executionId": f"{brain}-{minutes_ago}", "brainId": brain, "status": status, "startedAt": O.iso(t - dt.timedelta(minutes=1)), "endedAt": O.iso(t)}
    if failure_class:
        e["failureClass"] = failure_class
    return e


def decide(executions, trigger="INPUT_CHANGED"):
    c = ctx(manifest())
    if executions is not None:
        c["executions"] = executions
    return O.decide_brain(FISH, trigger, c)


def test_without_a_ledger_or_without_failures_nothing_changes():
    assert decide(None)["decision"] == "RUN"                                     # callers that pass no ledger keep today's behaviour
    assert decide([])["decision"] == "RUN"
    assert decide([ex("SUCCEEDED", 5), ex("FAILED", 60, "TRANSIENT_RUNTIME")])["decision"] == "RUN"     # a success after the failure resets it


def test_a_transient_failure_waits_for_its_backoff_then_runs():
    d = decide([ex("FAILED", 2, "TRANSIENT_PROVIDER")])
    assert d["decision"] == "WAITING" and d["reasonCode"] == "RETRY_BACKOFF" and d["retry"]["nextAttemptAt"] == O.iso(NOW + dt.timedelta(minutes=3))
    assert decide([ex("FAILED", 6, "TRANSIENT_PROVIDER")])["decision"] == "RUN"  # 5-minute backoff elapsed


def test_retries_are_bounded_then_need_a_person():
    d = decide([ex("FAILED", 120, "TRANSIENT_RUNTIME"), ex("FAILED", 200, "TRANSIENT_RUNTIME"), ex("FAILED", 300, "TRANSIENT_RUNTIME")])
    assert d["decision"] == "MANUAL_APPROVAL" and d["reasonCode"] == "RETRIES_EXHAUSTED"


def test_a_permanent_failure_is_not_retried_automatically():
    d = decide([ex("FAILED", 600, "PERMANENT_CONFIG")])
    assert d["decision"] == "MANUAL_APPROVAL" and d["reasonCode"] == "NOT_RETRYABLE"


def test_explicit_runs_are_never_held_back():
    c = ctx(manifest()); c["executions"] = [ex("FAILED", 1, "PERMANENT_CONFIG")]
    assert O.decide_brain(FISH, "MANUAL", c)["decision"] == "RUN"


def test_a_dependency_blocked_failure_reruns_on_a_dependency_change_only():
    assert O.retry_gate(FISH, "DEPENDENCY_CHANGED", {**ctx(manifest()), "executions": [ex("FAILED", 1, "DEPENDENCY_BLOCKED")]}) is None
    assert decide([ex("FAILED", 1, "DEPENDENCY_BLOCKED")])["decision"] == "MANUAL_APPROVAL"


def test_other_brains_failures_do_not_gate_this_brain_and_running_executions_are_ignored():
    assert decide([ex("FAILED", 1, "PERMANENT_CONFIG", brain="wind")])["decision"] == "RUN"
    assert decide([{"executionId": "x", "brainId": FISH, "status": "STARTED", "startedAt": O.iso(NOW)}])["decision"] == "RUN"
