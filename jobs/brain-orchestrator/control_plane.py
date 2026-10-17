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
                                     start, end, status, resources=mj.get("resources"), source="cloud-run",
                                     code_version=live.get("sourceVersion") or None, job_id=jid)     # the job's `commit` label when the /jobs sync saw one
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


def scheduler_states(tokens) -> dict:
    """{schedulerName: ENABLED|PAUSED} straight from Cloud Scheduler (one read-only list call). Any failure -> {} (unknown stays unknown)."""
    try:
        from sector_brain_platform import gcp
        return {(j.get("name") or "").rsplit("/", 1)[-1]: j.get("state") for j in gcp.list_scheduler_jobs(tokens) if j.get("name")}
    except Exception:
        return {}


# ---------------------------------------------------------------------------------------------------------- G1/G2: brain-health-v1 (control/healthV1)
# Everything below is generic glue: it reads the published world and the platform registries and hands them to the pure health builders.
# No Brain id, signal id or provider id appears here; relationships come from brains/*/brain.json, the Signal Registry and the execution manifest.
from sector_brain_platform import brain_health as BH, dependency_declarations as DD, signals as SG   # noqa: E402
from sector_brain_platform.jobs import cron_runs_per_day                                              # noqa: E402

HEALTH_NODE = BH.NODE


def expected_interval_hours(brain: dict, jobs_records: dict, scheduler_states: dict | None) -> float | None:
    """The Brain's recurring CADENCE expectation, from its schedule (cron of an ENABLED scheduler) — never from freshness.staleAfterHours,
    which is an evidence rule. None = no recurring expectation (manual / event-driven / paused)."""
    sch = brain.get("schedule") or {}
    name = sch.get("scheduler")
    if not name or sch.get("class") not in ("VALIDATION_EXCEPTION", "ORCHESTRATOR_OWNED", "LEGACY"):
        return None
    if C._job_enabled(jobs_records, name, scheduler_states) is not True:
        return None
    runs = cron_runs_per_day(((jobs_records or {}).get(name) or {}).get("cron") or sch.get("cron"))
    return None if not runs else round(24.0 / runs, 4)


def observe_dependencies(rows: list[dict], registries: dict, sources: dict | None, source_health: dict | None, signals_registry: dict | None) -> dict:
    """{dependencyId: observed | None}: what the Engine can read NOW about each declared dependency, by TYPE only.
    Brain -> /brains/{id} (registry); provider -> /sources/{id} + /health/sources/{id}; signal -> the Signal Registry (no runtime signal
    publication exists yet); platform registry -> not versioned yet. lastSuccessfulRun is carried so the evaluator can SAY it is not freshness."""
    out: dict = {}
    for r in rows:
        t, target = r["dependencyType"], r["target"]
        if t == "BRAIN":
            reg = (registries or {}).get(target)
            if not isinstance(reg, dict):
                out[r["dependencyId"]] = None
                continue
            fr = reg.get("freshness") if isinstance(reg.get("freshness"), dict) else {}
            obs = {"available": True, "ref": f"/brains/{target}"}
            for k in ("freshnessStatus", "evidenceObservedAt", "generatedAt", "publishedAt", "staleAfter", "expiresAt", "stale", "evidenceStale"):
                v = fr.get(k, reg.get(k))
                if v is not None:
                    obs[k] = v
            if obs.get("evidenceObservedAt") is None and (fr.get("sourceObservationAt") or reg.get("sourceObservationAt")):
                obs["evidenceObservedAt"] = fr.get("sourceObservationAt") or reg.get("sourceObservationAt")
            if reg.get("staleAfterHours") is not None:
                obs["staleAfterHours"] = reg["staleAfterHours"]
            if reg.get("lastSuccessfulRun"):
                obs["lastSuccessfulRun"] = reg["lastSuccessfulRun"]
            sv = reg.get("stateVersion") or reg.get("version")
            if sv is not None:
                obs["stateVersion"] = str(sv)
            if isinstance(reg.get("fingerprint"), str):
                obs["fingerprint"] = reg["fingerprint"]
            out[r["dependencyId"]] = obs
        elif t == "PROVIDER_DATA":
            src = (sources or {}).get(target)
            hs = (source_health or {}).get(target)
            if not isinstance(src, dict) and not isinstance(hs, dict):
                out[r["dependencyId"]] = None
                continue
            src, hs = src if isinstance(src, dict) else {}, hs if isinstance(hs, dict) else {}
            obs = {"available": True, "ref": f"/sources/{target}"}
            ev = src.get("latestObservationAt") or src.get("lastObservationAt") or src.get("latestIssuedAt") or hs.get("lastObservationAt")
            if ev:
                obs["evidenceObservedAt"] = ev
            if src.get("staleThresholdHours") is not None:
                obs["staleAfterHours"] = src["staleThresholdHours"]          # the OWNER's declared threshold for its own source
            st = hs.get("status") or src.get("health")
            if st:
                obs["reason"] = f"source health {st} (owner-reported)"
            out[r["dependencyId"]] = obs
        elif t == "ENVIRONMENTAL_SIGNAL":
            av, why = SG.availability(signals_registry, target)
            if av == "UNAVAILABLE":
                out[r["dependencyId"]] = {"available": False, "reason": why}
            else:
                out[r["dependencyId"]] = {"available": None, "reason": why + "; runtime signal publication is not implemented yet"}
        else:
            out[r["dependencyId"]] = {"available": None, "reason": f"platform registry {target!r} publishes no contract version yet (structure only)"}
    return out


def load_health_world(live) -> dict:
    """The extra read-only GETs the health plane needs (only when the health plane is requested: no recurring cost otherwise)."""
    return {"sources": live.get("sources") or {}, "sourceHealth": live.get("health/sources") or {}}


def build_health_state(world: dict, control_state: dict, jobs_records: dict, now: dt.datetime, *, scheduler_states: dict | None = None,
                       sources: dict | None = None, source_health: dict | None = None, root: str | None = None, code_version: str | None = None,
                       registered: dict | None = None) -> dict:
    """The whole control/healthV1 node from the published world + the platform registries. Pure given its inputs."""
    m, regs, health = world["manifest"], world["registries"], world["health"]
    registered = DD.load_registered_brains(root) if registered is None else registered
    signals_registry = SG.load() if os.path.exists(SG.DEFAULT_PATH) else None
    providers = DD.load_providers(root)
    graph = DD.dependency_graph(registered, manifest=m, signals=signals_registry, providers=providers)
    execs: dict[str, list] = {}
    for e in (control_state.get("executions") or {}).values():
        if isinstance(e, dict) and e.get("brainId"):
            execs.setdefault(e["brainId"], []).append(e)
    brains = {}
    for bid, g in graph["brains"].items():
        b = (m.get("brains") or {}).get(bid) or {}
        tgt = b.get("executionTarget") or {}
        obs = observe_dependencies(g["rows"], regs, sources, source_health, signals_registry)
        brains[bid] = BH.brain_health(bid, declared=g["rows"], declarations_known=g["declarationsKnown"], executions=execs.get(bid) or [], observations=obs,
                                      now=now, expected_interval_hours=expected_interval_hours(b, jobs_records, scheduler_states),
                                      brain_health_record=(health or {}).get(bid) if isinstance((health or {}).get(bid), dict) else None,
                                      registry=regs.get(bid) if isinstance(regs.get(bid), dict) else None,
                                      runtime_configured=(tgt.get("kind") != "none") if tgt else True, code_version=code_version)
    return BH.health_state(brains, graph, signals_registry, now, engine_mode=m.get("engineMode"))
