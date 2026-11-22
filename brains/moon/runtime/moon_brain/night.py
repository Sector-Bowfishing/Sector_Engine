"""Tonight's sky for one place: sun events, twilight, moon events, moonlight across the fishing window.

"Tonight" for a calendar date D is the night that starts on the evening of D at the lake. The Brain has no time-zone table, so
the night is anchored on LOCAL SOLAR NOON: span = [D 12:00 UTC - lon/15 h, +24 h). Every event is searched inside that span
and returned as a UTC instant; the client renders it in the lake's own zone. A noon-to-noon span holds exactly one evening and
the following morning at every longitude, which a UTC (or civil) calendar day does not.

The fishing window mirrors the Engine and the iOS app (ConditionsInputBuilder, docs: specs/conditions-engine.md "the night
window runs into TOMORROW"): start = end of astronomical twilight, else sunset + 80 min; end = the next sunrise, else start
+ 8 h. Moonlight across it is the Engine's moonAltitudeFraction: the mean of max(0, sin(topocentric altitude)) sampled
every 15 min, end inclusive.
"""
from __future__ import annotations

import datetime as dt
import math

from . import ephemeris as eph
from . import events as ev

WINDOW_SAMPLE_MINUTES = 15.0
SUNSET_FALLBACK_MINUTES = 80.0
WINDOW_FALLBACK_HOURS = 8.0


def iso(t: float | None) -> str | None:
    if t is None:
        return None
    return dt.datetime.fromtimestamp(round(t), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evening_date(lat: float, lon: float, now: dt.datetime) -> dt.date:
    """The default "tonight" for a lake: the evening date D of the night that has not yet ended at `now`. Take the night whose span (local
    solar noon of D to local solar noon of D+1) contains `now`; if that night's sunrise has already passed (morning, before local solar noon),
    tonight is the coming evening, D+1. With no sunrise in the span (polar day or night) the span's own date stands."""
    t = now.astimezone(dt.timezone.utc)
    d = (t + dt.timedelta(hours=lon / 15.0 - 12.0)).date()
    s0, s1 = span_for(d, lon)
    rs = ev.crossings(ev.sun_offset(ev.SUN_RISE_SET_H0), lat, lon, s0, s1)
    sunrise = ev.first(rs, "rise", after=ev.first(rs, "set"))
    return d + dt.timedelta(days=1) if sunrise is not None and t.timestamp() >= sunrise else d


def span_for(date: dt.date, lon: float) -> tuple[float, float]:
    noon = dt.datetime(date.year, date.month, date.day, 12, tzinfo=dt.timezone.utc).timestamp() - (lon / 15.0) * 3600.0
    return noon, noon + 86400.0


def _sun_state(lat: float, lon: float, start: float, end: float, h0: float) -> str | None:
    """None when the Sun crosses h0 in the span; otherwise ALWAYS_ABOVE or ALWAYS_BELOW (polar day / polar night)."""
    if ev.crossings(ev.sun_offset(h0), lat, lon, start, end):
        return None
    return "ALWAYS_ABOVE" if eph.sun_altitude(start, lat, lon) > h0 else "ALWAYS_BELOW"


def sun_block(lat: float, lon: float, start: float, end: float) -> tuple[dict, dict]:
    out = {}
    rs = ev.crossings(ev.sun_offset(ev.SUN_RISE_SET_H0), lat, lon, start, end)
    sunset = ev.first(rs, "set")
    sunrise = ev.first(rs, "rise", after=sunset) if sunset is not None else ev.first(rs, "rise")
    out["sunset"] = iso(sunset)
    out["sunrise"] = iso(sunrise)
    out["sunState"] = _sun_state(lat, lon, start, end, ev.SUN_RISE_SET_H0)
    raw = {"sunset": sunset, "sunrise": sunrise}
    tw = {}
    for name, h0 in ev.TWILIGHT_H0.items():
        cr = ev.crossings(ev.sun_offset(h0), lat, lon, start, end)
        dusk = ev.first(cr, "set")
        dawn = ev.first(cr, "rise", after=dusk) if dusk is not None else ev.first(cr, "rise")
        tw[name] = {"dusk": iso(dusk), "dawn": iso(dawn), "sunState": _sun_state(lat, lon, start, end, h0)}
        raw[name + "Dusk"], raw[name + "Dawn"] = dusk, dawn
    out["twilight"] = tw
    return out, raw


def moon_events(lat: float, lon: float, start: float, end: float) -> dict:
    cr = ev.crossings(ev.moon_offset, lat, lon, start, end)
    return {
        "moonrise": iso(ev.first(cr, "rise")),
        "moonset": iso(ev.first(cr, "set")),
        "events": [{"at": iso(t), "event": k} for t, k in cr],
        "upAtSpanStart": ev.moon_offset(start, lat, lon) >= 0,
    }


def fishing_window(raw: dict, span_start: float, span_end: float, sun_state: str | None) -> dict:
    """{start, end, basis} or {start: None, basis: NO_NIGHT} when the Sun never sets in the span."""
    if sun_state == "ALWAYS_ABOVE":
        return {"start": None, "end": None, "basis": "NO_NIGHT_SUN_ALWAYS_UP"}
    if sun_state == "ALWAYS_BELOW":
        return {"start": span_start, "end": span_end, "basis": "POLAR_NIGHT_WHOLE_SPAN"}
    if raw.get("astronomicalDusk") is not None:
        start, basis = raw["astronomicalDusk"], "ASTRONOMICAL_DUSK_TO_SUNRISE"
    elif raw.get("sunset") is not None:
        start, basis = raw["sunset"] + SUNSET_FALLBACK_MINUTES * 60.0, "SUNSET_PLUS_80_MIN_TO_SUNRISE"
    else:
        return {"start": None, "end": None, "basis": "NO_NIGHT_SUN_ALWAYS_UP"}
    end = raw.get("sunrise")
    if end is None or end <= start:
        end = start + WINDOW_FALLBACK_HOURS * 3600.0
        basis += "_FALLBACK_8H"
    return {"start": start, "end": end, "basis": basis}


def moonlight(lat: float, lon: float, start: float, end: float) -> dict:
    step = WINDOW_SAMPLE_MINUTES * 60.0
    t, n, s, up, peak = start, 0, 0.0, 0, -90.0
    while t <= end + 1e-6:
        alt = eph.moon_altitude(t, lat, lon)
        s += max(0.0, math.sin(math.radians(alt)))
        up += 1 if alt > 0 else 0
        peak = max(peak, alt)
        n += 1
        t += step
    return {"presence": round(min(1.0, s / n), 4), "upFraction": round(up / n, 4), "maxAltitudeDeg": round(peak, 2),
            "samples": n}


def tonight(lat: float, lon: float, date: dt.date) -> dict:
    """Everything astronomical about tonight at (lat, lon). No weather: see darkness.py for the on-water class."""
    s0, s1 = span_for(date, lon)
    sun, raw = sun_block(lat, lon, s0, s1)
    window = fishing_window(raw, s0, s1, sun["sunState"])
    mid = s0 + 43200.0          # local solar midnight: the instant the phase and illumination describe
    moon = {
        "phaseName": eph.moon_phase_name(mid),
        "phaseFraction": round(eph.moon_phase_fraction(mid), 6),
        "waxing": eph.moon_waxing(mid),
        "illumination": round(eph.moon_illumination(mid), 4),
        "illuminationAt": iso(mid),
        **moon_events(lat, lon, s0, s1),
    }
    out = {"date": date.isoformat(), "span": {"start": iso(s0), "end": iso(s1), "anchor": "LOCAL_SOLAR_NOON"},
           "sun": sun, "moon": moon,
           "window": {"start": iso(window["start"]), "end": iso(window["end"]), "basis": window["basis"]}}
    if window["start"] is not None:
        out["window"]["moonlight"] = moonlight(lat, lon, window["start"], window["end"])
    return out
