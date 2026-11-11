import csv
import datetime as dt
import io
import json
import os

import h1_shadow as H

HDR = "ActivityStartDate,CharacteristicName,ResultMeasureValue,ResultMeasure/MeasureUnitCode,ResultDetectionConditionText,MeasureQualifierCode,ResultStatusIdentifier\n"


def row(d, v, u="ft", det="", q="", st="Accepted"):
    b = io.StringIO()
    csv.writer(b, lineterminator="\n").writerow([d, "Depth, Secchi disk depth", v, u, det, q, st])
    return b.getvalue()


def test_band_edges():
    assert [H.band(x) for x in (1.49, 1.5, 2.99, 3.0, 5.99, 6.0)] == ["V0", "V1", "V1", "V2", "V2", "V3"]


def test_season():
    assert H.season(4) == "warm" and H.season(10) == "warm" and H.season(11) == "cool" and H.season(3) == "cool"


def test_parse_drops_censored_rejected_units():
    text = HDR + row("2024-06-01", 1, "m") + row("2024-06-02", 3, "ft", det="Visible to bottom") + row("2024-06-03", 4, st="Rejected") \
        + row("2024-06-04", 70) + row("2024-06-05", 30, "in")
    rows = H.parse_rows(text)
    assert [d for d, _ in rows] == ["2024-06-01", "2024-06-05"]
    assert abs(rows[0][1] - 3.28084) < 1e-6 and abs(rows[1][1] - 2.5) < 1e-9


def test_lake_day_median_across_stations():
    assert H.lake_days([("2024-06-01", 2.0), ("2024-06-01", 4.0), ("2024-06-02", 1.0)]) == {"2024-06-01": 3.0, "2024-06-02": 1.0}


def test_h1_window_never_sees_graded_year_and_widens():
    ld = {f"{y}-06-0{i}": 4.0 for y in (2019, 2020) for i in range(1, 4)}
    ld["2026-06-01"] = 10.0                      # the graded year itself: must be ignored
    r = H.h1(ld, 2026, "warm")
    assert r["status"] == "ANSWER" and r["band"] == "V2" and r["years"] == [2019, 2025]   # widened to Y-7
    assert H.h1({"2024-06-01": 4.0}, 2026, "warm")["status"] == "UNKNOWN"
    assert H.h1(ld, 2026, "cool")["status"] == "UNKNOWN"


def test_run_offline_with_fake_fetcher(tmp_path):
    text = HDR + "".join(row(f"{y}-0{m}-1{i}", 4.0) for y in (2023, 2024, 2025) for m in (5, 7) for i in range(2))
    doc = H.run(["Guntersville|AL", "Nowhere|ZZ"], str(tmp_path / "out"), str(tmp_path / "cache"), None, dt.date(2026, 7, 1), 5.0,
                fetcher=lambda *a: text)
    assert doc["lane"] == "SHADOW" and doc["customerVisible"] is False
    g = doc["lakes"][0]
    assert g["status"] == "ANSWER" and g["h1"]["warm"]["band"] == "V2"
    assert doc["lakes"][1]["status"] == "UNKNOWN"
    assert json.load(open(tmp_path / "out" / "h1-shadow.json"))["summary"]["answered"] == 1
    assert os.path.exists(tmp_path / "cache" / "Guntersville_AL.csv")


def test_sites_file_is_passed_to_fetcher(tmp_path):
    seen = {}

    def f(lat, lon, r, start, sites=None):
        seen["sites"] = sites
        return HDR
    doc = H.run(["Guntersville|AL"], str(tmp_path / "o"), None, None, dt.date(2026, 7, 1), 5.0, fetcher=f, sites={"Guntersville|AL": ["A-1", "B-2"]})
    assert seen["sites"] == ["A-1", "B-2"] and doc["lakes"][0]["stationSelection"] == "sites-file"
