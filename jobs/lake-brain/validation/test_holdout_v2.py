"""Harness checks for holdout_v2.py on SYNTHETIC series only (never on the research data): the machinery counts what the pre-registration says it counts."""
import datetime as dt
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import holdout_v2 as H  # noqa: E402
import rules_v2 as R  # noqa: E402


def synth(y0, y1, f):
    out = {}
    d = dt.date(y0, 1, 1)
    while d.year <= y1:
        out[d] = H.r2f(f(d))
        d += dt.timedelta(days=1)
    return out


def test_r2f_matches_rules_round():
    for x in (0.125, -0.125, 1.005, 593.8049, 100.5):
        assert H.r2f(x) == pytest.approx(float(R.r2(x)))


def test_in_move_windows():
    base = dt.date(2020, 3, 10)
    daily = {base + dt.timedelta(days=i): 100.0 for i in range(-5, 8)}
    for i in range(3, 8):
        daily[base + dt.timedelta(days=i)] = 100.6        # a +0.6 ft step between day 2 and day 3 -> windows [s, s+3] with s in 0..2 straddle it
    assert H.in_move(daily, base + dt.timedelta(days=2)) is True        # window s=0..3 contains it and |L(s+3)-L(s)| = 0.6
    assert H.in_move(daily, base + dt.timedelta(days=-4)) is False
    assert H.in_move(daily, base + dt.timedelta(days=7)) is False       # windows starting at day 4..7 see only the plateau


def test_flat_lake_is_all_stable_with_no_label_changes_and_no_rapid():
    daily = synth(2000, 2025, lambda d: 500.0)
    out = H.run_lake({"lakeId": "Flat|XX", "daily": daily, "regulated": True})
    assert out["testYears"] == [2021, 2022, 2023, 2024, 2025]
    for y in out["years"]:
        assert y["tier"] == "FULL" and y["trainYears"] >= 15
        assert y["changes"] == 0 and y["stable"] == y["labelled"] and y["hcRapid"] == 0 and y["stableInMove"] == 0
        assert y["cov"] == 1.0                                          # constant series: every day inside [p10, p90]


def test_iid_noise_is_calibrated_and_ha_reference_is_built():
    rng = np.random.default_rng(7)
    seasonal = lambda d: 500 + 2 * np.sin(d.timetuple().tm_yday / 365 * 2 * np.pi)  # noqa: E731
    vals = {}
    d = dt.date(1990, 1, 1)
    while d.year <= 2025:
        vals[d] = H.r2f(seasonal(d) + rng.normal(0, 1.0))
        d += dt.timedelta(days=1)
    out = H.run_lake({"lakeId": "Iid|XX", "daily": vals, "regulated": True})
    covs = [y["cov"] for y in out["years"]]
    assert 0.7 < np.mean(covs) < 0.9
    for y in out["years"]:
        assert y["loyoN"] == 30 and y["loyoLo"] <= y["loyoHi"] and "haPass" in y
        out_share = y["outside"] / y["days"]
        assert out_share < 0.08                                         # nominal 0.04
    # day-to-day noise of sd 1 ft makes the lake very choppy: trend labels change a lot and RAPID fires on the 0.25 ft floor
    assert sum(y["changes"] for y in out["years"]) > 0 and sum(y["hcRapid"] for y in out["years"]) > 0


def test_ramp_is_rising_and_young_history_is_not_tested():
    daily = synth(2018, 2025, lambda d: 500 + 0.2 * (d - dt.date(2018, 1, 1)).days)
    out = H.run_lake({"lakeId": "Ramp|XX", "daily": daily, "regulated": False})
    assert out["testYears"] == [2021, 2022, 2023, 2024, 2025]
    assert out["years"][0]["trainYears"] == 3 and out["years"][0]["tier"] == "NONE" and "days" not in out["years"][0]
    y = out["years"][-1]
    assert y["trainYears"] == 7 and y["tier"] == "PROVISIONAL"
    assert y["stable"] == 0                                              # +0.2 ft/day is above both floors


def test_aggregate_smoke_and_thresholds_are_the_preregistered_ones():
    assert (H.HA_LAKE_PASS_MIN, H.HA_COV_LO, H.HA_COV_HI) == (0.80, 0.75, 0.85) and H.HB_TAIL_MAX == 0.06
    assert H.HC_POOLED == (0.03, 0.08) and H.HC_LAKE_RANGE == (0.02, 0.09) and H.HC_LAKE_SHARE_MIN == 0.70
    assert H.HD_CHANGE_MAX == 0.30 and H.HD_STABLE_IN_MOVE_MAX == 0.08 and H.MOVE_FT == 0.5 and H.TEST_YEARS == 5
    daily = synth(1995, 2025, lambda d: 500 + 0.001 * d.toordinal() % 3)
    rec = {"lakeId": "A|XX", "daily": daily, "regulated": True, "provider": "usgs", "poolBasis": "fullPool", "lakeClass": "R3", "capability": "DIRECT_LAKE_GAUGE"}
    lake = H.run_lake(rec)
    agg = H.aggregate([lake], {"A|XX": rec})
    assert set(agg) == {"H-A", "H-B", "H-C", "H-D"}
    assert agg["H-A"]["lakesTested"] == 1 and agg["H-B"]["fullLakeYears"] == 5
