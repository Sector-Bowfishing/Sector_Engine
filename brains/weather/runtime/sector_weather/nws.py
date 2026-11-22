"""National Weather Service (api.weather.gov) decoding for the Weather Brain. Pure: bytes/dicts in, values out; no I/O.

The meaning rules are the Engine's NWS weather adapter (NWS_WEATHER_ADAPTER_V1.md,
Sources/SectorEngine/Fetchers/NWSWeatherService.swift), ported value for value so the Brain and the Engine read NWS the same way:
  * units are converted only from a known WMO unit code; an unknown unit gives None (never a guess);
  * QC flags X (rejected) and B (bad) drop the value;
  * the icon -> WMO weather code map is the adapter's NWSCondition table, so the sky wording is WeatherService.condition(forCode:).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

UNITS = {
    ("F", "degC"): lambda v: v * 9 / 5 + 32, ("F", "degF"): lambda v: v,
    ("pct", "percent"): lambda v: v,
    ("mph", "km_h-1"): lambda v: v / 1.609344, ("mph", "m_s-1"): lambda v: v * 3600 / 1609.344,
    ("mph", "kt"): lambda v: v * 1.150779, ("mph", "knot"): lambda v: v * 1.150779,
    ("deg", "degree_(angle)"): lambda v: v,
    ("hPa", "Pa"): lambda v: v / 100, ("hPa", "hPa"): lambda v: v,
    ("in", "mm"): lambda v: v / 25.4, ("in", "m"): lambda v: v / 0.0254,
}
REJECTED_QC = ("X", "B")


def convert(value, unit_code: str | None, target: str):
    if value is None or isinstance(value, bool):
        return None
    u = (unit_code or "").replace("wmoUnit:", "").replace("unit:", "")
    f = UNITS.get((target, u))
    return None if f is None else f(float(value))


def quantity(q: dict | None, target: str):
    """A NWS quantity {unitCode, value, qualityControl} -> float in `target` units, or None."""
    if not isinstance(q, dict):
        return None
    if str(q.get("qualityControl") or "").upper() in REJECTED_QC:
        return None
    return convert(q.get("value"), q.get("unitCode"), target)


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def parse_valid_time(s: str) -> tuple[datetime, int] | None:
    """'2026-11-06T14:00:00+00:00/PT2H' -> (start, whole hours). ISO 8601 P[nD][T[nH][nM]]; a sub-hour remainder is dropped."""
    parts = s.split("/", 1)
    if len(parts) != 2:
        return None
    start = parse_time(parts[0])
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", parts[1])
    if start is None or m is None:
        return None
    total = int(m.group(1) or 0) * 24 + int(m.group(2) or 0) + int(m.group(3) or 0) // 60
    return (start, total) if total > 0 else None


def floor_hour(t: datetime) -> datetime:
    return t.replace(minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------------------------------------- /points + stations
@dataclass(frozen=True)
class Point:
    grid_id: str
    grid_x: int
    grid_y: int
    forecast_grid_data: str
    observation_stations: str

    @property
    def gridpoint(self) -> str:
        return f"{self.grid_id}/{self.grid_x},{self.grid_y}"


def decode_point(doc: dict) -> Point | None:
    p = (doc or {}).get("properties") or {}
    try:
        return Point(str(p["gridId"]), int(p["gridX"]), int(p["gridY"]), str(p["forecastGridData"]), str(p["observationStations"]))
    except (KeyError, TypeError, ValueError):
        return None


def decode_stations(doc: dict) -> list[dict]:
    """Stations in NWS's order (nearest first): [{id, name, lon, lat}]."""
    out = []
    for f in (doc or {}).get("features") or []:
        p = f.get("properties") or {}
        sid = p.get("stationIdentifier")
        if not sid:
            continue
        c = ((f.get("geometry") or {}).get("coordinates") or [None, None])
        out.append({"id": sid, "name": p.get("name"), "lon": c[0], "lat": c[1]})
    return out


# ---------------------------------------------------------------------------------------------------------- observations
LAYER_PCT = {"SKC": 0.0, "CLR": 0.0, "NCD": 0.0, "NSC": 0.0, "FEW": 18.75, "SCT": 43.75, "BKN": 75.0, "OVC": 100.0, "VV": 100.0}


@dataclass
class Obs:
    station: str
    at: datetime
    text: str | None = None
    icon: str | None = None
    temp_f: float | None = None
    dew_f: float | None = None
    rh: float | None = None
    wind_mph: float | None = None
    wind_dir: float | None = None
    slp_hpa: float | None = None
    alt_hpa: float | None = None
    precip_1h_in: float | None = None
    layer_pct: float | None = None


def decode_observations(doc: dict) -> list[Obs]:
    """Observations newest first; rows without a parseable timestamp are dropped."""
    rows = []
    for f in (doc or {}).get("features") or []:
        p = f.get("properties") or {}
        at = parse_time(p.get("timestamp"))
        if at is None:
            continue
        layers = [LAYER_PCT.get(str(l.get("amount") or "").upper()) for l in (p.get("cloudLayers") or []) if isinstance(l, dict)]
        layers = [x for x in layers if x is not None]
        rows.append(Obs(
            station=str(p.get("station") or "").rsplit("/", 1)[-1], at=at, text=p.get("textDescription") or None, icon=p.get("icon") or None,
            temp_f=quantity(p.get("temperature"), "F"), dew_f=quantity(p.get("dewpoint"), "F"), rh=quantity(p.get("relativeHumidity"), "pct"),
            wind_mph=quantity(p.get("windSpeed"), "mph"), wind_dir=quantity(p.get("windDirection"), "deg"),
            slp_hpa=quantity(p.get("seaLevelPressure"), "hPa"), alt_hpa=quantity(p.get("barometricPressure"), "hPa"),
            precip_1h_in=quantity(p.get("precipitationLastHour"), "in"), layer_pct=max(layers) if layers else None))
    rows.sort(key=lambda o: o.at, reverse=True)
    return rows


# ---------------------------------------------------------------------------------------------------------- gridpoint forecast
@dataclass
class Grid:
    update_time: datetime | None = None
    temp_f: dict = field(default_factory=dict)          # hour -> value (a multi-hour period is the same value in every hour it covers)
    dew_f: dict = field(default_factory=dict)
    rh: dict = field(default_factory=dict)
    sky_pct: dict = field(default_factory=dict)
    pop_pct: dict = field(default_factory=dict)
    qpf: list = field(default_factory=list)              # [(start, hours, inches)] as issued: an accumulation, never split into rates

    def has_pressure(self) -> bool:
        return False                                      # NDFD carries no usable pressure layer (adapter §4): the forecast half stays null


def decode_grid(doc: dict) -> Grid | None:
    props = (doc or {}).get("properties")
    if not isinstance(props, dict):
        return None

    def hourly(key, target):
        layer = props.get(key)
        out = {}
        if not isinstance(layer, dict):
            return out
        for v in layer.get("values") or []:
            val = convert(v.get("value"), layer.get("uom"), target)
            vt = parse_valid_time(str(v.get("validTime") or ""))
            if val is None or vt is None:
                continue
            start, hours = vt
            for h in range(hours):
                out[start + timedelta(hours=h)] = val
        return out

    g = Grid(update_time=parse_time(props.get("updateTime")), temp_f=hourly("temperature", "F"), dew_f=hourly("dewpoint", "F"),
             rh=hourly("relativeHumidity", "pct"), sky_pct=hourly("skyCover", "pct"), pop_pct=hourly("probabilityOfPrecipitation", "pct"))
    layer = props.get("quantitativePrecipitation")
    if isinstance(layer, dict):
        for v in layer.get("values") or []:
            amt = convert(v.get("value"), layer.get("uom"), "in")
            vt = parse_valid_time(str(v.get("validTime") or ""))
            if amt is not None and amt >= 0 and vt is not None:
                g.qpf.append((vt[0], vt[1], amt))
    return g


def qpf_inches(g: Grid | None, now: datetime, hours: float) -> float | None:
    """Forecast liquid precipitation over [now, now + hours]. A period that only partly overlaps counts in proportion to the overlap (the
    Lake Brain's LakeRainSignal rule). None when the layer covers none of the window."""
    if g is None:
        return None
    end, total, covered = now + timedelta(hours=hours), 0.0, False
    for start, h, amt in g.qpf:
        stop = start + timedelta(hours=h)
        overlap = (min(stop, end) - max(start, now)).total_seconds()
        if overlap > 0:
            covered = True
            total += amt * overlap / (h * 3600)
    return round(total, 2) if covered else None


# ---------------------------------------------------------------------------------------------------------- icon/text -> WMO code
def icon_name(url: str | None) -> str | None:
    if not url:
        return None
    comps = url.split("?", 1)[0].split("/")
    for i, c in enumerate(comps):
        if c in ("day", "night") and i + 1 < len(comps):
            name = comps[i + 1].split(",", 1)[0]
            return name or None
    return None


def _intensity(text: str | None) -> str:
    t = (text or "").lower()
    if t.startswith("light") or " light " in t:
        return "light"
    if t.startswith("heavy") or " heavy " in t:
        return "heavy"
    return "moderate"


def _pick(i, light, moderate, heavy):
    return {"light": light, "moderate": moderate, "heavy": heavy}[i]


def sky_code_pct(p: float) -> int:
    """NWS octa categories: clear < 1/8, mostly clear < 3/8, partly/mostly cloudy < 7/8, overcast >= 7/8."""
    return 0 if p < 12.5 else 1 if p < 37.5 else 2 if p < 87.5 else 3


def sky_code_icon(icon: str) -> int | None:
    return {"skc": 0, "few": 1, "sct": 2, "bkn": 2, "ovc": 3}.get(icon.replace("wind_", ""))


def phenomenon_code(icon: str, text: str | None) -> int | None:
    t, i = (text or "").lower(), _intensity(text)
    if icon == "fog":
        return 45
    if icon == "rain":
        if "freezing drizzle" in t:
            return _pick(i, 56, 56, 57)
        if "drizzle" in t and "rain" not in t:
            return _pick(i, 51, 53, 55)
        return _pick(i, 61, 63, 65)
    if icon in ("rain_showers", "rain_showers_hi"):
        return _pick(i, 80, 81, 82)
    if icon in ("fzra", "rain_fzra", "snow_fzra", "sleet", "rain_sleet"):
        return _pick(i, 66, 66, 67)
    if icon in ("snow", "rain_snow", "snow_sleet"):
        if "snow shower" in t:
            return 86 if i == "heavy" else 85
        return _pick(i, 71, 73, 75)
    if icon == "blizzard":
        return 75
    if icon in ("tsra", "tsra_sct", "tsra_hi", "tornado", "hurricane", "tropical_storm"):
        return 96 if "hail" in t else 95
    return None


def phenomenon_code_text(text: str) -> int | None:
    t = text.lower()
    if "thunder" in t or "tornado" in t or "funnel" in t:
        return phenomenon_code("tsra", text)
    if "freezing rain" in t or "sleet" in t or "ice pellets" in t:
        return phenomenon_code("fzra", text)
    if "snow" in t:
        return phenomenon_code("snow", text)
    if "shower" in t:
        return phenomenon_code("rain_showers", text)
    if "rain" in t or "drizzle" in t:
        return phenomenon_code("rain", text)
    if "fog" in t:
        return 45
    return None


def sky_code_text(text: str) -> int | None:
    t = text.lower()
    if "mostly cloudy" in t or "partly cloudy" in t or "partly sunny" in t:
        return 2
    if "mostly clear" in t or "mostly sunny" in t or "fair" in t:
        return 1
    if "cloudy" in t or "overcast" in t:
        return 3
    if "clear" in t or "sunny" in t:
        return 0
    return None


def weather_code(icon: str | None, text: str | None, sky_pct: float | None) -> int | None:
    """A weather phenomenon from the icon (or the text) wins; otherwise the sky code from the total cloud % when known, else from icon/text."""
    name = icon_name(icon)
    if name:
        c = phenomenon_code(name.replace("wind_", ""), text)
        if c is not None:
            return c
    if name is None and text:
        c = phenomenon_code_text(text)
        if c is not None:
            return c
    if sky_pct is not None:
        return sky_code_pct(sky_pct)
    if name:
        c = sky_code_icon(name)
        if c is not None:
            return c
    return sky_code_text(text) if text else None


#: WeatherService.condition(forCode:) labels (the iOS app and the Engine use this exact table).
CONDITION = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
             56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Rain", 63: "Rain", 65: "Rain", 66: "Freezing rain", 67: "Freezing rain",
             71: "Snow", 73: "Snow", 75: "Snow", 77: "Snow", 80: "Rain showers", 81: "Rain showers", 82: "Rain showers", 85: "Snow showers",
             86: "Snow showers", 95: "Thunderstorm", 96: "Thunderstorm, hail", 99: "Thunderstorm, hail"}

#: WMO codes that mean something is falling (drizzle/rain/snow/showers/storm): the rain-onset rule's "precipitation present".
PRECIP_CODES = frozenset(c for c in CONDITION if c >= 51)
