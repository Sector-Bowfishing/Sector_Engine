"""The all-lakes watchdog lists (tools/ops/brain_watchdog_lakes.py): generated from the directory, pinned into the live policy and the staged
fragments, and --check catches any drift. Local only: no network."""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools", "ops"))
import brain_watchdog_lakes as BL   # noqa: E402


def test_the_committed_lists_match_the_directory():
    assert BL.main(["--check"]) == 0


def test_every_brain_covers_the_whole_directory():
    lakes = BL.generated()
    assert len(lakes) > 600 and lakes == sorted(set(lakes))
    pol = json.load(open(BL.POLICY))
    for b in BL.BRAINS:
        assert pol["brains"][b]["lakes"] == lakes


def test_check_flags_a_dropped_lake_and_a_missing_scope_ref():
    lakes = BL.generated()
    pol = copy.deepcopy(json.load(open(BL.POLICY)))
    pol["brains"]["water-temp"]["lakes"] = lakes[:-1]
    pol["brains"]["lake-brain"].pop("lakesScopeRef")
    probs = BL.problems(pol, lakes)
    assert any("water-temp" in p and "lakes pinned" in p for p in probs)
    assert any("lake-brain" in p and "lakesScopeRef" in p for p in probs)


def test_holders_and_approval_refs_are_untouched():
    pol = json.load(open(BL.POLICY))
    assert {b: pol["brains"][b]["holder"] for b in BL.BRAINS} == {b: "pulse" for b in BL.BRAINS}
    assert pol["brains"]["lake-brain"]["approvalRef"] == "owner-approval-2026-11-12/sector-ops-51-lake-on-pulse"
    assert pol["brains"]["water-temp"]["approvalRef"] == "owner-approval-2026-11-16/sector-ops-51-b1-b5"
    assert "approvalRef" not in pol["brains"]["water-clarity"]
