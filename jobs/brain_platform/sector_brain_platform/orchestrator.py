"""Brain Orchestrator — planning core (docs/brains/ORCHESTRATOR_DESIGN.md, consolidation Phase 11).

Pure: given what every Brain publishes about itself (registry `schedule`, `stalenessModel`,
`staleAfterHours`, `dependsOn`, `lastSuccessfulRun`, `health`) plus each Brain's own `plan()` verdict,
produce ONE ordered plan: which Brains run next, after which, why — with deduplication, single-flight
(running / lock), dependency order, retry with backoff, failure isolation and lake targeting.

No scheduler lives here and nothing executes. This is the LEGACY planner: jobs/brain-orchestrator/orchestrate.py calls
`plan()` and records its output at /control/orchestrator, but execution follows the decision model in `orchestration.py`; this
plan only drives execution with `--legacy-execution`. Page views never call this.
"""
from __future__ import annotations

import datetime as dt

from .timeutil import age_hours, iso, parse_time

MAX_RETRIES = 3
RETRY_BACKOFF_MIN = (5, 15, 45)          # minutes after the 1st, 2nd, 3rd failure
from .data_ownership import deployed_execution_order
from .keys import BRAINS
# Tie-break order for brains no dependsOn edge orders: the Cortex 3.1 target order (environmental specialists and Fish, then the Biological Brain, then Sector Intelligence; M08) projected
# onto the deployed packages. The combined biological-state package keeps its single slot after every environmental Brain.
DEFAULT_ORDER = tuple(deployed_execution_order(list(BRAINS)))


def _truthy(v) -> bool:
    return v is True or (isinstance(v, str) and v.strip().lower() in ("true", "yes", "1"))


def _topo(brains: dict[str, dict]) -> list[str]:
    """Dependency order: a brain runs after everything in its dependsOn. Stable for unrelated brains."""
    deps = {b: [d for d in ((brains[b].get("dependsOn") or [])) if d in brains] for b in brains}
    order, seen, visiting = [], set(), set()

    def visit(b):
        if b in seen:
            return
        if b in visiting:
            raise ValueError(f"dependency cycle at {b}")
        visiting.add(b)
        for d in sorted(deps[b], key=lambda x: (DEFAULT_ORDER.index(x) if x in DEFAULT_ORDER else 99, x)):
            visit(d)
        visiting.discard(b)
        seen.add(b)
        order.append(b)
    for b in sorted(brains, key=lambda x: (DEFAULT_ORDER.index(x) if x in DEFAULT_ORDER else 99, x)):
        visit(b)
    return order


def decide(brain_id: str, reg: dict, health: dict | None, brain_plan: dict | None, now: dt.datetime,
           upstream_failed: set[str]) -> dict:
    """One brain: RUN / SKIP / WAIT with reasons. Never invents a need: a VERSION/FINGERPRINT brain runs only
    when its own plan() says PUBLISH; a TIME brain when its published state is past staleAfterHours."""
    sched = reg.get("schedule") or {}
    model = reg.get("stalenessModel") or ("TIME" if reg.get("staleAfterHours") is not None else "VERSION")
    hstat = (health or {}).get("status") or reg.get("health")
    reasons, action = [], "SKIP"

    # single-flight: a running or locked brain is never started twice ("false"/"no" strings are not running:
    # the Lake Brain registry publishes schedule.running as a string)
    if _truthy(sched.get("running")):
        return {"brainId": brain_id, "action": "WAIT", "reasons": ["already running (single-flight)"]}
    lock = parse_time(sched.get("lockedUntil"))
    if lock and lock > now:
        return {"brainId": brain_id, "action": "WAIT", "reasons": [f"locked until {sched.get('lockedUntil')}"]}

    # retry with backoff after a failure; give up after MAX_RETRIES (needs a human)
    errors = int((health or {}).get("errorCount") or 0)
    if hstat == "FAILED":
        if errors > MAX_RETRIES:
            return {"brainId": brain_id, "action": "SKIP", "reasons": [f"FAILED {errors} times: retries exhausted, needs attention"]}
        last_run = parse_time((health or {}).get("lastRun"))
        wait_min = RETRY_BACKOFF_MIN[min(max(errors, 1), len(RETRY_BACKOFF_MIN)) - 1]
        if last_run and now < last_run + dt.timedelta(minutes=wait_min):
            return {"brainId": brain_id, "action": "WAIT", "reasons": [f"retry backoff: {wait_min} min after failure #{errors}"],
                    "nextAttemptAt": iso(last_run + dt.timedelta(minutes=wait_min))}
        reasons.append(f"retry after failure #{errors}")
        action = "RUN"

    # the brain's own verdict (version / fingerprint brains only know this themselves)
    if brain_plan and brain_plan.get("action") == "PUBLISH":
        reasons.extend(f"brain plan: {r}" for r in (brain_plan.get("reasons") or ["publish warranted"]))
        action = "RUN"

    # time staleness
    if model == "TIME":
        sa = reg.get("staleAfterHours")
        age = age_hours(reg.get("lastSuccessfulRun") or (health or {}).get("lastSuccess"), now)
        if age is None:
            reasons.append("never run"); action = "RUN"
        elif sa is not None and age >= float(sa):
            reasons.append(f"published state {age} h old >= staleAfterHours {sa}"); action = "RUN"
        nxt = parse_time(sched.get("nextCheckAt"))
        if nxt and now >= nxt:
            reasons.append(f"nextCheckAt {sched.get('nextCheckAt')} reached"); action = "RUN"

    # failure isolation: a failed upstream never blocks; the run is flagged so it publishes degraded inputs honestly
    degraded = sorted(d for d in (reg.get("dependsOn") or []) if d in upstream_failed)
    if action == "RUN" and degraded:
        reasons.append(f"upstream FAILED, running with degraded inputs: {', '.join(degraded)}")
    if action == "SKIP":
        reasons.append("published state is current" if model == "TIME" else "brain plan: nothing to do")
    out = {"brainId": brain_id, "action": action, "reasons": reasons}
    if degraded:
        out["degradedUpstream"] = degraded
    return out


def plan(brains: dict[str, dict], health: dict[str, dict] | None, now: dt.datetime, brain_plans: dict[str, dict] | None = None,
         targets: list[str] | None = None) -> dict:
    """The orchestrator's plan. `brains`: {brainId: registry}. `health`: {brainId: /health/brains/{id}}.
    `brain_plans`: {brainId: the brain's own plan() output}. `targets`: lake ids to refresh (passed through)."""
    health = health or {}
    brain_plans = brain_plans or {}
    order = _topo(brains)
    failed = {b for b in brains if ((health.get(b) or {}).get("status") or brains[b].get("health")) == "FAILED"}
    runs, waits, skips, seen = [], [], [], set()
    for b in order:
        if b in seen:                                         # dedupe (a brain appears once however many edges reach it)
            continue
        seen.add(b)
        d = decide(b, brains[b], health.get(b), brain_plans.get(b), now, failed)
        after = [x for x in (brains[b].get("dependsOn") or []) if any(r["brainId"] == x for r in runs)]
        if d["action"] == "RUN":
            r = {**d, "after": after, "priority": len(runs) + 1}
            if targets:
                r["lakes"] = list(targets)
            runs.append(r)
        elif d["action"] == "WAIT":
            waits.append(d)
        else:
            skips.append(d)
    return {"generatedAt": iso(now), "order": order, "runs": runs, "waiting": waits, "skipped": skips,
            "targets": list(targets) if targets else None}


def descriptor_gaps(brains: dict[str, dict]) -> dict[str, list[str]]:
    """What each registry still lacks for orchestration (contract §9/§11)."""
    out = {}
    for b, r in brains.items():
        missing = [k for k in ("schedule", "stalenessModel", "dependsOn", "lastSuccessfulRun") if k not in r]
        if r.get("stalenessModel", "TIME") == "TIME" and "staleAfterHours" not in r:
            missing.append("staleAfterHours")
        if not (r.get("descriptor") or r.get("orchestration")):
            missing.append("descriptor")
        if missing:
            out[b] = missing
    return out
