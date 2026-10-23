"""The corrected research workflow, offline. Each test reproduces a failure of the first overnight campaign (research-campaign-2026-10-23: 132 s, all
tracks DONE, no score moved, 'no weak areas' for Fish with three open gaps, dataset sizes and literature leads counted as VALIDATED) or
guards a rule of the new model: tiers are not interchangeable, the gap ledger decides when research stops, avenues never repeat, the
budget is respected, weak candidates are rejected on independent data and preserved, sources are registered explicitly, evidence is reused."""
import copy
import csv
import datetime as dt
import gzip
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import campaign as C  # noqa: E402

D, X, L = C.D, C.X, C.L
PY = sys.executable


# ------------------------------------------------------------------------------------------------------------------------------- fixtures
@pytest.fixture
def home(tmp_path):
    for bid, folder in C.DEFAULT_FOLDERS.items():
        d = tmp_path / folder
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({"brainId": bid, "items": [{"id": "existing", "workspacePath": "x", "retention": "ARCHIVAL"}]}))
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "manifest.json").write_text(json.dumps({"items": []}))
    return str(tmp_path)


def fake_acquire(content="same evidence"):
    def acquire(ev, home, spec, it, targets, gaps):
        rel = ev.rel("fake", spec["avenueId"] + ".txt")
        os.makedirs(os.path.dirname(os.path.join(home, rel)), exist_ok=True)
        open(os.path.join(home, rel), "w").write(content if content != "unique" else spec["avenueId"])
        sha = D.sha256(os.path.join(home, rel))
        ev.prov["files"][rel] = {"url": "https://example.test/" + spec["avenueId"], "sha256": sha, "bytes": 10, "status": "SAVED", "connector": "fake",
                                 "retrievedAt": D.now_iso(), "license": "test"}
        return {"evidencePath": rel}
    return acquire


def fake_analyze(tier="QUALITY_CHECKED", good=False, complete=True, kind="prediction", limit=None, weak=(), fail=False):
    """An experiment whose finding claims `tier`. good=True: the candidate beats the baseline by 1.0 (n=9); otherwise no gain."""
    def analyze(home, spec, mine, allacq, upstream=None):
        aid = spec["avenueId"]
        rel = mine[0]["evidencePath"]
        m = {"v": 0 if fail else 1, "base": 3.0, "cand": 2.0 if good else 3.0, "n": 9}
        g = f"discovery.exp.{aid}"
        ch = cap = None
        if L.rank(tier) >= L.rank("CANDIDATE_CHANGE"):
            ch = {k: ("x" if complete else "") for k in L.CHANGE_FIELDS}
            ch["proposed"] = {"offset": 1}
            cap = {"kind": kind, "name": "test error", "direction": "lower_better", "baselineMetric": g + ".base", "candidateMetric": g + ".cand", "minDelta": 0.5,
                   "nMetric": g + ".n", "minN": 3, "tests": [{"metric": g + ".cand", "op": "<=", "threshold": 2.5}]}
        f = D.finding(aid.upper(), f"claim {aid}", "PARAMETER", [rel], home, "test", g + ".v", ">=", 1, tier=tier, change=ch, capability=cap)
        return {"metrics": m, "findings": [f], "weak": list(weak), "limitations": limit or []}
    return analyze


def cfg_for(avenues, weaknesses=(("G-A", "gap a"), ("G-B", "gap b")), budget=None):
    return {"budget": {"wallSeconds": 3600, "maxAvenues": 40, "stallAvenues": 3, **(budget or {})},
            "brains": {"water-temp": {"purpose": "test", "weaknesses": [{"id": i, "title": t} for i, t in weaknesses], "avenues": avenues}}}


def av(aid, gaps=("G-A",), **kw):
    return {"id": aid, "run": "experiment", "experiment": "fake-" + aid, "gaps": list(gaps), **kw}


def register(monkeypatch, aid, analyze, content="unique", name=None):
    monkeypatch.setitem(X.EXPERIMENTS, name or "fake-" + aid, {"acquire": fake_acquire(content), "analyze": analyze})


def run1(home, monkeypatch, cfg, cid="t1", overrides=None, adapters=None):
    monkeypatch.setattr(C, "discovery_cfg", lambda: cfg)
    C.init(home, cid, brains=["water-temp"], budget_overrides=overrides)
    C.run(home, cid, adapters=adapters or {}, fetcher=D.OfflineFetcher())
    st = C.Campaign(home, cid).load()
    return st, st["tracks"]["water-temp"], L.Ledger(os.path.join(home, "water-temperature", "research", "gap-ledger.json"), "water-temp")


# ------------------------------------------------------------------------------------------------------------------------------- overnight failures
def test_fish_with_open_gaps_never_reports_no_weak_areas_and_runs_every_avenue(home):
    """Overnight: Fish had three open gaps and the follow-up said 'no weak areas' after one GBIF record-count check."""
    C.init(home, "f1", brains=["biological-state"])
    C.run(home, "f1", adapters={}, fetcher=D.OfflineFetcher())
    st = C.Campaign(home, "f1").load()["tracks"]["biological-state"]
    fol = st["stages"]["followup"]["result"]
    assert "no weak areas" not in json.dumps(fol)
    out = st["outcome"]
    assert out["outcome"] in ("STALLED", "BLOCKED") and out["improvementCampaignSuccessful"] is False
    assert out["avenuesRun"] >= 3 and "no new evidence" in out["reason"] and out["untriedAvenues"]    # offline: stall rule stops it, and says what was left untried
    assert set(out["gaps"]) >= {"FISH-VAL-001", "FISH-EVI-001", "FISH-PRD-001"}
    assert not [g for g, s in out["gaps"].items() if s == "RESOLVED_PENDING_APPROVAL"]  # nothing resolved by acquisition
    rep = json.load(open(os.path.join(home, "shared", "campaigns", "f1", "report.json")))
    assert rep["researchComplete"] is False and rep["improvementCampaignsSuccessful"] == 0 and rep["executionComplete"] is True
    assert "NOT research complete" in open(os.path.join(home, "shared", "campaigns", "f1", "REPORT.md")).read()


def test_a_validated_dataset_without_capability_gain_is_not_resolved_research(home, monkeypatch):
    register(monkeypatch, "data", fake_analyze(tier="QUALITY_CHECKED"))
    st, t, led = run1(home, monkeypatch, cfg_for([av("data")]))
    assert t["outcome"]["outcome"] == "STALLED" and not t["outcome"]["improvementCampaignSuccessful"]
    assert led.doc["gaps"]["G-A"]["status"] in ("INVESTIGATING", "EXHAUSTED")           # never PARTIAL/RESOLVED on data quality alone
    cand = st["tracks"]["water-temp"]["stages"]["candidate"]["result"]
    assert cand["lifecycle"] == "EVIDENCE_ONLY" and cand["scientificChanges"] == 0
    text = open(os.path.join(home, cand["path"], "SCIENTIFIC_DIFFERENCE.md")).read()
    assert "None." in text and "does not improve this Brain" in text


def test_tiers_are_not_interchangeable(home):
    ev = os.path.join(home, "e.txt")
    open(ev, "w").write("e")
    sha = D.sha256(ev)
    base = {"id": "F", "claim": "c", "kind": "RULE", "evidence": [{"path": "e.txt", "sha256": sha}], "validation": {"metric": "m", "op": ">=", "threshold": 1}}
    M = {"m": 5}
    assert C.validate_finding({**base, "tier": "EVIDENCE_LEAD"}, home, M)[0] == "VALIDATED"           # a lead can be a true lead...
    led = L.Ledger(os.path.join(home, "l.json"), "b")
    led.sync([{"id": "G", "title": "t"}])
    led.touch(["G"], "EVIDENCE_LEAD", "F", True, True)                                               # ...but it never moves a gap beyond INVESTIGATING
    led.touch(["G"], "QUALITY_CHECKED", "F", True, True)
    assert led.status("G") == "INVESTIGATING"
    v, why, _ = C.validate_finding({**base, "tier": "INDEPENDENTLY_VALIDATED"}, home, M)
    assert v == "REJECTED" and "capability test" in why                                              # independent validation needs a capability test
    v, why, _ = C.validate_finding({**base, "tier": "CANDIDATE_CHANGE", "change": {"scientificChange": "x"}}, home, M)
    assert v == "REJECTED" and "must document the change" in why                                     # an undocumented 'change' is not a candidate


def test_marginal_improvement_resolves_its_gap_but_research_continues(home, monkeypatch):
    register(monkeypatch, "imp", fake_analyze(tier="INDEPENDENTLY_VALIDATED", good=True))
    register(monkeypatch, "other", fake_analyze(tier="SCIENTIFIC_SUPPORT"))
    st, t, led = run1(home, monkeypatch, cfg_for([av("imp", resolves=["G-A"]), av("other", gaps=("G-B",))]))
    assert led.doc["gaps"]["G-A"]["status"] == "RESOLVED_PENDING_APPROVAL"
    assert led.doc["gaps"]["G-B"]["status"] in ("PARTIAL", "EXHAUSTED")
    assert any(k.startswith("other:") for k in led.doc["avenues"])                                   # the improvement did not terminate the investigation
    assert t["outcome"]["outcome"] == "IMPROVED" and t["outcome"]["improvements"] == ["imp"]
    cand = st["tracks"]["water-temp"]["stages"]["candidate"]["result"]
    assert cand["lifecycle"] == "CANDIDATE" and cand["improvements"] == ["IMP"]
    assert st["tracks"]["water-temp"]["stages"]["score"]["result"]["authoritativeUnchanged"] is True  # candidate only: authoritative scores never moved


def test_failed_hypothesis_is_rejected_and_preserved_and_the_next_rung_runs(home, monkeypatch):
    register(monkeypatch, "r1", fake_analyze(tier="INDEPENDENTLY_VALIDATED", good=False))
    register(monkeypatch, "r2", fake_analyze(tier="INDEPENDENTLY_VALIDATED", good=True))
    register(monkeypatch, "r3", fake_analyze(tier="INDEPENDENTLY_VALIDATED", good=True))
    st, t, led = run1(home, monkeypatch, cfg_for([av("r1", ladder="h", resolves=["G-A"]), av("r2", ladder="h", resolves=["G-A"]), av("r3", ladder="h", resolves=["G-A"])]))
    cand = os.path.join(home, st["tracks"]["water-temp"]["stages"]["candidate"]["result"]["path"])
    rej = json.load(open(os.path.join(cand, "rejected-hypotheses.json")))["hypotheses"]
    assert [h["id"] for h in rej] == ["R1"] and "capability test failed" in rej[0]["rejectedBecause"]   # numbers kept
    ch = json.load(open(os.path.join(cand, "candidate-changes.json")))["changes"]
    assert [c["id"] for c in ch] == ["R2"] and ch[0]["measured"]["improved"] and ch[0]["measured"]["delta"] == 1.0
    assert not any(k.startswith("r3:") for k in led.doc["avenues"])                                  # the ladder stopped at the first measured improvement


def test_a_blocked_evaluator_is_recorded_and_alternate_investigation_still_runs(home, monkeypatch, tmp_path):
    blocked = tmp_path / "blocked.py"
    blocked.write_text("import json,sys\nprint(json.dumps({'rc': 2, 'blocked': 'external input missing'}))\nsys.exit(2)\n")
    register(monkeypatch, "alt", fake_analyze(tier="SCIENTIFIC_SUPPORT"))
    st, t, led = run1(home, monkeypatch, cfg_for([av("alt")]), adapters={"water-temp": {"research": {"cmd": ["{python}", str(blocked)]}}})
    assert st["tracks"]["water-temp"]["stages"]["research"]["result"]["adapterBlocked"] == "external input missing"
    assert any(k.startswith("alt:") for k in led.doc["avenues"]) and led.doc["gaps"]["G-A"]["status"] in ("PARTIAL", "EXHAUSTED")


def test_missing_inputs_are_a_recorded_limitation_not_a_failed_track(home, monkeypatch):
    def broken(home, spec, mine, allacq, upstream=None):
        open(os.path.join(home, "does-not-exist.csv"))
    register(monkeypatch, "broken", broken)
    register(monkeypatch, "after", fake_analyze(tier="SCIENTIFIC_SUPPORT"))
    st, t, led = run1(home, monkeypatch, cfg_for([av("broken"), av("after", gaps=("G-B",))]))
    assert all(s["status"] == "DONE" for s in t["stages"].values())
    assert led.doc["gaps"]["G-A"]["status"] == "BLOCKED_EXTERNAL"                                    # the missing input became a blocker with a next source
    assert "restore or reconstruct" in led.doc["gaps"]["G-A"]["blockers"][0]["nextEvidenceSource"]
    assert any(k.startswith("after:") for k in led.doc["avenues"])                                   # the Brain continued with other independent work


def test_repeated_unsuccessful_searches_stop_as_stalled_and_never_repeat(home, monkeypatch):
    for i in range(6):
        register(monkeypatch, f"s{i}", fake_analyze(tier="QUALITY_CHECKED", fail=True), content="same evidence")
    avs = [av(f"s{i}", acquiring=True) for i in range(6)]
    st, t, led = run1(home, monkeypatch, cfg_for(avs, budget={"stallAvenues": 3}))
    ran = [k for k, v in led.doc["avenues"].items() if v["campaign"] == "t1"]
    assert len(ran) == 4 and len(set(ran)) == 4                                                      # 1 new + 3 with no new evidence, then stop; no key twice
    assert t["outcome"]["outcome"] == "STALLED" and "no new evidence" in t["outcome"]["reason"]
    C.init(home, "t2", brains=["water-temp"])                                                        # a later campaign may look again; unchanged evidence stops it as fast
    C.run(home, "t2", adapters={}, fetcher=D.OfflineFetcher())
    led2 = L.Ledger(os.path.join(home, "water-temperature", "research", "gap-ledger.json"), "water-temp")
    assert len([1 for v in led2.doc["avenues"].values() if v["campaign"] == "t2"]) <= 4


def test_research_budget_is_respected_and_reported_as_budget_reached(home, monkeypatch):
    for i in range(5):
        register(monkeypatch, f"b{i}", fake_analyze(tier="SCIENTIFIC_SUPPORT"))
    st, t, led = run1(home, monkeypatch, cfg_for([av(f"b{i}") for i in range(5)], budget={"maxAvenues": 2}))
    assert t["outcome"]["outcome"] == "BUDGET_REACHED" and t["outcome"]["avenuesRun"] == 2
    assert not any(k.startswith("b2:") for k in led.doc["avenues"])                                  # untried avenues remain actionable, not 'exhausted'
    assert led.doc["gaps"]["G-A"]["status"] != "EXHAUSTED"
    for i in range(5):
        register(monkeypatch, f"w{i}", fake_analyze(tier="SCIENTIFIC_SUPPORT"))
    st, t, led = run1(home, monkeypatch, cfg_for([av(f"w{i}") for i in range(5)]), cid="t3", overrides={"wallSeconds": -1})
    assert t["outcome"]["outcome"] == "BUDGET_REACHED" and t["outcome"]["avenuesRun"] == 1           # the window had already closed


def test_owner_action_records_are_written_and_the_gap_is_blocked_with_the_exact_source(home, monkeypatch):
    acts = [{"id": "field-data", "gap": "G-A", "publisher": "State agency", "dataset": "creel records", "access": "request from the agency", "verified": False, "addresses": "G-A"}]
    cfg = cfg_for([{"id": "needs", "run": "experiment", "experiment": "owner-actions", "gaps": ["G-A"], "params": {"actions": acts}}])
    st, t, led = run1(home, monkeypatch, cfg)
    rec = json.load(open(os.path.join(home, "water-temperature", "research", "data-acquisition", "field-data.json")))
    assert rec["status"] == "OWNER_ACTION_REQUIRED" and rec["accessVerified"] is False and rec["publisher"] == "State agency"
    assert led.doc["gaps"]["G-A"]["status"] == "BLOCKED_EXTERNAL"
    assert "State agency" in led.doc["gaps"]["G-A"]["blockers"][0]["nextEvidenceSource"]
    assert t["outcome"]["nextEvidenceSources"]


def test_all_eight_brains_use_the_ledger_outcome_model_and_none_claims_success_without_evidence(home):
    C.init(home, "e8")
    fin = C.run(home, "e8", adapters={}, fetcher=D.OfflineFetcher())
    assert fin == {b: "DONE" for b in C.BRAINS}
    st = C.Campaign(home, "e8").load()
    for bid, t in st["tracks"].items():
        assert t["outcome"]["outcome"] in L.OUTCOMES and t["outcome"]["outcome"] != "IMPROVED", bid
        assert os.path.exists(os.path.join(home, C.DEFAULT_FOLDERS[bid], "research", "gap-ledger.json")), bid
        assert t["outcome"]["avenuesRun"] >= 1, bid
    rep = json.load(open(os.path.join(home, "shared", "campaigns", "e8", "report.json")))
    assert rep["improvementCampaignsSuccessful"] == 0 and not rep["researchComplete"] and rep["executionComplete"]


def test_a_campaign_killed_mid_investigation_resumes_without_repeating_avenues(home):
    C.init(home, "k1", brains=["biological-state"])
    ad = os.path.join(home, "ad.json")
    json.dump({"adapters": {}}, open(ad, "w"))
    env = dict(os.environ, CAMPAIGN_CRASH_AT="biological-state:followup")
    p = subprocess.run([PY, C.__file__, "run", "--campaign", "k1", "--home", home, "--adapters", ad, "--offline"], env=env, capture_output=True, text=True)
    assert p.returncode == 137
    env.pop("CAMPAIGN_CRASH_AT")
    p = subprocess.run([PY, C.__file__, "run", "--campaign", "k1", "--home", home, "--adapters", ad, "--offline"], env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    led = L.Ledger(os.path.join(home, "fish-brain", "research", "gap-ledger.json"), "biological-state")
    keys = [k for k, v in led.doc["avenues"].items() if v["campaign"] == "k1"]
    assert len(keys) == len(set(keys)) >= 3                                                           # each avenue at most once; the killed follow-up was redone, not skipped
    ev = [json.loads(l) for l in open(os.path.join(home, "shared", "campaigns", "k1", "events.jsonl"))]
    fu = [e for e in ev if e["event"] == "stage-start" and e["stage"] == "followup"]
    assert len(fu) == len(keys) + 1                                                                   # one follow-up per avenue + the single re-run after the kill


# ------------------------------------------------------------------------------------------------------------------------------- Water Temp hypothesis
def _wt_world(home, noise_only=False):
    """Synthetic fleet: 6 lakes with a seasonal M0 bias (or none), 3 of them with an independent USGS sensor carrying the same bias."""
    off = {"DJF": 0.5, "MAM": -1.0, "JJA": -0.3, "SON": 0.7}
    vm = os.path.join(home, "water-temperature", "validation", "valmodel")
    os.makedirs(os.path.join(vm, "forcing"), exist_ok=True)
    with gzip.open(os.path.join(vm, "residuals_primary.csv.gz"), "wt") as fh:
        w = csv.writer(fh)
        w.writerow(["lake", "date", "m0", "e", "year", "season", "region", "cls"])
        for li in range(6):
            for year in range(2015, 2025):
                for mo in range(1, 13):
                    s = X.season_of(mo)
                    e = (0.4 if (year + mo + li) % 2 else -0.4) if noise_only else off[s] + (0.05 if (mo + li) % 2 else -0.05)
                    w.writerow([f"L{li}|XX", f"{year}-{mo:02d}-15", "10.0", f"{e:.3f}", year, s, "Southeast" if li % 2 else "Midwest", "STORAGE|MODERATE"])
    days = [(dt.date(2022, 11, 1) + dt.timedelta(days=i)).isoformat() for i in range(0, 520)]
    daily = {"time": days, "temperature_2m_mean": [12 + 10 * ((i % 365) / 365) for i in range(len(days))], "shortwave_radiation_sum": [None] * len(days),
             "wind_speed_10m_mean": [None] * len(days), "relative_humidity_2m_mean": [None] * len(days)}
    matched = {}
    for li in range(3):
        key = f"L{li}_XX"
        fp = f"water-temperature/validation/valmodel/forcing/{key}.json"
        json.dump({"latitude": 35, "longitude": -86, "daily": daily}, open(os.path.join(home, fp), "w"))
        forc = D.m0_daily(daily)
        vals = []
        for d in days[60:480]:
            m0 = D.m0_for_date(forc, d)
            if m0 is not None:
                vals.append({"value": f"{m0 - (0 if noise_only else off[X.season_of(int(d[5:7]))]):.4f}", "qualifiers": ["A"], "dateTime": d + "T00:00:00.000"})
        sp = f"water-temperature/sources/t/{key}_sensor.json"
        os.makedirs(os.path.dirname(os.path.join(home, sp)), exist_ok=True)
        json.dump({"value": {"timeSeries": [{"name": "USGS:1:00010:00003", "values": [{"method": [{"methodDescription": ""}], "value": vals}]}]}}, open(os.path.join(home, sp), "w"))
        matched[key] = {"lake": key, "forcing": fp, "sites": [{"site": "1", "path": sp, "siteName": "s"}]}
    return [{"matched": matched}]


def _wt_spec(rung):
    spec = dict(C.discovery_cfg()["brains"]["water-temp"]["avenues"][2]["params"])
    spec.update({"rung": rung, "avenueId": "wt-test", "minDays": 60})
    return spec


def test_water_temp_bias_hypothesis_is_accepted_only_on_independent_gain(home):
    acq = _wt_world(home)
    r = X.analyze_wt_bias(home, _wt_spec("season"), [], acq)
    m = r["metrics"]
    assert m["holdoutDeltaRmse"] > 0.3 and m["sensorDeltaRmse"] > 0.3 and m["sensorLakes"] == 3
    v, why, measured = C.validate_finding(r["findings"][0], home, {"discovery": {"exp": {"wt-test": m}}})
    assert v == "VALIDATED" and measured["improved"] and measured["candidate"] < measured["baseline"], why


def test_water_temp_bias_hypothesis_is_rejected_when_there_is_no_real_bias(home):
    acq = _wt_world(home, noise_only=True)
    r = X.analyze_wt_bias(home, _wt_spec("season"), [], acq)
    v, why, _ = C.validate_finding(r["findings"][0], home, {"discovery": {"exp": {"wt-test": r["metrics"]}}})
    assert v == "REJECTED" and ("fails" in why or "failed" in why)                                    # nothing to correct: no fabricated gain


# ------------------------------------------------------------------------------------------------------------------------------- sources, reuse, safety
def test_fetcher_refuses_hosts_outside_the_allowlist():
    f = D.Fetcher()
    for bad in ("https://example.com/x", "http://waterservices.usgs.gov/nwis/dv/", "https://firebaseio.com/x", "file:///etc/passwd"):
        with pytest.raises(D.FetchError):
            f.url(bad)
    assert f.url("https://api.gbif.org/v1/occurrence/search", {"limit": 0}).startswith("https://api.gbif.org/")


def test_new_sources_need_explicit_registration_with_licence_and_rationale(home):
    f = D.Fetcher(home=home)
    with pytest.raises(D.FetchError):
        f.url("https://data.example.org/x")                                                          # not registered: refused
    for bad in (["10.0.0.1"], ["foo.firebaseio.com"], ["x.run.app"], ["localhost"], ["not a host"]):
        with pytest.raises(ValueError):
            D.register_source(home, "bad", bad, "CC0", "p", "r", probe=False)
    with pytest.raises(ValueError):
        D.register_source(home, "nolic", ["data.example.org"], "", "p", "r", probe=False)
    rec = D.register_source(home, "ex", ["data.example.org"], "CC0", "test data", "needed for gap G", probe=False)
    assert rec["status"] == "ACTIVE" and rec["registeredBy"]
    assert D.Fetcher(home=home).url("https://data.example.org/x").startswith("https://data.example.org")
    with pytest.raises(D.FetchError):
        D.Fetcher().url("https://data.example.org/x")                                                # other research homes are unaffected
    assert "cwms-data.usace.army.mil" in D.allowed_hosts(None)                                       # reviewed registry entries are part of the floor


def test_evidence_already_collected_is_reused_not_downloaded_again(home):
    class Src(D.Fetcher):
        def __init__(self):
            super().__init__(gap=0, home=home)
            self.n = 0

        def get(self, base, params=None, accept=None):
            self.n += 1
            return b"payload"
    s1 = Src()
    e1 = D.Evidence(home, "water-temperature", "ca", s1)
    r1 = e1.fetch("c", "a.json", "https://api.gbif.org/v1/x", {"q": 1})
    e1.save()
    s2 = Src()
    e2 = D.Evidence(home, "water-temperature", "cb", s2)
    r2 = e2.fetch("c", "a.json", "https://api.gbif.org/v1/x", {"q": 1})
    assert s1.n == 1 and s2.n == 0 and r1 != r2
    assert open(os.path.join(home, r2), "rb").read() == b"payload" and e2.prov["files"][r2]["reusedFrom"] == r1


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


def test_findings_are_rejected_when_the_offline_re_run_does_not_reproduce_the_metrics(home, monkeypatch):
    register(monkeypatch, "d", fake_analyze(tier="SCIENTIFIC_SUPPORT"))
    orig, calls = C.run_analysis, []

    def drifting(c, st, bid):
        out = orig(c, st, bid)
        calls.append(1)
        if out and len(calls) > 1:
            out["metrics"]["exp"]["d"]["v"] = 99
        return out
    monkeypatch.setattr(C, "run_analysis", drifting)
    st, t, led = run1(home, monkeypatch, cfg_for([av("d")], budget={"maxAvenues": 1}))
    v = t["stages"]["validate"]["result"]
    assert v["discoveryReproducible"] is False
    assert v["results"] and all(r["verdict"] == "REJECTED" and "not produced" in r["reason"] for r in v["results"])


def test_tampered_evidence_is_rejected_at_validation(home, monkeypatch):
    register(monkeypatch, "tm", fake_analyze(tier="SCIENTIFIC_SUPPORT"))
    orig = C.STAGE_FN["validate"]

    def tamper(c, st, bid, ad, timeout):
        for root, _, files in os.walk(os.path.join(home, "water-temperature", "sources")):
            for f in files:
                if f.endswith(".txt"):
                    open(os.path.join(root, f), "a").write(" ")
        return orig(c, st, bid, ad, timeout)
    monkeypatch.setitem(C.STAGE_FN, "validate", tamper)
    st, t, led = run1(home, monkeypatch, cfg_for([av("tm")], budget={"maxAvenues": 1}))
    r = t["stages"]["validate"]["result"]["results"]
    assert r and all(x["verdict"] == "REJECTED" and "sha256 mismatch" in x["reason"] for x in r)


def test_read_only_sources_folder_is_never_modified(home):
    src = os.path.join(home, "water-temperature", "sources")
    os.makedirs(os.path.join(src, "protected"))
    os.chmod(src, 0o555)
    try:
        ev = D.Evidence(home, "water-temperature", "ro1", D.OfflineFetcher())
        assert ev.base == os.path.join("research", "discovery-sources")
        assert sorted(os.listdir(src)) == ["protected"] and (os.stat(src).st_mode & 0o777) == 0o555
    finally:
        os.chmod(src, 0o755)


def test_retry_failed_resumes_only_failed_stages_without_re_acquiring(home, monkeypatch):
    register(monkeypatch, "rf", fake_analyze(tier="SCIENTIFIC_SUPPORT"))
    cfg = cfg_for([av("rf")], budget={"maxAvenues": 1})
    monkeypatch.setattr(C, "discovery_cfg", lambda: cfg)
    C.init(home, "w6", brains=["water-temp"])
    bad = {"water-temp": {"validate": {"cmd": ["{python}", "-c", "import sys; sys.exit(1)"]}}}
    assert C.run(home, "w6", adapters=bad, fetcher=D.OfflineFetcher()) == {"water-temp": "FAILED"}
    assert C.run(home, "w6", adapters={}, fetcher=D.OfflineFetcher()) == {"water-temp": "FAILED"}        # without --retry-failed nothing is re-opened
    assert C.run(home, "w6", adapters={}, fetcher=D.OfflineFetcher(), retry_failed=True) == {"water-temp": "DONE"}
    sg = C.Campaign(home, "w6").load()["tracks"]["water-temp"]["stages"]
    assert sg["validate"]["retriedAfterFailure"] and sg["acquire"]["attempts"] == 1


def test_gaps_blocked_in_an_earlier_campaign_do_not_prevent_their_avenues_from_running_again(home, monkeypatch):
    """Regression (found in the first corrected live run): a gap blocked externally last time made every avenue serving it ineligible forever, so
    Clarity/Depth/Vegetation stopped after 0-1 avenues with others untried. A new campaign re-tests external blocks; only approval blocks persist."""
    acts = [{"id": "need", "gap": "G-A", "publisher": "P", "dataset": "d", "access": "a", "verified": False, "addresses": "x"}]
    cfg = cfg_for([{"id": "needs", "run": "experiment", "experiment": "owner-actions", "gaps": ["G-A"], "params": {"actions": acts}}])
    run1(home, monkeypatch, cfg, cid="b1")
    st, t, led = run1(home, monkeypatch, cfg, cid="b2")
    assert any(k.startswith("needs:") and v["campaign"] == "b2" for k, v in led.doc["avenues"].items())
    assert led.doc["gaps"]["G-A"]["status"] == "BLOCKED_EXTERNAL"                                    # re-recorded, not forgotten
    led.block("G-B", "approval", "needs owner", "owner", "b2")
    assert L.next_avenue([av("z", gaps=("G-B",))], led, [], set(), "b2") is None                    # an approval block does stop avenues that serve only it
