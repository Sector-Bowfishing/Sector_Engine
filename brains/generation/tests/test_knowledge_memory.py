"""Approved memory (Cortex BR-10, BR-11, BR-16, BR-18): Generation's knowledge release verifies on load, loads in a clean environment, is the ONLY
knowledge the runtime reads, and an unapproved release is never published from. Offline."""
import ast
import os
import subprocess
import sys

import pytest

from generation_brain import knowledge as K

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.abspath(os.path.join(HERE, "..", "runtime"))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def test_the_release_verifies_and_holds_exactly_the_runtime_knowledge():
    k = K.load()
    assert set(k.release["files"]) == set(K.FILES) and k.release["store"] == "PACKAGED_IN_IMAGE"
    assert k.release["releaseId"].startswith("generation-knowledge-") and k.lineage()[2].startswith("sha256:")
    assert k.catalog()["damLakeCount"] == len(k.catalog()["dams"]) and set(k.access()) == {"tva", "cwms", "swpa", "rise", "usgs"}


def test_an_unapproved_release_is_never_publishable():
    k = K.load()
    assert k.release["approvalStatus"] == "NOT_RECORDED" and not k.approved
    with pytest.raises(K.KnowledgeNotApproved, match="BLOCKED_AWAITING_APPROVED_RELEASE"):
        K.require_approved(k)


def test_clean_environment_load_without_home_research_data_or_repo_cwd(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": os.pathsep.join([RUNTIME, os.path.join(REPO, "jobs", "brain_platform")])}
    out = subprocess.run([sys.executable, "-c", "from generation_brain import knowledge as K; print(K.load().release['releaseId'])"],
                         cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().startswith("generation-knowledge-")


def test_runtime_reads_knowledge_only_from_the_release_and_never_imports_research():
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(RUNTIME, "generation_brain")) for f in fs if f.endswith(".py")] + [os.path.join(RUNTIME, "run.py")]
    for p in files:
        src = open(p, encoding="utf-8").read()
        tree = ast.parse(src)
        mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m.startswith("generation_research") for m in mods), p
        assert "LakeDirectory.swift" not in src and "bindings.proposed" not in src, p
