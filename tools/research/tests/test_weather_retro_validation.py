"""Offline tests for the Weather retrospective validation runner (protocol WX-RETRO-2026-11-23). No network: every input is a fixture.
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
    assert p["protocolId"] == "WX-RETRO-2026-11-23"
    assert d == open(W.PROTOCOL + ".sha256").read().split()[0]
    assert p["status"] == "PRE-REGISTERED" and "RETROSPECTIVE" in p["labels"]


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
    assert "0.05 hPa" in " ".join(c["R-5.1"]["checks"]) and "99.5 %" in c["R-5.1"]["pass"]
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
    assert r["coverage"] == 1.0 and r["agreement"]["temperature"] == 1.0
    assert r["pairs"]["pressure"] == 0 or r["agreement"]["pressure"] == 1.0
    assert W.substitution_check(["K8A1"], W.Archive(None), None)["result"] == "NOT_GRADED"


# ------------------------------------------------------------------------------------------------ end to end (SYNTHETIC archive)
def _write_station(path, sid, start, hours, rain_from=None, temp=60.0, alti=30.00, step=0.0):
    rows = [HEADER]
    for h in range(hours):
        t = start + timedelta(hours=h)
        wet = rain_from is not None and t >= rain_from
        rows.append(",".join([W.iem_id(sid), t.strftime("%Y-%m-%d %H:%M"), f"{temp:.2f}", "50.00", "70.0", "180.00", "8.00",
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
    assert r["R-5.1"]["matchShare"] == 1.0 and r["R-5.1"]["provenanceShare"] == 1.0 and r["R-5.1"]["values"] > 0
    assert r["R-5.1"]["computedResult"] == "INSUFFICIENT"                                       # 1 lake < 20
    pm = r["R-5.2"]["pressureMAE_hPa"]
    assert pm["value"] == pytest.approx(0.02 / 0.0295299830714, abs=0.01) and pm["pairs"] > 0
    assert r["R-5.2"]["airTempMAE_F"]["value"] == pytest.approx(2.0)
    assert r["R-5.2"]["trend3hAgreement"]["value"] == 1.0                                     # both steady
    ro = r["R-5.3"]["RAIN_ONSET"]
    assert ro["brainEvents"] == 1 and ro["hits"] == 1 and ro["truthEvents"] == 1 and ro["detected"] == 1
    assert ro["result"] == "INSUFFICIENT"
    assert r["R-5.3"]["FRONT_PASSAGE"]["result"] == "NOT_GRADED"
    assert "SUBSET" in r["qualifiers"] and "SUBSTITUTION_UNCERTAIN" in r["qualifiers"]
    assert all(r[k]["result"] != "PASS" for k in ("R-5.1", "R-5.2", "R-5.3"))
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
