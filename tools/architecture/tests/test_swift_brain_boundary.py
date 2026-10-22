"""Swift Brain boundary (Cortex 2.1, D-14b / decision D-C). Lake and Water Temperature are their own SwiftPM targets but still use symbols of the
customer `SectorEngine` library at `package` access. Until a non-customer Brain library is extracted (decision D-C), that surface is pinned:
it may shrink, never grow unreviewed, and the customer library never imports a Brain target."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(ROOT, "Sources", "SectorEngine")
PAT = re.compile(r"^\s*package\s+(?:final\s+|static\s+|override\s+)*(func|let|var|struct|enum|class|init|protocol|typealias)\b\s*([A-Za-z_][A-Za-z0-9_]*)?")


def _surface():
    out = []
    for dp, _, fs in os.walk(SRC):
        for f in sorted(fs):
            if f.endswith(".swift"):
                p = os.path.join(dp, f)
                for line in open(p, encoding="utf-8"):
                    m = PAT.match(line)
                    if m:
                        out.append(f"{os.path.relpath(p, SRC)}:{m.group(1)} {m.group(2) or ''}".strip())
    return sorted(out)


def test_the_package_access_surface_is_pinned():
    pinned = json.load(open(os.path.join(ROOT, "tools", "architecture", "baseline", "swift_package_surface.json")))["entries"]
    now = _surface()
    grown = sorted(set(now) - set(pinned))
    gone = sorted(set(pinned) - set(now))
    assert not grown, f"new `package` symbols in the customer library (review D-C, then pin): {grown}"
    assert not gone, f"`package` symbols removed: shrink tools/architecture/baseline/swift_package_surface.json: {gone}"


def test_the_customer_library_never_imports_a_brain_target():
    for dp, _, fs in os.walk(os.path.join(ROOT, "Sources")):
        for f in fs:
            if f.endswith(".swift"):
                src = open(os.path.join(dp, f), encoding="utf-8").read()
                assert not re.search(r"^\s*import\s+(LakeBrain|WaterTemperatureBrain)\b", src, re.M), os.path.join(dp, f)


def test_package_swift_keeps_the_brain_targets_out_of_the_customer_products():
    pkg = open(os.path.join(ROOT, "Package.swift"), encoding="utf-8").read()
    lib = re.search(r'\.library\(\s*name:\s*"SectorEngine"[^)]*\)', pkg)
    assert lib and "LakeBrain" not in lib.group(0) and "WaterTemperatureBrain" not in lib.group(0)


def test_brain_targets_import_their_library_unconditionally_so_they_build_on_linux():
    """A Brain target must not import SectorEngine inside `#if canImport(...)`: on Linux the import silently disappears and the job cannot build
    (regression found by the Linux CI job, 2026-10-20)."""
    for root in ("brains/lake/runtime", "brains/water-temperature/runtime", "brains/lake/tests/swift", "brains/water-temperature/tests/swift"):
        for dp, _, fs in os.walk(os.path.join(ROOT, root)):
            for f in fs:
                if not f.endswith(".swift"):
                    continue
                stack = []
                for n, line in enumerate(open(os.path.join(dp, f), encoding="utf-8"), 1):
                    s = line.strip()
                    if s.startswith("#if"):
                        stack.append(s)
                    elif s.startswith("#endif") and stack:
                        stack.pop()
                    elif re.match(r"(@testable\s+)?import\s+(SectorEngine|LakeBrain|WaterTemperatureBrain)\b", s):
                        assert not stack, f"{os.path.join(dp, f)}:{n}: `{s}` inside {stack}"
