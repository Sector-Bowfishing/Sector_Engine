import datetime as dt

from sector_brain_platform import assert_owned, beta_readiness

NOW = dt.datetime(2026, 10, 12, 12, 0, tzinfo=dt.timezone.utc)
VAL_OK = {b: {"status": "VALIDATED"} for b in ("lake-brain", "water-temp", "water-clarity", "wind", "sector-intelligence")}


def row(**over):
    base = {"lake": {"readiness": "VALIDATED", "kind": "observed", "stale": False}, "waterTemp": {"readiness": "VALIDATED", "kind": "measured", "stale": False},
            "waterClarity": {"readiness": "VALIDATED", "kind": "observed", "stale": False}, "wind": {"readiness": "VALIDATED", "kind": "analysis", "stale": False}}
    base.update(over)
    return {"slots": base, "readiness": {k: v.get("readiness") for k, v in base.items()}}


def intel(**over):
    base = {"kind": "evaluated", "evaluationVersion": "intelligence-eval-v1", "generatedAt": "2026-10-12T11:00:00Z",
            "synthesis": {"inputsFresh": 5}, "degradedInputs": [], "inputs": {"biology": {"status": "PUBLISHED", "knowledgeMedian": 6.0}}}
    base.update(over)
    return base


def test_ready_only_when_nothing_blocks_or_warns():
    r = beta_readiness("A|AL", row(), intel(), VAL_OK, {}, {}, NOW)
    assert r["betaReadiness"] == "READY" and r["blockers"] == [] and r["warnings"] == []
    assert_owned({"control/beta/A_AL": r}, "brain-platform")


def test_pilot_today_is_not_ready_with_traceable_blockers():
    fleet = row(lake={"readiness": "CALIBRATION", "kind": "observed", "stale": True}, waterTemp={"readiness": "CALIBRATION", "kind": "modeled", "stale": True},
               waterClarity={"readiness": "BETA", "kind": "modeled", "stale": False}, wind={"readiness": "CALIBRATION", "kind": "analysis", "stale": False})
    val = {"sector-intelligence": {"status": "NOT_VALIDATED"}, "lake-brain": {"status": "NOT_VALIDATED"}}
    r = beta_readiness("Guntersville|AL", fleet, intel(degradedInputs=["lake", "waterTemp"], inputs={"biology": {"status": "PUBLISHED", "knowledgeMedian": 4.5}}), val, {}, {"tva-restapi": True}, NOW)
    assert r["betaReadiness"] == "NOT_READY"
    codes = sorted(b["code"] + ":" + str(b.get("slot")) for b in r["blockers"])
    assert codes == ["SLOT_STALE:lake", "SLOT_STALE:waterTemp", "SYNTHESIS_NOT_VALIDATED:intelligence"]
    wc = {w["code"] for w in r["warnings"]}
    assert {"READINESS_NOT_VALIDATED", "INTELLIGENCE_INPUT_DEGRADED", "SPECIES_KNOWLEDGE_LOW", "BRAIN_NOT_VALIDATED", "SOURCE_STALE"} <= wc
    assert r["supportingBrainStates"]["waterTemp"]["kind"] == "modeled" and r["supportingBrainStates"]["intelligence"]["inputsFresh"] == 5


def test_missing_slot_and_missing_evaluation_block():
    r = beta_readiness("B|AL", {"slots": {"wind": {"readiness": "CALIBRATION", "stale": False}}}, None, VAL_OK, {}, {}, NOW)
    codes = {b["code"] for b in r["blockers"]}
    assert "SLOT_NOT_PUBLISHED" in codes and "NO_INTELLIGENCE_EVALUATION" in codes and r["betaReadiness"] == "NOT_READY"
    r2 = beta_readiness("C|AL", row(wind={"readiness": "DISCOVERED", "kind": "unavailable", "stale": False}), intel(), VAL_OK, {"wind": {"status": "FAILED"}}, {}, NOW)
    codes = {b["code"] for b in r2["blockers"]}
    assert {"VALUE_UNAVAILABLE", "READINESS_BELOW_MINIMUM", "BRAIN_FAILED"} <= codes


def test_candidate_when_only_warnings():
    r = beta_readiness("D|AL", row(waterClarity={"readiness": "BETA", "kind": "observed", "stale": False}), intel(), VAL_OK, {}, {}, NOW)
    assert r["betaReadiness"] == "CANDIDATE" and [w["code"] for w in r["warnings"]] == ["READINESS_NOT_VALIDATED"]
