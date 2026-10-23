"""Automatic discovery in the campaign coordinator, offline (a fake source server): gaps reconstructed when GAPS.json is missing, inputs
reconstructed or recorded as limitations, allowlisted acquisition with provenance + manifest registration, offline re-validation from the
hashed evidence, candidate packaging (approval NOT_RECORDED), follow-up iterations on weak areas, and acquisition failures that never stop
the campaign."""
import copy
import datetime as dt
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import campaign as C  # noqa: E402

D = C.D
LAKE = {"lat": 35.0, "lon": -86.0}
START, END = "2023-01-01", "2023-06-30"


def days(a, b):
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def forcing(a, b):
    t = days(a, b)
    return {"latitude": LAKE["lat"], "longitude": LAKE["lon"], "daily": {"time": t, "temperature_2m_mean": [20.0] * len(t),
            "shortwave_radiation_sum": [None] * len(t), "wind_speed_10m_mean": [None] * len(t), "relative_humidity_2m_mean": [None] * len(t)}}


class FakeSources(D.Fetcher):
    """Site 1 (near): sensor 3 C warmer than M0 (fails the 2.0 C bar). Site 2 (0.2 deg away, found only by the wider follow-up radius):
    0.3 C off and a longer record. WQP protected-lake metadata: header only (no new casts)."""

    def __init__(self):
        super().__init__(gap=0)
        self.calls = []

    def get(self, base, params=None):
        self.url(base, params)
        p = dict(params or {})
        self.calls.append((base, p))
        if base.endswith("/nwis/site/"):
            rows = ["agency_cd\tsite_no\tstation_nm\tsite_tp_cd\tdec_lat_va\tdec_long_va", "5s\t15s\t50s\t7s\t16s\t16s",
                    "USGS\t0001\tALPHA LAKE NEAR TOWN\tLK\t35.05\t-86.0", "USGS\t0002\tALPHA LAKE AT DAM\tLK\t35.2\t-86.0",
                    "USGS\t0003\tOTHER WATER NEAR TOWN\tLK\t35.01\t-86.0"]
            return ("# rdb\n" + "\n".join(rows) + "\n").encode()
        if base.endswith("/nwis/dv/"):
            off, start = (3.0, "2023-04-01") if p["sites"] == "0001" else (0.3, "2023-03-01")
            vals = [{"value": f"{22.2 + off:.2f}", "qualifiers": ["A"], "dateTime": d + "T00:00:00.000"} for d in days(start, END)]
            return json.dumps({"value": {"timeSeries": [{"name": f"USGS:{p['sites']}:00010:00003", "values": [{"method": [{"methodDescription": ""}],
                                                                                                               "value": vals}]}]}}).encode()
        if "open-meteo" in base:
            return json.dumps(forcing(p["start_date"], p["end_date"])).encode()
        if "waterqualitydata" in base:
            return b"OrganizationIdentifier,ActivityIdentifier,ActivityStartDate,MonitoringLocationIdentifier\n"
        return None


def wt_cfg():
    cfg = copy.deepcopy(D.load_config())
    w = cfg["brains"]["water-temp"]
    w.update({"startDate": START, "endDate": END, "pooledMinLakes": 1, "inputs": [],
              "protectedTruth": {"needed": 25, "sinceMMDDYYYY": "07-01-2026", "lakes": {"Wilson": {"bbox": [-87.6, 34.7, -87.3, 34.9], "recorded": 2}}}})
    return cfg


@pytest.fixture
def home(tmp_path):
    for bid, folder in C.DEFAULT_FOLDERS.items():
        d = tmp_path / folder
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({"brainId": bid, "items": [{"id": "existing", "workspacePath": "x", "retention": "ARCHIVAL"}]}))
    f = tmp_path / "water-temperature" / "validation" / "valmodel" / "forcing"
    f.mkdir(parents=True)
    (f / "Alpha_Lake_TN.json").write_text(json.dumps(forcing("2022-11-01", "2022-11-02")))
    snap = tmp_path / "water-temperature" / "validation" / "campaign-2026-10-22"
    snap.mkdir(parents=True)
    (snap / "wt_w5_sensor_snapshot.json").write_text(json.dumps({"rows": [{"sensor": "usgs:0009", "inM0CalibrationSet": True}]}))
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "manifest.json").write_text(json.dumps({"items": []}))
    return str(tmp_path)


def test_real_cycle_shape_discover_validate_package_follow_up_and_clean(home, monkeypatch):
    monkeypatch.setattr(C, "discovery_cfg", wt_cfg)
    C.init(home, "w1", brains=["water-temp"])
    src = FakeSources()
    assert C.run(home, "w1", adapters={}, fetcher=src) == {"water-temp": "DONE"}
    t = C.Campaign(home, "w1").load()["tracks"]["water-temp"]
    sg = t["stages"]
    # missing Engine GAPS.json -> reconstructed in the research home from the frozen score blockers
    g = sg["discover"]["result"]["gaps"]
    assert g["reconstructed"] and "WATERTEMP-GEN-LEVEL4PROTECTEDTRUTH" in g["open"]
    assert os.path.exists(os.path.join(home, "water-temperature", "research", "GAPS.generated.json"))
    # iteration 1: site 1 fails 2.0 C -> follow-up with a wider radius finds site 2 (site 1 excluded), which validates
    assert t["iteration"] == 2 and t["history"][0]["weak"] == ["Alpha_Lake_TN"]
    assert len(t["history"]) == 2 and t["history"][1]["weak"] == []        # iteration 2 ran its own follow-up evaluation
    assert sg["followup"]["result"]["continued"] is False and sg["followup"]["result"]["reason"] == "no weak areas"
    dv_sites = [p["sites"] for b, p in src.calls if b.endswith("/nwis/dv/")]
    assert dv_sites == ["0001", "0002"]                                    # distance-only match "OTHER WATER" never fetched
    v = sg["validate"]["result"]
    assert v["discoveryReproducible"] is True
    verdicts = {r["id"]: r["verdict"] for r in v["results"]}
    assert verdicts["WT-AUTO-SENSOR-Alpha_Lake_TN"] == "VALIDATED" and verdicts["WT-AUTO-SENSOR-POOLED"] == "VALIDATED"
    cand = sg["candidate"]["result"]
    assert cand["packaged"] and cand["approval"] == "NOT_RECORDED"
    assert C.K.load_release(os.path.join(home, cand["path"]), "water-temp")["approvalStatus"] == "NOT_RECORDED"
    # provenance + manifest registration; the workspace is cleaned, the evidence is retained
    prov = json.load(open(os.path.join(home, "water-temperature", "sources", "w1", "PROVENANCE.json")))
    saved = [p for p in prov["files"].values() if p["status"] == "SAVED"]
    assert saved and all(p["sha256"] and p["license"] and p["url"].startswith("https://") for p in saved)
    m = json.load(open(os.path.join(home, "water-temperature", "manifest.json")))
    assert sum(i["retention"] == "RECONSTRUCTABLE" for i in m["items"]) == len(saved) and m["items"][0]["id"] == "existing"
    assert not os.path.exists(os.path.join(home, "water-temperature", "analysis", "tmp", "w1"))
    # the Level-4 gap is an approval limitation (metadata only), never a protected-value read; the frozen score is unchanged
    lim = sg["research"]["result"]["limitations"]
    assert any(x.get("kind") == "approval" and "OWNER APPROVAL REQUIRED" in x["limitation"] for x in lim)
    assert sg["score"]["result"]["authoritativeUnchanged"] and "unchanged" in sg["score"]["result"]["impact"]["score"]
    assert "Result/search" not in json.dumps(src.calls)                    # no WQP result values requested for the protected lakes
    rep = open(os.path.join(home, "shared", "campaigns", "w1", "REPORT.md")).read()
    assert "OWNER APPROVAL REQUIRED" in rep and "reconstructed: True" in rep


def test_tampered_evidence_is_rejected_at_validation(home, monkeypatch):
    monkeypatch.setattr(C, "discovery_cfg", wt_cfg)
    orig = C.STAGE_FN["validate"]

    def tamper(c, st, bid, ad, timeout):
        for root, _, files in os.walk(os.path.join(home, "water-temperature", "sources")):
            for f in files:
                if "usgs-dv" in root:
                    open(os.path.join(root, f), "a").write(" ")
        return orig(c, st, bid, ad, timeout)

    monkeypatch.setitem(C.STAGE_FN, "validate", tamper)
    monkeypatch.setattr(C, "discovery_cfg", lambda: {**wt_cfg(), "maxIterations": 1})
    C.init(home, "w2", brains=["water-temp"])
    C.run(home, "w2", adapters={}, fetcher=FakeSources())
    v = C.Campaign(home, "w2").load()["tracks"]["water-temp"]["stages"]["validate"]["result"]
    sensor = [r for r in v["results"] if r["id"].startswith("WT-AUTO-SENSOR")]
    assert sensor and all(r["verdict"] == "REJECTED" and "sha256 mismatch" in r["reason"] for r in sensor)


def test_all_eight_complete_when_every_source_fails_and_adapters_are_blocked(home, tmp_path):
    blocked = tmp_path / "blocked.py"
    blocked.write_text("import json,sys\nprint(json.dumps({'rc': 2, 'blocked': 'external input missing'}))\nsys.exit(2)\n")
    ad = {b: {"research": {"cmd": ["{python}", str(blocked)]}} for b in C.BRAINS}
    C.init(home, "w3")
    fin = C.run(home, "w3", adapters=ad, fetcher=D.OfflineFetcher())
    assert fin == {b: "DONE" for b in C.BRAINS}                            # nothing stops the campaign
    st = C.Campaign(home, "w3").load()
    for bid, t in st["tracks"].items():
        assert t["stages"]["research"]["result"]["adapterBlocked"] == "external input missing"
        acq = t["stages"]["acquire"]["result"]
        if D.load_config()["brains"][bid]["kind"] not in ("upstream", "literature"):
            assert acq["failureCount"] > 0 and acq["evidenceFiles"] == 0, (bid, acq)   # recorded, not fatal
    rep = json.load(open(os.path.join(home, "shared", "campaigns", "w3", "report.json")))
    assert rep["complete"] and all(r["candidate"] is None for r in rep["tracks"])   # no evidence -> nothing invented


def test_fetcher_refuses_hosts_outside_the_allowlist():
    f = D.Fetcher()
    for bad in ("https://example.com/x", "http://waterservices.usgs.gov/nwis/dv/", "https://firebaseio.com/x", "file:///etc/passwd"):
        with pytest.raises(D.FetchError):
            f.url(bad)
    assert f.url("https://api.gbif.org/v1/occurrence/search", {"limit": 0}).startswith("https://api.gbif.org/")


def test_missing_inputs_are_reconstructed_or_recorded_never_raised(tmp_path, monkeypatch):
    monkeypatch.delenv("SECTOR_NOT_SET_FOR_TEST", raising=False)
    r = D.check_inputs(C.ENGINE, str(tmp_path), [
        {"path": "x/adapters.json", "reconstruct": {"gitShow": "HEAD:tools/research/adapters.json"}},
        {"path": "x/missing.csv", "reconstruct": {"gitShow": "HEAD:no/such/file"}, "limitation": "not in git"},
        {"env": "SECTOR_NOT_SET_FOR_TEST", "limitation": "private data"}])
    assert [x["input"] for x in r["reconstructed"]] == ["x/adapters.json"] and os.path.exists(tmp_path / "x" / "adapters.json")
    assert [x["limitation"] for x in r["limitations"]] == ["not in git", "private data"]


def test_gaps_come_from_gaps_json_or_are_reconstructed(tmp_path):
    (tmp_path / "wind-brain").mkdir()
    w = D.load_gaps(C.ENGINE, str(tmp_path), "wind", "wind-brain", "wind")
    assert not w["reconstructed"] and w["gaps"] and not (tmp_path / "wind-brain" / "research").exists()
    (tmp_path / "lake-brain" / "closeouts").mkdir(parents=True)
    (tmp_path / "lake-brain" / "closeouts" / "2026-10-22-x.md").write_text("# x\n\n## Blockers\n\nhold-out needs the CWMS history for three lakes\n\n## Other\n")
    lk = D.load_gaps(C.ENGINE, str(tmp_path), "lake-brain", "lake-brain", "lake")
    assert lk["reconstructed"] and [g["title"] for g in lk["gaps"]] == ["hold-out needs the CWMS history for three lakes"]
    assert json.load(open(tmp_path / "lake-brain" / "research" / "GAPS.generated.json"))["gaps"] == lk["gaps"]


def test_findings_are_rejected_when_the_offline_re_run_does_not_reproduce_the_metrics(home, monkeypatch):
    monkeypatch.setattr(C, "discovery_cfg", lambda: {**wt_cfg(), "maxIterations": 1})
    orig, calls = C.run_analysis, []

    def drifting(c, st, bid):                                              # the validate-stage re-run disagrees with the research run
        out = orig(c, st, bid)
        calls.append(1)
        if out and len(calls) > 1:
            out["metrics"]["lakes"]["Alpha_Lake_TN"]["rmseC"] = 0.0
        return out

    monkeypatch.setattr(C, "run_analysis", drifting)
    C.init(home, "w4", brains=["water-temp"])
    C.run(home, "w4", adapters={}, fetcher=FakeSources())
    v = C.Campaign(home, "w4").load()["tracks"]["water-temp"]["stages"]["validate"]["result"]
    assert v["discoveryReproducible"] is False
    auto = [r for r in v["results"] if r["id"].startswith("WT-AUTO")]
    assert auto and all(r["verdict"] == "REJECTED" and "not produced" in r["reason"] for r in auto)   # unreproducible -> no metric at all


def test_read_only_sources_folder_is_never_modified(home, monkeypatch, tmp_path):
    """A protected (read-only) sources/ stays untouched; evidence goes beside it under research/discovery-sources/."""
    monkeypatch.setattr(C, "discovery_cfg", lambda: {**wt_cfg(), "maxIterations": 1})
    src = os.path.join(home, "water-temperature", "sources")
    os.makedirs(os.path.join(src, "protected"))
    os.chmod(src, 0o555)
    try:
        C.init(home, "w5", brains=["water-temp"])
        assert C.run(home, "w5", adapters={}, fetcher=FakeSources()) == {"water-temp": "DONE"}
        acq = C.Campaign(home, "w5").load()["tracks"]["water-temp"]["acquired"][-1]
        assert acq["evidenceRoot"] == "water-temperature/research/discovery-sources/w5" and acq["evidenceFiles"] > 0
        assert sorted(os.listdir(src)) == ["protected"] and (os.stat(src).st_mode & 0o777) == 0o555
    finally:
        os.chmod(src, 0o755)


def test_retry_failed_resumes_only_failed_stages_without_re_downloading(home, monkeypatch):
    monkeypatch.setattr(C, "discovery_cfg", lambda: {**wt_cfg(), "maxIterations": 1})
    C.init(home, "w6", brains=["water-temp"])
    bad = {"water-temp": {"validate": {"cmd": ["{python}", "-c", "import sys; sys.exit(1)"]}}}
    assert C.run(home, "w6", adapters=bad, fetcher=FakeSources()) == {"water-temp": "FAILED"}
    src = FakeSources()
    assert C.run(home, "w6", adapters={}, fetcher=src) == {"water-temp": "FAILED"}       # without --retry-failed nothing is re-opened
    assert C.run(home, "w6", adapters={}, fetcher=src, retry_failed=True) == {"water-temp": "DONE"}
    assert src.calls == []                                                                 # acquire was DONE: no source re-contacted
    sg = C.Campaign(home, "w6").load()["tracks"]["water-temp"]["stages"]
    assert sg["validate"]["retriedAfterFailure"] and sg["acquire"]["attempts"] == 1
