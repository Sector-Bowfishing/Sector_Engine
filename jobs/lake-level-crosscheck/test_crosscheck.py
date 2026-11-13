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


def test_format_change_in_one_source_is_partial_not_fatal(tmp_path):
    def odd(url, headers=None, timeout=60):
        if "nwps" in url:
            return {"observed": {"primaryUnits": "ft", "data": [{"primary": 354.7}]}}  # no validTime: skipped
        return []                                                                       # not a dict: AttributeError
    r = X.collect(str(tmp_path), None, NOW, get=odd)
    assert r["status"] == "PARTIAL" and r["added"] == 0 and any("AttributeError" in e for e in r["errors"])


def test_cwms_units_and_quality(tmp_path):
    base = int(dt.datetime(2026, 11, 11, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert X.read_cwms("LRN", "x", NOW, get=lambda u, h=None, timeout=60: {"units": "ft", "values": [[base, 1.0, 0], [base + 3600000, 2.0, 17]]}) == [("2026-11-11T00:00:00Z", 1.0)]
    try:
        X.read_cwms("LRN", "x", NOW, get=lambda u, h=None, timeout=60: {"values": []})
    except RuntimeError as e:
        assert "units" in str(e)
    else:
        raise AssertionError("missing units must fail")


def test_naive_until_and_offset_times(tmp_path):
    assert X.main(["collect", "--data", str(tmp_path), "--until", "2000-01-01"]) == 0
    assert X.norm_time("2026-11-11T17:00:00-05:00") == "2026-11-11T22:00:00Z"


def test_summarize_skips_bad_lines_and_short_days(tmp_path):
    X.collect(str(tmp_path), None, NOW, get=fake_get)
    with open(tmp_path / "2026-11.jsonl", "a") as f:
        f.write('{"lake": "Lake Barkley|KY"}\n')
        f.write('{"lake": "Lake Barkley|KY", "role": "engine", "obsTime": "2026-11-12T01:00:00Z", "valueFt": 1}\n')
    s = X.summarize(str(tmp_path))["Lake Barkley|KY"]
    assert s["matchedDays"] == 1 and s["shareDaysWithinTol"] == 1.0


def test_cwms_null_entries_and_quality_bits():
    base = int(dt.datetime(2026, 11, 11, tzinfo=dt.timezone.utc).timestamp() * 1000)
    vals = [None, [None, 1.0, 0], [base, 1.0, 3 | 32], [base + 3600000, 2.0, -2147483645], [base + 7200000, 3.0, 9]]
    got = X.read_cwms("LRN", "x", NOW, get=lambda u, h=None, timeout=60: {"units": "ft", "values": vals})
    assert [v for _, v in got] == [1.0, 2.0]
