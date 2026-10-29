"""One authoritative cutover order: no conflicting sequence may remain anywhere in the repository records."""
import json
import os
import re

from sector_brain_platform import data_ownership as DO, publication_stage as PS
from sector_brain_platform.publisher import default_registry

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def test_order_is_complete_unique_dependency_respecting_and_blocks_shadow_only_brains():
    o = PS.cutover_order()
    ids = [x["brainId"] for x in o["order"]]
    blocked = [x["brainId"] for x in o["blocked"]]
    assert len(ids) == len(set(ids)) and not set(ids) & set(blocked)
    assert set(ids) | set(blocked) == set(default_registry().brains)                    # every registered Brain is either ordered or blocked, none forgotten
    assert ids[:3] == ["water-clarity", "biological-state", "wind"]                         # PL-10 as recorded in Cortex
    assert blocked == ["depth", "vegetation"]
    assert [x["step"] for x in o["order"]] == list(range(1, len(ids) + 1))
    assert next(x for x in o["order"] if x["brainId"] == "biological-state")["legacyCombined"] is True
    # Cutover order is the order in which the WRITER changes (risk and readiness); it is not the execution order. A consumer may change writer before its input Brain does,
    # because the input stays available from the input Brain's still-working direct writer. The execution order is data_ownership.execution_order() and is tested separately.
    assert o["rules"] and any("earlier step" in r for r in o["rules"])
    assert DO.execution_order()[-1] == "sector-intelligence"


def test_no_other_document_states_a_different_cutover_order():
    pat = re.compile(r"(?i)cutover order[^\n]{0,80}")
    for rel in ("docs/architecture/production/PRODUCTION_CUTOVER_PLANS_V1.md", "docs/cortex/sessions/2026-10-28-orchestrator-cortex-3-1.md"):
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        for m in pat.findall(text):
            assert "wind -> lake" not in m.lower() and "wind → lake" not in m.lower(), (rel, m)
