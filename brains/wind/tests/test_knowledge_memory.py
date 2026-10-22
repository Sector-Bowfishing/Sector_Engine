"""Approved memory (Cortex 2.1 BR-10, BR-11, BR-18): Wind's packaged knowledge release (lakes.json + brain/validation_evidence.json) is verified on
load, loads in a clean environment with no research workspace and no HOME, and a missing or tampered release stops the run (nothing falls back)."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from sector_brain_platform.knowledge_release import KnowledgeReleaseError, lineage_triple
from sector_wind import ingest

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.abspath(os.path.join(HERE, "..", "runtime"))
PLATFORM = os.path.abspath(os.path.join(HERE, "..", "..", "..", "jobs", "brain_platform"))


def test_the_packaged_release_verifies_and_covers_every_runtime_knowledge_file():
    r = ingest.verified_release()
    assert r["releaseId"] == "wind-knowledge-2026-10-20.1" and r["store"] == "PACKAGED_IN_IMAGE"
    assert set(r["files"]) == {"lakes.json", "sector_wind/brain/validation_evidence.json"}
    assert lineage_triple(r)[2].startswith("sha256:") and ingest.load_config()


def test_clean_environment_load_without_home_research_workspace_or_repo_cwd(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": os.pathsep.join([RUNTIME, PLATFORM])}       # no HOME, no research root, cwd outside the repo
    code = "from sector_wind import ingest; ingest.load_config(); print(ingest.verified_release()['releaseId'])"
    out = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "wind-knowledge-2026-10-20.1"


def _copy(tmp_path, monkeypatch):
    d = tmp_path / "runtime"
    shutil.copytree(RUNTIME, d, ignore=shutil.ignore_patterns("__pycache__", "archive"))
    monkeypatch.setattr(ingest, "RUNTIME_ROOT", str(d))
    return d


def test_a_missing_release_stops_the_run(tmp_path, monkeypatch):
    d = _copy(tmp_path, monkeypatch)
    os.remove(d / "knowledge-release.json")
    with pytest.raises(KnowledgeReleaseError, match="manifest missing"):
        ingest.load_config()


def test_a_tampered_lake_configuration_is_never_used(tmp_path, monkeypatch):
    d = _copy(tmp_path, monkeypatch)
    cfg = json.loads((d / "lakes.json").read_text())
    (d / "lakes.json").write_text(json.dumps(cfg) + "\n ")            # any byte change outside a new release
    with pytest.raises(KnowledgeReleaseError, match="fails verification"):
        ingest.load_config()


def test_tampered_validation_evidence_stops_the_run(tmp_path, monkeypatch):
    d = _copy(tmp_path, monkeypatch)
    ev = d / "sector_wind" / "brain" / "validation_evidence.json"
    ev.write_text(ev.read_text().replace("{", "{ ", 1))
    with pytest.raises(KnowledgeReleaseError, match="fails verification"):
        ingest.load_config()


def test_the_job_entry_point_refuses_with_exit_2_instead_of_crashing(tmp_path):
    d = tmp_path / "runtime"
    shutil.copytree(RUNTIME, d, ignore=shutil.ignore_patterns("__pycache__", "archive"))
    os.remove(d / "knowledge-release.json")
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": PLATFORM}
    out = subprocess.run([sys.executable, str(d / "main.py"), "status", "--store", f"local:{tmp_path / 'a'}", "--start", "2026-10-01", "--end", "2026-10-02"],
                         cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 2 and "REFUSED (nothing published)" in out.stderr and "Traceback" not in out.stderr, out.stderr
