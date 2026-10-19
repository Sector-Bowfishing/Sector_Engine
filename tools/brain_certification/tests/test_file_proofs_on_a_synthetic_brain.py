"""The file-based proofs run, positively and negatively, on a SYNTHETIC Brain built in a temp directory (no real Brain involved)."""
import json
import os
import shutil
import sys

import pytest

from brain_cert_kit import BrainCertSpec
from brain_cert_kit import proofs as P
from brain_cert_kit.env import Env

REAL = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


@pytest.fixture()
def repo(tmp_path):
    arch = tmp_path / "tools" / "architecture"
    arch.mkdir(parents=True)
    for f in ("report.py", "jsonschema_lite.py"):
        shutil.copy(os.path.join(REAL, "tools", "architecture", f), arch / f)
    (arch / "stable_brain_ids.json").write_text(json.dumps({"directoryToBrainId": {"synth": "synth-id"}}))
    b = tmp_path / "brains" / "synth"
    (b / "runtime").mkdir(parents=True)
    (b / "research").mkdir()
    (b / "brain.json").write_text(json.dumps({"dataBudget": {"maxTrackedFileBytes": 1000}}))
    (b / "runtime" / "core.py").write_text("def run(x):\n    return x\n")
    (b / "runtime" / "builder.py").write_text("import json\n\ndef build(x):\n    return json.dumps(x)\n")
    (b / "research" / "README.md").write_text("rules only\n")
    (b / "README.md").write_text("synthetic\n")
    return tmp_path


def spec(repo, **kw):
    base = dict(brain_id="synth-id", directory="synth", repo_root=str(repo), lifecycle="CALIBRATION", workspace_id="synth", bundle_id="b", contract_file="c.json",
                registry_schema_id="s", builder_module="runtime/builder.py", artifact_factory=lambda *a: {}, required_files=("README.md", "runtime/core.py"),
                unique_module_basenames=("core.py",), allowed_runtime_ext=(".py",), research_files=("README.md",), write_call_suffixes=("db.update",), allowed_write_sites=frozenset())
    base.update(kw)
    return BrainCertSpec(**base)


def env(repo, **kw):
    e = Env(spec(repo, **kw))
    sys.path[:] = [p for p in sys.path if not p.startswith(str(repo))]
    return e


def test_p01_location_and_identity_mapping(repo):
    P.p01_location_and_shape(env(repo))
    with pytest.raises(AssertionError, match="missing"):
        P.p01_location_and_shape(env(repo, required_files=("nope.md",)))
    with pytest.raises(AssertionError, match="stable_brain_ids"):
        P.p01_location_and_shape(env(repo, brain_id="other-id"))


def test_p02_one_implementation_and_retirement_pointer(repo):
    P.p02_one_production_implementation(env(repo))
    (repo / "jobs" / "old").mkdir(parents=True)
    (repo / "jobs" / "old" / "core.py").write_text("x = 1\n")
    with pytest.raises(AssertionError, match="outside"):
        P.p02_one_production_implementation(env(repo))
    (repo / "jobs" / "old" / "core.py").unlink()
    (repo / "jobs" / "old" / "README.md").write_text("# Moved: this directory moved to brains/synth\n")
    P.p02_one_production_implementation(env(repo, legacy_pointer_dir="jobs/old"))
    (repo / "jobs" / "old" / "extra.py").write_text("y = 2\n")
    with pytest.raises(AssertionError, match="only the retirement pointer"):
        P.p02_one_production_implementation(env(repo, legacy_pointer_dir="jobs/old"))


def test_p14_direct_write_pin_detects_added_removed_and_forbidden_clients(repo):
    rt = repo / "brains" / "synth" / "runtime"
    (rt / "writer.py").write_text("class W:\n    def put(self, u):\n        self.db.update(u)\n")
    site = ("writer.py", "put", "self.db.update")
    P.p14_direct_write_sites_pinned(env(repo, allowed_write_sites=frozenset({site})))
    with pytest.raises(AssertionError, match="differ"):
        P.p14_direct_write_sites_pinned(env(repo, allowed_write_sites=frozenset()))                      # an unaudited door
    (rt / "second.py").write_text("def f(db):\n    db.update({})\n")
    with pytest.raises(AssertionError, match="differ"):
        P.p14_direct_write_sites_pinned(env(repo, allowed_write_sites=frozenset({site})))
    (rt / "second.py").unlink()
    (rt / "rest.py").write_text("import urllib.request\nr = urllib.request.Request('u', method='PATCH')\n")
    with pytest.raises(AssertionError, match="REST write"):
        P.p14_direct_write_sites_pinned(env(repo, allowed_write_sites=frozenset({site})))
    (rt / "rest.py").write_text("import requests\n")
    with pytest.raises(AssertionError, match="direct database"):
        P.p14_direct_write_sites_pinned(env(repo, allowed_write_sites=frozenset({site})))


def test_p15_builder_purity(repo):
    P.p15_artifact_path_cannot_write(env(repo))
    (repo / "brains" / "synth" / "runtime" / "builder.py").write_text("import os\n\ndef build(x):\n    return os.environ\n")
    with pytest.raises(AssertionError, match="imports I/O"):
        P.p15_artifact_path_cannot_write(env(repo))
    (repo / "brains" / "synth" / "runtime" / "builder.py").write_text("def build(x):\n    return open('f').read()\n")
    with pytest.raises(AssertionError, match="open"):
        P.p15_artifact_path_cannot_write(env(repo))


def test_p16_runtime_isolation_paths_and_documented_exemptions(repo):
    P.p16_runtime_isolation_paths(env(repo))
    rt = repo / "brains" / "synth" / "runtime" / "core.py"
    rt.write_text("P = '/Users/someone/data'\n")
    with pytest.raises(AssertionError, match="core.py:1"):
        P.p16_runtime_isolation_paths(env(repo))
    rt.write_text("P = '/Users/someone/data'  # DELIBERATE_TEST_CONSTANT\n")
    P.p16_runtime_isolation_paths(env(repo, local_path_exempt_markers=("DELIBERATE_TEST_CONSTANT",)))


def test_p17_research_separation_budget_and_runtime_data(repo):
    P.p17_research_separate_from_runtime(env(repo))
    (repo / "brains" / "synth" / "runtime" / "data.csv").write_text("a,b\n")
    with pytest.raises(AssertionError, match="non-code"):
        P.p17_research_separate_from_runtime(env(repo))
    (repo / "brains" / "synth" / "runtime" / "data.csv").unlink()
    (repo / "brains" / "synth" / "research" / "notes.md").write_text("x" * 10)
    with pytest.raises(AssertionError, match="listing"):
        P.p17_research_separate_from_runtime(env(repo))
    (repo / "brains" / "synth" / "research" / "notes.md").unlink()
    (repo / "brains" / "synth" / "README.md").write_text("x" * 2000)
    with pytest.raises(AssertionError, match="data budget"):
        P.p17_research_separate_from_runtime(env(repo))
