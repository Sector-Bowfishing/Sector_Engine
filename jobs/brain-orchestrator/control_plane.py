"""Orchestrator control plane glue (docs/brains/platform/orchestrator/ORCHESTRATOR_CONTROL_V1.md): reads the published world, asks the pure decision
model what should happen, and publishes the compact read-only control state. Nothing here knows any domain science."""
from __future__ import annotations

import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
from sector_brain_platform import orchestration as O, control_state as C, iso  # noqa: E402
from sector_brain_platform import fingerprint as F                                # noqa: E402
from sector_brain_platform.timeutil import parse_time                             # noqa: E402

MAX_REQUESTS = 30


def load_world(live, now: dt.datetime) -> dict:
    """Everything the decision model needs, with read-only GETs. Missing stays missing."""
    manifest = O.load_manifest()
    prev = live.get("control/orchestratorV1") or {}
    return {"manifest": manifest, "prev": prev, "registries": live.get("brains") or {}, "health": live.get("health/brains") or {},
            "scores": live.get("scores") or {}, "overrides": prev.get("overrides") or {}}


def build_ctx(world: dict, now: dt.datetime, locks: dict | None, own_inputs: dict | None = None) -> dict:
    m, regs, prev = world["manifest"], world["registries"], world["prev"]
    running = {k: v for k, v in (locks or {}).items() if (parse_time((v or {}).get("lockedUntil")) or now) > now}
    out_fps = {bid: O.output_fingerprint(b, regs.get(bid))[0] for bid, b in m["brains"].items()}
    last_in = {}
    for rec in (prev.get("decisions") or {}).values():
        if rec.get("decision") == "RUN" and rec.get("inputFingerprint"):
            last_in.setdefault(rec["brainId"], rec["inputFingerprint"])
    return {"manifest": m, "mode": m["engineMode"], "now": now, "states": regs, "activity": O.effective_activity(m, world["overrides"]),
            "running": running, "out_fps": out_fps, "last_in_fps": last_in, "own_inputs": own_inputs or {}}


def prev_output_fps(world: dict) -> dict | None:
    """None = no baseline yet (first observation never cascades)."""
    pb = world["prev"].get("brains")
    if not pb:
        return None
    return {bid: (pb.get(bid) or {}).get("outputFingerprint") for bid in world["manifest"]["brains"]}


def evaluate(world: dict, now: dt.datetime, locks: dict | None, brain_plans: dict | None = None, run_now: tuple | None = None) -> tuple[dict, dict]:
    """-> (ctx, evaluation). brain_plans: {brainId: its own --plan verdict}; a PUBLISH verdict is that Brain's INPUT_CHANGED signal."""
    own = {}
    for bid, p in (brain_plans or {}).items():
        if (p or {}).get("action") == "PUBLISH":
            own[bid] = F.fingerprint({"reasons": p.get("reasons") or []})
    ctx = build_ctx(world, now, locks, own)
    ev = O.evaluate_world(ctx, prev_output_fps(world))
    for bid in sorted(own):
        ev["decisions"].append(O.decide_brain(bid, "INPUT_CHANGED", ctx))
    if run_now:
        bid, scope, who = run_now
        ev["decisions"].append(O.decide_brain(bid, "MANUAL", ctx, scope=scope, requested_by=who))
    ev["runs"] = sorted({d["brainId"] for d in ev["decisions"] if d["decision"] == "RUN"})
    return ctx, ev


def executions_from_cloud_run(manifest: dict, executions: dict, jobs_records: dict, now: dt.datetime, hours: int = 48) -> list[dict]:
    """Ledger records for Cloud Run executions the orchestrator did not start (legacy schedulers, manual runs). Trigger is inferred only for
    simple UTC crons and otherwise stays UNKNOWN; cost is an ESTIMATE from manifest resources and measured duration."""
    out = []
    for jid, mj in manifest["jobs"].items():
        if not mj.get("brainId"):          # the orchestrator's own wake-ups are the control plane, not a Brain execution: summary.lastCycle carries the evaluation
            continue
        for e in (executions.get(jid) or []):
            st = e.get("status") or {}
            start, end = parse_time(st.get("startTime")), parse_time(st.get("completionTime"))
            if not start or (now - start).total_seconds() > hours * 3600:
                continue
            name = (e.get("metadata") or {}).get("name") or ""
            ok = (st.get("succeededCount") or 0) > 0 and not st.get("failedCount")
            status = "RUNNING" if not end else ("SUCCEEDED" if ok else "FAILED")
            live = jobs_records.get(jid) or jobs_records.get(mj.get("scheduler") or "") or {}
            trig = O.infer_trigger(start, live.get("cron")) if live.get("timezone", "UTC") == "UTC" else "UNKNOWN"
            tasks = (e.get("spec") or {}).get("taskCount") or (mj.get("resources") or {}).get("tasks")
            rec = O.execution_record(name, mj.get("brainId") or "platform", trig,
                                     "legacy scheduler fire" if trig == "SCHEDULE" else "started outside the orchestrator (trigger not recorded)",
                                     start, end, status, resources=mj.get("resources"), source="cloud-run")
            rec["jobId"] = jid
            out.append(rec)
    return out


def process_requests(live, world: dict, ctx: dict, write: bool) -> dict:
    """Validate pending Ops control requests (/controlRequests/pending/{id}) against policy and store the outcome. Ops cannot write that node under
    today's rules (read-only); the request channel needs an Ops-side change (see the contract). Accepted PAUSE/RESUME become overrides."""
    pending = live.get("controlRequests/pending") or {}
    results, overrides = dict(world["prev"].get("requests") or {}), dict(world["overrides"])
    for rid, req in sorted(pending.items()):
        if rid in results:
            continue
        r = O.evaluate_request({**req, "requestId": req.get("requestId") or rid}, ctx)
        r = {k: v for k, v in r.items() if k != "decision_record"} | ({"decisionId": r["decision_record"]["decisionId"]} if r.get("decision_record") else {})
        results[rid] = r
        if r["decision"] == "ACCEPTED" and (r.get("effect") or {}).get("activityState"):
            overrides[r["brainId"]] = {"activityState": r["effect"]["activityState"], "by": r["requestedBy"], "requestId": rid, "at": r["at"]}
    keep = dict(sorted(results.items(), key=lambda kv: kv[1].get("at", ""), reverse=True)[:MAX_REQUESTS])
    return {"requests": keep, "overrides": overrides}
