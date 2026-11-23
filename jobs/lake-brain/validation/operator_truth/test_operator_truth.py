"""Offline tests of the operator-truth v1 sample rule and runner, on hand-built fixtures (no network)."""
import datetime as dt
import json
import os
import sys
import urllib.parse
from zoneinfo import ZoneInfo

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_sample as B  # noqa: E402
import run_operator_truth as R  # noqa: E402

UTC = dt.timezone.utc
CHI = ZoneInfo("America/Chicago")


# ---------------------------------------------------------------- sample rule
def rec(live, history=(), operator="US Army Corps of Engineers", lake="L|XX"):
    return {"lakeId": lake, "timeZone": "America/Chicago", "capability": "DIRECT_OPERATOR_POOL", "live": list(live),
            "history": list(history), "dam": {"operatorName": operator}}


def lv(provider, station, series=None, off=None, cad=60, lag=120):
    d = {"provider": provider, "station": station, "cadenceMin": cad, "lagMin": lag}
    if series:
        d["series"] = series
    if off is not None:
        d["datumOffsetFt"] = off
    return d


def test_a2w_and_cwms_same_office_tsid_is_same_series():
    a = B.assign(rec([lv("a2w", "SPA:Abiquiu", "Abiquiu.Elev.Inst.15Minutes.0.DCP-rev"), lv("cwms", "SPA", "Abiquiu.Elev.Inst.15Minutes.0.DCP-rev")]))
    assert a["candidates"][0]["independence"] == "SAME_SERIES" and a["truth"] is None and a["status"] == "EXCLUDED_SAME_SERIES_ONLY"


def test_operator_other_series_preferred_over_nws_and_cross_agency():
    a = B.assign(rec([lv("a2w", "LRP:Kinzua", "K.Elev.Inst.1Hour.0.OBS"), lv("nwps", "KINP1", "HPIRG"), lv("usgs", "03012520", "62615"),
                      lv("cwms", "LRP", "K.Elev.Inst.1Hour.0.RESOPS")]))
    assert a["truth"]["independence"] == "OPERATOR_OTHER_SERIES" and a["truth"]["kind"] == "cwms" and a["status"] == "VERDICT_ELIGIBLE"


def test_same_usgs_site_any_parameter_is_same_series():
    a = B.assign(rec([lv("usgs", "03075871", "00062")], [{"kind": "usgsDaily", "site": "03075871", "param": "62615", "stat": "dv"}],
                     operator="Private"))
    assert a["candidates"][0]["independence"] == "SAME_SERIES" and a["truth"] is None


def test_nws_only_is_report_only_and_same_lid_is_excluded():
    a = B.assign(rec([lv("usgs", "1", "62614"), lv("nwps", "ABCD1", "HPIRG")], operator="State"))
    assert a["status"] == "REPORT_ONLY_ELIGIBLE" and a["truth"]["independence"] == "NWS_REDISTRIBUTION"
    b = B.assign(rec([lv("nwps", "ABCD1", "HPIRG")], [{"kind": "hadsDaily", "lid": "ABCD1", "pe": "HP"}], operator="State"))
    assert b["status"] == "EXCLUDED_SAME_SERIES_ONLY"


def test_uncalibrated_and_subdaily_preferred():
    a = B.assign(rec([lv("nwps", "X1", "HPIRG"), lv("usgs", "9", "62614", off=-1.0)],
                     [{"kind": "usgsDaily", "site": "8", "param": "62614", "stat": "dv"}], operator="State"))
    assert a["truth"]["offsetFt"] == 0.0 and a["truth"]["kind"] == "usgsDaily"      # offset 0 beats sub-daily
    b = B.assign(rec([lv("nwps", "X1", "HPIRG"), lv("usgs", "9", "62614")], [{"kind": "usgsDaily", "site": "8", "param": "62614", "stat": "dv"}],
                     operator="State"))
    assert b["truth"]["kind"] == "usgs"


def test_tva_primary_not_reconstructible():
    a = B.assign(rec([lv("tva", "GVDA1"), lv("cwms", "LRN", "X.Elev.Inst.1Hour.0.raw")], operator="Tennessee Valley Authority"))
    assert a["status"] == "EXCLUDED_BRAIN_VALUE_NOT_RECONSTRUCTIBLE"


def test_allocation_take_all_small_and_proportional_large():
    al = B.allocate({"a": 81, "b": 29, "c": 7, "d": 9, "e": 4})
    assert al == {"c": 7, "d": 9, "e": 4, "a": 29, "b": 11} and sum(al.values()) == 60


def test_frozen_sample_is_the_rule_output_and_preregistered():
    assert R.verify_preregistration() == []
    with open(R.SAMPLE_PATH, encoding="utf-8") as fh:
        assert fh.read() == B.dumps(B.build(B.load_generated(), B.load_accepted()))


def test_verify_detects_a_changed_protocol(tmp_path):
    p = tmp_path / "prereg.md"
    p.write_text("changed")
    assert any("protocol differs" in x for x in R.verify_preregistration(prereg=str(p)))


# ---------------------------------------------------------------- runner pieces
def test_brain_value_latest_within_selection_window_and_rounding():
    m = dt.datetime(2026, 11, 3, 0, 0, tzinfo=CHI)
    obs = [(m - dt.timedelta(hours=2), 600.004), (m - dt.timedelta(minutes=30), 600.126), (m + dt.timedelta(minutes=5), 700.0)]
    assert R.brain_value(obs, m, 120, 60) == (m - dt.timedelta(minutes=30), 600.13)
    assert R.brain_value([(m - dt.timedelta(minutes=301), 1.0)], m, 120, 60) is None     # older than lag + 3 cadence = 300 min


def test_truth_match_tolerances():
    t = dt.datetime(2026, 11, 3, 6, 0, tzinfo=UTC)
    sub = [(t + dt.timedelta(minutes=91), 1.0)]
    assert R.match_truth(sub, t, "SUB_DAILY") is None
    assert R.match_truth(sub, t, "DAILY")[1] == 1.0
    tie = [(t - dt.timedelta(minutes=30), 1.0), (t + dt.timedelta(minutes=30), 2.0)]
    assert R.match_truth(tie, t, "SUB_DAILY")[1] == 1.0


def test_lake_class_thresholds():
    assert R.lake_class(13, 1.0, 0.0) == "INSUFFICIENT"
    assert R.lake_class(14, 0.90, 0.25) == "PASS"
    assert R.lake_class(14, 0.89, 0.0) == "FAIL"
    assert R.lake_class(21, 1.0, 0.26) == "FAIL"


# ---------------------------------------------------------------- fixture transport
def hourly(begin, end, value_fn):
    out, t = [], begin
    while t <= end:
        out.append((t, value_fn(t)))
        t += dt.timedelta(hours=1)
    return out


class FakeGet:
    """Routes GET URLs to hand-built series; records every URL (the runner has no other way to reach the network in tests)."""

    def __init__(self, series):
        self.series, self.urls = series, []

    def __call__(self, url, accept="application/json"):
        self.urls.append(url)
        u = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(u.query)
        if "cwms-data" in u.netloc:
            key = ("cwms", q["office"][0], q["name"][0])
            obs = self.series.get(key)
            if obs is None:
                return 404, b""
            return 200, json.dumps({"units": "ft", "values": [[int(t.timestamp() * 1000), v, 0] for t, v in obs]}).encode()
        if "waterservices" in u.netloc and "/iv/" in u.path:
            obs = self.series.get(("usgs", q["sites"][0], q["parameterCd"][0]), [])
            vals = [{"dateTime": t.isoformat(), "value": str(v)} for t, v in obs]
            return 200, json.dumps({"value": {"timeSeries": [{"values": [{"value": vals}]}]}}).encode()
        if "waterservices" in u.netloc and "/dv/" in u.path:
            obs = self.series.get(("usgsdv", q["sites"][0], q["parameterCd"][0]), [])
            vals = [{"dateTime": d + "T00:00:00.000", "value": str(v)} for d, v in obs]
            return 200, json.dumps({"value": {"timeSeries": [{"variable": {"noDataValue": -999999.0, "options": {"option": [{"optionCode": "00003"}]}},
                                                              "values": [{"value": vals}]}]}}).encode()
        if "api.water.noaa.gov" in u.netloc:
            lid = u.path.split("/")[4]
            obs = self.series.get(("nwps", lid), [])
            return 200, json.dumps({"pedts": "HPIRG", "primaryUnits": "ft",
                                    "data": [{"validTime": R._z(t), "primary": v} for t, v in obs]}).encode()
        if "data.usbr.gov" in u.netloc:
            obs = self.series.get(("rise", q["itemId"][0]), [])
            return 200, json.dumps({"links": {}, "data": [{"attributes": {"dateTime": t.isoformat(), "result": v,
                                                                           "resultAttributes": {"resultType": "observed"}}} for t, v in obs]}).encode()
        raise AssertionError(f"unexpected URL {url}")


def entry(primary, truth, lake="Test Lake|XX", tz="America/Chicago", stratum=None):
    return {"lakeId": lake, "timeZone": tz, "primaryProvider": stratum or primary["kind"], "primary": primary, "truth": truth}


def cwms_ref(kind, office, name, cadence="SUB_DAILY", off=0.0, cls="OPERATOR_OTHER_SERIES"):
    return {"kind": kind, "family": "CWMS", "key": [office, name], "offsetFt": off, "cadence": cadence, "cadenceMin": 60, "lagMin": 120,
            "independence": cls, "boundRole": "FALLBACK_LIVE"}


WIN_B = dt.datetime(2026, 10, 27, tzinfo=UTC)
WIN_E = dt.datetime(2026, 11, 25, tzinfo=UTC)


def test_a2w_primary_is_read_from_cwms_and_agreeing_lake_passes():
    p = cwms_ref("a2w", "LRP", "K.Elev.Inst.1Hour.0.OBS")
    t = cwms_ref("cwms", "LRP", "K.Elev.Inst.1Hour.0.RESOPS")
    get = FakeGet({("cwms", "LRP", "K.Elev.Inst.1Hour.0.OBS"): hourly(WIN_B, WIN_E, lambda x: 1306.52),
                   ("cwms", "LRP", "K.Elev.Inst.1Hour.0.RESOPS"): hourly(WIN_B, WIN_E, lambda x: 1306.50)})
    r = R.evaluate_lake(entry(p, t), get)
    assert r["result"] == "PASS" and r["n"] == 21 and r["medAE"] == 0.02 and r["meanE"] == 0.02
    assert all("cwms-data.usace.army.mil" in u for u in get.urls) and len(get.urls) == 2


def test_datum_error_fails_and_offset_is_added():
    p = dict(cwms_ref("cwms", "NAP", "B.Elev.Inst.15Minutes.0.Rev-DCP-88"))
    t = cwms_ref("cwmsDaily", "NAP", "B.Elev.Inst.~1Day.0.Rev-DCP", cadence="DAILY", off=0.0)
    series = {("cwms", "NAP", "B.Elev.Inst.15Minutes.0.Rev-DCP-88"): hourly(WIN_B, WIN_E, lambda x: 640.0),
              ("cwms", "NAP", "B.Elev.Inst.~1Day.0.Rev-DCP"): [(WIN_B + dt.timedelta(days=i, hours=6), 640.66) for i in range(29)]}
    assert R.evaluate_lake(entry(p, t), FakeGet(series))["result"] == "FAIL"
    t2 = dict(t, offsetFt=-0.66)                                            # the recorded offset (ADDED) puts truth on the live datum
    r = R.evaluate_lake(entry(p, t2), FakeGet(series))
    assert r["result"] == "PASS" and r["maxAE"] == 0.0


def test_daily_usgs_truth_at_noon_local_is_outside_daily_tolerance_of_midnight_value():
    p = {"kind": "nwps", "family": "NWS", "key": ["ECRI3"], "station": "ECRI3", "series": "HPIRG", "offsetFt": 0.0, "cadence": "SUB_DAILY",
         "cadenceMin": 60, "lagMin": 120}
    t = {"kind": "usgsDaily", "family": "USGS", "key": ["03353450", "62614"], "site": "03353450", "param": "62614", "stat": "00003",
         "offsetFt": 0.0, "cadence": "DAILY", "independence": "CROSS_AGENCY", "boundRole": "HISTORY"}
    days = [((dt.date(2026, 10, 27) + dt.timedelta(days=i)).isoformat(), 790.1) for i in range(30)]
    get = FakeGet({("nwps", "ECRI3"): hourly(WIN_B, WIN_E, lambda x: 790.0), ("usgsdv", "03353450", "62614"): days})
    r = R.evaluate_lake(entry(p, t, stratum="nwps"), get)
    # B at 00:00 local; the previous day's 12:00 local value is 12 h earlier (within 13 h): matched
    assert r["n"] == 21 and r["result"] == "PASS" and r["medAE"] == 0.1


def test_rise_primary_daily_values_and_insufficient_when_truth_missing():
    p = {"kind": "rise", "family": "USBR", "key": ["164"], "station": "164", "offsetFt": 0.0, "cadence": "DAILY", "cadenceMin": 1440, "lagMin": 2880}
    t = cwms_ref("cwms", "NWDM", "YETL.Elev.Inst.1Hour.0.Best-NWO", cls="CROSS_AGENCY")
    rise = [(dt.datetime(2026, 10, 27, tzinfo=dt.timezone(dt.timedelta(hours=-7))) + dt.timedelta(days=i), 3620.0) for i in range(29)]
    get = FakeGet({("rise", "164"): rise + [(dt.datetime(2026, 11, 30, tzinfo=UTC), 0.0)]})
    r = R.evaluate_lake(entry(p, t, tz="America/Denver", stratum="rise"), get)
    assert r["result"] == "INSUFFICIENT" and r["noTruthMatch"] == 21 and r["errors"]
    get = FakeGet({("rise", "164"): rise, ("cwms", "NWDM", "YETL.Elev.Inst.1Hour.0.Best-NWO"): hourly(WIN_B, WIN_E, lambda x: 3620.3)})
    r = R.evaluate_lake(entry(p, t, tz="America/Denver", stratum="rise"), get)
    assert r["result"] == "FAIL" and r["shareWithin"] == 1.0 and r["medAE"] == 0.3     # within 0.5 ft, but median above 0.25 ft


def test_nwps_pe_mismatch_is_a_fetch_error():
    def get(url, accept="application/json"):
        return 200, json.dumps({"pedts": "HGIRG", "primaryUnits": "ft", "data": []}).encode()
    with pytest.raises(R.FetchError):
        R.read_nwps(get, "X", "HP")


# ---------------------------------------------------------------- verdict and proposal
def lake(stratum, result, n=21, within=21, cls="OPERATOR_OTHER_SERIES"):
    return {"lakeId": f"{stratum}-{result}-{id(object())}", "stratum": stratum, "result": result, "n": n, "within": within,
            "truthClass": cls, "truthCadence": "SUB_DAILY"}


def test_verdict_pass_fail_inconclusive():
    lakes = [lake("a2w", "PASS") for _ in range(25)] + [lake("cwms", "PASS") for _ in range(10)] + [lake("rise", "PASS") for _ in range(9)] \
        + [lake("nwps", "PASS") for _ in range(4)] + [lake("nwps", "FAIL", within=10)]
    v = R.verdict(R.summarize(lakes))
    assert v["verdict"] == "PASS"
    v = R.verdict(R.summarize(lakes + [lake("nwps", "FAIL", within=10)]))      # nwps 4/6 PASS = 0.67 < 0.75
    assert v["verdict"] == "FAIL" and v["criteria"]["V4"]["strataBelow"] == ["nwps"]
    v = R.verdict(R.summarize(lakes[:40]))
    assert v["verdict"] == "INCONCLUSIVE"


def test_proposal_shape_matches_swift_validation_summary_and_only_on_pass():
    lakes = [lake("a2w", "PASS") for _ in range(30)] + [lake("cwms", "PASS") for _ in range(10)] + [lake("rise", "PASS") for _ in range(9)]
    s = R.summarize(lakes)
    res = {"summary": s, "verdict": R.verdict(s), "runAt": "2026-11-25T03:00:00Z"}
    prop = R.validation_node_proposal(res)
    assert set(prop) == {"brainId", "modelVersion", "validationVersion", "status", "lastRunAt", "holdoutType", "sampleCount", "lakeCount", "notes"}
    assert prop["status"] == "PARTIAL" and prop["lakeCount"] == 49 and prop["sampleCount"] == 49 * 21
    assert isinstance(prop["sampleCount"], int) and all(isinstance(n, str) for n in prop["notes"])
    res["verdict"] = {"verdict": "FAIL"}
    assert R.validation_node_proposal(res) is None


def test_run_window_and_outputs_only_in_out_dir(tmp_path):
    assert not R.in_run_window(dt.datetime(2026, 11, 23, tzinfo=UTC))
    assert R.in_run_window(dt.datetime(2026, 11, 25, tzinfo=UTC))
    assert not R.in_run_window(dt.datetime(2026, 12, 1, tzinfo=UTC))
    p = cwms_ref("cwms", "MVK", "A.Elev.Inst.1Hour.0.DCP-rev")
    t = cwms_ref("cwmsDaily", "MVK", "A.Elev.Inst.1Day.0.Manual", cadence="DAILY")
    sample = {"verdictSample": [entry(p, t)], "reportOnlySample": []}
    get = FakeGet({("cwms", "MVK", "A.Elev.Inst.1Hour.0.DCP-rev"): hourly(WIN_B, WIN_E, lambda x: 230.0),
                   ("cwms", "MVK", "A.Elev.Inst.1Day.0.Manual"): [(WIN_B + dt.timedelta(days=i, hours=13), 230.1) for i in range(29)]})
    res = R.run(sample, get, True, 1, dt.datetime(2026, 11, 25, tzinfo=UTC))
    assert res["published"] is False and res["verdict"]["verdict"] == "INCONCLUSIVE" and res["proposedValidationNode"] is None
    out = tmp_path / "out"
    paths = R.write_outputs(res, str(out))
    assert sorted(os.listdir(out)) == sorted(os.path.basename(x) for x in paths) and len(paths) == 3
    assert "no change (stays NOT_VALIDATED)" in R.summary_text(res)
