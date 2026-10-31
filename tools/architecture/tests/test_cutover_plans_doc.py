"""The per-Brain cutover plans (docs/architecture/production/CUTOVER_PLANS_WT_LAKE_INTELLIGENCE_V1.md) follow the enforced order and cover all nine common gates."""
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DOC = open(os.path.join(ROOT, "docs", "architecture", "production", "CUTOVER_PLANS_WT_LAKE_INTELLIGENCE_V1.md"), encoding="utf-8").read()
ORDER = [o["brainId"] for o in json.load(open(os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform", "cutover_order.json"), encoding="utf-8"))["order"]]
PLANNED = ("water-temp", "lake-brain", "sector-intelligence")


def _sections():
    parts = re.split(r"^## \d\. ", DOC, flags=re.M)[1:]
    return {re.search(r"\(`([a-z-]+)`", p).group(1): p for p in parts if re.search(r"\(`([a-z-]+)`", p)}


def test_the_plans_follow_the_enforced_cutover_order():
    found = [b for b in _sections() if b in PLANNED]
    assert found == [b for b in ORDER if b in PLANNED] == list(PLANNED)


def test_each_plan_covers_the_nine_common_gates_and_states_nothing_as_executed():
    for brain, text in _sections().items():
        if brain not in PLANNED:
            continue
        for g in range(1, 10):
            assert re.search(rf"^\| G{g} ", text, re.M), (brain, g)
    assert "NOTHING here is executed or authorised" in DOC
