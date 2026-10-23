"""The research campaign harness on a disposable fixture research home: dependency order, validation gate, candidate packaging (approval never
set, never into the Engine), authoritative scores untouched, network/Firebase blocked for adapters, cleanup limited to campaign-owned files,
failure isolation, bounded retries, interruption + resume, and one consolidated report."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import campaign as C  # noqa: E402

PY = sys.executable


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Unit tests never reach the network: every discovery request fails (and must be recorded, not fatal)."""
    monkeypatch.setattr(C.D, "Fetcher", C.D.OfflineFetcher)


@pytest.fixture
def home(tmp_path):
    """A fixture research home: every Brain folder with a manifest, an evidence file, an UNRELATED pre-existing tmp file and an existing candidate."""
    for bid, folder in C.DEFAULT_FOLDERS.items():
        d = tmp_path / folder
        (d / "datasets").mkdir(parents=True)
        (d / "datasets" / "evidence.csv").write_text(f"lake,value\nA,{len(bid)}\n")
        (d / "analysis" / "tmp" / "someone-else").mkdir(parents=True)
        (d / "analysis" / "tmp" / "someone-else" / "keep.txt").write_text("not ours")
        (d / "candidates" / "older").mkdir(parents=True)
        (d / "candidates" / "older" / "x.json").write_text("{}")
        (d / "manifest.json").write_text(json.dumps({"brainId": bid, "folder": folder, "owner": bid, "manifestVersion": 1,
                                                     "items": [{"id": "evidence", "workspacePath": "datasets/evidence.csv", "retention": "ARCHIVAL"}]}))
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "manifest.json").write_text(json.dumps({"items": []}))
    return str(tmp_path)


def metric_script(tmp_path, value, name="m.py", extra=""):
    p = tmp_path / name
    p.write_text("import json,os,sys\n" + extra + f"\njson.dump({{'score': {value}, 'ok': 1}}, open(os.path.join(os.environ['CAMPAIGN_OUT'], 'metrics.json'), 'w'))\n")
    return str(p)


def findings(home, bid, good=True):
    folder = C.DEFAULT_FOLDERS[bid]
    ev = os.path.join(home, folder, "datasets", "evidence.csv")
    return {"schema": C.FINDINGS_SCHEMA, "brainId": bid, "findings": [
        {"id": "F-good", "claim": "metric above floor", "kind": "PARAMETER", "fixture": True,
         "evidence": [{"path": f"{folder}/datasets/evidence.csv", "sha256": sha(ev)}], "validation": {"metric": "score", "op": ">=", "threshold": 1}},
        {"id": "F-badsha", "claim": "tampered", "kind": "RULE", "fixture": True,
         "evidence": [{"path": f"{folder}/datasets/evidence.csv", "sha256": "0" * 64}], "validation": {"metric": "score", "op": ">=", "threshold": 1}},
        {"id": "F-fails", "claim": "metric too low", "kind": "PARAMETER", "fixture": True,
         "evidence": [{"path": f"{folder}/datasets/evidence.csv", "sha256": sha(ev)}], "validation": {"metric": "score", "op": ">=", "threshold": 99}},
    ][: 3 if good else 2]}


def adapters_for(script):
    a = {"validate": {"cmd": ["{python}", script]}, "score": {"cmd": ["{python}", script], "value": "score", "measure": "fixture"}}
    return {b: a for b in C.BRAINS}


def submit_all(home, cid):
    for bid in C.BRAINS:
        p = os.path.join(home, f"f-{bid}.json")
        json.dump(findings(home, bid), open(p, "w"))
        assert C.main(["submit", "--campaign", cid, "--home", home, "--brain", bid, "--findings", p]) == 0


def test_end_to_end_eight_tracks_validation_packaging_cleanup_and_report(home, tmp_path):
    C.init(home, "c1")
    submit_all(home, "c1")
    fin = C.run(home, "c1", parallel=3, adapters=adapters_for(metric_script(tmp_path, 5)))
    assert fin == {b: "DONE" for b in C.BRAINS}
    st = C.Campaign(home, "c1").load()
    rep = json.load(open(os.path.join(home, "shared", "campaigns", "c1", "report.json")))
    assert rep["complete"] and rep["authoritativeScoresUnchanged"] and len(rep["tracks"]) == 8
    for bid in C.BRAINS:
        folder = os.path.join(home, C.DEFAULT_FOLDERS[bid])
        v = st["tracks"][bid]["stages"]["validate"]["result"]
        expected = (2, 2) if bid == "sector-intelligence" else (1, 2)                # + Intelligence's upstream-integration finding
        assert (v["validated"], v["rejected"]) == expected, (bid, v["results"])   # bad sha + failed threshold rejected
        assert {r["id"]: r["verdict"] for r in v["results"] if not r["id"].startswith("INT-AUTO")} == {"F-good": "VALIDATED", "F-badsha": "REJECTED", "F-fails": "REJECTED"}
        cand = os.path.join(folder, "candidates", "c1")
        rel = C.K.load_release(cand, bid)
        assert rel["approvalStatus"] == "NOT_RECORDED"                                               # never approved
        assert [f["id"] for f in json.load(open(os.path.join(cand, "findings.json")))["findings"] if not f.get("auto")] == ["F-good"]
        assert not os.path.exists(os.path.join(folder, "analysis", "tmp", "c1"))                   # campaign workspace removed
        assert open(os.path.join(folder, "analysis", "tmp", "someone-else", "keep.txt")).read() == "not ours"   # unrelated tmp kept
        assert os.path.exists(os.path.join(folder, "candidates", "older", "x.json"))               # existing candidates kept
        m = json.load(open(os.path.join(folder, "manifest.json")))
        assert any(i["id"] == "c1:knowledge-release.json" and i["retention"] == "ACTIVE" and i["sha256"] for i in m["items"])
        assert m["items"][0]["id"] == "evidence"                                                   # existing items preserved
        co = st["tracks"][bid]["stages"]["cleanup"]["result"]["closeout"]
        text = open(os.path.join(home, co)).read()
        assert all(f"## {s}" in text for s in C.CLOSEOUT_SECTIONS)
        assert st["tracks"][bid]["stages"]["score"]["result"]["candidateScore"] == 5
    assert os.path.exists(os.path.join(home, "shared", "campaigns", "c1", "REPORT.md"))


def test_dependency_order_intelligence_after_specialists_and_depth_vegetation_after_lake(home, tmp_path):
    C.init(home, "c2")
    st = C.Campaign(home, "c2").load()
    assert set(st["tracks"]["sector-intelligence"]["dependsOn"]) == {"biological-state", "lake-brain", "water-clarity", "water-temp", "wind"}
    assert st["tracks"]["depth"]["dependsOn"] == ["lake-brain"] and st["tracks"]["vegetation"]["dependsOn"] == ["lake-brain"]
    C.run(home, "c2", parallel=4, adapters=adapters_for(metric_script(tmp_path, 1)))
    ev = [json.loads(line) for line in open(os.path.join(home, "shared", "campaigns", "c2", "events.jsonl"))]
    first = {e["brain"]: i for i, e in enumerate(ev) if e.get("event") == "stage-start" and e["stage"] == "discover"}
    last = {e["brain"]: i for i, e in enumerate(ev) if e.get("event") == "stage-end" and e["stage"] == "cleanup"}
    assert all(first["sector-intelligence"] > last[d] for d in ("biological-state", "lake-brain", "water-clarity", "water-temp", "wind"))
    assert first["depth"] > last["lake-brain"] and first["vegetation"] > last["lake-brain"]


def test_no_findings_means_no_candidate_and_nothing_is_invented(home, tmp_path):
    C.init(home, "c3", brains=["wind"])
    C.run(home, "c3", adapters=adapters_for(metric_script(tmp_path, 9)))
    st = C.Campaign(home, "c3").load()
    assert st["tracks"]["wind"]["stages"]["validate"]["result"]["findings"] == 0
    assert st["tracks"]["wind"]["stages"]["candidate"]["result"]["packaged"] is False
    assert not os.path.exists(os.path.join(home, "wind-brain", "candidates", "c3"))


def test_failure_is_isolated_and_retries_are_bounded(home, tmp_path):
    C.init(home, "c4", brains=["wind", "lake-brain"])
    submit_all_subset = {"wind", "lake-brain"}
    for bid in submit_all_subset:
        p = os.path.join(home, f"f-{bid}.json")
        json.dump(findings(home, bid), open(p, "w"))
        C.main(["submit", "--campaign", "c4", "--home", home, "--brain", bid, "--findings", p])
    good = {"validate": {"cmd": ["{python}", metric_script(tmp_path, 5)]}}
    bad = {"validate": {"cmd": ["{python}", "-c", "import sys; sys.exit(3)"]}}
    fin = C.run(home, "c4", adapters={"wind": bad, "lake-brain": good})
    st = C.Campaign(home, "c4").load()
    assert fin == {"wind": "FAILED", "lake-brain": "DONE"}
    assert st["tracks"]["wind"]["stages"]["validate"]["attempts"] == 2                              # maxAttempts
    assert st["tracks"]["wind"]["stages"]["candidate"]["status"] == "PENDING"                        # nothing downstream of a failure
    rep = json.load(open(os.path.join(home, "shared", "campaigns", "c4", "report.json")))
    assert not rep["complete"] and any("validate" in e for t in rep["tracks"] if t["brainId"] == "wind" for e in t["errors"])


def test_interruption_is_recovered_without_redoing_finished_work(home, tmp_path):
    C.init(home, "c5", brains=["wind", "water-temp"])
    for bid in ("wind", "water-temp"):
        p = os.path.join(home, f"f-{bid}.json")
        json.dump(findings(home, bid), open(p, "w"))
        C.main(["submit", "--campaign", "c5", "--home", home, "--brain", bid, "--findings", p])
    ad = os.path.join(tmp_path, "ad.json")
    json.dump({"adapters": adapters_for(metric_script(tmp_path, 5))}, open(ad, "w"))
    env = dict(os.environ, CAMPAIGN_CRASH_AT="wind:candidate")
    p = subprocess.run([PY, C.__file__, "run", "--campaign", "c5", "--home", home, "--adapters", ad, "--parallel", "1"], env=env,
                       capture_output=True, text=True)
    assert p.returncode == 137                                                                       # killed mid-campaign
    st = C.Campaign(home, "c5").load()
    assert st["tracks"]["wind"]["stages"]["validate"]["status"] == "DONE" and st["tracks"]["wind"]["stages"]["candidate"]["status"] == "RUNNING"
    v_attempts = st["tracks"]["wind"]["stages"]["validate"]["attempts"]
    env.pop("CAMPAIGN_CRASH_AT")
    p = subprocess.run([PY, C.__file__, "run", "--campaign", "c5", "--home", home, "--adapters", ad], env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    st = C.Campaign(home, "c5").load()
    assert all(s["status"] == "DONE" for t in st["tracks"].values() for s in t["stages"].values())
    assert st["tracks"]["wind"]["stages"]["validate"]["attempts"] == v_attempts                      # finished stage not re-run
    assert st["tracks"]["wind"]["stages"]["candidate"]["attempts"] == 2                              # interrupted stage re-run once
    C.K.load_release(os.path.join(home, "wind-brain", "candidates", "c5"), "wind")


def test_adapters_run_with_network_and_firebase_blocked(home, tmp_path):
    probe = metric_script(tmp_path, 1, "probe.py", extra=(
        "import urllib.request\nok=0\n"
        "try:\n urllib.request.urlopen(os.environ['BRAIN_RTDB_URL']+'/x.json', timeout=3)\nexcept Exception:\n ok=1\n"
        "assert ok and os.environ['BRAIN_TOKEN_MODE']=='disabled' and 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ\n"
        "assert os.environ['HTTPS_PROXY'].startswith('http://127.0.0.1:9')\n"))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/nonexistent/creds.json"
    try:
        C.init(home, "c6", brains=["wind"])
        p = os.path.join(home, "f.json")
        json.dump(findings(home, "wind"), open(p, "w"))
        C.main(["submit", "--campaign", "c6", "--home", home, "--brain", "wind", "--findings", p])
        assert C.run(home, "c6", adapters={"wind": {"validate": {"cmd": ["{python}", probe]}}}) == {"wind": "DONE"}
    finally:
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS")


def test_candidates_never_go_into_the_engine_and_cleanup_refuses_foreign_workspaces(home, tmp_path, monkeypatch):
    C.init(home, "c7", brains=["wind"])
    c = C.Campaign(home, "c7")
    st = c.load()
    monkeypatch.setattr(C, "ENGINE", home)                                                         # pretend the research home were the Engine
    ws = c.workspace(st, "wind")
    os.makedirs(ws)
    json.dump({"schema": C.FINDINGS_SCHEMA, "brainId": "wind", "findings": []}, open(os.path.join(ws, "findings.json"), "w"))
    json.dump({"results": [{"id": "F", "verdict": "VALIDATED"}]}, open(os.path.join(ws, "validation.json"), "w"))
    with pytest.raises(RuntimeError, match="never writes into the Engine"):
        C.stage_candidate(c, st, "wind", {}, 10)
    monkeypatch.undo()
    open(os.path.join(ws, C.OWNER_MARKER), "w").write(json.dumps({"campaignId": "another-campaign"}))
    with pytest.raises(RuntimeError, match="not owned"):
        C.stage_cleanup(c, st, "wind", {}, 10)
    assert os.path.exists(os.path.join(ws, "findings.json"))                                         # nothing deleted


def test_authoritative_score_change_fails_the_score_stage(home, tmp_path, monkeypatch):
    C.init(home, "c8", brains=["wind"])
    c = C.Campaign(home, "c8")
    st = c.load()
    st["authoritativeBefore"] = {"docs/brains/scoring/frozen-scores.json": "tampered"}
    with pytest.raises(RuntimeError, match="authoritative"):
        C.stage_score(c, st, "wind", {}, 10)


def test_submit_refuses_foreign_or_malformed_findings(home):
    C.init(home, "c9", brains=["wind"])
    p = os.path.join(home, "f.json")
    json.dump({"schema": C.FINDINGS_SCHEMA, "brainId": "depth", "findings": []}, open(p, "w"))
    assert C.main(["submit", "--campaign", "c9", "--home", home, "--brain", "wind", "--findings", p]) == 2
    with pytest.raises(SystemExit):
        C.init(home, "c9")                                                                          # a campaign is never silently re-created


def test_fixture_findings_are_used_only_by_a_verification_campaign(home, tmp_path):
    fx = tmp_path / "fx.json"
    fx.write_text(json.dumps(findings(home, "wind")))
    ad = {"wind": {"validate": {"cmd": ["{python}", metric_script(tmp_path, 5)]}, "fixtureFindings": str(fx)}}
    C.init(home, "real", brains=["wind"])
    C.run(home, "real", adapters=ad)
    assert C.Campaign(home, "real").load()["tracks"]["wind"]["stages"]["validate"]["result"]["findings"] == 0   # never injected
    C.init(home, "verify", brains=["wind"], verification=True)
    C.run(home, "verify", adapters=ad)
    assert C.Campaign(home, "verify").load()["tracks"]["wind"]["stages"]["validate"]["result"]["findings"] == 3


def test_cleanup_removes_read_only_campaign_files_but_nothing_else(home, tmp_path):
    """APFS clones keep the research home's permissions (some snapshots are write-protected): the campaign's own copy must still be removable."""
    C.init(home, "ro", brains=["wind"])
    c = C.Campaign(home, "ro")
    st = c.load()
    ws = c.workspace(st, "wind")
    os.makedirs(os.path.join(ws, "clone", "locked"))
    open(os.path.join(ws, C.OWNER_MARKER), "w").write(json.dumps({"campaignId": "ro"}))
    f = os.path.join(ws, "clone", "locked", "snapshot.json")
    open(f, "w").write("{}")
    os.chmod(f, 0o444)
    os.chmod(os.path.join(ws, "clone", "locked"), 0o555)
    outside = os.path.join(home, "wind-brain", "datasets", "evidence.csv")
    os.chmod(outside, 0o444)
    C.stage_cleanup(c, st, "wind", {}, 10)
    assert not os.path.exists(ws) and os.path.exists(outside) and not os.access(outside, os.W_OK)   # foreign permissions untouched


def test_brief_names_the_folder_dependencies_contract_and_validator_metrics(home, tmp_path):
    C.init(home, "b1", brains=["lake-brain", "depth"])
    p = os.path.join(home, "f.json")
    json.dump(findings(home, "depth"), open(p, "w"))
    C.main(["submit", "--campaign", "b1", "--home", home, "--brain", "depth", "--findings", p])
    C.run(home, "b1", adapters=adapters_for(metric_script(tmp_path, 4)))
    b = C.brief(home, "b1", "depth")
    assert os.path.join(home, "depth") in b and "lake-brain" in b and C.FINDINGS_SCHEMA in b
    assert "'ok'" in b or "ok" in b.split("produced in this campaign:")[1]                       # validator metrics listed
    assert "Never: write to Firebase" in b and "NOT_RECORDED" in b
