"""PT-L4-2026-11-23-v2 runner, offline. Every fixture is hand-built and synthetic: synthetic square 'polygons' around the
directory points, synthetic station ids (SYN-*), synthetic counts and temperatures. No real cast, site or value."""
import csv
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import water_temp_protected_truth_v2 as W  # noqa: E402

P, DIGEST = W.load_protocol()
PTS = {l["lakeId"]: l["point"] for l in P["universe"]["lakes"]}
REQ = "Owner request (Michael, 2099-01-01): synthetic test"


def square(lake_id, half=0.05):
    lat, lon = PTS[lake_id]
    ring = [[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half], [lon - half, lat + half], [lon - half, lat - half]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}}


def registry(ids=None, half=0.05):
    ids = ids or [l["lakeId"] for l in P["universe"]["lakes"]]
    return {i: {"bbox": None, "geometry": square(i, half)} for i in ids}


# ------------------------------------------------------------------------------------------------------- protocol
def test_protocol_is_the_committed_preregistration():
    assert DIGEST == open(W.PROTOCOL + ".sha256").read().split()[0]
    assert P["protocolId"] == "PT-L4-2026-11-23-v2" and len(P["universe"]["lakes"]) == 62
    assert P["minimums"] == {"perLake": 25, "total": 150, "lakes": 4} == {"perLake": W.PER_LAKE, "total": W.TOTAL, "lakes": W.SLOTS}
    assert set(P["frozenLakes"]) <= set(PTS) and P["publication"]["authoritativeScoresUnchanged"] is True


def test_edited_protocol_is_refused(tmp_path):
    q = tmp_path / "p.json"
    shutil.copy(W.PROTOCOL, q)
    shutil.copy(W.PROTOCOL + ".sha256", str(q) + ".sha256")
    q.write_text(q.read_text().replace('"value": 2.5', '"value": 3.5'))
    with pytest.raises(SystemExit, match="REFUSED: protocol sha256"):
        W.load_protocol(str(q))


def test_same_water_ids_are_one_candidate():
    ws = {w["lakeId"]: w for w in W.waters(P)}
    assert len(ws) == 60
    assert ws["Kentucky Lake|KY"]["memberIds"] == ["Kentucky Lake|KY", "Kentucky Lake|TN"] and "Kentucky Lake|TN" not in ws
    assert "Walter F. George / Eufaula|GA" not in ws


# ------------------------------------------------------------------------------------------------------- whitelist
class GuardedRow(list):
    """A CSV row that fails the test if anything reads the temperature-value positions."""
    forbidden = set()

    def __getitem__(self, i):
        if i in self.forbidden:
            raise AssertionError(f"value column {i} was read")
        return super().__getitem__(i)

    def __iter__(self):
        raise AssertionError("the whole row was iterated (that reads the value column)")


def test_result_depth_whitelist_never_reads_or_stores_the_value():
    header = ["OrganizationIdentifier", "MonitoringLocationIdentifier", "ActivityIdentifier", "ActivityStartDate", "CharacteristicName",
              "ResultMeasureValue", "ResultMeasure/MeasureUnitCode", "ResultStatusIdentifier", "ResultDepthHeightMeasure/MeasureValue",
              "ResultDepthHeightMeasure/MeasureUnitCode", "ResultCommentText"]
    GuardedRow.forbidden = {header.index("ResultMeasureValue"), header.index("ResultMeasure/MeasureUnitCode"), header.index("ResultCommentText")}
    rows = [header, GuardedRow(["SYN", "SYN-1", "A1", "2023-06-01", "Temperature, water", "SENTINEL-31.4", "deg C", "Accepted", "0.5", "m", "SENTINEL-NOTE"]),
            GuardedRow(["SYN", "SYN-1", "A2", "2023-06-01", "Temperature, water", "SENTINEL-29.9", "deg C", "Accepted", "3.0", "m", "x"])]
    buf = io.StringIO()
    assert W.strip_result_rows(rows, buf) == 2
    text = buf.getvalue()
    assert "SENTINEL" not in text and "ResultMeasure" not in text
    got = list(csv.DictReader(io.StringIO(text)))
    assert list(got[0]) == [c for c in W.RESULT_DEPTH_COLUMNS if c in header]
    assert got[0]["ResultDepthHeightMeasure/MeasureValue"] == "0.5"
    assert not any(c.startswith("ResultMeasure") for c in W.RESULT_DEPTH_COLUMNS)


def test_census_refuses_a_depth_file_that_carries_a_value_column(tmp_path):
    wqp = tmp_path / "wqp"
    wqp.mkdir()
    (wqp / f"{W.slug('Wheeler|AL')}.resultdepth.csv").write_text("MonitoringLocationIdentifier,ActivityStartDate,ResultMeasureValue\nSYN-1,2023-06-01,20\n")
    st = tmp_path / "st.csv"
    st.write_text(",".join(W.V1.STATION_FIELDS) + "\n")
    ex = tmp_path / "ex.json"
    ex.write_text("{}")
    with pytest.raises(SystemExit, match="never stores values"):
        W.cmd_census(P, DIGEST, str(wqp), str(st), str(ex), "2026-11-22", str(tmp_path / "c.json"))


# ------------------------------------------------------------------------------------------------------- stations
@pytest.mark.parametrize("lake,dlat,sid,name,cls,expect_lake", [
    ("Wheeler|AL", 0.0, "21AWIC-TENR-296", "SYNTHETIC station", "MAIN_BODY", "Wheeler|AL"),             # river mile from the ADEM id
    ("Wheeler|AL", 0.0, "SYN-1", "SYNTHETIC Tennessee River TRM 348.0", "TAILWATER", "Wheeler|AL"),      # 1 mi below Guntersville Dam
    ("Wheeler|AL", 0.0, "SYN-2", "SYNTHETIC Elk River embayment", "EMBAYMENT", "Wheeler|AL"),
    ("Wheeler|AL", 0.0, "SYN-3", "SYNTHETIC Flint River arm", "EMBAYMENT", "Wheeler|AL"),                 # another river on a TVA main-stem lake
    ("Logan Martin|AL", 0.0, "SYN-4", "SYNTHETIC Coosa River at dam", "UNCLASSIFIED", "Logan Martin|AL"),  # another river off the Tennessee: review
    ("Logan Martin|AL", 0.0, "SYN-5", "SYNTHETIC Logan Martin Lake near dam", "MAIN_BODY", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.0, "SYN-6", "SYNTHETIC below Logan Martin Dam", "TAILWATER", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.0, "SYN-7", "SYNTHETIC station", "UNCLASSIFIED", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.5, "SYN-8", "SYNTHETIC station", "OUTSIDE", None),
])
def test_station_classes(lake, dlat, sid, name, cls, expect_lake):
    reg = registry([lake])
    lat, lon = PTS[lake]
    got, lid, why = W.classify(P, reg, sid, name, lat + dlat, lon)
    assert got == cls, why
    assert lid == expect_lake


def test_overlapping_polygons_are_resolved_by_river_mile_or_left_ambiguous():
    reg = {"Wilson|AL": {"bbox": None, "geometry": square("Wilson|AL", 0.3)}, "Pickwick Lake|TN": {"bbox": None, "geometry": square("Wilson|AL", 0.3)}}
    lat, lon = PTS["Wilson|AL"]
    assert W.classify(P, reg, "21AWIC-TENR-260", "SYNTHETIC forebay", lat, lon)[:2] == ("MAIN_BODY", "Wilson|AL")
    assert W.classify(P, reg, "SYN-9", "SYNTHETIC forebay", lat, lon)[0] == "AMBIGUOUS"


def test_polygon_tolerance_and_holes():
    ring = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    hole = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6], [0.4, 0.4]]
    g = {"type": "Polygon", "coordinates": [ring, hole]}
    assert W.in_polygon(0.2, 0.2, g) and not W.in_polygon(0.5, 0.5, g, 0.0)
    assert W.in_polygon(1.0005, 0.5, g) and not W.in_polygon(1.01, 0.5, g)       # ~55 m out: inside tolerance; ~1.1 km: not


# ------------------------------------------------------------------------------------------------------- exclusions
def test_exclusion_rules():
    reg = registry(half=0.3)
    reg["Weiss|AL"] = {"bbox": None, "geometry": None}
    g_lat, g_lon = PTS["Guntersville|AL"]
    m_lat, m_lon = PTS["Logan Martin|AL"]
    s_lat, s_lon = PTS["Seminole|GA"]
    sites = [{"site": "SYN-LK-NEAR", "siteType": "LK", "lat": m_lat + 0.05, "lon": m_lon, "has00010": "True", "m0Calibration": "False"},
             {"site": "SYN-LK-FAR-INSIDE", "siteType": "LK", "lat": s_lat + 0.28, "lon": s_lon, "has00010": "True", "m0Calibration": "False"},
             {"site": "SYN-ST-NEAR", "siteType": "ST", "lat": g_lat + 0.01, "lon": g_lon, "has00010": "True", "m0Calibration": "False"},
             {"site": "SYN-CAL", "siteType": "ST", "lat": PTS["Lay|AL"][0], "lon": PTS["Lay|AL"][1], "has00010": "True", "m0Calibration": "True"}]
    ex = W.exclusions(P, reg, sites, {"Jordan|AL"}, W.bound_lakes(), set())
    assert ex["Guntersville|AL"] == []                                       # a stream site is not a resolver lake gauge
    assert any(e.startswith("RESOLVER_SENSOR: USGS LK") for e in ex["Logan Martin|AL"])
    assert ex["Seminole|GA"] == ["WT_SAT_1: USGS LK 00010 site SYN-LK-FAR-INSIDE inside the polygon"]   # ~31 km away, inside
    assert ex["Lay|AL"] == ["M0_TUNING: calibration site SYN-CAL"]
    assert ex["Jordan|AL"] == ["M0_TUNING: directory id in the M0 calibration set"]
    assert ex["Okatibbee Lake|MS"] == ["RESOLVER_SENSOR: tempSensor binding"]
    assert ex["Weiss|AL"] == ["NO_GEOMETRY"]
    assert W.exclusions(P, reg, [], set(), set(), {"Wheeler|AL"})["Wheeler|AL"] == ["WT_SAT_1: in the committed WT-SAT-1 list"]


def test_unresolved_calibration_sites_are_reported(tmp_path):
    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps({"rows": [{"sensor": "usgs:SYN-A", "inM0CalibrationSet": True}, {"sensor": "usgs:SYN-B", "inM0CalibrationSet": True},
                                        {"sensor": "usgs:SYN-C", "inM0CalibrationSet": False}]}))
    sites = [{"site": "SYN-A", "lat": "34", "lon": "-86", "m0Calibration": "True"}]
    assert W.unresolved_calibration(sites, str(cal)) == ["SYN-B"]


# ------------------------------------------------------------------------------------------------------- census and selection
def stations_for(lakes):
    rows = {}
    for i, lid in enumerate(lakes):
        lat, lon = PTS[lid]
        rows[f"SYN-{i}"] = {"MonitoringLocationIdentifier": f"SYN-{i}", "LatitudeMeasure": str(lat), "LongitudeMeasure": str(lon),
                            "lakeId": lid, "class": "MAIN_BODY"}
    return rows


def dates(n, start="2022-04-01"):
    d0 = dt.date.fromisoformat(start)
    return [(d0 + dt.timedelta(days=7 * i)).isoformat() for i in range(n)]


def depth_rows(sid, n, start="2022-04-01"):
    return [{"MonitoringLocationIdentifier": sid, "ActivityStartDate": d, "CharacteristicName": "Temperature, water",
             "ResultStatusIdentifier": "Accepted", "ResultDepthHeightMeasure/MeasureValue": dep, "ResultDepthHeightMeasure/MeasureUnitCode": "m"}
            for d in dates(n, start) for dep in ("0.3", "4.0")]


def test_census_counts_result_depth_and_reports_the_frozen_window():
    st = stations_for(["Wheeler|AL"])
    rows = depth_rows("SYN-0", 20, "2025-12-01") + [{**r, "CharacteristicName": "pH"} for r in depth_rows("SYN-0", 3, "2021-02-01")]
    acts = [{"MonitoringLocationIdentifier": "SYN-0", "ActivityStartDate": "2021-03-01", "ActivityDepthHeightMeasure/MeasureValue": "1.0",
             "ActivityDepthHeightMeasure/MeasureUnitCode": "m"}]
    res = W.census(P, acts, rows, st, "2026-11-22")
    wh = res["waters"]["Wheeler|AL"]
    assert wh["qualifyingCasts"] == 21                           # 1 from activity metadata + 20 from result depth; pH rows ignored
    assert wh["qualifyingCastsToFrozenHoldoutEnd"] == 1 + sum(d <= "2026-06-30" for d in dates(20, "2025-12-01"))
    assert res["excluded"]["otherCharacteristic"] == 6


def census_with(counts):
    return {"waters": {lid: {"qualifyingCasts": n, "castKeys": [f"{lid}|SYN-{W.slug(lid)}-{i}|{d}" for i, d in enumerate(dates(n))]}
                       for lid, n in counts.items()}}


def test_selection_keeps_qualifying_frozen_lakes_and_replaces_short_ones_by_count_only():
    counts = {"Guntersville|AL": 36, "Wheeler|AL": 22, "Wilson|AL": 0, "Pickwick Lake|TN": 0,
              "Logan Martin|AL": 80, "Lay|AL": 40, "Jordan|AL": 40, "Weiss|AL": 120, "Seminole|GA": 30}
    excl = {"Weiss|AL": ["RESOLVER_SENSOR: x"]}
    sel = W.select(P, census_with(counts), excl)
    assert sel["retained"] == ["Guntersville|AL"]
    tie = sorted(["Lay|AL", "Jordan|AL"], key=lambda l: hashlib.sha256(l.encode()).hexdigest())
    assert sel["replacements"] == ["Logan Martin|AL"] + tie                # Weiss excluded; the 40/40 tie broken by sha256(lakeId)
    assert sel["outcome"] == "SELECTED" and sel["total"] == 36 + 80 + 40 + 40
    assert sel["frozenLakeStatus"]["Wheeler|AL"] == "22 casts"


def test_selection_is_insufficient_when_four_lakes_or_150_are_not_reached():
    assert W.select(P, census_with({"Guntersville|AL": 36, "Lay|AL": 30, "Jordan|AL": 26}), {})["outcome"] == "INSUFFICIENT_TRUTH"
    s = W.select(P, census_with({"Guntersville|AL": 36, "Lay|AL": 30, "Jordan|AL": 26, "Seminole|GA": 25}), {})
    assert s["outcome"] == "INSUFFICIENT_TRUTH" and s["shortfall"] == {"lakesWith25": 4, "total": 117}
    assert W.select(P, census_with({"Guntersville|AL": 36}), {"Guntersville|AL": ["M0_TUNING: x"]})["retained"] == []


# ------------------------------------------------------------------------------------------------------- step B
SEL_COUNTS = {"Guntersville|AL": 36, "Logan Martin|AL": 40, "Lay|AL": 40, "Jordan|AL": 40}


def selection():
    return {"protocolSha256": DIGEST, **W.select(P, census_with(SEL_COUNTS), {})}


def test_step_b_gate():
    sel = selection()
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.require_step_b(sel, DIGEST, None)
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.require_step_b(sel, DIGEST, "Claude request (under Owner approval 2026-11-22)")
    with pytest.raises(SystemExit, match="different protocol"):
        W.require_step_b(sel, "0" * 64, REQ)
    with pytest.raises(SystemExit, match="not SELECTED"):
        W.require_step_b({**sel, "outcome": "INSUFFICIENT_TRUTH"}, DIGEST, REQ)
    W.require_step_b(sel, DIGEST, REQ)


def test_step_b_fetches_only_counted_casts_one_site_date_each():
    sel = selection()
    qs = W.result_queries(sel)
    assert len(qs) == sum(SEL_COUNTS.values())
    for q in qs:
        assert q["params"]["startDateLo"] == q["params"]["startDateHi"] and q["params"]["siteid"] == q["siteid"]
        assert "bBox" not in q["params"]
    assert {(q["lakeId"], q["siteid"], q["date"]) for q in qs} == set(W.counted_casts(sel))


def forcing(air_c):
    d0, d1 = dt.date(2022, 1, 1), dt.date(2023, 12, 31)
    days = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    n = len(days)
    return {"daily": {"time": days, "temperature_2m_mean": [air_c] * n, "shortwave_radiation_sum": [0.0] * n,
                      "wind_speed_10m_mean": [5.0] * n, "relative_humidity_2m_mean": [0.0] * n}}


def test_compare_on_the_selection():
    sel = selection()
    results = [{"MonitoringLocationIdentifier": s, "ActivityStartDate": d, "CharacteristicName": "Temperature, water", "ResultStatusIdentifier": "Accepted",
                "ResultMeasureValue": "21.0", "ResultMeasure/MeasureUnitCode": "deg C", "ResultDepthHeightMeasure/MeasureValue": "0.5",
                "ResultDepthHeightMeasure/MeasureUnitCode": "m"} for _, s, d in W.counted_casts(sel)]
    f = {lid: forcing(20.0) for lid in SEL_COUNTS}
    res = W.compare(P, sel, results, f)                       # M0 == 20 C (Teq == air), truth 21 C: error -1 C everywhere
    assert res["outcome"] == "PASS" and res["pooledEqualLakeRmseC"] == 1.0 and res["authoritativeScoresUnchanged"] is True
    for r in results:
        if r["MonitoringLocationIdentifier"].startswith("SYN-") and r["ActivityStartDate"] < "2022-09-01":
            r["ResultMeasureValue"] = "26.0"
    assert W.compare(P, sel, results, f)["outcome"] == "FAIL"


def test_fetch_refuses_unlisted_sources():
    for url in ("https://example.com/data/x", "https://storage.googleapis.com/other-bucket/x", "http://www.waterqualitydata.us/data/x"):
        with pytest.raises(SystemExit, match="not an allowlisted source"):
            W._get_bytes(url)


def test_cli_verify(capsys):
    assert W.main(["verify"]) == 0
    assert json.loads(capsys.readouterr().out)["sha256"] == DIGEST
