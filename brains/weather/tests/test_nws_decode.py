"""NWS decoding: units, QC, valid times, the icon/text -> WMO table. Expected values are the Engine adapter's own test values
(Tests/SectorEngineTests/NWSWeatherServiceTests.swift) on the same recorded files, so the Brain and the Engine read NWS identically."""
import os
from datetime import datetime, timezone

import pytest

from sector_weather import nws
from weather_support import REC, load


def test_units_convert_only_from_known_codes():
    assert nws.convert(22, "wmoUnit:degC", "F") == pytest.approx(71.6)
    assert nws.convert(-40, "wmoUnit:degC", "F") == pytest.approx(-40)
    assert nws.convert(16.09344, "wmoUnit:km_h-1", "mph") == pytest.approx(10)
    assert nws.convert(101591.66, "wmoUnit:Pa", "hPa") == pytest.approx(1015.9166)
    assert nws.convert(25.4, "wmoUnit:mm", "in") == pytest.approx(1)
    assert nws.convert(10, "wmoUnit:furlong", "in") is None                  # unknown unit: never a guess
    assert nws.convert(None, "wmoUnit:Pa", "hPa") is None


def test_rejected_and_bad_qc_drop_the_value():
    assert nws.quantity({"unitCode": "wmoUnit:degC", "value": 20, "qualityControl": "X"}, "F") is None
    assert nws.quantity({"unitCode": "wmoUnit:degC", "value": 20, "qualityControl": "B"}, "F") is None
    assert nws.quantity({"unitCode": "wmoUnit:degC", "value": 20, "qualityControl": "Z"}, "F") == pytest.approx(68)


def test_valid_time_durations():
    s, h = nws.parse_valid_time("2026-11-06T14:00:00+00:00/PT2H")
    assert s == datetime(2026, 11, 6, 14, tzinfo=timezone.utc) and h == 2
    assert nws.parse_valid_time("2026-11-06T00:00:00+00:00/P1DT6H")[1] == 30
    assert nws.parse_valid_time("2026-11-06T00:00:00+00:00/PT30M") is None
    assert nws.parse_valid_time("garbage") is None


def test_recorded_point_and_stations():
    p = nws.decode_point(load(os.path.join(REC, "guntersville-points.json")))
    assert p.gridpoint == "HUN/76,30" and p.forecast_grid_data.endswith("/gridpoints/HUN/76,30")
    st = nws.decode_stations(load(os.path.join(REC, "guntersville-stations.json")))
    assert [s["id"] for s in st[:3]] == ["K8A1", "KBFZ", "K4A6"]


def test_recorded_observations_match_the_engine_adapter():
    obs = nws.decode_observations(load(os.path.join(REC, "champlain-obs-KBTV.json")))
    o = obs[0]
    assert o.station == "KBTV" and o.at == datetime(2026, 11, 6, 20, 30, tzinfo=timezone.utc)
    assert o.temp_f == pytest.approx(62.6) and o.alt_hpa == pytest.approx(1010.4984)
    assert [x.at for x in obs] == sorted((x.at for x in obs), reverse=True)
    assert nws.decode_observations(load(os.path.join(REC, "guntersville-obs-K8A1.json"))) == []


def test_recorded_grid_has_no_pressure_and_hourly_values():
    g = nws.decode_grid(load(os.path.join(REC, "guntersville-grid.json")))
    assert g.temp_f[datetime(2026, 11, 6, 15, tzinfo=timezone.utc)] == pytest.approx(59)
    assert not g.has_pressure()
    assert g.update_time == datetime(2026, 11, 6, 20, 43, 55, tzinfo=timezone.utc)


def test_qpf_counts_partial_periods_in_proportion():
    g = nws.Grid(qpf=[(datetime(2026, 1, 1, 0, tzinfo=timezone.utc), 6, 0.60)])
    assert nws.qpf_inches(g, datetime(2026, 1, 1, 3, tzinfo=timezone.utc), 6) == pytest.approx(0.30)
    assert nws.qpf_inches(nws.Grid(), datetime(2026, 1, 1, tzinfo=timezone.utc), 6) is None      # no layer: unknown, not 0


@pytest.mark.parametrize("icon,text,cover,code", [
    ("https://api.weather.gov/icons/land/night/rain,40/tsra?size=medium", "Light Rain", None, 61),
    ("https://api.weather.gov/icons/land/day/tsra", "Thunderstorm Hail", None, 96),
    ("https://api.weather.gov/icons/land/day/rain", "Drizzle", None, 53),
    ("https://api.weather.gov/icons/land/day/bkn", "Mostly Cloudy", 48.0, 2),
    ("https://api.weather.gov/icons/land/day/ovc", "Overcast", None, 3),
    (None, "Heavy Snow", None, 75),
    (None, "Fair", None, 1),
    ("https://api.weather.gov/icons/land/day/haze", "Haze", 90.0, 3),
])
def test_weather_code_table(icon, text, cover, code):
    assert nws.weather_code(icon, text, cover) == code
