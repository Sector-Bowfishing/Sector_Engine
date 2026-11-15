"""Sector_Ops #45: NBM point forecasts for the W1 lakes. Off by default; speed and gust at each point's nearest cell. Network stubbed."""
from datetime import datetime, timezone

import numpy as np

from sector_wind import grib, live, points
from sector_wind.store import LocalStore

INIT = datetime(2026, 11, 2, 3, tzinfo=timezone.utc)
KEY = "test:3x3"


def _grid():
    lat = np.repeat([40.00, 40.02, 40.04], 3)
    lon = np.tile([-100.00, -99.97, -99.94], 3)
    grib._GRIDS[KEY] = (lat, lon)


class _F:
    def __init__(self, values):
        self.values = np.asarray(values, float)
        self.missing = np.zeros(9, bool)
        self.grid_key = KEY


def _stub(monkeypatch):
    _grid()
    monkeypatch.setattr(points, "read_idx", lambda url: [])
    monkeypatch.setattr(points, "row_scramble_ratio", lambda v, c, nx: 1.0)
    monkeypatch.setattr(points, "_field", lambda url, ent, var, tail, step: _F(np.arange(9) + (100 if var == "GUST" else 0)))


PCFG = {"version": "wind-points-v1", "points": {"In|ZZ": {"lat": 40.021, "lon": -99.969}, "Far|ZZ": {"lat": 45.0, "lon": -90.0}}}


def test_packaged_points_are_the_w1_passing_lakes():
    p = points.load_points()
    assert p["version"] == "wind-points-v1" and len(p["points"]) == 142
    assert p["evidence"]["verdict"] == "SUPPORTED"
    assert not set(p["points"]) & set(p["excludedFailed"])
    for home in ("Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"):
        assert home not in p["points"]
    for v in p["points"].values():
        assert v["stationKm"] <= 10 and v["w1NightMaeMph"] <= 3.5 and abs(v["w1NightBiasMph"]) <= 2.0


def test_off_by_default():
    assert points.enabled({}) is False and points.enabled({"WIND_NBM_POINTS": "1"}) is True


def test_point_takes_its_nearest_cell_and_outside_points_are_listed(tmp_path, monkeypatch):
    _stub(monkeypatch)
    store = LocalStore(str(tmp_path))
    r = points.ingest_nbm_points(store, PCFG, INIT, [1, 2])
    assert r == {"status": "complete", "points": 1, "outsideGrid": 1}
    obj = store.get_json("nbm-points/2026110203.json.gz")
    steps = obj["points"]["In|ZZ"]
    assert [s["leadHours"] for s in steps] == [1, 2]
    assert steps[0]["speedMS"] == 4.0 and steps[0]["gustMS"] == 104.0       # cell 4 = (40.02, -99.97)
    assert set(steps[0]) == {"leadHours", "validTime", "speedMS", "gustMS"}  # no direction, no percentiles
    assert obj["outsideGrid"] == ["Far|ZZ"] and "not lake-surface wind" in obj["scope"]


def test_hourly_run_does_not_touch_points_unless_enabled(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(live, "latest_nbm_cycle", lambda now=None, max_back_h=4: INIT)
    monkeypatch.setattr(live, "ingest_nbm_cycle", lambda store, cfg, c, leads, q: {})
    monkeypatch.setattr(live, "ingest_rtma", lambda store, cfg, t: {})
    monkeypatch.setattr(live, "ingest_metar_day", lambda store, cfg, d: 0)
    monkeypatch.setattr(live, "write_latest_bundle", lambda store, lake, now: {})
    monkeypatch.setattr(points, "ingest_nbm_points", lambda *a: calls.append(a) or {"status": "complete"})
    cfg = {"lakes": {"guntersville": {"bbox": [-86.5, 34.3, -85.6, 34.9]}}}
    now = datetime(2026, 11, 2, 4, 5, tzinfo=timezone.utc)
    monkeypatch.delenv("WIND_NBM_POINTS", raising=False)
    s = live.run_hourly(LocalStore(str(tmp_path)), cfg, now)
    assert not calls and "nbmPoints" not in s
    monkeypatch.setenv("WIND_NBM_POINTS", "1")
    s = live.run_hourly(LocalStore(str(tmp_path)), cfg, now)
    assert len(calls) == 1 and s["nbmPoints"]["status"] == "complete"
