"""Registered Brains that are not migrated yet keep their operating contract at
docs/architecture/certification/<dir>/BRAIN_OPERATING_CONTRACT.md (STANDARD_BRAIN_PACKAGE_V1.md §2) until they
move to brains/<dir>/. This pins that every locked machine id has exactly one contract with all 19 sections,
using the same heading rule as invariant 4. Docs only: no runtime is touched.
"""
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
import report  # noqa: E402

with open(os.path.join(ROOT, "tools", "architecture", "stable_brain_ids.json"), encoding="utf-8") as fh:
    STABLE = json.load(fh)["directoryToBrainId"]
MIGRATED = set(report._brain_dirs(ROOT))
UNMIGRATED = sorted(set(STABLE) - MIGRATED)


def _contract(d):
    return os.path.join(ROOT, "docs", "architecture", "certification", d, "BRAIN_OPERATING_CONTRACT.md")


def _headings(text):
    return [re.sub(r"^\d+\.\s*", "", m.strip()).strip() for m in re.findall(r"^##\s+(.+)$", text, re.M)]


def test_unmigrated_set_is_the_expected_three():
    assert UNMIGRATED == ["lake", "sector-intelligence", "water-temperature"]


@pytest.mark.parametrize("d", UNMIGRATED)
def test_unmigrated_brain_has_an_operating_contract_with_all_sections(d):
    path = _contract(d)
    assert os.path.exists(path), f"{d}: missing {os.path.relpath(path, ROOT)}"
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    heads = _headings(text)
    assert [h for h in report.CONTRACT_HEADINGS if h not in heads] == []
    assert f"`{STABLE[d]}`" in text, f"{d}: contract does not name its machine id {STABLE[d]!r}"


@pytest.mark.parametrize("d", sorted(MIGRATED))
def test_a_migrated_brain_has_no_second_contract_under_certification(d):
    assert not os.path.exists(_contract(d)), f"{d} is migrated: its only contract is brains/{d}/BRAIN_OPERATING_CONTRACT.md"
