"""Cortex M04 (ENGINE_SAFE_DOCS): the combined biological-state charter is split into the two target charters, fish-knowledge and fish-behavior, before the M02
package split. The combined charter stays the one the tools read; these tests keep the three consistent until each target charter becomes its package's CHARTER.json."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FISH = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(FISH))
COMBINED = json.load(open(os.path.join(FISH, "research", "CHARTER.json"), encoding="utf-8"))
TARGET = {b: json.load(open(os.path.join(ROOT, COMBINED["splitInto"][b]), encoding="utf-8")) for b in ("fish-knowledge", "fish-behavior")}
#: brain-architecture.json authorizedInputs (Cortex 3.1.1): Fish consumes no Brain; Biological Brain consumes Fish and the environmental specialists
AUTHORIZED = {"fish-knowledge": set(), "fish-behavior": {"fish-knowledge", "wind", "water-clarity", "lake-brain", "water-temp", "depth", "vegetation"}}


def test_every_combined_prediction_lands_in_exactly_one_target_charter_unchanged():
    by_target = {b: {p["id"]: p for p in c["predicts"]} for b, c in TARGET.items()}
    for p in COMBINED["predicts"]:
        owner = p["targetBrain"]
        assert p["id"] in by_target[owner] and all(p["id"] not in v for b, v in by_target.items() if b != owner)
        assert {k: v for k, v in p.items() if k != "targetBrain"} == by_target[owner][p["id"]]          # same id, description and status: nothing re-graded
    assert sum(len(v) for v in by_target.values()) == len(COMBINED["predicts"])


def test_target_charters_use_only_authorized_inputs_and_fish_never_depends_on_biological_brain():
    for b, c in TARGET.items():
        assert c["brainId"] == b and c["schema"] == COMBINED["schema"] and c["status"] == COMBINED["status"]
        assert {n["brain"] for n in c["needsFrom"]} <= AUTHORIZED[b], b
    assert TARGET["fish-knowledge"]["needsFrom"] == []
    assert {n["brain"] for n in COMBINED["needsFrom"]} <= {n["brain"] for n in TARGET["fish-behavior"]["needsFrom"]}
    assert all(n["targetBrain"] == "fish-behavior" for n in COMBINED["needsFrom"])
    assert any(x["brain"] == "fish-behavior" for x in TARGET["fish-knowledge"]["providesTo"])


def test_each_target_charter_names_the_other_as_owner_of_what_it_must_not_do():
    assert any("Biological Brain owns it" in m for m in TARGET["fish-knowledge"]["mustNotPredict"])
    assert any("Fish Brain owns them" in m for m in TARGET["fish-behavior"]["mustNotPredict"])


def test_water_temperature_charter_names_the_biological_brain_as_owner_of_fish_behaviour():
    wt = json.load(open(os.path.join(ROOT, "brains", "water-temperature", "research", "CHARTER.json"), encoding="utf-8"))
    assert "fish behaviour (Biological Brain owns it)" in wt["mustNotPredict"] and "fish behaviour (Fish owns it)" not in wt["mustNotPredict"]
