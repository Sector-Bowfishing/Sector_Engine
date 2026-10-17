"""Phase 1B verification gates (integration level, offline, stdlib + pytest).

* conformance fixtures have exactly one canonical home and are byte-identical to the pre-move hashes
* score baseline matches the artifacts in this tree and detects drift
* the new foundation works from a clean copy that contains no Desktop path and no docs/
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import score_baseline  # noqa: E402


# ---- conformance: one canonical home ----------------------------------------------------------
def test_conformance_fixtures_are_byte_identical_to_pre_move_hashes():
    manifest = json.load(open(os.path.join(ROOT, "verification", "fixtures", "conformance", "manifest.json")))["sha256"]
    home = os.path.join(ROOT, "contracts", "conformance")
    actual = {f: hashlib.sha256(open(os.path.join(home, f), "rb").read()).hexdigest()
              for f in sorted(os.listdir(home)) if f.endswith(".json")}
    assert actual == manifest


def test_no_duplicate_live_fixture_copy_at_old_location():
    old = os.path.join(ROOT, "docs", "brains", "conformance")
    leftovers = [f for f in os.listdir(old) if f.endswith(".json")] if os.path.isdir(old) else []
    assert leftovers == []


def test_no_code_or_ci_reads_the_old_conformance_path():
    allowed = {"jobs/brain-orchestrator/preflight_lineage.py", "verification/fixtures/conformance/manifest.json"}   # lineage diff keeps the old path for pre-move deployed commits
    scan = [".github", "Sources", "Tests", "jobs", "scripts", "ops", "tools", "verification"]
    pat = re.compile(r"docs[/\"', ]+brains[/\"', ]+conformance")
    offenders = []
    for top in scan:
        for base, dirs, names in os.walk(os.path.join(ROOT, top)):
            dirs[:] = [d for d in dirs if d not in (".build", "__pycache__", "node_modules", ".git")]
            for n in names:
                p = os.path.join(base, n)
                rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
                if rel in allowed or rel.endswith("test_verification_gates.py"):
                    continue
                try:
                    if pat.search(open(p, encoding="utf-8", errors="ignore").read()):
                        offenders.append(rel)
                except OSError:
                    pass
    assert offenders == []


# ---- score baseline ----------------------------------------------------------------------------
def test_score_baseline_matches_tree():
    assert score_baseline.main(["--check"]) == 0


def test_score_baseline_detects_value_and_rubric_drift(tmp_path):
    root = tmp_path / "r"
    (root / "docs" / "brains" / "scoring").mkdir(parents=True)
    (root / "verification" / "fixtures" / "scores").mkdir(parents=True)
    for f in os.listdir(os.path.join(ROOT, "docs", "brains", "scoring")):
        src = os.path.join(ROOT, "docs", "brains", "scoring", f)
        if os.path.isfile(src):
            shutil.copy(src, root / "docs" / "brains" / "scoring" / f)
    shutil.copy(os.path.join(ROOT, "verification", "fixtures", "scores", "score_baseline.json"),
                root / "verification" / "fixtures" / "scores" / "score_baseline.json")
    assert score_baseline.main(["--root", str(root), "--check"]) == 0
    frozen = root / "docs" / "brains" / "scoring" / "frozen-scores.json"
    data = json.load(open(frozen))
    data["water-temp"]["value"] = 9.9
    json.dump(data, open(frozen, "w"))
    assert score_baseline.main(["--root", str(root), "--check"]) == 1
    shutil.copy(os.path.join(ROOT, "docs", "brains", "scoring", "frozen-scores.json"), frozen)
    rubric = root / "docs" / "brains" / "scoring" / "engine-score-v1.json"
    rubric.write_text(rubric.read_text() + " ")
    assert score_baseline.main(["--root", str(root), "--check"]) == 1


# ---- clean copy / import gate ------------------------------------------------------------------
FOUNDATION = ["contracts/schemas", "providers", "brains/_template", "tools/architecture", "platform", "engine", "deploy"]


@pytest.fixture(scope="module")
def clean_copy(tmp_path_factory):
    dest = tmp_path_factory.mktemp("clean") / "repo"
    for rel in FOUNDATION:
        src = os.path.join(ROOT, rel)
        shutil.copytree(src, dest / rel, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return dest


def test_clean_copy_has_no_docs_and_no_desktop_dependency(clean_copy):
    assert not (clean_copy / "docs").exists()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "SECTOR_RESEARCH_ROOT", "HOME")}
    env["HOME"] = str(clean_copy / "nohome")
    r = subprocess.run([sys.executable, "-I", str(clean_copy / "tools" / "architecture" / "report.py"), "--root", str(clean_copy)],
                       cwd=str(clean_copy.parent), capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "REPORT-ONLY" in r.stdout


def test_clean_copy_schemas_load_and_templates_validate(clean_copy):
    sys.path.insert(0, str(clean_copy / "tools" / "architecture"))
    try:
        import importlib
        jl = importlib.import_module("jsonschema_lite")
        load = lambda *p: json.load(open(os.path.join(str(clean_copy), *p)))
        pairs = [(("brains", "_template", "brain.template.json"), "brain.schema.json"),
                 (("brains", "_template", "research", "GAPS.template.json"), "research-gaps.schema.json"),
                 (("brains", "_template", "research", "MANIFEST.template.json"), "research-manifest.schema.json"),
                 (("providers", "PROVIDERS.json"), "providers.schema.json"),
                 (("tools", "architecture", "large_file_exceptions.json"), "large-file-exceptions.schema.json"),
                 (("platform", "registries", "signals", "signals.json"), "registry-signals.schema.json")]
        for doc, schema in pairs:
            assert jl.validate(load(*doc), load("contracts", "schemas", schema)) == [], doc
        for name in os.listdir(os.path.join(str(clean_copy), "contracts", "schemas")):
            if name.endswith(".json"):
                assert load("contracts", "schemas", name)["$schema"].endswith("2020-12/schema")
    finally:
        sys.path.remove(str(clean_copy / "tools" / "architecture"))


def test_foundation_sources_contain_no_absolute_user_path(clean_copy):
    pat = re.compile(r"/Users/[A-Za-z0-9._-]+/|C:\\\\Users")
    offenders = []
    for base, _, names in os.walk(str(clean_copy)):
        if os.sep + "tests" in base:
            continue   # negative examples live in tests
        for n in names:
            if n.endswith((".py", ".json", ".md", ".sh")) and pat.search(open(os.path.join(base, n), encoding="utf-8", errors="ignore").read()):
                offenders.append(os.path.relpath(os.path.join(base, n), str(clean_copy)))
    assert offenders == []
