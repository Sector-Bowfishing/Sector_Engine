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


def window_cloud(weather: dict | None, start: float, end: float) -> dict:
    """Mean cloud cover over [start, end] from the optional Weather Brain input. Never fills a gap."""
    if not weather:
        return {"status": "MISSING", "reason": "NO_WEATHER_INPUT"}
    hourly = weather.get("hourly")
    if not isinstance(hourly, list) or not hourly:
        return {"status": "MISSING", "reason": "NO_HOURLY_CLOUD_COVER"}
    vals = []
    for row in hourly:
        try:
            t = _parse(row["at"])
            v = row["cloudCoverPct"]
        except (KeyError, TypeError, ValueError):
            return {"status": "MISSING", "reason": "MALFORMED_HOURLY_ROW"}
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0 <= v <= 100):
            return {"status": "MISSING", "reason": "CLOUD_COVER_OUT_OF_RANGE"}
        if start - 1800 <= t <= end + 1800:
            vals.append(float(v))
    hours = max(1, math.ceil((end - start) / 3600.0))
    coverage = len(vals) / hours
    if coverage < MIN_HOURLY_COVERAGE:
        return {"status": "MISSING", "reason": "INSUFFICIENT_COVERAGE", "hoursWithValue": len(vals), "windowHours": hours}
    return {"status": "AVAILABLE", "meanPct": round(sum(vals) / len(vals), 1), "hoursWithValue": len(vals),
            "windowHours": hours, "source": weather.get("source"), "issuedAt": weather.get("issuedAt"),
            "contract": weather.get("contract")}


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
