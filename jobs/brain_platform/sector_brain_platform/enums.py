"""The closed vocabularies (contract section 3). Ops renders these verbatim."""
from __future__ import annotations

HEALTH = ("HEALTHY", "WARNING", "DEGRADED", "FAILED", "UNKNOWN", "NOT_CONFIGURED")
READINESS = ("DISCOVERED", "PROFILED", "CALIBRATION", "BETA", "VALIDATED", "PRODUCTION", "DEGRADED", "BLOCKED")
READINESS_LADDER = ("DISCOVERED", "PROFILED", "CALIBRATION", "BETA", "VALIDATED", "PRODUCTION")
BRAIN_STATUS = READINESS_LADDER
MODEL_LIFECYCLE = ("RESEARCH", "CANDIDATE", "SHADOW", "REVIEW", "PRODUCTION", "RETIRED")
VERSION_STATUS = ("CURRENT", "SHADOW", "CANDIDATE", "RETIRED")
STATE_KIND = ("measured", "modeled", "observed", "proxy", "analysis", "forecast", "evaluated", "not_evaluated", "unavailable")
STALENESS_MODEL = ("TIME", "VERSION", "FINGERPRINT")
# Evidence freshness verdict (BRAIN_IDENTITY_AND_LINEAGE_V1 section 4; the Publisher's artifact freshness uses the same words — tested equal).
FRESHNESS_STATUS = ("FRESH", "STALE", "EXPIRED", "UNAVAILABLE", "UNKNOWN")
SEVERITY = ("info", "success", "warning", "critical")
ACTIVITY_KIND = ("brain.registered", "brain.version", "brain.updated", "run.failed", "run.degraded", "health.changed",
                 "readiness.promoted", "readiness.changed", "model.changed", "source.changed", "score.changed")

_LEGACY_LIFECYCLE = {"ACTIVE_PRODUCTION": "PRODUCTION", "RESEARCH_CANDIDATE": "CANDIDATE", "PRODUCTION_EVIDENCE": "PRODUCTION"}
_LEGACY_KIND = {"OBSERVED": "observed", "PROXY": "proxy", "UNAVAILABLE": "unavailable", "MEASURED": "measured",
                "MODELED": "modeled", "NOT_EVALUATED": "not_evaluated"}


def is_promotion(frm: str | None, to: str | None) -> bool:
    """True only for an upward move on the ladder; off-ladder values are changes, not promotions."""
    return frm in READINESS_LADDER and to in READINESS_LADDER and READINESS_LADDER.index(to) > READINESS_LADDER.index(frm)


def normalize_model_lifecycle(value: str) -> str:
    v = _LEGACY_LIFECYCLE.get(value, value)
    if v not in MODEL_LIFECYCLE:
        raise ValueError(f"not a model lifecycle: {value!r}")
    return v


def normalize_state_kind(value: str) -> str:
    v = _LEGACY_KIND.get(value, value.lower() if isinstance(value, str) else value)
    if v not in STATE_KIND:
        raise ValueError(f"not a state kind: {value!r}")
    return v
