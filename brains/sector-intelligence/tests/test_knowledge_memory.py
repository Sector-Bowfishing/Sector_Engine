"""Approved memory (Cortex 2.1 BR-10, BR-11, BR-18): Sector Intelligence's packaged knowledge release (the hand-reviewed catalog) is verified on load,
loads in a clean environment with no research workspace and no HOME, and a missing or tampered release refuses the run (nothing is built or published)."""
import json
import os
import shutil
import subprocess
import sys

import pytest

import intelligence_support as S
import run

RUNTIME = os.path.join(S.REPO, "brains", "sector-intelligence", "runtime")
PLATFORM = os.path.join(S.REPO, "jobs", "brain_platform")


def test_the_packaged_release_verifies_and_matches_the_catalog_the_runtime_uses():
    release, cat, cat_sha = run.load_knowledge(RUNTIME)
    assert release["releaseId"] == "sector-intelligence-knowledge-2026-10-20.1" and release["files"] == ["catalog.json"]
    assert release["store"] == "PACKAGED_IN_IMAGE" and release["approvalStatus"] in ("APPROVED", "NOT_RECORDED")
    assert cat["catalogVersion"] and cat_sha


def test_clean_environment_load_without_home_research_workspace_or_repo_cwd(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": os.pathsep.join([RUNTIME, PLATFORM])}        # no HOME, no research root, cwd outside the repo
    code = "import run; r, c, s = run.load_knowledge(); print(r['releaseId'])"
    out = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "sector-intelligence-knowledge-2026-10-20.1"


def _copy(tmp_path):
    d = tmp_path / "runtime"
    shutil.copytree(RUNTIME, d, ignore=shutil.ignore_patterns("__pycache__", "out"))
    return d


def test_a_missing_release_refuses(tmp_path):
    d = _copy(tmp_path)
    os.remove(d / "knowledge-release.json")
    with pytest.raises(Exception, match="manifest missing"):
        run.load_knowledge(str(d))


def test_a_tampered_catalog_refuses_and_is_never_used(tmp_path):
    d = _copy(tmp_path)
    cat = json.loads((d / "catalog.json").read_text())
    cat["reviewNote"] = cat["reviewNote"] + " (edited outside a release)"
    (d / "catalog.json").write_text(json.dumps(cat))
    with pytest.raises(Exception, match="fails verification"):
        run.load_knowledge(str(d))


def test_the_job_entry_point_reports_a_refusal_not_a_crash(tmp_path):
    d = _copy(tmp_path)
    os.remove(d / "knowledge-release.json")
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": PLATFORM}
    out = subprocess.run([sys.executable, str(d / "run.py"), "--plan"], cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 2 and "REFUSED (nothing published)" in out.stderr
