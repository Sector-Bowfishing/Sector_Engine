"""Golden DepthState fixtures for downstream contracts (Intelligence / Water Temp / Clarity / Vegetation / Biological).
Regenerate deliberately with UPDATE_FIXTURES=1; a diff here is a contract change and must be reviewed."""
import json
import os

import pytest
from depth_brain.state import build_state
from tests.helpers import NOW, candidate, lake_state

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

CASES = {
    "shift_only_observed": (candidate(), lake_state(593.6)),
    "shift_only_rising": (candidate(lakeId="Rising|AL"), lake_state(596.2)),
    "unavailable_datum_unknown": (candidate(lakeId="Datum Unknown|TN", status="UNKNOWN", sigma=0.0, tier="C", blockedReasons=["DATUM_UNKNOWN"], possible=False), lake_state()),
    "unavailable_no_level": (candidate(lakeId="No Level|GA"), None),
    "tier_d_no_depth_evidence": (candidate(lakeId="Modeled Only|XX", tier="D"), lake_state()),
    "contour_zones_reference_unverified": (
        candidate(lakeId="Contour Lake|TX", tier="A",
                  evidence={"tier": "A", "researchTier": "A", "kind": "contour", "coverage": 0.9, "intervalFt": 2, "bestSource": "contour:TWDB"},
                  referenceZones={"cumulative": {"3.0": 0.1, "6.0": 0.2, "10.0": 0.3}, "intervalFt": 2, "coverage": 0.9, "source": "TWDB", "referenceStatus": "UNVERIFIED"}),
        lake_state(593.6)),
    "contour_zones_effective": (
        candidate(lakeId="Contour Lake|MN", tier="A",
                  evidence={"tier": "A", "researchTier": "A", "kind": "contour", "coverage": 0.9, "intervalFt": 2},
                  referenceZones={"cumulative": {"3.0": 0.1, "6.0": 0.2, "10.0": 0.3}, "intervalFt": 2, "coverage": 0.9, "source": "MN", "referenceStatus": "VERIFIED", "referencePoolFt": 595.0}),
        lake_state(592.0)),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden(name):
    rec, ls = CASES[name]
    state, _ = build_state(rec, ls, NOW, manifest_version="fixture")
    path = os.path.join(FIX, name + ".json")
    if os.environ.get("UPDATE_FIXTURES") == "1":
        os.makedirs(FIX, exist_ok=True)
        json.dump(state, open(path, "w"), indent=1, sort_keys=True)
    assert json.load(open(path)) == json.loads(json.dumps(state, sort_keys=True)), f"{name}: contract drift"


REQUIRED = ("lakeId", "brainId", "slot", "schemaVersion", "stateSchema", "kind", "effectiveDepth", "coverage", "freshness", "provenance", "limitations")


@pytest.mark.parametrize("name", sorted(CASES))
def test_required_keys_and_never_a_fabricated_number(name):
    rec, ls = CASES[name]
    state, _ = build_state(rec, ls, NOW)
    assert all(k in state for k in REQUIRED)
    ed = state["effectiveDepth"]
    if state["kind"] == "unavailable":
        assert ed["mode"] == "unknown" and "shiftFt" not in ed and ed["reasons"]
        assert "referenceZones" not in state and "effectiveZones" not in state and "facts" not in state
    assert all(k not in state for k in ("absoluteDepthFt", "meanDepthFt", "maxDepthFt", "flats", "dropoffs", "channels", "score"))


def test_intelligence_consumer_rules_on_fixtures():
    """Reference restatement used in docs/brains/depth/DEPTH_INTELLIGENCE_CONTRACT.md: Intelligence restates, never recomputes."""
    def restate(state):
        ed = state["effectiveDepth"]
        if state["kind"] != "observed" or ed["mode"] == "unknown":
            return {"depth": "unknown", "why": ed.get("reasons")}
        return {"shiftFt": ed["shiftFt"], "uncertaintyFt": ed["uncertaintyFt"], "confidence": ed["confidence"], "tier": state["coverage"]["sourceTier"]}
    r, ls = CASES["shift_only_observed"]
    s, _ = build_state(r, ls, NOW)
    assert restate(s) == {"shiftFt": -1.4, "uncertaintyFt": 0.29, "confidence": "HIGH", "tier": "UNKNOWN"}
    r, ls = CASES["unavailable_no_level"]
    s, _ = build_state(r, ls, NOW)
    assert restate(s)["depth"] == "unknown"
