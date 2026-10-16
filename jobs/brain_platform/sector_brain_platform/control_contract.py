"""The shared Brain control summary (docs/brains/platform/OPS_CONTROL_CONTRACT.md) - Model v1 field names.

Pure and additive. It does NOT replace control.brain_summary; `from_control_summary` maps the existing live summary onto the v1 names so a
migration can be dry-run and diffed before anything publishes. Fields a Brain cannot honestly fill are omitted, never defaulted.
"""
from __future__ import annotations

from .model_v1 import CUSTOMER_READINESS, LIFECYCLE, LIFECYCLE_CONDITIONS, SCORE_STATUS, ModelError, map_legacy_lifecycle

CONTROL_MODEL_VERSION = "brain-control-v1"
OPTIONAL = ("canonicalScore", "underlyingScore", "displayedScore", "scoreStatus", "claimMaturity", "criticalGates", "coverage", "validation",
            "freshness", "stateVersion", "lastMeaningfulUpdate", "executionType", "blockers", "nextExpectedUpdate", "customerReadiness", "dependencies")


def validate_control(c: dict) -> dict:
    if not c.get("brainId"):
        raise ModelError("control summary needs brainId")
    if c.get("lifecycle") not in LIFECYCLE + LIFECYCLE_CONDITIONS:
        raise ModelError(f"{c.get('brainId')}: lifecycle {c.get('lifecycle')!r} not in the v1 vocabulary")
    if "scoreStatus" in c and c["scoreStatus"] not in SCORE_STATUS:
        raise ModelError("scoreStatus not in vocabulary")
    if "customerReadiness" in c and c["customerReadiness"] not in CUSTOMER_READINESS:
        raise ModelError("customerReadiness not in vocabulary")
    bare = [k for k in ("score",) if k in c]
    if bare:
        raise ModelError("the bare field name 'score' is ambiguous; use canonicalScore / underlyingScore / displayedScore")
    cs, ds = c.get("canonicalScore"), c.get("displayedScore")
    if cs is not None and ds is not None and ds > cs:
        raise ModelError("displayedScore cannot exceed canonicalScore (gates only cap)")
    return c


def from_control_summary(brain_id: str, summary: dict) -> dict:
    """Map today's control.brains[id] onto v1 names. Reports the lifecycle mapping ambiguity instead of hiding it."""
    sc = summary.get("score") or {}
    legacy = summary.get("status")
    out = {"brainId": brain_id, "controlModel": CONTROL_MODEL_VERSION}
    if legacy:
        life, amb = map_legacy_lifecycle(legacy)
        out["lifecycle"] = life
        out["legacyLifecycle"] = legacy
        if amb:
            out["lifecycleMappingAmbiguous"] = True
    if sc.get("value") is not None:
        out["canonicalScore"] = sc["value"]
        out["displayedScore"] = sc["value"]
    if sc.get("uncapped") is not None:
        out["underlyingScore"] = sc["uncapped"]
    if sc.get("basis"):
        out["scoreStatus"] = {"COMPUTED": "COMPUTED", "FROZEN": "FROZEN"}.get(sc["basis"])
        if out["scoreStatus"] is None:
            del out["scoreStatus"]
    for src, dst in (("health", "health"), ("coverage", "coverage"), ("validation", "validation"), ("blockers", "blockers"),
                     ("lastSuccessfulRun", "lastMeaningfulUpdate"), ("version", "stateVersion")):
        if summary.get(src) not in (None, [], {}):
            out[dst] = summary[src]
    return out
