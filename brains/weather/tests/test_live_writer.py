"""The gated live writer (run.py --write; WEATHER_BRAIN_PLAN.md section 6.1). It refuses unless BOTH the knowledge release is APPROVED and
WEATHER_WRITE_APPROVED=1; with both, it writes exactly the dry run's write set, every path declared in brain.json (Cortex BR-13, FD-03).
Nothing here touches a network or a database: the live writer is replaced by an in-memory recorder with the same ownership checks."""
import importlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import pytest

from sector_brain_platform import declared_writes as D
from sector_weather import contract as C, knowledge as K, writer as WR
from sector_weather.client import PointCache
from sector_weather.publish import DRY_RUN_MODE, LIVE_MODE, run
from weather_support import LAKES, RECORDED_NOW, REPO, FixtureSource

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(HERE, "..", "runtime")
BRAIN_JSON = json.load(open(os.path.join(HERE, "..", "brain.json"), encoding="utf-8"))
OFFLINE = {"PATH": "/usr/bin:/bin", "PYTHONPATH": os.path.join(REPO, "jobs", "brain_platform"), "BRAIN_RTDB_URL": "http://127.0.0.1:9",
           "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9"}


def cli(*args, env=None, runtime=RUNTIME, cwd=None):
    return subprocess.run([sys.executable, os.path.join(runtime, "run.py"), *args], capture_output=True, text=True,
                          env={**OFFLINE, **(env or {})}, timeout=120, cwd=cwd)


def approved_copy(tmp_path):
    """A copy of the runtime whose release is marked APPROVED (approval is not part of the file digest): exercises the gate, never published."""
    d = tmp_path / "runtime"
    shutil.copytree(RUNTIME, d, ignore=shutil.ignore_patterns("__pycache__"))
    p = d / "knowledge" / "knowledge-release.json"
    m = json.loads(p.read_text())
    m["approval"] = {"status": "APPROVED", "record": "test-only approval record (never a real approval)"}
    p.write_text(json.dumps(m))
    return d


# ---------------------------------------------------------------------------------------------------------------- refusals
def test_the_release_is_not_approved_in_this_repository():
    assert C.RELEASE["approvalStatus"] == "NOT_RECORDED"                    # approvals are recorded by the owner, never by this change
    with pytest.raises(K.KnowledgeNotApproved):
        K.require_approved(C.RELEASE)


def test_write_refuses_without_an_approved_release_even_with_operator_intent(tmp_path):
    r = cli("--write", env={"WEATHER_WRITE_APPROVED": "1"}, cwd=str(tmp_path))
    assert r.returncode == 2 and "REFUSED (nothing published)" in r.stderr and K.BLOCKED in r.stderr and r.stdout == ""


def test_write_refuses_without_operator_intent_even_with_an_approved_release(tmp_path):
    d = approved_copy(tmp_path)
    for env in ({}, {"WEATHER_WRITE_APPROVED": "0"}, {"WEATHER_WRITE_APPROVED": "yes"}):
        r = cli("--write", env=env, runtime=str(d), cwd=str(tmp_path))
        assert r.returncode == 3 and "WEATHER_WRITE_APPROVED=1" in r.stderr and r.stdout == ""


@pytest.mark.parametrize("opt", [["--lakes", "Guntersville|AL"], ["--limit", "2"], ["--now", "2026-11-06T20:51:00Z"],
                                 ["--published", "x.json"], ["--directory", "x.json"]])
def test_dry_run_inputs_never_feed_a_live_write(tmp_path, opt):
    d = approved_copy(tmp_path)
    r = cli("--write", *opt, env={"WEATHER_WRITE_APPROVED": "1"}, runtime=str(d), cwd=str(tmp_path))
    assert r.returncode == 3 and "dry-run options" in r.stderr and r.stdout == ""


def test_the_live_client_refuses_an_app_database():
    with pytest.raises(WR.WriteError):
        WR.RtdbWriter("https://sector-9393c-default-rtdb.firebaseio.com")


# ---------------------------------------------------------------------------------------------------------------- the write set
class Recorder(WR.DryRunWriter):
    """Stands in for RtdbWriter: same ownership and key checks, in memory; remembers the URL it was given."""
    made = []

    def __init__(self, base_url, timeout=20.0):
        super().__init__()
        Recorder.made.append(base_url)


class _Src(FixtureSource):
    def __init__(self):
        super().__init__()
        self.http = type("H", (), {"requests": 0})()


class _Now(datetime):
    @classmethod
    def now(cls, tz=None):
        return RECORDED_NOW


def live(monkeypatch, published=None):
    """run.py main(['--write']) in-process with an APPROVED release, operator intent, fixture NWS and a recording writer."""
    import run as R
    R = importlib.reload(R)
    monkeypatch.setenv("WEATHER_WRITE_APPROVED", "1")
    monkeypatch.setattr(R.C, "RELEASE", {**C.RELEASE, "approvalStatus": "APPROVED", "approvalRecord": "test-only"})
    monkeypatch.setattr(WR, "RtdbWriter", Recorder)
    monkeypatch.setattr(R, "fetch_directory", lambda url: [dict(v) for v in LAKES.values()])
    monkeypatch.setattr(R, "LiveSource", _Src)
    monkeypatch.setattr(R, "datetime", _Now)
    Recorder.made.clear()
    tree = {}
    for lid, st in (published or {}).items():
        tree.setdefault("lakes", {}).setdefault(C.lake_key(lid), {}).setdefault("states", {})["weather"] = st
    real_init = Recorder.__init__
    monkeypatch.setattr(Recorder, "__init__", lambda self, url, timeout=20.0: (real_init(self, url), self._store.tree.update(tree)) and None)
    holder = {}
    real_patch = Recorder.patch
    monkeypatch.setattr(Recorder, "patch", lambda self, u: (holder.setdefault("w", self), real_patch(self, u)))
    rc = R.main(["--write"])
    return rc, holder.get("w")


def _flat(w):
    flat = {}
    for p in w.patches:
        flat.update(p)
    return flat


def test_the_live_write_set_equals_the_dry_run_and_is_fully_declared(monkeypatch, capsys):
    rc, w = live(monkeypatch)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["published"] is True and Recorder.made == [os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")]
    written = _flat(w)
    dry = run(list(LAKES.values()), FixtureSource(), PointCache(None), {}, RECORDED_NOW)["updates"]
    assert set(written) == set(dry)                                           # the live path adds and drops nothing
    assert written["brains/weather/publishMode"] == LIVE_MODE and dry["brains/weather/publishMode"] == DRY_RUN_MODE
    assert {k: v for k, v in written.items() if k != "brains/weather/publishMode"} == {k: v for k, v in dry.items() if k != "brains/weather/publishMode"}
    assert D.undeclared(BRAIN_JSON, written) == [] and D.unused_legacy(BRAIN_JSON, written) == [] and D.problems(BRAIN_JSON) == []


def test_the_live_planner_reads_the_published_states(monkeypatch, capsys):
    first = run(list(LAKES.values()), FixtureSource(), PointCache(None), {}, RECORDED_NOW)["states"]
    rc, w = live(monkeypatch, published=first)
    capsys.readouterr()
    written = _flat(w)
    assert rc == 0 and f"lakes/{C.lake_key('Champlain|VT')}/states/weather" not in written     # STEADY and not due: read back, not refetched


def test_a_run_with_no_due_lake_still_advances_last_successful_run():
    """Chosen behaviour (follow-up to #239): lastSuccessfulRun keeps its registry meaning and advances on a run that computed no lake, so
    Moon's DEPENDENCY_CHANGED fires after it too (the control-manifest fingerprint note says so; Moon then skips unchanged lakes)."""
    from sector_weather.publish import write_set
    u = write_set(list(LAKES.values()), {}, {lid: "CALIBRATION" for lid in LAKES}, [], RECORDED_NOW, computed=set())
    assert u["brains/weather/lastSuccessfulRun"] == C.iso(RECORDED_NOW)
    assert u["brains/weather/lastRunOutcome"]["computedLakeCount"] == 0 and u["brains/weather/lastRunOutcome"]["status"] == "SUCCESS"
    from sector_brain_platform import orchestration as O
    note = O.load_manifest()["brains"]["weather"]["fingerprint"]["note"]
    assert "lastSuccessfulRun" in O.load_manifest()["brains"]["weather"]["fingerprint"]["materialFields"] and "computedLakeCount 0" in note
