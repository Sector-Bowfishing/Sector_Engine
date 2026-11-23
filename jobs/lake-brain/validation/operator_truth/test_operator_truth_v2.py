"""Offline tests of the operator-truth v2 rule and runner, on hand-built fixtures (no network)."""
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.parse
from zoneinfo import ZoneInfo

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_sample_v2 as B  # noqa: E402
import run_operator_truth_v2 as R  # noqa: E402

UTC = dt.timezone.utc
CHI = ZoneInfo("America/Chicago")


# ---------------------------------------------------------------- the v2 rule
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


def cls(primary, cand, op="CWMS"):
    return B.classify(B.candidate(primary, "value"), B.candidate(cand, "history" if "kind" in cand else "live"), op)


def test_same_location_parameter_across_offices_is_same_series():
    assert cls(lv("cwms", "NWO", "CHCR.Elev.Inst.1Hour.0.Best-NWO"), lv("cwms", "NWDM", "CHCR.Elev.Inst.1Hour.0.Best-NWO")) == "SAME_SERIES"
    assert cls(lv("a2w", "NWP:FRN", "FRN.Elev-Forebay.Inst.0.0.MIXED-REV"), {"kind": "cwmsDaily", "office": "NWDP",
               "series": "FRN.Elev-Forebay.Inst.~1Day.0.CBT-REV"}) == "SAME_SERIES"


def test_raw_and_rev_of_one_feed_is_same_series():
    assert cls(lv("a2w", "SWL:Bull_Shoals", "Bull_Shoals_Dam-Headwater.Elev.Inst.1Hour.0.Decodes-rev"),
               lv("cwms", "SWL", "Bull_Shoals_Dam-Headwater.Elev.Inst.1Hour.0.Decodes-raw")) == "SAME_SERIES"
    assert cls(lv("a2w", "LRL:Barren", "Barren.Elev.Inst.0.0.lrldlb-rev"), lv("cwms", "LRL", "Barren.Elev.Inst.0.0.lrldlb-raw")) == "SAME_SERIES"


def test_same_sensor_suspected_cases():
    assert cls(lv("a2w", "LRP:Kinzua", "Kinzua-Lake.Elev.Inst.1Hour.0.OBS"), lv("cwms", "LRP", "Kinzua-Lake.Elev.Inst.1Hour.0.RESOPS")) \
        == "SAME_SENSOR_SUSPECTED"
    assert cls(lv("cwms", "SAW", "BEJ.Elev.Inst.15Minutes.0.USGS-raw"), lv("usgs", "02098197", "62614")) == "SAME_SENSOR_SUSPECTED"
    assert cls(lv("cwms", "SWF", "PSMT2.Elev.Inst.1Hour.0.Decodes-Rev"), {"kind": "usgsDaily", "site": "08088500", "param": "62614",
               "stat": "dv"}) == "SAME_SENSOR_SUSPECTED"
    assert cls(lv("nwps", "DIXK2", "HPIRG"), lv("usgs", "03290080", "62614"), op=None) == "SAME_SENSOR_SUSPECTED"
    assert cls(lv("cwms", "MVP", "MissHW_Leech-Lake.Elev.Inst.~15Minutes.0.best-NGVD29"),
               {"kind": "cwmsDaily", "office": "MVP", "series": "MissHW_Leech.Elev.Inst.~15Minutes.0.best-NGVD29"}) == "SAME_SERIES"


def test_independent_classes():
    assert cls(lv("cwms", "LRP", "Milton-Lake.Elev.Inst.1Hour.0.RESOPS"), {"kind": "usgsDaily", "site": "03091000", "param": "62615",
               "stat": "dv"}) == "CROSS_AGENCY"
    assert cls(lv("cwms", "SPA", "Pueblo.Elev.Inst.15Minutes.0.DCP-rev"), {"kind": "riseDaily", "item": "682"}, op="USBR") \
        == "OPERATOR_OTHER_SERIES"


def test_fallback_offset_datum_and_a1_block_the_verdict():
    r = B.assign(rec([lv("cwms", "LRP", "X.Elev.Inst.1Hour.0.OBS"), lv("usgs", "1", "62614")]), {})
    assert r["status"] == "REPORT_ONLY_ELIGIBLE" and r["candidates"][0]["verdictBlock"].startswith("FALLBACK_LIVE")
    r = B.assign(rec([lv("cwms", "LRP", "X.Elev.Inst.1Hour.0.OBS")], [{"kind": "usgsDaily", "site": "1", "param": "62614", "stat": "dv",
                                                                     "offsetFt": 2434.4}]), {})
    assert r["candidates"][0]["verdictBlock"] == "OFFSET_FITTED" and r["status"] != "VERDICT"
    r = B.assign(rec([lv("usgs", "9", "62615")], [{"kind": "cwmsDaily", "office": "SWF", "series": "Y.Elev.Inst.~1Day.0.Manual"},
                                                 {"kind": "usgsDaily", "site": "8", "param": "62614", "stat": "dv"}]), {})
    assert r["candidates"][1]["verdictBlock"] == "DATUM_MISMATCH" and r["truth"]["kind"] == "cwmsDaily"
    r = B.assign(rec([lv("a2w", "SWT:Keystone", "Keystone.Elev.Inst.1Hour.0.Ccp-Rev")],
                     [{"kind": "usgsDaily", "site": "1", "param": "00062", "stat": "dv"}]), {})
    assert r["status"] == "EXCLUDED_A1_UNVERIFIED"
    r = B.assign(rec([lv("a2w", "SWT:Keystone", "Keystone.Elev.Inst.1Hour.0.Ccp-Rev"), lv("cwms", "SWD", "Keystone.Elev.Inst.1Hour.0.Ccp-Rev")],
                     [{"kind": "usgsDaily", "site": "1", "param": "00062", "stat": "dv"}]), {})
    assert r["status"] == "VERDICT" and r["primary"]["key"][0] == "SWD" and r["independentTruth"]


def test_frozen_set_is_the_rule_output_and_preregistered():
    assert R.verify_preregistration() == []
    with open(R.SAMPLE_PATH, encoding="utf-8") as fh:
        assert fh.read() == B.dumps(B.build(B.load_generated(), B.load_accepted(), B.load_reviewed()))


def _chain(tmp_path, runner_text="print(1)\n"):
    files = {"sample_v2.json": tmp_path / "s.json", "build_sample_v2.py": tmp_path / "b.py", "run_operator_truth_v2.py": tmp_path / "r.py"}
    for i, p in enumerate(files.values()):
        p.write_text(runner_text if i == 2 else f"x{i}")
    pins = "\n".join(f"`{k}` {hashlib.sha256(p.read_bytes()).hexdigest()}" for k, p in files.items())
    prereg = tmp_path / "P.md"
    prereg.write_text(f"protocol\n<!-- pins:begin -->\n{pins}\n<!-- pins:end -->\n")
    lock = tmp_path / "P.sha256"
    lock.write_text(hashlib.sha256(prereg.read_bytes()).hexdigest() + "\n")
    return prereg, lock, {k: str(v) for k, v in files.items()}


def test_integrity_chain(tmp_path):
    prereg, lock, files = _chain(tmp_path)
    assert R.verify_preregistration(str(prereg), str(lock), files) == []
    open(files["run_operator_truth_v2.py"], "a").write("# tampered\n")
    assert R.verify_preregistration(str(prereg), str(lock), files) == ["run_operator_truth_v2.py differs from its pre-registered sha256"]
    prereg.write_text("changed")
    assert R.verify_preregistration(str(prereg), str(lock), files) == ["protocol differs from the sha256 in its lock file"]
    os.remove(files["sample_v2.json"])
    assert any("missing" in x for x in R.verify_preregistration(str(prereg), str(lock), files))


def test_missing_sample_is_refused_not_a_crash(monkeypatch, capsys):
    monkeypatch.setattr(R, "verify_preregistration", lambda: [])
    monkeypatch.setattr(R, "SAMPLE_PATH", "/nonexistent/sample_v2.json")
    assert R.main(["--verify-only"]) == 2 and "REFUSED" in capsys.readouterr().out


# ---------------------------------------------------------------- runner pieces
def test_brain_value_selection_freshness_and_rounding():
    m = dt.datetime(2026, 11, 3, 0, 0, tzinfo=CHI)
    obs = [(m - dt.timedelta(hours=2), 600.004), (m - dt.timedelta(minutes=30), 600.126), (m + dt.timedelta(minutes=5), 700.0)]
    assert R.brain_value(obs, m, 120, 60) == (m - dt.timedelta(minutes=30), 600.13)
    assert R.brain_value([(m - dt.timedelta(minutes=301), 1.0)], m, 120, 60) is None
    assert R.is_fresh(m - dt.timedelta(minutes=180), m, 120, 60) and not R.is_fresh(m - dt.timedelta(minutes=181), m, 120, 60)


def test_merge_keeps_the_later_reading_of_a_timestamp():
    t = dt.datetime(2026, 11, 3, tzinfo=UTC)
    assert R._merge([(t, 1.0), (t, 2.0)]) == [(t, 2.0)]


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


def entry(primary, truth, lake="Test Lake|XX", tz="America/Chicago", stratum=None, independent=False):
    return {"lakeId": lake, "timeZone": tz, "primaryProvider": stratum or primary["kind"], "primary": primary, "truth": truth,
            "independentTruth": independent}


def cwms_ref(kind, office, name, cadence="SUB_DAILY", off=0.0, cls="OPERATOR_OTHER_SERIES"):
    return {"kind": kind, "family": "CWMS", "key": [office, name], "offsetFt": off, "cadence": cadence, "cadenceMin": 60, "lagMin": 120,
            "independence": cls, "boundRole": "HISTORY"}


WIN_B = dt.datetime(2026, 10, 27, tzinfo=UTC)
WIN_E = dt.datetime(2026, 11, 25, tzinfo=UTC)


def test_a2w_value_is_read_from_cwms_under_its_evidenced_office_and_agreeing_lake_passes():
    p = cwms_ref("a2w", "SWD", "K.Elev.Inst.1Hour.0.Ccp-Rev")
    t = {"kind": "usgsDaily", "family": "USGS", "key": ["1", "62614"], "site": "1", "param": "62614", "stat": "00003", "offsetFt": 0.0,
         "cadence": "DAILY", "independence": "CROSS_AGENCY", "boundRole": "HISTORY"}
    days = [((dt.date(2026, 10, 27) + dt.timedelta(days=i)).isoformat(), 723.4) for i in range(30)]
    get = FakeGet({("cwms", "SWD", "K.Elev.Inst.1Hour.0.Ccp-Rev"): hourly(WIN_B, WIN_E, lambda x: 723.5), ("usgsdv", "1", "62614"): days})
    r = R.evaluate_lake(entry(p, t, stratum="a2w", independent=True), get)
    assert r["result"] == "PASS" and r["n"] == 21 and r["medAE"] == 0.1 and r["medianAgeMin"] == 0 and r["independent"]
    assert any("cwms-data" in u and "office=SWD" in u for u in get.urls)


def test_datum_error_fails_and_recorded_offset_is_added():
    p = cwms_ref("cwms", "NAP", "B.Elev.Inst.15Minutes.0.Rev-DCP-88")
    t = cwms_ref("cwmsDaily", "NAP", "C.Elev.Inst.~1Day.0.Manual", cadence="DAILY")
    series = {("cwms", "NAP", "B.Elev.Inst.15Minutes.0.Rev-DCP-88"): hourly(WIN_B, WIN_E, lambda x: 640.0),
              ("cwms", "NAP", "C.Elev.Inst.~1Day.0.Manual"): [(WIN_B + dt.timedelta(days=i, hours=6), 640.66) for i in range(29)]}
    assert R.evaluate_lake(entry(p, t), FakeGet(series))["result"] == "FAIL"
    r = R.evaluate_lake(entry(p, dict(t, offsetFt=-0.66)), FakeGet(series))
    assert r["result"] == "PASS" and r["maxAE"] == 0.0


def test_previous_day_usgs_mean_at_noon_local_is_within_daily_tolerance():
    p = cwms_ref("cwms", "LRP", "Milton-Lake.Elev.Inst.1Hour.0.RESOPS")
    t = {"kind": "usgsDaily", "family": "USGS", "key": ["03091000", "62615"], "site": "03091000", "param": "62615", "stat": "dv",
         "offsetFt": 0.0, "cadence": "DAILY", "independence": "CROSS_AGENCY", "boundRole": "HISTORY"}
    days = [((dt.date(2026, 10, 27) + dt.timedelta(days=i)).isoformat(), 948.1) for i in range(30)]
    r = R.evaluate_lake(entry(p, t), FakeGet({("cwms", "LRP", "Milton-Lake.Elev.Inst.1Hour.0.RESOPS"): hourly(WIN_B, WIN_E, lambda x: 948.0),
                                              ("usgsdv", "03091000", "62615"): days}))
    assert r["n"] == 21 and r["result"] == "PASS" and r["medAE"] == 0.1          # 00:00 local vs the previous day's 12:00 local: 12 h


def test_stale_brain_values_are_not_scored_and_ages_reported():
    p = cwms_ref("cwms", "MVK", "A.Elev.Inst.1Hour.0.DCP-rev")
    t = cwms_ref("cwmsDaily", "MVK", "Z.Elev.Inst.1Day.0.Manual", cadence="DAILY")
    every4h = [x for x in hourly(WIN_B, WIN_E, lambda x: 230.0) if x[0].hour in (2, 14)]   # 4 h old at 00:00 CST: selectable, stale
    get = FakeGet({("cwms", "MVK", "A.Elev.Inst.1Hour.0.DCP-rev"): every4h,
                   ("cwms", "MVK", "Z.Elev.Inst.1Day.0.Manual"): [(WIN_B + dt.timedelta(days=i, hours=13), 230.0) for i in range(29)]})
    r = R.evaluate_lake(entry(p, t), get)
    assert r["staleBrainValue"] == 21 and r["result"] == "INSUFFICIENT" and r["insufficientReason"] == "STALE_BRAIN_VALUE"
    assert all(n["ageMin"] > 180 for n in r["nights"])


def test_rise_drops_placeholders_and_missing_truth_is_insufficient():
    p = {"kind": "rise", "family": "USBR", "key": ["164"], "station": "164", "offsetFt": 0.0, "cadence": "DAILY", "cadenceMin": 1440, "lagMin": 2880}
    t = cwms_ref("cwms", "NWDM", "YETL.Elev.Inst.1Hour.0.Best-NWO", cls="CROSS_AGENCY")
    rise = [(dt.datetime(2026, 10, 27, tzinfo=dt.timezone(dt.timedelta(hours=-7))) + dt.timedelta(days=i), 3620.0) for i in range(29)]
    obs = R.read_rise(FakeGet({("rise", "164"): rise + [(dt.datetime(2026, 11, 30, tzinfo=UTC), 0.0)]}), "164", WIN_B)
    assert len(obs) == 29
    r = R.evaluate_lake(entry(p, t, tz="America/Denver", stratum="rise"), FakeGet({("rise", "164"): rise}))
    assert r["result"] == "INSUFFICIENT" and r["noTruthMatch"] == 21 and r["errors"]


def test_nwps_pe_mismatch_is_a_fetch_error():
    def get(url, accept="application/json"):
        return 200, json.dumps({"pedts": "HGIRG", "primaryUnits": "ft", "data": []}).encode()
    with pytest.raises(R.FetchError):
        R.read_nwps(get, "X", "HP")


# ---------------------------------------------------------------- verdict and proposal
def lake(stratum, result, n=21, within=21, independent=False):
    return {"lakeId": f"{stratum}-{result}-{id(object())}", "stratum": stratum, "result": result, "n": n, "within": within,
            "truthClass": "CROSS_AGENCY" if independent else "OPERATOR_OTHER_SERIES", "truthCadence": "DAILY", "independent": independent}


def _big(independent):
    return [lake("a2w", "PASS", independent=independent) for _ in range(25)] + [lake("cwms", "PASS", independent=independent) for _ in range(10)] \
        + [lake("rise", "PASS", independent=independent) for _ in range(10)]


def test_verdict_needs_the_independent_subset_on_its_own():
    lakes = _big(False) + _big(True)
    v = R.verdict(R.summarize(lakes), R.summarize([x for x in lakes if x["independent"]]))
    assert v["verdict"] == "PASS"
    small_ind = _big(False) + [lake("a2w", "PASS", independent=True) for _ in range(4)]
    v = R.verdict(R.summarize(small_ind), R.summarize([x for x in small_ind if x["independent"]]))
    assert v["verdict"] == "INCONCLUSIVE" and v["criteria"]["V1"]["pass"] and not v["independentCriteria"]["V1"]["pass"]
    bad = _big(False) + _big(True)[:35] + [lake("rise", "FAIL", within=5, independent=True) for _ in range(10)]
    v = R.verdict(R.summarize(bad), R.summarize([x for x in bad if x["independent"]]))
    assert v["verdict"] == "FAIL" and v["independentCriteria"]["V4"]["strataBelow"] == ["rise"]


def test_frozen_v2_set_cannot_reach_a_fleet_verdict():
    with open(R.SAMPLE_PATH, encoding="utf-8") as fh:
        s = json.load(fh)
    assert len(s["verdictSet"]) < R.V1_MIN_SCORED                                  # pre-registered: v2 is INCONCLUSIVE whatever the data say


def test_proposal_shape_matches_swift_validation_summary_and_only_on_pass():
    lakes = _big(True)
    s = R.summarize(lakes)
    res = {"summary": s, "verdict": R.verdict(s, s), "runAt": "2026-11-25T03:00:00Z", "preregSha256": "a" * 64, "runnerSha256": "b" * 64}
    prop = R.validation_node_proposal(res)
    assert set(prop) == {"brainId", "modelVersion", "validationVersion", "status", "lastRunAt", "holdoutType", "sampleCount", "lakeCount", "notes"}
    assert prop["status"] == "PARTIAL" and prop["lakeCount"] == 45 and prop["sampleCount"] == 45 * 21
    res["verdict"] = {"verdict": "INCONCLUSIVE"}
    assert R.validation_node_proposal(res) is None


def test_run_records_runner_hash_and_commit_and_writes_only_out_dir(tmp_path):
    assert not R.in_run_window(dt.datetime(2026, 11, 23, tzinfo=UTC)) and R.in_run_window(dt.datetime(2026, 11, 25, tzinfo=UTC))
    p = cwms_ref("cwms", "MVK", "A.Elev.Inst.1Hour.0.DCP-rev")
    t = cwms_ref("cwmsDaily", "MVK", "Z.Elev.Inst.1Day.0.Manual", cadence="DAILY")
    sample = {"verdictSet": [entry(p, t)], "reportOnlySample": []}
    get = FakeGet({("cwms", "MVK", "A.Elev.Inst.1Hour.0.DCP-rev"): hourly(WIN_B, WIN_E, lambda x: 230.0),
                   ("cwms", "MVK", "Z.Elev.Inst.1Day.0.Manual"): [(WIN_B + dt.timedelta(days=i, hours=13), 230.1) for i in range(29)]})
    res = R.run(sample, get, True, 1, dt.datetime(2026, 11, 25, tzinfo=UTC), "c" * 64, "d" * 64, "abc123")
    assert res["runnerSha256"] == "d" * 64 and res["commit"] == "abc123" and res["published"] is False
    assert res["verdict"]["verdict"] == "INCONCLUSIVE" and res["proposedValidationNode"] is None
    out = tmp_path / "out"
    paths = R.write_outputs(res, str(out))
    assert sorted(os.listdir(out)) == sorted(os.path.basename(x) for x in paths) and len(paths) == 3
    assert "no change (stays NOT_VALIDATED)" in R.summary_text(res)
