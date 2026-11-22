"""On-water darkness: moon illumination x moon presence across the fishing window, reduced by cloud when the Weather Brain
supplies cloud cover. The rule is fixed BEFORE anything is scored and lives in contracts/moon-night-light-v1.json
(darknessRule); this module is its only implementation.

DARKNESS_RULE_V1 (constants are the Engine's DarknessFactor / ConditionsConfig.Darkness, so the Brain and the app agree):

    I  = moon illumination at local solar midnight                    (0..1, sector-moon-v1)
    P  = moon presence over the window = mean max(0, sin(alt))         (0..1, the Engine's moonAltitudeFraction)
    C  = clamp((cloudPct - 50) / 50, 0, 1) * (1 - 0.8 * 0.3)           (cloud that cancels moonlight; 0.3 = the Engine's default
                                                                        city-glow, since no per-lake skyglow input exists)
    A  = I * P * (1 - C)                                               (moonlight reaching the water, 0..1)
    class: A < 0.15 DARK | A < 0.35 MOSTLY_DARK | A < 0.60 SOME_MOONLIGHT | else BRIGHT_MOON

Cloud comes from the Weather Brain state (sector-brain-weather-state-v1): forecast.hourly[].cloudCoverPct plus the current-hour
sky.cloudCoverPct, mean over the distinct hours of the window (window_cloud).

Cloud cover missing, partial or invalid -> C is NOT assumed (the Engine's `cloud ?? 0` default is a guess this Brain refuses):
the answer is the MOON_ONLY class (A = I * P, the clear-sky upper bound on moonlight), labelled as such, with the reason.
No night (Sun never sets) -> class NO_NIGHT.
"""
from __future__ import annotations

import datetime as dt
import math

RULE_ID = "DARKNESS_RULE_V1"
CLOUD_KNEE_PCT = 50.0
CLOUD_SPAN_PCT = 50.0
DEFAULT_CITY_GLOW = 0.3
CITY_GLOW_BLOCKING_WEIGHT = 0.8
MIN_HOURLY_COVERAGE = 0.75
CLASSES = (("DARK", 0.15), ("MOSTLY_DARK", 0.35), ("SOME_MOONLIGHT", 0.60), ("BRIGHT_MOON", math.inf))
EFFECTIVE_LABEL = {"MOSTLY_DARK": "mostly dark", "SOME_MOONLIGHT": "some glow", "BRIGHT_MOON": "bright — moon up"}


def _parse(ts: str) -> float:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def _parse_aware(ts) -> float:
    """An hourly timestamp must carry an explicit UTC offset ('Z' or +hh:mm). A naive one would be read in the host's local time, so it is
    refused (ValueError -> MALFORMED_HOURLY_ROW), never guessed."""
    if not isinstance(ts, str):
        raise ValueError("timestamp is not a string")
    t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("timestamp has no UTC offset")
    return t.timestamp()


def classify(moonlight_index: float) -> str:
    for name, upper in CLASSES:
        if moonlight_index < upper:
            return name
    return "BRIGHT_MOON"


def label(cls: str, illumination: float, presence: float) -> str:
    """The Engine's DarknessFactor label: '<phase %> moon · <effective>'."""
    if cls == "DARK":
        eff = "moon down" if presence < 0.15 else "dark water"
    else:
        eff = EFFECTIVE_LABEL[cls]
    return f"{int(round(illumination * 100))}% moon · {eff}"


WEATHER_STATE_SCHEMA = "sector-brain-weather-state-v1"
WINDOW_MARGIN_S = 1800


def _miss(reason: str, **extra) -> dict:
    return {"status": "MISSING", "reason": reason, **extra}


def _weather_rows(weather: dict) -> list:
    """Hourly cloud rows from a Weather Brain state document (sector-brain-weather-state-v1, /lakes/{k}/states/weather):
    `forecast.hourly[]` rows {at, cloudCoverPct: number|null} (the NWS forecast grid, origin forecastGrid) and the current hour
    `sky.cloudCoverPct` {value, at, origin}. Nothing else in the document is read. Raises KeyError/TypeError on a malformed shape."""
    rows = []
    for r in (weather.get("forecast") or {}).get("hourly") or []:
        rows.append((r["at"], r["cloudCoverPct"], "forecastGrid"))
    cur = (weather.get("sky") or {}).get("cloudCoverPct")
    if cur is not None:
        rows.append((cur["at"], cur["value"], cur.get("origin") or "unknown"))
    return rows


def window_cloud(weather: dict | None, start: float, end: float) -> dict:
    """Mean cloud cover over the fishing window from the optional Weather Brain state. Never fills a gap.

    Coverage counts DISTINCT hours: each row is keyed on the top of its hour, the same hour twice with the same value counts once, and the
    same hour with two different values refuses the input (CONFLICTING_HOURLY_VALUES), so a repeated reading cannot pass the floor. The window's
    hours are the top-of-hour instants within [start - 30 min, end + 30 min]; at least 75 % of them need a value."""
    if not weather:
        return _miss("NO_WEATHER_INPUT")
    if not isinstance(weather, dict) or weather.get("schema") != WEATHER_STATE_SCHEMA:
        return _miss("UNSUPPORTED_WEATHER_INPUT")
    try:
        rows = _weather_rows(weather)
    except (KeyError, TypeError, AttributeError):
        return _miss("MALFORMED_HOURLY_ROW")
    if not rows:
        return _miss("NO_HOURLY_CLOUD_COVER")
    by_hour, origins = {}, {}
    for at, v, origin in rows:
        try:
            t = _parse_aware(at)
        except ValueError:
            return _miss("MALFORMED_HOURLY_ROW")
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0 <= v <= 100):
            return _miss("CLOUD_COVER_OUT_OF_RANGE")
        h = int(t // 3600) * 3600
        if h in by_hour and by_hour[h] != float(v):
            return _miss("CONFLICTING_HOURLY_VALUES")
        by_hour[h], origins[h] = float(v), origin
    first = int(math.ceil((start - WINDOW_MARGIN_S) / 3600.0)) * 3600
    expected = list(range(first, int(end + WINDOW_MARGIN_S) + 1, 3600)) or [int(start // 3600) * 3600]
    have = [h for h in expected if h in by_hour]
    if len(have) / len(expected) < MIN_HOURLY_COVERAGE:
        return _miss("INSUFFICIENT_COVERAGE", hoursWithValue=len(have), windowHours=len(expected))
    used = {}
    for h in have:
        used[origins[h]] = used.get(origins[h], 0) + 1
    return {"status": "AVAILABLE", "meanPct": round(sum(by_hour[h] for h in have) / len(have), 1), "hoursWithValue": len(have),
            "windowHours": len(expected), "source": "weather", "contract": WEATHER_STATE_SCHEMA,
            "issuedAt": (weather.get("forecast") or {}).get("issuedAt"), "generatedAt": weather.get("generatedAt"), "origins": used}


def cloud_cancel(cloud_pct: float) -> float:
    f = min(1.0, max(0.0, (cloud_pct - CLOUD_KNEE_PCT) / CLOUD_SPAN_PCT))
    return f * (1 - CITY_GLOW_BLOCKING_WEIGHT * DEFAULT_CITY_GLOW)


def assess(sky: dict, weather: dict | None) -> dict:
    """The on-water darkness block for one lake-night. `sky` is night.tonight(...)."""
    illum = sky["moon"]["illumination"]
    win = sky["window"]
    if win.get("start") is None:
        return {"rule": RULE_ID, "class": "NO_NIGHT", "basis": "NO_NIGHT",
                "statement": "The Sun does not set at this lake tonight; there is no dark window to classify.",
                "cloudCover": {"status": "NOT_APPLICABLE"}}
    presence = win["moonlight"]["presence"]
    moon_only_index = round(illum * presence, 4)
    moon_only = classify(moon_only_index)
    cloud = window_cloud(weather, _parse(win["start"]), _parse(win["end"]))
    out = {"rule": RULE_ID, "illumination": illum, "presence": presence,
           "moonOnly": {"moonlightIndex": moon_only_index, "class": moon_only, "label": label(moon_only, illum, presence)},
           "cloudCover": cloud}
    if cloud["status"] == "AVAILABLE":
        cancel = round(cloud_cancel(cloud["meanPct"]), 4)
        idx = round(illum * presence * (1 - cancel), 4)
        cls = classify(idx)
        out.update({"basis": "MOON_AND_CLOUD", "cloudCancel": cancel, "moonlightIndex": idx, "class": cls,
                    "label": label(cls, illum, presence),
                    "statement": f"Moon and cloud: {cloud['meanPct']}% mean cloud over the window cancels {round(cancel * 100)}% of the moonlight."})
    else:
        out.update({"basis": "MOON_ONLY", "cloudCancel": None, "moonlightIndex": moon_only_index, "class": moon_only,
                    "label": label(moon_only, illum, presence),
                    "statement": f"Cloud cover not available ({cloud['reason']}): moon-only answer, the clear-sky upper bound on moonlight. No cloud value was assumed."})
    return out
