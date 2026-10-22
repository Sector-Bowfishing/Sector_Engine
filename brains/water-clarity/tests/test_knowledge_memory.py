"""Approved memory (Cortex 2.1 BR-10, BR-11, BR-18): Water Clarity's packaged knowledge release (the public catalog) is verified on load, loads in a
clean environment with no research workspace and no HOME, and a missing or tampered release refuses the run (nothing is built or published). The
optional private overlay is detail only and degrades explicitly (PRIVATE_OVERLAY_UNAVAILABLE); it is never a substitute for the release."""
import json
import os
import shutil
import subprocess
import sys

import clarity_support as S

RUNTIME = os.path.join(S.REPO, "brains", "water-clarity", "runtime")
PLATFORM = os.path.join(S.REPO, "jobs", "brain_platform")
RID = "water-clarity-knowledge-2026-10-20.1"


def test_the_packaged_release_verifies_and_reaches_the_artifact_lineage():
    r = S.cb.RELEASE
    assert (r["releaseId"], r["store"], r["files"]) == (RID, "PACKAGED_IN_IMAGE", ["catalog.json"])
    lin = S.pa.release_lineage()
    assert lin == {"knowledge_release": RID, "manifest_ref": "image:knowledge-release.json", "manifest_sha256": r["releaseDigest"]}


def _clean_env():
    return {"PATH": "/usr/bin:/bin", "PYTHONPATH": PLATFORM}            # no HOME, no research root, no private overlay, cwd outside the repo


def test_clean_environment_load_without_home_research_workspace_or_repo_cwd(tmp_path):
    code = f"import sys; sys.path.insert(0, {RUNTIME!r}); import clarity_brain as cb; print(cb.RELEASE['releaseId'], cb.CATALOG_DETAIL)"
    out = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), env=_clean_env(), capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == [RID, "PUBLIC_ONLY"]


def _copy(tmp_path):
    d = tmp_path / "runtime"
    shutil.copytree(RUNTIME, d, ignore=shutil.ignore_patterns("__pycache__", "catalog.private.json"))
    return d


def _run(d, tmp_path):
    return subprocess.run([sys.executable, str(d / "run.py"), "--dry-run"], cwd=str(tmp_path), env=_clean_env(), capture_output=True, text=True, timeout=60)


def test_a_missing_release_refuses_the_run(tmp_path):
    d = _copy(tmp_path)
    os.remove(d / "knowledge-release.json")
    out = _run(d, tmp_path)
    assert out.returncode == 2 and "REFUSED (nothing published)" in out.stderr and "manifest missing" in out.stderr


def test_a_tampered_catalog_refuses_the_run_and_is_never_used(tmp_path):
    d = _copy(tmp_path)
    cat = json.loads((d / "catalog.json").read_text())
    cat["brainVersion"] = cat["brainVersion"] + "-edited"
    (d / "catalog.json").write_text(json.dumps(cat))
    out = _run(d, tmp_path)
    assert out.returncode == 2 and "REFUSED (nothing published)" in out.stderr and "fails verification" in out.stderr
