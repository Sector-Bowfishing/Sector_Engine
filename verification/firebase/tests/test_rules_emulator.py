"""Brain RTDB rules on the Firebase emulator (FD-11 / PL-08). Runs only where the Ops-owned rules and a running RTDB emulator are available:

    SECTOR_OPS_RULES=/path/to/Sector_Ops/database.rules.json RTDB_EMULATOR=http://localhost:9311 python -m pytest verification/firebase

Skipped otherwise (CI has neither: the rules live in the Sector Ops repository)."""
import json
import os
import sys
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules_emulator_check as R  # noqa: E402

RULES = os.environ.get("SECTOR_OPS_RULES")
EMU = os.environ.get("RTDB_EMULATOR")


def _available() -> bool:
    if not (RULES and EMU and os.path.isfile(RULES)):
        return False
    try:
        urllib.request.urlopen(f"{EMU}/.json{R.NS}", timeout=2)
        return True
    except urllib.error.HTTPError:
        return True                                   # the emulator answered (a rules denial is still an answer)
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _available(), reason="needs SECTOR_OPS_RULES and a running RTDB emulator (RTDB_EMULATOR)")


@pytest.mark.parametrize("proposed", [False, True], ids=["deployed", "proposed-least-privilege"])
def test_rules(proposed):
    with open(RULES, encoding="utf-8") as fh:
        rules = json.load(fh)
    diffs = [(n, got, want) for n, got, want in R.run(rules, proposed, base=EMU) if got != want]
    assert not diffs, diffs


def test_proposal_changes_only_lakes_and_adds_one_allowlist():
    with open(RULES, encoding="utf-8") as fh:
        rules = json.load(fh)
    p = R.propose_species_presence_rules(rules)
    changed = {k for k in set(rules["rules"]) | set(p["rules"]) if rules["rules"].get(k) != p["rules"].get(k)}
    assert changed == {"lakes", "access"}
    assert p["rules"]["access"]["opsUsers"] == rules["rules"]["access"]["opsUsers"]
