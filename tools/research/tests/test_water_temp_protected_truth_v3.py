"""PT-L4-2026-11-23-v3 runner, offline. Every fixture is hand-built and synthetic: synthetic square 'polygons' around the
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
import water_temp_protected_truth_v3 as W  # noqa: E402

P, DIGEST = W.load_protocol()
PTS = {l["lakeId"]: l["point"] for l in P["universe"]["lakes"]}
REQ = "Owner request (Michael, 2099-01-01): synthetic test"
V2 = os.path.join(W.REPO, "docs", "brains", "water-temp-protected-truth-v2", "PT-L4-2026-11-23-v2.protocol.json")


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
    assert P["protocolId"] == "PT-L4-2026-11-23-v3" and len(P["universe"]["lakes"]) == 62
    assert P["minimums"] == {"perLake": 25, "total": 150, "lakes": 4} == {"perLake": W.PER_LAKE, "total": W.TOTAL, "lakes": W.SLOTS}
    assert P["passMark"]["pooledEqualLakeRmseC"]["value"] == P["passMark"]["perLakeRmseC"]["value"] == W.RMSE_MARK
    assert "INSUFFICIENT_PAIRED" not in json.dumps(P["passMark"]["outcomes"])


def test_v2_is_kept_byte_identical_and_refused():
    assert W.V1.sha256_file(V2) == "e02e2e08740767dec4720a610c112010eb78ad73ad1b223b14365489a499867d"
    with pytest.raises(SystemExit, match="executes PT-L4-2026-11-23-v3 only"):
        W.load_protocol(V2)


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


# ------------------------------------------------------------------------------------------------------- whitelists
class GuardedRow(list):
    """A CSV row that fails the test if the runner indexes a forbidden position or iterates the row."""
    forbidden = set()

    def __getitem__(self, i):
        if i in self.forbidden:
            raise AssertionError(f"forbidden column {i} was indexed")
        return super().__getitem__(i)

    def __iter__(self):
        raise AssertionError("the whole row was iterated")


def test_result_depth_whitelist_never_indexes_or_stores_the_value():
    header = ["OrganizationIdentifier", "MonitoringLocationIdentifier", "ActivityIdentifier", "ActivityStartDate", "CharacteristicName",
              "ResultMeasureValue", "ResultMeasure/MeasureUnitCode", "ResultStatusIdentifier", "ResultDepthHeightMeasure/MeasureValue",
              "ResultDepthHeightMeasure/MeasureUnitCode", "ResultCommentText"]
    GuardedRow.forbidden = {header.index("ResultMeasureValue"), header.index("ResultMeasure/MeasureUnitCode"), header.index("ResultCommentText")}
    rows = [header, GuardedRow(["SYN", "SYN-1", "A1", "2023-06-01", "Temperature, water", "SENTINEL-31.4", "deg C", "Accepted", "0.5", "m", "SENTINEL-NOTE"])]
    buf = io.StringIO()
    assert W.strip_result_rows(rows, buf) == 1
    assert "SENTINEL" not in buf.getvalue() and "ResultMeasure" not in buf.getvalue()
    assert not any(c.startswith("ResultMeasure") for c in W.RESULT_DEPTH_COLUMNS)


def test_station_and_activity_metadata_are_stored_as_whitelisted_columns_only():
    raw = ("OrganizationIdentifier,MonitoringLocationIdentifier,ActivityIdentifier,ActivityStartDate,ActivityCommentText,"
           "ActivityDepthHeightMeasure/MeasureValue,ActivityDepthHeightMeasure/MeasureUnitCode\n"
           "SYN,SYN-1,A1,2023-06-01,SENTINEL surface 24.1 C,0.5,m\n").encode()
    out = W._stripped_csv(raw, W.ACTIVITY_COLUMNS).decode()
    assert "SENTINEL" not in out and "Comment" not in out and "A1" in out
    for cols in (W.STATION_COLUMNS, W.ACTIVITY_COLUMNS):
        assert not any("Comment" in c or c.startswith("ResultMeasure") for c in cols)


def test_usgs_metadata_keeps_whitelisted_properties_only():
    body = json.dumps({"features": [{"id": "USGS-SYN1", "geometry": {"type": "Point", "coordinates": [-86, 34]},
                                     "properties": {"monitoring_location_id": "USGS-SYN1", "site_type_code": "LK", "parameter_code": "00010",
                                                    "last_value": "SENTINEL-21.5", "statistic_id": "x"}}]}).encode()
    out = W.strip_usgs(body).decode()
    assert "SENTINEL" not in out and "last_value" not in out and '"LK"' in out


def test_census_refuses_a_depth_file_with_a_non_whitelisted_column(tmp_path):
    wqp = tmp_path / "wqp"
    wqp.mkdir()
    (wqp / f"{W.slug('Wheeler|AL')}.resultdepth.csv").write_text("MonitoringLocationIdentifier,ActivityStartDate,ResultMeasureValue\nSYN-1,2023-06-01,20\n")
    st = tmp_path / "st.csv"
    st.write_text(",".join(W.V1.STATION_FIELDS) + "\n")
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps({"protocolSha256": DIGEST, "exclusions": {}}))
    with pytest.raises(SystemExit, match="non-whitelisted column"):
        W.cmd_census(P, DIGEST, str(wqp), str(st), str(st), W.V1.sha256_file(str(st)), str(ex), "2026-11-22", str(tmp_path / "c.json"))


def test_fetch_refuses_unlisted_sources_and_redirects():
    for url in ("https://example.com/data/x", "https://storage.googleapis.com/other-bucket/x", "http://www.waterqualitydata.us/data/x"):
        with pytest.raises(SystemExit, match="not an allowlisted source"):
            W._get_bytes(url)
    with pytest.raises(SystemExit, match="not an allowlisted source"):
        W._CheckedRedirect().redirect_request(None, None, 302, "Found", {}, "https://evil.example/data/x")


# ------------------------------------------------------------------------------------------------------- stations
@pytest.mark.parametrize("lake,dlat,sid,name,cls,expect_lake", [
    ("Wheeler|AL", 0.0, "21AWIC-TENR-296", "SYNTHETIC station", "MAIN_BODY", "Wheeler|AL"),
    ("Wheeler|AL", 0.0, "SYN-1", "SYNTHETIC Tennessee River TRM 348.0", "TAILWATER", "Wheeler|AL"),
    ("Wheeler|AL", 0.0, "SYN-2", "SYNTHETIC Elk River embayment", "EMBAYMENT", "Wheeler|AL"),
    ("Wheeler|AL", 0.0, "SYN-3", "SYNTHETIC Flint River arm", "EMBAYMENT", "Wheeler|AL"),
    ("Logan Martin|AL", 0.0, "SYN-4", "SYNTHETIC Coosa River at dam", "UNCLASSIFIED", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.0, "SYN-5", "SYNTHETIC Logan Martin Lake near dam", "MAIN_BODY", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.0, "SYN-6", "SYNTHETIC below Logan Martin Dam", "TAILWATER", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.0, "SYN-7", "SYNTHETIC station", "UNCLASSIFIED", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.5, "SYN-8", "SYNTHETIC station", "OUTSIDE", None),
])
def test_station_classes(lake, dlat, sid, name, cls, expect_lake):
    lat, lon = PTS[lake]
    got, lid, why = W.classify(P, registry([lake]), sid, name, lat + dlat, lon)
    assert got == cls, why
    assert lid == expect_lake


def test_polygon_tolerance_and_holes():
    ring = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
    hole = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6], [0.4, 0.4]]
    g = {"type": "Polygon", "coordinates": [ring, hole]}
    assert W.in_polygon(0.2, 0.2, g) and not W.in_polygon(0.5, 0.5, g, 0.0)
    assert W.in_polygon(1.0005, 0.5, g) and not W.in_polygon(1.01, 0.5, g)


def _write_stations(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=W.V1.STATION_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return str(path)


def _row(sid, cls, lake="Logan Martin|AL", lat="33.4", lon="-86.3", note=""):
    return {"MonitoringLocationIdentifier": sid, "OrganizationIdentifier": "SYN", "MonitoringLocationName": "SYNTHETIC", "LatitudeMeasure": lat,
            "LongitudeMeasure": lon, "lakeId": lake, "class": cls, "reason": "t", "reviewNote": note}


def test_review_rules(tmp_path):
    draft = _write_stations(tmp_path / "d.csv", [_row("SYN-U", "UNCLASSIFIED"), _row("SYN-E", "EMBAYMENT"), _row("SYN-N", "UNCLASSIFIED", lat="", lon="")])
    ok = _write_stations(tmp_path / "ok.csv", [_row("SYN-U", "MAIN_BODY", note="own river at the dam"), _row("SYN-E", "EMBAYMENT"),
                                               _row("SYN-N", "UNCLASSIFIED", lat="", lon="")])
    assert W.load_reviewed(draft, ok, W.V1.sha256_file(ok))["SYN-U"]["class"] == "MAIN_BODY"
    with pytest.raises(SystemExit, match="differs from the posted"):
        W.load_reviewed(draft, ok, "0" * 64)
    bad = [([_row("SYN-U", "MAIN_BODY"), _row("SYN-E", "EMBAYMENT"), _row("SYN-N", "UNCLASSIFIED", lat="", lon="")], "without a reviewNote"),
           ([_row("SYN-U", "UNCLASSIFIED"), _row("SYN-E", "MAIN_BODY", note="x"), _row("SYN-N", "UNCLASSIFIED", lat="", lon="")], "only UNCLASSIFIED"),
           ([_row("SYN-U", "UNCLASSIFIED"), _row("SYN-E", "EMBAYMENT")], "adds or removes"),
           ([_row("SYN-U", "UNCLASSIFIED"), _row("SYN-E", "EMBAYMENT"), _row("SYN-N", "MAIN_BODY", lat="", lon="", note="x")], "no coordinates"),
           ([_row("SYN-U", "UNCLASSIFIED", lat="33.5"), _row("SYN-E", "EMBAYMENT"), _row("SYN-N", "UNCLASSIFIED", lat="", lon="")], "changed in review")]
    for i, (rows, msg) in enumerate(bad):
        rv = _write_stations(tmp_path / f"b{i}.csv", rows)
        with pytest.raises(SystemExit, match=msg):
            W.load_reviewed(draft, rv, W.V1.sha256_file(rv))


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
    assert ex["Guntersville|AL"] == []
    assert any(e.startswith("RESOLVER_SENSOR: USGS LK") for e in ex["Logan Martin|AL"])
    assert ex["Seminole|GA"] == ["WT_SAT_1: USGS LK 00010 site SYN-LK-FAR-INSIDE inside the polygon"]
    assert ex["Lay|AL"] == ["M0_TUNING: calibration site SYN-CAL"]
    assert ex["Jordan|AL"] == ["M0_TUNING: directory id in the M0 calibration set"]
    assert ex["Okatibbee Lake|MS"] == ["RESOLVER_SENSOR: tempSensor binding"]
    assert ex["Weiss|AL"] == ["NO_GEOMETRY"]


def test_exclusions_cli_requires_and_records_the_calibration_lake_list(tmp_path):
    with pytest.raises(SystemExit):
        W.main(["exclusions", "--registry", "r", "--sites", "s", "--calibration", "c", "--out", "o"])     # --calibration-lakes missing
    reg = tmp_path / "reg"
    reg.mkdir()
    (reg / "lakes.v1.json").write_text(json.dumps({"lakes": [{"lakeId": "Lay|AL", "lakeKey": "Lay_AL", "bbox": [0, 0, 1, 1]}]}))
    (reg / "Lay_AL.analysis.geojson").write_text(json.dumps(square("Lay|AL")))
    sites = tmp_path / "sites.csv"
    sites.write_text("site,siteType,lat,lon,has00010,m0Calibration\n")
    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps({"rows": []}))
    lakes = tmp_path / "lakes.json"
    lakes.write_text(json.dumps(["Jordan|AL"]))
    out = tmp_path / "ex.json"
    assert W.main(["exclusions", "--registry", str(reg), "--sites", str(sites), "--calibration", str(cal), "--calibration-lakes", str(lakes), "--out", str(out)]) == 0
    rec = json.loads(out.read_text())
    assert rec["calibrationLakes"] == ["Jordan|AL"] and rec["calibrationLakesSha256"] == W.V1.sha256_file(str(lakes))
    assert rec["exclusions"]["Jordan|AL"] == ["M0_TUNING: directory id in the M0 calibration set", "NO_GEOMETRY"]


# ------------------------------------------------------------------------------------------------------- census and selection
def stations_for(lakes):
    out = {}
    for i, lid in enumerate(lakes):
        lat, lon = PTS[lid]
        out[f"SYN-{i}"] = {"MonitoringLocationIdentifier": f"SYN-{i}", "LatitudeMeasure": str(lat), "LongitudeMeasure": str(lon), "lakeId": lid, "class": "MAIN_BODY"}
    return out


def dates(n, start="2022-04-01"):
    d0 = dt.date.fromisoformat(start)
    return [(d0 + dt.timedelta(days=7 * i)).isoformat() for i in range(n)]


def rdrow(sid, d, rdep="", rdu="", adep="", adu="", status="Accepted", ch="Temperature, water", act=None):
    return {"MonitoringLocationIdentifier": sid, "ActivityStartDate": d, "ActivityIdentifier": act or f"{sid}-{d}", "CharacteristicName": ch,
            "ResultStatusIdentifier": status, "ResultDepthHeightMeasure/MeasureValue": rdep, "ResultDepthHeightMeasure/MeasureUnitCode": rdu,
            "ActivityDepthHeightMeasure/MeasureValue": adep, "ActivityDepthHeightMeasure/MeasureUnitCode": adu}


def test_census_counts_from_result_depth_rows_with_one_depth_order_and_status():
    st = stations_for(["Wheeler|AL"])
    rows = [rdrow("SYN-0", "2022-04-01", "0.5", "m"),
            rdrow("SYN-0", "2022-04-08", "3.0", "m", "0.5", "m"),           # result depth wins: 3.0 m, not counted
            rdrow("SYN-0", "2022-04-15", "", "", "1.2", "m"),               # falls back to activity depth
            rdrow("SYN-0", "2022-04-22", "0.5", "m", status="Rejected"),
            rdrow("SYN-0", "2022-04-29", "0.5", ""),                         # unit missing: no depth
            rdrow("SYN-0", "2022-05-06", "0.5", "m", ch="pH"),
            rdrow("SYN-0", "2026-08-01", "0.5", "m")]
    res = W.census(P, rows, st, "2026-11-22")
    wh = res["waters"]["Wheeler|AL"]
    assert wh["qualifyingCasts"] == 3 and wh["qualifyingCastsToFrozenHoldoutEnd"] == 2
    assert wh["stepARejects"] == {"deeperThan1.5m": 1, "rejectedStatus": 1, "noDepth": 1, "otherCharacteristic": 1}
    assert wh["casts"]["Wheeler|AL|SYN-0|2022-04-15"] == ["SYN-0-2022-04-15@1.2"]


def test_dedupe_survives_coordinate_less_stations():
    st = {"A": {"LatitudeMeasure": "", "LongitudeMeasure": ""}, "B": {"LatitudeMeasure": "34.0", "LongitudeMeasure": "-87.0"},
          "C": {"LatitudeMeasure": "34.001", "LongitudeMeasure": "-87.001"}}
    casts = {k: {"lakeId": "Wheeler|AL", "station": k, "date": "2022-04-01", "readings": {k}} for k in ("A", "B", "C")}
    assert sorted(W._dedupe(casts, st)) == ["A", "B"]


def census_with(counts):
    return {"waters": {lid: {"qualifyingCasts": n, "casts": {f"{lid}|SYN-{W.slug(lid)}-{i}|{d}": [f"SYN-{W.slug(lid)}-{i}-{d}@0.5"]
                                                              for i, d in enumerate(dates(n))}} for lid, n in counts.items()}}


def test_selection_keeps_qualifying_frozen_lakes_and_replaces_short_ones_by_count_only():
    counts = {"Guntersville|AL": 36, "Wheeler|AL": 22, "Wilson|AL": 0, "Pickwick Lake|TN": 0,
              "Logan Martin|AL": 80, "Lay|AL": 40, "Jordan|AL": 40, "Weiss|AL": 120, "Seminole|GA": 30}
    sel = W.select(P, census_with(counts), {"Weiss|AL": ["RESOLVER_SENSOR: x"]})
    assert sel["retained"] == ["Guntersville|AL"]
    tie = sorted(["Lay|AL", "Jordan|AL"], key=lambda l: hashlib.sha256(l.encode()).hexdigest())
    assert sel["replacements"] == ["Logan Martin|AL"] + tie and sel["outcome"] == "SELECTED"
    assert W.select(P, census_with({"Guntersville|AL": 36, "Lay|AL": 30, "Jordan|AL": 26, "Seminole|GA": 25}), {})["outcome"] == "INSUFFICIENT_TRUTH"


# ------------------------------------------------------------------------------------------------------- step B
SEL_COUNTS = {"Guntersville|AL": 36, "Logan Martin|AL": 40, "Lay|AL": 40, "Jordan|AL": 40}


def selection_files(tmp_path):
    st = _write_stations(tmp_path / "st.csv", [])
    sel = {"protocolSha256": DIGEST, "stationFileSha256": W.V1.sha256_file(st), **W.select(P, census_with(SEL_COUNTS), {})}
    sp = tmp_path / "selection.json"
    sp.write_text(json.dumps(sel))
    return sel, str(sp), W.V1.sha256_file(str(sp)), st


def test_step_b_gate(tmp_path):
    sel, sp, sha, st = selection_files(tmp_path)
    W.load_selection_for_step_b(sp, sha, st, DIGEST, REQ)
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.load_selection_for_step_b(sp, sha, st, DIGEST, "Claude request (under Owner approval 2026-11-22)")
    with pytest.raises(SystemExit, match="posted selection sha256"):
        W.load_selection_for_step_b(sp, "0" * 64, st, DIGEST, REQ)
    with pytest.raises(SystemExit, match="different protocol"):
        W.load_selection_for_step_b(sp, sha, st, "0" * 64, REQ)
    with open(st, "a") as fh:
        fh.write("SYN-X,SYN,SYNTHETIC,1,1,Lay|AL,MAIN_BODY,late,\n")
    with pytest.raises(SystemExit, match="station file differs"):
        W.load_selection_for_step_b(sp, sha, st, DIGEST, REQ)


def test_step_b_fetches_only_counted_casts_and_the_derived_forcing_window(tmp_path):
    sel, *_ = selection_files(tmp_path)
    qs = W.result_queries(sel)
    assert len(qs) == sum(SEL_COUNTS.values()) and all(q["params"]["startDateLo"] == q["params"]["startDateHi"] for q in qs)
    assert all("bBox" not in q["params"] for q in qs)
    p = W.forcing_params(P, sel, "Lay|AL")
    ds = dates(40)
    assert (p["start_date"], p["end_date"]) == ((dt.date.fromisoformat(ds[0]) - dt.timedelta(days=46)).isoformat(), ds[-1])
    assert [p["latitude"], p["longitude"]] == PTS["Lay|AL"]


def forcing(air_c, start="2022-01-01", end="2023-12-31", null_on=()):
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    days = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    air = [None if d in null_on else air_c for d in days]
    n = len(days)
    return {"daily": {"time": days, "temperature_2m_mean": air, "shortwave_radiation_sum": [0.0] * n,
                      "wind_speed_10m_mean": [5.0] * n, "relative_humidity_2m_mean": [0.0] * n}}


def results_for(sel, value="21.0", unit="deg C"):
    return [{"MonitoringLocationIdentifier": s, "ActivityStartDate": d, "ActivityIdentifier": f"{s}-{d}", "CharacteristicName": "Temperature, water",
             "ResultStatusIdentifier": "Accepted", "ResultMeasureValue": value, "ResultMeasure/MeasureUnitCode": unit,
             "ResultDepthHeightMeasure/MeasureValue": "0.5", "ResultDepthHeightMeasure/MeasureUnitCode": "m"} for _, s, d in W.counted_casts(sel)]


def test_forcing_that_does_not_cover_every_cast_is_refused(tmp_path):
    sel, *_ = selection_files(tmp_path)
    with pytest.raises(SystemExit, match="does not cover counted cast"):
        W.check_forcing(forcing(20.0, start="2022-03-01"), [d for lid, _, d in W.counted_casts(sel) if lid == "Lay|AL"])


def test_compare_pass_and_unknowns_count_against(tmp_path):
    sel, *_ = selection_files(tmp_path)
    f = {lid: forcing(20.0) for lid in SEL_COUNTS}
    res = W.compare(P, sel, results_for(sel), f)           # M0 == 20 C (Teq == air), truth 21 C
    assert res["outcome"] == "PASS" and res["pooledEqualLakeRmseC"] == 1.0
    miss = {k: v for k, v in f.items() if k != "Lay|AL"}
    r = W.compare(P, sel, results_for(sel), miss)
    assert r["outcome"] == "FAIL" and r["perLake"]["Lay|AL"]["failed"] == "FORCING_MISSING" and r["pooledEqualLakeRmseC"] is None
    one_day = W.counted_casts(sel)[0]
    holed = {**f, one_day[0]: forcing(20.0, null_on={one_day[2]})}
    r = W.compare(P, sel, results_for(sel), holed)
    assert r["outcome"] == "FAIL" and r["perLake"][one_day[0]]["failed"] == "UNPAIRED_CAST"


def test_step_b_truth_rejects_are_reported_and_can_fail_a_lake(tmp_path):
    sel, *_ = selection_files(tmp_path)
    f = {lid: forcing(20.0) for lid in SEL_COUNTS}
    rows = results_for(sel)
    g = [r for r in rows if r["MonitoringLocationIdentifier"].startswith("SYN-Guntersville")]
    for r in g[:12]:
        r["ResultMeasureValue"] = "99"                     # out of range: 36 - 12 = 24 scored < 25
    r = W.compare(P, sel, rows, f)
    gl = r["perLake"]["Guntersville|AL"]
    assert gl["failed"] == "SCORED_BELOW_25" and len(gl["truthRejectsStepB"]) == 12 and r["outcome"] == "FAIL"
    extra = dict(rows[0], ActivityIdentifier="NOT-COUNTED", ResultMeasureValue="5")
    assert W.truth_values(sel, [extra])[0] == {}           # a reading not counted in step A never enters


def test_compare_is_write_once(tmp_path):
    out = tmp_path / "compare.json"
    out.write_text("{}")
    with pytest.raises(SystemExit, match="write-once"):
        W.cmd_compare(P, DIGEST, "s", "x", "st", "r", "f", REQ, str(out))


def test_cli_verify(capsys):
    assert W.main(["verify"]) == 0
    assert json.loads(capsys.readouterr().out)["sha256"] == DIGEST
