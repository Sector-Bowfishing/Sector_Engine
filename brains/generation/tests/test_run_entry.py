"""run.py is Generation's only publish entry. Knowledge comes only from the verified release; an unapproved release is never published from
(BLOCKED_AWAITING_APPROVED_RELEASE), a missing or tampered one refuses the run, the Brain has no executor, and nothing here needs the network."""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(HERE, "runtime")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FIXTURES = os.path.join(HERE, "tests", "fixtures", "hand-built")
OFFLINE = {"BRAIN_RTDB_URL": "http://127.0.0.1:9", "PATH": "/usr/bin:/bin", "PYTHONPATH": os.path.join(REPO, "jobs", "brain_platform"),
           "HTTPS_PROXY": "http://127.0.0.1:9", "HTTP_PROXY": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "http_proxy": "http://127.0.0.1:9"}


def run(*args, env=None, runtime=RUNTIME, cwd=None):
    return subprocess.run([sys.executable, os.path.join(runtime, "run.py"), *args], capture_output=True, text=True,
                          env={**OFFLINE, **(env or {})}, timeout=120, cwd=cwd)


def _copy(tmp_path):
    d = tmp_path / "runtime"
    shutil.copytree(RUNTIME, d, ignore=shutil.ignore_patterns("__pycache__"))
    return d


def test_write_is_blocked_while_the_release_is_unapproved_even_with_operator_intent(tmp_path):
    r = run("--write", env={"GENERATION_WRITE_APPROVED": "1"}, cwd=str(tmp_path))
    assert r.returncode == 2 and "REFUSED (nothing published)" in r.stderr and "BLOCKED_AWAITING_APPROVED_RELEASE" in r.stderr


def test_plan_reports_blocked_without_touching_the_network(tmp_path):
    r = run("--plan", cwd=str(tmp_path))
    v = json.loads(r.stdout)
    assert r.returncode == 0 and v["action"] == "SKIP" and v["status"] == "BLOCKED_AWAITING_APPROVED_RELEASE"
    assert v["knowledgeRelease"]["approvalStatus"] == "NOT_RECORDED" and v["knowledgeRelease"]["releaseDigest"].startswith("sha256:")


def test_dry_run_needs_explicit_intent_and_runs_offline_on_fixtures(tmp_path):
    r = run("--dry-run", cwd=str(tmp_path))
    assert r.returncode == 2 and "BLOCKED_AWAITING_APPROVED_RELEASE" in r.stderr
    r = run("--dry-run", "--allow-unapproved-release", "--fixtures", FIXTURES, "--lake", "Guntersville|AL", cwd=str(tmp_path))
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["published"] is False and out["evaluated"] == 1 and out["knowledgeRelease"]["approvalStatus"] == "NOT_RECORDED"


def test_a_missing_release_refuses_the_run(tmp_path):
    d = _copy(tmp_path)
    os.remove(d / "knowledge" / "knowledge-release.json")
    r = run("--plan", runtime=str(d), cwd=str(tmp_path))
    assert r.returncode == 2 and "REFUSED" in r.stderr and "manifest missing" in r.stderr


def test_a_tampered_release_refuses_the_run(tmp_path):
    d = _copy(tmp_path)
    p = d / "knowledge" / "source_access.json"
    p.write_text(p.read_text().replace('"ACCESS_CHECK_REQUIRED"', '"ALLOWED"'))       # flipping an access status outside a release
    r = run("--plan", runtime=str(d), cwd=str(tmp_path))
    assert r.returncode == 2 and "fails verification" in r.stderr


def test_generation_is_registered_disabled():
    """Declared, not grepped from orchestrator source: the control manifest gives Generation no execution target and no schedule."""
    m = json.load(open(os.path.join(REPO, "jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")))
    g = m["brains"]["generation"]
    assert g["executionTarget"]["kind"] == "none" and g["executionTarget"]["startedByOrchestrator"] is False
    assert g["activityState"] == "PARKED" and g["schedule"]["class"] == "MANUAL" and g["customerPublication"] is False
    assert not any(j.get("brainId") == "generation" for j in m["jobs"].values())
