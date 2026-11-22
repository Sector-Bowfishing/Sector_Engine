"""The four tiles on the recorded fixtures: the same values the Engine adapter's tests assert (NWSWeatherServiceTests.swift), so the Brain's
Sky / Barometric Pressure / Air Temperature / Humidity mean exactly what the app's tiles mean."""
from datetime import datetime, timezone

import pytest

from sector_weather.client import PointCache
from sector_weather.publish import run
from weather_support import LAKES, RECORDED_NOW, FixtureSource


def _state(lake, now=RECORDED_NOW):
    return run([LAKES[lake]], FixtureSource(), PointCache(None), {}, now)["states"][lake]


def test_champlain_sea_level_pressure_with_the_station_offset_and_the_3h_tile_trend():
    s = _state("Champlain|VT")
    p = s["pressure"]
    assert s["kind"] == "observation" and p["station"] == "KBTV" and p["kind"] == "seaLevel" and p["origin"] == "observation"
    assert s["origins"]["cloudCoverPct"] == "forecastGrid" and s["origins"]["airTemperatureF"] == "observation" and s["mixedOrigin"] is True
    assert p["seaLevelOffsetHPa"] == pytest.approx(-0.1) and p["hPa"] == pytest.approx(1010.4)
    assert p["inHg"] == pytest.approx(1010.3984 * 0.0295299830714, abs=0.005)
    assert p["trend3h"]["trend"] == "falling"                            # displayPressureTrend: the tile, sheet and score trend
    assert p["trend12h"]["trend"] == "steady" and p["trend12h"]["changeHPa"] == pytest.approx(-0.70, abs=0.01)
    assert p["forecast"] is None                                         # the NWS grid has no pressure layer: no forecast, never an estimate
    assert s["airTemperatureF"]["value"] == pytest.approx(62.6) and s["humidityPct"]["value"] == 59
    assert s["sky"]["cloudCoverPct"] == {"value": 48, "at": "2026-11-06T20:00:00Z", "origin": "forecastGrid", "station": None}
    assert s["sky"]["weatherCode"]["value"] == 2 and s["sky"]["description"] == "Partly cloudy" and s["sky"]["nwsText"] == "Partly Cloudy"
    assert s["sky"]["word"] == "broken cloud"                            # iOS cloudWord: 25 <= 48 < 60


def test_guntersville_with_stale_stations_falls_back_to_the_grid_and_leaves_pressure_null():
    s = _state("Guntersville|AL")
    assert s["kind"] == "forecast" and s["pressure"] is None and "pressure" in s["missing"]
    assert s["airTemperatureF"] == {"value": 69.0, "at": "2026-11-06T20:00:00Z", "origin": "forecastGrid", "station": None}
    assert s["sky"]["cloudCoverPct"]["value"] == 15 and s["sky"]["weatherCode"]["value"] == 1 and s["sky"]["description"] == "Mainly clear"
    assert s["weatherChange"]["level"] == "WATCH"                        # cannot rule a change out without observations


def test_guntersville_while_fresh_uses_the_newest_station_and_labels_the_altimeter():
    s = _state("Guntersville|AL", datetime(2026, 11, 6, 19, tzinfo=timezone.utc))
    assert s["airTemperatureF"]["station"] == "K4A6" and s["airTemperatureF"]["value"] == pytest.approx(73.4)
    assert s["humidityPct"]["value"] == 47
    p = s["pressure"]
    assert p["kind"] == "altimeter" and p["seaLevelOffsetHPa"] is None and p["hPa"] == pytest.approx(1015.6)
    assert p["trend12h"]["trend"] == "steady" and p["trend3h"]["trend"] == "falling"
    # DELIBERATE DIFFERENCE from the Engine adapter (which asserts 0 here): K4A6 itself reported "Mostly Cloudy"; the adapter lets the grid's 15 %
    # cover override that into "Clear" while labelling it an observation. The Brain keeps the station's own report (review of #234).
    assert s["sky"]["weatherCode"] == {"value": 2, "at": "2026-11-06T18:35:00Z", "origin": "observation", "station": "K4A6"}
    assert s["sky"]["nwsText"] == "Mostly Cloudy"


def test_forecast_rows_are_the_next_12_grid_hours():
    rows = _state("Champlain|VT")["forecast"]["hourly"]
    assert len(rows) == 12 and rows[0]["at"] == "2026-11-06T21:00:00Z" and rows[-1]["at"] == "2026-11-07T08:00:00Z"


def test_a_station_report_is_never_overridden_by_the_grid_cloud_cover():
    """Review of #234 (blocking 1): station "Clear" + grid 95 % used to give "Overcast" labelled as the station's observation."""
    from datetime import timedelta
    from sector_weather.nws import Grid, decode_observations
    from sector_weather.reading import assemble
    from weather_support import collection, obs_feature
    now = datetime(2026, 11, 20, 2, 10, tzinfo=timezone.utc)
    clear = collection([obs_feature("KTST", now - timedelta(minutes=17), temp_c=15, alt_pa=101500, text="Clear",
                                    icon="https://api.weather.gov/icons/land/night/skc?size=medium")])
    grid = Grid(sky_pct={now.replace(minute=0): 95.0})
    rd = assemble(["KTST"], {"KTST": decode_observations(clear)}, grid, now)
    assert rd.values["weatherCode"]["value"] == 0 and rd.values["weatherCode"]["origin"] == "observation"
    assert rd.values["cloudCoverPct"] == {"value": 95.0, "at": now.replace(minute=0), "origin": "forecastGrid", "station": None}
    silent = collection([obs_feature("KTST", now - timedelta(minutes=17), temp_c=15, alt_pa=101500)])   # the station says nothing about the sky
    rd = assemble(["KTST"], {"KTST": decode_observations(silent)}, grid, now)
    assert rd.values["weatherCode"]["value"] == 3 and rd.values["weatherCode"]["origin"] == "forecastGrid"


def test_kind_is_observation_when_any_tile_is_observed_and_mixed_origin_is_explicit():
    from datetime import timedelta
    from weather_support import collection, obs_feature
    now = datetime(2026, 11, 6, 20, 51, tzinfo=timezone.utc)
    only_pressure = {"KTST": collection([obs_feature("KTST", now - timedelta(minutes=20), alt_pa=101500)])}

    class Src(FixtureSource):
        def stations(self, url):
            return {"features": [{"properties": {"stationIdentifier": "KTST", "name": "Test"}, "geometry": {"coordinates": [-73.3, 44.47]}}]}

        def observations(self, station, now):
            return only_pressure["KTST"]
    st = run([LAKES["Champlain|VT"]], Src(), PointCache(None), {}, now)["states"]["Champlain|VT"]
    assert st["kind"] == "observation" and st["origins"]["pressure"] == "observation" and st["origins"]["airTemperatureF"] == "forecastGrid"
    assert st["mixedOrigin"] is True
