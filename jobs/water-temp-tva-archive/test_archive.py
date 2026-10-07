"""Tests for the Water Temp TVA archiver. Run: python -m pytest jobs/water-temp-tva-archive -q"""
import datetime as dt
import json

import pytest

import archive as A

OBS = [{"Day": "10/06/2026", "Time": "11 PM CDT", "ReservoirElevation": "554.29",
        "TailwaterElevation": "507.07", "AverageHourlyDischarge": "63,258"},
       {"Day": "10/07/2026", "Time": "12 AM CDT", "ReservoirElevation": "554.27",
        "TailwaterElevation": "507.06", "AverageHourlyDischarge": "63,166"}]
PRED = [{"Day": "10/07/2026", "AverageInflow": "31,020", "MidnightElevation": 553.87, "AverageOutflow": "39,188"}]
NOW = dt.datetime(2026, 10, 7, 5, 20, tzinfo=dt.timezone.utc)


def fetcher(obs=OBS, pred=PRED):
    def f(url):
        return json.dumps(obs if "observed" in url else pred).encode()
    return f


def load(tmp, key):
    return json.loads((tmp / key).read_text())


def test_time_parsing_midnight_noon_and_zone():
    assert A.local_hour("10/07/2026", "12 AM CDT").isoformat() == "2026-10-07T00:00:00-05:00"
    assert A.local_hour("10/07/2026", "12 PM CDT").hour == 12
    assert A.local_hour("01/07/2026", "3 PM CST").isoformat() == "2026-01-07T15:00:00-06:00"


def test_numbers_with_thousands_separator_and_numeric():
    assert A.number("63,258") == 63258.0 and A.number(553.87) == 553.87
    with pytest.raises(A.SchemaError):
        A.number("n/a")


def test_archives_hours_into_local_dates_and_raw(tmp_path):
    s = A.archive_dam(A.LocalStore(str(tmp_path)), "wt", "WHLA1", fetcher(), NOW)
    assert s["newObservedHours"] == 2 and s["predictedStored"]
    d6 = load(tmp_path, "wt/WHLA1/2026-10-06.json")
    assert list(d6["observed"]) == ["2026-10-06T23:00:00-05:00"]
    h = d6["observed"]["2026-10-06T23:00:00-05:00"]
    assert h["parsed"]["avgHourlyDischargeCfs"] == 63258.0 and h["raw"] == OBS[0]
    assert h["parsed"]["utcTime"] == "2026-10-07T04:00:00Z"
    assert (tmp_path / "wt/raw/WHLA1/observed/2026-10-07T05Z.json").read_bytes() == json.dumps(OBS).encode()


def test_rerun_is_idempotent(tmp_path):
    st = A.LocalStore(str(tmp_path))
    A.archive_dam(st, "wt", "WLSA1", fetcher(), NOW)
    before = (tmp_path / "wt/WLSA1/2026-10-07.json").read_bytes()
    s = A.archive_dam(st, "wt", "WLSA1", fetcher(), NOW)
    assert s["newObservedHours"] == 0 and s["revisions"] == 0 and not s["predictedStored"]
    assert (tmp_path / "wt/WLSA1/2026-10-07.json").read_bytes() == before


def test_changed_value_is_kept_as_revision_never_overwritten(tmp_path):
    st = A.LocalStore(str(tmp_path))
    A.archive_dam(st, "wt", "PICT1", fetcher(), NOW)
    changed = [dict(OBS[0], AverageHourlyDischarge="60,000"), OBS[1]]
    s = A.archive_dam(st, "wt", "PICT1", fetcher(obs=changed), NOW + dt.timedelta(hours=1))
    assert s["revisions"] == 1
    d6 = load(tmp_path, "wt/PICT1/2026-10-06.json")
    assert d6["observed"]["2026-10-06T23:00:00-05:00"]["raw"]["AverageHourlyDischarge"] == "63,258"
    assert d6["revisions"][0]["raw"]["AverageHourlyDischarge"] == "60,000"


def test_no_gap_filling(tmp_path):
    A.archive_dam(A.LocalStore(str(tmp_path)), "wt", "GVDA1", fetcher(obs=[OBS[0]]), NOW)
    d6 = load(tmp_path, "wt/GVDA1/2026-10-06.json")
    assert len(d6["observed"]) == 1


@pytest.mark.parametrize("bad", [
    [],                                                     # empty response
    [dict(OBS[0], Extra="x")],                              # new key
    [{k: v for k, v in OBS[0].items() if k != "Time"}],     # missing key
    [dict(OBS[0], Time="23:00")],                           # time format changed
    {"rows": OBS},                                          # wrapper object
])
def test_schema_change_fails_loudly_and_writes_nothing(tmp_path, bad):
    with pytest.raises(A.SchemaError):
        A.archive_dam(A.LocalStore(str(tmp_path)), "wt", "WHLA1", fetcher(obs=bad), NOW)
    assert not any(tmp_path.rglob("*.json"))


def test_predicted_schema_change_fails(tmp_path):
    with pytest.raises(A.SchemaError):
        A.archive_dam(A.LocalStore(str(tmp_path)), "wt", "WHLA1", fetcher(pred=[{"Day": "10/07/2026"}]), NOW)


def test_main_returns_nonzero_when_a_dam_fails(tmp_path, monkeypatch):
    def f(url):
        if "PICT1" in url:
            raise RuntimeError("HTTP 503")
        return fetcher()(url)
    monkeypatch.setattr(A, "http_fetch", f)
    assert A.main(["--local-dir", str(tmp_path), "--dams", "WHLA1,PICT1"]) == 1
    assert (tmp_path / "water-temp/tva/WHLA1/2026-10-07.json").exists() or any(tmp_path.rglob("WHLA1/*.json"))
