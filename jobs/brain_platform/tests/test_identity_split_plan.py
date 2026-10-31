"""The identity-split plan (platform/security/identity_split_plan.json, Sector_Ops 19) is a PLAN: these tests keep it consistent with the target write model, never prove IAM."""
import json
import os

from sector_brain_platform.keys import BRAINS
from sector_brain_platform.publisher_live import security_model as SM

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PLAN = json.load(open(os.path.join(ROOT, "platform", "security", "identity_split_plan.json"), encoding="utf-8"))
WRITES_BRAIN_DATA = {"ADMIN", "WRITE_BRAIN_FAMILIES"}


def test_the_plan_claims_nothing_applied():
    assert PLAN["status"] == "PLAN_NOT_APPLIED"
    assert {s["state"] for s in PLAN["steps"]} <= {"DONE_PILOT", "PREPARED", "PLANNED", "BLOCKED"}


def test_every_registered_brain_has_a_current_and_a_target_identity_class():
    for side in ("current", "target"):
        assert set(BRAINS) <= set(PLAN[side]), side
        assert set(PLAN[side].values()) <= set(PLAN["classes"]) | {"NONE"}


def test_in_the_target_only_the_publisher_writes_brain_data():
    """FD-15: every target Brain identity is database READ-ONLY; the one exception is the frozen legacy combined package, named with its reason."""
    writers = {who for who, cls in PLAN["target"].items() if PLAN["classes"].get(cls, {}).get("rtdb") in WRITES_BRAIN_DATA}
    assert writers - set(PLAN["targetExceptions"]) == {"publisher"}
    assert set(PLAN["targetExceptions"]) == {"biological-state"} and "BA-04" in PLAN["targetExceptions"]["biological-state"]
    assert PLAN["target"]["orchestrator"] == "orchestrator" and PLAN["classes"]["orchestrator"]["rtdb"] == "WRITE_PLATFORM_FAMILIES"


def test_the_plan_matches_the_code_level_write_model():
    """The classes' database capabilities agree with security_model.rtdb_write_allowed (TARGET): a Brain job writes nothing, the Publisher writes its Brain's families only."""
    probe = "lakes/probe_AL/states/waterClarity"
    assert not SM.rtdb_write_allowed(SM.SPECIALIST, probe, brain_id="water-clarity")
    assert SM.rtdb_write_allowed(SM.PUBLISHER, probe, brain_id="water-clarity")
    assert not SM.rtdb_write_allowed(SM.PUBLISHER, probe, brain_id="wind")                  # cross-domain
    assert not SM.rtdb_write_allowed(SM.ORCHESTRATOR, probe) and not SM.rtdb_write_allowed(SM.OPS, probe)
    assert SM.STORE_CAPABILITIES["publisher"]["delete"] == () and SM.STORE_CAPABILITIES["specialist"]["create_only"] == ("artifacts/{ownBrain}/",)


def test_steps_are_ordered_gated_and_each_has_a_denial_probe():
    ids = [s["id"] for s in PLAN["steps"]]
    assert ids == [f"S{i}" for i in range(len(ids))]
    for i, s in enumerate(PLAN["steps"]):
        assert s["gate"].strip() and s["denialProbe"].strip()
        assert all(ids.index(d) < i for d in s.get("dependsOn", []))
    order = [s["what"].split()[0] for s in PLAN["steps"]]
    assert order.index("wind-hourly") < order.index("water-temp-brain") < order.index("lake-brain") < order.index("sector-intelligence")   # cutover_order.json


def test_no_account_names_or_project_details_in_the_public_plan():
    text = json.dumps(PLAN)
    for bad in ("@", "iam.gserviceaccount", "sector-9393c", "gs://", "brain-writer", "wind-hourly-job", "sector-publisher"):
        assert bad not in text, bad
