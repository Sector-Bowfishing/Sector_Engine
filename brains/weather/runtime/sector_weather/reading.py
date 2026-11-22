"""One lake's current weather from NWS station observations and the NWS forecast grid. Pure.

A port of the Engine adapter's `assemble` (NWSWeatherService.swift) for the four Weather tiles: Sky, Barometric Pressure, Air Temperature and
Humidity. Every value carries `at` (the observation time, or the start of the forecast-grid hour), `origin` (`observation` | `forecastGrid`)
and the station. A value nobody reported is None. Pressure has no forecast fallback: the NWS grid has no pressure layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import contract as C
from .nws import CONDITION, Grid, Obs, floor_hour, qpf_inches, sky_code_pct, weather_code


@dataclass
class Reading:
    now: datetime
    values: dict = field(default_factory=dict)           # tile -> {value, at, origin, station}
    pressure: dict | None = None                         # {hPa, inHg, at, station, kind, seaLevelOffsetHPa, trend3h, trend12h}
    pressure_series: list = field(default_factory=list)  # [(at, raw hPa)] newest first, one station, one quantity (for trends and signals)
    temp_station_obs: list = field(default_factory=list) # the temperature station's observations, newest first (signals)
    newest_obs: Obs | None = None
    grid: Grid | None = None
    stations_used: list = field(default_factory=list)
    observations: dict = field(default_factory=dict)     # station -> [Obs] newest first, as fetched


def _val(value, at, origin, station=None):
    return {"value": value, "at": at, "origin": origin, "station": station}


def tendency(current: float, at: datetime, series: list, hours: int, steady: float) -> dict | None:
    """Signed change from the sample closest to `hours` before `at` (strictly within 90 min), classified with a ± steady band.
    The iOS rule (recentPressureChangeInHg / pressureTrend); None when no sample is near the target (never 'steady/0')."""
    target = at - timedelta(hours=hours)
    if not series:
        return None
    t, v = min(series, key=lambda s: abs((s[0] - target).total_seconds()))
    if abs((t - target).total_seconds()) >= C.TREND_SAMPLE_TOLERANCE_MIN * 60:
        return None
    ch = current - v
    return {"trend": "rising" if ch > steady else ("falling" if ch < -steady else "steady"), "change": ch, "from": t}


def assemble(stations: list[str], observations: dict[str, list[Obs]], grid: Grid | None, now: datetime) -> Reading:
    rd = Reading(now=now, grid=grid, stations_used=list(stations), observations=dict(observations))
    fresh = [(sid, [o for o in observations.get(sid) or []
                    if (now - o.at).total_seconds() <= C.OBSERVATION_MAX_AGE_MIN * 60 and o.at <= now + timedelta(minutes=10)])
             for sid in stations]

    def pick(has):
        newest = None
        for _, obs in fresh:
            o = next((x for x in obs if has(x)), None)
            if o and (now - o.at).total_seconds() <= C.PREFERRED_MAX_AGE_MIN * 60 and (newest is None or o.at > newest.at):
                newest = o
        if newest:
            return newest
        for _, obs in fresh:
            o = next((x for x in obs if has(x)), None)
            if o:
                return o
        return None

    hour = floor_hour(now)

    def grid_val(layer: dict | None, fn=lambda v: v):
        v = (layer or {}).get(hour)
        return None if v is None else _val(fn(v), hour, "forecastGrid")

    t_obs = pick(lambda o: o.temp_f is not None)
    rd.values["airTemperatureF"] = _val(t_obs.temp_f, t_obs.at, "observation", t_obs.station) if t_obs else grid_val(grid and grid.temp_f)
    h_obs = pick(lambda o: o.rh is not None)
    rd.values["humidityPct"] = _val(round(h_obs.rh), h_obs.at, "observation", h_obs.station) if h_obs else grid_val(grid and grid.rh, round)
    d_obs = pick(lambda o: o.dew_f is not None)
    rd.values["dewPointF"] = _val(d_obs.dew_f, d_obs.at, "observation", d_obs.station) if d_obs else grid_val(grid and grid.dew_f)
    if t_obs:
        rd.temp_station_obs = observations.get(t_obs.station) or []

    # Pressure: the newest fresh altimeter setting, reported as sea-level pressure with the station's own SLP - altimeter offset when
    # one exists within 6 h (else labelled `altimeter`). Trends use the raw altimeter series of that ONE station, so the offset never
    # enters a tendency (adapter §3.1).
    p_obs = pick(lambda o: o.alt_hpa is not None)
    kind, offset, raw = None, None, None
    if p_obs:
        rows = [o for o in observations.get(p_obs.station) or [] if o.at <= p_obs.at]
        rd.pressure_series = [(o.at, o.alt_hpa) for o in rows if o.alt_hpa is not None]
        pair = next((o for o in rows if o.slp_hpa is not None and o.alt_hpa is not None
                     and (p_obs.at - o.at).total_seconds() <= C.SLP_OFFSET_MAX_AGE_MIN * 60), None)
        offset = (pair.slp_hpa - pair.alt_hpa) if pair else None
        raw, kind = p_obs.alt_hpa, ("seaLevel" if pair else "altimeter")
        value = p_obs.alt_hpa + (offset or 0.0)
    else:
        p_obs = pick(lambda o: o.slp_hpa is not None)
        if p_obs:
            rows = [o for o in observations.get(p_obs.station) or [] if o.at <= p_obs.at]
            rd.pressure_series = [(o.at, o.slp_hpa) for o in rows if o.slp_hpa is not None]
            raw, kind, value = p_obs.slp_hpa, "seaLevel", p_obs.slp_hpa
    if p_obs:
        t3 = tendency(raw, p_obs.at, rd.pressure_series, 3, C.TREND_3H_STEADY_INHG / C.HPA_TO_INHG)
        t12 = tendency(raw, p_obs.at, rd.pressure_series, 12, C.TREND_12H_STEADY_HPA)
        rd.pressure = {"hPa": value, "inHg": value * C.HPA_TO_INHG, "at": p_obs.at, "station": p_obs.station, "origin": "observation", "kind": kind,
                       "seaLevelOffsetHPa": offset, "trend3h": t3, "trend12h": t12}

    # Sky: total cloud % from the forecast grid's current hour (model total cloud, like the app's Open-Meteo cloud_cover); the observation's
    # cloud layers only when the grid has no hour (ASOS layers stop at 12,000 ft). Present weather only from a fresh observation.
    sky_obs = pick(lambda o: o.icon is not None or o.text is not None)
    cover = grid_val(grid and grid.sky_pct)
    if cover is None:
        l_obs = pick(lambda o: o.layer_pct is not None)
        cover = _val(l_obs.layer_pct, l_obs.at, "observation", l_obs.station) if l_obs else None
    rd.values["cloudCoverPct"] = cover
    # The code is labelled by where it really came from (review of #234): a station's own icon/text is decoded WITHOUT the grid's cloud %, so the
    # value never contradicts what the station reported; only when the station says nothing about the sky does the grid cover give the code, and
    # then it is labelled forecastGrid. (The Engine adapter passes the grid % into the station's code; the Brain deliberately does not.)
    code = None
    c = weather_code(sky_obs.icon, sky_obs.text, None) if sky_obs is not None else None
    if c is not None:
        code = _val(c, sky_obs.at, "observation", sky_obs.station)
    elif cover is not None and cover["origin"] == "forecastGrid":
        code = _val(sky_code_pct(cover["value"]), cover["at"], "forecastGrid")
    rd.values["weatherCode"] = code
    rd.values["nwsText"] = sky_obs.text if sky_obs else None
    rd.newest_obs = max((obs[0] for _, obs in fresh if obs), key=lambda o: o.at, default=None)

    pr_obs = pick(lambda o: o.precip_1h_in is not None)
    rd.values["precipLastHourIn"] = _val(pr_obs.precip_1h_in, pr_obs.at, "observation", pr_obs.station) if pr_obs else None
    return rd


def forecast_rows(grid: Grid | None, now: datetime, hours: int = C.FORECAST_HOURS) -> list[dict]:
    """The next `hours` hours of the NWS forecast grid at the top of each hour (an official forecast, labelled as such)."""
    if grid is None:
        return []
    out = []
    h0 = floor_hour(now)
    for i in range(1, hours + 1):
        h = h0 + timedelta(hours=i)
        row = {"at": C.iso(h), "airTemperatureF": C.r(grid.temp_f.get(h)), "humidityPct": None if grid.rh.get(h) is None else round(grid.rh[h]),
               "dewPointF": C.r(grid.dew_f.get(h)), "cloudCoverPct": None if grid.sky_pct.get(h) is None else round(grid.sky_pct[h]),
               "precipProbabilityPct": None if grid.pop_pct.get(h) is None else round(grid.pop_pct[h])}
        if any(v is not None for k, v in row.items() if k != "at"):
            out.append(row)
    return out


def describe_code(code: int | None) -> str | None:
    return None if code is None else CONDITION.get(code, "—")


def qpf(grid: Grid | None, now: datetime, hours: float):
    return qpf_inches(grid, now, hours)
