"""The weather-change signal: is the weather at this lake changing now, or about to? Pure; thresholds from contract.THRESHOLDS (pre-stated).

Output (state field `weatherChange`, contract weather-state-v1 §4):
  level     CHANGE  at least one OBSERVED event (pressure fast, air-temperature swing, front passage, rain onset)
            WATCH   no observed event, but rain is forecast (RAIN_EXPECTED) or an input needed to rule a change out is unknown
            STEADY  every rule was evaluated on measured data and none fired, and no rain is forecast
  events    [{kind, basis OBSERVED|FORECAST, value, threshold, unit, at}]
  unknown   the rules that could not be evaluated, and why (unknown never counts as "no change")
  signature changes whenever the level, the event kinds or the observation they rest on change; consumers refresh when it differs
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from . import contract as C
from .nws import PRECIP_CODES, weather_code
from .reading import Reading, qpf

T = C.THRESHOLDS


def _near(series, target, tol_min=C.TREND_SAMPLE_TOLERANCE_MIN):
    """(at, value) closest to `target`, strictly within the tolerance, else None (the trend rule)."""
    if not series:
        return None
    s = min(series, key=lambda x: abs((x[0] - target).total_seconds()))
    return s if abs((s[0] - target).total_seconds()) < tol_min * 60 else None


def _raining(o) -> bool:
    code = weather_code(o.icon, o.text, None) if (o.icon or o.text) else None
    return (code in PRECIP_CODES) or (o.precip_1h_in is not None and o.precip_1h_in >= T["measurablePrecipIn"])


def _ang(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def evaluate(rd: Reading) -> dict:
    now, win = rd.now, timedelta(hours=T["windowHours"])
    events, unknown, inputs = [], [], {}

    def ev(kind, basis, value, threshold, unit, at):
        events.append({"kind": kind, "basis": basis, "value": C.r(value, 3), "threshold": threshold, "unit": unit, "at": C.iso(at)})

    # 1. pressure tendency (3 h, one station, raw series)
    p = rd.pressure
    t3 = (p or {}).get("trend3h")
    if t3 is None:
        unknown.append("pressure3h: no fresh pressure observation with a sample 3 h earlier")
    else:
        d = t3["change"] * C.HPA_TO_INHG
        inputs["pressureChange3hInHg"] = round(d, 3)
        if d <= -T["pressureFastInHgPer3h"]:
            ev("PRESSURE_FALLING_FAST", "OBSERVED", d, -T["pressureFastInHgPer3h"], "inHg/3h", p["at"])
        elif d >= T["pressureFastInHgPer3h"]:
            ev("PRESSURE_RISING_FAST", "OBSERVED", d, T["pressureFastInHgPer3h"], "inHg/3h", p["at"])

    # 2. air-temperature swing (3 h, the temperature station)
    obs = rd.temp_station_obs
    newest_t = next((o for o in obs if o.temp_f is not None), None)
    fresh_t = newest_t if newest_t and (now - newest_t.at).total_seconds() <= C.OBSERVATION_MAX_AGE_MIN * 60 else None
    t_series = [(o.at, o.temp_f) for o in obs if o.temp_f is not None]
    past_t = _near(t_series, fresh_t.at - win) if fresh_t else None
    if past_t is None:
        unknown.append("airTemp3h: no fresh air-temperature observation with a sample 3 h earlier")
    else:
        dt_f = fresh_t.temp_f - past_t[1]
        inputs["airTempChange3hF"] = round(dt_f, 1)
        if abs(dt_f) >= T["airTempSwingFPer3h"]:
            ev("AIR_TEMP_SWING", "OBSERVED", dt_f, T["airTempSwingFPer3h"], "degF/3h", fresh_t.at)

    # 3. front passage: a wind turn of >= 90 deg (both ends >= 5 mph) AND a pressure trough, or a >= 5 F temperature or dew point drop
    if fresh_t is None:
        unknown.append("front: no fresh observation at the temperature station")
    else:
        windy = [(o.at, o) for o in obs if o.wind_mph is not None and o.wind_dir is not None and o.wind_mph >= T["frontWindMinMph"]
                 and fresh_t.at - win <= o.at <= fresh_t.at]
        end = windy[0][1] if windy else None
        start = _near(windy, fresh_t.at - win)
        turn = _ang(end.wind_dir, start[1].wind_dir) if end and start and end is not start[1] else None
        inputs["windTurn3hDeg"] = None if turn is None else round(turn)
        support = []
        seg = [(t, v) for t, v in rd.pressure_series if p and p["at"] - win <= t <= p["at"]]
        if len(seg) >= 3:
            lo_t, lo_v = min(seg, key=lambda s: s[1])
            first, last = seg[-1][1], seg[0][1]                              # series is newest first
            fall, rise = (first - lo_v) * C.HPA_TO_INHG, (last - lo_v) * C.HPA_TO_INHG
            if fall >= T["frontTroughInHg"] and rise >= T["frontTroughInHg"]:
                support.append(f"pressure trough at {C.iso(lo_t)}")
        if past_t is not None and past_t[1] - fresh_t.temp_f >= T["frontDropF"]:
            support.append(f"air temperature fell {past_t[1] - fresh_t.temp_f:.1f} F")
        d_series = [(o.at, o.dew_f) for o in obs if o.dew_f is not None]
        d_new = next((o for o in obs if o.dew_f is not None and o.at == fresh_t.at), None)
        d_past = _near(d_series, fresh_t.at - win) if d_new else None
        if d_new and d_past and d_past[1] - d_new.dew_f >= T["frontDropF"]:
            support.append(f"dew point fell {d_past[1] - d_new.dew_f:.1f} F")
        if turn is None:
            unknown.append("front: no pair of sustained-wind observations 3 h apart")
        elif turn >= T["frontWindShiftDeg"] and support:
            ev("FRONT_PASSAGE", "OBSERVED", turn, T["frontWindShiftDeg"], "deg", fresh_t.at)
            events[-1]["support"] = support

    # 4. rain onset (observed) and 5. rain expected (forecast)
    newest = rd.newest_obs
    raining_now = None
    if newest is None or (now - newest.at).total_seconds() > C.PREFERRED_MAX_AGE_MIN * 60:
        unknown.append("rainOnset: no observation in the last 75 min")
    else:
        raining_now = _raining(newest)
        prior = [o for o in rd.observations.get(newest.station) or []
                 if newest.at - timedelta(hours=T["rainOnsetDryLookbackHours"]) <= o.at <= newest.at - timedelta(minutes=60)]
        if raining_now:
            if not prior:
                unknown.append("rainOnset: raining now, but no observation in the preceding 3 h to show it was dry")
            elif not any(_raining(o) for o in prior):
                ev("RAIN_ONSET", "OBSERVED", newest.precip_1h_in or 0.0, T["measurablePrecipIn"], "in", newest.at)
                events[-1]["support"] = [newest.text or "precipitation reported"]
    q = qpf(rd.grid, now, T["rainExpectedHours"])
    inputs["forecastRainNext6hIn"] = q
    if q is None:
        unknown.append("rainExpected: the forecast grid has no precipitation for the next 6 h")
    elif q >= T["rainExpectedIn"] and not raining_now:
        ev("RAIN_EXPECTED", "FORECAST", q, T["rainExpectedIn"], "in/6h", rd.grid.update_time or now)

    observed = [e for e in events if e["basis"] == "OBSERVED"]
    critical_unknown = [u for u in unknown if u.split(":")[0] in ("pressure3h", "airTemp3h")]
    level = "CHANGE" if observed else ("WATCH" if (events or critical_unknown) else "STEADY")
    basis_at = C.iso(newest.at) if newest else None
    sig_src = "|".join([level, ",".join(sorted(e["kind"] for e in events)), basis_at or "-"])
    return {"level": level, "events": events, "unknown": unknown, "inputs": inputs, "evaluatedAt": C.iso(now), "basisObservationAt": basis_at,
            "thresholdsVersion": C.THRESHOLDS_VERSION, "signature": hashlib.sha256(sig_src.encode()).hexdigest()[:16]}

