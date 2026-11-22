"""Tonight's span, the fishing window and moonlight: the Engine/iOS behaviour the Brain must reproduce (iOS specs/conditions-engine.md)."""
import datetime as dt

import pytest

from moon_brain import ephemeris as eph
from moon_brain import night


def _t(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


@pytest.mark.parametrize("lat,lon", [(34.42, -86.26), (26.95, -80.8), (44.5, -73.3), (34.45, -114.3), (59.55, -155.0), (21.3, -157.8)])
@pytest.mark.parametrize("date", [dt.date(2026, 3, 20), dt.date(2026, 6, 21), dt.date(2026, 11, 22), dt.date(2026, 12, 23)])
def test_the_night_runs_into_tomorrow(lat, lon, date):
    """The 2026-08-03 bug: a window built from same-day sunrise ended ~15 h before it started. Here sunset < dusk < window < sunrise, always."""
    sky = night.tonight(lat, lon, date)
    w = sky["window"]
    s, e = _t(w["start"]), _t(w["end"])
    assert e > s
    assert _t(sky["sun"]["sunset"]) < s < e
    assert _t(sky["sun"]["sunrise"]) == pytest.approx(e, abs=1)
    assert _t(sky["span"]["start"]) < _t(sky["sun"]["sunset"]) < _t(sky["span"]["end"])
    tw = sky["sun"]["twilight"]
    for name in ("civil", "nautical", "astronomical"):
        if tw[name]["dusk"]:
            assert _t(sky["sun"]["sunset"]) < _t(tw[name]["dusk"]) < _t(tw[name]["dawn"]) < _t(sky["sun"]["sunrise"])


def test_moon_up_all_night_is_not_reported_as_down():
    """Langston, AL, the night of 2026-08-03 (the measured case in iOS specs/conditions-engine.md): a waning gibbous up from ~10:20 PM CDT to
    mid-morning. Presence must be large, not 0. (The spec's '79.6 %' was read at request time that afternoon and its '9:59 PM' moonrise is the
    previous evening's: the Engine's moonRiseSet scans the UTC day. The Brain reads illumination at local solar midnight and moon events in the
    noon-to-noon span.)"""
    sky = night.tonight(34.53, -86.08, dt.date(2026, 8, 3))
    ml = sky["window"]["moonlight"]
    assert sky["moon"]["illumination"] > 0.65 and sky["moon"]["phaseName"] == "Waning gibbous"
    assert "2026-08-04T03:00:00Z" < sky["moon"]["moonrise"] < "2026-08-04T03:45:00Z"
    assert ml["presence"] > 0.3 and ml["upFraction"] > 0.8


def test_window_basis_falls_back_to_sunset_plus_80_when_no_astronomical_dark():
    """Champlain at midsummer still reaches -18; Iliamna (59.55 N) does not: the window starts at sunset + 80 min, as in the Engine."""
    sky = night.tonight(59.55, -155.0, dt.date(2026, 6, 21))
    assert sky["sun"]["twilight"]["astronomical"]["dusk"] is None
    assert sky["sun"]["twilight"]["astronomical"]["sunState"] == "ALWAYS_ABOVE"
    assert sky["window"]["basis"].startswith("SUNSET_PLUS_80_MIN_TO_SUNRISE")
    assert _t(sky["window"]["start"]) == pytest.approx(_t(sky["sun"]["sunset"]) + 80 * 60, abs=1)


def test_polar_day_has_no_night_and_polar_night_uses_the_whole_span():
    day = night.tonight(70.6, -153.5, dt.date(2026, 6, 21))           # Teshekpuk, AK: midnight sun
    assert day["sun"]["sunset"] is None and day["sun"]["sunState"] == "ALWAYS_ABOVE"
    assert day["window"]["start"] is None and day["window"]["basis"] == "NO_NIGHT_SUN_ALWAYS_UP" and "moonlight" not in day["window"]
    dark = night.tonight(70.6, -153.5, dt.date(2026, 12, 21))         # polar night
    assert dark["sun"]["sunState"] == "ALWAYS_BELOW" and dark["window"]["basis"] == "POLAR_NIGHT_WHOLE_SPAN"


def test_span_is_anchored_on_local_solar_noon():
    sky = night.tonight(34.42, -86.26, dt.date(2026, 11, 22))
    assert sky["span"]["start"] == "2026-11-22T17:45:02Z" and sky["span"]["anchor"] == "LOCAL_SOLAR_NOON"
    assert sky["moon"]["illuminationAt"] == "2026-11-23T05:45:02Z"
    assert sky["moon"]["illumination"] == round(eph.moon_illumination(_t("2026-11-23T05:45:02Z")), 4)


def test_moonlight_is_the_engine_presence_definition():
    """mean max(0, sin(alt)) every 15 min, end inclusive (Astronomy.moonAltitudeFraction)."""
    import math
    sky = night.tonight(34.42, -86.26, dt.date(2026, 11, 22))
    s, e = _t(sky["window"]["start"]), _t(sky["window"]["end"])
    xs, t = [], s
    while t <= e + 1e-6:
        xs.append(max(0.0, math.sin(math.radians(eph.moon_altitude(t, 34.42, -86.26)))))
        t += 900
    assert sky["window"]["moonlight"]["presence"] == round(sum(xs) / len(xs), 4)
    assert sky["window"]["moonlight"]["samples"] == len(xs)


def test_absent_moon_events_are_absent_not_invented():
    """Some spans hold only a moonrise or only a moonset (the ~50 min daily lag). Every reported event is a real crossing, in order."""
    for d in range(1, 31):
        sky = night.tonight(34.42, -86.26, dt.date(2026, 11, d))
        evs = sky["moon"]["events"]
        assert 0 <= len(evs) <= 2
        assert [e["at"] for e in evs] == sorted(e["at"] for e in evs)
        kinds = [e["event"] for e in evs]
        assert sky["moon"]["moonrise"] == next((e["at"] for e in evs if e["event"] == "rise"), None)
        assert sky["moon"]["moonset"] == next((e["at"] for e in evs if e["event"] == "set"), None)
        assert kinds != ["rise", "rise"] and kinds != ["set", "set"]
