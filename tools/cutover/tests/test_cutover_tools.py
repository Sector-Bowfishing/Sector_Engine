"""Cutover B3/B4 tools: the capture is GET-only and private; the fake refuses writes; the comparison ignores only registered volatile keys."""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import fake_rtdb as F          # noqa: E402
import lake_rehearsal as R     # noqa: E402
import rtdb_capture as C       # noqa: E402


def test_capture_refuses_a_folder_inside_a_git_checkout(monkeypatch):
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "t")
    assert C.main(["--brain", "lake-brain", "--out", os.path.join(HERE, "nope")], fetch=lambda *a: {}) == 2
    assert not os.path.exists(os.path.join(HERE, "nope"))


def test_capture_needs_a_token(monkeypatch, tmp_path):
    monkeypatch.delenv("BRAIN_ACCESS_TOKEN", raising=False)
    assert C.main(["--brain", "lake-brain", "--out", str(tmp_path / "c")], fetch=lambda *a: {}) == 2


def test_capture_gets_every_lake_path_and_records_a_digest(monkeypatch, tmp_path):
    monkeypatch.setenv("BRAIN_ACCESS_TOKEN", "t")
    monkeypatch.setattr(C, "inside_git", lambda p: False)
    seen = []
    assert C.main(["--brain", "lake-brain", "--out", str(tmp_path / "c")], fetch=lambda url, p, tok: seen.append(p) or {"x": 1}) == 0
    m = json.load(open(tmp_path / "c" / "MANIFEST.json"))
    assert seen == m["paths"] and "lakes/Guntersville_AL" in seen and "brains/lake-brain" in seen and len(m["sha256"]) == 64
    assert C.main(["--brain", "lake-brain", "--out", str(tmp_path / "c")], fetch=lambda *a: {}) == 2      # never overwritten


def test_fake_serves_gets_and_refuses_writes():
    cap = {"lakes/A_X": {"states": {"lake": {"levelFt": 1}}}, "brains/lake-brain": {"health": "HEALTHY"}}
    with F.FakeRTDB(cap) as f:
        get = lambda p, q="": json.loads(urllib.request.urlopen(f"{f.url}/{p}.json{q}").read())
        assert get("lakes/A_X/states/lake/levelFt") == 1 and get("brains/lake-brain", "?shallow=true") == {"health": True}
        assert get("lakes/B_Y") is None
        req = urllib.request.Request(f"{f.url}/lakes/A_X.json", data=b"{}", method="PATCH")
        try:
            urllib.request.urlopen(req)
            raise AssertionError("write accepted")
        except urllib.error.HTTPError as e:
            assert e.code == 405
    assert f.refused and "lakes/B_Y" in f.uncovered and "lakes/A_X/states/lake/levelFt" not in f.uncovered


def test_compare_ignores_only_volatile_keys():
    cap = {"lakes/A_X/states/lake": {"levelFt": 1, "updatedAt": "t0"}, "brains/lake-brain/health": "HEALTHY"}
    art = {"sections": [{"mutations": [
        {"path": "/lakes/A_X/states/lake", "op": "set", "value": {"levelFt": 1, "updatedAt": "t1"}},
        {"path": "/brains/lake-brain/health", "op": "set", "value": "HEALTHY"}]}]}
    out = R.compare(art, cap, keys=frozenset({"updatedAt"}))
    assert (out["equal"], out["volatileOnly"], out["verdict"]) == (1, 1, "ZERO_UNEXPLAINED")
    art["sections"][0]["mutations"][0]["value"]["levelFt"] = 2
    art["sections"][0]["mutations"].append({"path": "/lakes/B_Y/brain", "op": "set", "value": {}})
    out = R.compare(art, cap, keys=frozenset({"updatedAt"}))
    assert out["different"] == ["/lakes/A_X/states/lake"] and out["notInCapture"] == ["/lakes/B_Y/brain"] and out["verdict"] == "DIFFERENCES_TO_EXPLAIN"


def test_rehearsal_refuses_a_bucket_archive(tmp_path):
    (tmp_path / "cap").mkdir(); (tmp_path / "cap" / "capture.json").write_text("{}")
    assert R.main(["--capture", str(tmp_path / "cap"), "--job", "x", "--out", str(tmp_path / "o"), "--archive", "gs://b"]) == 2
