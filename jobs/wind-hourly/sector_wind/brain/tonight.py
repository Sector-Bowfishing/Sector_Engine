"""WindState `tonight` block: only what the research supports (docs/wind-research/WIND_FORECAST_VALIDATION.md,
frozen H2 criteria docs/brains/wind/WIND_H2_PREREG.md).

SUPPORTED   direction when the forecast is >= 5 mph; calm/light category; "could turn breezy" risk flag (NBM P90);
            "easing" / "steady" over the evening.
WITHHELD    lay-down, rising, gust, exact over-water speed, direction below 5 mph. These are emitted as null with a
            reason, never as a guess. Forecast values are never labelled as observations.

Pure functions: no I/O, deterministic. The same functions are used by the H2 runner so the product and its test cannot
drift apart."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import contract as C

SCHEMA = "sector-wind-tonight-v1"
CAT_EDGES = (5.0, 10.0, 15.0)                       # mph: calm < 5 <= light < 10 <= breezy < 15 <= windy
CATEGORIES = ("calm", "light", "breezy", "windy")
DIRECTION_MIN_MPH = 5.0                             # below this the direction is not shown (research: 0.65 within 22.5 deg at 3-5 mph)
CONF_HIGH_MIN_MPH, CONF_MED_MIN_MPH = 5.0, 3.0
BREEZY_P90_MPH = 10.0                               # NBM P90 sustained >= this at any tonight hour => breezy-risk flag
TREND_STEP_MPH = 2.0
WINDOW_LOCAL_START_H, WINDOW_LOCAL_END_H = 19, 25   # 19:00 -> 01:00 local clock (the validated 00Z-06Z CDT window)
MIN_WINDOW_HOURS = 3
PERCENTILE_MAX_AGE_H = 12.0                         # P90 exists only for 00/06/12/18Z inits; older than this is not used

STATE_TZ = {
    "AL": "America/Chicago", "AR": "America/Chicago", "IL": "America/Chicago", "IA": "America/Chicago", "LA": "America/Chicago",
    "MN": "America/Chicago", "MS": "America/Chicago", "MO": "America/Chicago", "OK": "America/Chicago", "WI": "America/Chicago",
    "CT": "America/New_York", "DE": "America/New_York", "GA": "America/New_York", "ME": "America/New_York", "MD": "America/New_York",
    "MA": "America/New_York", "NH": "America/New_York", "NJ": "America/New_York", "NY": "America/New_York", "NC": "America/New_York",
    "OH": "America/New_York", "PA": "America/New_York", "RI": "America/New_York", "SC": "America/New_York", "VT": "America/New_York",
    "VA": "America/New_York", "WV": "America/New_York", "DC": "America/New_York",
    "CO": "America/Denver", "MT": "America/Denver", "NM": "America/Denver", "UT": "America/Denver", "WY": "America/Denver",
    "AZ": "America/Phoenix", "CA": "America/Los_Angeles", "NV": "America/Los_Angeles", "WA": "America/Los_Angeles",
    "AK": "America/Anchorage", "HI": "Pacific/Honolulu",
}
# Split states resolved by longitude (west of the line = first zone).
SPLIT_TZ = {
    "FL": (-85.0, "America/Chicago", "America/New_York"), "TN": (-85.5, "America/Chicago", "America/New_York"),
    "KY": (-86.0, "America/Chicago", "America/New_York"), "IN": (-86.5, "America/Chicago", "America/New_York"),
    "MI": (-87.6, "America/Chicago", "America/Detroit"), "TX": (-104.0, "America/Denver", "America/Chicago"),
    "KS": (-101.8, "America/Denver", "America/Chicago"), "NE": (-101.0, "America/Denver", "America/Chicago"),
    "SD": (-100.3, "America/Denver", "America/Chicago"), "ND": (-101.3, "America/Denver", "America/Chicago"),
    "ID": (-115.5, "America/Los_Angeles", "America/Boise"), "OR": (-117.0, "America/Los_Angeles", "America/Boise"),
}


def category(mph: float | None) -> str | None:
    if mph is None:
        return None
    return CATEGORIES[sum(mph >= e for e in CAT_EDGES)]


def tz_for(state: str | None, lon: float | None) -> str | None:
    """IANA zone from the lake's state (and longitude for split states). None when it cannot be determined."""
    if not state:
        return None
    if state in SPLIT_TZ:
        if lon is None:
            return None
        edge, west, east = SPLIT_TZ[state]
        return west if lon < edge else east
    return STATE_TZ.get(state)


def tonight_window(now: datetime, tzname: str) -> tuple[datetime, datetime]:
    """19:00 -> 01:00 local clock. Before 01:00 the window that began the previous evening is still 'tonight'."""
    tz = ZoneInfo(tzname)
    loc = now.astimezone(tz)
    day = loc.date() if loc.hour >= 2 else (loc - timedelta(days=1)).date()
    start = datetime(day.year, day.month, day.day, WINDOW_LOCAL_START_H, tzinfo=tz)
    end = start + timedelta(hours=WINDOW_LOCAL_END_H - WINDOW_LOCAL_START_H)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def circ_mean_deg(dirs: list[float], weights: list[float]) -> float | None:
    sx = sum(w * math.sin(math.radians(d)) for d, w in zip(dirs, weights))
    sy = sum(w * math.cos(math.radians(d)) for d, w in zip(dirs, weights))
    if abs(sx) + abs(sy) < 1e-9:
        return None
    return math.degrees(math.atan2(sx, sy)) % 360


def circ_dist(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def breezy_flag(p90_mph_max: float | None) -> bool | None:
    return None if p90_mph_max is None else p90_mph_max >= BREEZY_P90_MPH


def confidence(mean_mph: float | None, flag: bool | None, stale: bool) -> tuple[str, list[str]]:
    """Frozen in WIND_H2_PREREG: HIGH = mean >= 5 and no breezy-risk flag; MEDIUM = mean 3-5, or flag; LOW = mean < 3 / unavailable / stale.
    An unknown flag (no percentile cycle) cannot be HIGH."""
    if mean_mph is None or stale:
        return "LOW", ["forecastUnavailableOrStale"]
    if mean_mph < CONF_MED_MIN_MPH:
        return "LOW", ["windTooLightForDirection"]
    reasons = []
    if mean_mph < CONF_HIGH_MIN_MPH:
        reasons.append("lightWindDirectionLessCertain")
    if flag:
        reasons.append("breezyRisk")
    if flag is None:
        reasons.append("noPercentileCycle")
    return ("HIGH", []) if not reasons else ("MEDIUM", reasons)


def build_tonight(steps: list[dict], p90_steps: list[dict] | None, init: datetime | None, p90_init: datetime | None,
                  now: datetime, tzname: str | None, current: dict | None = None) -> dict:
    """steps: [{'at': iso, 'mph', 'dirDeg', 'gustMph'}] from the newest NBM cycle (any hour).
    p90_steps: [{'at': iso, 'p90Mph'}] from the newest percentile cycle, or None.
    current: {'kind','sustainedMph','gustMph','directionDeg'} already in the state (analysis or forecast), passed through unchanged."""
    block = {"schema": SCHEMA, "kind": "forecast", "basis": "NOAA NBM v5.0 point forecast (land-referenced; not an over-water observation)",
             "window": None, "current": current, "available": False, "unavailableReason": None,
             "speed": None, "direction": None, "trend": None, "breezyRisk": None, "confidence": None, "freshness": None,
             "withheld": {"layDown": "no validated skill (POD 0.07)", "rising": "no validated skill", "gust": "forecast gusts unvalidated (NBM ≥20 kt POD 0)",
                          "overWaterSpeed": "no over-water reference", "directionBelow5mph": "unreliable (0.65 within 22.5° at 3-5 mph)"}}
    if tzname is None:
        block["unavailableReason"] = "timeZoneUnknown"
        return _finish(block, None, init, p90_init, now)
    ws, we = tonight_window(now, tzname)
    block["window"] = {"startUtc": C.iso(ws), "endUtc": C.iso(we), "timeZone": tzname, "localHours": "19:00-01:00"}
    stale = init is None or (now - init).total_seconds() / 3600 > C.STALE_FORECAST_CYCLE_H
    inwin = [s for s in steps if s.get("mph") is not None and ws <= _t(s["at"]) <= we]
    if len(inwin) < MIN_WINDOW_HOURS:
        block["unavailableReason"] = "forecastDoesNotCoverTonight"
        return _finish(block, True if init is None else stale, init, p90_init, now)
    mph = [s["mph"] for s in inwin]
    mean = round(sum(mph) / len(mph), 1)
    # speed
    p90max = None
    if p90_steps and p90_init is not None and (now - p90_init).total_seconds() / 3600 <= PERCENTILE_MAX_AGE_H:
        vals = [p["p90Mph"] for p in p90_steps if p.get("p90Mph") is not None and ws <= _t(p["at"]) <= we]
        p90max = max(vals) if vals else None
    flag = breezy_flag(p90max)
    block["speed"] = {"meanMph": mean, "minMph": min(mph), "maxMph": max(mph), "category": category(mean),
                      "ifItBlowsMph": p90max, "ifItBlowsCategory": category(p90max),
                      "note": "Point forecast. Observed wind above 10 mph ran 4.6-6 mph higher than forecast in research; treat the category as a floor, not a ceiling."}
    # direction (shown only when the mean forecast is >= 5 mph)
    dirs = [(s["dirDeg"], s["mph"]) for s in inwin if s.get("dirDeg") is not None and s["mph"] >= 1.0]
    dmean = circ_mean_deg([d for d, _ in dirs], [w for _, w in dirs]) if dirs else None
    shown = dmean is not None and mean >= DIRECTION_MIN_MPH
    spread = None
    if dirs and dmean is not None:
        spread = round(max(circ_dist(d, dmean) for d, _ in dirs))
    block["direction"] = {"shown": shown, "fromDeg": round(dmean) if shown else None, "fromCardinal": C.cardinal(dmean) if shown else None,
                          "maxSpreadDeg": spread if shown else None,
                          "reason": None if shown else ("windTooLightForDirection" if dmean is not None or mean < DIRECTION_MIN_MPH else "directionUnavailable"),
                          "convention": "meteorological: the bearing the wind blows FROM"}
    # trend: easing / steady only
    first, last = _nearest(inwin, ws), _nearest(inwin, we)
    if first and last and first is not last:
        delta = round(last["mph"] - first["mph"], 1)
        if delta <= -TREND_STEP_MPH:
            label, why = "easing", "forecast speed at the end of the evening is at least 2 mph below the start"
        elif delta < TREND_STEP_MPH:
            label, why = "steady", "forecast speed changes less than 2 mph over the evening"
        else:
            label, why = None, "increase not claimed (no validated skill); see breezyRisk"
        block["trend"] = {"label": label, "deltaMph": delta, "basis": why, "validation": "easing precision 0.65 (CAL+H1); lay-down and rising have no validated skill"}
    # breezy risk
    block["breezyRisk"] = {"flag": flag, "p90MaxMph": p90max, "thresholdMph": BREEZY_P90_MPH,
                           "basis": "NBM P90 sustained wind at any hour of the window",
                           "meaning": None if flag is None else ("could turn breezy" if flag else None),
                           "evidence": "about 1 in 3 flagged nights reached 10 mph versus 1 in 50 unflagged (CAL+H1, land stations); a risk flag, not a prediction",
                           "unavailableReason": None if flag is not None else "noRecentPercentileCycle"}
    lab, reasons = confidence(mean, flag, stale)
    block["confidence"] = {"label": lab, "reasons": reasons, "basis": "frozen rule: WIND_H2_PREREG.md"}
    block["available"] = True
    return _finish(block, stale, init, p90_init, now)


def _finish(block, stale, init, p90_init, now):
    block["freshness"] = {"forecastInit": C.iso(init), "forecastAgeHours": None if init is None else round((now - init).total_seconds() / 3600, 2),
                          "percentileInit": C.iso(p90_init), "percentileAgeHours": None if p90_init is None else round((now - p90_init).total_seconds() / 3600, 2),
                          "stale": bool(stale) if stale is not None else True, "generatedAt": C.iso(now)}
    if block["confidence"] is None:
        block["confidence"] = {"label": "LOW", "reasons": [block["unavailableReason"] or "unavailable"], "basis": "frozen rule: WIND_H2_PREREG.md"}
    return block


def _t(iso_s: str) -> datetime:
    return datetime.strptime(iso_s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _nearest(rows, t):
    return min(rows, key=lambda r: abs((_t(r["at"]) - t).total_seconds())) if rows else None
