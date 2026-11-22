"""Moon and Night Light Brain contract constants. The machine-readable contract is brains/moon/contracts/moon-night-light-v1.json
(the output state, the optional Weather input and DARKNESS_RULE_V1); the Publisher declaration is contracts/moon-publication-v1.json."""
from __future__ import annotations

from datetime import datetime, timezone

BRAIN_ID = "moon"
SLOT = "moon"
SNAPSHOT_FIELD = "moonNightLight"
DISPLAY_NAME = "Moon and Night Light"
DOMAIN = "condition"
QUESTION = "How much moonlight reaches the water tonight, and when does it get dark?"
BRAIN_VERSION = "moon-brain-0.1.0-calibration"
SCHEMA_VERSION = 1
STATE_SCHEMA = "moon-night-light-v1"
MODEL_ID = "sector-moon-v1+usno-events+darkness-rule-v1"
JOB_ID = "moon-brain"
STALENESS_MODEL = "TIME"                 # tonight changes every day; cloud input changes hourly
STALE_AFTER_HOURS = 24
DEPENDS_ON = []                          # the Weather Brain (cloud cover) is an OPTIONAL input declared in the contract, not yet a registered Brain
EPHEMERIS_SPEC = "sector-moon-v1"        # contracts/moon/moon-v1.json
EVENT_DEFINITIONS = "USNO / Meeus ch. 15 standard altitudes (sun -0.8333, -6, -12, -18; moon 0.7275*parallax - 0.5667)"
WEATHER_INPUT_CONTRACT = "moon-weather-cloud-input-v0"   # provisional: replaced by the Weather Brain's own contract when it exists

READINESS = ("CALIBRATION", "DEGRADED")
DARKNESS_CLASSES = ("DARK", "MOSTLY_DARK", "SOME_MOONLIGHT", "BRIGHT_MOON", "NO_NIGHT")
DARKNESS_BASES = ("MOON_AND_CLOUD", "MOON_ONLY", "NO_NIGHT")
READINESS_DEFINITIONS = {
    "CALIBRATION": "computed from the ephemeris; cross-checked against USNO in tests; not field-validated as a darkness measure",
    "DEGRADED": "the lake could not be computed this run (error recorded); nothing is substituted",
}
SCORE_NOTE = "The Moon and Night Light Brain has no Engine readiness score: no rubric has been approved for it."


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
