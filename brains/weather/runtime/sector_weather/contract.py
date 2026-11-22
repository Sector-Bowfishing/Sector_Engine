"""Weather Brain contract constants. The weather-change thresholds and freshness tiers are PRE-STATED (owner decision 2026-11-22, Sector_Ops
#51): fixed before any result was seen, packaged as a verified knowledge release (runtime/knowledge/, versioned by THRESHOLDS_VERSION), and
changed only by a new version with its reason. They are checked, not fitted, by the pre-registered validation in the Weather Brain plan
(WEATHER_BRAIN_PLAN.md §5). The reason for each value is in the release file and in contracts/weather-state-v1.md.

The Weather Brain answers ONE question: what is the weather doing at this lake, from measured station observations and the official NWS
forecast, and is it changing? It never decides whether tonight is good, never predicts fish, and never fills a gap with an estimate."""
from __future__ import annotations

import re
from datetime import datetime, timezone

BRAIN_ID = "weather"
SLOT = "weather"                              # /lakes/{k}/states/weather, /lakeFleet/{k}/slots/weather
DISPLAY_NAME = "Weather"
DOMAIN = "condition"
QUESTION = "What is the weather doing at this lake, and is it changing?"
BRAIN_VERSION = "weather-brain-0.1.0"
STATE_SCHEMA = "sector-brain-weather-state-v1"
SCHEMA_VERSION = 1
PROVIDER = "api.weather.gov (U.S. National Weather Service)"
SOURCE_IDS = ("nws-station-observations", "nws-forecast-grid")

HPA_TO_INHG = 0.0295299830714                  # WeatherReading.hPaToInHg (iOS)

# ── observation selection (the Engine NWS adapter's rules, NWS_WEATHER_ADAPTER_V1 §2) ─────────────────────────────────────────────
OBSERVATION_MAX_AGE_MIN = 120                  # an observation older than this is never "now"
PREFERRED_MAX_AGE_MIN = 75                     # newest-wins window across the nearest stations
MAX_STATIONS = 3
SLP_OFFSET_MAX_AGE_MIN = 360
TREND_SAMPLE_TOLERANCE_MIN = 90                # a trend needs a past sample within 90 min of its target (strict <)
OBS_LOOKBACK_HOURS = 13                        # 12 h trend + one hour of slack
FORECAST_HOURS = 12

# ── pressure trend: the iOS app's definitions (WeatherService.swift) ──────────────────────────────────────────────────────────────
TREND_3H_STEADY_INHG = 0.02                    # displayPressureTrend: 3 h tendency, steady within ±0.02 inHg (the tile/sheet/score trend)
TREND_12H_STEADY_HPA = 1.5                     # pressureTrend: 12 h lookback, steady within ±1.5 hPa (kept for parity; not the tile trend)

# ── sky wording: the iOS Sky tile (MetricSheets.swift cloudWord) ──────────────────────────────────────────────────────────────────
def cloud_word(pct: float | None) -> str | None:
    if pct is None:
        return None
    c = int(round(pct))
    return "clear" if c < 25 else ("broken cloud" if c < 60 else "overcast")


# ── weather-change signal and cadence: PRE-STATED, loaded from the verified knowledge release (knowledge.py; refuses if it does not verify) ──
from .knowledge import load as _load_knowledge                     # noqa: E402

RELEASE, _K = _load_knowledge()
THRESHOLDS_VERSION = _K["thresholdsVersion"]
THRESHOLDS = dict(_K["changeRules"])          # pressureFastInHgPer3h, airTempSwingFPer3h, frontWindShiftDeg, ... (weather-state-v1.md §4)
CHANGE_LEVELS = ("CHANGE", "WATCH", "STEADY")
EVENT_KINDS = ("PRESSURE_FALLING_FAST", "PRESSURE_RISING_FAST", "AIR_TEMP_SWING", "FRONT_PASSAGE", "RAIN_ONSET", "RAIN_EXPECTED")

# ── the Brain's own refresh cadence (the Lake Brain's adaptive-freshness shape, #216; weather-state-v1.md §5) ───────────────────────
_F = _K["freshness"]
TIER_WINDOW_MIN = dict(_F["tierWindowMin"])   # how long a reading counts as current, from the OBSERVATION
CEILING_MIN = _F["ceilingMin"]                # never current more than 4 h after the observation, whatever the tier
REFRESH_LATENCY_MIN = _F["refreshLatencyMin"] # one hourly Orchestrator grant + run and publish: counted from the RUN
RECHECK_MIN = _F["recheckMin"]                # CHANGE/WATCH lakes: recomputed on every hourly grant
STEADY_RECHECK_MAX_MIN = _F["steadyRecheckMaxMin"]
PLANNER_TOLERANCE_MIN = _F["plannerToleranceMin"]
STALE_AFTER_HOURS = _F["staleAfterHours"]     # Brain-level registry rule: a lake state generated more than 3 h ago is stale
DUE_AFTER_HOURS = _F["dueAfterHours"]         # the Orchestrator grants every hourly tick; the per-lake planner decides who is fetched

READINESS_DEFINITIONS = {
    "DISCOVERED": "In the canonical Sector lake directory; no Weather state computed yet.",
    "CALIBRATION": "A state from a fresh station observation plus the NWS forecast grid; pressure/air-temperature validation pending (plan §5).",
    "DEGRADED": "A state exists but its observation is stale or a tile is missing this run (no estimate is put in its place).",
    "BLOCKED": "Outside NWS coverage (api.weather.gov /points has no grid for the lake): the Brain abstains for this lake.",
}
STATE_KINDS = {
    "observation": "Pressure and air temperature come from a station observation (ASOS/AWOS via api.weather.gov).",
    "forecast": "No fresh observation: air temperature and humidity are the NWS forecast grid's current hour; pressure is null.",
    "unavailable": "No observation and no forecast value: every tile is null.",
}


def lake_key(lake_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id)


def iso(t: datetime | None) -> str | None:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def r(x: float | None, nd: int = 1) -> float | None:
    return None if x is None else round(x, nd)
