"""Risky-night flag shadow (Sector_Ops #27): off by default, records the frozen rule only. Network stubbed."""
from datetime import datetime, timezone

import numpy as np

from sector_wind import grib, live, points, pw15
from sector_wind.store import LocalStore

INIT = datetime(2026, 11, 2, 0, tzinfo=timezone.utc)
KEY = "test:3x3"
PCFG = {"version": "wind-points-v1", "points": {"In|ZZ": {"lat": 40.021, "lon": -99.969}, "Far|ZZ": {"lat": 45.0, "lon": -90.0}}}


class _F:
    def __init__(self, values):
        self.values = np.asarray(values, float); self.missing = np.zeros(9, bool); self.grid_key = KEY


def _stub(monkeypatch, speed, prob_pct, levels):
    grib._GRIDS[KEY] = (np.repeat([40.00, 40.02, 40.04], 3), np.tile([-100.00, -99.97, -99.94], 3))
    monkeypatch.setattr(pw15, "read_idx", lambda url: [])
    monkeypatch.setattr(pw15, "row_scramble_ratio", lambda v, c, nx: 1.0)
    monkeypatch.setattr(pw15, "cells_in_bbox", lambda k, b: np.arange(9))
    monkeypatch.setattr(pw15, "_field", lambda *a: _F([speed] * 9))
    thr = [3.6011, 5.6588, 8.7456, 11.3177]
    monkeypatch.setattr(pw15, "_qmd_fields", lambda qurl, f: ([(t, _F([p] * 9)) for t, p in zip(thr, prob_pct)], {l: _F([v] * 9) for l, v in levels.items()}))


def test_exceed_matches_frozen_rule():
    pts = [(3.6011, 0.9), (5.6588, 0.7), (8.7456, 0.4), (11.3177, 0.1), (2.0, 0.5), (4.0, 0.75), (9.0, 0.9)]
    assert pw15.exceed([(3.0, 0.5)], 99.0) == 0.25                     # beyond the curve: at most half the last tail
    assert abs(pw15.exceed([(4.0, 0.5), (10.0, 1.0)], 7.0) - 0.25) < 1e-9
    assert 0.0 <= pw15.exceed(pts, pw15.T15) <= 1.0


def test_local_night_uses_standard_clock():
    assert pw15.local_night(datetime(2026, 11, 2, 3, tzinfo=timezone.utc), -100.0)     # 20 local
    assert not pw15.local_night(datetime(2026, 11, 2, 18, tzinfo=timezone.utc), -100.0)


def test_flag_only_when_under_15_and_p_at_least_0_15(tmp_path, monkeypatch):
    st = LocalStore(str(tmp_path))
    # NBM 5 m/s (<15 mph), P(>11.3177 m/s)=40% so P(>6.7056) is well above 0.15 -> flag
    _stub(monkeypatch, 5.0, [95, 80, 60, 40], {50: 4.0, 75: 6.0, 90: 12.0})
    r = pw15.ingest_pw15_shadow(st, PCFG, INIT, [3])
    row = st.get_json("pw15-shadow/2026110200.json.gz")["points"]["In|ZZ"][0]
    assert row["wouldFlag"] is True and row["pW15"] >= 0.15 and row["night"] is True and r["points"] == 1
    # calm tails -> no flag
    _stub(monkeypatch, 3.0, [60, 1, 0, 0], {50: 2.5, 75: 3.0, 90: 3.5})
    pw15.ingest_pw15_shadow(st, PCFG, INIT, [3])
    assert st.get_json("pw15-shadow/2026110200.json.gz")["points"]["In|ZZ"][0]["wouldFlag"] is False
    # deterministic already >= 15 mph (7 m/s): never flagged (the rule only lowers confidence where NBM looks fine)
    _stub(monkeypatch, 8.0, [99, 99, 90, 60], {50: 9.0, 75: 11.0, 90: 14.0})
    pw15.ingest_pw15_shadow(st, PCFG, INIT, [3])
    assert st.get_json("pw15-shadow/2026110200.json.gz")["points"]["In|ZZ"][0]["wouldFlag"] is False


def test_non_synoptic_cycle_is_skipped(tmp_path):
    r = pw15.ingest_pw15_shadow(LocalStore(str(tmp_path)), PCFG, datetime(2026, 11, 2, 3, tzinfo=timezone.utc))
    assert r["status"] == "skipped"


def test_hourly_run_off_by_default(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(live, "latest_nbm_cycle", lambda now=None, max_back_h=4: datetime(2026, 11, 2, 3, tzinfo=timezone.utc))
    monkeypatch.setattr(live, "ingest_nbm_cycle", lambda store, cfg, c, leads, q: {})
    monkeypatch.setattr(live, "ingest_rtma", lambda store, cfg, t: {})
    monkeypatch.setattr(live, "ingest_metar_day", lambda store, cfg, d: 0)
    monkeypatch.setattr(live, "write_latest_bundle", lambda store, lake, now: {})
    monkeypatch.setattr(pw15, "ingest_pw15_shadow", lambda store, p, syn: calls.append(syn) or {"status": "complete"})
    cfg = {"lakes": {"guntersville": {"bbox": [-86.5, 34.3, -85.6, 34.9]}}}
    now = datetime(2026, 11, 2, 4, 5, tzinfo=timezone.utc)
    monkeypatch.delenv("WIND_PW15_SHADOW", raising=False)
    s = live.run_hourly(LocalStore(str(tmp_path)), cfg, now)
    assert not calls and "pW15Shadow" not in s and "pw15Shadow" not in s
    monkeypatch.setenv("WIND_PW15_SHADOW", "1")
    s = live.run_hourly(LocalStore(str(tmp_path)), cfg, now)
    assert calls == [datetime(2026, 11, 2, 0, tzinfo=timezone.utc)] and s["pw15Shadow"]["status"] == "complete"


def test_exceed_equals_research_exceed():
    # Golden values taken from brains/wind/research/tools/forcing_eval.exceed (the W-NOW-1..3 rule) on the same curve.
    pts = [(3.6011, 0.9), (5.6588, 0.7), (8.7456, 0.4), (11.3177, 0.1), (4.0, 0.5), (6.0, 0.75), (12.0, 0.9)]
    for T, want in ((2.0, 0.5001527311099386), (6.7056, 0.1), (11.0, 0.1), (50.0, 0.05)):
        assert abs(pw15.exceed(pts, T) - want) < 1e-9


def test_shadow_error_never_fails_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(live, "latest_nbm_cycle", lambda now=None, max_back_h=4: datetime(2026, 11, 2, 3, tzinfo=timezone.utc))
    for n, r in (("ingest_nbm_cycle", lambda *a: {}), ("ingest_rtma", lambda *a: {}), ("ingest_metar_day", lambda *a: 0), ("write_latest_bundle", lambda *a: {})):
        monkeypatch.setattr(live, n, r)
    def boom(*a): raise RuntimeError("x")
    monkeypatch.setattr(pw15, "ingest_pw15_shadow", boom)
    monkeypatch.setenv("WIND_PW15_SHADOW", "1")
    s = live.run_hourly(LocalStore(str(tmp_path)), {"lakes": {"g": {"bbox": [-86.5, 34.3, -85.6, 34.9]}}}, datetime(2026, 11, 2, 4, 5, tzinfo=timezone.utc))
    assert s["errors"] == [] and "pw15ShadowError" in s
