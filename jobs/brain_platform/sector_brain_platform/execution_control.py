"""Global + per-Brain execution control (Rehtac Cortex 2.7.0 PL-15..PL-18, BR-21; owner directive 2026-10-23).

ONE authoritative switch for automatic Brain execution, at /control/executionControlV1 (registry family fam.control-execution-control):

    {"schema": "brain-execution-control-v1", "state": "PAUSED" | "ENABLED",
     "brains": {"<brainId>": {"enabled": bool, "limits": {maxRunsPerDay, maxRetries, maxConcurrency, maxCostPerDay}}},
     "limits": {"maxStartsPerCycle": int}, "approvalRef": str|null, "changedBy": str, "changedAt": ISO, "reason": str}

Written ONLY by the owner CLI (tools/ops/execution_control.py). Never by the orchestrator, a Brain, a deploy script or Sector Ops.
FAIL CLOSED: absent, unreadable, wrong schema or invalid => PAUSED. ENABLED needs an approvalRef. A Brain absent from `brains` is
disabled. Stdlib only, no clock (callers pass `now`)."""
from __future__ import annotations

NODE = "control/executionControlV1"
SCHEMA = "brain-execution-control-v1"
STATES = ("PAUSED", "ENABLED")
AUTHORITY = "brain-orchestrator"
DEFAULT_LIMITS = {"maxRunsPerDay": 24, "maxRetries": 2, "maxConcurrency": 1, "maxCostPerDay": 1.0}
DEFAULT_MAX_STARTS_PER_CYCLE = 2          # no catch-up burst: after a long pause at most this many workers start per orchestrator cycle
AUTOMATIC_TRIGGERS = ("SCHEDULE", "INPUT_CHANGED", "DEPENDENCY_CHANGED", "RECOVERY", "VALIDATION")


def _num(x, lo=0):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x >= lo


def parse(raw) -> dict:
    """-> effective control: {state, valid, reason, brains{id: {enabled, limits}}, maxStartsPerCycle, approvalRef, changedBy, changedAt}.
    Anything not provably ENABLED is PAUSED (fail closed)."""
    base = {"state": "PAUSED", "valid": False, "brains": {}, "maxStartsPerCycle": DEFAULT_MAX_STARTS_PER_CYCLE,
            "approvalRef": None, "changedBy": None, "changedAt": None}
    if raw is None:
        return {**base, "reason": "execution control not found: fail closed (PAUSED)"}
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        return {**base, "reason": "execution control unreadable or wrong schema: fail closed (PAUSED)"}
    st = raw.get("state")
    if st not in STATES:
        return {**base, "reason": f"execution control state {st!r} invalid: fail closed (PAUSED)"}
    if st == "ENABLED" and not (isinstance(raw.get("approvalRef"), str) and raw["approvalRef"].strip()):
        return {**base, "reason": "ENABLED without an owner approvalRef: fail closed (PAUSED)"}
    brains = {}
    for bid, b in (raw.get("brains") or {}).items():
        if not isinstance(b, dict):
            continue
        lim = dict(DEFAULT_LIMITS)
        for k, v in (b.get("limits") or {}).items():
            if k in DEFAULT_LIMITS and _num(v):
                lim[k] = v
        brains[bid] = {"enabled": b.get("enabled") is True, "limits": lim}
    mspc = (raw.get("limits") or {}).get("maxStartsPerCycle")
    return {"state": st, "valid": True, "reason": f"execution control {st}", "brains": brains,
            "maxStartsPerCycle": int(mspc) if _num(mspc, 0) else DEFAULT_MAX_STARTS_PER_CYCLE,
            "approvalRef": raw.get("approvalRef"), "changedBy": raw.get("changedBy"), "changedAt": raw.get("changedAt")}


def brain_enabled(ctl: dict, brain_id: str) -> bool:
    return (ctl.get("brains") or {}).get(brain_id, {}).get("enabled") is True


def limits(ctl: dict, brain_id: str) -> dict:
    return (ctl.get("brains") or {}).get(brain_id, {}).get("limits") or dict(DEFAULT_LIMITS)


def automatic_allowed(ctl: dict) -> tuple[bool, str]:
    """May this cycle do ANY automatic work (worker starts, plan checks that call providers, shadow lane)?"""
    if ctl.get("state") != "ENABLED":
        return False, ctl.get("reason") or "execution control PAUSED"
    return True, "execution control ENABLED"


def gate(ctl: dict, brain_id: str, trigger: str, *, admin: dict | None, starts_this_cycle: int, runs_today: int,
         cost_today: float | None = None) -> tuple[bool, str]:
    """May the orchestrator start this Brain's worker now? Evaluated AFTER the decision model said RUN.
    admin = {"requestedBy", "reason"} for an explicit, authorized ADMIN run-now (allowed while PAUSED, recorded, never re-enables anything)."""
    lim = limits(ctl, brain_id)
    if admin:
        if not (admin.get("requestedBy") and admin.get("reason")):
            return False, "admin run refused: requestedBy and reason are both required"
    else:
        if trigger not in AUTOMATIC_TRIGGERS and trigger not in ("MANUAL", "ADMIN"):
            return False, f"unknown trigger {trigger}"
        if ctl.get("state") != "ENABLED":
            return False, f"global execution control is {ctl.get('state')}: {ctl.get('reason')}"
        if not brain_enabled(ctl, brain_id):
            return False, f"{brain_id} is not enabled in the execution control"
        if trigger in ("MANUAL", "ADMIN"):
            return False, "manual/admin runs need an explicit --admin-reason (separately authorized)"
    if starts_this_cycle >= ctl.get("maxStartsPerCycle", DEFAULT_MAX_STARTS_PER_CYCLE):
        return False, f"maxStartsPerCycle {ctl.get('maxStartsPerCycle')} reached (no catch-up burst); evaluated again next cycle"
    if runs_today >= lim["maxRunsPerDay"]:
        return False, f"maxRunsPerDay {lim['maxRunsPerDay']} reached for {brain_id}"
    if cost_today is not None and cost_today >= lim["maxCostPerDay"]:
        return False, f"maxCostPerDay {lim['maxCostPerDay']} USD reached for {brain_id} (estimate {cost_today:.2f})"
    return True, "admin run (recorded)" if admin else "permitted by the execution control"


def document(state: str, *, brains: dict, changed_by: str, changed_at: str, approval_ref: str | None, reason: str,
             max_starts_per_cycle: int = DEFAULT_MAX_STARTS_PER_CYCLE) -> dict:
    """The owner CLI's document. Refuses ENABLED without approvalRef (the same rule parse() enforces)."""
    if state not in STATES:
        raise ValueError(f"state must be one of {STATES}")
    if state == "ENABLED" and not (approval_ref and approval_ref.strip()):
        raise ValueError("ENABLED requires an owner approvalRef")
    return {"schema": SCHEMA, "schemaVersion": "1.0.0", "authority": AUTHORITY, "state": state, "brains": brains,
            "limits": {"maxStartsPerCycle": max_starts_per_cycle}, "approvalRef": approval_ref, "changedBy": changed_by,
            "changedAt": changed_at, "reason": reason,
            "note": "Written only by the owner CLI (tools/ops/execution_control.py). Absent/invalid = PAUSED. A deployment never changes it."}


def summary(ctl: dict) -> dict:
    """Compact, leak-free view for status documents (engineering-status-ops-v1 executionControl; Cortex status executionControl)."""
    out = {"state": ctl.get("state", "PAUSED"), "valid": bool(ctl.get("valid")), "reason": (ctl.get("reason") or "")[:200],
           "brains": {b: {"enabled": v.get("enabled") is True} for b, v in (ctl.get("brains") or {}).items()},
           "maxStartsPerCycle": ctl.get("maxStartsPerCycle", DEFAULT_MAX_STARTS_PER_CYCLE)}
    for k in ("approvalRef", "changedAt"):
        if ctl.get(k):
            out[k] = str(ctl[k])[:120]
    return out
