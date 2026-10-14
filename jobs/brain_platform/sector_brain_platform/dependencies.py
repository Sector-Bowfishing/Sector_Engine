"""Dependency metadata (docs/brains/platform/SECTOR_BRAIN_MODEL_V1.md section 6): small, declarative, no DAG engine.

A dependency entry: {id, requirement: REQUIRED|OPTIONAL, minClaimMaturity?, stateVersion?, freshness?, fallback}.
Freshness authority: the OWNING Brain's own freshness verdict is primary. A consumer may impose a stricter rule only through an explicit,
documented `stricterMaxAgeHours` + `stricterReason`; absent that, the consumer reports the owner's verdict verbatim.
"""
from __future__ import annotations

from .model_v1 import CLAIM_MATURITY, DEPENDENCY_FALLBACK, DEPENDENCY_REQUIREMENT, MATURITY_RANK, ModelError


def validate_dependency(dep: dict) -> dict:
    if not dep.get("id"):
        raise ModelError("dependency needs an id")
    if dep.get("requirement") not in DEPENDENCY_REQUIREMENT:
        raise ModelError(f"dependency {dep['id']}: requirement must be one of {DEPENDENCY_REQUIREMENT}")
    if dep.get("fallback") not in DEPENDENCY_FALLBACK:
        raise ModelError(f"dependency {dep['id']}: fallback must be one of {DEPENDENCY_FALLBACK}")
    m = dep.get("minClaimMaturity")
    if m is not None and m not in CLAIM_MATURITY:
        raise ModelError(f"dependency {dep['id']}: minClaimMaturity {m!r} not in the closed vocabulary")
    if dep.get("stricterMaxAgeHours") is not None and not dep.get("stricterReason"):
        raise ModelError(f"dependency {dep['id']}: a stricter freshness rule than the owner's needs a documented stricterReason")
    return dep


def evaluate(dep: dict, upstream: dict | None) -> dict:
    """upstream: {stateVersion?, claimMaturity?, freshness:{stale?, evidenceStale?, ageHours?}, health?}. -> {status, reasons[]}.
    status: SATISFIED | DEGRADED (optional dep unmet, or required dep unmet with a DEGRADE fallback) | UNSATISFIED."""
    validate_dependency(dep)
    reasons = []
    if not upstream:
        reasons.append("upstream state not published")
    else:
        fr = upstream.get("freshness") or {}
        if fr.get("stale") is True:
            reasons.append("owner reports state stale")             # the owner's verdict, reported verbatim
        if fr.get("evidenceStale") is True:
            reasons.append("owner reports evidence stale")
        cap = dep.get("stricterMaxAgeHours")
        if cap is not None and fr.get("ageHours") is not None and fr["ageHours"] > cap:
            reasons.append(f"consumer rule: age {fr['ageHours']} h > {cap} h ({dep['stricterReason']})")
        need = dep.get("minClaimMaturity")
        have = upstream.get("claimMaturity")
        if need and (have is None or MATURITY_RANK.get(have, 0) < MATURITY_RANK[need]):
            reasons.append(f"claim maturity {have or 'unknown'} below required {need}")
        if dep.get("stateVersion") and upstream.get("stateVersion") not in (None, dep["stateVersion"]) and not _compatible(dep, upstream):
            reasons.append(f"stateVersion {upstream.get('stateVersion')} != expected {dep['stateVersion']}")
    if not reasons:
        return {"id": dep["id"], "status": "SATISFIED", "reasons": []}
    if dep["requirement"] == "OPTIONAL" or dep["fallback"] in ("DEGRADE", "USE_LAST_GOOD"):
        return {"id": dep["id"], "status": "DEGRADED", "reasons": reasons, "fallback": dep["fallback"]}
    return {"id": dep["id"], "status": "UNSATISFIED", "reasons": reasons, "fallback": dep["fallback"]}


def _compatible(dep, upstream) -> bool:
    return upstream.get("stateVersion") in (dep.get("acceptStateVersions") or ())
