"""What the Biological Brain depends on and when it should run. No scheduler lives here.

The future Sector Brain Orchestrator owns scheduling, execution, retries, dependency ordering, deduplication and
failure isolation. This module only answers the brain-side questions the orchestrator will ask:
  * what are my inputs/dependencies?
  * what makes my published state stale?
  * given what is published now and what is upstream, is a run warranted (and why)?

Species knowledge is version-driven, not time-driven: it never goes stale by age.
"""
from __future__ import annotations

DESCRIPTOR = {
    "brainId": "biological-state",
    "schedule": "none: run on demand, or when the future Sector Brain Orchestrator decides a dependency changed",
    "components": {
        "speciesKnowledge": {
            "status": "ACTIVE",
            "inputs": ["private canonical bundle pointer gs://sector-biology-private/biology/v1/latest.json"],
            "staleness": "version-based: stale only when the published researchVersion/manifest/brain version differs from upstream; never by age",
            "recomputeWhen": ["latest.json researchVersion changed", "latest.json manifestSha256 changed", "brain code version changed"],
        },
        "biologicalState": {
            "status": "NOT_STARTED",
            "plannedInputs": ["water-temp state", "water-clarity state", "wind state", "canonical lake directory / lake-brain", "calendar / season",
                              "species knowledge researchVersion"],
            "plannedRecomputeWhen": ["an upstream condition state changes materially (thresholds defined with the state model)",
                                     "an upstream state becomes stale or degraded", "the date crosses a species phase boundary",
                                     "species knowledge researchVersion changes"],
            "note": "Not built; requires separate approval. Must never be recomputed per user page-load.",
        },
    },
}


def plan(published: dict | None, pointer: dict, brain_version: str) -> dict:
    """Decide whether the species-knowledge publish is warranted. Pure: no I/O."""
    reasons = []
    if not published:
        reasons.append("nothing published yet")
    else:
        if published.get("researchVersion") != pointer.get("researchVersion"):
            reasons.append(f"researchVersion {published.get('researchVersion')} -> {pointer.get('researchVersion')}")
        if published.get("manifestSha256") != pointer.get("manifestSha256"):
            reasons.append("manifest changed")
        if published.get("version") != brain_version:
            reasons.append(f"brain version {published.get('version')} -> {brain_version}")
        if (published.get("health") or "HEALTHY") != "HEALTHY":
            reasons.append(f"last publish health {published.get('health')}")
    return {"component": "speciesKnowledge", "action": "PUBLISH" if reasons else "SKIP",
            "reasons": reasons or ["published state matches upstream; nothing to do"]}
