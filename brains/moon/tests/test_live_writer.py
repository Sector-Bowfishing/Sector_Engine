"""The gated live writer (run.py --write; MOON_BRAIN_PLAN.md section 7.1). It refuses unless BOTH the knowledge release is APPROVED and
MOON_WRITE_APPROVED=1; with both, it reads each lake's Weather state from the Brain RTDB (only within the dependency's maxAgeHours) and writes
exactly the paths brain.json declares (Cortex BR-13, FD-03). No network, no database: the live writer is replaced by an in-memory recorder."""
import datetime as dt
import importlib
import json
import os
import shutil
import subprocess
import sys

import pytest

import moon_support as S
from moon_brain import lakes as L, writer as WR
from moon_brain.publish import LIVE_MODE
from sector_brain_platform import declared_writes as D, lake_key, orchestration as O

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(HERE, "..", "runtime")
BRAIN_JSON = json.load(open(os.path.join(HERE, "..", "brain.json"), encoding="utf-8"))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OFFLINE = {"PATH": "/usr/bin:/bin", "PYTHONPATH": os.path.join(REPO, "jobs", "brain_platform"), "BRAIN_RTDB_URL": "http://127.0.0.1:9",
           "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9"}
TWO = ("Guntersville|AL", "Lake Champlain|VT")


def cli(*args, env=None, runtime=RUNTIME, cwd=None):
    return subprocess.run([sys.executable, os.path.join(runtime, "run.py"), *args], capture_output=True, text=True,
                          env={**OFFLINE, **(env or {})}, timeout=300, cwd=cwd)


def approved_copy(tmp_path):
    d = tmp_path / "runtime"
    shutil.copytree(RUNTIME, d, ignore=shutil.ignore_patterns("__pycache__"))
    p = d / "knowledge" / "knowledge-release.json"
    m = json.loads(p.read_text())
    m["approval"] = {"status": "APPROVED", "record": "test-only approval record (never a real approval)"}
    p.write_text(json.dumps(m))
    return d


# ---------------------------------------------------------------------------------------------------------------- refusals
def test_the_release_is_not_approved_in_this_repository():
    d = L.load()
    assert d["release"]["approvalStatus"] == "NOT_RECORDED"
    with pytest.raises(L.KnowledgeNotApproved):
        L.require_approved(d)


def test_write_refuses_without_an_approved_release_even_with_operator_intent(tmp_path):
    r = cli("--write", env={"MOON_WRITE_APPROVED": "1"}, cwd=str(tmp_path))
    assert r.returncode == 2 and "REFUSED (nothing published)" in r.stderr and L.BLOCKED in r.stderr and r.stdout == ""


def test_write_refuses_without_operator_intent_even_with_an_approved_release(tmp_path):
    d = approved_copy(tmp_path)
    for env in ({}, {"MOON_WRITE_APPROVED": "0"}):
        r = cli("--write", env=env, runtime=str(d), cwd=str(tmp_path))
        assert r.returncode == 3 and "MOON_WRITE_APPROVED=1" in r.stderr and r.stdout == ""


@pytest.mark.parametrize("opt", [["--date", "2026-11-22"], ["--weather", "w.json"], ["--lakes", "Guntersville|AL"]])
def test_dry_run_inputs_never_feed_a_live_write(tmp_path, opt):
    d = approved_copy(tmp_path)
    r = cli("--write", *opt, env={"MOON_WRITE_APPROVED": "1"}, runtime=str(d), cwd=str(tmp_path))
    assert r.returncode == 3 and "dry-run options" in r.stderr and r.stdout == ""


def test_the_live_client_refuses_an_app_database():
    with pytest.raises(WR.WriteError):
        WR.RtdbWriter("https://sector-9393c-default-rtdb.firebaseio.com")


def test_the_weather_age_limit_is_the_manifest_dependency():
    import run as R
    edge = next(d for d in O.load_manifest()["brains"]["moon"]["dependencies"] if d["id"] == "weather")
    assert R.WEATHER_MAX_AGE_HOURS == edge["maxAgeHours"]


# ---------------------------------------------------------------------------------------------------------------- the write set
class Recorder(WR.DryRunWriter):
    seed: dict = {}
    last = None

    def __init__(self, base_url, timeout=20.0):
        super().__init__(json.loads(json.dumps(Recorder.seed)))
        Recorder.last = self


def live(monkeypatch, weather_at: dict):
    """run.py main(['--write']) in-process: APPROVED release (2 lakes), operator intent, Weather states seeded in the recorder's tree."""
    import run as R
    R = importlib.reload(R)
    real = L.load

    def approved_two():
        d = real()
        lakes = [r for r in d["lakes"] if r["lakeId"] in TWO]
        return {**d, "lakes": lakes, "count": len(lakes), "release": {**d["release"], "approvalStatus": "APPROVED"}}
    monkeypatch.setattr(R.L, "load", approved_two)
    monkeypatch.setenv("MOON_WRITE_APPROVED", "1")
    monkeypatch.setattr(WR, "RtdbWriter", Recorder)
    seed = {}
    for lid, at in weather_at.items():
        seed.setdefault("lakes", {}).setdefault(lake_key(lid), {})["states"] = {"weather": S.run_state(at, 100)}
    Recorder.seed = seed
    return R.main(["--write"])


def _iso(h):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=h)).replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_live_write_set_is_fully_declared_and_uses_only_recent_weather(monkeypatch, capsys):
    rc = live(monkeypatch, {"Guntersville|AL": _iso(1), "Lake Champlain|VT": _iso(6)})     # one fresh, one older than 3 h
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["published"] is True and out["weatherInput"] == {"used": 1, "absent": 0, "tooOld": 1, "noGeneratedAt": 0}
    written = {}
    for p in Recorder.last.patches:
        written.update(p)
    written = {k: v for k, v in written.items()}
    assert D.undeclared(BRAIN_JSON, written) == [] and D.unused_legacy(BRAIN_JSON, written) == [] and D.problems(BRAIN_JSON) == []
    assert written["brains/moon"]["publishMode"] == LIVE_MODE
    assert not any(k.endswith("/states/weather") for k in written)                     # Moon reads Weather, never writes it
    basis = {lid: written[f"lakes/{lake_key(lid)}/states/moon"]["darkness"]["basis"] for lid in TWO}
    assert basis["Lake Champlain|VT"] in ("MOON_ONLY", "NO_NIGHT")                           # the stale state was not used
