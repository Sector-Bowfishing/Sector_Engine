import json
import os

from depth_brain import ops_summary
from depth_brain.publish import publish
from depth_brain.writer import DryRunWriter
from tests.test_shadow_control import MAN, NOW2, pilot_states

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(HERE, "runtime", "knowledge", "claim_levels.json")))
CL = D["claims"]


def test_closed_vocabulary_and_levels():
    assert {c["status"] for c in CL} <= set(D["statusVocabulary"])
    assert {c["level"] for c in CL} <= {1, 2, 3}
    assert len({c["id"] for c in CL}) == len(CL)


def test_every_claim_has_evidence_scope_and_no_customer_exposure():
    for c in CL:
        assert c["evidence"] and c["scope"], c["id"]
        assert c["customerExposure"] == "NONE", c["id"]


def test_level3_claims_are_never_more_than_not_validated():
    for c in CL:
        if c["level"] == 3:
            assert c["status"] in ("NOT_VALIDATED", "NOT_CLAIMED", "CALIBRATION"), c["id"]          # no field truth exists: nothing may be called validated


def test_a_failed_or_unvalidated_claim_does_not_downgrade_provider_truth():
    by = {c["id"]: c for c in CL}
    assert by["knownFlatClass"]["status"] == "NOT_VALIDATED" and by["effectiveZoneBoundsOther"]["status"] == "WITHHELD"
    assert by["currentLakeLevel"]["status"] == "PROVIDER_VERIFIED" and by["levelShift"]["status"] == "VERIFIED" and by["referencePool"]["status"] == "PROVIDER_VERIFIED"


def test_no_claim_covers_what_depth_refuses():
    by = {c["id"]: c for c in CL}
    assert by["absoluteDepthFlatsChannels"]["status"] == "NOT_CLAIMED"
    assert not any(c["status"] in ("VERIFIED", "PROVIDER_VERIFIED", "DESK_VALIDATED") and any(w in c["id"].lower() for w in ("flats", "absolute", "globathy")) for c in CL)


def test_registry_publishes_lifecycle_claims_and_execution_model():
    w = DryRunWriter()
    publish(MAN, pilot_states(), w, NOW2)
    reg = w.tree["brains"]["depth"]
    assert reg["lifecycle"] == "SHADOW" and reg["status"] == "PROFILED"
    assert reg["claims"]["byStatus"] == ops_summary.claim_summary()["byStatus"] and len(reg["claims"]["claims"]) == len(CL)
    ex = reg["execution"]
    assert ex["type"] == "DEPENDENCY_DRIVEN" and ex["clock"] is False and ex["maxStateAgeHours"]["unavailable"] == 48.0
    assert "score" not in reg and reg["scoreStatus"] == "NOT_ESTABLISHED"


def test_mission_lock_and_wake_conditions_are_in_the_spec():
    spec = open(os.path.join(HERE, "BRAIN_SPEC.md")).read()
    assert "MISSION LOCK" in spec and "NOT a hydrographic survey" in spec and "without product approval" in spec
    assert "WAIT STATE" in spec and "point-in-time" in spec
    for w in ("Reclamation", "TVA", "Duke", "Lake publishes", "NWPS", "field/sonar", "control job", "rubric mismatch", "licensing"):
        assert w in spec, w


def test_no_cron_and_no_official_score_anywhere_in_depth_runtime():
    reg_src = open(os.path.join(HERE, "runtime", "depth_brain", "ops_summary.py")).read()
    assert '"clock": False' in reg_src and "NOT_ESTABLISHED" in reg_src
    assert "cron" not in open(os.path.join(HERE, "runtime", "run.py")).read().lower().replace("no cron", "")


def test_claim_scopes_are_computed_from_the_manifest_not_hardcoded():
    from depth_brain.fleet import fleet_metrics
    fm = fleet_metrics(MAN)
    cs = {c["id"]: c["scope"] for c in ops_summary.claim_summary(fm)["claims"]}
    assert cs["levelShift"].startswith(f"{fm['shiftPossible']} lakes defensible")
    assert str(fm["ratingZoneLakes"]) in cs["ratingZoneShares"] and "{" not in "".join(cs.values())
    raw = {c["id"]: c["scope"] for c in CL}
    assert not any(ch.isdigit() for ch in raw["levelShift"].replace("{shiftPossible}", "").replace("{pilotVerified}", ""))


def test_rated_lake_claims_never_exceed_what_the_evidence_supports():
    by = {c["id"]: c for c in CL}
    assert by["ratingZoneShares"]["level"] == 2 and by["ratingZoneShares"]["status"] == "VERIFIED"
    assert "never where" in by["ratingZoneShares"]["scope"] and "0.127" in by["ratingZoneShares"]["evidence"]
    assert by["knownFlatClass"]["status"] == "NOT_VALIDATED"          # no field truth, so no Level-3 class is claimed because shares exist
