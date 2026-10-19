"""Wind Brain package gates (Repository Phase 2). Cross-component: Wind package, Publisher registry, deploy staging.

Dependency-light gates run everywhere. Gates that execute Wind code need its runtime deps (numpy, eccodes): they skip with
BLOCKED_DEPENDENCY when those are absent, and SECTOR_REQUIRE_WIND_DEPS=1 (set by the Wind CI job) turns a skip into a failure.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
WIND = os.path.join(ROOT, "brains", "wind")
RUNTIME = os.path.join(WIND, "runtime")
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
import report  # noqa: E402
from jsonschema_lite import validate  # noqa: E402

MAC_PATH = re.compile(r"/Users/|~/Desktop|~/Library|Library/Caches|Sector Research|Sector_Research_Data|Desktop/Development|iOS/sector-wind")
RESEARCH_MODULES = {"bowfishing_score", "evidence", "exemplars", "field", "field_qa", "field_run", "fieldops", "overwater",
                    "provider_bakeoff", "rrfs", "scoreboard"}


def _need(*mods):
    missing = []
    for m in mods:
        try:
            __import__(m)
        except ImportError:
            missing.append(m)
    if missing:
        msg = f"BLOCKED_DEPENDENCY: Wind runtime deps not installed: {missing}"
        if os.environ.get("SECTOR_REQUIRE_WIND_DEPS") == "1":
            pytest.fail(msg)
        pytest.skip(msg)


def _tracked(prefix):
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", prefix or "."], capture_output=True, check=True).stdout.decode()
    return [p for p in out.split("\0") if p]


# ---- identity / contract ---------------------------------------------------------------------------------


# ---- production boundary ---------------------------------------------------------------------------------
def _imports(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    mod = os.path.relpath(path, RUNTIME)[:-3].replace(os.sep, ".")      # e.g. sector_wind.brain.profile / sector_wind.brain.__init__
    package = mod.rsplit(".", 1)[0] if "." in mod else ""              # the package a relative import is resolved against
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                parts = package.split(".")
                anchor = ".".join(parts[: len(parts) - (n.level - 1)])
                base = f"{anchor}.{n.module}" if n.module else anchor
            else:
                base = n.module or ""
            out.add(base)
            out.update(f"{base}.{a.name}" for a in n.names)
    return out


def _runtime_files():
    return sorted(os.path.join(ROOT, p) for p in _tracked("brains/wind/runtime") if p.endswith(".py"))


def test_runtime_never_imports_research_and_contains_no_mac_path():
    offenders = []
    for f in _runtime_files():
        for m in _imports(f):
            if m.startswith("sector_wind_research") or m.split(".")[-1] in RESEARCH_MODULES and m.startswith("sector_wind"):
                offenders.append((os.path.relpath(f, ROOT), m))
    assert offenders == []
    for p in _tracked("brains/wind/runtime"):
        if p.endswith((".py", ".json", ".txt")):
            assert not MAC_PATH.search(open(os.path.join(ROOT, p), encoding="utf-8").read()), p


def test_every_shipped_module_is_reachable_from_a_runtime_entrypoint():
    files = {os.path.relpath(f, RUNTIME): f for f in _runtime_files()}
    def modfile(m):
        p = m.replace(".", "/")
        return next((c for c in (p + ".py", p + "/__init__.py") if c in files), None)
    seen, stack = set(), ["main.py", "sector_wind/brain/__main__.py", "sector_wind/brain/artifact.py"]
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        parts = f[:-3].split("/")
        stack += [i for i in ("/".join(parts[:k]) + "/__init__.py" for k in range(1, len(parts))) if i in files]
        stack += [mf for m in _imports(files[f]) if (mf := modfile(m))]
    assert sorted(set(files) - seen) == [], "shipped but unreachable (research or dead code in the production package)"


def test_single_canonical_wind_implementation():
    tracked = _tracked("")
    pkgs = sorted({p.split("sector_wind/")[0] for p in tracked if "/sector_wind/" in p})
    assert pkgs == ["brains/wind/runtime/"]
    assert [p for p in tracked if p.startswith("jobs/wind-hourly/")] == ["jobs/wind-hourly/README.md"]


# ---- deploy staging ----------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    dest = tmp_path_factory.mktemp("wind-context") / "ctx"
    r = subprocess.run(["bash", os.path.join(WIND, "deploy", "deploy-job.sh"), "--stage-only", str(dest)], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != "MICHAEL_APPROVED_WIND_DEPLOY"})
    assert r.returncode == 0, r.stderr
    return dest


def test_staged_image_context_is_exact(staged):
    assert sorted(os.listdir(staged)) == sorted([".gcloudignore", "Dockerfile", "lakes.json", "main.py", "requirements.txt",
                                                 "sector_brain_platform", "sector_wind"])
    shipped = sorted(os.path.relpath(os.path.join(d, f), staged / "sector_wind") for d, _, fs in os.walk(staged / "sector_wind") for f in fs)
    assert shipped == sorted(p[len("brains/wind/runtime/sector_wind/"):] for p in _tracked("brains/wind/runtime/sector_wind"))
    assert not any("sector_wind_research" in d or "research" in os.path.basename(d) for d, _, _ in os.walk(staged))
    docker = open(staged / "Dockerfile").read()
    assert "COPY lakes.json main.py ./" in docker and "COPY sector_wind ./sector_wind" in docker and "COPY sector_brain_platform ./sector_brain_platform" in docker


def test_staged_image_entrypoint_imports_from_the_image_layout(staged, tmp_path):
    _need("numpy", "eccodes")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-E", "-s", "main.py", "--help"], cwd=staged, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr[-2000:]
    r = subprocess.run([sys.executable, "-E", "-s", "-c", "import sys; sys.path.insert(0, '.'); import sector_wind.brain.publish, sector_wind.brain.artifact"],
                       cwd=staged, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr[-2000:]


# ---- clean copy: production tests without the research package or any Mac path ----------------------------
def test_production_tests_pass_in_a_clean_copy_without_research_package(tmp_path):
    _need("numpy", "eccodes", "pytest")
    dest = tmp_path / "repo"
    shutil.copytree(WIND, dest / "brains" / "wind", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "sector_wind_research"))
    shutil.copytree(os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform"), dest / "jobs" / "brain_platform" / "sector_brain_platform",
                    ignore=shutil.ignore_patterns("__pycache__"))
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "home"), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests", "-o", "testpaths=tests", "--ignore=tests/test_wind_kit_certification.py",
                        "-o", "pythonpath=runtime ../../jobs/brain_platform"], cwd=dest / "brains" / "wind", capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert " passed" in r.stdout and " failed" not in r.stdout
