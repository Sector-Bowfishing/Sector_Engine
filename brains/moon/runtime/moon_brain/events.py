"""Rise, set and twilight instants: the USNO / Meeus event definitions applied to the sector-moon-v1 ephemeris.

Definitions (Meeus, Astronomical Algorithms 2nd ed., ch. 15; the same standard altitudes USNO's Astronomical Applications
Department uses for its rise/set/twilight tables):

    sunrise / sunset          the Sun's centre at geometric altitude h0 = -0deg50' (-0.8333): 34' refraction + 16' semidiameter
    civil twilight            the Sun's centre at -6 deg
    nautical twilight         the Sun's centre at -12 deg
    astronomical twilight     the Sun's centre at -18 deg
    moonrise / moonset        the Moon's upper limb on the horizon with standard refraction, observer at sea level:
                              geocentric altitude of the centre h0 = 0.7275 * parallax - 0deg34'

Method: sample (altitude - h0) every SCAN_MINUTES, then bisect every sign change to BISECT_SECONDS. Positions are recomputed at
every trial instant (no fixed-day approximation). An event that does not happen in the span (polar day or night, a Moon that
does not rise that day) is simply absent: callers report it as absent, never interpolate one.
"""
from __future__ import annotations

from . import ephemeris as eph

SCAN_MINUTES = 10.0
BISECT_SECONDS = 1.0

SUN_RISE_SET_H0 = -50.0 / 60.0
TWILIGHT_H0 = {"civil": -6.0, "nautical": -12.0, "astronomical": -18.0}
REFRACTION_DEG = 34.0 / 60.0
MOON_PARALLAX_FACTOR = 0.7275


def sun_offset(h0: float):
    return lambda t, lat, lon: eph.sun_altitude(t, lat, lon) - h0


def moon_offset(t: float, lat: float, lon: float) -> float:
    alt, par = eph.moon_geocentric(t, lat, lon)
    return alt - (MOON_PARALLAX_FACTOR * par - REFRACTION_DEG)


def _bisect(f, lat, lon, a, fa, b):
    while b - a > BISECT_SECONDS:
        m = (a + b) / 2.0
        fm = f(m, lat, lon)
        if (fa < 0) == (fm < 0):
            a, fa = m, fm
        else:
            b = m
    return (a + b) / 2.0


def crossings(f, lat: float, lon: float, start: float, end: float) -> list[tuple[float, str]]:
    """Every instant in [start, end) where f crosses zero: [(t, 'rise'|'set')], in time order."""
    step = SCAN_MINUTES * 60.0
    out = []
    t0, f0 = start, f(start, lat, lon)
    while t0 < end:
        t1 = min(t0 + step, end)
        f1 = f(t1, lat, lon)
        if (f0 < 0) != (f1 < 0):
            t = _bisect(f, lat, lon, t0, f0, t1)
            if start <= t < end:
                out.append((t, "rise" if f1 >= 0 else "set"))
        t0, f0 = t1, f1
    return out


def first(events, kind: str, after: float | None = None) -> float | None:
    for t, k in events:
        if k == kind and (after is None or t > after):
            return t
    return None
