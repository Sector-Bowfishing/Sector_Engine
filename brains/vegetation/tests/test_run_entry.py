"""run.py is Vegetation's only run entry. Knowledge comes only from the verified release; an unapproved release is never published from (there is no
live writer at all), a missing or tampered release refuses the run, and nothing here needs the network."""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(HERE, "runtime")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OFFLINE = {"PATH": "/usr/bin:/bin", "PYTHONPATH": os.path.join(REPO, "jobs", "brain_platform")}


def run(*args, runtime=RUNTIME, cwd=None):
    return subprocess.run([sys.executable, os.path.join(runtime, "run.py"), *args], capture_output=True, text=True, env=OFFLINE, timeout=120, cwd=cwd)


def test_plan_reports_blocked_while_the_release_is_unapproved(tmp_path):
    r = run("--plan", cwd=str(tmp_path))
    v = json.loads(r.stdout)
    assert r.returncode == 0 and v["status"] == "BLOCKED_AWAITING_APPROVED_RELEASE" and v["knowledgeRelease"]["approvalStatus"] == "NOT_RECORDED"


def test_dry_run_needs_explicit_intent_and_writes_only_a_local_file(tmp_path):
    out = tmp_path / "dry.json"
    r = run("--dry-run", str(out), cwd=str(tmp_path))
    assert r.returncode == 2 and "BLOCKED_AWAITING_APPROVED_RELEASE" in r.stderr and not out.exists()
    r = run("--dry-run", str(out), "--allow-unapproved-release", cwd=str(tmp_path))
    rep = json.loads(r.stdout)
    assert r.returncode == 0 and rep["published"] is False and out.exists()
    dumped = json.load(open(out))
    tree = dumped.get("tree", dumped)
    assert set(tree) >= {"brains", "lakes", "lakeFleet"} and set(tree["brains"]) == {"vegetation"}


def test_there_is_no_write_mode():
    r = subprocess.run([sys.executable, os.path.join(RUNTIME, "run.py"), "--write"], capture_output=True, text=True, env=OFFLINE, timeout=60)
    assert r.returncode == 2 and ("unrecognized arguments" in r.stderr or "one of the arguments" in r.stderr)


def _copy(tmp_path):
    d = tmp_path / "runtime"
    shutil.copytree(RUNTIME, d, ignore=shutil.ignore_patterns("__pycache__"))
    return d


def test_a_missing_release_refuses_the_run(tmp_path):
    d = _copy(tmp_path)
    os.remove(d / "knowledge" / "knowledge-release.json")
    r = run("--plan", runtime=str(d), cwd=str(tmp_path))
    assert r.returncode == 2 and "REFUSED" in r.stderr and "manifest missing" in r.stderr


def test_a_tampered_release_refuses_the_run(tmp_path):
    d = _copy(tmp_path)
    p = d / "knowledge" / "agency_sfwmd_okeechobee.json"
    p.write_text(p.read_text() + " ")
    r = run("--plan", runtime=str(d), cwd=str(tmp_path))
    assert r.returncode == 2 and "fails verification" in r.stderr


def test_vegetation_has_no_executor_and_no_schedule():
    m = json.load(open(os.path.join(REPO, "jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")))["brains"]["vegetation"]
    assert m["executionTarget"]["kind"] == "none" and m["schedule"]["class"] == "MANUAL" and m["customerPublication"] is False
