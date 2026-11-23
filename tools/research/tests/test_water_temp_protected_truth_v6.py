"""PT-L4-2026-11-23-v6 runner, offline. Every fixture is hand-built and synthetic: synthetic square 'polygons' around the
directory points, synthetic station ids (SYN-*), synthetic counts and temperatures. No real cast, site or value. Run ledgers
live in pytest's tmp_path and Sector_Ops #51 is a fake issue (no network)."""
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
import water_temp_protected_truth_v6 as W  # noqa: E402

P, DIGEST = W.load_protocol()
PTS = {l["lakeId"]: l["point"] for l in P["universe"]["lakes"]}
REQ = "Owner request (Michael, 2099-01-01): synthetic test"
DOCS = os.path.join(W.REPO, "docs", "brains")
V2 = os.path.join(DOCS, "water-temp-protected-truth-v2", "PT-L4-2026-11-23-v2.protocol.json")
V3 = os.path.join(DOCS, "water-temp-protected-truth-v3", "PT-L4-2026-11-23-v3.protocol.json")
V4 = os.path.join(DOCS, "water-temp-protected-truth-v4", "PT-L4-2026-11-23-v4.protocol.json")
V5 = os.path.join(DOCS, "water-temp-protected-truth-v5", "PT-L4-2026-11-23-v5.protocol.json")

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
    assert P["protocolId"] == "PT-L4-2026-11-23-v6" and P["censusCutoff"] == W.CUTOFF == "2026-11-22" and len(P["universe"]["lakes"]) == 62
    assert P["minimums"] == {"perLake": 25, "total": 150, "lakes": 4} == {"perLake": W.PER_LAKE, "total": W.TOTAL, "lakes": W.SLOTS}
    assert P["passMark"]["pooledEqualLakeRmseC"]["value"] == P["passMark"]["perLakeRmseC"]["value"] == W.RMSE_MARK
    assert "INSUFFICIENT_PAIRED" not in json.dumps(P["passMark"]["outcomes"])


def test_superseded_protocols_are_kept_byte_identical_and_refused():
    assert W.V1.sha256_file(V2) == "e02e2e08740767dec4720a610c112010eb78ad73ad1b223b14365489a499867d"
    assert W.V1.sha256_file(V3) == "ebc1a77b1977924c2bb586340887f2fad7a3196b20bf4f2ef2305853716f170d"
    assert W.V1.sha256_file(V4) == "aac78d48276ba692d7f485971e594c01c000ccc966631f4900bf46a817a096e0"
    assert W.V1.sha256_file(V5) == "c2367bf246e62f2214e4b0110c2f2e920ad3184e299d05a40ea6486a7c1b7509"
    for old in (V2, V3, V4, V5):
        with pytest.raises(SystemExit, match="executes PT-L4-2026-11-23-v6 only"):
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




# ------------------------------------------------------------------------------------------------------- run ledger (shared module, fake #51)
RL = W.RL
ISSUE_PATH = f"repos/{RL.ANCHOR_REPO}/issues/{RL.ANCHOR_ISSUE}/comments?per_page=100"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.delenv(RL.ENV_ROOT, raising=False)

    def refuse(path):
        raise AssertionError(f"a test reached the real gh: {path}")
    monkeypatch.setattr(RL, "_gh_api", refuse)


class Issue:
    """A fake Sector_Ops #51 behind `gh api --paginate` (synthetic comments only)."""

    def __init__(self):
        self.comments, self.next_id = [], 5000
        self.clock = dt.datetime(2026, 11, 23, tzinfo=dt.timezone.utc)

    def post(self, body):
        self.clock += dt.timedelta(minutes=1)
        t = self.clock.strftime("%Y-%m-%dT%H:%M:%SZ")
        cid, self.next_id = self.next_id, self.next_id + 1
        self.comments.append({"id": cid, "created_at": t, "updated_at": t, "body": body, "html_url": f"https://example.invalid/51#{cid}"})

    def __call__(self, path):
        assert path == ISSUE_PATH, path
        return json.dumps(self.comments)


def new_ledger(tmp_path, anchored=True, issue=None):
    root = tmp_path / "research" / "water-temperature"
    root.mkdir(parents=True, exist_ok=True)
    issue = issue or Issue()
    L = RL.Ledger(root, W.PROTOCOL_ID, DIGEST, gh=issue, result_steps=W.RESULT_STEPS)
    L.issue = issue
    if anchored and not any(c["body"].startswith(f"Run anchor: {W.PROTOCOL_ID} {L.anchor()}") for c in issue.comments):
        issue.post(L.post_anchor_text())
    return L


def publisher(L):
    posted = []

    def publish(text, confirm, what):
        posted.append(what)
        L.issue.post(text)
        return confirm()
    publish.posted = posted
    return publish


def test_protocol_declares_the_runners_result_steps_and_keys():
    W.check_ledger_constants(P)
    assert P["runLedger"]["resultSteps"] == ["compare", "select"] and P["runLedger"]["keys"] == W.STEP_KEYS
    assert all("shim" not in n for n in os.listdir(os.path.join(W.REPO, "tools", "research")))


def test_anchor_text_names_protocol_result_steps_and_sha(tmp_path):
    L = new_ledger(tmp_path, anchored=False)
    first = L.post_anchor_text().splitlines()[0]
    assert first == f"Run anchor: {W.PROTOCOL_ID} {L.anchor()} compare,select {DIGEST}"
    with pytest.raises(RL.LedgerRefusal, match="no `Run anchor:"):
        L.require_external_anchor()


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


def test_no_step_runs_before_the_anchor(tmp_path):
    L = new_ledger(tmp_path, anchored=False)
    reg, sites, cal, lakes = _exclusion_inputs(tmp_path)
    with pytest.raises(RL.LedgerRefusal, match="Run anchor"):
        W.cmd_exclusions(P, DIGEST, L, reg, sites, cal, lakes, None, str(tmp_path / "ex.json"))


def test_exclusions_run_once_and_record_their_inputs(tmp_path):
    L = new_ledger(tmp_path)
    reg, sites, cal, lakes = _exclusion_inputs(tmp_path)
    (tmp_path / "run0").mkdir()
    rec = W.cmd_exclusions(P, DIGEST, L, reg, sites, cal, lakes, None, str(tmp_path / "run0" / "ex.json"))
    assert rec["calibrationLakes"] == ["Jordan|AL"] and rec["exclusions"]["Jordan|AL"][0].startswith("M0_TUNING")
    done = W._completed(L, "exclusions")
    assert done["inputs"]["calibrationLakes"] == W.V1.sha256_file(lakes) and "wtSat1" not in done["inputs"]
    assert done["outputs"]["exclusions.json"] == W.V1.sha256_file(str(tmp_path / "run0" / "ex.json"))
    (tmp_path / "run1").mkdir()
    with pytest.raises(RL.LedgerRefusal, match="already ran"):
        W.cmd_exclusions(P, DIGEST, L, reg, sites, cal, lakes, None, str(tmp_path / "run1" / "ex.json"))


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
    assert W.census(P, rows, {"SYN-0": dict(st["SYN-0"], lakeId="Lay|AL")})["waters"]["Lay|AL"]["qualifyingCasts"] == 3


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
    """exclusions and census recorded through the ledger as non-result steps (synthetic census content), then the real select."""
    d = tmp_path / folder
    d.mkdir()
    st = _write_stations(d / "st.csv", [])
    ssha = W.V1.sha256_file(st)
    ex = d / "ex.json"
    ex.write_text(json.dumps({"protocolSha256": DIGEST, "exclusions": {}}))
    W._run_plain(L, "exclusions", {}, {}, lambda: (None, {"exclusions.json": W.V1.sha256_file(str(ex))}))
    cp = d / "census.json"
    cp.write_text(json.dumps({"protocolSha256": DIGEST, "stationDraftSha256": ssha, "stationFileSha256": ssha,
                              "exclusionsSha256": W.V1.sha256_file(str(ex)), **census_with(SEL_COUNTS)}))
    W._run_plain(L, "census", {}, {"stationDraft": ssha, "stationReviewed": ssha}, lambda: (None, {"census.json": W.V1.sha256_file(str(cp))}))
    sp = d / "selection.json"
    pub = publisher(L)
    sel = W.cmd_select(P, DIGEST, L, str(cp), str(ex), str(sp), pub)
    assert pub.posted == ["start", "result"]
    return sel, str(sp), st, str(cp), str(ex)


def test_select_is_a_result_step_with_public_start_and_result(tmp_path):
    L = new_ledger(tmp_path)
    sel, sp, st, cp, ex = step_a(tmp_path, L)
    e = L.require("select", "all")
    assert e["counted"] is True and e["outputs"]["selection.json"] == W.V1.sha256_file(sp) and e["result"]["outcome"] == "SELECTED"
    firsts = [c["body"].splitlines()[0].split()[:4] for c in L.issue.comments]
    assert [f[:2] for f in firsts] == [["Run", "anchor:"], ["Run", "start:"], ["Run", "result:"]]
    assert any(x["status"] == RL.RESULT_CONFIRMED and x["step"] == "select" for x in L.entries())
    (tmp_path / "run1").mkdir()
    with pytest.raises(RL.LedgerRefusal, match="already ran"):
        W.cmd_select(P, DIGEST, L, cp, ex, str(tmp_path / "run1" / "selection.json"), publisher(L))
    other = tmp_path / "run1" / "selection.json"
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
    with pytest.raises(RL.LedgerRefusal, match="no COMPLETED run"):
        W.cmd_census(P, DIGEST, L, str(d), st, sha, st, sha, str(ex), str(d / "c.json"))
    with pytest.raises(RL.LedgerRefusal, match="no COMPLETED run"):
        W.cmd_select(P, DIGEST, L, str(d / "c.json"), str(ex), str(d / "s.json"), publisher(L))


def test_census_runs_once_and_refuses_non_whitelisted_columns(tmp_path):
    L = new_ledger(tmp_path)
    wqp = tmp_path / "wqp"
    wqp.mkdir()
    st = _write_stations(tmp_path / "st.csv", [])
    sha = W.V1.sha256_file(st)
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps({"protocolSha256": DIGEST, "exclusions": {}}))
    W._run_plain(L, "exclusions", {}, {}, lambda: (None, {"exclusions.json": W.V1.sha256_file(str(ex))}))
    (wqp / f"{W.slug('Wheeler|AL')}.resultdepth.csv").write_text("MonitoringLocationIdentifier,ActivityStartDate,ResultMeasureValue\nSYN-1,2023-06-01,20\n")
    with pytest.raises(SystemExit, match="non-whitelisted column"):
        W.cmd_census(P, DIGEST, L, str(wqp), st, sha, st, sha, str(ex), str(tmp_path / "c.json"))
    os.remove(wqp / f"{W.slug('Wheeler|AL')}.resultdepth.csv")
    W.cmd_census(P, DIGEST, L, str(wqp), st, sha, st, sha, str(ex), str(tmp_path / "c.json"))
    assert W._completed(L, "census")["inputs"]["stationReviewed"] == sha
    with pytest.raises(RL.LedgerRefusal, match="already ran"):
        W.cmd_census(P, DIGEST, L, str(wqp), st, sha, st, sha, str(ex), str(tmp_path / "c2.json"))


def test_publish_waits_for_listing_and_never_reposts(tmp_path):
    posts, calls, slept = [], [], []

    def confirm():
        calls.append(1)
        if len(calls) < 3:
            raise RL.LedgerRefusal("`Run start: x` on repo#51: not listed yet: wait and retry confirm_started(); do NOT repost")
        return {"ok": True}
    assert W.publish_and_confirm("Run start: x", confirm, posts.append, None, 3600, slept.append) == {"ok": True}
    assert posts == ["Run start: x"] and len(calls) == 3 and len(slept) == 2
    with pytest.raises(RL.LedgerRefusal, match="not listed yet"):
        W.publish_and_confirm("Run start: y", lambda: (_ for _ in ()).throw(RL.LedgerRefusal("not listed yet")), posts.append, None, 30, slept.append)
    path = tmp_path / "start.txt"
    with pytest.raises(RL.LedgerRefusal, match="other"):
        W.publish_and_confirm("Run start: z", lambda: (_ for _ in ()).throw(RL.LedgerRefusal("other")), None, str(path), 30, slept.append)
    assert path.read_text() == "Run start: z"                    # written for the operator to post by hand


def test_research_records_never_carry_an_owner_header():
    with pytest.raises(SystemExit, match="never carry an Owner header"):
        W.gh_post("Owner request (Michael, 2099-01-01): x")


def test_unconfirmed_start_is_aborted_before_any_value(tmp_path):
    L = new_ledger(tmp_path)
    computed = []

    def publish(text, confirm, what):
        raise RL.LedgerRefusal("not listed yet (timeout)")
    with pytest.raises(RL.LedgerRefusal):
        W._run_result(L, "select", {}, {}, lambda: computed.append(1), publish)
    assert computed == [] and [e["status"] for e in L.entries() if e["step"] == "select"] == [RL.STARTED, RL.ABORTED]


# ------------------------------------------------------------------------------------------------------- step B
def test_step_b_gate(tmp_path):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)
    assert W.load_selection_for_step_b(L, sp, st, DIGEST, REQ)[1] == W.V1.sha256_file(sp)
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.load_selection_for_step_b(L, sp, st, DIGEST, "Claude request (under Owner approval 2026-11-22)")
    with pytest.raises(RL.LedgerRefusal, match="no COMPLETED run"):
        W.load_selection_for_step_b(new_ledger(tmp_path / "elsewhere"), sp, st, DIGEST, REQ)
    with open(st, "a") as fh:
        fh.write("SYN-X,SYN,SYNTHETIC,1,1,Lay|AL,MAIN_BODY,late,\n")
    with pytest.raises(SystemExit, match="station file differs"):
        W.load_selection_for_step_b(L, sp, st, DIGEST, REQ)


def test_step_b_queries_and_the_derived_forcing_window(tmp_path):
    sel, *_ = step_a(tmp_path, new_ledger(tmp_path))
    qs = W.result_queries(sel)
    assert len(qs) == sum(SEL_COUNTS.values()) and all(q["params"]["startDateLo"] == q["params"]["startDateHi"] and "bBox" not in q["params"] for q in qs)
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


def test_compare_pass_and_unknowns_count_against(tmp_path):
    sel, *_ = step_a(tmp_path, new_ledger(tmp_path))
    f = {lid: forcing(20.0) for lid in SEL_COUNTS}
    assert W.compare(P, sel, results_for(sel), f)["outcome"] == "PASS"
    rows = results_for(sel)
    del rows[5], rows[0]
    assert "CAST_NOT_RETURNED" in W.compare(P, sel, rows, f)["perLake"]["Guntersville|AL"]["failed"]
    r = W.compare(P, sel, results_for(sel), {k: v for k, v in f.items() if k != "Lay|AL"})
    assert r["perLake"]["Lay|AL"]["failed"] == ["FORCING_MISSING"] and r["outcome"] == "FAIL"
    c0 = W.counted_casts(sel)[0]
    assert "UNPAIRED_CAST" in W.compare(P, sel, results_for(sel), {**f, c0[0]: forcing(20.0, null_on={c0[2]})})["perLake"][c0[0]]["failed"]
    rows = results_for(sel)
    for x in [x for x in rows if x["MonitoringLocationIdentifier"].startswith("SYN-Guntersville")][:12]:
        x["ResultMeasureValue"] = "99"
    assert W.compare(P, sel, rows, f)["perLake"]["Guntersville|AL"]["failed"] == ["SCORED_BELOW_25"]
    with pytest.raises(SystemExit, match="appears twice"):
        W.truth_values(sel, results_for(sel) + [results_for(sel)[0]])


def fake_sources(monkeypatch, value="21.0"):
    """Serve synthetic step-B bodies by request parameters (no network)."""
    def get(url, params=None):
        if url == W.V1.OPEN_METEO:
            return json.dumps(forcing(20.0)).encode()
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(result_row("x", "2022-01-01")))
        w.writeheader()
        w.writerow(result_row(params["siteid"], dt.datetime.strptime(params["startDateLo"], "%m-%d-%Y").date().isoformat(), value))
        return buf.getvalue().encode()
    monkeypatch.setattr(W, "_get_bytes", get)


def step_b(tmp_path, L, sp, st, monkeypatch):
    fake_sources(monkeypatch)
    rdir, fdir = str(tmp_path / "rb"), str(tmp_path / "fb")
    W.cmd_fetch_results(P, DIGEST, L, sp, st, REQ, rdir)
    W.cmd_fetch_forcing(P, DIGEST, L, sp, st, REQ, fdir)
    return rdir, fdir


def test_compare_is_a_result_step_once_per_selection(tmp_path, monkeypatch):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)
    rdir, fdir = step_b(tmp_path, L, sp, st, monkeypatch)
    with pytest.raises(RL.LedgerRefusal, match="already ran"):
        W.cmd_fetch_results(P, DIGEST, L, sp, st, REQ, str(tmp_path / "rb2"))
    pub = publisher(L)
    rec = W.cmd_compare(P, DIGEST, L, sp, st, rdir, fdir, REQ, str(tmp_path / "c0.json"), pub)
    assert rec["outcome"] == "PASS" and pub.posted == ["start", "result"]
    e = L.require("compare", "selection")
    assert e["counted"] is True and e["result"]["outcome"] == "PASS"
    (tmp_path / "other").mkdir()
    with pytest.raises(RL.LedgerRefusal, match="already ran"):
        W.cmd_compare(P, DIGEST, L, sp, st, rdir, fdir, REQ, str(tmp_path / "other" / "c1.json"), publisher(L))
    assert L.audit(check_external=True)["findings"] == []


def test_edited_values_with_rewritten_provenance_are_refused(tmp_path, monkeypatch):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)
    rdir, fdir = step_b(tmp_path, L, sp, st, monkeypatch)
    pp = os.path.join(rdir, "results.provenance.json")
    prov = json.load(open(pp))
    for it in prov["items"]:
        path = os.path.join(rdir, it["path"])
        open(path, "w").write(open(path).read().replace(",21.0,", ",19.0,"))
        it["sha256"] = W.V1.sha256_file(path)
    json.dump(prov, open(pp, "w"))
    with pytest.raises(RL.LedgerRefusal, match="changed since it was bound"):
        W.cmd_compare(P, DIGEST, L, sp, st, rdir, fdir, REQ, str(tmp_path / "new" / "c.json"), publisher(L))
    assert not any(e["step"] == "compare" for e in L.entries())          # refused before begin: nothing started


def test_provenance_urls_are_checked(tmp_path, monkeypatch):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)
    rdir, fdir = step_b(tmp_path, L, sp, st, monkeypatch)
    exp = {q["file"]: q["params"] for q in W.result_queries(sel)}
    with pytest.raises(SystemExit, match="was not fetched from"):
        W.verify_against_provenance(rdir, "results.provenance.json", exp, W._listing(rdir, "results"), W.V1.OPEN_METEO)
    W.verify_against_provenance(rdir, "results.provenance.json", exp, W._listing(rdir, "results"), W.V1.WQP.format(kind="Result"))


def test_failed_fetch_is_aborted_before_result_and_may_be_retried(tmp_path, monkeypatch):
    L = new_ledger(tmp_path)
    sel, sp, st, *_ = step_a(tmp_path, L)

    def boom(*a, **k):
        raise OSError("synthetic network failure")
    monkeypatch.setattr(W, "_get_bytes", boom)
    with pytest.raises(OSError):
        W.cmd_fetch_results(P, DIGEST, L, sp, st, REQ, str(tmp_path / "f0"))
    assert [e["status"] for e in L.entries() if e["step"] == "fetch-results"] == [RL.STARTED, RL.ABORTED]
    fake_sources(monkeypatch)
    assert W.cmd_fetch_results(P, DIGEST, L, sp, st, REQ, str(tmp_path / "f1"))["files"] == sum(SEL_COUNTS.values())


def test_cli_verify(capsys):
    assert W.main(["verify"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sha256"] == DIGEST and out["censusCutoff"] == "2026-11-22" and out["resultSteps"] == ["compare", "select"]
