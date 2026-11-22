"""The weather-change signal on HAND-BUILT cases (tests/fixtures/hand_built, weather_support builders) and on the recorded fixtures.
The thresholds are the pre-stated v1 values; these tests pin them so a change needs a new thresholds version, not a silent edit."""
import os
from datetime import datetime, timedelta, timezone

from sector_weather import contract as C
from sector_weather.nws import Grid, decode_observations
from sector_weather.reading import assemble
from sector_weather.signal import evaluate
from weather_support import HAND, collection, hourly, load

NOW = datetime(2026, 11, 20, 2, 10, tzinfo=timezone.utc)


def _eval(features_or_doc, grid=None, now=NOW):
    doc = features_or_doc if isinstance(features_or_doc, dict) else collection(features_or_doc)
    obs = decode_observations(doc)
    return evaluate(assemble(["KTST"], {"KTST": obs}, grid, now))


def _kinds(sig):
    return sorted(e["kind"] for e in sig["events"])


def _steady(i):
    return dict(temp_c=15, dew_c=10, alt_pa=101500 - 5 * i, wind_kmh=10, wind_dir=200, text="Clear",
                icon="https://api.weather.gov/icons/land/night/skc?size=medium")


def _dry_grid():
    return Grid(qpf=[(NOW.replace(minute=0) - timedelta(hours=2), 12, 0.0)])


def test_thresholds_are_the_pre_stated_v1_values():
    assert C.THRESHOLDS_VERSION == "weather-change-thresholds-v1"
    assert C.THRESHOLDS == {"pressureFastInHgPer3h": 0.06, "airTempSwingFPer3h": 8.0, "frontWindShiftDeg": 90.0, "frontWindMinMph": 5.0,
                            "frontTroughInHg": 0.02, "frontDropF": 5.0, "measurablePrecipIn": 0.01, "rainOnsetDryLookbackHours": 3.0,
                            "rainExpectedIn": 0.10, "rainExpectedHours": 6.0, "windowHours": 3.0}


def test_steady_night_is_steady_with_every_rule_evaluated():
    sig = _eval(hourly(NOW, 6, _steady), _dry_grid())
    assert sig["level"] == "STEADY" and sig["events"] == [] and sig["unknown"] == []
    assert sig["inputs"]["pressureChange3hInHg"] == round(-15 / 100 * C.HPA_TO_INHG, 3)


def test_pressure_falling_fast_at_the_threshold_but_not_below_it():
    fast = _eval(hourly(NOW, 6, lambda i: {**_steady(i), "alt_pa": 101500 - 69 * i}), _dry_grid())     # 2.07 hPa / 3 h = 0.061 inHg
    slow = _eval(hourly(NOW, 6, lambda i: {**_steady(i), "alt_pa": 101500 - 66 * i}), _dry_grid())     # 1.98 hPa / 3 h = 0.058 inHg
    assert _kinds(fast) == ["PRESSURE_FALLING_FAST"] and fast["level"] == "CHANGE"
    assert slow["level"] == "STEADY"


def test_air_temperature_swing_of_8f_in_3h():
    sig = _eval(hourly(NOW, 6, lambda i: {**_steady(i), "temp_c": 20 - 1.5 * i}), _dry_grid())      # 4.5 C = 8.1 F over 3 h
    assert "AIR_TEMP_SWING" in _kinds(sig) and sig["level"] == "CHANGE"


def test_front_passage_from_the_hand_built_recording_shape():
    doc = load(os.path.join(HAND, "front_passage_KTST.json"))
    sig = _eval(doc, _dry_grid())
    assert set(_kinds(sig)) == {"FRONT_PASSAGE", "AIR_TEMP_SWING", "PRESSURE_RISING_FAST"}
    front = next(e for e in sig["events"] if e["kind"] == "FRONT_PASSAGE")
    assert front["value"] >= 90 and any("air temperature fell" in s for s in front["support"])


def test_a_sunset_cooling_without_a_wind_turn_is_not_a_front():
    sig = _eval(hourly(NOW, 6, lambda i: {**_steady(i), "temp_c": 20 - 1.0 * i, "dew_c": 12 - 1.0 * i}), _dry_grid())
    assert "FRONT_PASSAGE" not in _kinds(sig)


def test_a_wind_turn_alone_is_not_a_front():
    sig = _eval(hourly(NOW, 6, lambda i: {**_steady(i), "wind_dir": 200 if i < 4 else 330}), _dry_grid())
    assert "FRONT_PASSAGE" not in _kinds(sig) and sig["inputs"]["windTurn3hDeg"] >= 90


def test_rain_onset_after_dry_hours():
    sig = _eval(load(os.path.join(HAND, "rain_onset_KTST.json")), _dry_grid())
    assert _kinds(sig) == ["RAIN_ONSET"] and sig["level"] == "CHANGE"


def test_continuing_rain_is_not_an_onset():
    wet = lambda i: {**_steady(i), "text": "Rain", "icon": "https://api.weather.gov/icons/land/night/rain?size=medium", "precip_mm": 2.0}
    assert "RAIN_ONSET" not in _kinds(_eval(hourly(NOW, 6, wet), _dry_grid()))


def test_rain_expected_from_the_official_forecast_is_watch_not_change():
    grid = Grid(qpf=[(NOW.replace(minute=0), 6, 0.30)])
    sig = _eval(hourly(NOW, 6, _steady), grid)
    assert _kinds(sig) == ["RAIN_EXPECTED"] and sig["events"][0]["basis"] == "FORECAST" and sig["level"] == "WATCH"


def test_unknown_inputs_are_watch_never_steady():
    sig = _eval(hourly(NOW, 1, _steady), _dry_grid())                     # only 1 h of history: the 3 h rules cannot be evaluated
    assert sig["level"] == "WATCH" and any(u.startswith("pressure3h") for u in sig["unknown"])
    assert _eval([], None)["level"] == "WATCH"


def test_signature_changes_with_the_observation_and_the_level():
    a = _eval(hourly(NOW, 6, _steady), _dry_grid())
    b = _eval(hourly(NOW + timedelta(hours=1), 7, _steady), _dry_grid(), NOW + timedelta(hours=1))
    c = _eval(hourly(NOW, 6, lambda i: {**_steady(i), "alt_pa": 101500 - 80 * i}), _dry_grid())
    assert len({a["signature"], b["signature"], c["signature"]}) == 3
