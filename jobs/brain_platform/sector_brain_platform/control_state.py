"""The compact read-only control state Sector Ops renders (contract: docs/brains/platform/orchestrator/ORCHESTRATOR_CONTROL_V1.md).

Pure builders. Published (by the orchestrator, as the platform writer) under `/control/orchestratorV1/*`, beside the existing `/control/overview`
and `/control/orchestrator`. UNKNOWN stays absent: a missing value is never a zero. Bounded: recent executions and decisions are capped ring buffers.
"""
from __future__ import annotations

import datetime as dt

from . import orchestration as O
from .timeutil import age_hours, iso, parse_time

SECTIONS = ("summary", "brains", "edges", "jobs", "schedules", "executions", "decisions", "latestDecisions", "health", "cost", "blockers", "graph", "overrides", "requests")
VOLATILE = ("lastEvaluatedAt", "asOf", "syncedAt", "ageHours", "durationMs")   # ageHours moves every evaluation; `stale` carries the decision
NODE = "control/orchestratorV1"
HEARTBEAT_HOURS = 6        # an unchanged control plane refreshes only its summary timestamp this often


def _strip(o):
    if isinstance(o, dict):
        return {k: v2 for k, v in o.items() if (v2 := _strip(v)) not in (None, {}, [])}
    if isinstance(o, list):
        return [x for x in (_strip(v) for v in o) if x not in (None, {}, [])]
    return o


def _key(*parts) -> str:
    import re
    return "__".join(re.sub(r"[.$#\[\]/\x00-\x1f\x7f|]", "_", str(p)) for p in parts)


def execution_mode(brain: dict, enabled: bool | None) -> str:
    """How this Brain currently gets to run, in one word Ops can show."""
    cls = (brain.get("schedule") or {}).get("class")
    if cls == "VALIDATION_EXCEPTION":
        return "VALIDATION_EXCEPTION" if enabled is not False else "PAUSED"
    if cls == "INPUT_DRIVEN":
        return "INPUT_DRIVEN"
    if cls == "PAUSED":
        return "MANUAL"            # the Brain's recurring schedule is paused, so it runs only on manual / targeted / validation triggers
    if cls in ("ORCHESTRATOR_OWNED", "LEGACY"):
        return "SCHEDULED" if enabled else "PAUSED"
    return "MANUAL"


def _job_enabled(jobs: dict, scheduler: str | None, live: dict | None = None) -> bool | None:
    """Scheduler truth. Cloud Scheduler's own state (`live`, read this evaluation) wins; otherwise the /jobs record's schedulerState; never the record's
    `enabled` (an event-driven job is 'enabled' as a job while its own scheduler can be paused). Unknown stays None."""
    if not scheduler:
        return None
    if live and scheduler in live:
        return live[scheduler] == "ENABLED"
    j = (jobs or {}).get(scheduler)
    st = (j or {}).get("schedulerState")
    return None if not st else st == "ENABLED"


def build_jobs(manifest: dict, jobs: dict, executions: list[dict], states: dict | None = None) -> tuple[dict, dict]:
    """-> (jobs, schedules). One authoritative schedule model: every known job with its classification, whether it is actually enabled, and the
    last/next execution from the /jobs sync (Scheduler authoritative for enabled/cron/next)."""
    out, sched = {}, {}
    for jid, mj in sorted(manifest["jobs"].items()):
        live = (jobs or {}).get(jid) or (jobs or {}).get(mj.get("scheduler") or "") or {}
        enabled = _job_enabled(jobs, mj.get("scheduler"), states) if mj.get("scheduler") else None
        last = next((e for e in executions if e.get("jobId") == jid), None)
        rec = {"jobId": jid, "brainId": mj.get("brainId"), "purpose": mj.get("purpose"), "executionTarget": mj.get("target") or jid, "classification": mj["classification"],
               "schedule": live.get("schedule") or (mj.get("cron")), "enabled": enabled, "validationOnly": mj.get("validationOnly", False),
               "customerImpact": mj.get("customerImpact", False), "lastStartedAt": live.get("lastStartedAt"), "lastCompletedAt": live.get("lastCompletedAt"),
               "lastResult": live.get("runtimeStatus"), "durationMs": live.get("durationMs"), "nextDue": live.get("nextScheduledAt") if enabled else None,
               "costEstimate": {"basis": "ESTIMATED" if mj.get("estMonthlyUsdWhenEnabled") is not None else "UNKNOWN", "monthlyUsdWhenEnabled": mj.get("estMonthlyUsdWhenEnabled")},
               "lastExecutionId": (last or {}).get("executionId")}
        out[_key(jid)] = _strip(rec)
        if mj.get("scheduler"):
            sched[_key(mj["scheduler"])] = _strip({"scheduler": mj["scheduler"], "jobId": jid, "classification": mj["classification"], "enabled": enabled,
                                                   "cron": live.get("cron") or None, "timezone": live.get("timezone"), "nextDue": live.get("nextScheduledAt") if enabled else None,
                                                   "owner": "LEGACY_SCHEDULER" if mj["classification"] in ("VALIDATION_EXCEPTION", "LEGACY", "PAUSED") else "ORCHESTRATOR"})
    return out, sched


def merge_decisions(prev_latest: dict, prev_recent: dict, decisions: list[dict], limit: int = O.DECISION_LEDGER_MAX) -> tuple[dict, dict]:
    """latestDecisions holds the CURRENT verdict per (Brain, trigger) with `since` (stable until it changes, so an unchanged verdict does not rewrite the node).
    `recent` is a bounded, newest-first log of verdict CHANGES (plus every RUN). Answers 'why did/didn't this run' without an unbounded log."""
    latest, recent = dict(prev_latest or {}), dict(prev_recent or {})
    items = sorted(recent.values(), key=lambda d: d.get("at", ""), reverse=True)
    for d in decisions:
        k = _key(d["brainId"], d["trigger"])
        cur = latest.get(k) or {}
        same = cur.get("decision") == d["decision"] and cur.get("reasonCode") == d["reasonCode"] and cur.get("reason") == d["reason"]
        if not same:
            latest[k] = _strip({"brainId": d["brainId"], "trigger": d["trigger"], "decision": d["decision"], "reasonCode": d["reasonCode"], "reason": d["reason"],
                                "since": d["at"], "decisionId": d["decisionId"]})
        if not same or d["decision"] == "RUN":
            items = O.append_bounded(items, _strip(d), limit)
    return latest, {x["decisionId"]: x for x in items[:limit]}


def build_control_state(manifest: dict, mode: str, now: dt.datetime, *, registries: dict, health: dict, scores: dict, jobs: dict, evaluation: dict,
                        prev: dict | None = None, new_executions: list[dict] | None = None, locks: dict | None = None, trigger: str = "SCHEDULE",
                        duration_ms: int | None = None, overrides: dict | None = None, out_fps: dict | None = None, requests: dict | None = None,
                        scheduler_states: dict | None = None) -> dict:
    prev = prev or {}
    graph = O.validate_graph(manifest)
    activity = O.effective_activity(manifest, overrides)
    by_id = {e["executionId"]: e for e in (prev.get("executions") or {}).values() if e.get("brainId") != "platform"}   # the orchestrator's own wake-ups are not Brain executions
    by_id.update({e["executionId"]: e for e in (new_executions or [])})          # a re-observed execution (now finished) replaces its earlier record
    execs = sorted(by_id.values(), key=lambda x: x.get("startedAt", ""), reverse=True)[:O.EXECUTION_LEDGER_MAX]
    latest, recent = merge_decisions(prev.get("latestDecisions"), prev.get("decisions"), evaluation["decisions"])
    jobs_out, scheds = build_jobs(manifest, jobs, execs, scheduler_states)
    changes = evaluation["changes"]
    day = f"{now:%Y-%m-%d}"
    fps = out_fps if out_fps is not None else {bid: O.output_fingerprint(b, registries.get(bid))[0] for bid, b in manifest["brains"].items()}
    dctx = {"manifest": manifest, "mode": mode, "now": now, "states": registries, "activity": activity, "running": {}, "out_fps": fps}
    dep_rows = {bid: {r["id"]: r for r in O.eval_dependencies(b, dctx)[0]} for bid, b in manifest["brains"].items()}
    cost_day = O.cost_rollup(execs, day)

    brains, blockers, next_dues = {}, [], []
    for bid, b in sorted(manifest["brains"].items()):
        reg = registries.get(bid) or {}
        h = (health.get(bid) or {})
        sc = (scores or {}).get(bid) or {}
        mj = [mj for mj in manifest["jobs"].values() if mj.get("brainId") == bid and mj["classification"] == "VALIDATION_EXCEPTION"]
        enabled = _job_enabled(jobs, (b.get("schedule") or {}).get("scheduler"), scheduler_states)
        bl = [d for d in latest.values() if d["brainId"] == bid and d["decision"] in ("BLOCKED_DEPENDENCY", "BLOCKED_POLICY", "MANUAL_APPROVAL", "WAITING")]
        # BLOCKED_POLICY on the SCHEDULE trigger is the intended steady state of a manual Brain; it is a blocker only if someone asked for a run
        bl = [d for d in bl if d["decision"] != "BLOCKED_POLICY" or d["trigger"] != "SCHEDULE"]
        for d in bl:
            blockers.append({"brainId": bid, "decision": d["decision"], "trigger": d["trigger"], "reason": d["reason"], "since": d.get("since")})
        last_run = reg.get("lastSuccessfulRun")
        ageh = age_hours(last_run, now) if last_run else None
        sh = (b.get("freshness") or {}).get("staleAfterHours")
        nd = (jobs.get((b.get("schedule") or {}).get("scheduler") or "", {}) or {}).get("nextScheduledAt") if enabled else None
        if nd:
            next_dues.append(nd)
        lastx = next((e for e in execs if e.get("brainId") == bid), None)
        fpv, basis = O.output_fingerprint(b, reg)
        brains[_key(bid)] = _strip({
            "brainId": bid, "displayName": b["displayName"], "group": b["group"], "health": h.get("status") or reg.get("health"), "lifecycle": b["lifecycle"],
            "legacyStatus": reg.get("status"), "activityState": activity[bid],
            "scoreRef": {"path": f"/scores/{bid}", "canonicalScore": sc.get("value"), "scoreStatus": sc.get("basis")} if sc else None,
            "productReadiness": reg.get("productReadiness"),
            "executionMode": execution_mode(b, enabled), "scheduleClass": (b.get("schedule") or {}).get("class"),
            "exception": {k: v for k, v in ((b.get("schedule") or {}).get("exception") or {}).items() if k in ("gate", "stop", "maxMonthlyUsd", "approvedAt")},
            "lastRun": last_run, "lastResult": (lastx or {}).get("status") or h.get("status"), "nextDue": nd,
            "freshness": {"staleAfterHours": sh, "ageHours": ageh, "stale": (ageh > sh) if (ageh is not None and sh is not None) else None},
            "inputFingerprint": O.input_fingerprint(bid, b, fps),
            "inputChanged": (None if not (prev.get("brains") or {}).get(_key(bid), {}).get("inputFingerprint") else
                             ("UNCHANGED" if prev["brains"][_key(bid)]["inputFingerprint"] == O.input_fingerprint(bid, b, fps) else "CHANGED")),
            "outputChanged": changes.get(bid), "outputFingerprint": fpv, "outputFingerprintBasis": basis,
            "costToday": O.cost_rollup([e for e in execs if e.get("brainId") == bid], day),
            "currentBlocker": (bl[0]["reason"] if bl else None),
            "decisions": {d["trigger"]: {"decision": d["decision"], "reasonCode": d["reasonCode"], "reason": d["reason"], "since": d.get("since")}
                          for d in latest.values() if d["brainId"] == bid},
            "customerPublication": O.publish_allowed(mode, b), "costClass": b["costClass"], "scopes": b.get("scopes"),
            "retry": {"failureClass": (lastx or {}).get("failureClass")} if (lastx or {}).get("failureClass") else None,
        })
    runs = sorted(evaluation.get("runs") or [])
    by_act = {a: sorted(b for b, s in activity.items() if s == a) for a in O.ACTIVITY_STATES}
    decision_counts: dict[str, int] = {}
    for d in evaluation["decisions"]:
        decision_counts[d["decision"]] = decision_counts.get(d["decision"], 0) + 1
    status = "BLOCKED" if graph["errors"] else ("DEGRADED" if any(h.get("status") in ("FAILED", "DEGRADED") for h in health.values() if isinstance(h, dict)) else "IDLE" if not runs else "ACTIVE")
    latest_ev = max(recent.values(), key=lambda d: d.get("at", ""), default=None)
    summary = _strip({
        "version": O.CONTROL_VERSION, "engineMode": mode, "status": status,
        "policy": "PRE_PRODUCTION: recurring compute OFF by default; customer publication disabled; only approved validation exceptions run on a schedule" if mode == "PRE_PRODUCTION" else None,
        "lastCycle": {"trigger": trigger, "durationMs": duration_ms, "decisionCounts": decision_counts, "lastEvaluatedAt": iso(now)},
        "activeBrains": by_act["ACTIVE"], "parkedBrains": by_act["PARKED"], "maintenanceBrains": by_act["MAINTENANCE"],
        "running": sorted(k.split("|")[0] for k in (locks or {}) if (parse_time((locks[k] or {}).get("lockedUntil")) or now) > now),
        "queued": runs, "blocked": sorted({b["brainId"] for b in blockers}), "nextDue": min(next_dues) if next_dues else None,
        "costToday": cost_day, "recentDecision": ({k: latest_ev[k] for k in ("decisionId", "brainId", "trigger", "decision", "reasonCode", "at") if k in latest_ev} if latest_ev else None),
        "scheduler": _strip({"state": "ENABLED" if _job_enabled(jobs, "brain-orchestrator", scheduler_states) else ("PAUSED" if _job_enabled(jobs, "brain-orchestrator", scheduler_states) is False else None),
                             "cron": ((jobs or {}).get("brain-orchestrator") or {}).get("cron")}),
        "graphValid": not graph["errors"], "customerPublication": False if mode == "PRE_PRODUCTION" else None,
    })
    edge_out = {}
    for e in O.edges(manifest):
        r = dep_rows.get(e["to"], {}).get(e["from"], {})
        # Read vs run, per edge: the consumer's view of the upstream's EXISTING state and what the orchestrator does about it (READ_EXISTING = no execution).
        edge_out[_key(e["from"], e["to"])] = _strip({**e, "status": r.get("status"), "action": r.get("action"), "upstreamActivity": activity.get(e["from"])})
    state = {"summary": summary, "brains": brains, "edges": edge_out, "jobs": jobs_out, "schedules": scheds,
             "executions": {e["executionId"]: _strip(e) for e in execs}, "decisions": recent, "latestDecisions": latest,
             "health": {"graphErrors": graph["errors"], "graphWarnings": graph["warnings"],
                        "brains": {_key(b): (health.get(b) or {}).get("status") for b in manifest["brains"] if (health.get(b) or {}).get("status")}},
             "cost": _strip({"today": cost_day, "enabledMonthlyEstimateUsd": round(sum(mj.get("estMonthlyUsdWhenEnabled") or 0 for jid, mj in manifest["jobs"].items()
                                                                                      if _job_enabled(jobs, mj.get("scheduler"), scheduler_states) is True), 2),
                             "basis": "ESTIMATED", "note": "list-price estimate from job resources and runtime; not a bill"}),
             "blockers": blockers, "graph": {"order": graph["order"], "errors": graph["errors"], "warnings": graph["warnings"]},
             "overrides": overrides or {}, "requests": requests if requests is not None else (prev.get("requests") or {})}
    return _finalize(state)


def _finalize(state: dict) -> dict:
    """RTDB drops empty containers; strip them here so published == computed and comparisons are stable. `blockers` is a list (RTDB stores it as an indexed map)."""
    out = _strip(state)
    out["blockers"] = {f"{i:02d}": b for i, b in enumerate(state.get("blockers") or [])}
    return _strip(out)


def _stable(v):
    if isinstance(v, dict):
        return {k: _stable(x) for k, x in v.items() if k not in VOLATILE}
    if isinstance(v, list):
        return [_stable(x) for x in v]
    return v


def changed_paths(state: dict, published: dict | None) -> dict:
    """RTDB multi-path update containing only sections whose content (ignoring evaluation timestamps) differs. Whole-section replace keeps retention
    honest (an expired execution disappears). Summary is rewritten whenever any other section changes so `lastEvaluatedAt` means something."""
    published = published or {}
    out = {f"{NODE}/{s}": state[s] for s in SECTIONS if s in state and _stable(state[s]) != _stable(published.get(s))}
    for s in SECTIONS:                                   # a section that disappeared (e.g. blockers cleared) must be deleted
        if s not in state and s in published:
            out[f"{NODE}/{s}"] = None
    if out and "summary" in state:
        out[f"{NODE}/summary"] = state["summary"]
    elif not out and "summary" in state:
        # Heartbeat: an unchanged control plane is not rewritten, but `lastEvaluatedAt` must not go stale forever.
        new_t = parse_time((state["summary"].get("lastCycle") or {}).get("lastEvaluatedAt"))
        old_t = parse_time(((published.get("summary") or {}).get("lastCycle") or {}).get("lastEvaluatedAt"))
        if new_t and (old_t is None or (new_t - old_t).total_seconds() >= HEARTBEAT_HOURS * 3600):
            out[f"{NODE}/summary"] = state["summary"]
    return out
