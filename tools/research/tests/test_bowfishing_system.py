"""Charters, cross-Brain integration with ABSTAIN, the capability measurement, agent research tasks for uncovered gaps, and ninth-Brain onboarding."""
import datetime as dt
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import campaign as C  # noqa: E402
import bowfishing_capability as K  # noqa: E402
import integration as I  # noqa: E402
import onboard as O  # noqa: E402

D, L = C.D, C.L
ENGINE = C.ENGINE
NOW = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.timezone.utc)


# ------------------------------------------------------------------------------------------------------------------------------- charters + contract
def test_every_registered_brain_has_a_charter_with_a_bowfishing_purpose():
    ids = {json.load(open(p))["brainId"] for p in __import__("glob").glob(os.path.join(ENGINE, "brains", "*", "brain.json")) if "_template" not in p}
    ch = I.charters(ENGINE)
    assert ids <= set(ch), f"Brains without CHARTER.json: {sorted(ids - set(ch))}"
    for bid, c in ch.items():
        assert c["bowfishingPurpose"] and c["decisionsInformed"] and c["predicts"] and c["fitForPurpose"] and c["abstainWhen"], bid
        assert "UNFILLED" not in json.dumps(c), f"{bid}: charter has unfilled fields"
        assert all(x["status"] for x in c["predicts"])


def test_charter_dependencies_are_symmetric_and_no_new_undeclared_edge_appears():
    g = I.contract_gaps(ENGINE)
    assert g["asymmetric"] == []
    rec = set(json.load(open(os.path.join(ENGINE, "tools", "research", "integration_contract_gaps.json")))["undeclaredInBrainJson"])
    assert set(g["undeclaredInBrainJson"]) <= rec, f"new undeclared dependency: {sorted(set(g['undeclaredInBrainJson']) - rec)} - declare it in brain.json consumes"


# ------------------------------------------------------------------------------------------------------------------------------- integration with ABSTAIN
READY = {"brains": {"water-temp": {"capabilities": [{"id": "modeledSurfaceTempWithFleetErrorBound", "class": "VALIDATED_FOR_INTERNAL_TEST"}]},
                    "wind": {"capabilities": [{"id": "observation", "class": "EXPERIMENTAL"}, {"id": "strongWindNightForecast", "class": "ABSTAIN", "reason": "no skill"}]}}}


def nodes(age_h=1.0):
    t = lambda h: (NOW - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    return {"lake": {"currentElevationFt": 593.9, "observationTime": t(age_h)}, "waterTemp": {"currentTempF": 50.0, "provenance": {"generatedAt": t(age_h)}},
            "wind": {"observation": {"sustainedMph": 4.0, "observedAt": t(0.5)}, "gustMph": 9.0, "forecast": {"initTime": t(2)}},
            "waterClarity": {"clarityFt": 4.0, "generatedAt": t(age_h), "satellite": {"observedAt": t(15 * 24)}}}


def test_integration_shows_age_and_label_per_factor_and_never_combines_into_a_score():
    r = I.assess("Guntersville_AL", nodes(), NOW, READY)
    f = {(x["brain"], x["factor"]): x for x in r["factors"]}
    assert f[("lake-brain", "observedPoolElevation")]["status"] == "FRESH" and f[("water-temp", "modeledSurfaceTemp")]["capabilityClass"] == "VALIDATED_FOR_INTERNAL_TEST"
    assert f[("water-temp", "modeledSurfaceTemp")]["uncertainty"]["value"] == 2.3 and f[("water-temp", "modeledSurfaceTemp")]["value"] == 10.0
    assert f[("wind", "strongWindNight")]["status"] == "ABSTAIN" and "value" not in f[("wind", "strongWindNight")]                       # abstain is never a number
    assert f[("depth", "allDepthOutputs")]["status"] == "ABSTAIN" and f[("vegetation", "allVegetationOutputs")]["status"] == "ABSTAIN"
    assert f[("water-clarity", "satelliteEstimate")]["status"] == "ABSTAIN" and "value" not in f[("water-clarity", "satelliteEstimate")]
    assert r["overall"]["recommendation"] == "ABSTAIN" and "score" not in json.dumps(r).lower().replace("capability", "")
    assert r["mode"].startswith("INTERNAL")


def test_stale_and_missing_inputs_are_flagged_and_listed_as_limiting_not_filled_in():
    r = I.assess("L", nodes(age_h=30), NOW, READY)
    st = {(x["brain"], x["factor"]): x["status"] for x in r["factors"]}
    assert st[("lake-brain", "observedPoolElevation")] == "STALE" and st[("water-temp", "modeledSurfaceTemp")] == "STALE"
    assert "lake-brain:observedPoolElevation STALE" in r["overall"]["limitingFactors"]
    n = nodes()
    n["wind"] = None
    r = I.assess("L", n, NOW, READY)
    assert {(x["brain"], x["factor"]): x["status"] for x in r["factors"]}[("wind", "observation")] == "MISSING"


def test_only_supported_field_tested_rules_are_shown_and_contradicted_rules_are_withheld():
    spec = [{"ruleId": "LG-TMP-01", "species": "LNGR", "type": "thermal_cold", "expect": "cold_lt_warm", "claim": "longnose gar activity is lowest in cold water"},
            {"ruleId": "SC-TMP-01", "species": "SVCP", "type": "thermal_cold", "expect": "cold_not_lower", "claim": "silver carp stay active in cold water"},
            {"ruleId": "BF-MV-04", "species": "BWFN", "type": "thermal_cold", "expect": "cold_lt_warm", "claim": "bowfin fall below 10 C"},
            {"ruleId": "FD-MV-02", "species": "FWDM", "type": "diel", "expect": "night_gt_day", "claim": "drum feed at night"}]
    ft = {"LG-TMP-01": {"decisive": 1, "verdict": "SUPPORTED", "ratio": 0.48, "ciLo": 0.3, "ciHi": 0.7}, "SC-TMP-01": {"decisive": 1, "verdict": "CONTRADICTED", "ratio": 0.08, "ciLo": 0.03, "ciHi": 0.49},
          "BF-MV-04": {"decisive": 0, "verdict": "INCONCLUSIVE"}, "FD-MV-02": {"decisive": 1, "verdict": "SUPPORTED", "ratio": 4.0, "ciLo": 3.3, "ciHi": 4.8}}
    cold = I.assess("L", nodes(), NOW, READY, field_tests=ft, spec_tests=spec, fp={"coldC": 15.0})                         # 50 F = 10 C: cold
    shown = {x["ruleId"] for x in cold["speciesNotes"]["shown"]}
    assert shown == {"LG-TMP-01", "FD-MV-02"} and [x["ruleId"] for x in cold["speciesNotes"]["withheld"]] == ["SC-TMP-01"]   # inconclusive is neither shown nor withheld
    n = nodes()
    n["waterTemp"]["currentTempF"] = 75.0
    warm = I.assess("L", n, NOW, READY, field_tests=ft, spec_tests=spec, fp={"coldC": 15.0})
    assert {x["ruleId"] for x in warm["speciesNotes"]["shown"]} == {"FD-MV-02"}                                            # the cold rule does not apply at 24 C
    stale = I.assess("L", nodes(age_h=30), NOW, READY, field_tests=ft, spec_tests=spec, fp={"coldC": 15.0})
    assert "LG-TMP-01" not in {x["ruleId"] for x in stale["speciesNotes"]["shown"]}                                         # no temperature note from a stale temperature


def test_seasonal_calm_night_prior_is_attached_with_its_definition():
    r = I.assess("L", nodes(), NOW, READY, wind_climatology={"HSV": {"10": 0.71}}, month=10, station="HSV")
    assert r["seasonalPrior"]["probabilityOfCalmNight"] == 0.71 and "over-land proxy" in r["seasonalPrior"]["basis"]


# ------------------------------------------------------------------------------------------------------------------------------- agent tasks, onboarding
@pytest.fixture
def home(tmp_path):
    for bid, folder in C.DEFAULT_FOLDERS.items():
        d = tmp_path / folder
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps({"brainId": bid, "items": []}))
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "manifest.json").write_text("{}")
    return str(tmp_path)


def test_a_gap_no_avenue_covers_gets_an_agent_research_task_not_an_exhausted_label(home, monkeypatch):
    cfg = {"budget": {"wallSeconds": 3600, "maxAvenues": 10, "stallAvenues": 3},
           "brains": {"water-temp": {"weaknesses": [{"id": "G-NOCONNECTOR", "title": "something no connector knows about"}], "avenues": []}}}
    monkeypatch.setattr(C.D, "load_gaps", lambda *a, **k: {"source": "test", "reconstructed": False, "gaps": []})
    monkeypatch.setattr(C, "discovery_cfg", lambda: cfg)
    C.init(home, "a1", brains=["water-temp"])
    C.run(home, "a1", adapters={}, fetcher=D.OfflineFetcher())
    led = L.Ledger(os.path.join(home, "water-temperature", "research", "gap-ledger.json"), "water-temp")
    assert led.doc["gaps"]["G-NOCONNECTOR"]["status"] != "EXHAUSTED"
    t = json.load(open(os.path.join(home, "water-temperature", "research", "agent-tasks", "G-NOCONNECTOR.json")))
    assert t["status"] == "OPEN" and t["gapId"] == "G-NOCONNECTOR" and any("search the open web" in x for x in t["how"]) and "treat a missing connector as no evidence" in t["mustNot"]
    out = C.Campaign(home, "a1").load()["tracks"]["water-temp"]["outcome"]
    assert any("queued agent research" in n for n in out["nextEvidenceSources"])
    import taskqueue as TQ
    q = TQ.load(home)["tasks"]
    assert len(q) == 1 and q[0]["kind"] == "agent-research" and q[0]["status"] == "QUEUED" and q[0]["gap"] == "G-NOCONNECTOR"        # executable work, not just a file


def test_a_ninth_brain_is_onboarded_with_one_command_and_runs_through_the_coordinator(home, tmp_path, monkeypatch):
    eng = tmp_path / "engine"
    (eng / "brains" / "ninth").mkdir(parents=True)
    json.dump({"brainId": "ninth-brain", "consumes": []}, open(eng / "brains" / "ninth" / "brain.json", "w"))
    disc = tmp_path / "discovery.json"
    shutil.copy(os.path.join(ENGINE, "tools", "research", "discovery.json"), disc)
    with pytest.raises(ValueError):
        O.add_brain(str(tmp_path / "engine"), "x", "missing-dir", "x", "d")                                             # must be registered first
    r = O.add_brain(str(eng), "ninth-brain", "ninth", "ninth-brain", "where bowfish hold during runoff events", home=home, consumes=["lake-brain"], provides=["sector-intelligence"], discovery_path=str(disc))
    assert any("GAPS.json" in x for x in r["created"]) and any("CHARTER.json" in x for x in r["created"]) and (eng / "brains" / "ninth" / "research" / "GAPS.json").exists()
    ch = json.load(open(eng / "brains" / "ninth" / "research" / "CHARTER.json"))
    assert ch["status"] == "SKELETON_UNFILLED" and "UNFILLED" in json.dumps(ch)                                       # an unfilled charter is visible, never silently accepted
    assert os.path.exists(os.path.join(home, "ninth-brain", "manifest.json")) and os.path.isdir(os.path.join(home, "ninth-brain", "candidates"))
    d = json.load(open(disc))["brains"]["ninth-brain"]
    assert d["folder"] == "ninth-brain" and {a["experiment"] if a["run"] == "experiment" else a["kind"] for a in d["avenues"]} == {"literature", "dataset-search"}
    assert O.add_brain(str(eng), "ninth-brain", "ninth", "ninth-brain", "d", discovery_path=str(disc))["created"] == []   # idempotent
    # the coordinator takes it up: simulate the registry load, then run offline
    monkeypatch.setitem(C.DEFAULT_FOLDERS, "ninth-brain", "ninth-brain")
    monkeypatch.setattr(C, "BRAINS", C.BRAINS + ("ninth-brain",))
    monkeypatch.setitem(C.BRAIN_DIRS, "ninth-brain", "ninth")
    monkeypatch.setattr(C, "discovery_cfg", lambda: json.load(open(disc)))
    C.init(home, "n9", brains=["ninth-brain"])
    assert C.run(home, "n9", adapters={}, fetcher=D.OfflineFetcher()) == {"ninth-brain": "DONE"}
    t = C.Campaign(home, "n9").load()["tracks"]["ninth-brain"]
    assert t["outcome"]["outcome"] in ("STALLED", "BLOCKED") and t["outcome"]["nextEvidenceSources"]


# ------------------------------------------------------------------------------------------------------------------------------- capability contract
def _cap_home(tmp_path):
    h = tmp_path / "home"
    for _, folder in K.FOLDERS.items():
        (h / folder / "research").mkdir(parents=True)
    wt = h / "water-temperature"
    (wt / "candidates" / "c1").mkdir(parents=True)
    json.dump({"metrics": {"discovery": {"pooledEqualLakeRmseC": 2.5, "lakesValidated": 4, "exp": {"wt-interval-season": {"nominal": 0.8, "lakes": {"a": {"covBase": 0.6, "covCand": 0.8}, "b": {"covBase": 0.85, "covCand": 0.8}},
               "sensorDeltaIs": 0.3}}}}}, open(wt / "candidates" / "c1" / "validation.json", "w"))
    json.dump({"gaps": {"G": {"bestTier": "SCIENTIFIC_SUPPORT"}}}, open(wt / "research" / "gap-ledger.json", "w"))
    fz = h / "water-temperature" / "validation" / "valmodel" / "forcing"
    fz.mkdir(parents=True)
    for i in range(10):
        (fz / f"L{i}.json").write_text("{}")
    json.dump({"metrics": {"pooled_equalLake_rmse_C": 2.4}}, open(wt / "validation" / "w1.json", "w"))
    os.makedirs(wt / "validation" / "campaign-2026-10-22")
    shutil.copy(wt / "validation" / "w1.json", wt / "validation" / "campaign-2026-10-22" / "wt_w1_reproduction.json")
    return str(h)


def test_capability_is_computed_from_evidence_with_unmeasured_dimensions_and_separate_candidate(tmp_path):
    h = _cap_home(tmp_path)
    rep = K.compute(ENGINE, h, "c1", readiness_path=os.path.join(h, "none.json"))
    wt = next(b for b in rep["brains"] if b["brainId"] == "water-temp")
    d = wt["current"]["dimensions"]
    assert d["predictionFitness"]["status"] == "MEASURED" and d["predictionFitness"]["value"] == round(2.0 / 2.5, 4)       # target 2.0 C vs worse of 2.4 / 2.5
    assert d["coverage"]["value"] == 0.4 and d["validationDepth"]["value"] == 0.4
    assert d["uncertaintyHandling"]["value"] == 0.5 and wt["candidate"]["dimensions"]["uncertaintyHandling"]["value"] == 1.0 and wt["candidate"]["dimensions"]["uncertaintyHandling"]["validated"] is False
    assert d["practicalAvailability"]["status"] == "UNMEASURED"                                                          # no readiness record: not zero, not typed
    wind = next(b for b in rep["brains"] if b["brainId"] == "wind")
    assert wind["current"]["dimensions"]["predictionFitness"]["status"] == "UNMEASURED" and wind["current"]["measuredWeight"] < 0.5
    assert "not an engineering score" in rep["separation"].lower() and all(b["current"]["value"] is None or 0 <= b["current"]["value"] <= 1 for b in rep["brains"])


def test_practical_availability_is_computed_from_the_readiness_classes_and_candidates_do_not_count_as_current(tmp_path):
    h = _cap_home(tmp_path)
    rp = os.path.join(h, "ready.json")
    json.dump({"brains": {"wind": {"capabilities": [{"id": "a", "class": "VALIDATED_FOR_INTERNAL_TEST"}, {"id": "b", "class": "ABSTAIN"},
                                                    {"id": "c", "class": "VALIDATED_FOR_INTERNAL_TEST", "deployed": False}]}}}, open(rp, "w"))
    wind = next(b for b in K.compute(ENGINE, h, "c1", readiness_path=rp)["brains"] if b["brainId"] == "wind")
    assert wind["current"]["dimensions"]["practicalAvailability"]["value"] == 0.5                       # (1.0 + 0.0) / 2 deployed capabilities
    assert wind["candidate"]["dimensions"]["practicalAvailability"]["value"] == round(2 / 3, 4)          # the validated candidate counts only in the candidate column


# ------------------------------------------------------------------------------------------------------------------------------- V1 scenarios + outcomes
def _run_scenario(sc):
    n = nodes(age_h=sc["ageHours"])
    n["waterTemp"]["currentTempF"] = sc["tempF"]
    if sc.get("windMph"):
        n["wind"]["observation"]["sustainedMph"] = sc["windMph"]
    if sc.get("dropNode"):
        n[sc["dropNode"]] = None
    spec = [{"ruleId": "LG-TMP-01", "species": "LNGR", "type": "thermal_cold", "expect": "cold_lt_warm", "claim": "longnose gar activity is lowest in cold water"},
            {"ruleId": "SC-TMP-01", "species": "SVCP", "type": "thermal_cold", "expect": "cold_not_lower", "claim": "silver carp stay active in cold water"}]
    ft = {"LG-TMP-01": {"decisive": 1, "verdict": "SUPPORTED", "ratio": 0.48, "ciLo": 0.3, "ciHi": 0.7}, "SC-TMP-01": {"decisive": 1, "verdict": "CONTRADICTED", "ratio": 0.08, "ciLo": 0.03, "ciHi": 0.49}}
    return I.assess("Guntersville_AL", n, NOW, READY, field_tests=ft, spec_tests=spec, fp={"coldC": 15.0})


def test_every_v1_internal_scenario_passes_its_pre_declared_expectations():
    sc = json.load(open(os.path.join(ENGINE, "tools", "research", "scenarios", "v1_internal.json")))["scenarios"]
    assert len(sc) >= 8
    for s in sc:
        r = _run_scenario(s)
        f = {f"{x['brain']}:{x['factor']}": x for x in r["factors"]}
        e = s["expect"]
        for k in e.get("fresh", []):
            assert f[k]["status"] == "FRESH", (s["id"], k)
        for k in e.get("stale", []):
            assert f[k]["status"] == "STALE", (s["id"], k)
        for k in e.get("abstain", []):
            assert f[k]["status"] == "ABSTAIN", (s["id"], k)
        for k in e.get("missing", []):
            assert f[k]["status"] == "MISSING", (s["id"], k)
        for k in e.get("noValueFor", []):
            assert "value" not in f[k], (s["id"], k)
        for k in e.get("limiting", []):
            assert k in r["overall"]["limitingFactors"], (s["id"], k)
        shown = {x["ruleId"]: x for x in r["speciesNotes"]["shown"]}
        assert set(e.get("notes", [])) <= set(shown), (s["id"], shown)
        assert not (set(e.get("noNotes", [])) & set(shown)), (s["id"], shown)
        assert set(e.get("withheld", [])) <= {x["ruleId"] for x in r["speciesNotes"]["withheld"]}, s["id"]
        for k in e.get("borderline", []):
            assert shown[k]["borderline"] is True and 0.5 <= shown[k]["applicabilityProbability"] < 0.8, (s["id"], shown[k])
        if e.get("noSpeciesTempNotes"):
            assert shown == {}, s["id"]
        if "recommendation" in e:
            assert r["overall"]["recommendation"] == e["recommendation"]


def test_outcomes_are_recorded_append_only_and_compared_with_what_the_app_showed(tmp_path):
    import outcomes as O2
    h = str(tmp_path)
    snap = tmp_path / "a.json"
    snap.write_text(json.dumps(I.assess("Guntersville_AL", nodes(), NOW, READY, wind_climatology={"HSV": {"10": 0.7}}, month=10, station="HSV")))
    O2.record(h, "Guntersville_AL", "2026-11-02T21:30", "tester", {"surfaceTempC": 11.0, "calmNight": True, "clarityFt": 3.0}, str(snap))
    O2.record(h, "Guntersville_AL", "2026-11-03T21:30", "tester", {"surfaceTempC": 9.0, "calmNight": False}, str(snap))
    with pytest.raises(ValueError):
        O2.record(h, "Guntersville_AL", "2026-11-04", "tester", {"unknownField": 1})
    ev = O2.evaluate(h, "Guntersville_AL")
    assert ev["records"] == 2 and ev["tempComparisons"] == 2 and ev["tempBiasC"] == -0.0 + round(((10.0 - 11.0) + (10.0 - 9.0)) / 2, 3)
    assert ev["calmComparisons"] == 2 and 0 <= ev["calmBrier"] <= 1 and "changes no score" in ev["note"]
    assert len(open(os.path.join(h, "shared", "pilot", "outcomes", "Guntersville_AL.jsonl")).readlines()) == 2
