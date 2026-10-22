"""Orchestrator execution safety (Cortex PL-02, architecture completion 2026-10-20): the scorer step is isolated (a timeout is recorded, never
fatal to the cycle) and in-process Brains run under their declared control-manifest timeout, capped by the orchestrator's own 30-minute task."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import orchestrate as o  # noqa: E402


def test_a_scorer_timeout_is_recorded_not_raised(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=k.get("timeout"))
    monkeypatch.setattr(o.subprocess, "run", boom)
    r = o.run_scorer(["python", "score_brains.py"], timeout=7)
    assert r == {"published": False, "timedOut": True, "tail": "score_brains.py timed out after 7s"}


def test_scorer_success_and_failure_keep_their_meaning(monkeypatch):
    monkeypatch.setattr(o.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 0, stdout="ok\n", stderr=""))
    assert o.run_scorer(["x"]) == {"published": True, "tail": "ok"}
    monkeypatch.setattr(o.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 2, stdout="", stderr="bad\n"))
    assert o.run_scorer(["x"]) == {"published": False, "tail": "bad"}


def test_in_process_timeout_is_the_declared_one_capped_by_the_task():
    m = {"defaults": {"timeoutSeconds": 900}, "brains": {"a": {"timeoutSeconds": 1200}, "b": {}, "c": {"timeoutSeconds": 99999}}}
    assert (o.in_process_timeout(m, "a"), o.in_process_timeout(m, "b"), o.in_process_timeout(m, "c")) == (1200, 900, 1800)


def test_todays_in_process_brains_keep_their_timeout():
    from sector_brain_platform import orchestration as O
    m = O.load_manifest()
    assert {b: o.in_process_timeout(m, b) for b in ("biological-state", "sector-intelligence")} == {"biological-state": 1800, "sector-intelligence": 1800}
