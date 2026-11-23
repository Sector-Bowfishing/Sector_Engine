"""PT-L4-2026-11-23-v4 runner, offline. Every fixture is hand-built and synthetic: synthetic square 'polygons' around the
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
import water_temp_protected_truth_v4 as W  # noqa: E402

P, DIGEST = W.load_protocol()
PTS = {l["lakeId"]: l["point"] for l in P["universe"]["lakes"]}
REQ = "Owner request (Michael, 2099-01-01): synthetic test"
V2 = os.path.join(W.REPO, "docs", "brains", "water-temp-protected-truth-v2", "PT-L4-2026-11-23-v2.protocol.json")
V3 = os.path.join(W.REPO, "docs", "brains", "water-temp-protected-truth-v3", "PT-L4-2026-11-23-v3.protocol.json")


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
    assert P["protocolId"] == "PT-L4-2026-11-23-v4" and P["censusCutoff"] == W.CUTOFF == "2026-11-22" and len(P["universe"]["lakes"]) == 62
    assert P["minimums"] == {"perLake": 25, "total": 150, "lakes": 4} == {"perLake": W.PER_LAKE, "total": W.TOTAL, "lakes": W.SLOTS}
    assert P["passMark"]["pooledEqualLakeRmseC"]["value"] == P["passMark"]["perLakeRmseC"]["value"] == W.RMSE_MARK
    assert "INSUFFICIENT_PAIRED" not in json.dumps(P["passMark"]["outcomes"])


def test_superseded_protocols_are_kept_byte_identical_and_refused():
    assert W.V1.sha256_file(V2) == "e02e2e08740767dec4720a610c112010eb78ad73ad1b223b14365489a499867d"
    assert W.V1.sha256_file(V3) == "ebc1a77b1977924c2bb586340887f2fad7a3196b20bf4f2ef2305853716f170d"
    for old in (V2, V3):
        with pytest.raises(SystemExit, match="executes PT-L4-2026-11-23-v4 only"):
            W.load_protocol(old)


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
    GuardedRow.forbidden = {header.index("ResultMeasureValue"), header.index("ResultCommentText")}
    rows = [header, GuardedRow(["SYN", "SYN-1", "A1", "2023-06-01", "Temperature, water", "SENTINEL-31.4", "deg C", "Accepted", "0.5", "m", "SENTINEL-NOTE"])]
    buf = io.StringIO()
    assert W.strip_result_rows(rows, buf) == 1
    out = buf.getvalue()
    assert "SENTINEL" not in out and "ResultMeasureValue" not in out and "deg C" in out
    assert "ResultMeasureValue" not in W.RESULT_DEPTH_COLUMNS
    assert [c for c in W.RESULT_DEPTH_COLUMNS if c.startswith("ResultMeasure")] == ["ResultMeasure/MeasureUnitCode"]


def test_station_and_activity_metadata_are_stored_as_whitelisted_columns_only():
    raw = ("OrganizationIdentifier,MonitoringLocationIdentifier,ActivityIdentifier,ActivityStartDate,ActivityCommentText,"
           "ActivityDepthHeightMeasure/MeasureValue,ActivityDepthHeightMeasure/MeasureUnitCode\n"
           "SYN,SYN-1,A1,2023-06-01,SENTINEL surface 24.1 C,0.5,m\n").encode()
    out = W._stripped_csv(raw, W.ACTIVITY_COLUMNS).decode()
    assert "SENTINEL" not in out and "Comment" not in out and "A1" in out


def test_usgs_metadata_keeps_whitelisted_properties_only():
    body = json.dumps({"features": [{"id": "USGS-SYN1", "geometry": {"type": "Point", "coordinates": [-86, 34]},
                                     "properties": {"monitoring_location_id": "USGS-SYN1", "site_type_code": "LK", "last_value": "SENTINEL-21.5"}}]}).encode()
    out = W.strip_usgs(body).decode()
    assert "SENTINEL" not in out and '"LK"' in out


def test_fetch_refuses_unlisted_sources_and_redirects():
    for url in ("https://example.com/data/x", "https://storage.googleapis.com/other-bucket/x", "http://www.waterqualitydata.us/data/x"):
        with pytest.raises(SystemExit, match="not an allowlisted source"):
            W._get_bytes(url)
    with pytest.raises(SystemExit, match="not an allowlisted source"):
        W._CheckedRedirect().redirect_request(None, None, 302, "Found", {}, "https://evil.example/data/x")


# ------------------------------------------------------------------------------------------------------- stations and review
@pytest.mark.parametrize("lake,dlat,sid,name,cls,expect_lake", [
    ("Wheeler|AL", 0.0, "21AWIC-TENR-296", "SYNTHETIC station", "MAIN_BODY", "Wheeler|AL"),
    ("Wheeler|AL", 0.0, "SYN-1", "SYNTHETIC Tennessee River TRM 348.0", "TAILWATER", "Wheeler|AL"),
    ("Wheeler|AL", 0.0, "SYN-3", "SYNTHETIC Flint River arm", "EMBAYMENT", "Wheeler|AL"),
    ("Logan Martin|AL", 0.0, "SYN-4", "SYNTHETIC Coosa River at dam", "UNCLASSIFIED", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.0, "SYN-5", "SYNTHETIC Logan Martin Lake near dam", "MAIN_BODY", "Logan Martin|AL"),
    ("Logan Martin|AL", 0.5, "SYN-8", "SYNTHETIC station", "OUTSIDE", None),
])
def test_station_classes(lake, dlat, sid, name, cls, expect_lake):
    lat, lon = PTS[lake]
    got, lid, why = W.classify(P, registry([lake]), sid, name, lat + dlat, lon)
    assert got == cls, why
    assert lid == expect_lake


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
    base = [_row("SYN-U", "UNCLASSIFIED"), _row("SYN-E", "EMBAYMENT"), _row("SYN-N", "UNCLASSIFIED", lat="", lon="", lake="")]
    draft = _write_stations(tmp_path / "d.csv", base)
    dsha = W.V1.sha256_file(draft)
    ok = _write_stations(tmp_path / "ok.csv", [_row("SYN-U", "MAIN_BODY", note="the dam's own river"), base[1], base[2]])
    assert W.load_reviewed(draft, dsha, ok, W.V1.sha256_file(ok))["SYN-U"]["class"] == "MAIN_BODY"
    with pytest.raises(SystemExit, match="posted reviewed-file hash"):
        W.load_reviewed(draft, dsha, ok, "0" * 64)
    with pytest.raises(SystemExit, match="posted draft hash"):
        W.load_reviewed(draft, "0" * 64, ok, W.V1.sha256_file(ok))
    bad = [([_row("SYN-U", "MAIN_BODY"), base[1], base[2]], "without a reviewNote"),
           ([base[0], _row("SYN-E", "MAIN_BODY", note="x"), base[2]], "only UNCLASSIFIED"),
           ([_row("SYN-U", "MAIN_BODY", lake="Lay|AL", note="x"), base[1], base[2]], "keeps the draft's lake"),
           ([base[0], base[1]], "adds or removes"),
           ([base[0], base[1], _row("SYN-N", "MAIN_BODY", lat="", lon="", lake="Lay|AL", note="x")], "no coordinates"),
           ([_row("SYN-U", "UNCLASSIFIED", lat="33.5"), base[1], base[2]], "changed in review"),
           ([_row("SYN-U", "UNCLASSIFIED", note="sneaky"), base[1], base[2]], "not reclassified")]
    for i, (rows, msg) in enumerate(bad):
        rv = _write_stations(tmp_path / f"b{i}.csv", rows)
        with pytest.raises(SystemExit, match=msg):
            W.load_reviewed(draft, dsha, rv, W.V1.sha256_file(rv))


# ------------------------------------------------------------------------------------------------------- exclusions
def test_exclusion_rules():
    reg = registry(half=0.3)
    reg["Weiss|AL"] = {"bbox": None, "geometry": None}
    m_lat, m_lon = PTS["Logan Martin|AL"]
    s_lat, s_lon = PTS["Seminole|GA"]
    sites = [{"site": "SYN-LK-NEAR", "siteType": "LK", "lat": m_lat + 0.05, "lon": m_lon, "has00010": "True", "m0Calibration": "False"},
             {"site": "SYN-LK-FAR-INSIDE", "siteType": "LK", "lat": s_lat + 0.28, "lon": s_lon, "has00010": "True", "m0Calibration": "False"},
             {"site": "SYN-CAL", "siteType": "ST", "lat": PTS["Lay|AL"][0], "lon": PTS["Lay|AL"][1], "has00010": "True", "m0Calibration": "True"}]
    ex = W.exclusions(P, reg, sites, {"Jordan|AL"}, W.bound_lakes(), set())
    assert ex["Guntersville|AL"] == [] and any(e.startswith("RESOLVER_SENSOR: USGS LK") for e in ex["Logan Martin|AL"])
    assert ex["Seminole|GA"] == ["WT_SAT_1: USGS LK 00010 site SYN-LK-FAR-INSIDE inside the polygon"]
    assert ex["Lay|AL"] == ["M0_TUNING: calibration site SYN-CAL"] and ex["Jordan|AL"] == ["M0_TUNING: directory id in the M0 calibration set"]
    assert ex["Okatibbee Lake|MS"] == ["RESOLVER_SENSOR: tempSensor binding"] and ex["Weiss|AL"] == ["NO_GEOMETRY"]


def test_exclusions_cli_requires_and_records_the_calibration_lake_list(tmp_path):
    with pytest.raises(SystemExit):
        W.main(["exclusions", "--registry", "r", "--sites", "s", "--calibration", "c", "--out", "o"])
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
    args = ["exclusions", "--registry", str(reg), "--sites", str(sites), "--calibration", str(cal), "--calibration-lakes", str(lakes), "--out", str(out)]
    assert W.main(args) == 0
    rec = json.loads(out.read_text())
    assert rec["calibrationLakes"] == ["Jordan|AL"] and rec["calibrationLakesSha256"] == W.V1.sha256_file(str(lakes))
    with pytest.raises(SystemExit, match="write-once"):
        W.main(args)


# ------------------------------------------------------------------------------------------------------- census and selection
def dates(n, start="2022-04-01"):
    d0 = dt.date.fromisoformat(start)
    return [(d0 + dt.timedelta(days=7 * i)).isoformat() for i in range(n)]


def rdrow(sid, d, rdep="", rdu="", adep="", adu="", status="Accepted", ch="Temperature, water", unit="deg C", act=None):
    return {"MonitoringLocationIdentifier": sid, "ActivityStartDate": d, "ActivityIdentifier": act or f"{sid}-{d}", "CharacteristicName": ch,
            "ResultStatusIdentifier": status, "ResultMeasure/MeasureUnitCode": unit, "ResultDepthHeightMeasure/MeasureValue": rdep,
            "ResultDepthHeightMeasure/MeasureUnitCode": rdu, "ActivityDepthHeightMeasure/MeasureValue": adep, "ActivityDepthHeightMeasure/MeasureUnitCode": adu}


def test_census_rules_and_frozen_holdout_window():
    lat, lon = PTS["Wheeler|AL"]
    st = {"SYN-0": {"MonitoringLocationIdentifier": "SYN-0", "LatitudeMeasure": str(lat), "LongitudeMeasure": str(lon), "lakeId": "Wheeler|AL", "class": "MAIN_BODY"}}
    rows = [rdrow("SYN-0", "2022-04-01", "0.5", "m"),
            rdrow("SYN-0", "2022-04-08", "3.0", "m", "0.5", "m"),            # Result depth first: 3.0 m
            rdrow("SYN-0", "2022-04-15", "", "", "1.2", "m"),                # Activity depth fallback
            rdrow("SYN-0", "2022-04-22", "0.5", "m", status="Rejected"),
            rdrow("SYN-0", "2022-04-29", "0.5", ""),                          # no depth unit
            rdrow("SYN-0", "2022-05-06", "0.5", "m", unit="mg/L"),           # unknown temperature unit, decided in step A
            rdrow("SYN-0", "2022-05-13", "0.5", "m", ch="pH"),
            rdrow("SYN-0", "2026-08-01", "0.5", "m"),                          # after the holdout end: info only for a frozen lake
            rdrow("SYN-0", "2026-11-23", "0.5", "m")]                          # after the fixed cutoff
    wh = W.census(P, rows, st)["waters"]["Wheeler|AL"]
    assert wh["qualifyingCasts"] == 2 and wh["infoCastsToCutoff"] == 3 and wh["window"] == ["2021-01-01", "2026-06-30"]
    assert wh["stepARejects"] == {"deeperThan1.5m": 1, "rejectedStatus": 1, "noDepth": 1, "unknownUnit": 1, "otherCharacteristic": 1, "outsideWindow": 1}
    st2 = {"SYN-0": dict(st["SYN-0"], lakeId="Lay|AL")}
    assert W.census(P, rows, st2)["waters"]["Lay|AL"]["qualifyingCasts"] == 3        # a replacement candidate counts to the cutoff


def test_census_is_write_once_and_refuses_non_whitelisted_columns(tmp_path):
    wqp = tmp_path / "wqp"
    wqp.mkdir()
    st = _write_stations(tmp_path / "st.csv", [])
    sha = W.V1.sha256_file(st)
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps({"protocolSha256": DIGEST, "exclusions": {}}))
    out = tmp_path / "c.json"
    W.cmd_census(P, DIGEST, str(wqp), st, sha, st, sha, str(ex), str(out))
    with pytest.raises(SystemExit, match="write-once"):
        W.cmd_census(P, DIGEST, str(wqp), st, sha, st, sha, str(ex), str(out))
    (wqp / f"{W.slug('Wheeler|AL')}.resultdepth.csv").write_text("MonitoringLocationIdentifier,ActivityStartDate,ResultMeasureValue\nSYN-1,2023-06-01,20\n")
    with pytest.raises(SystemExit, match="non-whitelisted column"):
        W.cmd_census(P, DIGEST, str(wqp), st, sha, st, sha, str(ex), str(tmp_path / "c2.json"))


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
    tie = sorted(["Lay|AL", "Jordan|AL"], key=lambda l: hashlib.sha256(l.encode()).hexdigest())
    assert sel["retained"] == ["Guntersville|AL"] and sel["replacements"] == ["Logan Martin|AL"] + tie and sel["outcome"] == "SELECTED"
    assert W.select(P, census_with({"Guntersville|AL": 36, "Lay|AL": 30, "Jordan|AL": 26, "Seminole|GA": 25}), {})["outcome"] == "INSUFFICIENT_TRUTH"


def test_one_selection_per_protocol_id(tmp_path):
    cp = tmp_path / "census.json"
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps({"exclusions": {}}))
    cp.write_text(json.dumps({"protocolSha256": DIGEST, "exclusionsSha256": W.V1.sha256_file(str(ex)), "stationDraftSha256": "d",
                              "stationFileSha256": "s", **census_with(SEL_COUNTS)}))
    out, reg = tmp_path / "selection.json", tmp_path / "selection-registry.json"
    W.cmd_select(P, DIGEST, str(cp), str(ex), str(out), str(reg))
    assert json.loads(reg.read_text())["selectionSha256"] == W.V1.sha256_file(str(out))
    with pytest.raises(SystemExit, match="one selection per protocol id"):
        W.cmd_select(P, DIGEST, str(cp), str(ex), str(tmp_path / "other.json"), str(reg))


# ------------------------------------------------------------------------------------------------------- step B
SEL_COUNTS = {"Guntersville|AL": 36, "Logan Martin|AL": 40, "Lay|AL": 40, "Jordan|AL": 40}


def selection_files(tmp_path):
    st = _write_stations(tmp_path / "st.csv", [])
    sel = {"protocolSha256": DIGEST, "stationFileSha256": W.V1.sha256_file(st), **W.select(P, census_with(SEL_COUNTS), {})}
    sp = tmp_path / "selection.json"
    sp.write_text(json.dumps(sel))
    reg = tmp_path / "selection-registry.json"
    reg.write_text(json.dumps({"protocolId": W.PROTOCOL_ID, "protocolSha256": DIGEST, "selectionSha256": W.V1.sha256_file(str(sp))}))
    return sel, str(sp), str(reg), st


def test_step_b_gate(tmp_path):
    sel, sp, reg, st = selection_files(tmp_path)
    W.load_selection_for_step_b(sp, reg, st, DIGEST, REQ)
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.load_selection_for_step_b(sp, reg, st, DIGEST, "Claude request (under Owner approval 2026-11-22)")
    with pytest.raises(SystemExit, match="no selection registry"):
        W.load_selection_for_step_b(sp, str(tmp_path / "none.json"), st, DIGEST, REQ)
    other = tmp_path / "selection2.json"
    other.write_text(json.dumps({**sel, "note": "a second selection"}))
    with pytest.raises(SystemExit, match="registered selection sha256"):
        W.load_selection_for_step_b(str(other), reg, st, DIGEST, REQ)
    with pytest.raises(SystemExit, match="different protocol"):
        W.load_selection_for_step_b(sp, reg, st, "0" * 64, REQ)
    with open(st, "a") as fh:
        fh.write("SYN-X,SYN,SYNTHETIC,1,1,Lay|AL,MAIN_BODY,late,\n")
    with pytest.raises(SystemExit, match="station file differs"):
        W.load_selection_for_step_b(sp, reg, st, DIGEST, REQ)


def test_step_b_queries_and_the_derived_forcing_window(tmp_path):
    sel, *_ = selection_files(tmp_path)
    qs = W.result_queries(sel)
    assert len(qs) == sum(SEL_COUNTS.values()) and len({q["file"] for q in qs}) == len(qs)
    assert all(q["params"]["startDateLo"] == q["params"]["startDateHi"] and "bBox" not in q["params"] for q in qs)
    p = W.forcing_params(P, sel, "Lay|AL")
    ds = dates(40)
    assert (p["start_date"], p["end_date"]) == ((dt.date.fromisoformat(ds[0]) - dt.timedelta(days=46)).isoformat(), ds[-1])


def forcing(air_c, start="2022-01-01", end="2023-12-31", null_on=()):
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    days = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    n = len(days)
    return {"daily": {"time": days, "temperature_2m_mean": [None if d in null_on else air_c for d in days], "shortwave_radiation_sum": [0.0] * n,
                      "wind_speed_10m_mean": [5.0] * n, "relative_humidity_2m_mean": [0.0] * n}}


def result_row(s, d, value="21.0", unit="deg C"):
    return {"MonitoringLocationIdentifier": s, "ActivityStartDate": d, "ActivityIdentifier": f"{s}-{d}", "CharacteristicName": "Temperature, water",
            "ResultStatusIdentifier": "Accepted", "ResultMeasureValue": value, "ResultMeasure/MeasureUnitCode": unit,
            "ResultDepthHeightMeasure/MeasureValue": "0.5", "ResultDepthHeightMeasure/MeasureUnitCode": "m"}


def results_for(sel, value="21.0"):
    return [result_row(s, d, value) for _, s, d in W.counted_casts(sel)]


def test_forcing_that_does_not_cover_every_cast_is_refused(tmp_path):
    sel, *_ = selection_files(tmp_path)
    with pytest.raises(SystemExit, match="does not cover counted cast"):
        W.check_forcing(forcing(20.0, start="2022-03-01"), [d for lid, _, d in W.counted_casts(sel) if lid == "Lay|AL"])


def test_compare_pass_and_unknowns_count_against(tmp_path):
    sel, *_ = selection_files(tmp_path)
    f = {lid: forcing(20.0) for lid in SEL_COUNTS}
    res = W.compare(P, sel, results_for(sel), f)
    assert res["outcome"] == "PASS" and res["pooledEqualLakeRmseC"] == 1.0
    rows = results_for(sel)
    del rows[5], rows[0]                                           # two counted readings not returned: the reviewed reproduction
    r = W.compare(P, sel, rows, f)
    assert r["outcome"] == "FAIL" and "CAST_NOT_RETURNED" in r["perLake"]["Guntersville|AL"]["failed"]
    r = W.compare(P, sel, results_for(sel), {k: v for k, v in f.items() if k != "Lay|AL"})
    assert r["outcome"] == "FAIL" and r["perLake"]["Lay|AL"]["failed"] == ["FORCING_MISSING"] and r["pooledEqualLakeRmseC"] is None
    c0 = W.counted_casts(sel)[0]
    r = W.compare(P, sel, results_for(sel), {**f, c0[0]: forcing(20.0, null_on={c0[2]})})
    assert r["outcome"] == "FAIL" and "UNPAIRED_CAST" in r["perLake"][c0[0]]["failed"]
    rows = results_for(sel)
    g = [x for x in rows if x["MonitoringLocationIdentifier"].startswith("SYN-Guntersville")]
    for x in g[:12]:
        x["ResultMeasureValue"] = "99"
    r = W.compare(P, sel, rows, f)
    assert r["perLake"]["Guntersville|AL"]["failed"] == ["SCORED_BELOW_25"] and len(r["perLake"]["Guntersville|AL"]["truthRejectsStepB"]) == 12


def test_duplicate_and_uncounted_readings(tmp_path):
    sel, *_ = selection_files(tmp_path)
    rows = results_for(sel)
    with pytest.raises(SystemExit, match="appears twice"):
        W.truth_values(sel, rows + [rows[0]])
    extra = dict(rows[0], ActivityIdentifier="NOT-COUNTED", ResultMeasureValue="5")
    assert W.truth_values(sel, [extra])[0] == {}


def fetched_folders(tmp_path, sel):
    """Write step-B files plus provenance exactly as fetch-results / fetch-forcing do (synthetic bodies)."""
    rdir, fdir = tmp_path / "rb", tmp_path / "fb"
    prov = []
    for q in W.result_queries(sel):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(result_row("x", "2022-01-01")))
        w.writeheader()
        w.writerow(result_row(q["siteid"], q["date"]))
        W._save(str(rdir), q["file"], buf.getvalue().encode(), "u", q["params"], prov)
    W.V1.write_provenance(str(rdir), "results.provenance.json", prov)
    prov = []
    for l in sel["lakes"]:
        W._save(str(fdir), W.forcing_file(l["lakeId"]), json.dumps(forcing(20.0)).encode(), "u", W.forcing_params(P, sel, l["lakeId"]), prov)
    W.V1.write_provenance(str(fdir), "forcing.provenance.json", prov)
    return str(rdir), str(fdir)


def test_cmd_compare_verifies_files_against_provenance(tmp_path):
    sel, sp, reg, st = selection_files(tmp_path)
    rdir, fdir = fetched_folders(tmp_path, sel)
    out = tmp_path / "compare.json"
    rec = W.cmd_compare(P, DIGEST, sp, reg, st, rdir, fdir, REQ, str(out))
    assert rec["outcome"] == "PASS" and len(rec["inputSha256"]) == sum(SEL_COUNTS.values()) + 4
    with pytest.raises(SystemExit, match="write-once"):
        W.cmd_compare(P, DIGEST, sp, reg, st, rdir, fdir, REQ, str(out))
    files = sorted(os.listdir(os.path.join(rdir, "results")))

    def attempt(n):
        return lambda: W.cmd_compare(P, DIGEST, sp, reg, st, rdir, fdir, REQ, str(tmp_path / f"c{n}.json"))

    os.remove(os.path.join(rdir, "results", files[0]))                         # a deleted result file
    with pytest.raises(SystemExit, match="does not hold exactly"):
        attempt(1)()
    shutil.rmtree(rdir); shutil.rmtree(fdir)
    rdir, fdir = fetched_folders(tmp_path, sel)
    open(os.path.join(rdir, "results", "extra.csv"), "w").write("x\n")       # an extra file
    with pytest.raises(SystemExit, match="does not hold exactly"):
        attempt(2)()
    os.remove(os.path.join(rdir, "results", "extra.csv"))
    with open(os.path.join(rdir, "results", files[1]), "a") as fh:            # an edited file
        fh.write("tampered\n")
    with pytest.raises(SystemExit, match="changed after it was fetched"):
        attempt(3)()
    shutil.rmtree(rdir); shutil.rmtree(fdir)
    rdir, fdir = fetched_folders(tmp_path, sel)
    pp = os.path.join(fdir, "forcing.provenance.json")
    d = json.load(open(pp))
    d["items"][0]["params"]["start_date"] = "2000-01-01"                       # forcing fetched with a chosen window
    json.dump(d, open(pp, "w"))
    with pytest.raises(SystemExit, match="parameters the selection does not imply"):
        attempt(4)()
    d["items"].append(dict(d["items"][1]))                                     # a duplicate entry
    json.dump(d, open(pp, "w"))
    with pytest.raises(SystemExit, match="lists a file twice"):
        attempt(5)()


def test_step_b_fetches_are_write_once(tmp_path):
    (tmp_path / "results").mkdir()
    with pytest.raises(SystemExit, match="write-once"):
        W._refuse_existing(str(tmp_path), ["results.provenance.json", "results"])


def test_cli_verify(capsys):
    assert W.main(["verify"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sha256"] == DIGEST and out["censusCutoff"] == "2026-11-22"
