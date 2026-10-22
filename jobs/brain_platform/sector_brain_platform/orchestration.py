"""Brain Orchestrator decision model (docs/brains/platform/orchestrator/ORCHESTRATOR_CONTROL_V1.md).

The traffic cop. It understands contracts, dependencies, execution metadata, material change, schedules and state. It does NOT understand
wind physics, fish biology, clarity models, depth or vegetation science: those live in the specialist Brains, which only tell the
orchestrator *how* to run, what they consume, and a fingerprint of what they produced.

Pure and stdlib-only: given the manifest, the published world and a trigger, produce a DECISION RECORD. Nothing here starts a job or writes a node.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

from . import fingerprint as fp
from .timeutil import iso, parse_time

CONTROL_VERSION = "orchestrator-control-v1"
MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "control_manifest.json")

ENGINE_MODES = ("PRE_PRODUCTION", "PRODUCTION")
ACTIVITY_STATES = ("ACTIVE", "PARKED", "MAINTENANCE")
TRIGGERS = ("SCHEDULE", "MANUAL", "INPUT_CHANGED", "DEPENDENCY_CHANGED", "VALIDATION", "RECOVERY", "ADMIN")
EXPLICIT_TRIGGERS = ("MANUAL", "ADMIN", "VALIDATION", "RECOVERY")          # a person/validation plan asked for this run
AUTOMATIC_TRIGGERS = ("SCHEDULE", "INPUT_CHANGED", "DEPENDENCY_CHANGED")   # the system decided
DECISIONS = ("RUN", "SKIP_UNCHANGED", "SKIP_PARKED", "SKIP_NOT_DUE", "SKIP_LEGACY_OWNED", "SKIP_UNKNOWN_CHANGE",
             "BLOCKED_DEPENDENCY", "BLOCKED_POLICY", "WAITING", "MANUAL_APPROVAL")
SCHEDULE_CLASSES = ("ORCHESTRATOR_OWNED", "LEGACY", "VALIDATION_EXCEPTION", "MANUAL", "INPUT_DRIVEN", "PAUSED")
COST_CLASSES = ("NONE", "LOW", "MEDIUM", "HEAVY")
GROUPS = ("FOUNDATION", "CURRENT_CONDITIONS", "ENVIRONMENT", "BIOLOGICAL", "SYNTHESIS")
DEP_REQUIREMENT = ("REQUIRED", "OPTIONAL")
ON_STALE = ("DEPENDENCY_STALE", "MANUAL_APPROVAL", "RUN_DEPENDENCY")
CHANGE = ("CHANGED", "UNCHANGED", "UNKNOWN")
FAILURE_CLASSES = ("TRANSIENT_PROVIDER", "TRANSIENT_RUNTIME", "INVALID_INPUT", "DEPENDENCY_BLOCKED", "PERMANENT_CONFIG")
RETRYABLE = ("TRANSIENT_PROVIDER", "TRANSIENT_RUNTIME")
REQUEST_ACTIONS = ("RUN_NOW", "PAUSE", "RESUME", "SET_MANUAL")
PROTECTED_ACTIONS = ("SET_ENGINE_MODE", "ACTIVATE_PRODUCTION", "PUBLISH_CUSTOMER", "CHANGE_PROTECTED_SCHEDULE", "PROMOTE_LIFECYCLE",
                     "DISABLE_VALIDATION_CAPTURE")
REQUEST_DECISIONS = ("ACCEPTED", "REJECTED", "NEEDS_CONFIRMATION")
COST_BASIS = ("MEASURED", "ESTIMATED", "UNKNOWN")

# List prices, us-central1 tier 1 (Cloud Run jobs); an ESTIMATE, never presented as a bill.
VCPU_SECOND_USD, GIB_SECOND_USD = 0.000024, 0.0000025
EXECUTION_LEDGER_MAX = 60
DECISION_LEDGER_MAX = 120


class ManifestError(ValueError):
    pass


# ------------------------------------------------------------------------------------------------------------ manifest
def load_manifest(path: str = MANIFEST_PATH) -> dict:
    m = json.load(open(path))
    errs = validate_manifest(m)
    if errs:
        raise ManifestError("; ".join(errs))
    return m


def validate_manifest(m: dict) -> list[str]:
    """Structural errors only (the dependency graph is validated by `validate_graph`)."""
    errs = []
    if m.get("engineMode") not in ENGINE_MODES:
        errs.append(f"engineMode {m.get('engineMode')!r} not in {ENGINE_MODES}")
    for bid, b in (m.get("brains") or {}).items():
        if b.get("activityState") not in ACTIVITY_STATES:
            errs.append(f"{bid}: activityState {b.get('activityState')!r}")
        if b.get("group") not in GROUPS:
            errs.append(f"{bid}: group {b.get('group')!r}")
        for t in b.get("allowedTriggers", []):
            if t not in TRIGGERS:
                errs.append(f"{bid}: trigger {t!r}")
        if (b.get("schedule") or {}).get("class") not in SCHEDULE_CLASSES:
            errs.append(f"{bid}: schedule.class {(b.get('schedule') or {}).get('class')!r}")
        if b.get("costClass") not in COST_CLASSES:
            errs.append(f"{bid}: costClass {b.get('costClass')!r}")
        if b.get("customerPublication") not in (False, None) and m.get("engineMode") == "PRE_PRODUCTION":
            errs.append(f"{bid}: customerPublication must be false in PRE_PRODUCTION")
        for d in b.get("dependencies", []):
            if d.get("requirement") not in DEP_REQUIREMENT:
                errs.append(f"{bid}->{d.get('id')}: requirement {d.get('requirement')!r}")
            if d.get("onStale") not in ON_STALE:
                errs.append(f"{bid}->{d.get('id')}: onStale {d.get('onStale')!r}")
    for jid, j in (m.get("jobs") or {}).items():
        if j.get("classification") not in SCHEDULE_CLASSES:
            errs.append(f"job {jid}: classification {j.get('classification')!r}")
    return errs


def validate_graph(m: dict) -> dict:
    """{errors[], warnings[], order[]}. Unknown dependency ids, self-edges and cycles are ERRORS (fail closed); a Brain that declares no
    `dependencies` key at all is a visible WARNING (missing metadata is not the same as 'no dependencies')."""
    brains = m.get("brains") or {}
    errors, warnings = [], []
    for bid, b in brains.items():
        if "dependencies" not in b:
            warnings.append(f"{bid}: no dependency metadata declared")
        for d in b.get("dependencies", []):
            if d["id"] == bid:
                errors.append(f"{bid}: depends on itself")
            elif d["id"] not in brains:
                errors.append(f"{bid}: depends on unknown Brain {d['id']!r}")
    order, state = [], {}

    def visit(n, path):
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            errors.append("dependency cycle: " + " -> ".join(path + [n]))
            return
        state[n] = 1
        for d in brains[n].get("dependencies", []):
            if d["id"] in brains and d["id"] != n:
                visit(d["id"], path + [n])
        state[n] = 2
        order.append(n)
    for n in sorted(brains):
        visit(n, [])
    return {"errors": errors, "warnings": warnings, "order": order if not errors else []}


def consumers_of(m: dict, brain_id: str) -> list[dict]:
    """[{consumer, requirement, usesFields?}] for every Brain that lists `brain_id` as a dependency."""
    out = []
    for cid, b in (m.get("brains") or {}).items():
        for d in b.get("dependencies", []):
            if d["id"] == brain_id:
                out.append({"consumer": cid, "requirement": d["requirement"], "usesFields": d.get("usesFields")})
    return sorted(out, key=lambda x: x["consumer"])


def edges(m: dict) -> list[dict]:
    """Machine-readable edges. `kind`: HARD (requirement REQUIRED) or SOFT (OPTIONAL). A consumer reading existing state is an edge too: reading is not running."""
    out = []
    for cid, b in sorted((m.get("brains") or {}).items()):
        for d in b.get("dependencies", []):
            out.append({"from": d["id"], "to": cid, "kind": "HARD" if d["requirement"] == "REQUIRED" else "SOFT", "maxAgeHours": d.get("maxAgeHours"),
                        "onStale": d["onStale"], "usesFields": d.get("usesFields"), "provisional": bool(d.get("provisional"))})
    return out


# ------------------------------------------------------------------------------------------------------------ policy
def effective_activity(m: dict, overrides: dict | None = None) -> dict[str, str]:
    """activityState per Brain: the manifest, then accepted overrides (PAUSE -> PARKED, RESUME -> ACTIVE). Never hard-coded in decision logic."""
    out = {bid: b["activityState"] for bid, b in m["brains"].items()}
    for bid, o in (overrides or {}).items():
        if bid in out and (o or {}).get("activityState") in ACTIVITY_STATES:
            out[bid] = o["activityState"]
    return out


def schedule_policy(brain: dict, mode: str) -> tuple[bool, str]:
    """PRE_PRODUCTION: a recurring schedule needs a named readiness purpose, bounded cost, a stop condition and a reason the timed evidence
    cannot be recreated. Without all four -> not allowed (manual / input-driven / off). Encoded, not only documented."""
    sch = brain.get("schedule") or {}
    if mode != "PRE_PRODUCTION":
        return False, "recurring policy for PRODUCTION is not defined: fail closed"
    if sch.get("class") not in ("VALIDATION_EXCEPTION", "ORCHESTRATOR_OWNED", "LEGACY"):
        return False, f"schedule class {sch.get('class')} is not a recurring class"
    ex = sch.get("exception") or {}
    missing = [k for k in ("gate", "notReconstructable", "maxMonthlyUsd", "stop", "approvedAt") if not ex.get(k)]
    if missing:
        return False, f"PRE_PRODUCTION recurring schedule lacks {missing}"
    return True, "approved recurring-schedule exception (gate, cost cap, stop, approval recorded)"


def publish_allowed(mode: str, brain: dict) -> bool:
    """Customer publication is never enabled in PRE_PRODUCTION, and in PRODUCTION only for a PRODUCTION-lifecycle Brain that opted in."""
    return mode == "PRODUCTION" and bool(brain.get("customerPublication")) and brain.get("lifecycle") == "PRODUCTION"


# ------------------------------------------------------------------------------------------------------------ material change
def classify_change(prev: str | None, new: str | None) -> str:
    """CHANGED | UNCHANGED | UNKNOWN. Unknown stays unknown: a missing fingerprint is not 'no change' and not 'change'."""
    if new is None:
        return "UNKNOWN"
    if prev is None:
        return "CHANGED"          # first observation
    return "UNCHANGED" if prev == new else "CHANGED"


def output_fingerprint(brain: dict, registry: dict | None) -> tuple[str | None, str]:
    """-> (fingerprint|None, basis). The Brain's own fingerprint wins; otherwise a hash of the manifest-declared registry projection
    (basis REGISTRY_PROJECTION: contract-level, no domain knowledge); otherwise None/UNKNOWN."""
    reg = registry or {}
    src = (brain.get("fingerprint") or {}).get("outputSource")
    if src and src.startswith("registry:"):
        v = reg.get(src.split(":", 1)[1])
        return (str(v), "BRAIN_OWNED") if v else (None, "UNKNOWN")
    if src == "registryProjection":
        fields = (brain.get("fingerprint") or {}).get("materialFields") or []
        proj = {f: reg[f] for f in fields if f in reg}
        return (fp.fingerprint(proj), "REGISTRY_PROJECTION") if proj else (None, "UNKNOWN")
    return None, "UNKNOWN"


def input_fingerprint(brain_id: str, brain: dict, out_fps: dict[str, str | None], own: str | None = None) -> str:
    """Generic input fingerprint of a consumer = the output fingerprints of what it depends on (UNKNOWN stays distinct from any value), plus the
    Brain's OWN input signal when it reports one (e.g. Biological's research-bundle change from its own `--plan`)."""
    body = {d["id"]: (out_fps.get(d["id"]) or "UNKNOWN") for d in brain.get("dependencies", [])}
    if own:
        body["__own"] = own
    return fp.fingerprint(body)


# ------------------------------------------------------------------------------------------------------------ dependency state
def dep_status(dep: dict, state: dict | None, now: dt.datetime) -> str:
    """FRESH | STALE | MISSING | UNKNOWN for a consumer's requirement on an upstream's EXISTING state."""
    if not state or not state.get("lastSuccessfulRun"):
        return "MISSING"
    last = parse_time(state["lastSuccessfulRun"])
    if last is None:
        return "UNKNOWN"
    cap = dep.get("maxAgeHours")
    if cap is None:
        s = state.get("stale")
        return "UNKNOWN" if s is None else ("STALE" if s else "FRESH")
    return "FRESH" if (now - last).total_seconds() / 3600 <= float(cap) else "STALE"


def eval_dependencies(brain: dict, ctx: dict) -> tuple[list[dict], dict | None]:
    """-> (dependency rows, blocking {decision, reason, runDependencies?} | None).
    A fresh upstream is READ, never woken. A stale one follows the consumer's `onStale` policy; waking a dependency additionally needs that
    dependency to be ACTIVE (a PARKED Brain is never woken implicitly)."""
    rows, block = [], None
    for d in brain.get("dependencies", []):
        st = dep_status(d, (ctx.get("states") or {}).get(d["id"]), ctx["now"])
        row = {"id": d["id"], "requirement": d["requirement"], "status": st, "action": "READ_EXISTING" if st == "FRESH" else "NONE"}
        if st != "FRESH":
            if d["requirement"] == "OPTIONAL":
                row["action"] = "IGNORED_OPTIONAL"
            else:
                row["action"] = d["onStale"]
                if d["onStale"] == "MANUAL_APPROVAL":
                    block = block or {"decision": "MANUAL_APPROVAL", "reason": f"required dependency {d['id']} is {st}; manual approval needed"}
                elif d["onStale"] == "RUN_DEPENDENCY":
                    if ctx["activity"].get(d["id"]) == "ACTIVE":
                        block = block or {"decision": "WAITING", "reason": f"required dependency {d['id']} is {st}; run it first", "runDependencies": [d["id"]]}
                    else:
                        row["action"] = "DEPENDENCY_STALE"
                        block = block or {"decision": "BLOCKED_DEPENDENCY", "reason": f"required dependency {d['id']} is {st} and is {ctx['activity'].get(d['id'])}: not woken"}
                else:
                    block = block or {"decision": "BLOCKED_DEPENDENCY", "reason": f"required dependency {d['id']} is {st}"}
        rows.append(row)
    return rows, block


# ------------------------------------------------------------------------------------------------------------ the decision
def _rec(ctx: dict, brain_id: str, trigger: str, decision: str, reason: str, code: str, **extra) -> dict:
    assert decision in DECISIONS and trigger in TRIGGERS
    now = ctx["now"]
    b = ctx["manifest"]["brains"].get(brain_id) or {}
    out = {"decisionId": f"d-{now:%Y%m%dT%H%M%SZ}-{brain_id}-{trigger}", "at": iso(now), "brainId": brain_id, "trigger": trigger,
           "decision": decision, "reason": reason, "reasonCode": code, "activityState": ctx["activity"].get(brain_id),
           "scheduleState": {"class": (b.get("schedule") or {}).get("class"), "owner": (b.get("schedule") or {}).get("owner")},
           "publish": False}
    out.update({k: v for k, v in extra.items() if v is not None})
    return out


def with_job_success(m: dict, states: dict, jobs: dict | None) -> dict:
    """Registry-ish states for the decision model, where a SCOPED Cloud Run job the orchestrator starts also counts its own last successful
    execution (/jobs/{job}.lastSuccessfulAt) as the Brain's lastSuccessfulRun. A scoped run (for example Water Temp on the 5 pilot lakes,
    internal operation 2026-10-22) refreshes its scope without restating the fleet registry, so the registry time alone would make the job due
    every cycle. The later of the two wins; nothing is invented when both are missing; unscoped and in-process Brains are unchanged."""
    out = dict(states or {})
    for bid, b in (m.get("brains") or {}).items():
        t = b.get("executionTarget") or {}
        if t.get("kind") != "cloud-run-job" or not t.get("startedByOrchestrator") or not t.get("scoped"):
            continue
        job_t = parse_time(((jobs or {}).get(t.get("job")) or {}).get("lastSuccessfulAt"))
        if job_t is None:
            continue
        reg = dict(out.get(bid) or {})
        reg_t = parse_time(reg.get("lastSuccessfulRun"))
        if reg_t is None or job_t > reg_t:
            reg["lastSuccessfulRun"] = iso(job_t)
            reg["lastSuccessfulRunBasis"] = f"job {t.get('job')} lastSuccessfulAt (scoped run)"
        out[bid] = reg
    return out


def due(brain: dict, state: dict | None, now: dt.datetime) -> bool | None:
    """Time-driven due check from the Brain's own freshness expectation. None = no time rule (VERSION/FINGERPRINT Brain: never 'due' by clock)."""
    h = (brain.get("freshness") or {}).get("staleAfterHours")
    if h is None:
        return None
    last = parse_time((state or {}).get("lastSuccessfulRun"))
    return True if last is None else (now - last).total_seconds() / 3600 >= float(h)


def decide_brain(brain_id: str, trigger: str, ctx: dict, scope: str | None = None, requested_by: str | None = None,
                 upstream: dict | None = None) -> dict:
    """One decision record. ctx: {manifest, mode, now, states{id: registry-ish state}, activity{id}, running{key}, out_fps{id}, last_in_fps{id}}.
    upstream (DEPENDENCY_CHANGED): {brainId, change CHANGED|UNCHANGED|UNKNOWN, changedFields?}."""
    m, now, mode = ctx["manifest"], ctx["now"], ctx["mode"]
    b = (m["brains"] or {}).get(brain_id)
    if b is None:
        return _rec(ctx, brain_id, trigger, "BLOCKED_POLICY", "unknown Brain (not in the execution manifest)", "UNKNOWN_BRAIN")
    extra = {"scope": scope, "requestedBy": requested_by}
    if mode != "PRE_PRODUCTION":
        return _rec(ctx, brain_id, trigger, "BLOCKED_POLICY", "engine mode other than PRE_PRODUCTION has no defined execution policy: fail closed", "MODE_UNDEFINED", **extra)
    sch0 = b.get("schedule") or {}
    key = f"{brain_id}|{scope or '*'}"
    if key in (ctx.get("running") or {}) or f"{brain_id}|*" in (ctx.get("running") or {}):
        return _rec(ctx, brain_id, trigger, "WAITING", "already running for this scope (single-flight)", "ALREADY_RUNNING", **extra)
    if trigger == "SCHEDULE" and "SCHEDULE" not in b.get("allowedTriggers", []):
        return _rec(ctx, brain_id, trigger, "SKIP_NOT_DUE", f"no recurring schedule intent ({sch0.get('class')}): runs only on manual, input or dependency triggers", "NO_SCHEDULE_INTENT", **extra)
    if trigger not in b.get("allowedTriggers", []):
        if trigger in AUTOMATIC_TRIGGERS:      # an automatic propagation this Brain does not accept is a plain skip, not a blocker
            return _rec(ctx, brain_id, trigger, "SKIP_NOT_DUE", f"{brain_id} does not accept {trigger}", "TRIGGER_NOT_ENABLED", **extra)
        return _rec(ctx, brain_id, trigger, "BLOCKED_POLICY", f"trigger {trigger} is not allowed for {brain_id}", "TRIGGER_NOT_ALLOWED", **extra)
    activity = ctx["activity"].get(brain_id, b["activityState"])
    sch = b.get("schedule") or {}

    if trigger == "SCHEDULE":
        if sch.get("owner") == "LEGACY_SCHEDULER":
            # a legacy scheduler (not the orchestrator) starts this job; the orchestrator observes it and never double-starts
            return _rec(ctx, brain_id, trigger, "SKIP_LEGACY_OWNED", f"scheduled by legacy scheduler {sch.get('scheduler')} ({sch.get('class')}); the orchestrator does not start it",
                        "LEGACY_OWNED", **extra)
        ok, why = schedule_policy(b, mode)
        if not ok:
            code = "RECURRING_OFF_BY_DEFAULT"
            return _rec(ctx, brain_id, trigger, "BLOCKED_POLICY", f"recurring compute is OFF in PRE_PRODUCTION: {why}", code, **extra)
    if activity == "PARKED" and trigger in AUTOMATIC_TRIGGERS + ("RECOVERY",):
        return _rec(ctx, brain_id, trigger, "SKIP_PARKED", "Brain is PARKED: does not execute automatically (existing state remains readable)", "PARKED", **extra)
    if activity == "PARKED" and trigger == "VALIDATION" and sch.get("class") != "VALIDATION_EXCEPTION":
        return _rec(ctx, brain_id, trigger, "SKIP_PARKED", "PARKED Brain without an approved validation exception", "PARKED", **extra)
    if activity == "MAINTENANCE" and trigger in ("INPUT_CHANGED", "DEPENDENCY_CHANGED"):
        return _rec(ctx, brain_id, trigger, "SKIP_PARKED", "MAINTENANCE Brain: limited approved operations only, no automatic expansion", "MAINTENANCE_LIMITED", **extra)

    # bounded retry (PL-02): an AUTOMATIC trigger never re-runs a Brain whose recent runs failed beyond the retry policy
    gate = retry_gate(brain_id, trigger, ctx)
    if gate is not None:
        return _rec(ctx, brain_id, trigger, gate["decision"], gate["reason"], gate["code"], retry=gate["retry"], **extra)

    # material-change gating for automatic downstream triggers
    in_fp = input_fingerprint(brain_id, b, ctx.get("out_fps") or {}, (ctx.get("own_inputs") or {}).get(brain_id))
    if trigger == "DEPENDENCY_CHANGED":
        ch = (upstream or {}).get("change", "UNKNOWN")
        if ch == "UNCHANGED":
            return _rec(ctx, brain_id, trigger, "SKIP_UNCHANGED", f"NO_MATERIAL_CHANGE in {(upstream or {}).get('brainId')}", "NO_MATERIAL_CHANGE", inputFingerprint=in_fp, **extra)
        if ch == "UNKNOWN":
            return _rec(ctx, brain_id, trigger, "SKIP_UNKNOWN_CHANGE", f"whether {(upstream or {}).get('brainId')} changed is UNKNOWN (no fingerprint): not cascading", "CHANGE_UNKNOWN", inputFingerprint=in_fp, **extra)
        edge = next((d for d in b.get("dependencies", []) if d["id"] == (upstream or {}).get("brainId")), None)
        used, changed = (edge or {}).get("usesFields"), (upstream or {}).get("changedFields")
        if used and changed is not None and not (set(used) & set(changed)):
            return _rec(ctx, brain_id, trigger, "SKIP_UNCHANGED", "changed fields are not used by this consumer", "FIELDS_NOT_USED", inputFingerprint=in_fp, **extra)
    if trigger in ("INPUT_CHANGED", "DEPENDENCY_CHANGED") and (ctx.get("last_in_fps") or {}).get(brain_id) == in_fp:
        return _rec(ctx, brain_id, trigger, "SKIP_UNCHANGED", "input fingerprint equals the last one processed", "INPUT_FP_UNCHANGED", inputFingerprint=in_fp, **extra)
    if trigger == "SCHEDULE":
        dd = due(b, (ctx.get("states") or {}).get(brain_id), now)
        if dd is not True:
            return _rec(ctx, brain_id, trigger, "SKIP_NOT_DUE", "not due by the Brain's freshness expectation" if dd is False else "no time-based rule for this Brain", "NOT_DUE", **extra)

    rows, block = eval_dependencies(b, ctx)
    if block:
        return _rec(ctx, brain_id, trigger, block["decision"], block["reason"], "DEPENDENCY", dependencyState=rows, inputFingerprint=in_fp,
                    runDependencies=block.get("runDependencies"), **extra)
    why = {"SCHEDULE": "due by schedule and permitted by approved exception", "MANUAL": "manual run requested", "ADMIN": "admin run requested", "VALIDATION": "validation capture",
           "RECOVERY": "recovery run", "INPUT_CHANGED": "input fingerprint changed", "DEPENDENCY_CHANGED": "a dependency materially changed"}[trigger]
    return _rec(ctx, brain_id, trigger, "RUN", why, trigger, dependencyState=rows, inputFingerprint=in_fp, **extra)


def evaluate_world(ctx: dict, prev_out_fps: dict[str, str | None] | None = None) -> dict:
    """One observation pass: per-Brain SCHEDULE decision + material-change detection from published output fingerprints, then downstream decisions.
    -> {decisions[], changes{brainId: CHANGED|UNCHANGED|UNKNOWN}, runs[brainId]}. Parked Brains' existing state is read, never woken."""
    m = ctx["manifest"]
    decisions, changes = [], {}
    outs = ctx.get("out_fps") or {}
    for bid in sorted(m["brains"]):
        decisions.append(decide_brain(bid, "SCHEDULE", ctx))
        # no baseline at all -> UNKNOWN (first observation records the baseline; it must not cascade a wave of runs)
        changes[bid] = "UNKNOWN" if prev_out_fps is None else classify_change(prev_out_fps.get(bid), outs.get(bid))
    changed_fields = ctx.get("changed_fields") or {}
    for cid in sorted(m["brains"]):
        deps = m["brains"][cid].get("dependencies", [])
        if not deps:
            continue
        eff = {}
        for d in deps:
            ch = changes.get(d["id"], "UNKNOWN")
            cf = changed_fields.get(d["id"])
            if ch == "CHANGED" and d.get("usesFields") and cf is not None and not (set(d["usesFields"]) & set(cf)):
                ch = "UNCHANGED"                      # it changed, but not in anything this consumer reads
            eff[d["id"]] = ch
        agg = "CHANGED" if "CHANGED" in eff.values() else ("UNKNOWN" if "UNKNOWN" in eff.values() else "UNCHANGED")
        src = sorted(k for k, v in eff.items() if v == agg) or sorted(eff)
        decisions.append(decide_brain(cid, "DEPENDENCY_CHANGED", ctx, upstream={"brainId": ",".join(src), "change": agg}))
    runs = sorted({d["brainId"] for d in decisions if d["decision"] == "RUN"})
    return {"decisions": decisions, "changes": changes, "runs": runs}


def plan_waves(run_ids: list[str], m: dict) -> list[list[str]]:
    """Dependency-aware concurrency: Brains in the same wave have no edge between them (within the run set) and may run in parallel."""
    ids, waves, done = set(run_ids), [], set()
    deps = {b: {d["id"] for d in m["brains"][b].get("dependencies", []) if d["id"] in ids} for b in ids}
    while len(done) < len(ids):
        wave = sorted(b for b in ids - done if deps[b] <= done)
        if not wave:
            raise ManifestError("dependency cycle among runs: " + ", ".join(sorted(ids - done)))
        waves.append(wave)
        done |= set(wave)
    return waves


# ------------------------------------------------------------------------------------------------------------ concurrency, retry, cost
def acquire_lock(locks: dict, key: str, execution_id: str, now: dt.datetime, ttl_minutes: int = 30) -> tuple[bool, dict]:
    """Single-flight per `brain|scope`. A live lock held by another execution refuses; an expired one is replaced. Returns (acquired, new locks)."""
    cur = (locks or {}).get(key)
    if cur and parse_time(cur.get("lockedUntil")) and parse_time(cur["lockedUntil"]) > now and cur.get("executionId") != execution_id:
        return False, dict(locks)
    new = dict(locks or {})
    new[key] = {"executionId": execution_id, "lockedUntil": iso(now + dt.timedelta(minutes=ttl_minutes)), "sequence": int(((cur or {}).get("sequence") or 0)) + 1}
    return True, new


def may_commit(last_committed_started_at: str | None, started_at: str) -> bool:
    """A stale execution must not overwrite a newer one's committed result: an execution may commit only if it STARTED no earlier than the last committed one."""
    a, b = parse_time(last_committed_started_at), parse_time(started_at)
    return a is None or (b is not None and b >= a)


def classify_failure(error: str | None, exit_code: int | None = None) -> str:
    e = (error or "").lower()
    if any(k in e for k in ("timeout", "timed out", "429", "503", "502", "504", "connection", "temporar", "rate limit", "unavailable")):
        return "TRANSIENT_PROVIDER" if any(k in e for k in ("provider", "http", "429", "503", "502", "504", "rate limit", "connection")) else "TRANSIENT_RUNTIME"
    if any(k in e for k in ("memory", "oom", "killed", "evict", "deadline")):
        return "TRANSIENT_RUNTIME"
    if any(k in e for k in ("schema", "invalid", "malformed", "parse", "empty response", "illegalkey", "illegal key")):
        return "INVALID_INPUT"
    if any(k in e for k in ("dependency", "upstream", "blocked")):
        return "DEPENDENCY_BLOCKED"
    if any(k in e for k in ("permission", "403", "401", "not found", "no such", "missing env", "config", "denied")):
        return "PERMANENT_CONFIG"
    return "TRANSIENT_RUNTIME" if exit_code not in (None, 0) else "TRANSIENT_RUNTIME"


def retry_decision(failure_class: str, attempt: int, policy: dict, now: dt.datetime) -> dict:
    """Bounded retry by class. attempt = failures so far (1 after the first failure)."""
    if failure_class not in FAILURE_CLASSES:
        raise ValueError(failure_class)
    pol = policy or {"maxAttempts": 3, "backoffMinutes": [5, 15, 45]}
    if failure_class not in RETRYABLE:
        why = {"INVALID_INPUT": "bad input will not fix itself: needs attention", "PERMANENT_CONFIG": "configuration/permission problem: needs a human",
               "DEPENDENCY_BLOCKED": "re-evaluated when the dependency changes, not retried on a timer"}[failure_class]
        return {"retry": False, "failureClass": failure_class, "reason": why}
    if attempt >= pol["maxAttempts"]:
        return {"retry": False, "failureClass": failure_class, "reason": f"retries exhausted after {attempt} attempts: needs attention"}
    wait = pol["backoffMinutes"][min(max(attempt, 1), len(pol["backoffMinutes"])) - 1]
    return {"retry": True, "failureClass": failure_class, "attempt": attempt, "nextAttemptAt": iso(now + dt.timedelta(minutes=wait)), "reason": f"retry {attempt + 1} of {pol['maxAttempts']} in {wait} min"}


def consecutive_failures(brain_id: str, executions) -> list[dict]:
    """The Brain's failed executions since its last finished success/skip, newest first (unfinished STARTED runs are ignored)."""
    mine = sorted((e for e in executions or () if e.get("brainId") == brain_id and e.get("status") in ("SUCCEEDED", "SKIPPED", "FAILED")),
                  key=lambda e: e.get("endedAt") or e.get("startedAt") or "", reverse=True)
    out = []
    for e in mine:
        if e["status"] != "FAILED":
            break
        out.append(e)
    return out


def retry_gate(brain_id: str, trigger: str, ctx: dict) -> dict | None:
    """None = no gate. Applies the manifest retry policy (`retry` on the Brain, else `defaults.retry`) to the Brain's consecutive failures, for
    AUTOMATIC triggers only; MANUAL / ADMIN / VALIDATION / RECOVERY always proceed. It can only hold a run back, never start one.
    Without an execution ledger in ctx (`executions`) the gate is inactive."""
    if trigger not in AUTOMATIC_TRIGGERS or "executions" not in ctx:
        return None
    failed = consecutive_failures(brain_id, ctx["executions"])
    if not failed:
        return None
    last = failed[0]
    fc = last.get("failureClass") if last.get("failureClass") in FAILURE_CLASSES else "TRANSIENT_RUNTIME"
    if fc == "DEPENDENCY_BLOCKED" and trigger == "DEPENDENCY_CHANGED":
        return None                                                 # re-evaluated when the dependency changes: exactly this trigger
    m = ctx["manifest"]
    policy = ((m.get("brains") or {}).get(brain_id) or {}).get("retry") or (m.get("defaults") or {}).get("retry")
    failed_at = parse_time(last.get("endedAt") or last.get("startedAt")) or ctx["now"]
    rd = retry_decision(fc, len(failed), policy, failed_at)
    if not rd["retry"]:
        code = "RETRIES_EXHAUSTED" if fc in RETRYABLE else "NOT_RETRYABLE"
        return {"decision": "MANUAL_APPROVAL", "code": code, "retry": rd, "reason": f"last {len(failed)} run(s) failed ({fc}): {rd['reason']}"}
    if ctx["now"] < parse_time(rd["nextAttemptAt"]):
        return {"decision": "WAITING", "code": "RETRY_BACKOFF", "retry": rd, "reason": f"last run failed ({fc}): {rd['reason']} (not before {rd['nextAttemptAt']})"}
    return None


def estimate_cost(resources: dict | None, seconds: float | None, tasks: int | None = None) -> dict:
    """{usd|None, basis}. ESTIMATED from list prices when resources and runtime are known, otherwise UNKNOWN (never zero)."""
    if not resources or seconds is None:
        return {"usd": None, "basis": "UNKNOWN"}
    n = tasks or resources.get("tasks") or 1
    usd = n * float(seconds) * (float(resources.get("cpu", 1)) * VCPU_SECOND_USD + float(resources.get("memoryGiB", 0.5)) * GIB_SECOND_USD)
    return {"usd": round(usd, 4), "basis": "ESTIMATED"}


def cost_rollup(executions: list[dict], day: str) -> dict:
    """Cost for one UTC day from the bounded ledger. Unknown executions are counted and make the total a lower bound, never zero."""
    todays = [e for e in executions if (e.get("startedAt") or "").startswith(day)]
    known = [e for e in todays if (e.get("cost") or {}).get("usd") is not None]
    unknown = len(todays) - len(known)
    basis = "UNKNOWN" if not todays else ("ESTIMATED" if known else "UNKNOWN")
    return {"day": day, "executions": len(todays), "usd": round(sum(e["cost"]["usd"] for e in known), 4) if known else None,
            "basis": basis, "unknownExecutions": unknown, "lowerBound": bool(unknown and known)}


# ------------------------------------------------------------------------------------------------------------ ledgers
def append_bounded(items: list[dict], rec: dict, limit: int, key: str = "decisionId") -> list[dict]:
    """Newest first, de-duplicated by id, hard-capped. The control plane is not a logging warehouse."""
    out = [rec] + [x for x in (items or []) if x.get(key) != rec.get(key)]
    return out[:limit]


def execution_record(execution_id: str, brain_id: str, trigger: str, reason: str, started: dt.datetime, ended: dt.datetime | None, status: str,
                     scope: str | None = None, input_fp: str | None = None, output_changed: str = "UNKNOWN", resources: dict | None = None,
                     downstream: list[dict] | None = None, failure_class: str | None = None, source: str = "orchestrator",
                     code_version: str | None = None, consumed: list[dict] | None = None, job_id: str | None = None) -> dict:
    """Additive lineage (execution-health-v1): `code_version` = the code that produced the execution when KNOWN (image commit label,
    DEPLOYMENT_VERSION); `consumed` = the dependencies the execution ACTUALLY consumed, as recorded by the producer
    (execution_health.CONSUMED_KEYS). Both are absent when unknown: the orchestrator never invents lineage."""
    secs = (ended - started).total_seconds() if ended else None
    rec = {"executionId": execution_id, "brainId": brain_id, "trigger": trigger, "reason": reason, "startedAt": iso(started), "status": status, "source": source,
           "outputChanged": output_changed, "cost": estimate_cost(resources, secs)}
    if ended:
        rec.update({"endedAt": iso(ended), "durationSeconds": round(secs, 1)})
    if consumed is not None:
        from .execution_health import normalize_consumed
        consumed = normalize_consumed(consumed)                     # canonical: contract keys only, type from the id prefix, sorted by dependencyId
    for k, v in (("scope", scope), ("inputFingerprint", input_fp), ("downstream", [{"brainId": d["brainId"], "decision": d["decision"]} for d in downstream] if downstream else None),
                 ("failureClass", failure_class), ("codeVersion", code_version), ("consumed", consumed), ("jobId", job_id)):
        if v is not None:
            rec[k] = v
    return rec


_CRON = re.compile(r"^(\d{1,2}) (\*|\d{1,2}) \* \* \*$")


def infer_trigger(started: dt.datetime, cron: str | None, tz_offset_hours: int = 0, window_minutes: int = 15) -> str:
    """For executions the orchestrator did not start (legacy schedulers): SCHEDULE when the start falls within a few minutes after a cron fire time
    (simple `M H * * *` / `M * * * *` crons), otherwise UNKNOWN. Never guessed beyond that."""
    m = _CRON.match(cron or "")
    if not m:
        return "UNKNOWN"
    minute, hour = int(m.group(1)), m.group(2)
    s = started + dt.timedelta(hours=tz_offset_hours)
    if hour != "*" and s.hour != int(hour):
        return "UNKNOWN"
    delta = (s.minute - minute) % 60 if hour == "*" else s.minute - minute
    return "SCHEDULE" if 0 <= delta <= window_minutes else "UNKNOWN"


# ------------------------------------------------------------------------------------------------------------ control requests
def evaluate_request(req: dict, ctx: dict) -> dict:
    """Validate an Ops control request against Orchestrator policy. Ops gets NO arbitrary command execution: only the closed action set, scoped,
    with protected actions failing closed unless explicitly confirmed. Returns the request record to be stored; it never starts anything itself.
    req: {requestId, requestedBy, action, brainId, scope?, confirm?{by, phrase}}"""
    m, now = ctx["manifest"], ctx["now"]
    rid, who, action, bid = req.get("requestId"), req.get("requestedBy"), req.get("action"), req.get("brainId")
    base = {"requestId": rid, "requestedBy": who, "action": action, "brainId": bid, "scope": req.get("scope"), "at": iso(now)}

    def out(decision, reasons, **kw):
        assert decision in REQUEST_DECISIONS
        return {**base, "decision": decision, "reasons": reasons, **kw}
    if not rid or not who:
        return out("REJECTED", ["requestId and requestedBy are required"])
    b = m["brains"].get(bid) if bid else None
    if action in PROTECTED_ACTIONS:
        phrase = f"CONFIRM {action} {bid or 'ENGINE'}"
        conf = req.get("confirm") or {}
        if conf.get("by") != who or conf.get("phrase") != phrase:
            return out("NEEDS_CONFIRMATION", [f"protected action; resubmit with confirm.by = requester and confirm.phrase = {phrase!r}"], protected=True)
        if action in ("SET_ENGINE_MODE", "ACTIVATE_PRODUCTION", "PUBLISH_CUSTOMER", "PROMOTE_LIFECYCLE"):
            return out("REJECTED", [f"{action} is confirmed but is performed only through a reviewed change to the manifest and a deploy, never by a runtime request"], protected=True)
        # confirmed DISABLE_VALIDATION_CAPTURE / CHANGE_PROTECTED_SCHEDULE: allowed to be recorded for the operator, still executed by a human
        return out("ACCEPTED", ["confirmed protected action recorded; apply the documented gcloud/PREPRODUCTION_PAUSED_JOBS procedure"], protected=True)
    if action not in REQUEST_ACTIONS:
        return out("REJECTED", [f"unknown action {action!r}; allowed {REQUEST_ACTIONS + PROTECTED_ACTIONS}"])
    if b is None:
        return out("REJECTED", [f"unknown Brain {bid!r}"])
    is_validation = (b.get("schedule") or {}).get("class") == "VALIDATION_EXCEPTION"
    if action == "PAUSE" and is_validation:
        return out("NEEDS_CONFIRMATION" if (req.get("confirm") or {}).get("phrase") != f"CONFIRM DISABLE_VALIDATION_CAPTURE {bid}" else "ACCEPTED",
                   ["pausing a Brain with a validation exception disables evidence capture: protected action DISABLE_VALIDATION_CAPTURE"],
                   protected=True, resubmitAs="DISABLE_VALIDATION_CAPTURE")
    if action == "PAUSE":
        return out("ACCEPTED", [f"{bid} -> PARKED"], effect={"activityState": "PARKED"})
    if action == "RESUME":
        return out("ACCEPTED", [f"{bid} -> ACTIVE"], effect={"activityState": "ACTIVE"})
    if action == "SET_MANUAL":
        return out("ACCEPTED", [f"{bid} schedule intent -> MANUAL"], effect={"scheduleClass": "MANUAL"})
    # RUN_NOW: scoped; never "run everything"
    scope = req.get("scope")
    if not scope or scope in ("*", "all", "ALL", "fleet") and not b.get("allowFleetRunNow"):
        return out("REJECTED", [f"RUN_NOW needs an explicit scope; allowed for {bid}: {b.get('scopes') or 'none'}"])
    if b.get("scopes") and scope not in b["scopes"] and not (scope == "fleet" and b.get("allowFleetRunNow")):
        return out("REJECTED", [f"scope {scope!r} is not allowed for {bid}; allowed: {b['scopes']}"])
    d = decide_brain(bid, "MANUAL", ctx, scope=scope, requested_by=who)
    if d["decision"] != "RUN":
        return out("REJECTED", [f"policy: {d['decision']} - {d['reason']}"], decision_record=d)
    tgt = b.get("executionTarget") or {}
    if not tgt.get("scoped") and scope not in ("fleet", "pilots") and tgt.get("kind") != "none":
        return out("ACCEPTED", ["accepted; the executor cannot pass a scope to this target, so run it manually"], decision_record=d,
                   manualCommand=f"gcloud run jobs execute {tgt.get('job')} --region us-central1 --wait  # scope {scope}: {tgt.get('needsIam') or 'scope is baked into the job'}")
    return out("ACCEPTED", ["queued for the next orchestrator cycle (scoped manual run)"], decision_record=d)
