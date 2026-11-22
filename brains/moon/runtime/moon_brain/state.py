"""One lake-night: the moon-night-light-v1 state for /lakes/{k}/states/moon. Pure: no clock, no I/O, deterministic for its inputs."""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from . import contract as C
from . import darkness
from . import night


def _weather_rows(weather: dict | None) -> list:
    """The cloud rows the darkness rule reads from the Weather state (only those), so an unrelated Weather field never re-triggers."""
    if not isinstance(weather, dict):
        return []
    try:
        return sorted(([str(a), v, o] for a, v, o in darkness._weather_rows(weather)), key=lambda x: (x[0], x[2]))
    except (KeyError, TypeError, AttributeError):
        return [["MALFORMED"]]


def input_fingerprint(lake: dict, date: dt.date, weather: dict | None) -> str:
    """Material inputs only: the lake coordinate, the night, the cloud rows and the Brain version. No run time, no execution id."""
    blob = {"lakeId": lake["lakeId"], "lat": lake["lat"], "lon": lake["lon"], "date": date.isoformat(), "brainVersion": C.BRAIN_VERSION,
            "weather": _weather_rows(weather), "weatherSchema": (weather or {}).get("schema") if isinstance(weather, dict) else None}
    return hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()


def build_state(lake: dict, date: dt.date, weather: dict | None = None) -> dict:
    sky = night.tonight(lake["lat"], lake["lon"], date)
    dark = darkness.assess(sky, weather)
    return {
        "schema": C.STATE_SCHEMA, "schemaVersion": C.SCHEMA_VERSION, "brainId": C.BRAIN_ID, "brainVersion": C.BRAIN_VERSION,
        "lakeId": lake["lakeId"], "date": sky["date"], "readiness": "CALIBRATION",
        "span": sky["span"], "sun": sky["sun"], "moon": sky["moon"], "window": sky["window"], "darkness": dark,
        "provenance": {"ephemeris": C.EPHEMERIS_SPEC, "events": C.EVENT_DEFINITIONS, "darknessRule": darkness.RULE_ID,
                       "coordinate": {"lat": lake["lat"], "lon": lake["lon"], "source": "registry.lakes (LakeDirectory projection)"},
                       "weatherInput": "PROVIDED" if weather else "ABSENT",
                       "inputFingerprint": input_fingerprint(lake, date, weather)},
    }


def plan(published: dict | None, lake: dict, date: dt.date, weather: dict | None) -> dict:
    fp = input_fingerprint(lake, date, weather)
    if not published:
        return {"action": "PUBLISH", "reasons": ["no published Moon state"], "fingerprint": fp}
    if (published.get("provenance") or {}).get("inputFingerprint") != fp:
        return {"action": "PUBLISH", "reasons": ["input fingerprint changed"], "fingerprint": fp}
    return {"action": "SKIP", "reasons": ["inputs unchanged"], "fingerprint": fp}
