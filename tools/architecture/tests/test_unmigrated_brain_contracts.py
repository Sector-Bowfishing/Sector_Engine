"""Every locked machine id (tools/architecture/stable_brain_ids.json) has ONE operating contract with all 19 sections: in its canonical package
brains/<dir>/ once migrated, or at docs/architecture/certification/<dir>/ until then (STANDARD_BRAIN_PACKAGE_V1.md section 2). A migrated Brain must not keep
a second copy under certification/. Same heading rule as invariant 4. Docs only: no runtime is touched.
"""
import json
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
import sys  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
import report  # noqa: E402

with open(os.path.join(ROOT, "tools", "architecture", "stable_brain_ids.json"), encoding="utf-8") as fh:
    STABLE = json.load(fh)["directoryToBrainId"]
MIGRATED = set(report._brain_dirs(ROOT))


def _certification_contract(d):
    return os.path.join(ROOT, "docs", "architecture", "certification", d, "BRAIN_OPERATING_CONTRACT.md")


def _headings(text):
    return [re.sub(r"^\d+\.\s*", "", m.strip()).strip() for m in re.findall(r"^##\s+(.+)$", text, re.M)]


@pytest.mark.parametrize("d", sorted(STABLE))
def test_every_locked_brain_has_exactly_one_operating_contract_with_all_sections(d):
    package = os.path.join(ROOT, "brains", d, "BRAIN_OPERATING_CONTRACT.md")
    found = [p for p in (package, _certification_contract(d)) if os.path.exists(p)]
    assert len(found) == 1, f"{d}: expected exactly one operating contract, found {[os.path.relpath(p, ROOT) for p in found]}"
    assert (found[0] == package) == (d in MIGRATED), f"{d}: a migrated Brain's contract lives in its package; an unmigrated one under certification/"
    with open(found[0], encoding="utf-8") as fh:
        text = fh.read()
    assert [h for h in report.CONTRACT_HEADINGS if h not in _headings(text)] == []
    assert f"`{STABLE[d]}`" in text, f"{d}: contract does not name its machine id {STABLE[d]!r}"


def test_all_locked_brains_are_migrated():
    # Cortex architecture completion (2026-10-20): the six locked Brains are migrated. Depth and Vegetation are not locked ids yet.
    assert sorted(STABLE) == sorted(MIGRATED)
