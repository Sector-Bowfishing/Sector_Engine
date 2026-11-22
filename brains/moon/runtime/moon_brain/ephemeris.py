"""Sun and Moon positions: the shared Sector moon spec (contracts/moon/moon-v1.json, specId sector-moon-v1).

This is a line-for-line port of the reference implementation, Sources/SectorEngine/Engine/Astronomy.swift (Paul Schlyter,
"How to compute planetary positions": low precision, about 1-2 arcmin for the Moon). It is NOT a second algorithm: the
illumination, phase fraction and phase name must pass the same 52 vectors the Engine, iOS, Android and Web pass
(tests/test_moon_spec_vectors.py). Keep it in step with Astronomy.swift; change the spec, not one copy.

The only addition is the altitude of the Sun, and the Moon's geocentric altitude and horizontal parallax, which the event
finder (events.py) needs to apply the USNO / Meeus rise-set definitions. Sidereal time uses the IAU 1982 GMST expression
(Meeus, Astronomical Algorithms 2nd ed., eq. 12.4); it differs from Schlyter's L+180 by about 1 s of time.

Pure, stdlib only. Angles in degrees unless a name says rad. Times are POSIX seconds (UTC).
"""
from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass

SYNODIC_DAYS = 29.530588853
KNOWN_NEW_MOON_EPOCH = 947182440          # 2000-01-06 18:14 UTC (moon-v1 phaseFraction)
_J2000_POSIX = 946728000.0                # 2000-01-01 12:00:00 UTC = JD 2451545.0


def sind(d): return math.sin(math.radians(d))
def cosd(d): return math.cos(math.radians(d))
def asind(x): return math.degrees(math.asin(max(-1.0, min(1.0, x))))
def acosd(x): return math.degrees(math.acos(max(-1.0, min(1.0, x))))
def atan2d(y, x): return math.degrees(math.atan2(y, x))


def rev360(x: float) -> float:
    r = math.fmod(x, 360.0)
    return r + 360.0 if r < 0 else r


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


@dataclass(frozen=True)
class Body:
    ra: float          # right ascension, degrees
    dec: float         # declination, degrees
    lon: float         # ecliptic longitude, degrees
    lat: float         # ecliptic latitude, degrees
    distance: float    # Sun: AU; Moon: Earth radii


def day_number(t: float) -> float:
    """Schlyter's day number d at the instant t (epoch 2000 Jan 0.0 UT), built exactly as Astronomy.swift dayContext does:
    the integer formula on the UTC calendar date plus the UT fraction."""
    days, sec = divmod(t, 86400.0)
    date = _dt.date(1970, 1, 1) + _dt.timedelta(days=int(days))
    y, m, day = date.year, date.month, date.day
    d_int = 367 * y - (7 * (y + ((m + 9) // 12))) // 4 + (275 * m) // 9 + day - 730530
    return float(d_int) + (sec / 3600.0) / 24.0


def sun_coords(d: float) -> Body:
    w = 282.9404 + 4.70935e-5 * d
    e = 0.016709 - 1.151e-9 * d
    M = rev360(356.0470 + 0.9856002585 * d)
    oblecl = 23.4393 - 3.563e-7 * d
    E = M + (180 / math.pi) * e * sind(M) * (1 + e * cosd(M))
    x = cosd(E) - e
    y = sind(E) * math.sqrt(1 - e * e)
    r = math.sqrt(x * x + y * y)
    v = atan2d(y, x)
    lon = rev360(v + w)
    xs, ys = r * cosd(lon), r * sind(lon)
    xe, ye, ze = xs, ys * cosd(oblecl), ys * sind(oblecl)
    ra = rev360(atan2d(ye, xe))
    dec = atan2d(ze, math.sqrt(xe * xe + ye * ye))
    return Body(ra=ra, dec=dec, lon=lon, lat=0.0, distance=r)


def moon_coords(d: float) -> Body:
    oblecl = 23.4393 - 3.563e-7 * d
    N = rev360(125.1228 - 0.0529538083 * d)
    i = 5.1454
    w = rev360(318.0634 + 0.1643573223 * d)
    a = 60.2666
    e = 0.054900
    M = rev360(115.3654 + 13.0649929509 * d)
    E = M + (180 / math.pi) * e * sind(M) * (1 + e * cosd(M))
    for _ in range(2):
        E = E - (E - (180 / math.pi) * e * sind(E) - M) / (1 - e * cosd(E))
    x = a * (cosd(E) - e)
    y = a * math.sqrt(1 - e * e) * sind(E)
    r0 = math.sqrt(x * x + y * y)
    v = atan2d(y, x)
    xeclip = r0 * (cosd(N) * cosd(v + w) - sind(N) * sind(v + w) * cosd(i))
    yeclip = r0 * (sind(N) * cosd(v + w) + cosd(N) * sind(v + w) * cosd(i))
    zeclip = r0 * (sind(v + w) * sind(i))
    lon = rev360(atan2d(yeclip, xeclip))
    lat = atan2d(zeclip, math.sqrt(xeclip * xeclip + yeclip * yeclip))
    r = r0

    sun = sun_coords(d)
    Ms = rev360(356.0470 + 0.9856002585 * d)
    Mm = M
    Lm = rev360(N + w + M)
    Ls = sun.lon
    D = rev360(Lm - Ls)
    F = rev360(Lm - N)

    lon += -1.274 * sind(Mm - 2 * D)
    lon += 0.658 * sind(2 * D)
    lon += -0.186 * sind(Ms)
    lon += -0.059 * sind(2 * Mm - 2 * D)
    lon += -0.057 * sind(Mm - 2 * D + Ms)
    lon += 0.053 * sind(Mm + 2 * D)
    lon += 0.046 * sind(2 * D - Ms)
    lon += 0.041 * sind(Mm - Ms)
    lon += -0.035 * sind(D)
    lon += -0.031 * sind(Mm + Ms)
    lon += -0.015 * sind(2 * F - 2 * D)
    lon += 0.011 * sind(Mm - 4 * D)

    lat += -0.173 * sind(F - 2 * D)
    lat += -0.055 * sind(Mm - F - 2 * D)
    lat += -0.046 * sind(Mm + F - 2 * D)
    lat += 0.033 * sind(F + 2 * D)
    lat += 0.017 * sind(2 * Mm + F)

    r += -0.58 * cosd(Mm - 2 * D)
    r += -0.46 * cosd(2 * D)

    xeclip = r * cosd(lon) * cosd(lat)
    yeclip = r * sind(lon) * cosd(lat)
    zeclip = r * sind(lat)
    xe = xeclip
    ye = yeclip * cosd(oblecl) - zeclip * sind(oblecl)
    ze = yeclip * sind(oblecl) + zeclip * cosd(oblecl)
    ra = rev360(atan2d(ye, xe))
    dec = atan2d(ze, math.sqrt(xe * xe + ye * ye))
    dist = math.sqrt(xe * xe + ye * ye + ze * ze)
    return Body(ra=ra, dec=dec, lon=rev360(lon), lat=lat, distance=dist)


# ------------------------------------------------------------------------------------------------ moon-v1 public surface
def moon_illumination(t: float) -> float:
    """Illuminated fraction 0..1 from the true Sun-Moon elongation (moon-v1 `illumination`)."""
    d = day_number(t)
    sun, moon = sun_coords(d), moon_coords(d)
    elong = acosd(cosd(sun.lon - moon.lon) * cosd(moon.lat))
    return _clamp01((1 + cosd(180 - elong)) / 2)


def moon_phase_fraction(t: float) -> float:
    """0 = new, 0.5 = full (moon-v1 `phaseFraction`). For the phase NAME only, never for illumination."""
    days = (t - KNOWN_NEW_MOON_EPOCH) / 86400.0
    raw = math.fmod(days, SYNODIC_DAYS)
    return math.fmod(raw + SYNODIC_DAYS, SYNODIC_DAYS) / SYNODIC_DAYS


def moon_phase_name(t: float) -> str:
    f = moon_phase_fraction(t)
    if f < 0.03 or f >= 0.97:
        return "New moon"
    if f < 0.22:
        return "Waxing crescent"
    if f < 0.28:
        return "First quarter"
    if f < 0.47:
        return "Waxing gibbous"
    if f < 0.53:
        return "Full moon"
    if f < 0.72:
        return "Waning gibbous"
    if f < 0.78:
        return "Last quarter"
    return "Waning crescent"


def moon_waxing(t: float) -> bool:
    return moon_phase_fraction(t) <= 0.5


def sun_moon_elongation_signed(t: float) -> float:
    """Moon minus Sun ecliptic longitude, -180..180 (0 = conjunction/new, +-180 = opposition/full)."""
    d = day_number(t)
    x = rev360(moon_coords(d).lon - sun_coords(d).lon)
    return x - 360.0 if x > 180.0 else x


# -------------------------------------------------------------------------------------------- local altitude (events)
def gmst_deg(t: float) -> float:
    """Greenwich mean sidereal time in degrees (Meeus eq. 12.4)."""
    jd_off = (t - _J2000_POSIX) / 86400.0
    T = jd_off / 36525.0
    return rev360(280.46061837 + 360.98564736629 * jd_off + 0.000387933 * T * T - T * T * T / 38710000.0)


def _altitude(ra: float, dec: float, t: float, lat: float, lon: float) -> float:
    ha = rev360(gmst_deg(t) + lon - ra)
    return asind(sind(lat) * sind(dec) + cosd(lat) * cosd(dec) * cosd(ha))


def sun_altitude(t: float, lat: float, lon: float) -> float:
    """Geometric (airless) altitude of the Sun's centre, degrees. East longitude positive."""
    s = sun_coords(day_number(t))
    return _altitude(s.ra, s.dec, t, lat, lon)


def moon_geocentric(t: float, lat: float, lon: float) -> tuple[float, float]:
    """(geocentric altitude of the Moon's centre, horizontal parallax), degrees."""
    m = moon_coords(day_number(t))
    return _altitude(m.ra, m.dec, t, lat, lon), asind(1.0 / m.distance)


def moon_altitude(t: float, lat: float, lon: float) -> float:
    """Topocentric altitude of the Moon's centre (parallax applied, no refraction): what Astronomy.moonAltitudeDeg returns."""
    alt, par = moon_geocentric(t, lat, lon)
    return alt - par * cosd(alt)
