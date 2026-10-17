"""G1 — generic EXECUTION / JOB health (execution-health-v1).

PROCESS health only: did the job execute, when, did it succeed, is it running, was it skipped and why, what code produced it,
is its cadence itself unhealthy. It deliberately says NOTHING about evidence freshness: `lastSuccessful` is process history,
never a freshness verdict (docs/architecture/certification/BRAIN_IDENTITY_AND_LINEAGE_V1.md §4 rule 1; dependency_health.py owns
freshness). Generic: no Brain id, no science; every input is an execution record or a Brain's own health record.

Existing conventions are REUSED, not duplicated: process health is the contract HEALTH vocabulary (enums.HEALTH); execution records
are orchestration.execution_record() shapes (status STARTED/RUNNING/SUCCEEDED/FAILED, normalised here); in-process Brains publish
`/health/brains/{id}` ("the publish is the run"), mapped by `from_health_record`.
"""
from __future__ import annotations

import datetime as dt

from .enums import HEALTH
from .timeutil import age_hours, iso, parse_time

EXECUTION_HEALTH_VERSION = "execution-health-v1"
EXECUTION_STATUS = ("RUNNING", "SUCCEEDED", "FAILED", "SKIPPED", "DEGRADED", "UNKNOWN")
# status words already written by producers (execution_record / Cloud Run / health records) -> canonical
LEGACY_EXECUTION_STATUS = {"STARTED": "RUNNING", "SUCCESS": "SUCCEEDED", "COMPLETED": "SUCCEEDED", "FAILURE": "FAILED", "ERROR": "FAILED",
                           "SKIP": "SKIPPED", "SKIPPED_UNCHANGED": "SKIPPED", "CANCELLED": "FAILED"}
PROCESS_HEALTH = HEALTH                          # HEALTHY WARNING DEGRADED FAILED UNKNOWN NOT_CONFIGURED (contract section 3)
CADENCE_STATUS = ("ON_CADENCE", "OVERDUE", "NOT_EXPECTED", "UNKNOWN")
CADENCE_GRACE = 1.5                              # a run is OVERDUE after expectedIntervalHours * CADENCE_GRACE without a success
DEGRADING_RUN_HEALTH = ("WARNING", "DEGRADED")   # a completed run whose Brain-reported health is one of these is a DEGRADED execution
CONSUMED_KEYS = ("dependencyId", "dependencyType", "ref", "stateVersion", "fingerprint", "artifactId", "generatedAt", "evidenceObservedAt",
                 "publishedAt", "consumedAt", "freshnessStatus", "staleAfter", "expiresAt")   # the actual-consumption lineage entry (G2): what was
                 # consumed, when, and the OWNER's freshness verdict/rule as of consumption; absent = NOT recorded, never invented


def normalize_status(value, ended: bool | None = None) -> str:
    """Canonical EXECUTION_STATUS. Unknown words stay UNKNOWN (never guessed from exit codes or timestamps)."""
    if value is None:
        return "UNKNOWN"
    v = str(value).upper()
    v = LEGACY_EXECUTION_STATUS.get(v, v)
    return v if v in EXECUTION_STATUS else "UNKNOWN"


def normalize_consumed(items) -> list[dict] | None:
    """The consumed-dependency lineage of an execution, keys restricted to CONSUMED_KEYS. None when the producer recorded nothing."""
    if items is None:
        return None
    out = []
    for c in items:
        if not isinstance(c, dict) or not isinstance(c.get("dependencyId"), str) or ":" not in c["dependencyId"]:
            continue
        e = {k: c[k] for k in CONSUMED_KEYS if c.get(k) is not None}
        prefix = e["dependencyId"].split(":", 1)[0]
        e.setdefault("dependencyType", {"brain": "BRAIN", "signal": "ENVIRONMENTAL_SIGNAL", "provider": "PROVIDER_DATA", "registry": "PLATFORM_REGISTRY"}.get(prefix, e.get("dependencyType")))
        if e.get("dependencyType") is None:
            del e["dependencyType"]
        out.append(e)
    return sorted(out, key=lambda c: c["dependencyId"])


def normalize_execution(rec: dict) -> dict:
    """One execution in the canonical shape. Fields the producer did not give are ABSENT (RTDB drops them anyway); nothing is defaulted.
    `rec`: an orchestration.execution_record(), a control_plane.executions_from_cloud_run() record, or a from_health_record() record."""
    started, ended = rec.get("startedAt"), rec.get("endedAt")
    status = normalize_status(rec.get("status") or rec.get("executionStatus"))
    detail = rec.get("statusDetail")
    run_health = rec.get("runHealth")
    if status == "SUCCEEDED" and (run_health in DEGRADING_RUN_HEALTH or rec.get("partial") is True):
        status, detail = "DEGRADED", detail or (f"run health {run_health}" if run_health in DEGRADING_RUN_HEALTH else "partial run")
    if status == "SKIPPED":
        detail = detail or rec.get("skipReason") or rec.get("reason")
    out = {"executionId": rec.get("executionId"), "subjectId": rec.get("brainId") or rec.get("subjectId"), "executionStatus": status,
           "source": rec.get("source") or "unknown"}
    for k in ("jobId", "trigger", "reason", "scope", "inputFingerprint", "outputChanged", "failureClass", "codeVersion", "runHealth", "error"):
        if rec.get(k) is not None:
            out[k] = rec[k]
    if started:
        out["startedAt"] = started
    if ended:
        out["endedAt"] = ended
        s, e = parse_time(started), parse_time(ended)
        if s and e:
            out["durationSeconds"] = round((e - s).total_seconds(), 1)
    elif rec.get("durationSeconds") is not None:
        out["durationSeconds"] = rec["durationSeconds"]
    if detail:
        out["statusDetail"] = str(detail)[:300]
    consumed = normalize_consumed(rec.get("consumed"))
    out["consumptionRecorded"] = consumed is not None
    if consumed is not None:
        out["consumed"] = consumed
    return out


def from_health_record(brain_id: str, health: dict | None, code_version: str | None = None) -> dict | None:
    """A synthetic last execution for a Brain that publishes only `/health/brains/{id}` (in-process Brains: the publish IS the run).
    None when there is no record. Status comes from the Brain's own health word (FAILED -> FAILED, HEALTHY -> SUCCEEDED,
    WARNING/DEGRADED -> DEGRADED, UNKNOWN/NOT_CONFIGURED -> UNKNOWN); the run time is lastRun; errors are carried verbatim."""
    if not health or not health.get("lastRun"):
        return None
    h = health.get("status")
    status = {"HEALTHY": "SUCCEEDED", "FAILED": "FAILED", "WARNING": "SUCCEEDED", "DEGRADED": "SUCCEEDED"}.get(h, "UNKNOWN")
    rec = {"executionId": f"{brain_id}-health-{str(health['lastRun']).replace(':', '').replace('-', '')}", "brainId": brain_id,
           "startedAt": health["lastRun"], "endedAt": health["lastRun"], "status": status, "source": "health-record", "runHealth": h,
           "trigger": "UNKNOWN", "reason": "observed from /health/brains (the publish is the run; trigger not recorded)"}
    if health.get("durationMs") is not None:
        rec["durationSeconds"] = round(float(health["durationMs"]) / 1000, 1)
    if health.get("latestError") and h == "FAILED":
        rec["error"] = str(health["latestError"])[:300]
    if code_version:
        rec["codeVersion"] = code_version
    return rec


def _brief(e: dict) -> dict:
    return {k: e[k] for k in ("executionId", "executionStatus", "startedAt", "endedAt", "trigger", "codeVersion", "failureClass", "statusDetail") if e.get(k) is not None}


def cadence(last_success_at: str | None, now: dt.datetime, expected_interval_hours: float | None, grace: float = CADENCE_GRACE) -> dict:
    """Is the execution cadence itself unhealthy? Pure process timing: a late run is OVERDUE; it says nothing about evidence freshness.
    expected_interval_hours None = no recurring expectation (manual / event-driven) -> NOT_EXPECTED."""
    out: dict = {}
    if expected_interval_hours is not None:
        out["expectedIntervalHours"] = float(expected_interval_hours)
        out["overdueAfterHours"] = round(float(expected_interval_hours) * grace, 3)
    age = age_hours(last_success_at, now)
    if age is not None:
        out["lastSuccessAgeHours"] = age
    if expected_interval_hours is None:
        out.update(status="NOT_EXPECTED", reason="no recurring cadence declared (manual / event-driven)")
    elif age is None:
        out.update(status="UNKNOWN", reason="no successful execution on record")
    elif age > out["overdueAfterHours"]:
        out.update(status="OVERDUE", reason=f"last success {age} h ago > {out['overdueAfterHours']} h (expected every {expected_interval_hours} h)")
    else:
        out.update(status="ON_CADENCE", reason=f"last success {age} h ago within {out['overdueAfterHours']} h")
    return out


def execution_summary(subject_id: str, executions: list[dict] | None, now: dt.datetime, *, expected_interval_hours: float | None = None,
                      brain_health: dict | None = None, runtime_configured: bool = True, code_version: str | None = None) -> dict:
    """The G1 answer for one Brain/job. `executions`: records (any producer shape; normalised here). `brain_health`: /health/brains/{id}
    (used as the run when no execution records exist, and carried as `brainReportedHealth`). `runtime_configured` False = registered,
    no runtime (NOT_CONFIGURED). Deterministic: same inputs, same output."""
    execs = [normalize_execution(e) for e in (executions or []) if isinstance(e, dict)]
    if not execs:
        hr = from_health_record(subject_id, brain_health, code_version)
        if hr:
            execs = [normalize_execution(hr)]
    execs.sort(key=lambda e: (e.get("startedAt") or "", e.get("executionId") or ""), reverse=True)
    out: dict = {"version": EXECUTION_HEALTH_VERSION, "subjectId": subject_id, "executionCount": len(execs)}
    reasons: list[str] = []
    last = execs[0] if execs else None
    completed = [e for e in execs if e["executionStatus"] in ("SUCCEEDED", "FAILED", "DEGRADED")]
    ok = next((e for e in execs if e["executionStatus"] == "SUCCEEDED"), None)
    failed = next((e for e in execs if e["executionStatus"] == "FAILED"), None)
    if last:
        out["lastExecution"] = _brief(last)
        out["running"] = last["executionStatus"] == "RUNNING"
    if ok:
        out["lastSuccessful"] = _brief(ok)
        out["lastSuccessfulAt"] = ok.get("endedAt") or ok.get("startedAt")
    if failed:
        out["lastFailed"] = _brief(failed)
        out["lastFailedAt"] = failed.get("endedAt") or failed.get("startedAt")
        if failed.get("error"):
            out["lastError"] = failed["error"]
    streak = 0
    for e in completed:
        if e["executionStatus"] == "FAILED":
            streak += 1
        else:
            break
    if completed:
        out["consecutiveFailures"] = streak
    versions = sorted({e["codeVersion"] for e in execs if e.get("codeVersion")})
    if versions:
        out["codeVersions"] = versions
    if brain_health and brain_health.get("status"):
        out["brainReportedHealth"] = brain_health["status"]

    # process health: the HEALTH vocabulary, derived from the newest COMPLETED execution (a RUNNING one has no outcome yet)
    if not runtime_configured:
        health = "NOT_CONFIGURED"; reasons.append("registered Brain without a runtime")
    elif not execs:
        health = "UNKNOWN"; reasons.append("no execution on record")
    elif last["executionStatus"] == "UNKNOWN":
        health = "UNKNOWN"; reasons.append(f"last execution {last.get('executionId')} has an unknown outcome")
    else:
        newest = completed[0] if completed else None
        if last["executionStatus"] == "RUNNING":
            reasons.append(f"execution {last.get('executionId')} is running")
        if last["executionStatus"] == "SKIPPED":
            reasons.append(f"last execution skipped: {last.get('statusDetail') or 'reason not recorded'}")
        if newest is None:
            health = "UNKNOWN"; reasons.append("no completed execution on record")
        elif newest["executionStatus"] == "FAILED":
            health = "FAILED"; reasons.append(f"last completed execution failed" + (f" ({newest.get('failureClass')})" if newest.get("failureClass") else ""))
            if streak >= 3:
                reasons.append(f"{streak} consecutive failures")
        elif newest["executionStatus"] == "DEGRADED":
            health = "DEGRADED"; reasons.append(f"last completed execution degraded: {newest.get('statusDetail') or 'partial'}")
        else:
            health = "HEALTHY"
            if newest.get("runHealth") == "WARNING":
                health = "WARNING"; reasons.append("Brain reported WARNING for its last run")
    cad = cadence(out.get("lastSuccessfulAt"), now, expected_interval_hours)
    out["cadence"] = cad
    if cad["status"] == "OVERDUE":
        reasons.append("cadence: " + cad["reason"])
        if health == "HEALTHY":
            health = "WARNING"
    out["processHealth"] = health
    out["processHealthReasons"] = reasons
    out["evaluatedAt"] = iso(now)
    return out
