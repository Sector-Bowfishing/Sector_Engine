"""What the Sector Intelligence Brain depends on and when it should run. No scheduler lives here.

The future Sector Brain Orchestrator owns scheduling, dependency ordering, retries, deduplication and failure
isolation. This module only answers the brain-side questions: what are my inputs, what makes my published state
stale, and is a run warranted now?
"""
from __future__ import annotations

DESCRIPTOR = {
    "brainId": "sector-intelligence",
    "schedule": "none: run on demand, or when the future Sector Brain Orchestrator sees an upstream change",
    "components": {
        "registryAndDependencies": {
            "status": "ACTIVE",
            "inputs": ["/brains/{lake-brain,water-temp,water-clarity,wind,biological-state}",
                       "/health/brains/{same}", "/validation/{same}/status",
                       "Cloud Run service sector-engine (serving revision + image digest)", "catalog.json"],
            "staleness": "fingerprint-based: stale when an upstream brain's registration, publishing status, health, "
                         "version or lifecycle changes, when the serving Engine revision or image changes, or when the "
                         "catalog or this brain's version changes",
            "recomputeWhen": ["an upstream brain registers, publishes, goes stale or changes health/version",
                              "a new Engine revision serves traffic", "catalog.json changes", "brain code version changes"],
        },
        "lakeInputAvailability": {
            "status": "ACTIVE",
            "inputs": ["GET /lakes (Engine directory)", "/lakeFleet/{k} slots written by each brain"],
            "staleness": "reflects the run time (generatedAt); refreshed with the registry",
            "recomputeWhen": ["same as registryAndDependencies", "an upstream brain publishes a new fleet run"],
        },
        "normalizedEvaluation": {
            "status": "NOT_STARTED",
            "plannedInputs": ["/snapshots/{k}/latest (normalized Brain states)", "/lakes/{k}/states/lake",
                              "/species/{speciesId}", "/lakes/{k}/speciesPresence", "policy context"],
            "plannedRecomputeWhen": ["an upstream state used by the evaluation changes materially or goes stale",
                                     "the evaluation window rolls over"],
            "note": "Not built. Must never be recomputed per user page-load.",
        },
    },
}


def plan(published: dict | None, fingerprint: str, brain_version: str, max_age_hours: float = 24.0,
         published_age_hours: float | None = None) -> dict:
    """Decide whether a publish is warranted. Pure: no I/O."""
    reasons = []
    if not published:
        reasons.append("nothing published yet")
    else:
        if published.get("version") != brain_version:
            reasons.append(f"brain version {published.get('version')} -> {brain_version}")
        if published.get("fingerprint") != fingerprint:
            reasons.append("upstream brains, serving revision or catalog changed")
        if (published.get("health") or "HEALTHY") != "HEALTHY":
            reasons.append(f"last publish health {published.get('health')}")
        if published_age_hours is not None and published_age_hours > max_age_hours:
            reasons.append(f"last publish {published_age_hours} h ago > {max_age_hours} h (per-lake freshness)")
    return {"component": "registryAndDependencies", "action": "PUBLISH" if reasons else "SKIP",
            "reasons": reasons or ["published state matches upstream; nothing to do"]}
