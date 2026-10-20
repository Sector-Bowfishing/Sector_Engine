"""WindBrain contract constants (Sector Brain Platform v1; Sector Ops docs SECTOR_BRAIN_RTDB_SCHEMA.md +
BRAIN_INTEGRATION_REQUIREMENTS.md §5). Engine owns these enums; Ops renders them verbatim.

WindBrain answers ONE question: what are the wind and water-surface conditions doing on this lake?
Shoreline ranking BY WIND EXPOSURE ONLY lives in the separate, nonproduction `sector_wind.assessment` layer (V2); this adapter never
decides fishing locations, whether tonight is good, or species behaviour — Sector Intelligence does."""
from __future__ import annotations

import re
from datetime import datetime, timezone

BRAIN_ID = "wind"
SLOT = "wind"                       # /lakes/{k}/states/wind, /lakeFleet/{k}/readiness/wind
SNAPSHOT_FIELD = "wind"             # /snapshots/{k}/latest/wind
DISPLAY_NAME = "Wind"
DOMAIN = "condition"
QUESTION = "What are the wind and water-surface conditions doing?"
BRAIN_VERSION = "wind-brain-1.0.0"
SCHEMA_VERSION = 1
STATE_SCHEMA = "sector-brain-wind-state-v1"
PROFILE_SCHEMA = "sector-brain-wind-profile-v1"
JOB_ID = "wind-hourly"
JOB_SCHEDULE = "5 * * * * (UTC)"

# ── Readiness (per lake + brain). Wind meaning of each value: ───────────────────────────────
READINESS_DEFINITIONS = {
    "DISCOVERED": "In the canonical Sector lake directory; WindBrain has no frozen fetch geometry and no forcing archive for it.",
    "PROFILED": "Frozen fetch tables built and QA'd (SPM84/CEM 9-ray); no live wind forcing archived, so no state is published.",
    "CALIBRATION": "Profiled + live hourly NBM/RTMA-RU/METAR archive + atmospheric validation against local stations; "
                   "surface/exposure physics NOT field-validated (Wind Certification caps 6 and 7 active).",
    "BETA": "Not used yet.",
    "VALIDATED": "Not reached: needs field (bank-scale) exposure + surface validation under Evidence Addendum v1.",
    "PRODUCTION": "Not reached: the Candidate is research/shadow only; production wind is Open-Meteo Best Match in /conditions.",
    "DEGRADED": "A CALIBRATION lake whose current state is stale, partial or unavailable this run.",
    "BLOCKED": "Not used yet.",
}
READINESS = tuple(READINESS_DEFINITIONS)
HEALTH = ("HEALTHY", "WARNING", "DEGRADED", "FAILED", "UNKNOWN", "NOT_CONFIGURED")
STATE_KINDS = {
    "analysis": "Current value is the RTMA-RU 2.5 km analysis at the lake point (an analysis, not an observation).",
    "forecast": "No fresh analysis; current value is the newest NBM forecast for this hour (a forecast, not an observation).",
    "unavailable": "No usable analysis or forecast; values are null.",
}

# ── Freshness (BRAIN_INTEGRATION_REQUIREMENTS §5 'Stale') ───────────────────────────────────
STALE_FORECAST_CYCLE_H = 3.0        # newest NBM cycle older than this -> stale
STALE_GENERATED_MIN = 90            # state generatedAt older than this -> stale (Ops-side clock check)
STALE_AFTER_HOURS = STALE_GENERATED_MIN / 60
ANALYSIS_MAX_AGE_H = 2.0            # RTMA-RU older than this is not used as 'current'
OBSERVATION_MAX_AGE_H = 1.5         # METAR older than this is not shown as the latest observation
HOURLY_MAX = 24
TREND_THRESHOLD_MPH = 2.0           # forecast(+3 h) vs current: |Δ| < 2 mph -> steady
TRANSITION_THRESHOLDS_MPH = (5, 10, 15, 20)

# ── Models (do NOT silently promote the candidate) ──────────────────────────────────────────
CANDIDATE_MODEL = "wind-candidate-2026.10.stage2-baseline"
PRODUCTION_MODEL = {
    "modelId": "open-meteo-best-match",
    "status": "ACTIVE_PRODUCTION",
    "servedBy": "Sector Engine /conditions (Swift WeatherService) + Sector app conditions card",
    "provider": "Open-Meteo /v1/forecast, no `models` parameter (Best Match), wind_speed_unit=mph",
    "resolvesTo": "NOAA HRRR (about 0-46 h), then GFS; the model used is not exposed in the response",
    "gustDefinition": "max of the preceding hour",
    "licence": "free tier (non-commercial terms); Sector is a subscription app",
    "brainOutput": False,
    "note": "WindBrain does not compute or republish production wind; Ops already reads it live from Engine /conditions.",
}
RESEARCH_CANDIDATE = {
    "modelId": CANDIDATE_MODEL,
    "status": "RESEARCH_CANDIDATE",
    "promoted": False,
    "forcing": "NOAA NBM v5.0 (direct NODD, hourly cycles) + RTMA-RU (15 min analysis) + METAR (local observed evidence)",
    "surfacePhysics": "frozen CEM EM 1110-2-1100 II-2-36..39 + frozen duration rule (M0) + frozen SPM84/CEM fetch tables",
    "archive": "gs://sector-wind-candidate/wind/v1 (private)",
}
H2_SEALED_UNTIL = datetime(2027, 1, 1, tzinfo=timezone.utc)


def lake_key(lake_id: str) -> str:
    """Engine storage slug (same as gs://sector-lake-surface/lakes/<slug>/)."""
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id)


def iso(t: datetime | None) -> str | None:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def mph(ms: float | None) -> float | None:
    return None if ms is None else round(ms / 0.44704, 1)


CARDINALS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")


def cardinal(deg: float | None) -> str | None:
    return None if deg is None else CARDINALS[int((deg % 360) / 22.5 + 0.5) % 16]
