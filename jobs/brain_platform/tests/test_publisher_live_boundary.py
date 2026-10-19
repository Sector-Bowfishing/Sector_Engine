"""Boundaries that keep Publisher LIVE V1 inert: the SHADOW package is untouched, nothing imports the live package, and no Brain is enabled."""
import ast
import os
import subprocess
import sys

from sector_brain_platform.publisher import PublisherMode, Result

PLAT = os.path.join(os.path.dirname(__file__), "..", "sector_brain_platform")


def test_shadow_vocabulary_is_unchanged_so_the_shadow_guarantee_still_holds():
    assert set(PublisherMode.__members__) == {"SHADOW", "DRY_RUN"} and {r.name for r in Result} == {"SKIP", "SHADOW_READY", "REJECTED", "FAILED_VALIDATION"}


def test_no_platform_module_and_no_shadow_module_imports_the_live_package():
    bad = []
    for dp, _, fs in os.walk(PLAT):
        if "publisher_live" in dp:
            continue
        for f in fs:
            if f.endswith(".py"):
                text = open(os.path.join(dp, f)).read()
                if "publisher_live" in text:
                    bad.append(os.path.join(dp, f))
    assert bad == [], bad
    code = "import sys; sys.path.insert(0, %r); import sector_brain_platform, sector_brain_platform.publisher; print('sector_brain_platform.publisher_live' in sys.modules)" % os.path.abspath(os.path.join(PLAT, ".."))
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip() == "False"


def test_the_orchestrator_does_not_import_the_live_package():
    src = open(os.path.join(os.path.dirname(__file__), "..", "..", "brain-orchestrator", "orchestrate.py")).read()
    assert "publisher_live" not in src


def test_nothing_in_the_live_package_enables_a_brain_or_reads_the_environment():
    pkg = os.path.join(PLAT, "publisher_live")
    for f in os.listdir(pkg):
        if f.endswith(".py"):
            tree = ast.parse(open(os.path.join(pkg, f)).read())
            for n in ast.walk(tree):
                if isinstance(n, ast.Attribute) and n.attr in ("environ", "getenv"):
                    raise AssertionError(f"{f} reads the environment: the live path cannot be switched on by an env var")
    from sector_brain_platform.publisher_live import LiveAuthorization
    assert LiveAuthorization().brains() == ()
