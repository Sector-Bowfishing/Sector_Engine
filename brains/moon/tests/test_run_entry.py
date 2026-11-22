"""run.py: plan says SKIP, --write refuses, --tonight writes a local file only."""
import json
import os
import subprocess
import sys

import moon_support as S

RUN = os.path.join(os.path.dirname(__file__), "..", "runtime", "run.py")


def _run(*args):
    return subprocess.run([sys.executable, RUN, *args], capture_output=True, text=True, timeout=300)


def test_plan_skips():
    r = _run("--plan")
    assert r.returncode == 0 and json.loads(r.stdout)["action"] == "SKIP"


def test_write_is_refused():
    r = _run("--write")
    assert r.returncode == 2 and "REFUSED" in r.stderr


def test_tonight_for_listed_lakes(tmp_path):
    out = tmp_path / "tonight.json"
    w = tmp_path / "w.json"
    w.write_text(json.dumps({"Guntersville|AL": S.run_state("2026-11-22T23:00:00Z", 100)}))
    r = _run("--tonight", str(out), "--date", "2026-11-22", "--lakes", "Guntersville|AL,Iliamna|AK", "--weather", str(w))
    assert r.returncode == 0, r.stderr
    doc = json.load(open(out))
    assert set(doc["lakes"]) == {"Guntersville|AL", "Iliamna|AK"} and json.loads(r.stdout)["published"] is False
    assert doc["lakes"]["Guntersville|AL"]["darkness"]["basis"] == "MOON_AND_CLOUD"
    assert doc["lakes"]["Iliamna|AK"]["darkness"]["basis"] == "MOON_ONLY"


def test_unknown_lake_is_refused(tmp_path):
    r = _run("--tonight", str(tmp_path / "x.json"), "--lakes", "Atlantis|ZZ")
    assert r.returncode == 2 and "not directory lakes" in r.stderr


def test_without_date_each_lake_gets_its_own_tonight(tmp_path):
    out = tmp_path / "t.json"
    r = _run("--tonight", str(out), "--lakes", "Guntersville|AL,Iliamna|AK")
    assert r.returncode == 0, r.stderr
    doc = json.load(open(out))
    assert doc["date"] == "PER_LAKE_CURRENT_NIGHT" and all(len(v["date"]) == 10 for v in doc["lakes"].values())
