"""G1 execution health (execution-health-v1): success, failure, skip, running, unknown timestamps, cadence, code version, determinism,
backward compatibility with the existing execution_record / Cloud Run / health-record shapes. Synthetic fixtures only."""
import datetime as dt
import json

import pytest

from sector_brain_platform import execution_health as EH, orchestration as O
from sector_brain_platform.enums import HEALTH

NOW = dt.datetime(2026, 10, 16, 12, 0, tzinfo=dt.timezone.utc)


def iso(h_ago):
    return (NOW - dt.timedelta(hours=h_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def rec(eid, status, started_h, ended_h=None, **kw):
    r = {"executionId": eid, "brainId": "alpha", "trigger": "SCHEDULE", "reason": "due", "startedAt": iso(started_h), "status": status, "source": "orchestrator"}
    if ended_h is not None:
        r["endedAt"] = iso(ended_h)
    r.update(kw)
    return r


def test_vocabularies_reuse_existing_contract_words():
    assert EH.PROCESS_HEALTH == HEALTH
    assert set(EH.EXECUTION_STATUS) == {"RUNNING", "SUCCEEDED", "FAILED", "SKIPPED", "DEGRADED", "UNKNOWN"}
    assert EH.normalize_status("STARTED") == "RUNNING" and EH.normalize_status("SUCCEEDED") == "SUCCEEDED"       # existing producer words map 1:1
    assert EH.normalize_status("whatever") == "UNKNOWN" and EH.normalize_status(None) == "UNKNOWN"


def test_successful_execution():
    s = EH.execution_summary("alpha", [rec("e1", "SUCCEEDED", 2, 1.9, codeVersion="abc123")], NOW, expected_interval_hours=6)
    assert s["processHealth"] == "HEALTHY" and s["running"] is False and s["consecutiveFailures"] == 0
    assert s["lastSuccessful"]["executionId"] == "e1" and s["lastSuccessfulAt"] == iso(1.9) and "lastFailed" not in s
    assert s["codeVersions"] == ["abc123"] and s["lastExecution"]["codeVersion"] == "abc123"
    assert s["cadence"]["status"] == "ON_CADENCE" and s["cadence"]["expectedIntervalHours"] == 6 and s["cadence"]["overdueAfterHours"] == 9
    assert s["processHealthReasons"] == []


def test_failed_execution_and_consecutive_failures():
    ex = [rec("e3", "FAILED", 1, 0.9, failureClass="TRANSIENT_PROVIDER", error="503 from provider"),
          rec("e2", "FAILED", 2, 1.9), rec("e1", "SUCCEEDED", 3, 2.9)]
    s = EH.execution_summary("alpha", ex, NOW)
    assert s["processHealth"] == "FAILED" and s["consecutiveFailures"] == 2
    assert s["lastFailed"]["executionId"] == "e3" and s["lastFailed"]["failureClass"] == "TRANSIENT_PROVIDER" and s["lastError"] == "503 from provider"
    assert s["lastSuccessful"]["executionId"] == "e1"                                         # last success is still known beside the failure
    assert any("failed" in r for r in s["processHealthReasons"])
    three = [rec(f"f{i}", "FAILED", i + 1, i + 0.9) for i in range(3)]
    assert any("3 consecutive failures" in r for r in EH.execution_summary("alpha", three, NOW)["processHealthReasons"])


def test_skipped_execution_records_why_and_keeps_the_last_real_outcome():
    ex = [rec("s1", "SKIPPED", 0.5, 0.49, skipReason="no material input changed"), rec("e1", "SUCCEEDED", 5, 4.9)]
    s = EH.execution_summary("alpha", ex, NOW)
    assert s["lastExecution"]["executionStatus"] == "SKIPPED" and s["lastExecution"]["statusDetail"] == "no material input changed"
    assert s["processHealth"] == "HEALTHY"                                                     # a skip is not a failure
    assert any("skipped" in r for r in s["processHealthReasons"])
    only_skips = EH.execution_summary("alpha", [rec("s1", "SKIPPED", 0.5, 0.49)], NOW)
    assert only_skips["processHealth"] == "UNKNOWN" and "lastSuccessful" not in only_skips    # never completed: unknown, not healthy


def test_running_and_degraded_executions():
    s = EH.execution_summary("alpha", [rec("r1", "STARTED", 0.1), rec("e1", "SUCCEEDED", 3, 2.9)], NOW)
    assert s["running"] is True and s["lastExecution"]["executionStatus"] == "RUNNING" and s["processHealth"] == "HEALTHY"
    d = EH.execution_summary("alpha", [rec("d1", "SUCCEEDED", 1, 0.9, runHealth="DEGRADED")], NOW)
    assert d["lastExecution"]["executionStatus"] == "DEGRADED" and d["processHealth"] == "DEGRADED"
    p = EH.normalize_execution(rec("p1", "SUCCEEDED", 1, 0.9, partial=True))
    assert p["executionStatus"] == "DEGRADED" and p["statusDetail"] == "partial run"
    w = EH.execution_summary("alpha", [rec("w1", "SUCCEEDED", 1, 0.9, runHealth="WARNING")], NOW)
    assert w["lastExecution"]["executionStatus"] == "DEGRADED"


def test_unknown_timestamps_and_outcomes_stay_unknown_never_zero():
    s = EH.execution_summary("alpha", [{"executionId": "u1", "brainId": "alpha", "status": "SUCCEEDED"}], NOW, expected_interval_hours=1)
    assert "startedAt" not in s["lastExecution"] and "durationSeconds" not in s["lastExecution"]
    assert s["cadence"]["status"] == "UNKNOWN" and "lastSuccessAgeHours" not in s["cadence"]   # no timestamp: unknown age, not 0 h
    bad = EH.normalize_execution({"executionId": "u2", "brainId": "alpha", "startedAt": "not a time", "endedAt": "later", "status": "SUCCEEDED"})
    assert "durationSeconds" not in bad
    u = EH.execution_summary("alpha", [{"executionId": "u3", "brainId": "alpha", "startedAt": iso(1)}], NOW)
    assert u["lastExecution"]["executionStatus"] == "UNKNOWN" and u["processHealth"] == "UNKNOWN"
    empty = EH.execution_summary("alpha", [], NOW)
    assert empty["processHealth"] == "UNKNOWN" and empty["executionCount"] == 0 and "consecutiveFailures" not in empty and "running" not in empty
    assert EH.execution_summary("alpha", [], NOW, runtime_configured=False)["processHealth"] == "NOT_CONFIGURED"


def test_cadence_is_process_timing_not_freshness():
    c = EH.cadence(iso(10), NOW, 6)
    assert c["status"] == "OVERDUE" and c["lastSuccessAgeHours"] == 10 and c["overdueAfterHours"] == 9
    assert EH.cadence(iso(8), NOW, 6)["status"] == "ON_CADENCE"                                # within grace
    assert EH.cadence(iso(100), NOW, None) == {"lastSuccessAgeHours": 100, "status": "NOT_EXPECTED", "reason": "no recurring cadence declared (manual / event-driven)"}
    assert EH.cadence(None, NOW, 6)["status"] == "UNKNOWN"
    s = EH.execution_summary("alpha", [rec("e1", "SUCCEEDED", 20, 19.9)], NOW, expected_interval_hours=6)
    assert s["processHealth"] == "WARNING" and any(r.startswith("cadence:") for r in s["processHealthReasons"])
    assert not any(k for k in json.dumps(s) .split('"') if k in ("fresh", "stale", "freshnessStatus"))          # G1 never utters a freshness verdict


def test_health_record_is_the_run_for_in_process_brains():
    h = {"status": "HEALTHY", "lastRun": iso(3), "lastSuccess": iso(3), "durationMs": 1500, "errorCount": 0}
    s = EH.execution_summary("beta", [], NOW, brain_health=h, code_version="orch@deadbeef")
    assert s["executionCount"] == 1 and s["processHealth"] == "HEALTHY" and s["brainReportedHealth"] == "HEALTHY"
    assert s["lastExecution"]["trigger"] == "UNKNOWN" and s["lastSuccessfulAt"] == iso(3) and s["codeVersions"] == ["orch@deadbeef"]
    f = EH.execution_summary("beta", [], NOW, brain_health={"status": "FAILED", "lastRun": iso(1), "latestError": "boom"})
    assert f["processHealth"] == "FAILED" and f["lastError"] == "boom"
    assert EH.from_health_record("beta", {"status": "HEALTHY"}) is None                        # no lastRun: no run invented
    assert EH.execution_summary("beta", [], NOW, brain_health={"status": "DEGRADED"})["brainReportedHealth"] == "DEGRADED"


def test_backward_compatible_with_execution_record_and_cloud_run_shapes():
    old = O.execution_record("x1", "alpha", "SCHEDULE", "due", NOW - dt.timedelta(minutes=3), NOW, "SUCCEEDED")   # the pre-G1 call signature
    assert "codeVersion" not in old and "consumed" not in old
    n = EH.normalize_execution(old)
    assert n["executionStatus"] == "SUCCEEDED" and n["durationSeconds"] == 180 and n["consumptionRecorded"] is False
    new = O.execution_record("x2", "alpha", "MANUAL", "asked", NOW - dt.timedelta(minutes=1), NOW, "SUCCEEDED", code_version="c1", job_id="alpha-job",
                             consumed=[{"dependencyId": "brain:beta", "stateVersion": "7", "consumedAt": "2026-10-16T11:59:00Z", "secret": "no"}])
    n2 = EH.normalize_execution(new)
    assert n2["codeVersion"] == "c1" and n2["jobId"] == "alpha-job" and n2["consumptionRecorded"] is True
    assert n2["consumed"] == [{"dependencyId": "brain:beta", "stateVersion": "7", "consumedAt": "2026-10-16T11:59:00Z"}]   # key set is closed
    started = O.execution_record("x3", "alpha", "SCHEDULE", "due", NOW, None, "STARTED")
    assert EH.normalize_execution(started)["executionStatus"] == "RUNNING"


def test_summary_is_deterministic_and_order_independent():
    ex = [rec("e1", "SUCCEEDED", 3, 2.9), rec("e2", "FAILED", 2, 1.9), rec("e3", "SUCCEEDED", 1, 0.9)]
    a = EH.execution_summary("alpha", ex, NOW, expected_interval_hours=2)
    b = EH.execution_summary("alpha", list(reversed(ex)), NOW, expected_interval_hours=2)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["lastExecution"]["executionId"] == "e3" and a["lastFailed"]["executionId"] == "e2" and a["consecutiveFailures"] == 0


def test_no_brain_or_signal_or_provider_id_is_hardcoded_in_the_health_modules():
    """The platform discovers relationships; it never writes them in code (no `if brain == 'x'`, no CANVAS_DEPENDENCIES table)."""
    import ast, os
    from sector_brain_platform import keys, signals as SG, dependency_declarations as DD
    ids = set(keys.BRAINS) | set(O.load_manifest()["brains"]) | set(SG.load()) | set(DD.load_providers() or {})
    pkg = os.path.dirname(EH.__file__)
    for mod in ("execution_health", "dependency_health", "dependency_declarations", "brain_health", "signals"):
        tree = ast.parse(open(os.path.join(pkg, mod + ".py")).read())
        consts = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        hard = sorted(c for c in consts if c in ids or any(c.startswith(p) and c[len(p):] in ids for p in ("brain:", "signal:", "provider:")))
        assert hard == [], f"{mod}.py hardcodes platform entity ids: {hard}"
