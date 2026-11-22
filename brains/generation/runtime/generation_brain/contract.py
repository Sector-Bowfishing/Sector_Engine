"""Generation Brain identity and the state contract constants (generation-dam-state-v1). Pure data."""
from __future__ import annotations

from datetime import datetime, timezone

BRAIN_ID = "generation"
DISPLAY_NAME = "Generation Brain"
DOMAIN = "dam-release-and-generation"
QUESTION = "Is the dam on this lake releasing or generating now, how much, and when does the operator's schedule start or stop it?"
SLOT = "generation"
SNAPSHOT_FIELD = "generation"
BRAIN_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"
STATE_SCHEMA = "generation-dam-state-v1"
MODEL_ID = "generation-release-assembly-v0.1"
LIFECYCLE = "CALIBRATION"
STALENESS_MODEL = "ADAPTIVE_PER_DAM"
DEPENDS_ON: tuple = ()

# State kinds: what one lake's state is built from. Never a value that no source measured or published.
OBSERVED = "OBSERVED"              # a measured release (discharge / units) within its freshness window, with or without a schedule
SCHEDULE_ONLY = "SCHEDULE_ONLY"    # the operator's published schedule covers now, but no measured release is current
UNAVAILABLE = "UNAVAILABLE"        # the lake has a bound source but nothing usable came back (or every reading is stale)
NOT_BOUND = "NOT_BOUND"            # no source is bound for this lake in the knowledge release (the stated coverage reason applies)
KINDS = {
    OBSERVED: "a measured release (operator discharge or unit status) inside its freshness window",
    SCHEDULE_ONLY: "the operator's published schedule covers now; no current measured release",
    UNAVAILABLE: "a bound source returned nothing usable or only stale readings: abstain, never a default",
    NOT_BOUND: "no source bound in the knowledge release; the catalog's coverage reason applies",
}

# Release status. UNKNOWN is an abstention, never "off".
GENERATING, SPILLING, RELEASING, OFF, UNKNOWN = "GENERATING", "SPILLING", "RELEASING", "OFF", "UNKNOWN"

READINESS_DEFINITIONS = {
    "CALIBRATION": "a bound source produced a current state; not validated against the operator's schedule yet",
    "DEGRADED": "a bound source failed or is stale this run",
    "NOT_BOUND": "no release source bound in the knowledge release",
}

SCORE_NOTE = "Generation has no Engine readiness score and no rubric; it publishes measured and published operator data only."

# Freshness tiers (freshness.py). Counted in minutes; the orchestrator grants at most hourly, so nothing is read more often than hourly.
TIER_TRANSITION, TIER_ACTIVE, TIER_STEADY, TIER_UNKNOWN = "TRANSITION", "ACTIVE", "STEADY", "UNKNOWN"


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s: str | None) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
