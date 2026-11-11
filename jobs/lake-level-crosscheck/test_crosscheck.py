import datetime as dt
import json

import crosscheck as X

NOW = dt.datetime(2026, 11, 12, 6, 0, tzinfo=dt.timezone.utc)


def fake_get(url, headers=None, timeout=60):
    if "nwps" in url:
        return {"observed": {"primaryUnits": "ft", "data": [{"validTime": f"2026-11-11T{h:02d}:00:00Z", "primary": 354.70} for h in range(24)]
                             + [{"validTime": "2026-11-11T23:30:00Z", "primary": -999}]}}
    base = int(dt.datetime(2026, 11, 11, tzinfo=dt.timezone.utc).timestamp() * 1000)
    return {"units": "ft", "values": [[base + h * 3600000, 354.80, 0] for h in range(24)] + [[base, None, 5]]}


def test_collect_appends_once_and_skips_missing(tmp_path):
    r = X.collect(str(tmp_path), None, NOW, get=fake_get)
    assert r["status"] == "OK" and r["added"] == 48
    assert X.collect(str(tmp_path), None, NOW, get=fake_get)["added"] == 0   # idempotent
    s = X.summarize(str(tmp_path))
    b = s["Lake Barkley|KY"]
    assert b["matchedHours"] == 24 and b["matchedDays"] == 1
    assert b["meanDiffFt"] == -0.1 and b["shareDaysWithinTol"] == 1.0


def test_window_end(tmp_path):
    r = X.collect(str(tmp_path), NOW - dt.timedelta(hours=1), NOW, get=fake_get)
    assert r["status"] == "WINDOW_ENDED" and r["added"] == 0


def test_partial_on_source_error(tmp_path):
    def bad(url, headers=None, timeout=60):
        if "cwms" in url:
            raise RuntimeError("down")
        return fake_get(url)
    r = X.collect(str(tmp_path), None, NOW, get=bad)
    assert r["status"] == "PARTIAL" and r["added"] == 24 and r["errors"]


def test_units_guard():
    try:
        X.read_nwps("KYDK2", get=lambda u, h=None, timeout=60: {"observed": {"primaryUnits": "m", "data": []}})
    except RuntimeError as e:
        assert "units" in str(e)
    else:
        raise AssertionError("expected a units error")
