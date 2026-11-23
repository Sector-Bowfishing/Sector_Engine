"""Offline tests for the Weather retrospective validation runner (protocol WX-RETRO-2026-11-23.5; .4, .3, .2 and v1 superseded). No network: every input is a fixture.
Synthetic archive rows are labelled SYNTHETIC; the NWS responses are the Weather Brain's RECORDED fixtures of 2026-11-06."""
import copy
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    assert p["protocolId"] == "WX-RETRO-2026-11-23.5"
    assert "BOUND before any comparison" in p["designRule"] and "every exclusion counts against the Brain" in p["designRule"]
    assert d == open(W.PROTOCOL + ".sha256").read().split()[0]
    assert p["status"] == "PRE-REGISTERED" and "RETROSPECTIVE" in p["labels"]


def test_superseded_protocols_are_kept_unchanged_and_refused():
    d = os.path.dirname(W.PROTOCOL)
    for name, digest in (("WX-RETRO-2026-11-23.protocol.json", "6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8"),
                         ("WX-RETRO-2026-11-23.2.protocol.json", "01eac7bc56033154dcf64ee365826a0da1c4d33cd921cec7ec76e79df48eb58c"),
                         ("WX-RETRO-2026-11-23.3.protocol.json", "492c1befe2707ce559c5999da7931548e69728c9fffadf16524813efdb5ec7c7"),
                         ("WX-RETRO-2026-11-23.4.protocol.json", "55f850efe9ebd6dc972df59152667b99a5c49dc26cd87263b049c4ea3e9f314d")):
        path = os.path.join(d, name)
        assert W.sha256_file(path) == digest == open(path + ".sha256").read().split()[0]   # byte-identical
        with pytest.raises(SystemExit, match="SUPERSEDED"):
            W.load_protocol(path)
    p, _ = W.load_protocol()
    assert {x["sha256"] for x in p["supersedes"]} == W.SUPERSEDED_SHA256


def test_a_protocol_with_another_id_or_superseded_status_is_refused(tmp_path):
    p = json.load(open(W.PROTOCOL))
    for change, msg in (({"protocolId": "WX-RETRO-2026-11-23.6"}, "is not"), ({"status": "SUPERSEDED"}, "SUPERSEDED")):
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

    def grade(self):
        return W.grade(self.p, self.bind(), self.run)


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


# ------------------------------------------------------------------------------------------------ the shared run ledger (#251), #51 mocked
class Issue:
    """A fake Sector_Ops #51 behind `gh api --paginate` (no network)."""

    def __init__(self):
        self.comments, self.next_id = [], 1000
        self.clock = datetime(2000, 1, 1, tzinfo=UTC)
        self.lag = 0                                                         # the next `lag` listings hide the newest comment

    def post(self, body):
        self.clock += timedelta(minutes=1)
        t = self.clock.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.comments.append({"id": self.next_id, "created_at": t, "updated_at": t, "body": body,
                              "html_url": f"https://example.invalid/51#c{self.next_id}"})
        self.next_id += 1

    def __call__(self, path):
        assert path.endswith("/issues/51/comments?per_page=100"), path
        listed = self.comments
        if self.lag:
            self.lag -= 1
            listed = self.comments[:-1]
        return json.dumps(listed)


@pytest.fixture
def ledgered(tmp_path, monkeypatch):
    """open_ledger -> a Ledger under a scratch research root with a fake #51; the runner's post hook posts on the fake issue."""
    monkeypatch.delenv(W.PRL.ENV_ROOT, raising=False)
    monkeypatch.setattr(W.PRL, "_gh_api", lambda path: (_ for _ in ()).throw(AssertionError("real gh reached")))
    root = tmp_path / "Sector Research" / "weather-brain"
    root.mkdir(parents=True)
    issue = Issue()
    _, sha = W.load_protocol()

    def open_ledger(run):
        return W.PRL.Ledger(root, W.EXPECTED_PROTOCOL_ID, sha, forbid_under=[run], result_steps=W.RESULT_STEPS, gh=issue)

    posted = []

    def hook(kind, text, run):
        posted.append(kind)
        issue.post(text)
    monkeypatch.setattr(W, "open_ledger", open_ledger)
    monkeypatch.setattr(W, "_post_hook", hook)
    monkeypatch.setattr(W, "POLL_S", 0)
    return {"issue": issue, "open": open_ledger, "posted": posted, "root": root}


def _anchor(ledgered, run):
    L = ledgered["open"](run)
    ledgered["issue"].post(L.post_anchor_text())
    return L


def _fetched(ledgered, R):
    """Record the four fetch steps in the ledger for a run folder the Run builder wrote (what the fetch commands do around their work)."""
    L = ledgered["open"](R.run)
    for stage, step in W.FETCH_STEPS.items():
        L.begin(step, W.KEY, args={}, inputs={} if stage == "stations" else {"stations": Path(R.run, "stations")})
        L.complete(step, W.KEY, outputs={stage: Path(R.run, stage)})


def _real_run(tmp_path):
    R = Run(tmp_path, real_protocol=True)
    R.lakes = [{"id": "Nowhere|XX", "lat": 0, "lon": 0, "status": "BLOCKED"}]
    R.brain = []
    return R.build()


def test_the_ledger_declares_grade_as_the_only_result_step():
    p, _ = W.load_protocol()
    assert W.RESULT_STEPS == frozenset({"grade"}) and W.KEY == "directory" and W.LEDGER_BRAIN == "weather"
    assert "bind is NOT result-defining" in p["runLedger"]["resultSteps"] and "'directory'" in p["runLedger"]["stepsAndKeys"]


def test_every_step_refuses_before_the_anchor(tmp_path, ledgered):
    run = str(tmp_path / "run")
    with pytest.raises(W.PRL.LedgerRefusal, match="anchor"):
        W.main(["fetch-stations", "--run", run])                             # refused at begin(), before any network
    assert not os.path.exists(os.path.join(run, "stations"))


def test_bind_and_grade_follow_the_ledger_and_post_start_and_result_once(tmp_path, ledgered):
    R = _real_run(tmp_path)
    _anchor(ledgered, R.run)
    _fetched(ledgered, R)
    assert W.main(["bind", "--run", R.run]) == 0
    assert W.main(["grade", "--run", R.run]) == 0
    assert ledgered["posted"] == ["start", "result"]
    rep = json.load(open(os.path.join(R.run, "report.json")))
    assert rep["protocolId"] == "WX-RETRO-2026-11-23.5" and "counting" in rep
    audit = json.load(open(os.path.join(R.run, "ledger-audit.json")))
    assert audit["result_steps"] == ["grade"] and audit["findings"] == []
    g = [s_ for s_ in audit["steps"] if s_["step"] == "grade"]
    assert len(g) == 1 and g[0]["counted"] is True
    L = ledgered["open"](R.run)
    assert L.first("grade", W.KEY)["counted"] is True
    with pytest.raises(SystemExit, match="write-once"):
        W.main(["grade", "--run", R.run])
    os.remove(os.path.join(R.run, "report.json"))                          # even with the report gone, the ledger refuses a re-run
    for f in ("ledger-audit.json", "ledger-start.txt", "ledger-result.txt"):
        if os.path.exists(os.path.join(R.run, f)):
            os.remove(os.path.join(R.run, f))
    with pytest.raises(W.PRL.LedgerRefusal, match="already ran"):
        W.main(["grade", "--run", R.run])


def test_grade_refuses_inputs_that_changed_after_bind(tmp_path, ledgered):
    R = _real_run(tmp_path)
    _anchor(ledgered, R.run)
    _fetched(ledgered, R)
    W.main(["bind", "--run", R.run])
    open(os.path.join(R.run, "fronts", "codsus.txt"), "a").write("VALID 111015Z\n")
    with pytest.raises(W.PRL.LedgerRefusal, match="changed since it was bound"):
        W.main(["grade", "--run", R.run])
    assert ledgered["posted"] == []                                          # nothing started


def test_bind_refuses_a_stage_that_differs_from_its_completed_fetch(tmp_path, ledgered):
    R = _real_run(tmp_path)
    _anchor(ledgered, R.run)
    _fetched(ledgered, R)
    open(os.path.join(R.run, "asos", "provenance.json"), "a").write(" ")
    with pytest.raises(SystemExit, match="completed with"):
        W.main(["bind", "--run", R.run])


def test_a_fetch_step_runs_once(tmp_path, ledgered):
    R = _real_run(tmp_path)
    _anchor(ledgered, R.run)
    _fetched(ledgered, R)
    os.rename(os.path.join(R.run, "fronts"), os.path.join(R.run, "fronts-old"))
    with pytest.raises(W.PRL.LedgerRefusal, match="already ran"):
        W.main(["fetch-fronts", "--run", R.run])                            # refused at begin(), before any network


def test_not_listed_yet_waits_and_never_reposts(tmp_path, ledgered):
    R = _real_run(tmp_path)
    _anchor(ledgered, R.run)
    _fetched(ledgered, R)
    W.main(["bind", "--run", R.run])
    issue = ledgered["issue"]
    real_post = issue.post

    def lagging_post(body):
        real_post(body)
        issue.lag = 2                                                        # the first two listings miss it
    issue.post = lagging_post
    assert W.main(["grade", "--run", R.run]) == 0
    starts = [c for c in issue.comments if c["body"].startswith("Run start:")]
    assert len(starts) == 1 and ledgered["posted"] == ["start", "result"]


def test_a_second_start_record_is_a_repeat(tmp_path, ledgered, monkeypatch):
    R = _real_run(tmp_path)
    _anchor(ledgered, R.run)
    _fetched(ledgered, R)
    W.main(["bind", "--run", R.run])
    issue = ledgered["issue"]

    def hook(kind, text, run):
        issue.post(f"Run start: {W.EXPECTED_PROTOCOL_ID} grade {W.KEY} {'0' * 64}")  # someone else's start, first
        issue.post(text)
    monkeypatch.setattr(W, "_post_hook", hook)
    with pytest.raises(W.PRL.RepeatDetected):
        W.main(["grade", "--run", R.run])
    assert not os.path.exists(os.path.join(R.run, "report.json"))           # nothing compared


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


def _stations_only(tmp_path, ledgered):
    """A run whose stations stage is complete in the ledger and whose fronts stage does not exist yet."""
    R = _real_run(tmp_path)
    shutil.rmtree(os.path.join(R.run, "fronts"))
    L = _anchor(ledgered, R.run)
    L.begin("fetch-stations", W.KEY, args={}, inputs={})
    L.complete("fetch-stations", W.KEY, outputs={"stations": Path(R.run, "stations")})
    return R


def _good_fronts(run):
    d = W._new_stage(run, "fronts")
    prov = []
    W._save(d, "codsus.txt", b"", prov, "https://mesonet.agron.iastate.edu/x", kind="fronts")
    W._write_prov(d, prov)
    return {"fronts": Path(d)}


def test_an_interrupt_before_the_first_save_aborts_and_the_retry_is_allowed(tmp_path, ledgered, monkeypatch):
    R = _stations_only(tmp_path, ledgered)

    def interrupted(run):
        W._new_stage(run, "fronts")
        raise KeyboardInterrupt("operator")
    monkeypatch.setattr(W, "_fetch_fronts", interrupted)
    with pytest.raises(KeyboardInterrupt):
        W.main(["fetch-fronts", "--run", R.run])
    ents = [e for e in ledgered["open"](R.run).entries() if e["step"] == "fetch-fronts"]
    assert [e["status"] for e in ents] == ["STARTED", "ABORTED_BEFORE_RESULT"]
    assert not os.path.exists(os.path.join(R.run, "fronts"))                 # the empty stage folder is removed
    monkeypatch.setattr(W, "_fetch_fronts", _good_fronts)
    assert W.main(["fetch-fronts", "--run", R.run]) == 0
    ents = [e for e in ledgered["open"](R.run).entries() if e["step"] == "fetch-fronts"]
    assert ents[-1]["status"] == "COMPLETED" and ents[-1]["run"] == 2


def test_an_interrupt_after_one_save_is_terminal_and_the_retry_is_refused(tmp_path, ledgered, monkeypatch, capsys):
    R = _stations_only(tmp_path, ledgered)

    def interrupted(run):
        d = W._new_stage(run, "fronts")
        W._save(d, "codsus.txt", b"VALID 111015Z\n", [], "https://mesonet.agron.iastate.edu/x", kind="fronts")
        raise KeyboardInterrupt("operator")
    monkeypatch.setattr(W, "_fetch_fronts", interrupted)
    with pytest.raises(KeyboardInterrupt):
        W.main(["fetch-fronts", "--run", R.run])
    assert "new protocol id" in capsys.readouterr().err
    ents = [e for e in ledgered["open"](R.run).entries() if e["step"] == "fetch-fronts"]
    assert [e["status"] for e in ents] == ["STARTED"]                        # left open: terminal
    assert os.path.exists(os.path.join(R.run, "fronts", "codsus.txt"))      # nothing deleted
    monkeypatch.setattr(W, "_fetch_fronts", _good_fronts)
    with pytest.raises(SystemExit, match="exists"):
        W.main(["fetch-fronts", "--run", R.run])
    shutil.rmtree(os.path.join(R.run, "fronts"))                             # even with the folder gone, the ledger refuses
    with pytest.raises(W.PRL.LedgerRefusal, match="never completed"):
        W.main(["fetch-fronts", "--run", R.run])


def test_a_saved_file_counts_even_if_the_folder_was_emptied(tmp_path, ledgered, monkeypatch):
    R = _stations_only(tmp_path, ledgered)

    def interrupted(run):
        d = W._new_stage(run, "fronts")
        W._save(d, "codsus.txt", b"x", [], "https://mesonet.agron.iastate.edu/x", kind="fronts")
        os.remove(os.path.join(d, "codsus.txt"))
        raise RuntimeError("boom")
    monkeypatch.setattr(W, "_fetch_fronts", interrupted)
    with pytest.raises(RuntimeError):
        W.main(["fetch-fronts", "--run", R.run])
    ents = [e for e in ledgered["open"](R.run).entries() if e["step"] == "fetch-fronts"]
    assert [e["status"] for e in ents] == ["STARTED"]                        # the in-memory save count decides too


def test_every_file_write_goes_through_the_counted_helper():
    """Any open() for writing, json.dump to a file, write_text/write_bytes, os.replace/rename or shutil copy outside _write_file fails;
    directories may be created only by _write_file and _new_stage."""
    import ast
    tree = ast.parse(open(W.__file__).read())
    bad = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for c in [n for n in ast.walk(fn) if isinstance(n, ast.Call)]:
            f = c.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            owner = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""
            if name == "open":
                mode = c.args[1].value if len(c.args) > 1 and isinstance(c.args[1], ast.Constant) else next(
                    (k.value.value for k in c.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)), "r")
                if not isinstance(mode, str) or any(ch in mode for ch in "wxa+"):
                    if fn.name != "_write_file":
                        bad.append((fn.name, c.lineno, "open"))
            elif (owner, name) in (("json", "dump"), ("os", "replace"), ("os", "rename"), ("shutil", "copy"), ("shutil", "copyfile"),
                                   ("shutil", "move")) or name in ("write_text", "write_bytes"):
                bad.append((fn.name, c.lineno, f"{owner}.{name}"))
            elif (owner, name) in (("os", "makedirs"), ("os", "mkdir")) and fn.name not in ("_write_file", "_new_stage"):
                bad.append((fn.name, c.lineno, f"{owner}.{name}"))
    assert bad == []


def test_remove_empty_tree_removes_directories_only(tmp_path):
    d = tmp_path / "stage"
    (d / "a" / "b").mkdir(parents=True)
    W._remove_empty_tree(str(d))
    assert not d.exists()
    (d / "a").mkdir(parents=True)
    (d / "a" / "f.txt").write_text("x")
    W._remove_empty_tree(str(d))
    assert (d / "a" / "f.txt").exists()                                       # a file anywhere: nothing removed


def test_an_interrupt_after_only_provenance_is_written_is_terminal(tmp_path, ledgered, monkeypatch):
    R = _stations_only(tmp_path, ledgered)

    def interrupted(run):
        d = W._new_stage(run, "fronts")
        W._write_prov(d, [])
        raise KeyboardInterrupt("operator")
    monkeypatch.setattr(W, "_fetch_fronts", interrupted)
    with pytest.raises(KeyboardInterrupt):
        W.main(["fetch-fronts", "--run", R.run])
    ents = [e for e in ledgered["open"](R.run).entries() if e["step"] == "fetch-fronts"]
    assert [e["status"] for e in ents] == ["STARTED"]


def test_an_interrupt_inside_the_writer_after_counting_is_terminal(tmp_path, ledgered, monkeypatch):
    R = _stations_only(tmp_path, ledgered)

    def interrupted(run):
        d = W._new_stage(run, "fronts")
        real = W.os.makedirs
        monkeypatch.setattr(W.os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt("during makedirs")))
        try:
            W._save(d, "x/codsus.txt", b"x", [], "https://mesonet.agron.iastate.edu/x", kind="fronts")
        finally:
            monkeypatch.setattr(W.os, "makedirs", real)
    monkeypatch.setattr(W, "_fetch_fronts", interrupted)
    with pytest.raises(KeyboardInterrupt):
        W.main(["fetch-fronts", "--run", R.run])
    ents = [e for e in ledgered["open"](R.run).entries() if e["step"] == "fetch-fronts"]
    assert [e["status"] for e in ents] == ["STARTED"]                        # counted before any directory or byte


def _fetched_but_not_bound(tmp_path, ledgered):
    R = _real_run(tmp_path)
    _anchor(ledgered, R.run)
    _fetched(ledgered, R)
    return R


def test_a_bind_interrupt_before_the_manifest_aborts_and_bind_may_retry(tmp_path, ledgered, monkeypatch):
    R = _fetched_but_not_bound(tmp_path, ledgered)
    real_bind = W.bind
    monkeypatch.setattr(W, "bind", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt("operator")))
    with pytest.raises(KeyboardInterrupt):
        W.main(["bind", "--run", R.run])
    assert not os.path.exists(os.path.join(R.run, W.MANIFEST))
    ents = [e for e in ledgered["open"](R.run).entries() if e["step"] == "bind"]
    assert [e["status"] for e in ents] == ["STARTED", "ABORTED_BEFORE_RESULT"]
    monkeypatch.setattr(W, "bind", real_bind)
    assert W.main(["bind", "--run", R.run]) == 0
    assert [e for e in ledgered["open"](R.run).entries() if e["step"] == "bind"][-1]["status"] == "COMPLETED"


def test_a_bind_interrupt_after_the_manifest_is_written_is_terminal(tmp_path, ledgered, monkeypatch):
    R = _fetched_but_not_bound(tmp_path, ledgered)
    real_write = W._write_file

    def write_then_interrupt(path, data, exclusive=False):
        real_write(path, data, exclusive)
        if path.endswith(W.MANIFEST):
            raise KeyboardInterrupt("operator")
    monkeypatch.setattr(W, "_write_file", write_then_interrupt)
    with pytest.raises(KeyboardInterrupt):
        W.main(["bind", "--run", R.run])
    assert os.path.exists(os.path.join(R.run, W.MANIFEST))
    ents = [e for e in ledgered["open"](R.run).entries() if e["step"] == "bind"]
    assert [e["status"] for e in ents] == ["STARTED"]
    monkeypatch.setattr(W, "_write_file", real_write)
    os.remove(os.path.join(R.run, W.MANIFEST))
    with pytest.raises(W.PRL.LedgerRefusal, match="never completed"):
        W.main(["bind", "--run", R.run])
