"""Approved memory (Cortex 2.1 BR-10, BR-11, BR-16, BR-18): Vegetation's knowledge release verifies on load, loads in a clean environment, is the ONLY
knowledge the runtime reads, and an unapproved release is never published from (the four stages stay separate: research -> approval -> release ->
runtime). Offline."""
import ast
import os
import subprocess
import sys

import pytest

from vegetation_brain import knowledge as K

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.abspath(os.path.join(HERE, "..", "runtime"))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def test_the_release_verifies_and_holds_exactly_the_runtime_knowledge():
    k = K.load()
    assert set(k.release["files"]) == set(K.FILES) and k.release["store"] == "PACKAGED_IN_IMAGE"
    assert k.release["releaseId"].startswith("vegetation-knowledge-") and k.lineage()[2].startswith("sha256:")


def test_an_unapproved_release_is_never_publishable():
    k = K.load()
    assert k.release["approvalStatus"] == "NOT_RECORDED" and not k.approved            # no approval record exists yet (gated G-1)
    with pytest.raises(K.KnowledgeNotApproved, match="BLOCKED_AWAITING_APPROVED_RELEASE"):
        K.require_approved(k)


def test_clean_environment_load_without_home_research_data_or_repo_cwd(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": os.pathsep.join([RUNTIME, os.path.join(REPO, "jobs", "brain_platform")])}
    out = subprocess.run([sys.executable, "-c", "from vegetation_brain import knowledge as K; print(K.load().release['releaseId'])"],
                         cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().startswith("vegetation-knowledge-")


def test_runtime_reads_knowledge_only_from_the_release_directory_and_never_imports_research():
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(RUNTIME, "vegetation_brain")) for f in fs if f.endswith(".py")] + [os.path.join(RUNTIME, "run.py")]
    for p in files:
        src = open(p, encoding="utf-8").read()
        tree = ast.parse(src)
        mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(m.startswith("vegetation_research") for m in mods), p
        assert "maturity_inputs" not in src and "VALIDATION_PREREGISTRATION" not in src.replace("records/VEGETATION_VALIDATION_PREREGISTRATION.md", ""), p
        for lit in (n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)):
            assert not lit.endswith((".csv", ".tif", "maturity_inputs.json")), (p, lit)
