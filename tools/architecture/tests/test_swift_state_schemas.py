"""Versioned state contracts for the Swift Brains (BR-13): lake-state-v1 and water-temp-state-v1 are GENERATED from the Swift Codable records, are
current, and every state the runners actually wrote (golden write sets, regenerated only by the Swift fixture tests) validates against them."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
import swift_state_schema as G  # noqa: E402
from jsonschema_lite import validate  # noqa: E402

GOLDEN = {"lake-state-v1": ("brains/lake/tests/golden/lake_run_updates.json", "/states/lake"),
          "water-temp-state-v1": ("brains/water-temperature/tests/golden/water_temp_run_updates.json", "/states/waterTemp")}


def test_the_generated_schemas_are_current():
    assert G.main(["--check"]) == 0


def test_every_recorded_state_validates_against_its_schema():
    for rec in G.RECORDS:
        schema = json.load(open(os.path.join(ROOT, rec["out"])))
        golden, suffix = GOLDEN[rec["id"]]
        states = {k: v for k, v in json.load(open(os.path.join(ROOT, golden))).items() if k.startswith("lakes/") and k.endswith(suffix)}
        assert states, rec["id"]
        for k, v in states.items():
            assert list(validate(v, schema)) == [], (rec["id"], k, list(validate(v, schema))[:3])


def test_a_state_missing_a_required_field_or_carrying_an_unknown_one_is_rejected():
    for rec in G.RECORDS:
        schema = json.load(open(os.path.join(ROOT, rec["out"])))
        golden, suffix = GOLDEN[rec["id"]]
        state = next(v for k, v in json.load(open(os.path.join(ROOT, golden))).items() if k.endswith(suffix))
        assert list(validate({k: v for k, v in state.items() if k != schema["required"][0]}, schema))
        assert list(validate({**state, "inventedField": 1}, schema))
