"""Offline tests for the Weather retrospective validation runner (protocol WX-RETRO-2026-11-23.4; .3, .2 and v1 superseded). No network: every input is a fixture.
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
    assert p["protocolId"] == "WX-RETRO-2026-11-23.4"
    assert "BOUND before any comparison" in p["designRule"] and "every exclusion counts against the Brain" in p["designRule"]
    assert d == open(W.PROTOCOL + ".sha256").read().split()[0]
    assert p["status"] == "PRE-REGISTERED" and "RETROSPECTIVE" in p["labels"]


def test_superseded_protocols_are_kept_unchanged_and_refused():
    d = os.path.dirname(W.PROTOCOL)
    for name, digest in (("WX-RETRO-2026-11-23.protocol.json", "6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8"),
                         ("WX-RETRO-2026-11-23.2.protocol.json", "01eac7bc56033154dcf64ee365826a0da1c4d33cd921cec7ec76e79df48eb58c"),
                         ("WX-RETRO-2026-11-23.3.protocol.json", "492c1befe2707ce559c5999da7931548e69728c9fffadf16524813efdb5ec7c7")):
        path = os.path.join(d, name)
        assert W.sha256_file(path) == digest == open(path + ".sha256").read().split()[0]   # byte-identical
        with pytest.raises(SystemExit, match="SUPERSEDED"):
            W.load_protocol(path)
    p, _ = W.load_protocol()
    assert {x["sha256"] for x in p["supersedes"]} == W.SUPERSEDED_SHA256


def test_a_protocol_with_another_id_or_superseded_status_is_refused(tmp_path):
    p = json.load(open(W.PROTOCOL))
    for change, msg in (({"protocolId": "WX-RETRO-2026-11-23.5"}, "is not"), ({"status": "SUPERSEDED"}, "SUPERSEDED")):
        f = tmp_path / f"p{len(msg)}.json"
        f.write_text(json.dumps(p | change))
        (tmp_path / (f.name + ".sha256")).write_text(W.sha256_file(str(f)) + "  x\n")
        with pytest.raises(SystemExit, match=msg):
            W.load_protocol(str(f))


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
    assert "COUNTS AS A DISAGREEMENT" in c["R-5.2"]["metrics"]["trend3hAgreement"] and "unknown counts against" in p["unknownsRule"]
    g = p["substitutionCheck"]["gating"]
    assert "seaLevelPressure" in g["R-5.2"] and "seaLevelPressure" in g["R-5.3.FRONT_PASSAGE"]
    assert {"wetPrecipitation", "wetPresentWeatherPresence"} <= set(g["R-5.3.RAIN_ONSET"])
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
    p, _ = W.load_protocol()
    assert os.environ.get("SECTOR_WEATHER_USER_AGENT") or W.USER_AGENT in p["execution"]["userAgent"]        # runner and protocol agree


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


# ------------------------------------------------------------------------------------------------ run folders (what the fetch steps write)
def _rows(sid, start, hours, rain_from=None, temp=60.0, alti=30.00, gap=None, shift_at=None, wet_at=None):
    """SYNTHETIC hourly archive rows. gap=(a, b): no report in [a, b). shift_at: from then on wind 300 deg and 8 F colder (a front).
    wet_at: a predicate on the report time that makes it rain."""
    rows = [HEADER]
    for h in range(hours):
        t = start + timedelta(hours=h)
        if gap and gap[0] <= t < gap[1]:
            continue
        wet = (rain_from is not None and t >= rain_from) or (wet_at is not None and wet_at(t))
        shifted = shift_at is not None and t >= shift_at
        rows.append(",".join([W.iem_id(sid), t.strftime("%Y-%m-%d %H:%M"), f"{temp - (8 if shifted else 0):.2f}", "50.00", "70.0",
                              "300.00" if shifted else "180.00", "8.00", f"{alti:.2f}", "1016.00", "0.0500" if wet else "0.0000",
                              "OVC", "null", "null", "null", "-RA" if wet else "null"]))
    return "\n".join(rows)


class Run:
    """Builds a run folder exactly as the fetch steps do (stage folders, provenance records with sha256 and fetchedAt)."""

    def __init__(self, tmp_path, frm="2026-11-10T00:00:00Z", to="2026-11-11T00:00:00Z", lake=LAKE, real_protocol=False):
        p, self.sha = W.load_protocol()
        self.p = copy.deepcopy(p)
        if not real_protocol:
            for k in ("changeSignal_5_3", "representativeness_5_2", "fidelity_5_1"):
                self.p["windows"][k].update({"from": frm, "to": to})
        st = W.decode_stations(rec("guntersville-stations.json")) + [{"id": "KSYN1", "name": "SYNTHETIC", "lat": 34.50, "lon": -86.26}]
        sel = W.select_stations(lake, st)
        self.ind = sel["candidates"][0]["id"]
        self.lakes = [dict(lake, status="OK", **sel)]
        self.brain = [s["id"] for s in sel["brainStations"]]
        self.directory_count = None
        self.window, self.iem, self.nws, self.errors, self.minutes_apart = {}, {}, {}, {}, 1
        self.codsus = ""
        self.run = str(tmp_path / "run")

    def stations(self):
        return sorted(set(self.brain) | {c["id"] for l in self.lakes if l["status"] == "OK" for c in l["candidates"]})

    def build(self):
        r = self.run
        count = self.directory_count if self.directory_count is not None else len(self.lakes)
        doc = {"directory": {"count": count, "sha256": "x"}, "subset": False, "lakes": self.lakes}
        t0 = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)

        def put(stage, rel, data, rec_, items):
            path = os.path.join(r, stage, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").write(data)
            items.append(dict(rec_, file=rel, sha256=W.sha256_file(path)))

        def prov(stage, items):
            os.makedirs(os.path.join(r, stage), exist_ok=True)
            json.dump({"items": items}, open(os.path.join(r, stage, "provenance.json"), "w"))

        it = []
        put("stations", "stations.json", json.dumps(doc), {"fetchedAt": t0.isoformat()}, it)
        prov("stations", it)
        it = []
        for s_ in self.stations():
            if ("window", s_) in self.errors:
                it.append({"station": s_, "kind": "window", "file": f"window/{s_}.csv", "error": "HTTP 500", "fetchedAt": t0.isoformat()})
            else:
                put("asos", f"window/{s_}.csv", self.window.get(s_, HEADER), {"station": s_, "kind": "window", "fetchedAt": t0.isoformat()}, it)
        prov("asos", it)
        it = []
        for s_ in self.stations():
            for kind, rel, data, dt in (("iem", f"iem/{s_}.csv", self.iem.get(s_, HEADER), 0),
                                        ("nws", f"nws/{s_}.json", json.dumps(self.nws.get(s_, {"features": []})), self.minutes_apart)):
                at = (t0 + timedelta(minutes=dt)).strftime("%Y-%m-%dT%H:%M:%SZ")
                if (kind, s_) in self.errors:
                    it.append({"station": s_, "kind": kind, "file": rel, "error": "HTTP 500 after 4 attempts", "fetchedAt": at})
                else:
                    put("recent", rel, data, {"station": s_, "kind": kind, "fetchedAt": at}, it)
        prov("recent", it)
        it = []
        put("fronts", "codsus.txt", self.codsus, {"kind": "fronts", "fetchedAt": t0.isoformat()}, it)
        prov("fronts", it)
        return self

    def bind(self):
        return W.bind(self.p, self.sha, self.run)

    def grade(self, run_number=1):
        return W.grade(self.p, self.bind(), self.run, run_number)


START = datetime(2026, 11, 9, 10, 53, tzinfo=UTC)


def _iem_copy_of(nws, sid):
    rows = [HEADER]
    f = lambda v, nd=2: "null" if v is None else f"{v:.{nd}f}"  # noqa: E731
    for o in nws:
        alti = None if o.alt_hpa is None else round(o.alt_hpa * 0.0295299830714, 2)
        rows.append(",".join([W.iem_id(sid), o.at.strftime("%Y-%m-%d %H:%M"), f(o.temp_f), f(o.dew_f), f(o.rh), "null", "null",
                              f(alti), f(o.slp_hpa), f(o.precip_1h_in, 4), "null", "null", "null", "null", "null"]))
    return "\n".join(rows)


# ------------------------------------------------------------------------------------------------ substitution check
def test_substitution_check_agrees_when_the_archive_carries_the_same_reports(tmp_path):
    doc = rec("guntersville-obs-KBFZ.json")
    nws = W.decode_observations(doc)
    assert nws
    R = Run(tmp_path)
    R.nws["KBFZ"], R.iem["KBFZ"] = doc, _iem_copy_of(nws, "KBFZ")
    m_ = R.build().bind()
    r = W.substitution_check(["KBFZ"], os.path.join(R.run, "recent"), m_)
    m = r["metrics"]
    assert r["coverage"]["share"] == 1.0 and m["temperature"]["value"]["agreement"] == 1.0
    assert m["pressure"]["value"]["pairs"] == 0 or m["pressure"]["value"]["agreement"] == 1.0
    assert set(m) >= {"temperature", "dewPoint", "pressure", "seaLevelPressure", "windSpeed", "windDirection", "precipitation",
                      "presentWeatherPresence", "wetPrecipitation", "wetPresentWeatherPresence"}
    assert "null" in m["seaLevelPressure"] and "null" not in m["wetPrecipitation"]
    assert m["wetPrecipitation"]["value"]["marks"] == {"agreement>=": 0.95, "minPairs": 200}
    assert m["windSpeed"]["null"]["agreement"] < 1.0                                         # wind left null in the archive copy: measured
    assert m["temperature"]["value"]["result"] == "INSUFFICIENT"                             # < 1000 pairs
    g = W.gates(r)
    assert not g["R-5.2"]["ok"] and "temperature" in g["R-5.2"]["notPassing"]
    assert m_["stationStatus"]["KBFZ"]["flag"] is None


def test_gates_need_value_and_null_agreement_and_coverage():
    ok = {"value": {"result": "PASS"}, "null": {"result": "PASS"}}
    sub = {"coverage": {"result": "PASS"}, "metrics": {k: dict(ok) for k in W.SUB_FIELDS} | {
        k: {"value": {"result": "PASS"}} for k in ("presentWeatherPresence", *W.WET_METRICS)}}
    assert all(v["ok"] for v in W.gates(sub).values())
    sub["metrics"]["windDirection"] = {"value": {"result": "PASS"}, "null": {"result": "FAIL"}}
    g = W.gates(sub)
    assert not g["R-5.3.FRONT_PASSAGE"]["ok"] and g["R-5.3.RAIN_ONSET"]["ok"] and g["R-5.2"]["ok"]
    sub["metrics"]["windDirection"] = dict(ok)
    sub["metrics"]["seaLevelPressure"] = {"value": {"result": "FAIL"}, "null": {"result": "PASS"}}
    g = W.gates(sub)
    assert not g["R-5.2"]["ok"] and not g["R-5.3.FRONT_PASSAGE"]["ok"] and g["R-5.3.RAIN_ONSET"]["ok"]
    sub["metrics"]["seaLevelPressure"] = dict(ok)
    sub["metrics"]["wetPrecipitation"] = {"value": {"result": "INSUFFICIENT"}}
    g = W.gates(sub)
    assert not g["R-5.3.RAIN_ONSET"]["ok"] and g["R-5.2"]["ok"]
    sub["coverage"]["result"] = "FAIL"
    assert not any(v["ok"] for v in W.gates(sub).values())


# ------------------------------------------------------------------------------------------------ bind: decided before any comparison
def test_bind_records_failures_and_flags_from_provenance_and_timestamps_only(tmp_path):
    R = Run(tmp_path)
    base = datetime(2026, 11, 20, 0, 53, tzinfo=UTC)
    R.nws["K4A6"] = {"features": [{"properties": {"station": "https://api.weather.gov/stations/K4A6", "timestamp": (base + timedelta(hours=h)).isoformat(),
                                                   "temperature": {"unitCode": "wmoUnit:degC", "value": 10.0}}} for h in range(30)]}
    R.iem["K4A6"] = "\n".join([HEADER] + [f"4A6,{(base + timedelta(hours=h)).strftime('%Y-%m-%d %H:%M')},50.00" + ",null" * 12
                                          for h in range(10)])
    R.errors = {("nws", "KBFZ"): 1}
    m = R.build().bind()
    st = m["stationStatus"]
    assert st["KBFZ"]["flag"] == "FETCH_FAILED" and st["KBFZ"]["recentNws"] == "FETCH_FAILED"
    assert st["K4A6"]["flag"] == "COVERAGE_FLOOR" and st["K4A6"]["recentCoverage"] == pytest.approx(10 / 30, abs=1e-3)
    lake = m["lakes"][0]
    assert lake["excluded"] == "SUBSTITUTION_FETCH_FAILED" and not any(lake["criteria"].values())
    assert m["exclusions"]["R-5.2"] == {"SUBSTITUTION_FETCH_FAILED": 1} and m["population"]["R-5.1R"] == 0


def test_a_missing_fetch_time_or_missing_file_is_fetch_failed(tmp_path):
    R = Run(tmp_path).build()
    prov = json.load(open(os.path.join(R.run, "asos", "provenance.json")))
    for it in prov["items"]:
        if it.get("station") == "K8A1":
            del it["fetchedAt"]
    json.dump(prov, open(os.path.join(R.run, "asos", "provenance.json"), "w"))
    os.remove(os.path.join(R.run, "recent", "iem", "K4A6.csv"))
    prov = json.load(open(os.path.join(R.run, "recent", "provenance.json")))
    prov["items"] = [x for x in prov["items"] if not (x.get("station") == "K4A6" and x.get("kind") == "iem")]
    json.dump(prov, open(os.path.join(R.run, "recent", "provenance.json"), "w"))
    st = R.bind()["stationStatus"]
    assert st["K8A1"]["window"] == "FETCH_FAILED" and st["K4A6"]["recentIem"] == "FETCH_FAILED"


def test_bind_refuses_a_hash_mismatch_or_an_unrecorded_file(tmp_path):
    R = Run(tmp_path).build()
    with open(os.path.join(R.run, "asos", "window", "KBFZ.csv"), "a") as fh:
        fh.write("\nBFZ,2026-11-10 00:53,99.00" + ",null" * 12)
    with pytest.raises(SystemExit, match="sha256 differs"):
        R.bind()
    R2 = Run(tmp_path / "b").build()
    open(os.path.join(R2.run, "asos", "window", "KEXTRA.csv"), "w").write(HEADER)
    with pytest.raises(SystemExit, match="no provenance record"):
        R2.bind()


def test_independent_fallback_follows_the_bound_rule(tmp_path):
    R = Run(tmp_path)
    st = W.decode_stations(rec("guntersville-stations.json")) + [{"id": "KSYN1", "name": "SYNTHETIC", "lat": 34.50, "lon": -86.26},
                                                                  {"id": "KSYN2", "name": "SYNTHETIC", "lat": 34.60, "lon": -86.26}]
    R.lakes = [dict(LAKE, status="OK", **W.select_stations(LAKE, st))]
    for s_ in R.brain + ["KSYN2"]:
        R.window[s_] = _rows(s_, START, 42)
    R.errors = {("nws", "KSYN1"): 1}
    lake = R.build().bind()["lakes"][0]
    assert lake["independent"]["id"] == "KSYN2"
    assert lake["skippedCandidates"] == [{"id": "KSYN1", "reason": "FETCH_FAILED"}]


def test_contemporaneity_is_bound_and_blocks_every_pass(tmp_path):
    R = Run(tmp_path)
    R.minutes_apart = 61
    m = R.build().bind()
    assert m["substitution"]["status"] == "NOT_GRADED" and m["substitution"]["reason"].startswith("FETCH_NOT_CONTEMPORANEOUS")
    r = W.grade(R.p, m, R.run)
    assert r["R-SUB"]["result"] == "NOT_GRADED" and "SUBSTITUTION_UNCERTAIN" in r["qualifiers"]


def test_fetch_steps_take_stations_only_from_the_recorded_stations_json(tmp_path):
    R = Run(tmp_path).build()
    f = os.path.join(R.run, "stations", "stations.json")
    open(f, "a").write(" ")
    with pytest.raises(SystemExit, match="stations.json sha256"):
        W.load_stations(R.run)
    with pytest.raises(SystemExit, match="exists"):
        W._new_stage(R.run, "asos")                                                          # write-once stage folders


# ------------------------------------------------------------------------------------------------ grade: exact disk match, run log, write-once
def _cli_run(tmp_path, name="run"):
    """A real-protocol run folder with one BLOCKED lake (nothing to grade), for the CLI gates."""
    R = Run(tmp_path / name, real_protocol=True)
    R.lakes = [{"id": "Nowhere|XX", "lat": 0, "lon": 0, "status": "BLOCKED"}]
    R.brain = []
    R.build()
    assert W.main(["bind", "--run", R.run]) == 0
    return R


def test_grade_refuses_when_disk_differs_from_the_manifest(tmp_path):
    R = _cli_run(tmp_path)
    open(os.path.join(R.run, "fronts", "codsus.txt"), "a").write("VALID 111015Z\n")
    with pytest.raises(SystemExit, match="differ from run-manifest"):
        W.main(["grade", "--run", R.run, "--run-log", str(tmp_path / "RUNS.jsonl")])
    with pytest.raises(SystemExit, match="write-once"):
        W.main(["bind", "--run", R.run])


def test_run_log_only_run_one_counts_and_reports_are_write_once(tmp_path):
    log = str(tmp_path / "RUNS.jsonl")
    R1 = _cli_run(tmp_path, "r1")
    assert W.main(["grade", "--run", R1.run, "--run-log", log]) == 0
    rep1 = json.load(open(os.path.join(R1.run, "report.json")))
    assert rep1["runNumber"] == 1 and rep1["priorRuns"] == 0 and "REPEAT_RUN" not in rep1["qualifiers"]
    with pytest.raises(SystemExit, match="write-once"):
        W.main(["grade", "--run", R1.run, "--run-log", log])
    R2 = _cli_run(tmp_path, "r2")
    assert W.main(["grade", "--run", R2.run, "--run-log", log]) == 0
    rep2 = json.load(open(os.path.join(R2.run, "report.json")))
    assert rep2["runNumber"] == 2 and "REPEAT_RUN" in rep2["qualifiers"] and rep2["counts"] is False
    assert all(rep2[k]["result"] in ("NOT_GRADED", "INSUFFICIENT") for k in ("R-5.1R", "R-5.2"))
    events = [json.loads(x)["event"] for x in open(log)]
    assert events == ["START", "RESULT", "START", "RESULT"]
    assert rep1["protocolSha256"] == open(W.PROTOCOL + ".sha256").read().split()[0]


def test_excluded_lakes_count_against_the_brain_through_coverage(tmp_path):
    R = Run(tmp_path)
    R.window = {s_: _rows(s_, START, 42) for s_ in R.brain + [R.ind]}
    R.directory_count = 2                                                                    # half the directory is bound
    R.lakes.append({"id": "Nowhere|XX", "lat": 0, "lon": 0, "status": "BLOCKED"})
    r = R.build().grade()
    cov = r["R-5.2"]["coverage"]
    assert cov["share"] == 0.5 and cov["excludedByReason"] == {"BLOCKED": 1}
    assert r["R-5.2"]["metricsResult"] == "INSUFFICIENT" and r["R-5.2"]["computedResult"] == "FAIL"
    assert r["R-5.2"]["reason"] == "COVERAGE_BELOW_MINIMUM"


def test_a_short_stations_file_is_subset_and_cannot_pass_or_fail(tmp_path):
    R = Run(tmp_path)
    R.directory_count = 621
    m = R.build().bind()
    assert m["subset"] is True
    r = W.grade(R.p, m, R.run)
    assert "SUBSET" in r["qualifiers"] and all(r[k]["result"] not in ("PASS", "FAIL") for k in ("R-5.1R", "R-5.2"))


# ------------------------------------------------------------------------------------------------ end to end (SYNTHETIC archive)
def test_grade_end_to_end_on_synthetic_archive(tmp_path):
    R = Run(tmp_path)
    rain = datetime(2026, 11, 10, 12, 53, tzinfo=UTC)
    for s_ in R.brain:
        R.window[s_] = _rows(s_, START, 42, rain_from=rain if s_ == "K8A1" else None)
    R.window[R.ind] = _rows(R.ind, START, 42, rain_from=rain + timedelta(hours=1), temp=62.0, alti=30.02)
    R.lakes.append({"id": "Nowhere|XX", "lat": 0, "lon": 0, "status": "BLOCKED"})
    r = R.build().grade()
    assert r["lakes"]["exclusions"]["R-5.2"] == {"BLOCKED": 1} and r["lakes"]["population"]["R-5.2"] == 1
    assert r["R-5.1R"]["matchShare"] == 1.0 and r["R-5.1R"]["provenanceShare"] == 1.0 and r["R-5.1R"]["values"] > 0
    assert r["R-5.1R"]["metricsResult"] == "INSUFFICIENT"                                      # 1 lake < 20
    assert "NOT the plan's 5.1" in r["R-5.1R"]["label"]
    assert r["lakes"]["independentStations"][0]["distanceToBrainStationMi"] >= 3.0
    pm = r["R-5.2"]["pressureMAE_hPa"]
    assert pm["value"] == pytest.approx(0.02 / 0.0295299830714, abs=0.01) and pm["pairs"] > 0
    assert r["R-5.2"]["airTempMAE_F"]["value"] == pytest.approx(2.0)
    assert r["R-5.2"]["trend3hAgreement"]["value"] == 1.0                                     # both steady
    ro = r["R-5.3"]["RAIN_ONSET"]
    assert ro["brainEvents"] == 1 and ro["hits"] == 1 and ro["truthEvents"] == 1 and ro["detected"] == 1
    assert r["R-5.3"]["FRONT_PASSAGE"]["result"] == "NOT_GRADED"                               # no eligible bulletin bound
    assert "SUBSTITUTION_UNCERTAIN" in r["qualifiers"]
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


def test_pod_is_graded_on_all_truth_and_a_miss_without_brain_data_counts(tmp_path):
    R = Run(tmp_path)
    r1, later = datetime(2026, 11, 10, 6, 53, tzinfo=UTC), datetime(2026, 11, 10, 15, 53, tzinfo=UTC)
    gap = (datetime(2026, 11, 10, 3, 0, tzinfo=UTC), datetime(2026, 11, 10, 10, 0, tzinfo=UTC))  # the Brain's stations are silent
    R.window[R.ind] = _rows(R.ind, START, 42, wet_at=lambda t: r1 <= t < r1 + timedelta(hours=2) or t >= later)
    for s_ in R.brain:
        R.window[s_] = _rows(s_, START, 42, rain_from=later if s_ == "K8A1" else None, gap=gap)
    ro = R.build().grade()["R-5.3"]["RAIN_ONSET"]
    assert ro["truthEvents"] == 2 and ro["detected"] == 1 and ro["POD"] == 0.5               # the silent-data onset is a MISS
    sec = ro["secondaryEvaluableOnly"]
    assert sec["truthEvents"] == 1 and sec["POD"] == 1.0 and sec["label"].startswith("SECONDARY")
    assert any("3 h dry lookback" in a for a in ro["amendmentAdditions"])


def test_disclosed_fixture_span_is_not_graded_and_its_reports_make_no_hit(tmp_path):
    R = Run(tmp_path, "2026-11-06T00:00:00Z", "2026-11-07T02:00:00Z")
    start = datetime(2026, 11, 5, 10, 53, tzinfo=UTC)
    for s_ in R.brain:
        R.window[s_] = _rows(s_, start, 42)
    R.window[R.ind] = _rows(R.ind, start, 42, wet_at=lambda t: datetime(2026, 11, 6, 10, tzinfo=UTC) <= t < datetime(2026, 11, 6, 12, tzinfo=UTC))
    r = R.build().grade()
    ex = r["lakes"]["excludedSpans"]
    assert ex["instants"] == 17                                   # 07:10Z .. 23:10Z for Guntersville
    assert ex["values"] > 0                                       # 00:10Z on 11-07 would publish the 23:53Z report: excluded
    assert ex["truthReports"] == 2 and ex["truthEvents"] == 1     # wet reports inside the span: no truth onset, no hit


def test_front_hits_and_unjudgeable_brain_fronts_are_kept_out_of_far(tmp_path):
    shift = datetime(2026, 11, 10, 14, 53, tzinfo=UTC)
    near = "\n".join(["000", "ASUS01 KWBC 101600", "CODSUS", "VALID 111015Z", "COLD 3500863 3400863", ""])     # through the lake at 15Z
    far = "\n".join(["000", "ASUS01 KWBC 102200", "CODSUS", "VALID 111021Z", "COLD 4500900 4400900", ""])      # 45N, 6 h later
    out = []
    for name, txt in (("a", near), ("b", far)):
        R = Run(tmp_path / name)
        for s_ in R.brain + [R.ind]:
            R.window[s_] = _rows(s_, START, 42, shift_at=shift)
        R.codsus = txt
        out.append(R.build().grade()["R-5.3"]["FRONT_PASSAGE"])
    a, b = out
    assert a["brainEvents"] == 1 and a["hits"] == 1 and a["truthEvents"] == 1 and a["detected"] == 1
    assert b["unjudgeableBrainEventsExcludedFromFAR"] == 1 and b["brainEvents"] == 0 and b["truthEvents"] == 0


def test_a_null_brain_trend_counts_against_the_brain_and_truth_gaps_are_counted(tmp_path):
    R = Run(tmp_path)
    gap = (datetime(2026, 11, 10, 6, 0, tzinfo=UTC), datetime(2026, 11, 10, 12, 0, tzinfo=UTC))   # the Brain's stations are silent 6 h
    ind_gap = (datetime(2026, 11, 10, 18, 0, tzinfo=UTC), datetime(2026, 11, 10, 21, 0, tzinfo=UTC))
    for s_ in R.brain:
        R.window[s_] = _rows(s_, START, 42, gap=gap)
    R.window[R.ind] = _rows(R.ind, START, 42, gap=ind_gap)
    r52 = R.build().grade()["R-5.2"]
    tr, av, tc, mc = r52["trend3hAgreement"], r52["brainAvailability"], r52["trendCounts"], r52["maeCounts"]
    assert tc["brainTrendNullCountedAsDisagreement"] > 0
    assert tr["value"] == pytest.approx((tr["pairs"] - tc["brainTrendNullCountedAsDisagreement"]) / tr["pairs"], abs=1e-4)
    assert av["pressure"]["instants"] == 24 and av["pressure"]["share"] < 1.0                 # unknowns stay in the denominator
    assert mc["pressureTruthNoReportExcluded"] > 0 and mc["airTempTruthNoReportExcluded"] > 0  # truth gaps counted, not silent


def test_a_front_episode_overlapping_the_fixture_span_is_excluded(tmp_path):
    R = Run(tmp_path, "2026-11-06T00:00:00Z", "2026-11-08T00:00:00Z")
    start = datetime(2026, 11, 5, 10, 53, tzinfo=UTC)
    for s_ in R.brain + [R.ind]:
        R.window[s_] = _rows(s_, start, 66)
    # an episode at 11-07 01Z..04Z: both endpoints are after the span (ends 11-07 00Z), but its +/- 3 h window overlaps it
    R.codsus = "\n".join(["000", "ASUS01 KWBC 070100", "CODSUS", "VALID 110701Z", "COLD 3500863 3400863",
                          "000", "ASUS01 KWBC 070400", "CODSUS", "VALID 110704Z", "COLD 3500863 3400863",
                          "000", "ASUS01 KWBC 071800", "CODSUS", "VALID 110718Z", "COLD 3500863 3400863", ""])
    fp = R.build().grade()["R-5.3"]["FRONT_PASSAGE"]
    assert fp["truthEvents"] == 1                                                              # only the 18Z episode remains
