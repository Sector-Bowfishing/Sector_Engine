import pytest
from sector_wind.validate import _metrics, KT

def test_direction_metrics_are_circular_and_gated():
    pairs = [(5.0, 359.0, None, 5.0, 1.0, None),      # 2 deg
             (5.0, 90.0, None, 5.0, 100.0, None),     # 10 deg
             (1.0, 0.0, None, 1.0, 180.0, None)]      # too light: excluded
    m = _metrics(pairs)
    assert m["dir_n"] == 2 and m["dir_mean"] == pytest.approx(6.0) and m["dir_within22_5"] == 1.0

def test_missing_gust_is_not_zero():
    pairs = [(5.0, 90.0, 8.0, 5.0, 90.0, None), (5.0, 90.0, 12.0, 5.0, 90.0, 11.0)]
    m = _metrics(pairs)
    assert m["gust_n"] == 1 and m["gust_bias_conditional"] == pytest.approx(1.0)

def test_event_pod_far():
    MPH = 0.44704
    pairs = [(16 * MPH, 0, None, 16 * MPH, 0, None), (16 * MPH, 0, None, 5 * MPH, 0, None), (5 * MPH, 0, None, 16 * MPH, 0, None)]
    m = _metrics(pairs)
    assert m["pod_15mph"] == pytest.approx(0.5) and m["far_15mph"] == pytest.approx(0.5)
