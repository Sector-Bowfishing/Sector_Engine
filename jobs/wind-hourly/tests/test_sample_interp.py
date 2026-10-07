import math
from datetime import datetime, timezone
import pytest
from sector_wind.sample import Analysis, Forecast, Observed, WindSample, circular_error, make_sample
from sector_wind.interp import CutoutIndex, blend, blend_wind

T = datetime(2026, 10, 6, 3, tzinfo=timezone.utc)

def test_kind_is_required():
    with pytest.raises(TypeError):
        WindSample(validTime=T, retrievedAt=T, lat=0, lon=0, speedMS=1, dirFromDeg=1, gustMS=None, source="x", decoderVersion="d")
    with pytest.raises(TypeError):
        WindSample("forecast", T, T, 0, 0, 1.0, 10.0, None, "x", "d")   # a bare string is not a kind

def test_calm_has_no_direction_and_missing_gust_stays_missing():
    s = make_sample(Analysis("RTMA-RU", T), T, T, 34, -86, 0.3, 0.0, None, "k", "d")
    assert s.isCalm and s.dirFromDeg is None and s.gustMS is None and s.u == 0.0
    with pytest.raises(ValueError):
        WindSample(Analysis("RTMA-RU", T), T, T, 34, -86, 0.2, 90.0, None, "k", "d")

def test_unknown_speed_is_none_not_zero():
    s = make_sample(Forecast("NBM", "NBM v4.3", T, 3), T, T, 34, -86, float("nan"), float("nan"), None, "k", "d")
    assert s.speedMS is None and s.u is None and not s.isCalm

def test_from_west_moves_east():
    s = make_sample(Observed("HSV", "ASOS", 10.0, "2-min"), T, T, 34, -86, 5.0, 270.0, 7.0, "k", "d")
    assert s.u == pytest.approx(5.0) and s.v == pytest.approx(0.0, abs=1e-9)

def test_359_vs_1_is_2_degrees():
    assert circular_error(359, 1) == pytest.approx(2.0)
    assert circular_error(1, 359) == pytest.approx(2.0)
    assert circular_error(10, 190) == pytest.approx(180.0)

def test_age_uses_init_for_forecasts():
    from datetime import timedelta
    s = make_sample(Forecast("NBM", "NBM v4.3", T, 6), T + timedelta(hours=6), T, 0, 0, 3, 90, None, "k", "d")
    assert s.ageHours(T + timedelta(hours=2)) == pytest.approx(2.0)

def _grid(nx=5, ny=5):
    cells, lat, lon = [], [], []
    for r in range(ny):
        for c in range(nx):
            cells.append(r * nx + c); lat.append(34.0 + 0.0225 * r); lon.append(-87.0 + 0.0272 * c)
    return CutoutIndex(cells, lat, lon, nx), lat, lon

def test_bilinear_is_exact_for_linear_field():
    ci, lat, lon = _grid()
    field = [2.0 + 10 * (la - 34.0) + 5 * (lo + 87.0) for la, lo in zip(lat, lon)]
    w = ci.weights(34.031, -86.95)
    assert w.method == "bilinear"
    assert blend(field, w) == pytest.approx(2.0 + 10 * 0.031 + 5 * 0.05, abs=1e-6)

def test_direction_is_blended_in_uv_not_degrees():
    ci, lat, lon = _grid()
    n = len(lat); spd = [5.0] * n
    dirs = [350.0 if (i % 5) % 2 == 0 else 10.0 for i in range(n)]
    w = ci.weights(34.0112, -86.9864)       # between a 350 column and a 10 column
    s, d = blend_wind(spd, dirs, w)
    assert circular_error(d, 0.0) < 5.0      # degree-averaging would give ~180
