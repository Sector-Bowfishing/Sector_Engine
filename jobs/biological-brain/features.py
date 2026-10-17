"""Biological condition features: what the Biological Brain MEANS by a condition, computed from specialist Brain states.

Ownership rule (docs/brains/BIOLOGICAL_RULES_AND_STATE_CONTRACT.md):
  * Specialist Brains own the environmental truth (water temperature, lake level/trend, clarity, tributary discharge,
    habitat classes). The Biological Brain NEVER fetches live data; it receives normalized inputs.
  * The Biological Brain owns the biological MEANING: e.g. `warmRise` = a rising stage while the water is at or above
    the temperature at which the researched species respond to a rise.
  * Missing, stale or unpublished input -> UNKNOWN. No placeholder environmental truth is ever created.

A feature is registered only when (a) researched Biological evidence supports a species response to it, (b) its inputs
can be supplied by a specialist Brain (today, or as an explicit NOT_PUBLISHED dependency), and (c) its meaning is
documented here. Everything is pure and deterministic.
"""
from __future__ import annotations

FEATURES_VERSION = "biological-features-v1"

UNKNOWN = "UNKNOWN"
TRUE, FALSE = "TRUE", "FALSE"

# Specialist input slots (normalized by the caller; see normalize_inputs in bio_state.py).
#   waterTemp.values: currentTempF, trend24hF         (Water Temp Brain)
#   lake.values:      trendState, levelState, tributaryDischargeTrend (Lake Brain; tributaryDischargeTrend NOT YET PUBLISHED)
#   waterClarity.values: clarityFt                    (Water Clarity Brain)
#   calendar:         month (1-12), daypart (DAY|TWILIGHT|NIGHT)     (Engine calendar; not a Brain)
USABLE_INPUT_STATUS = ("PUBLISHED", "DEGRADED")      # STALE / NOT_PUBLISHED / anything else -> UNKNOWN

# Temperature bands (degrees C, lower bound inclusive). Coarse input classes anchored on the cue values that recur in the
# researched literature (10 C carp gate; 15 C movement/run onset; 18 C silver-carp spawn; 21/26/30 C warm-season ranges).
# They are NOT biological optimum thresholds: species rules choose which bands matter and carry their own uncertainty.
TEMP_BANDS = (
    ("LT_10C", float("-inf"), 10.0),
    ("C10_15", 10.0, 15.0),
    ("C15_18", 15.0, 18.0),
    ("C18_21", 18.0, 21.0),
    ("C21_26", 21.0, 26.0),
    ("C26_30", 26.0, 30.0),
    ("GE_30C", 30.0, float("inf")),
)
TEMP_BAND_IDS = tuple(b[0] for b in TEMP_BANDS)

WARM_RISE_MIN_C = 15.0                  # a rise only counts as "warm" at or above this water temperature
TREND_NOISE_F = 1.0                     # |24 h change| below this is STEADY (instrument noise floor, not biology)
CROSSING_THRESHOLDS_C = (15.0, 18.0, 20.0)
CLARITY_BANDS = (("TURBID", 0.0, 1.3), ("MODERATE", 1.3, 3.3), ("CLEAR", 3.3, float("inf")))   # feet; ~0.4 m / ~1 m
STAGE_TRENDS = ("RISING_RAPIDLY", "RISING", "STABLE", "FALLING", "FALLING_RAPIDLY")
DAYPARTS = ("DAY", "TWILIGHT", "NIGHT")

# habitat classes the Biological rules can express (AREA-level features: supplied by Lake/Depth/Vegetation Brains when they
# publish map layers; at lake level they are not evaluable and remain knowledge for Intelligence to apply per area)
HABITAT_CLASSES = (
    "shallowVegetatedHabitat", "floodedVegetation", "backwaterHabitat", "tributaryAccess", "tributaryMouth",
    "tailwaterHabitat", "channelBorder", "deepChannelPool", "openWaterBasin", "woodyCover",
)
DEPTH_CLASSES = ("LT_0_5M", "M0_5_1_5", "M1_5_3", "GT_3M")


def f_to_c(f: float) -> float:
    return round((f - 32.0) * 5.0 / 9.0, 2)


def temp_band(c: float) -> str:
    for bid, lo, hi in TEMP_BANDS:
        if lo <= c < hi:
            return bid
    return UNKNOWN


def clarity_band(ft: float) -> str:
    for bid, lo, hi in CLARITY_BANDS:
        if lo <= ft < hi:
            return bid
    return UNKNOWN


# ---------------------------------------------------------------- registry (the public feature contract)
# availability: PUBLISHED = a specialist Brain publishes the input today; NOT_PUBLISHED = the owner has not published it yet
# (the feature is defined and evidence-backed, and evaluates to UNKNOWN until it is supplied); AREA = per-area map layer.
REGISTRY: dict[str, dict] = {
    "waterTempBand": {"states": TEMP_BAND_IDS, "owner": "water-temp", "inputs": ["waterTemp.currentTempF"], "availability": "PUBLISHED",
                      "meaning": "Coarse class of the current lake water temperature (C, lower bound inclusive)."},
    "temperatureTrend": {"states": ("WARMING", "STEADY", "COOLING"), "owner": "water-temp", "inputs": ["waterTemp.trend24hF"],
                         "availability": "PUBLISHED", "meaning": f"24 h change at or beyond +/-{TREND_NOISE_F} F is warming/cooling."},
    "temperatureCrossing15C": {"states": ("UP_24H", "DOWN_24H", "NONE_24H"), "owner": "water-temp",
                               "inputs": ["waterTemp.currentTempF", "waterTemp.trend24hF"], "availability": "PUBLISHED",
                               "meaning": "The 15 C line was crossed within the last 24 h (only 24 h is knowable from the published trend)."},
    "temperatureCrossing18C": {"states": ("UP_24H", "DOWN_24H", "NONE_24H"), "owner": "water-temp",
                               "inputs": ["waterTemp.currentTempF", "waterTemp.trend24hF"], "availability": "PUBLISHED",
                               "meaning": "The 18 C line was crossed within the last 24 h."},
    "temperatureCrossing20C": {"states": ("UP_24H", "DOWN_24H", "NONE_24H"), "owner": "water-temp",
                               "inputs": ["waterTemp.currentTempF", "waterTemp.trend24hF"], "availability": "PUBLISHED",
                               "meaning": "The 20 C line was crossed within the last 24 h."},
    "stageTrend": {"states": STAGE_TRENDS, "owner": "lake-brain", "inputs": ["lake.trendState"], "availability": "PUBLISHED",
                   "meaning": "Pool/lake level trend over 24 h as classified by the Lake Brain. A PROXY for river/tributary stage: in pool-controlled "
                              "rivers stage and discharge decouple, so rules that cite it carry that caveat."},
    "risingStage": {"states": (TRUE, FALSE), "owner": "lake-brain", "inputs": ["lake.trendState"], "availability": "PUBLISHED",
                    "meaning": "stageTrend is RISING or RISING_RAPIDLY."},
    "fallingStage": {"states": (TRUE, FALSE), "owner": "lake-brain", "inputs": ["lake.trendState"], "availability": "PUBLISHED",
                     "meaning": "stageTrend is FALLING or FALLING_RAPIDLY."},
    "warmRise": {"states": (TRUE, FALSE), "owner": "biological (inputs: lake-brain + water-temp)",
                 "inputs": ["lake.trendState", "waterTemp.currentTempF"], "availability": "PUBLISHED",
                 "meaning": f"risingStage AND water at or above {WARM_RISE_MIN_C:g} C. Evidence: gars and grass carp respond to a rise when the water is warm."},
    "coldRise": {"states": (TRUE, FALSE), "owner": "biological (inputs: lake-brain + water-temp)",
                 "inputs": ["lake.trendState", "waterTemp.currentTempF"], "availability": "PUBLISHED",
                 "meaning": f"risingStage AND water below {WARM_RISE_MIN_C:g} C."},
    "rapidDischargeIncrease": {"states": (TRUE, FALSE), "owner": "lake-brain (tributary hydrology)", "inputs": ["lake.tributaryDischargeTrend"],
                               "availability": "NOT_PUBLISHED",
                               "meaning": "A tributary/inflow discharge increase classified RISING_RAPIDLY. Strongest cross-species signal in the research; "
                                          "no Brain publishes the input yet, so this is always UNKNOWN today."},
    "clarityBand": {"states": tuple(b[0] for b in CLARITY_BANDS), "owner": "water-clarity", "inputs": ["waterClarity.clarityFt"],
                    "availability": "PUBLISHED", "meaning": "Coarse engineering bands (feet), not biological thresholds."},
    "daypart": {"states": DAYPARTS, "owner": "engine-calendar", "inputs": ["calendar.daypart"], "availability": "PUBLISHED",
                "meaning": "Lake-local day / twilight / night."},
    "spawnWindow": {"states": ("IN_WINDOW", "MONTH_ONLY", "TEMP_ONLY", "OUTSIDE"), "owner": "biological (species-evaluated)",
                    "inputs": ["calendar.month", "waterTemp.currentTempF"], "availability": "PUBLISHED",
                    "meaning": "Species-specific. IN_WINDOW: month in the species window AND water within its spawn temperature range."},
}
for _h in HABITAT_CLASSES:
    REGISTRY[_h] = {"states": (TRUE, FALSE), "owner": "lake-brain / depth / vegetation (area-level)", "inputs": ["area map layer"],
                    "availability": "AREA", "meaning": "Per-area habitat class; evaluated by Intelligence against map layers, not at lake level."}


def _values(inputs: dict, slot: str) -> dict | None:
    s = (inputs or {}).get(slot) or {}
    if s.get("status") not in USABLE_INPUT_STATUS:
        return None
    return s.get("values") or {}


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _res(state, reason, degraded=False):
    return {"state": state, "reason": reason, **({"degraded": True} if degraded else {})}


def _degraded(inputs: dict, *slots) -> bool:
    return any(((inputs or {}).get(s) or {}).get("status") == "DEGRADED" for s in slots)


def evaluate_features(inputs: dict, calendar: dict | None = None) -> dict:
    """Evaluate every lake-level feature. `inputs` = {slot: {status, values}}; `calendar` = {month, daypart}."""
    out: dict[str, dict] = {}
    cal = calendar or {}
    wt = _values(inputs, "waterTemp")
    cur_f = _num((wt or {}).get("currentTempF"))
    trend_f = _num((wt or {}).get("trend24hF"))
    cur_c = f_to_c(cur_f) if cur_f is not None else None
    wt_missing = "water temperature not published or stale"

    out["waterTempBand"] = _res(temp_band(cur_c), f"{cur_c:g} C", _degraded(inputs, "waterTemp")) if cur_c is not None else _res(UNKNOWN, wt_missing)
    if trend_f is None:
        out["temperatureTrend"] = _res(UNKNOWN, "24 h temperature trend not published")
    else:
        out["temperatureTrend"] = _res("WARMING" if trend_f >= TREND_NOISE_F else "COOLING" if trend_f <= -TREND_NOISE_F else "STEADY", f"{trend_f:+g} F / 24 h")
    for t in CROSSING_THRESHOLDS_C:
        fid = f"temperatureCrossing{int(t)}C"
        if cur_f is None or trend_f is None:
            out[fid] = _res(UNKNOWN, "needs current temperature and 24 h trend")
            continue
        prev_c = f_to_c(cur_f - trend_f)
        out[fid] = _res("UP_24H" if prev_c < t <= cur_c else "DOWN_24H" if cur_c < t <= prev_c else "NONE_24H", f"{prev_c:g} -> {cur_c:g} C")

    lk = _values(inputs, "lake")
    ts = (lk or {}).get("trendState")
    if ts in STAGE_TRENDS:
        out["stageTrend"] = _res(ts, "Lake Brain trendState", _degraded(inputs, "lake"))
        rising, falling = ts in ("RISING", "RISING_RAPIDLY"), ts in ("FALLING", "FALLING_RAPIDLY")
        out["risingStage"] = _res(TRUE if rising else FALSE, ts)
        out["fallingStage"] = _res(TRUE if falling else FALSE, ts)
    else:
        why = "lake trend not published, stale or UNKNOWN"
        for fid in ("stageTrend", "risingStage", "fallingStage"):
            out[fid] = _res(UNKNOWN, why)

    rs, warm = out["risingStage"]["state"], (None if cur_c is None else cur_c >= WARM_RISE_MIN_C)
    out["warmRise"] = _and3(rs, warm, "rising stage", f"water >= {WARM_RISE_MIN_C:g} C")
    out["coldRise"] = _and3(rs, None if warm is None else (not warm), "rising stage", f"water < {WARM_RISE_MIN_C:g} C")

    dt_ = (lk or {}).get("tributaryDischargeTrend")
    out["rapidDischargeIncrease"] = (_res(TRUE if dt_ == "RISING_RAPIDLY" else FALSE, "tributary discharge trend") if dt_ in STAGE_TRENDS
                                     else _res(UNKNOWN, "no Brain publishes tributary discharge change yet"))

    wc = _values(inputs, "waterClarity")
    ft = _num((wc or {}).get("clarityFt"))
    out["clarityBand"] = _res(clarity_band(ft), f"{ft:g} ft", _degraded(inputs, "waterClarity")) if ft is not None else _res(UNKNOWN, "clarity not published or stale")

    dp = cal.get("daypart")
    out["daypart"] = _res(dp, "calendar") if dp in DAYPARTS else _res(UNKNOWN, "daypart not supplied")
    for h in HABITAT_CLASSES:
        out[h] = _res(UNKNOWN, "area-level habitat class: not evaluable at lake level")
    for fid, fe in out.items():       # a derived feature is degraded when any specialist input it reads is degraded
        slots = {i.split(".")[0] for i in REGISTRY[fid]["inputs"]}
        if fe["state"] != UNKNOWN and any(_degraded(inputs, s) for s in slots):
            fe["degraded"] = True
    return out


def _and3(rising_state: str, cond, left: str, right: str) -> dict:
    """Three-valued AND of (risingStage TRUE) and a boolean condition that may be None (unknown)."""
    if rising_state == FALSE or cond is False:
        return _res(FALSE, f"not ({left} and {right})")
    if rising_state == UNKNOWN or cond is None:
        return _res(UNKNOWN, f"{left if rising_state == UNKNOWN else right} unknown")
    return _res(TRUE, f"{left} and {right}")


def spawn_window(month: int | None, temp_c: float | None, window: dict | None) -> dict:
    """Species-evaluated: window = {months: [...]|None, tempC: {min, max}} (both inclusive). Missing input -> UNKNOWN."""
    if not window:
        return _res(UNKNOWN, "no spawn phenology rule for this species/region")
    months, tr = window.get("months"), window.get("tempC") or {}
    month_ok = None if (month is None) else (True if not months else month in months)
    temp_ok = None
    if temp_c is not None and tr.get("min") is not None and tr.get("max") is not None:
        temp_ok = tr["min"] <= temp_c <= tr["max"]
    if month_ok is None and temp_ok is None:
        return _res(UNKNOWN, "month and temperature unknown")
    if month_ok is not False and temp_ok is not False and None not in (month_ok, temp_ok):
        return _res("IN_WINDOW", "month and temperature both in range")
    if month_ok is None or temp_ok is None:
        known = temp_ok if month_ok is None else month_ok
        if known is False:
            return _res("OUTSIDE", ("temperature" if month_ok is None else "month") + " outside the window (other input unknown)")
        return _res(UNKNOWN, "one input unknown")
    if month_ok and not temp_ok:
        return _res("MONTH_ONLY", "month in window; temperature outside range")
    if temp_ok and not month_ok:
        return _res("TEMP_ONLY", "temperature in range; month outside window")
    return _res("OUTSIDE", "month and temperature both outside")
