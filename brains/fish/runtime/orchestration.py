"""What the Biological Brain depends on and when it should run. No scheduler lives here.

The future Sector Brain Orchestrator owns scheduling, execution, retries, dependency ordering, deduplication and
failure isolation. This module only answers the brain-side questions the orchestrator will ask:
  * what are my inputs/dependencies?
  * what makes my published state stale?
  * given what is published now and what is upstream, is a run warranted (and why)?

Species knowledge is version-driven, not time-driven: it never goes stale by age.
The per-lake state is fingerprint-driven (`bio_state.state_fingerprint`): no change in material inputs means no work.
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
            "status": "IN_PROGRESS",
            "scope": "internal pilot (Guntersville; Hartwell dry runs); nothing is written per lake and no customer path reads it",
            "inputs": ["lake-brain state (trendState, species presence)", "water-temp state (currentTempF, trend24hF)", "water-clarity state (clarityFt)",
                       "calendar (month, daypart)", "rules bundle (rulesVersion, featuresVersion)"],
            "futureInputs": ["tributary discharge trend (no Brain publishes it)", "depth zone shares (Depth Brain)", "observed vegetation (Vegetation Brain)"],
            "recomputeWhen": ["a feature state changes (temperature band, temperature trend, 24 h crossing, lake trend, clarity band, daypart)",
                              "species presence changes (Lake Brain)", "rulesVersion or featuresVersion changes", "an input becomes stale (> 36 h) or recovers"],
            "skipWhen": "state_fingerprint(new state) equals the last one: write nothing, log nothing",
            "needsClock": "no cron. The state depends on daypart and month, so it can change with elapsed time; it is evaluated on demand for a pilot lake before a trip "
                          "(prospective validation needs a timed snapshot BEFORE the outing), never because a customer opened a page",
            "maxInputAgeHours": 36,
            "note": "Must never be recomputed per user page-load. Per-lake publication to the Brain RTDB is OFF (needs approval).",
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


def plan_state(last_fingerprint: str | None, new_fingerprint: str) -> dict:
    """Decide whether a freshly evaluated Biological State needs to be written/logged. Pure. Compute because INPUT TRUTH CHANGED."""
    if last_fingerprint is None:
        return {"component": "biologicalState", "action": "WRITE", "reasons": ["no previous state"]}
    if last_fingerprint == new_fingerprint:
        return {"component": "biologicalState", "action": "SKIP", "reasons": ["material inputs unchanged (fingerprint equal)"]}
    return {"component": "biologicalState", "action": "WRITE", "reasons": ["fingerprint changed"]}
