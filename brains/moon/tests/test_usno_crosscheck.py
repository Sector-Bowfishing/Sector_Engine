"""Cross-check against USNO published values (tests/fixtures/usno_reference.json, retrieved 2026-11-22).

Stated tolerances (contracts/moon-night-light-v1.json usnoCrossCheck): rise/set and twilight +-2 min; principal phase instants +-20 min;
illumination at a principal phase within 0.003 of 0, 0.5 or 1. USNO rounds to the minute, so +-2 min allows about 1.5 min of model error."""
import datetime as dt
import json
import os

import pytest

from moon_brain import ephemeris as eph
from moon_brain import events as ev
from moon_brain import night

REF = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "usno_reference.json"), encoding="utf-8"))
RISE_SET_TOL_S = 120
TWILIGHT_TOL_S = 120
PHASE_TOL_S = 20 * 60
ILLUM_TOL = 0.003
PHASE_ANGLE = {"New Moon": 0.0, "First Quarter": 90.0, "Full Moon": 180.0, "Last Quarter": 270.0}
PHASE_ILLUM = {"New Moon": 0.0, "First Quarter": 0.5, "Full Moon": 1.0, "Last Quarter": 0.5}


def _day(date: str) -> float:
    return dt.datetime.fromisoformat(date + "T00:00:00+00:00").timestamp()


def _ut(date: str, hhmm: str) -> float:
    h, m = hhmm.split(":")
    return _day(date) + int(h) * 3600 + int(m) * 60


def _one(events, kind):
    hits = [t for t, k in events if k == kind]
    assert len(hits) == 1, f"expected one {kind} in the UTC day, got {len(hits)}"
    return hits[0]


ONEDAY = [(r["place"], r["date"], key, hhmm) for r in REF["oneday"] for key, hhmm in r["ut"].items()]
FN = {"sunrise": (ev.sun_offset(ev.SUN_RISE_SET_H0), "rise"), "sunset": (ev.sun_offset(ev.SUN_RISE_SET_H0), "set"),
      "civilBegin": (ev.sun_offset(ev.TWILIGHT_H0["civil"]), "rise"), "civilEnd": (ev.sun_offset(ev.TWILIGHT_H0["civil"]), "set"),
      "moonrise": (ev.moon_offset, "rise"), "moonset": (ev.moon_offset, "set")}


@pytest.mark.parametrize("place,date,key,hhmm", ONEDAY, ids=lambda x: str(x))
def test_rise_set_and_civil_twilight_within_two_minutes_of_usno(place, date, key, hhmm):
    p = REF["places"][place]
    f, kind = FN[key]
    got = _one(ev.crossings(f, p["lat"], p["lon"], _day(date), _day(date) + 86400), kind)
    tol = TWILIGHT_TOL_S if key.startswith("civil") else RISE_SET_TOL_S
    assert abs(got - _ut(date, hhmm)) <= tol, f"{place} {date} {key}: {dt.datetime.fromtimestamp(got, dt.timezone.utc)} vs USNO {hhmm}"


@pytest.mark.parametrize("row", REF["twilightTables"], ids=lambda r: f"{r['place']}-{r['date']}-{r['kind']}")
def test_nautical_and_astronomical_twilight_within_two_minutes_of_usno(row):
    p = REF["places"][row["place"]]
    cr = ev.crossings(ev.sun_offset(ev.TWILIGHT_H0[row["kind"]]), p["lat"], p["lon"], _day(row["date"]), _day(row["date"]) + 86400)
    if row["ut"]["begin"] is None:                                  # USNO "////": the Sun never gets that low that day
        assert cr == []
        return
    assert abs(_one(cr, "rise") - _ut(row["date"], row["ut"]["begin"])) <= TWILIGHT_TOL_S
    assert abs(_one(cr, "set") - _ut(row["date"], row["ut"]["end"])) <= TWILIGHT_TOL_S


@pytest.mark.parametrize("row", REF["phases"], ids=lambda r: f"{r['phase']}-{r['at']}")
def test_principal_phases_match_usno(row):
    t_usno = dt.datetime.fromisoformat(row["at"].replace("Z", "+00:00")).timestamp()
    target = PHASE_ANGLE[row["phase"]]

    def off(t):
        return (eph.sun_moon_elongation_signed(t) - target + 180.0) % 360.0 - 180.0
    a, b = t_usno - 86400, t_usno + 86400
    while b - a > 1:
        m = (a + b) / 2
        if off(m) < 0:
            a = m
        else:
            b = m
    assert abs(a - t_usno) <= PHASE_TOL_S
    assert abs(eph.moon_illumination(t_usno) - PHASE_ILLUM[row["phase"]]) <= ILLUM_TOL


def test_tonight_uses_the_same_events_usno_publishes():
    """The Brain's own output path (night.tonight), not just the event finder: Guntersville, the evening of 2026-11-22."""
    sky = night.tonight(34.42, -86.26, dt.date(2026, 11, 22))
    assert abs(_parse(sky["sun"]["sunset"]) - _ut("2026-11-22", "22:37")) <= RISE_SET_TOL_S
    assert abs(_parse(sky["sun"]["twilight"]["civil"]["dusk"]) - _ut("2026-11-22", "23:04")) <= TWILIGHT_TOL_S
    assert abs(_parse(sky["sun"]["twilight"]["nautical"]["dusk"]) - _ut("2026-11-22", "23:35")) <= TWILIGHT_TOL_S
    assert abs(_parse(sky["moon"]["moonrise"]) - _ut("2026-11-22", "20:56")) <= RISE_SET_TOL_S


def _parse(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
