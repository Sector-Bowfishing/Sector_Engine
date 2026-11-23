"""artifact_entry.py: Weather's artifact mode for Sector Pulse `weather-central` (prepared, off). Recorded NWS fixtures, a fake live database:
no network, no credential, no database write."""
import json
import os
import subprocess
import sys

import artifact_entry as AE
import pytest
from sector_brain_platform import python_artifact_entry as E
from sector_weather import knowledge as K
from weather_support import HERE, LAKES, RECORDED_NOW, REPO, FixtureSource
import weather_cert_support as CS
from sector_weather.client import PointCache
from sector_weather.publish import run

EXEC_ID = "00000000-0000-4000-8000-000000000001"


class FakeLive:
    def __init__(self, tree=None):
        self.tree, self.calls = tree or {}, []

    def get(self, path, shallow=False):
        self.calls.append(path)
        return None


def _entry(tmp_path, monkeypatch, *, approved=True, intent="1", extra=()):
    if approved:
        monkeypatch.setattr(K, "require_approved", lambda rel: rel)
    if intent:
        monkeypatch.setenv("WEATHER_WRITE_APPROVED", intent)
    else:
        monkeypatch.delenv("WEATHER_WRITE_APPROVED", raising=False)
    monkeypatch.setenv("SECTOR_ENGINE_COMMIT", "test")
    live = FakeLive()
    argv = ["--execution-id", EXEC_ID, "--artifact-dir", str(tmp_path / "store"), "--emit", str(tmp_path / "artifact.json"), "--read-rtdb",
            "--point-cache", str(tmp_path / "data" / "nws-points.json"), *extra]
    rc = AE.main(argv, source=FixtureSource(), directory=[LAKES["Guntersville|AL"], LAKES["Champlain|VT"]],
                 live_factory=lambda url, b: E.LiveReadOnly(live), now=RECORDED_NOW)
    return rc, live


def test_the_hand_off_is_the_write_set_run_py_would_write(tmp_path, monkeypatch):
    rc, live = _entry(tmp_path, monkeypatch)
    assert rc == 0
    art = json.load(open(tmp_path / "artifact.json"))
    assert art["lineage"]["brainId"] == "weather" and art["lineage"]["knowledgeRelease"] == CS.LINEAGE[0]
    assert "lakes/Guntersville_AL/states/weather" in live.calls                    # previous state read from live, GET only
    assert (tmp_path / "data" / "nws-points.json").exists()                          # the durable /points cache was written to the data folder
    reference = run([LAKES["Guntersville|AL"], LAKES["Champlain|VT"]], FixtureSource(), PointCache(None), {}, RECORDED_NOW,
                    publish_mode=AE.CENTRAL_MODE)["updates"]
    sealed = AE.PA.build_artifact(reference, AE.PA.BuildContext("2026-11-06T20:51:00Z", EXEC_ID, "weather@test",
                                                                   lifecycle=AE.PA.LIFECYCLE), release_lineage=CS.LINEAGE).artifact
    assert sealed["sections"] == art["sections"]
    assert {k: v for k, v in sealed["lineage"].items() if k != "artifactId"} == {k: v for k, v in art["lineage"].items() if k != "artifactId"}


def test_the_gates_hold(tmp_path, monkeypatch):
    assert _entry(tmp_path, monkeypatch, approved=False)[0] == 2                    # the packaged release is not APPROVED
    assert _entry(tmp_path, monkeypatch, intent=None)[0] == 3
    assert not (tmp_path / "artifact.json").exists()


def test_the_cli_refuses_without_an_approved_release_and_without_the_user_agent(tmp_path):
    env = {**os.environ, "PYTHONPATH": os.path.join(REPO, "jobs", "brain_platform"), "WEATHER_WRITE_APPROVED": "1"}
    env.pop("SECTOR_WEATHER_USER_AGENT", None)
    r = subprocess.run([sys.executable, "artifact_entry.py", "--artifact-dir", str(tmp_path / "s"), "--emit", str(tmp_path / "a.json"), "--read-rtdb"],
                       cwd=os.path.join(HERE, "..", "runtime"), capture_output=True, text=True, env=env, timeout=120)
    assert r.returncode == 2 and "BLOCKED_AWAITING_APPROVED_RELEASE" in r.stderr and not (tmp_path / "s").exists()


def test_the_user_agent_contact_is_required_outside_tests(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(K, "require_approved", lambda rel: rel)
    monkeypatch.setenv("WEATHER_WRITE_APPROVED", "1")
    monkeypatch.delenv("SECTOR_WEATHER_USER_AGENT", raising=False)
    rc = AE.main(["--artifact-dir", str(tmp_path / "s")], live_factory=lambda u, b: None)
    assert rc == 2 and "SECTOR_WEATHER_USER_AGENT" in capsys.readouterr().err


def test_the_write_intent_name_is_run_py_s():
    assert AE.R.WRITE_INTENT_ENV == "WEATHER_WRITE_APPROVED"
