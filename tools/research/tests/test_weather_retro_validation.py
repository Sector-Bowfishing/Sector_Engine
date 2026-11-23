"""Offline tests for the Weather retrospective validation runner (protocol WX-RETRO-2026-11-23.2; v1 superseded). No network: every input is a fixture.
Synthetic archive rows are labelled SYNTHETIC; the NWS responses are the Weather Brain's RECORDED fixtures of 2026-11-06."""
import copy
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import weather_retro_validation as W  # noqa: E402

REC = os.path.join(W.REPO, "brains", "weather", "tests", "fixtures", "recorded")
LAKE = {"id": "Guntersville|AL", "lat": 34.42, "lon": -86.26}
UTC = timezone.utc
HEADER = "station,valid,tmpf,dwpf,relh,drct,sknt,alti,mslp,p01i,skyc1,skyc2,skyc3,skyc4,wxcodes"


def rec(name):
    return json.load(open(os.path.join(REC, name)))


# ------------------------------------------------------------------------------------------------ protocol
def test_protocol_hash_verifies_and_matches_the_registered_value():
    p, d = W.load_protocol()
    assert p["protocolId"] == "WX-RETRO-2026-11-23.2"
    assert d == open(W.PROTOCOL + ".sha256").read().split()[0]
    assert p["status"] == "PRE-REGISTERED" and "RETROSPECTIVE" in p["labels"]


def test_v1_is_kept_unchanged_and_superseded():
    v1 = os.path.join(os.path.dirname(W.PROTOCOL), "WX-RETRO-2026-11-23.protocol.json")
    p1, d1 = W.load_protocol(v1)                                                             # its hash still verifies
    assert d1 == "6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8"
    p, _ = W.load_protocol()
    assert p["supersedes"]["sha256"] == d1 and W.PROTOCOL != v1


def test_disclosed_fixtures_are_excluded_spans():
    p, _ = W.load_protocol()
    assert "2026-11-06" in p["dataExaminedBeforeRegistration"]
    sp = W._spans(p)
    assert sp and {"Guntersville|AL", "Champlain|VT"} <= sp[0][0]
    assert sp[0][1] <= datetime(2026, 11, 6, 7, 51, tzinfo=UTC) and sp[0][2] >= datetime(2026, 11, 6, 20, 51, tzinfo=UTC)


def test_a_tampered_protocol_is_refused(tmp_path):
    f = tmp_path / "p.json"
    shutil.copy(W.PROTOCOL, f)
    shutil.copy(W.PROTOCOL + ".sha256", str(f) + ".sha256")
    f.write_text(f.read_text().replace('"POD >= 0.8', '"POD >= 0.5'))
    with pytest.raises(SystemExit, match="REFUSED"):
        W.load_protocol(str(f))


def test_protocol_marks_are_the_plans():
    p, _ = W.load_protocol()
    c = p["criteria"]
    assert "0.05 hPa" in " ".join(c["R-5.1R"]["checks"]) and "99.5 %" in c["R-5.1R"]["pass"]
    assert "NOT the plan's 5.1" in c["R-5.1R"]["plan"]
    assert "ALL truth" in c["R-5.3"]["RAIN_ONSET"]["PODpopulation"] and "ALL episodes" in c["R-5.3"]["FRONT_PASSAGE"]["PODpopulation"]
    assert "<= 1.0 hPa" in c["R-5.2"]["metrics"]["pressureMAE"] and ">= 0.80" in c["R-5.2"]["metrics"]["trend3hAgreement"]
    assert "<= 3.0 deg F" in c["R-5.2"]["metrics"]["airTempMAE"]
    assert c["R-5.3"]["RAIN_ONSET"]["pass"] == "POD >= 0.8 and FAR <= 0.3"
    assert c["R-5.3"]["FRONT_PASSAGE"]["pass"] == "POD >= 0.6 and FAR <= 0.4"


def test_instants_are_hourly_at_ten_past():
    xs = W.instants(datetime(2026, 9, 20, tzinfo=UTC), datetime(2026, 9, 20, 3, tzinfo=UTC))
    assert [x.strftime("%H:%M") for x in xs] == ["00:10", "01:10", "02:10"]
    p, _ = W.load_protocol()
    assert len(W.instants(*W.window(p, "changeSignal_5_3"))) == 60 * 24


# ------------------------------------------------------------------------------------------------ network guard
def test_http_refuses_hosts_outside_the_protocol():
    def boom(*a, **k):
        raise AssertionError("must not open")
    with pytest.raises(SystemExit, match="not allowlisted"):
        W.Http(opener=boom).get("https://example.com/x")
    with pytest.raises(SystemExit, match="not allowlisted"):
        W.Http(opener=boom).get("http://mesonet.agron.iastate.edu/x")


def test_redirects_are_refused():
    import urllib.request
    with pytest.raises(RuntimeError, match="REFUSED redirect"):
        W._NoRedirect().redirect_request(urllib.request.Request("https://api.weather.gov/x"), None, 301, "Moved", {}, "https://elsewhere.example/")
    assert W.USER_AGENT.startswith("Sector-WeatherRetroValidation/0.2") or os.environ.get("SECTOR_WEATHER_USER_AGENT")


# ------------------------------------------------------------------------------------------------ station selection (recorded NWS list)
def test_station_selection_is_the_brains_and_the_independent_is_not_one_of_them():
    st = W.decode_stations(rec("guntersville-stations.json"))
    sel = W.select_stations(LAKE, st)
    assert [s["id"] for s in sel["brainStations"]] == ["K8A1", "KBFZ", "K4A6"]            # publish.resolve_point: first 3
    ids = [c["id"] for c in sel["candidates"]]
    assert not set(ids) & {"K8A1", "KBFZ", "K4A6"}
    assert ids == []                                    # K4A9 (30.9 mi) and KHSV (33.7 mi) are beyond 25 mi: no independent station
    st2 = st + [{"id": "KSYN2", "name": "SYNTHETIC", "lat": 34.60, "lon": -86.26}, {"id": "KSYN1", "name": "SYNTHETIC", "lat": 34.50, "lon": -86.26}]
    sel2 = W.select_stations(LAKE, st2)
    assert [c["id"] for c in sel2["candidates"]] == ["KSYN1", "KSYN2"]                       # nearest first
    assert [s["id"] for s in sel2["brainStations"]] == ["K8A1", "KBFZ", "K4A6"]
    assert all(c["distanceToBrainStationMi"] >= 3.0 for c in sel2["candidates"])
    k8a1 = next(x for x in st if x["id"] == "K8A1")                                           # SYNTHETIC: a sensor next to K8A1
    sel3 = W.select_stations(LAKE, st + [{"id": "KNEAR", "name": "SYNTHETIC", "lat": k8a1["lat"] + 0.01, "lon": k8a1["lon"]}])
    assert "KNEAR" not in [c["id"] for c in sel3["candidates"]]


def test_iem_station_ids():
    assert W.iem_id("KBFZ") == "BFZ" and W.iem_id("K4A6") == "4A6"
    assert W.iem_id("PANC") == "PANC" and W.iem_id("KXYZW") == "KXYZW"
    q = dict(W.iem_params("KBFZ", datetime(2026, 9, 19, 11, tzinfo=UTC), datetime(2026, 11, 19, 3, tzinfo=UTC)))
    assert q["station"] == "BFZ" and q["tz"] == "Etc/UTC" and q["missing"] == "null"
    assert [v for k, v in W.iem_params("KBFZ", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)) if k == "report_type"] == ["3", "4"]


# ------------------------------------------------------------------------------------------------ archive adapter
def test_wxcodes_map_to_text_the_brain_reads_as_precipitation():
    assert W.wx_text("-RA BR") == "Light Rain"
    assert W.wx_text("+TSRA") == "Thunderstorm"
    assert W.wx_text("SHRA") == "Rain Showers"
    assert W.wx_text("BR") == "Mist"
    assert W.wx_text("") is None and W.wx_text(None) is None
    assert W.wx_text("BR -RA") == "Light Rain"                                              # the earliest row wins, not the first token
    assert W.wx_text("HZ +TSRA") == "Thunderstorm"
    assert W.wx_text("VCSH") == "Showers in Vicinity" and W.wx_text("VCTS") == "Thunderstorm in Vicinity"
    assert W.wx_text("VCFG") == "Fog in Vicinity" and W.wx_text("-RA VCTS") == "Light Rain"
    for wx in ("-RA", "+TSRA", "SHRA", "-DZ", "SN", "FZRA"):
        assert W.weather_code(None, W.wx_text(wx), None) in W.PRECIP_CODES, wx
    for wx in ("BR", "FG", "UP"):
        assert W.weather_code(None, W.wx_text(wx), None) not in W.PRECIP_CODES, wx


def test_iem_csv_parses_to_brain_units():
    text = "\n".join(["#DEBUG: comment", HEADER,
                      "BFZ,2026-11-05 13:53,61.00,50.00,67.0,180.00,10.00,30.00,1016.20,0.0001,BKN,OVC,null,null,-RA",
                      "BFZ,2026-11-05 12:53,null,null,null,null,null,null,null,null,null,null,null,null,null"])
    obs = W.parse_iem_csv(text, "KBFZ")
    assert [o.at.hour for o in obs] == [13, 12]                                             # newest first
    o = obs[0]
    assert o.station == "KBFZ" and o.temp_f == 61.0 and o.rh == 67.0
    assert o.alt_hpa == pytest.approx(30.00 / 0.0295299830714) and o.slp_hpa == 1016.2
    assert o.wind_mph == pytest.approx(11.50779) and o.wind_dir == 180.0
    assert o.precip_1h_in < 0.01 and o.layer_pct == 100.0 and o.text == "Light Rain"
    assert obs[1].temp_f is None and obs[1].alt_hpa is None                                   # missing stays missing, never filled


def test_series_lookback_is_the_brains_13h_request():
    base = datetime(2026, 11, 5, 0, 53, tzinfo=UTC)
    s = W.Series([W.Obs("KX", base + timedelta(hours=h)) for h in range(30)])
    now = datetime(2026, 11, 6, 0, 10, tzinfo=UTC)
    lb = s.lookback(now)
    assert lb[0].at < now and lb[-1].at >= now - timedelta(hours=13) and lb[0].at > lb[-1].at
    assert s.nearest(now, 30, lambda o: True).at == datetime(2026, 11, 5, 23, 53, tzinfo=UTC)
    assert s.nearest(now, 10, lambda o: True) is None


# ------------------------------------------------------------------------------------------------ fronts
CODSUS = """000
ASUS01 KWBC 151800
CODSUS
CODED SURFACE FRONTAL POSITIONS...NWS WEATHER PREDICTION CENTER
VALID 101515Z
HIGHS 1030 4001010
LOWS 1002 3550870
COLD WK 3550870 3440865 3330862
 3200860
STNRY 3442860 3442870
WARM 3550870 3580850
TROF 3440863 3300860

VALID 101518Z
COLD 3600850 3500840
VALID 101521Z
COLD 36 87 34 86
"""


def test_codsus_parse_high_resolution_types_and_ineligible_low_resolution():
    a = W.parse_codsus(CODSUS, datetime(2026, 10, 20, tzinfo=UTC))
    t15, t18, t21 = (datetime(2026, 10, 15, h, tzinfo=UTC) for h in (15, 18, 21))
    assert a[t15]["eligible"] and a[t18]["eligible"] and not a[t21]["eligible"]
    kinds = [k for k, _ in a[t15]["fronts"]]
    assert kinds == ["COLD", "WARM"]                                                         # STNRY and TROF excluded
    cold = a[t15]["fronts"][0][1]
    assert cold[0] == (35.5, -87.0) and cold[-1] == (32.0, -86.0) and len(cold) == 4           # continuation line joined


TWO_PRODUCTS = """\x01
000
ASUS01 KWBC 151900
CODSUS
CODED SURFACE FRONTAL POSITIONS...NWS WEATHER PREDICTION CENTER
VALID 101518Z
COLD 3600850 3500840
 3400830
\x03
\x01
000
ASUS01 KWBC 151800
CODSUS
CODED SURFACE FRONTAL POSITIONS...NWS WEATHER PREDICTION CENTER
VALID 101518Z
WARM 3000800 3100810
\x03
"""


def test_codsus_separator_does_not_poison_the_previous_bulletin_and_latest_issuance_wins():
    a = W.parse_codsus(TWO_PRODUCTS, datetime(2026, 10, 20, tzinfo=UTC))
    t = datetime(2026, 10, 15, 18, tzinfo=UTC)
    assert a[t]["eligible"]                                                                    # the '000' separator is not a coordinate
    assert a[t]["bulletins"] == 2 and a[t]["issued"] == datetime(2026, 10, 15, 19, tzinfo=UTC)
    assert [k for k, _ in a[t]["fronts"]] == ["COLD"]                                          # 1900Z beats 1800Z although it came first
    assert a[t]["fronts"][0][1][-1] == (34.0, -83.0)


def test_front_distance_and_episodes():
    assert W.dist_to_polyline_mi(34.42, -86.26, [(34.0, -86.26), (35.0, -86.26)]) == pytest.approx(0.0, abs=1e-6)
    assert W.dist_to_polyline_mi(34.42, -86.26, [(34.42, -87.26)]) == pytest.approx(69.05 * 0.8246, rel=0.01)
    a = W.parse_codsus(CODSUS, datetime(2026, 10, 20, tzinfo=UTC))
    eps = W.front_episodes(34.42, -86.26, a)
    assert eps == [(datetime(2026, 10, 15, 15, tzinfo=UTC), datetime(2026, 10, 15, 15, tzinfo=UTC))]


# ------------------------------------------------------------------------------------------------ substitution check (recorded NWS vs adapter)
def test_substitution_check_agrees_when_the_archive_carries_the_same_reports(tmp_path):
    nws = W.decode_observations(rec("guntersville-obs-KBFZ.json"))
    assert nws
    rows = [HEADER]
    for o in nws:
        f = lambda v, nd=2: "null" if v is None else f"{v:.{nd}f}"  # noqa: E731
        alti = None if o.alt_hpa is None else round(o.alt_hpa * 0.0295299830714, 2)
        rows.append(",".join(["BFZ", o.at.strftime("%Y-%m-%d %H:%M"), f(o.temp_f), f(o.dew_f), f(o.rh), "null", "null",
                              f(alti), f(o.slp_hpa), f(o.precip_1h_in, 4), "null", "null", "null", "null", "null"]))
    (tmp_path / "recent").mkdir()
    (tmp_path / "recent" / "KBFZ.csv").write_text("\n".join(rows))
    (tmp_path / "nws").mkdir()
    shutil.copy(os.path.join(REC, "guntersville-obs-KBFZ.json"), tmp_path / "nws" / "KBFZ.json")
    r = W.substitution_check(["KBFZ"], W.Archive(str(tmp_path / "recent")), str(tmp_path / "nws"))
    m = r["metrics"]
    assert r["coverage"]["share"] == 1.0 and m["temperature"]["value"]["agreement"] == 1.0
    assert m["pressure"]["value"]["pairs"] == 0 or m["pressure"]["value"]["agreement"] == 1.0
    assert set(m) >= {"temperature", "dewPoint", "pressure", "windSpeed", "windDirection", "precipitation", "presentWeatherPresence"}
    assert m["windSpeed"]["null"]["agreement"] < 1.0                                         # wind left null in the archive copy: measured
    assert m["temperature"]["value"]["result"] == "INSUFFICIENT"                             # < 1000 pairs
    g = W.gates(r)
    assert not g["R-5.2"]["ok"] and "temperature" in g["R-5.2"]["notPassing"]
    assert r["flaggedStations"] == []
    assert W.substitution_check(["K8A1"], W.Archive(None), None)["result"] == "NOT_GRADED"


def test_gates_need_value_and_null_agreement_and_coverage():
    ok = {"value": {"result": "PASS"}, "null": {"result": "PASS"}}
    sub = {"coverage": {"result": "PASS"}, "metrics": {k: dict(ok) for k in W.SUB_FIELDS} | {"presentWeatherPresence": {"value": {"result": "PASS"}}}}
    assert all(v["ok"] for v in W.gates(sub).values())
    sub["metrics"]["windDirection"] = {"value": {"result": "PASS"}, "null": {"result": "FAIL"}}
    g = W.gates(sub)
    assert not g["R-5.3.FRONT_PASSAGE"]["ok"] and g["R-5.3.RAIN_ONSET"]["ok"] and g["R-5.2"]["ok"]
    sub["coverage"]["result"] = "FAIL"
    assert not any(v["ok"] for v in W.gates(sub).values())


def test_a_station_below_the_coverage_floor_is_flagged(tmp_path):
    base = datetime(2026, 11, 20, 0, 53, tzinfo=UTC)
    feats = [{"properties": {"station": "https://api.weather.gov/stations/KLOW", "timestamp": (base + timedelta(hours=h)).isoformat(),
                             "temperature": {"unitCode": "wmoUnit:degC", "value": 10.0}}} for h in range(30)]
    (tmp_path / "nws").mkdir()
    (tmp_path / "nws" / "KLOW.json").write_text(json.dumps({"features": feats}))
    (tmp_path / "recent").mkdir()
    rows = [HEADER] + [f"KLOW,{(base + timedelta(hours=h)).strftime('%Y-%m-%d %H:%M')},50.00" + ",null" * 12 for h in range(10)]
    (tmp_path / "recent" / "KLOW.csv").write_text("\n".join(rows))
    r = W.substitution_check(["KLOW"], W.Archive(str(tmp_path / "recent")), str(tmp_path / "nws"))
    assert r["flaggedStations"] == ["KLOW"] and r["perStation"]["KLOW"]["coverage"] == pytest.approx(10 / 30, abs=1e-3)


# ------------------------------------------------------------------------------------------------ end to end (SYNTHETIC archive)
def _write_station(path, sid, start, hours, rain_from=None, temp=60.0, alti=30.00, step=0.0, gap=None, shift_at=None):
    """SYNTHETIC hourly archive rows. gap=(a, b): no report in [a, b). shift_at: from then on wind 300 deg and 8 F colder (a front)."""
    rows = [HEADER]
    for h in range(hours):
        t = start + timedelta(hours=h)
        if gap and gap[0] <= t < gap[1]:
            continue
        wet = rain_from is not None and t >= rain_from
        shifted = shift_at is not None and t >= shift_at
        rows.append(",".join([W.iem_id(sid), t.strftime("%Y-%m-%d %H:%M"), f"{temp - (8 if shifted else 0):.2f}", "50.00", "70.0",
                              "300.00" if shifted else "180.00", "8.00",
                              f"{alti - step * h:.2f}", "1016.00", "0.0500" if wet else "0.0000", "OVC", "null", "null", "null",
                              "-RA" if wet else "null"]))
    with open(os.path.join(path, f"{sid}.csv"), "w") as fh:
        fh.write("\n".join(rows))


def test_grade_end_to_end_on_synthetic_archive(tmp_path):
    p, _ = W.load_protocol()
    p = copy.deepcopy(p)
    for k in ("changeSignal_5_3", "representativeness_5_2", "fidelity_5_1"):
        p["windows"][k].update({"from": "2026-11-10T00:00:00Z", "to": "2026-11-11T00:00:00Z"})
    st = W.decode_stations(rec("guntersville-stations.json")) + [{"id": "KSYN1", "name": "SYNTHETIC", "lat": 34.50, "lon": -86.26}]
    sel = W.select_stations(LAKE, st)
    ind = sel["candidates"][0]["id"]
    doc = {"subset": True, "lakes": [dict(LAKE, status="OK", **sel), {"id": "Nowhere|XX", "lat": 0, "lon": 0, "status": "BLOCKED"}]}
    win = tmp_path / "asos" / "window"
    win.mkdir(parents=True)
    start = datetime(2026, 11, 9, 10, 53, tzinfo=UTC)
    rain = datetime(2026, 11, 10, 12, 53, tzinfo=UTC)
    for s in ("K8A1", "KBFZ", "K4A6"):
        _write_station(win, s, start, 42, rain_from=rain if s == "K8A1" else None)
    _write_station(win, ind, start, 42, rain_from=rain + timedelta(hours=1), temp=62.0, alti=30.02)
    r = W.grade(p, doc, str(tmp_path / "asos"), None, None)

    assert r["lakes"]["excluded"]["BLOCKED"] == 1 and r["lakes"]["gradedFor5_2and5_3"] == 1
    assert r["R-5.1R"]["matchShare"] == 1.0 and r["R-5.1R"]["provenanceShare"] == 1.0 and r["R-5.1R"]["values"] > 0
    assert r["R-5.1R"]["computedResult"] == "INSUFFICIENT"                                      # 1 lake < 20
    assert "NOT the plan's 5.1" in r["R-5.1R"]["label"]
    assert r["lakes"]["independentStations"][0]["distanceToBrainStationMi"] >= 3.0
    pm = r["R-5.2"]["pressureMAE_hPa"]
    assert pm["value"] == pytest.approx(0.02 / 0.0295299830714, abs=0.01) and pm["pairs"] > 0
    assert r["R-5.2"]["airTempMAE_F"]["value"] == pytest.approx(2.0)
    assert r["R-5.2"]["trend3hAgreement"]["value"] == 1.0                                     # both steady
    ro = r["R-5.3"]["RAIN_ONSET"]
    assert ro["brainEvents"] == 1 and ro["hits"] == 1 and ro["truthEvents"] == 1 and ro["detected"] == 1
    assert ro["result"] == "INSUFFICIENT"
    assert r["R-5.3"]["FRONT_PASSAGE"]["result"] == "NOT_GRADED"
    assert "SUBSET" in r["qualifiers"] and "SUBSTITUTION_UNCERTAIN" in r["qualifiers"]
    assert all(r[k]["result"] != "PASS" for k in ("R-5.1R", "R-5.2", "R-5.3"))
    assert set(r["labels"]) >= {"INTERNAL_EXPERIMENTAL", "NOT_FOR_CUSTOMERS"}


def test_a_false_alarm_and_a_miss_are_counted():
    g = W.grade_pod_far(det=24, n_truth=30, hits=21, n_brain=30, lakes=10, pod_min=0.8, far_max=0.3)
    assert g["POD"] == 0.8 and g["FAR"] == 0.3 and g["result"] == "PASS"
    g = W.grade_pod_far(det=23, n_truth=30, hits=21, n_brain=30, lakes=10, pod_min=0.8, far_max=0.3)
    assert g["result"] == "FAIL"
    assert W.grade_pod_far(30, 30, 30, 30, 9, 0.8, 0.3)["result"] == "INSUFFICIENT"


def test_rain_truth_onset_needs_a_measured_dry_lookback():
    base = datetime(2026, 11, 10, 0, 53, tzinfo=UTC)
    s = W.Series([W.Obs("KX", base, precip_1h_in=None), W.Obs("KX", base + timedelta(hours=1), precip_1h_in=0.02)])
    assert W.rain_onsets(s, base, base + timedelta(hours=3), 0.01) == []                       # no measured dry report before
    s = W.Series([W.Obs("KX", base, precip_1h_in=0.0), W.Obs("KX", base + timedelta(hours=1), precip_1h_in=0.02),
                  W.Obs("KX", base + timedelta(hours=2), precip_1h_in=0.05)])
    assert W.rain_onsets(s, base, base + timedelta(hours=3), 0.01) == [base + timedelta(hours=1)]


def test_grade_cli_writes_only_the_report(tmp_path):
    (tmp_path / "asos" / "window").mkdir(parents=True)
    stations = tmp_path / "stations.json"
    stations.write_text(json.dumps({"subset": True, "lakes": []}))
    before = set(os.listdir(tmp_path))
    out = tmp_path / "report.json"
    assert W.main(["grade", "--stations", str(stations), "--asos", str(tmp_path / "asos"), "--out", str(out)]) == 0
    assert set(os.listdir(tmp_path)) - before == {"report.json"}
    rep = json.loads(out.read_text())
    assert rep["protocolSha256"] == open(W.PROTOCOL + ".sha256").read().split()[0]
    assert rep["thresholdsVersion"] == "weather-change-thresholds-v1"


def _setup(tmp_path, frm, to, lake=LAKE):
    p, _ = W.load_protocol()
    p = copy.deepcopy(p)
    for k in ("changeSignal_5_3", "representativeness_5_2", "fidelity_5_1"):
        p["windows"][k].update({"from": frm, "to": to})
    st = W.decode_stations(rec("guntersville-stations.json")) + [{"id": "KSYN1", "name": "SYNTHETIC", "lat": 34.50, "lon": -86.26}]
    sel = W.select_stations(lake, st)
    win = tmp_path / "asos" / "window"
    win.mkdir(parents=True)
    return p, {"subset": True, "lakes": [dict(lake, status="OK", **sel)]}, win, sel["candidates"][0]["id"]


def test_pod_is_graded_on_all_truth_and_a_miss_without_brain_data_counts(tmp_path):
    p, doc, win, ind = _setup(tmp_path, "2026-11-10T00:00:00Z", "2026-11-11T00:00:00Z")
    start = datetime(2026, 11, 9, 10, 53, tzinfo=UTC)
    r1 = datetime(2026, 11, 10, 6, 53, tzinfo=UTC)
    gap = (datetime(2026, 11, 10, 3, 0, tzinfo=UTC), datetime(2026, 11, 10, 10, 0, tzinfo=UTC))  # the Brain's stations are silent
    rows = [HEADER]
    for h in range(42):
        t = start + timedelta(hours=h)
        wet = r1 <= t < r1 + timedelta(hours=2) or t >= datetime(2026, 11, 10, 15, 53, tzinfo=UTC)
        rows.append(",".join([W.iem_id(ind), t.strftime("%Y-%m-%d %H:%M"), "60.00", "50.00", "70.0", "180.00", "8.00", "30.00",
                              "1016.00", "0.0500" if wet else "0.0000", "OVC", "null", "null", "null", "-RA" if wet else "null"]))
    (win / f"{ind}.csv").write_text("\n".join(rows))
    for s_ in ("K8A1", "KBFZ", "K4A6"):
        _write_station(win, s_, start, 42, rain_from=datetime(2026, 11, 10, 15, 53, tzinfo=UTC) if s_ == "K8A1" else None, gap=gap)
    ro = W.grade(p, doc, str(tmp_path / "asos"))["R-5.3"]["RAIN_ONSET"]
    assert ro["truthEvents"] == 2 and ro["detected"] == 1 and ro["POD"] == 0.5               # the silent-data onset is a MISS
    sec = ro["secondaryEvaluableOnly"]
    assert sec["truthEvents"] == 1 and sec["POD"] == 1.0 and sec["label"].startswith("SECONDARY")
    assert any("3 h dry lookback" in a for a in ro["amendmentAdditions"])


def test_disclosed_fixture_span_is_not_graded(tmp_path):
    p, doc, win, ind = _setup(tmp_path, "2026-11-06T00:00:00Z", "2026-11-07T02:00:00Z")
    start = datetime(2026, 11, 5, 10, 53, tzinfo=UTC)
    for s_ in ("K8A1", "KBFZ", "K4A6", ind):
        _write_station(win, s_, start, 42)
    r = W.grade(p, doc, str(tmp_path / "asos"))
    ex = r["lakes"]["excludedSpans"]
    assert ex["instants"] == 17                                   # 07:10Z .. 23:10Z for Guntersville
    assert ex["values"] > 0                                       # 00:10Z on 11-07 would publish the 23:53Z report: excluded
    other = W.grade(p, {"subset": True, "lakes": [dict(doc["lakes"][0], id="Elsewhere|AL")]}, str(tmp_path / "asos"))
    assert other["lakes"]["excludedSpans"]["instants"] == 0


def test_front_hits_and_unjudgeable_brain_fronts_are_kept_out_of_far(tmp_path):
    p, doc, win, ind = _setup(tmp_path, "2026-11-10T00:00:00Z", "2026-11-11T00:00:00Z")
    start = datetime(2026, 11, 9, 10, 53, tzinfo=UTC)
    shift = datetime(2026, 11, 10, 14, 53, tzinfo=UTC)
    for s_ in ("K8A1", "KBFZ", "K4A6", ind):
        _write_station(win, s_, start, 42, shift_at=shift)
    near = "\n".join(["000", "ASUS01 KWBC 101600", "CODSUS", "VALID 111015Z", "COLD 3500863 3400863", ""])     # through the lake at 15Z
    far = "\n".join(["000", "ASUS01 KWBC 102200", "CODSUS", "VALID 111021Z", "COLD 4500900 4400900", ""])      # 45N, 6 h later
    a = W.grade(p, doc, str(tmp_path / "asos"), None, near)["R-5.3"]["FRONT_PASSAGE"]
    assert a["brainEvents"] == 1 and a["hits"] == 1 and a["truthEvents"] == 1 and a["detected"] == 1
    b = W.grade(p, doc, str(tmp_path / "asos"), None, far)["R-5.3"]["FRONT_PASSAGE"]
    assert b["unjudgeableBrainEventsExcludedFromFAR"] == 1 and b["brainEvents"] == 0 and b["truthEvents"] == 0
