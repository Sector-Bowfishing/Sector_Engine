"""The four independent Brain readiness dimensions (Cortex 2.6.0 operations.md IO-01, IO-08) for engineering-status-ops-v1 1.2.0.

Static dimensions (scientific validation, knowledge release, customer eligibility, score measurement classes, limitations) come from the
commit-bound engineering report (tools/cortex_status). This module adds the LIVE ones from evidence the orchestrator already holds in its
cycle (no extra database reads): runtime readiness and internal operation, from the control state it just built, the Cloud Scheduler states and
the shadow-lane summaries. Stdlib only, no clock (callers pass `now`).

Honest-status rules (IO-08, PL-04):
  - ACTIVE needs an enabled trigger AND a successful execution within 1.5 x the expected interval. An input- or dependency-driven Brain has no
    fixed interval: ACTIVE needs its enabled trigger, the Brain's own plan check observed in this cycle, and a successful last execution.
  - SHADOW (INTERNAL-mode shadow lane) needs a shadow run within 1.5 x its cadence.
  - a paused scheduler is PAUSED, never ACTIVE; a failed last execution is FAILED; no evidence is NOT_VERIFIED. Nothing is inferred from
    scientific maturity, and incomplete science never makes infrastructure look broken.
"""
from __future__ import annotations

import datetime as dt

from .timeutil import iso, parse_time

RUNTIME = ("READY", "NOT_READY", "NOT_VERIFIED")
INTERNAL = ("NOT_DEPLOYED", "SHADOW", "ACTIVE", "DEGRADED", "PAUSED", "FAILED", "NOT_VERIFIED")
SCIENCE = ("NOT_STARTED", "IN_PROGRESS", "PARTIAL", "VALIDATED", "NOT_VERIFIED")
CUSTOMER = ("NOT_ELIGIBLE", "ELIGIBLE", "NOT_VERIFIED")
KNOWLEDGE = ("NONE", "RESEARCH", "CANDIDATE", "APPROVED")
MEASUREMENTS = ("STRUCTURAL_CERTIFICATION", "RUNTIME_READINESS", "INTERNAL_OPERATIONAL_HEALTH", "SCIENTIFIC_MATURITY", "DOMAIN_CAPABILITY",
                "CUSTOMER_ELIGIBILITY", "ENGINEERING_SCORE")
SLACK = 1.5
ORCHESTRATOR_SCHEDULER = "brain-orchestrator"
OK_RESULTS = ("SUCCEEDED", "SKIPPED", "HEALTHY", "OK")   # SKIPPED = the Brain's runtime ran and found nothing new to publish (a successful no-op)
BAD_RESULTS = ("FAILED", "TIMEOUT", "ERROR")


def _age_h(ts, now: dt.datetime) -> float | None:
    t = parse_time(ts)
    return None if t is None else round((now - t).total_seconds() / 3600, 2)


def _trigger(b: dict) -> tuple[str, str | None]:
    """-> (kind, scheduler): TIME (a scheduler starts it when stale), EVENT (input/dependency driven) or SHADOW."""
    if (b.get("shadowLane") or {}).get("enabled") and b.get("activityState") == "PARKED":
        return "SHADOW", ORCHESTRATOR_SCHEDULER
    sch = b.get("schedule") or {}
    own = sch.get("scheduler") if sch.get("owner") == "LEGACY_SCHEDULER" or sch.get("class") == "VALIDATION_EXCEPTION" else None
    if (b.get("freshness") or {}).get("staleAfterHours") is not None:
        return "TIME", own or ORCHESTRATOR_SCHEDULER
    return "EVENT", ORCHESTRATOR_SCHEDULER


def live(brain_id: str, b: dict, row: dict | None, *, scheduler_states: dict | None, shadow_doc: dict | None, plan: dict | None,
         now: dt.datetime) -> dict:
    """Runtime readiness + internal operation for one Brain. b = its control_manifest entry, row = its control-state row (orchestratorV1)."""
    row = row or {}
    kind, sched = _trigger(b)
    sstate = (scheduler_states or {}).get(sched)
    enabled = None if sstate is None else sstate == "ENABLED"
    io: dict = {"trigger": kind, "scheduler": sched, "schedulerState": sstate or "UNKNOWN"}
    if kind == "SHADOW":
        cad = float((b.get("shadowLane") or {}).get("cadenceHours") or 24)
        last_at = (shadow_doc or {}).get("runAt")
        fail = (shadow_doc or {}).get("lastFailure") or {}
        failed = bool(fail.get("at") and (not last_at or str(fail["at"]) > str(last_at)))
        age = _age_h(last_at, now)
        io.update({"expectedIntervalHours": cad, "lastExecutionAt": last_at, "lastExecutionResult": "FAILED" if failed else ("SUCCEEDED" if last_at else None),
                   "lane": "INTERNAL_EXPERIMENTAL", "lastExecutionKind": "SHADOW_RUN"})
        if failed:
            st, why = "FAILED", "the latest shadow run failed"
        elif enabled is False:
            st, why = "PAUSED", f"scheduler {sched} is {sstate}"
        elif age is None:
            st, why = "NOT_VERIFIED", "no shadow run observed"
        elif age <= cad * SLACK and enabled:
            st, why = "SHADOW", f"INTERNAL-mode shadow run {age} h ago (cadence {cad:g} h); approved path abstains"
        else:
            st, why = "NOT_VERIFIED", f"last shadow run {age} h ago exceeds {SLACK} x cadence {cad:g} h" if age is not None else "scheduler state unknown"
        rt = "NOT_READY" if failed else ("READY" if last_at else "NOT_VERIFIED")
        io.update({"status": st, "basis": why})
        io = {k: v for k, v in io.items() if v is not None}
        return {"runtimeReadiness": {"status": rt, "basis": "latest shadow run " + ("failed" if failed else "succeeded" if last_at else "not observed")},
                "internalOperation": io}

    lx = row.get("lastExecution") or {}
    last_at, result = lx.get("at"), str(lx.get("status") or "").upper() or None
    age = _age_h(last_at, now)
    io.update({"lastExecutionAt": last_at, "lastExecutionResult": result, "lastSuccessfulRun": row.get("lastSuccessfulRun")})
    if row.get("lastSuccessfulRunBasis"):
        io["lastSuccessfulRunBasis"] = row["lastSuccessfulRunBasis"]
    activity = row.get("activityState") or b.get("activityState")
    if kind == "TIME":
        iv = float((b.get("freshness") or {}).get("staleAfterHours"))
        io["expectedIntervalHours"] = iv
        # the Brain counts as executed within its interval when its last success is fresh, even if the last attempt was a no-op skip
        succ_age = _age_h(row.get("lastSuccessfulRun"), now)
    else:
        iv, succ_age = None, None
        io["planCheck"] = "OBSERVED" if plan and plan.get("action") in ("PUBLISH", "SKIP") else ("FAILED" if plan else "NOT_OBSERVED")
        if plan and plan.get("action") in ("PUBLISH", "SKIP"):
            io["lastPlanCheckAt"] = iso(now)
    if activity == "PARKED":
        st, why = "PAUSED", "PARKED in the execution manifest (existing state stays readable)"
    elif result in BAD_RESULTS:
        st, why = "FAILED", f"latest execution {result}"
    elif enabled is False:
        st, why = "PAUSED", f"scheduler {sched} is {sstate}"
    elif enabled is None:
        st, why = "NOT_VERIFIED", f"scheduler {sched} state unknown"
    elif kind == "TIME":
        ok_ages = [a for a in (succ_age, age if result in OK_RESULTS else None) if a is not None]
        best = min(ok_ages) if ok_ages else None
        if best is not None and best <= iv * SLACK:
            st, why = "ACTIVE", f"trigger enabled; successful execution {best} h ago (expected every {iv:g} h)"
        else:
            st, why = "NOT_VERIFIED", ("no successful execution observed" if best is None else
                                        f"last successful execution {best} h ago exceeds {SLACK} x {iv:g} h")
    else:
        if io["planCheck"] == "OBSERVED" and result in OK_RESULTS:
            st, why = "ACTIVE", ("trigger enabled; the Brain's own plan check ran this cycle; last execution succeeded"
                                 + (" with nothing new to publish" if result == "SKIPPED" else "") + " (runs when its inputs change)")
        elif io["planCheck"] == "FAILED":
            st, why = "DEGRADED", "the Brain's own plan check failed this cycle"
        else:
            st, why = "NOT_VERIFIED", "no plan check this cycle or no successful execution on record"
    if kind == "EVENT" and io.get("lastPlanCheckAt"):
        # IO-08 evidence for an input/dependency-driven Brain: its runtime's own plan check runs every orchestrator cycle (hourly). That check is
        # the observed execution; the last full run (publish or no-op) is reported beside it, never hidden.
        io.update({"lastFullRunAt": last_at, "lastFullRunResult": result, "lastExecutionAt": io["lastPlanCheckAt"],
                   "lastExecutionResult": "SUCCEEDED", "lastExecutionKind": "PLAN_CHECK", "expectedIntervalHours": 1.0})
    elif last_at:
        io["lastExecutionKind"] = "RUN"
    io.update({"status": st, "basis": why})
    io = {k: v for k, v in io.items() if v is not None}
    rt = "NOT_READY" if result in BAD_RESULTS else ("READY" if result in OK_RESULTS or row.get("lastSuccessfulRun") else "NOT_VERIFIED")
    return {"runtimeReadiness": {"status": rt, "basis": f"latest execution {result.lower() if result else 'not observed'}"},
            "internalOperation": io,
            "health": row.get("health") or "UNKNOWN",
            "inputFreshness": {"verdict": (row.get("freshness") or {}).get("verdict") or "UNKNOWN",
                               **({"reason": str(row["freshness"]["reason"])[:240]} if (row.get("freshness") or {}).get("reason") else {})},
            "lastDataUpdate": ({k: str(v) for k, v in row["lastDataUpdate"].items() if k in ("at", "basis", "version") and v is not None}
                               if isinstance(row.get("lastDataUpdate"), dict) else None)}


def shadow_summary(doc: dict | None) -> dict | None:
    """Counts-only view of a brain-shadow-lane-v1 summary for Ops: no lake values, no digests, no internal fields."""
    if not isinstance(doc, dict) or doc.get("schema") != "brain-shadow-lane-v1":
        return None
    lakes = doc.get("lakes") or {}
    kinds: dict = {}
    for r in lakes.values():
        k = (r or {}).get("kind") or "unknown"
        kinds[k] = kinds.get(k, 0) + 1
    rel, ap = doc.get("candidateRelease") or {}, doc.get("approvedPath") or {}
    out = {"lane": doc.get("lane"), "executionMode": doc.get("executionMode"), "experimental": doc.get("experimental") is True,
           "authoritative": False, "customerEligible": False, "lastRunAt": doc.get("runAt"), "lakeCount": doc.get("lakeCount"),
           "readinessCounts": doc.get("readinessCounts") or {}, "outputKinds": kinds,
           "observedLakes": kinds.get("observed", 0), "candidateReleaseId": rel.get("releaseId"), "candidateApproval": rel.get("approvalStatus"),
           "approvedPath": {k: ap[k] for k in ("status", "reason") if isinstance(ap.get(k), str)}}
    if (doc.get("lastFailure") or {}).get("at"):
        out["lastFailureAt"] = doc["lastFailure"]["at"]
    return {k: v for k, v in out.items() if v is not None}


def apply_control(out: dict, brain_id: str, control: dict | None) -> dict:
    """Cortex 2.7.0 PL-16 / IO-08: the global execution control comes first. While it is not ENABLED (or disables this Brain), a Brain is PAUSED
    whatever its last execution says; FAILED stays FAILED (a real failure is never hidden). control=None means "not evaluated" (older callers)."""
    if control is None:
        return out
    io = dict(out.get("internalOperation") or {})
    g = control.get("state", "PAUSED")
    on = (control.get("brains") or {}).get(brain_id, {}).get("enabled") is True
    io["executionControl"] = {"global": g, "brainEnabled": on}
    if io.get("status") != "FAILED":
        if g != "ENABLED":
            io["status"], io["basis"] = "PAUSED", f"global execution control {g}: no automatic execution until the owner authorizes resumption ({(control.get('reason') or '')[:120]})"
        elif not on:
            io["status"], io["basis"] = "PAUSED", f"{brain_id} is disabled in the execution control"
    return {**out, "internalOperation": io}


def overlay(es_doc: dict, manifest: dict, control_brains: dict | None, *, scheduler_states: dict | None, shadow_docs: dict | None,
            plans: dict | None, now: dt.datetime, control: dict | None = None) -> dict:
    """An AVAILABLE engineering-status-ops-v1 document with each Brain's `operations` block completed from live evidence. Returns a new dict."""
    out = dict(es_doc)
    brains = []
    cb = control_brains or {}
    for b in es_doc.get("brains") or []:
        bid = b["brainId"]
        mb = (manifest.get("brains") or {}).get(bid)
        ops = dict(b.get("operations") or {})
        if mb is None:
            ops.update({"runtimeReadiness": {"status": "NOT_VERIFIED", "basis": "not in the execution manifest"},
                        "internalOperation": {"status": "NOT_DEPLOYED", "basis": "not in the execution manifest"}})
        else:
            row = cb.get(bid) or cb.get(bid.replace("-", "_")) or next((r for r in cb.values() if isinstance(r, dict) and r.get("brainId") == bid), None)
            sd = (shadow_docs or {}).get(bid)
            ops.update(apply_control(live(bid, mb, row, scheduler_states=scheduler_states, shadow_doc=sd, plan=(plans or {}).get(bid), now=now), bid, control))
            ss = shadow_summary(sd)
            if ss:
                ops["shadowLane"] = ss
        ops["liveAsOf"] = iso(now)
        brains.append({**b, "operations": {k: v for k, v in ops.items() if v is not None}})
    out["brains"] = brains
    out["operationsAsOf"] = iso(now)
    if control is not None:
        from .execution_control import summary
        out["executionControl"] = summary(control)
    return out


def counts(doc: dict) -> dict:
    c: dict = {}
    for b in doc.get("brains") or []:
        s = ((b.get("operations") or {}).get("internalOperation") or {}).get("status") or "NOT_VERIFIED"
        c[s] = c.get(s, 0) + 1
    return c
