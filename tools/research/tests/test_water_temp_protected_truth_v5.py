"""PT-L4-2026-11-23-v5 runner, offline. Every fixture is hand-built and synthetic: synthetic square 'polygons' around the
directory points, synthetic station ids (SYN-*), synthetic counts and temperatures. No real cast, site or value. Run ledgers
live in pytest's tmp_path."""
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
import water_temp_protected_truth_v5 as W  # noqa: E402

P, DIGEST = W.load_protocol()
PTS = {l["lakeId"]: l["point"] for l in P["universe"]["lakes"]}
REQ = "Owner request (Michael, 2099-01-01): synthetic test"
DOCS = os.path.join(W.REPO, "docs", "brains")
V2 = os.path.join(DOCS, "water-temp-protected-truth-v2", "PT-L4-2026-11-23-v2.protocol.json")
V3 = os.path.join(DOCS, "water-temp-protected-truth-v3", "PT-L4-2026-11-23-v3.protocol.json")
V4 = os.path.join(DOCS, "water-temp-protected-truth-v4", "PT-L4-2026-11-23-v4.protocol.json")

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
    assert P["protocolId"] == "PT-L4-2026-11-23-v5" and P["censusCutoff"] == W.CUTOFF == "2026-11-22" and len(P["universe"]["lakes"]) == 62
    assert P["minimums"] == {"perLake": 25, "total": 150, "lakes": 4} == {"perLake": W.PER_LAKE, "total": W.TOTAL, "lakes": W.SLOTS}
    assert P["passMark"]["pooledEqualLakeRmseC"]["value"] == P["passMark"]["perLakeRmseC"]["value"] == W.RMSE_MARK
    assert "INSUFFICIENT_PAIRED" not in json.dumps(P["passMark"]["outcomes"])


def test_superseded_protocols_are_kept_byte_identical_and_refused():
    assert W.V1.sha256_file(V2) == "e02e2e08740767dec4720a610c112010eb78ad73ad1b223b14365489a499867d"
    assert W.V1.sha256_file(V3) == "ebc1a77b1977924c2bb586340887f2fad7a3196b20bf4f2ef2305853716f170d"
    assert W.V1.sha256_file(V4) == "aac78d48276ba692d7f485971e594c01c000ccc966631f4900bf46a817a096e0"
    for old in (V2, V3, V4):
        with pytest.raises(SystemExit, match="executes PT-L4-2026-11-23-v5 only"):
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




# ------------------------------------------------------------------------------------------------------- run ledger
def new_ledger(tmp_path):
    return W.ledger(DIGEST, str(tmp_path / "research-root"))


def test_ledger_root_is_never_inside_an_output_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("SECTOR_RESEARCH_ROOT", raising=False)
    with pytest.raises(SystemExit, match="no research root"):
        W.research_root(None, [str(tmp_path / "out")])
    with pytest.raises(SystemExit, match="inside an --out folder"):
        W.research_root(str(tmp_path / "out" / "root"), [str(tmp_path / "out")])
    assert W.research_root(str(tmp_path / "root"), [str(tmp_path / "out")]) == os.path.realpath(str(tmp_path / "root"))


def test_ledger_only_run_one_counts_and_the_chain_is_checked(tmp_path):
    L = new_ledger(tmp_path)
    assert L.begin("census", W.PROTOCOL_ID, {}, {}) == 1
    L.abort_before_result("census", W.PROTOCOL_ID, "network")
    assert L.begin("census", W.PROTOCOL_ID, {}, {}) == 2           # an aborted run may be retried
    L.complete("census", W.PROTOCOL_ID, {"census.json": "x"}, {})
    with pytest.raises(SystemExit, match="already ran"):
        L.begin("census", W.PROTOCOL_ID, {}, {})
    assert L.require("census", W.PROTOCOL_ID)["run"] == 2
    lines = open(L.path).read().splitlines()
    lines[1] = lines[1].replace("network", "edited")
    open(L.path, "w").write("\n".join(lines) + "\n")
    with pytest.raises(SystemExit, match="broken at entry 1"):
        new_ledger(tmp_path)


def _exclusion_inputs(tmp_path):
    reg = tmp_path / "reg"
    reg.mkdir(exist_ok=True)
    (reg / "lakes.v1.json").write_text(json.dumps({"lakes": [{"lakeId": "Lay|AL", "lakeKey": "Lay_AL", "bbox": [0, 0, 1, 1]}]}))
    (reg / "Lay_AL.analysis.geojson").write_text(json.dumps(square("Lay|AL")))
    sites = tmp_path / "sites.csv"
    sites.write_text("site,siteType,lat,lon,has00010,m0Calibration\n")
    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps({"rows": []}))
    lakes = tmp_path / "lakes.json"
    lakes.write_text(json.dumps(["Jordan|AL"]))
    return str(reg), str(sites), str(cal), str(lakes)


def test_exclusions_run_once_per_protocol_and_record_their_inputs(tmp_path):
    with pytest.raises(SystemExit):
        W.main(["exclusions", "--registry", "r", "--sites", "s", "--calibration", "c", "--out", "o"])       # --calibration-lakes missing
    reg, sites, cal, lakes = _exclusion_inputs(tmp_path)
    root = str(tmp_path / "root")
    run0 = tmp_path / "run0"
    run0.mkdir()
    args = ["--research-root", root, "exclusions", "--registry", reg, "--sites", sites, "--calibration", cal, "--calibration-lakes", lakes]
    assert W.main(args + ["--out", str(run0 / "ex.json")]) == 0
    rec = json.loads((run0 / "ex.json").read_text())
    assert rec["calibrationLakes"] == ["Jordan|AL"]
    L = W.ledger(DIGEST, root)
    run = L.require("exclusions", W.PROTOCOL_ID)
    assert run["inputs"]["calibrationLakes"] == W.V1.sha256_file(lakes) and run["inputs"]["wtSat1"] == "unfrozen"
    assert run["outputs"]["exclusions.json"] == W.V1.sha256_file(str(run0 / "ex.json"))
    (tmp_path / "run1").mkdir()
    with pytest.raises(SystemExit, match="already ran"):
        W.main(args + ["--out", str(tmp_path / "run1" / "ex.json")])              # a second folder is still a second run


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
    rows = [rdrow("SYN-0", "2022-04-01", "0.5", "m"), rdrow("SYN-0", "2022-04-08", "3.0", "m", "0.5", "m"),
            rdrow("SYN-0", "2022-04-15", "", "", "1.2", "m"), rdrow("SYN-0", "2022-04-22", "0.5", "m", status="Rejected"),
            rdrow("SYN-0", "2022-04-29", "0.5", ""), rdrow("SYN-0", "2022-05-06", "0.5", "m", unit="mg/L"),
            rdrow("SYN-0", "2022-05-13", "0.5", "m", ch="pH"), rdrow("SYN-0", "2026-08-01", "0.5", "m"), rdrow("SYN-0", "2026-11-23", "0.5", "m")]
    wh = W.census(P, rows, st)["waters"]["Wheeler|AL"]
    assert wh["qualifyingCasts"] == 2 and wh["infoCastsToCutoff"] == 3 and wh["window"] == ["2021-01-01", "2026-06-30"]
    assert wh["stepARejects"] == {"deeperThan1.5m": 1, "rejectedStatus": 1, "noDepth": 1, "unknownUnit": 1, "otherCharacteristic": 1, "outsideWindow": 1}
    st2 = {"SYN-0": dict(st["SYN-0"], lakeId="Lay|AL")}
    assert W.census(P, rows, st2)["waters"]["Lay|AL"]["qualifyingCasts"] == 3


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


SEL_COUNTS = {"Guntersville|AL": 36, "Logan Martin|AL": 40, "Lay|AL": 40, "Jordan|AL": 40}


def step_a(tmp_path, L, folder="run0"):
    """Steps A through select, recorded in the ledger like the CLI does (synthetic census content)."""
    d = tmp_path / folder
    d.mkdir()
    st = _write_stations(d / "st.csv", [])
    ssha = W.V1.sha256_file(st)
    ex = d / "ex.json"
    ex.write_text(json.dumps({"protocolSha256": DIGEST, "exclusions": {}}))
    L.begin("exclusions", W.PROTOCOL_ID, {}, {})
    L.complete("exclusions", W.PROTOCOL_ID, {"exclusions.json": W.V1.sha256_file(str(ex))}, {})
    cp = d / "census.json"
    cp.write_text(json.dumps({"protocolSha256": DIGEST, "stationDraftSha256": ssha, "stationFileSha256": ssha,
                              "exclusionsSha256": W.V1.sha256_file(str(ex)), **census_with(SEL_COUNTS)}))
    L.begin("census", W.PROTOCOL_ID, {}, {"stationDraft": ssha, "stationReviewed": ssha})
    L.complete("census", W.PROTOCOL_ID, {"census.json": W.V1.sha256_file(str(cp))}, {})
    sp = d / "selection.json"
    sel = W.cmd_select(P, DIGEST, L, str(cp), str(ex), str(sp))
    return sel, str(sp), st, str(cp), str(ex)


def test_one_selection_per_protocol_whatever_the_folder(tmp_path):
    L = new_ledger(tmp_path)
    sel, sp, st, cp, ex = step_a(tmp_path, L)
    assert L.require("select", W.PROTOCOL_ID)["outputs"]["selection.json"] == W.V1.sha256_file(sp)
    (tmp_path / "run1").mkdir()
    with pytest.raises(SystemExit, match="already ran"):
        W.cmd_select(P, DIGEST, L, cp, ex, str(tmp_path / "run1" / "selection.json"))
    other = tmp_path / "run1" / "selection.json"                 # a hand-made second selection in another folder
    other.write_text(json.dumps({**sel, "note": "second"}))
    with pytest.raises(SystemExit, match="not the select output recorded"):
        W.load_selection_for_step_b(L, str(other), st, DIGEST, REQ)


def test_census_and_select_need_the_recorded_upstream_outputs(tmp_path):
    L = new_ledger(tmp_path)
    d = tmp_path / "x"
    d.mkdir()
    ex = d / "ex.json"
    ex.write_text("{}")
    st = _write_stations(d / "st.csv", [])
    sha = W.V1.sha256_file(st)
    with pytest.raises(SystemExit, match="not recorded as complete"):
        W.cmd_census(P, DIGEST, L, str(d), st, sha, st, sha, str(ex), str(d / "c.json"))
    with pytest.raises(SystemExit, match="not recorded as complete"):
        W.cmd_select(P, DIGEST, L, str(d / "c.json"), str(ex), str(d / "s.json"))


def test_census_runs_once_and_refuses_non_whitelisted_columns(tmp_path):
    L = new_ledger(tmp_path)
    wqp = tmp_path / "wqp"
    wqp.mkdir()
    st = _write_stations(tmp_path / "st.csv", [])
    sha = W.V1.sha256_file(st)
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps({"protocolSha256": DIGEST, "exclusions": {}}))
    L.begin("exclusions", W.PROTOCOL_ID, {}, {})
    L.complete("exclusions", W.PROTOCOL_ID, {"exclusions.json": W.V1.sha256_file(str(ex))}, {})
    (wqp / f"{W.slug('Wheeler|AL')}.resultdepth.csv").write_text("MonitoringLocationIdentifier,ActivityStartDate,ResultMeasureValue\nSYN-1,2023-06-01,20\n")
    with pytest.raises(SystemExit, match="non-whitelisted column"):
        W.cmd_census(P, DIGEST, L, str(wqp), st, sha, st, sha, str(ex), str(tmp_path / "c.json"))
    os.remove(wqp / f"{W.slug('Wheeler|AL')}.resultdepth.csv")
    W.cmd_census(P, DIGEST, L, str(wqp), st, sha, st, sha, str(ex), str(tmp_path / "c.json"))
    assert L.require("census", W.PROTOCOL_ID)["inputs"]["stationReviewed"] == sha
    with pytest.raises(SystemExit, match="already ran"):
        W.cmd_census(P, DIGEST, L, str(wqp), st, sha, st, sha, str(ex), str(tmp_path / "c2.json"))


# ------------------------------------------------------------------------------------------------------- step B
def test_step_b_gate(tmp_path):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)
    assert W.load_selection_for_step_b(L, sp, st, DIGEST, REQ)[1] == W.V1.sha256_file(sp)
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.load_selection_for_step_b(L, sp, st, DIGEST, "Claude request (under Owner approval 2026-11-22)")
    with pytest.raises(SystemExit, match="not recorded as complete"):
        W.load_selection_for_step_b(new_ledger(tmp_path / "elsewhere"), sp, st, DIGEST, REQ)
    with open(st, "a") as fh:
        fh.write("SYN-X,SYN,SYNTHETIC,1,1,Lay|AL,MAIN_BODY,late,\n")
    with pytest.raises(SystemExit, match="station file differs"):
        W.load_selection_for_step_b(L, sp, st, DIGEST, REQ)


def test_step_b_queries_and_the_derived_forcing_window(tmp_path):
    sel, *_ = step_a(tmp_path, new_ledger(tmp_path))
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
    sel, *_ = step_a(tmp_path, new_ledger(tmp_path))
    with pytest.raises(SystemExit, match="does not cover counted cast"):
        W.check_forcing(forcing(20.0, start="2022-03-01"), [d for lid, _, d in W.counted_casts(sel) if lid == "Lay|AL"])


def test_compare_pass_and_unknowns_count_against(tmp_path):
    sel, *_ = step_a(tmp_path, new_ledger(tmp_path))
    f = {lid: forcing(20.0) for lid in SEL_COUNTS}
    assert W.compare(P, sel, results_for(sel), f)["outcome"] == "PASS"
    rows = results_for(sel)
    del rows[5], rows[0]
    r = W.compare(P, sel, rows, f)
    assert r["outcome"] == "FAIL" and "CAST_NOT_RETURNED" in r["perLake"]["Guntersville|AL"]["failed"]
    r = W.compare(P, sel, results_for(sel), {k: v for k, v in f.items() if k != "Lay|AL"})
    assert r["perLake"]["Lay|AL"]["failed"] == ["FORCING_MISSING"] and r["outcome"] == "FAIL"
    c0 = W.counted_casts(sel)[0]
    r = W.compare(P, sel, results_for(sel), {**f, c0[0]: forcing(20.0, null_on={c0[2]})})
    assert "UNPAIRED_CAST" in r["perLake"][c0[0]]["failed"]
    rows = results_for(sel)
    for x in [x for x in rows if x["MonitoringLocationIdentifier"].startswith("SYN-Guntersville")][:12]:
        x["ResultMeasureValue"] = "99"
    assert W.compare(P, sel, rows, f)["perLake"]["Guntersville|AL"]["failed"] == ["SCORED_BELOW_25"]


def test_duplicate_and_uncounted_readings(tmp_path):
    sel, *_ = step_a(tmp_path, new_ledger(tmp_path))
    rows = results_for(sel)
    with pytest.raises(SystemExit, match="appears twice"):
        W.truth_values(sel, rows + [rows[0]])
    assert W.truth_values(sel, [dict(rows[0], ActivityIdentifier="NOT-COUNTED", ResultMeasureValue="5")])[0] == {}


def fetched(tmp_path, L, sel, sp, folder="fetch0", value="21.0"):
    """Step-B files and provenance written as the fetch commands write them, and recorded in the ledger the same way."""
    sha = W.V1.sha256_file(sp)
    rdir, fdir = tmp_path / folder / "rb", tmp_path / folder / "fb"
    L.begin("fetch-results", sha, {}, {})
    prov = []
    for q in W.result_queries(sel):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(result_row("x", "2022-01-01")))
        w.writeheader()
        w.writerow(result_row(q["siteid"], q["date"], value))
        W._save(str(rdir), q["file"], buf.getvalue().encode(), W.V1.WQP.format(kind="Result"), q["params"], prov)
    W.V1.write_provenance(str(rdir), "results.provenance.json", prov)
    W._bind_and_complete(L, "fetch-results", sha, str(rdir), "results.provenance.json", [q["file"] for q in W.result_queries(sel)])
    L.begin("fetch-forcing", sha, {}, {})
    prov = []
    for l in sel["lakes"]:
        W._save(str(fdir), W.forcing_file(l["lakeId"]), json.dumps(forcing(20.0)).encode(), W.V1.OPEN_METEO, W.forcing_params(P, sel, l["lakeId"]), prov)
    W.V1.write_provenance(str(fdir), "forcing.provenance.json", prov)
    W._bind_and_complete(L, "fetch-forcing", sha, str(fdir), "forcing.provenance.json", [W.forcing_file(l["lakeId"]) for l in sel["lakes"]])
    return str(rdir), str(fdir)


def test_cmd_compare_runs_once_per_selection_on_the_recorded_files(tmp_path):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)
    rdir, fdir = fetched(tmp_path, L, sel, sp)
    rec = W.cmd_compare(P, DIGEST, L, sp, st, rdir, fdir, REQ, str(tmp_path / "c0.json"))
    assert rec["outcome"] == "PASS" and L.require("compare", W.V1.sha256_file(sp))["result"]["outcome"] == "PASS"
    (tmp_path / "other").mkdir()
    with pytest.raises(SystemExit, match="already ran"):
        W.cmd_compare(P, DIGEST, L, sp, st, rdir, fdir, REQ, str(tmp_path / "other" / "c1.json"))


def test_edited_values_with_rewritten_provenance_are_refused(tmp_path):
    """The round-4 probe: edit values, rewrite provenance hashes to match, compare into a new folder."""
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)
    rdir, fdir = fetched(tmp_path, L, sel, sp)
    pp = os.path.join(rdir, "results.provenance.json")
    prov = json.load(open(pp))
    for it in prov["items"]:
        path = os.path.join(rdir, it["path"])
        open(path, "w").write(open(path).read().replace(",21.0,", ",19.0,"))
        it["sha256"] = W.V1.sha256_file(path)
    json.dump(prov, open(pp, "w"))
    with pytest.raises(SystemExit, match="changed after fetch-results recorded it"):
        W.cmd_compare(P, DIGEST, L, sp, st, rdir, fdir, REQ, str(tmp_path / "new" / "c.json"))
    with pytest.raises(SystemExit, match="not recorded as complete"):            # a fresh fetch folder never recorded in the ledger
        W.cmd_compare(P, DIGEST, new_ledger(tmp_path / "x"), sp, st, rdir, fdir, REQ, str(tmp_path / "c2.json"))


def test_second_fetch_is_refused_and_provenance_urls_are_checked(tmp_path):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)
    rdir, fdir = fetched(tmp_path, L, sel, sp)
    with pytest.raises(SystemExit, match="already ran"):
        W.cmd_fetch_results(P, DIGEST, L, sp, st, REQ, str(tmp_path / "fetch1"))
    with pytest.raises(SystemExit, match="already ran"):
        W.cmd_fetch_forcing(P, DIGEST, L, sp, st, REQ, str(tmp_path / "fetch1"))
    exp = {q["file"]: q["params"] for q in W.result_queries(sel)}
    with pytest.raises(SystemExit, match="was not fetched from"):
        W.verify_against_provenance(rdir, "results.provenance.json", exp, W._listing(rdir, "results"), W.V1.OPEN_METEO)
    W.verify_against_provenance(rdir, "results.provenance.json", exp, W._listing(rdir, "results"), W.V1.WQP.format(kind="Result"))
    os.remove(os.path.join(rdir, "results", sorted(os.listdir(os.path.join(rdir, "results")))[0]))
    with pytest.raises(SystemExit, match="does not hold exactly|missing"):
        W.verify_against_provenance(rdir, "results.provenance.json", exp, W._listing(rdir, "results"), W.V1.WQP.format(kind="Result"))


def test_failed_fetch_is_aborted_before_result_and_may_be_retried(tmp_path, monkeypatch):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)

    def boom(*a, **k):
        raise OSError("synthetic network failure")
    monkeypatch.setattr(W, "_get_bytes", boom)
    with pytest.raises(OSError):
        W.cmd_fetch_results(P, DIGEST, L, sp, st, REQ, str(tmp_path / "f0"))
    runs = [json.loads(x) for x in open(L.path) if '"fetch-results"' in x]
    assert [r["event"] for r in runs] == ["begin", "abort"]
    assert L.first("fetch-results", W.V1.sha256_file(sp)) is None


def test_cli_verify(capsys):
    assert W.main(["verify"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sha256"] == DIGEST and out["censusCutoff"] == "2026-11-22"
