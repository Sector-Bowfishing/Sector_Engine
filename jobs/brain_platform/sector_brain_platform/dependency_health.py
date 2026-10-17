"""G2 — generic DEPENDENCY health and FRESHNESS health (dependency-health-v1).

Three questions, kept apart: was the dependency AVAILABLE; was its evidence FRESH (at the time it was consumed); is the consumer's
requirement therefore SATISFIED. None of them is process health (execution_health.py) and none is derived from `lastSuccessfulRun`:
a record that offers only lastSuccessfulRun yields freshness UNKNOWN, by design and by test.

Timestamp semantics are the existing lineage vocabulary (BRAIN_IDENTITY_AND_LINEAGE_V1 §4, Publisher freshness): evidenceObservedAt,
generatedAt (== inputGeneratedAt for a consumer), publishedAt, staleAfter / expiresAt (owner-declared), freshnessStatus
(FRESH STALE EXPIRED UNAVAILABLE UNKNOWN). The OWNER's verdict is primary (FRESHNESS_MODEL.md); a consumer may only be stricter,
through its declared freshnessPolicy {maxAgeHours, reason}. Generic: no Brain id, no signal id, no science.
"""
from __future__ import annotations

import datetime as dt

from .enums import FRESHNESS_STATUS
from .timeutil import iso, parse_time

DEPENDENCY_HEALTH_VERSION = "dependency-health-v1"
# FRESHNESS_STATUS: enums.FRESHNESS_STATUS == publisher.model.FRESHNESS_STATUSES (one vocabulary; the platform package never imports the Publisher)
AVAILABILITY = ("AVAILABLE", "MISSING", "UNKNOWN")
DEPENDENCY_STATUS = ("SATISFIED", "DEGRADED", "UNSATISFIED", "UNKNOWN")   # model v1 dependencies.evaluate() words + UNKNOWN
FRESHNESS_AUTHORITY = ("OWNER_VERDICT", "OWNER_RULE", "CONSUMER_RULE", "PLATFORM_REGISTRY", "UNKNOWN")
AGE_BASIS = ("EVIDENCE_OBSERVED", "GENERATED", "PUBLISHED")
EVALUATION_BASIS = ("RECORDED_CONSUMPTION", "CURRENT_STATE")
_FRESH_RANK = {"FRESH": 0, "UNKNOWN": 1, "UNAVAILABLE": 2, "STALE": 3, "EXPIRED": 4}      # worst wins when aggregating
_DEP_RANK = {"SATISFIED": 0, "UNKNOWN": 1, "DEGRADED": 2, "UNSATISFIED": 3}


def _t(v):
    return parse_time(v) if isinstance(v, str) else v


def _freshness(observed: dict, at: dt.datetime, reasons: list[str]) -> tuple[str, str, dict]:
    """(freshnessStatus, authority, facts) from what the OWNER published. Never from lastSuccessfulRun."""
    facts: dict = {}
    for k in ("evidenceObservedAt", "generatedAt", "publishedAt", "staleAfter", "expiresAt"):
        if observed.get(k):
            facts[k] = observed[k]
    if observed.get("staleAfterHours") is not None:
        facts["staleAfterHours"] = float(observed["staleAfterHours"])
    ref_key = next((k for k in ("evidenceObservedAt", "generatedAt", "publishedAt") if facts.get(k)), None)
    ref = _t(facts[ref_key]) if ref_key else None
    if ref is not None:
        facts["ageHoursAtConsumption"] = round((at - ref).total_seconds() / 3600, 2)
        facts["ageBasis"] = {"evidenceObservedAt": "EVIDENCE_OBSERVED", "generatedAt": "GENERATED", "publishedAt": "PUBLISHED"}[ref_key]
    v = observed.get("freshnessStatus")
    if v is not None:
        if v in FRESHNESS_STATUS:
            reasons.append(f"owner reports {v}")
            return v, "OWNER_VERDICT", facts
        reasons.append(f"owner freshnessStatus {v!r} is not in the vocabulary: treated as UNKNOWN")
        return "UNKNOWN", "UNKNOWN", facts
    if observed.get("stale") is not None or observed.get("evidenceStale") is not None:
        stale = observed.get("stale") is True or observed.get("evidenceStale") is True
        reasons.append("owner reports " + ("stale" if stale else "fresh") + " (state envelope)")
        return ("STALE" if stale else "FRESH"), "OWNER_VERDICT", facts
    exp = _t(facts.get("expiresAt"))
    if exp is not None and at > exp:
        reasons.append(f"owner expiresAt {facts['expiresAt']} passed")
        return "EXPIRED", "OWNER_RULE", facts
    sa = _t(facts.get("staleAfter"))
    if sa is not None:
        reasons.append(f"owner staleAfter {facts['staleAfter']} " + ("passed" if at > sa else "not reached"))
        return ("STALE" if at > sa else "FRESH"), "OWNER_RULE", facts
    if facts.get("staleAfterHours") is not None and ref is not None:
        stale = facts["ageHoursAtConsumption"] > facts["staleAfterHours"]
        reasons.append(f"owner rule staleAfterHours {facts['staleAfterHours']}: age {facts['ageHoursAtConsumption']} h")
        return ("STALE" if stale else "FRESH"), "OWNER_RULE", facts
    if observed.get("lastSuccessfulRun") and ref is None:
        reasons.append("only lastSuccessfulRun is published: process history, not evidence freshness")
    reasons.append("owner publishes no freshness verdict or rule")
    return "UNKNOWN", "UNKNOWN", facts


def evaluate_dependency(declared: dict, observed: dict | None, now: dt.datetime, consumed: dict | None = None) -> dict:
    """One dependency row. `declared`: a dependency_declarations row. `observed`: what the Engine can read about the dependency NOW
    (None = not published / missing; {"available": None} = could not be determined). `consumed`: the execution's recorded consumption
    entry for this dependency, if any (then the evaluation is at consumedAt against the consumed state: RECORDED_CONSUMPTION)."""
    reasons: list[str] = []
    row = {"dependencyId": declared["dependencyId"], "dependencyType": declared["dependencyType"], "declaringBrain": declared["declaringBrain"]}
    req = declared.get("requirement")
    if req is None:
        req = "REQUIRED"; reasons.append("requirement not declared: treated as REQUIRED (fail closed)")
    row["requirement"] = req
    if declared.get("legacy"):
        row["legacy"] = True
    # --- which state is being judged
    if consumed:
        basis, at = "RECORDED_CONSUMPTION", _t(consumed.get("consumedAt")) or now
        obs = dict(consumed)
        obs["available"] = True
        row["consumedAt"] = iso(at)
        for k in ("ref", "stateVersion", "fingerprint", "artifactId"):
            if consumed.get(k) is not None:
                row.setdefault("lineageRef", {})[k] = consumed[k]
    else:
        basis, at, obs = "CURRENT_STATE", now, observed
    row["evaluationBasis"] = basis
    row["evaluatedAt"] = iso(at)
    # --- availability
    if obs is None:
        avail = "MISSING"; reasons.append("dependency state not published / not found")
    elif obs.get("available") is False:
        avail = "MISSING"; reasons.append(obs.get("reason") or "dependency reports unavailable")
    elif obs.get("available") is None and not any(obs.get(k) for k in ("freshnessStatus", "stale", "evidenceStale", "generatedAt", "evidenceObservedAt", "publishedAt", "staleAfter", "expiresAt")):
        avail = "UNKNOWN"; reasons.append(obs.get("reason") or "availability could not be determined")
    else:
        avail = "AVAILABLE"
        if obs.get("reason"):
            reasons.append(obs["reason"])
        for k in ("ref", "stateVersion", "fingerprint", "artifactId"):
            if obs.get(k) is not None:
                row.setdefault("lineageRef", {})[k] = obs[k]
    row["availability"] = avail
    # --- freshness (owner-authoritative; consumer only stricter)
    if avail == "AVAILABLE":
        fs, authority, facts = _freshness(obs, at, reasons)
        row.update(facts)
        pol = declared.get("freshnessPolicy")
        if pol:
            row["consumerMaxAgeHours"] = pol["maxAgeHours"]
            age = facts.get("ageHoursAtConsumption")
            if age is None:
                reasons.append(f"consumer rule maxAgeHours {pol['maxAgeHours']} cannot be applied: no evidence age")
            elif age > pol["maxAgeHours"] and fs in ("FRESH", "UNKNOWN"):
                row["ownerFreshnessStatus"] = fs
                fs, authority = "STALE", "CONSUMER_RULE"
                reasons.append(f"consumer rule: age {age} h > {pol['maxAgeHours']} h ({pol['reason']})")
    elif avail == "MISSING":
        fs, authority = "UNAVAILABLE", "UNKNOWN"
    else:
        fs, authority = "UNKNOWN", "UNKNOWN"
    row["freshnessStatus"], row["freshnessAuthority"] = fs, authority
    # --- the requirement verdict
    if avail == "UNKNOWN":
        status = "UNKNOWN"
    elif avail == "MISSING":
        status = "UNSATISFIED" if req == "REQUIRED" else "DEGRADED"
    elif fs == "FRESH":
        status = "SATISFIED"
    elif fs == "UNKNOWN":
        status = "UNKNOWN"; reasons.append("freshness unknown: not assumed fresh")
    elif fs == "EXPIRED":
        status = "UNSATISFIED" if req == "REQUIRED" else "DEGRADED"
    else:                                                       # STALE or UNAVAILABLE evidence on an available dependency
        status = "DEGRADED"
    row["dependencyStatus"] = status
    row["reasons"] = reasons
    return row


def aggregate(rows: list[dict], declarations_known: bool = True) -> dict:
    """{dependencyHealth, freshnessHealth, reasons} for one consumer. dependencyHealth = worst requirement verdict; freshnessHealth = worst
    freshness of the REQUIRED dependencies (BRAIN_IDENTITY_AND_LINEAGE_V1 §4 rule 3: a derived artifact is no fresher than its worst
    required input). An UNKNOWN never counts as FRESH/SATISFIED. Unknown declarations -> UNKNOWN, not 'no dependencies'."""
    out: dict = {"version": DEPENDENCY_HEALTH_VERSION, "declared": len(rows), "reasons": []}
    if not declarations_known:
        out.update(dependencyHealth="UNKNOWN", freshnessHealth="UNKNOWN")
        out["reasons"].append("dependency declarations unknown for this Brain")
        return out
    if not rows:
        out.update(dependencyHealth="SATISFIED", freshnessHealth="UNKNOWN", freshnessBasis="no declared dependency carries evidence")
        out["reasons"].append("no declared dependencies: nothing to require; evidence freshness is not assessable from declarations")
        return out
    out["dependencyHealth"] = max((r["dependencyStatus"] for r in rows), key=lambda s: _DEP_RANK[s])
    required = [r for r in rows if r["requirement"] == "REQUIRED"]
    if required:
        out["freshnessHealth"] = max((r["freshnessStatus"] for r in required), key=lambda s: _FRESH_RANK[s])
        out["freshnessBasis"] = "worst REQUIRED dependency"
    else:
        out["freshnessHealth"] = "UNKNOWN"
        out["freshnessBasis"] = "no REQUIRED dependency declared (optional dependencies do not bound freshness): not assessable"
    for r in rows:
        if r["dependencyStatus"] != "SATISFIED":
            out["reasons"].append(f"{r['dependencyId']}: {r['dependencyStatus']} / {r['freshnessStatus']}")
    out["counts"] = {"byStatus": _count(rows, "dependencyStatus"), "byFreshness": _count(rows, "freshnessStatus"), "byType": _count(rows, "dependencyType")}
    return out


def _count(rows, key):
    c: dict[str, int] = {}
    for r in rows:
        c[r[key]] = c.get(r[key], 0) + 1
    return dict(sorted(c.items()))


def reconcile_consumption(declared_rows: list[dict], execution: dict | None) -> dict:
    """Declared vs ACTUAL. {consumptionRecorded, declaredAndConsumed[], declaredNotConsumed[], consumedNotDeclared[]} for a normalised
    execution. No `consumed` on the execution -> consumptionRecorded False and nothing is inferred."""
    declared_ids = [r["dependencyId"] for r in declared_rows]
    if not execution or not execution.get("consumptionRecorded"):
        return {"consumptionRecorded": False, "declaredAndConsumed": [], "declaredNotConsumed": [], "consumedNotDeclared": [],
                "note": "the producer recorded no consumed-dependency lineage for this execution"}
    consumed_ids = [c["dependencyId"] for c in execution.get("consumed") or []]
    return {"consumptionRecorded": True,
            "declaredAndConsumed": sorted(set(declared_ids) & set(consumed_ids)),
            "declaredNotConsumed": sorted(set(declared_ids) - set(consumed_ids)),
            "consumedNotDeclared": sorted(set(consumed_ids) - set(declared_ids))}


def evaluate_all(declared_rows: list[dict], observations: dict[str, dict | None], now: dt.datetime, execution: dict | None = None) -> list[dict]:
    """Every declared row, judged at the execution's recorded consumption when it exists, otherwise against the current observation.
    `observations`: {dependencyId: observed | None}. A dependency with no key at all is UNKNOWN (not observed), not MISSING."""
    by_consumed = {c["dependencyId"]: c for c in (execution or {}).get("consumed") or []} if execution and execution.get("consumptionRecorded") else {}
    out = []
    for d in sorted(declared_rows, key=lambda r: r["dependencyId"]):
        did = d["dependencyId"]
        if did in by_consumed:
            out.append(evaluate_dependency(d, None, now, consumed=by_consumed[did]))
        elif did in observations:
            out.append(evaluate_dependency(d, observations[did], now))
        else:
            out.append(evaluate_dependency(d, {"available": None, "reason": "not observed by the Engine"}, now))
    return out
