"""SEC-1 / SEC-2 (repository side). REPO_READY only: all enforcement here is against FAKE clients; LIVE_SECURITY_VERIFIED (rules + IAM) is a separate, later fact."""
import json
import os

import pytest

from live_rig import Rig
from gatep_fixtures import bundle
from sector_brain_platform.keys import BRAINS
from sector_brain_platform.publisher_live import security_model as SM
from sector_brain_platform.publisher_live.fakes import FakeRtdb
from sector_brain_platform.publisher_live.rtdb_client import RtdbRestPublisherClient

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


@pytest.mark.parametrize("key", ["scores/wind", "scores/wind/score", "control/healthV1/x", "engine/score", "jobs/wind-hourly", "access/x", "schemaVersion", "controlRequests/r1",
                                 "health/jobs/wind-hourly", "health/engine/x", "health/rtdb/x", "brains/wind/score", "brains/water-clarity/status", "lakeFleet/k/lakeId",
                                 "snapshots/k/latest/lakeId", "health/brains/wind/lastRun", "health/brains/wind/latestError", "validationOps/x", "species/x"])
def test_the_publisher_can_never_write_platform_foreign_or_orchestrator_owned_paths_for_wind(key):
    assert not SM.publisher_key_allowed("wind", key)


@pytest.mark.parametrize("brain,key", [("wind", "lakes/k/states/wind"), ("wind", "brains/wind/version"), ("wind", "brains/wind/publication"), ("wind", "health/brains/wind/status"),
                                       ("biological-state", "species/example_fish"), ("biological-state", "brains/biological-state/status"),
                                       ("water-clarity", "lakes/k/states/waterClarity"), ("water-clarity", "brains/water-clarity/version")])
def test_the_publisher_can_write_exactly_the_producing_brains_own_families(brain, key):
    assert SM.publisher_key_allowed(brain, key)


def test_cross_domain_writes_are_denied_for_the_publisher_acting_for_another_brain():
    assert not SM.publisher_key_allowed("wind", "lakes/k/states/waterClarity")
    assert not SM.publisher_key_allowed("water-clarity", "lakes/k/states/wind")
    assert not SM.publisher_key_allowed("biological-state", "brains/wind/version")


def test_principal_matrix_specialist_ops_denied_in_target_publisher_success_and_current_reality_is_visible():
    db = FakeRtdb()
    key = {"lakes/k/states/wind": {"windMS": 1}}
    for principal in (SM.SPECIALIST, SM.OPS):
        with pytest.raises(SM.AccessDenied):
            SM.PrincipalGuardedRtdb(db, principal, brain_id="wind").update(key)
    SM.PrincipalGuardedRtdb(db, SM.PUBLISHER, brain_id="wind").update(key)                     # tested success
    assert db.get("lakes/k/states/wind") == {"windMS": 1}
    SM.PrincipalGuardedRtdb(FakeRtdb(), SM.SPECIALIST, brain_id="wind", phase="CURRENT").update(key)      # TODAY a specialist can: the gap exit evidence F closes
    with pytest.raises(SM.AccessDenied):
        SM.PrincipalGuardedRtdb(db, SM.PUBLISHER, brain_id="wind").update({"scores/wind": 1})
    with pytest.raises(SM.AccessDenied):
        SM.PrincipalGuardedRtdb(db, SM.ORCHESTRATOR, brain_id="wind").update({"brains/wind/version": "x"})         # platform identities do not write Brain domain data
    SM.PrincipalGuardedRtdb(db, SM.SCORER).update({"scores/wind": {"score": 3.3}})
    with pytest.raises(SM.AccessDenied):
        SM.PrincipalGuardedRtdb(db, SM.OPS).update({"scores/wind": 1})


def test_the_live_publisher_refuses_a_forbidden_key_even_if_a_plan_somehow_contained_it():
    with pytest.raises(SM.AccessDenied):
        SM.assert_publisher_keys("wind", {"lakes/k/states/wind": {"a": 1}, "scores/wind": 1})


def test_store_capabilities_publisher_has_no_delete_and_specialists_are_create_only_on_their_own_prefix():
    caps = SM.STORE_CAPABILITIES
    assert all(not c["delete"] for c in caps.values()) and caps["ops"]["read"] == () and caps["specialist"]["overwrite"] == ()
    assert "artifacts/" not in caps["publisher"]["create_only"] and "artifacts/" in caps["publisher"]["read"]


def test_sec2_multi_writer_collision_inventory_is_pinned_so_a_new_collision_cannot_appear_silently():
    multi = SM.current_multi_writer_paths()
    assert set(multi) == set(SM.TARGET_PLATFORM_OWNED_COLLISIONS)
    assert all(multi[p] == sorted(BRAINS) for p in multi), multi          # today EVERY registered Brain may write these platform-owned paths (legacy behaviour, unchanged here)
    for p in SM.TARGET_PLATFORM_OWNED_COLLISIONS:
        assert not any(SM.publisher_key_allowed(b, p.replace("{k}", "k").replace("{id}", "j")) for b in BRAINS)    # ...and the Publisher writes none of them


def test_the_security_plan_json_is_generated_from_the_model_and_claims_only_repo_ready():
    on_disk = json.load(open(os.path.join(REPO, "platform", "security", "publisher_security_plan.json")))
    assert on_disk == json.loads(json.dumps(SM.security_plan()))
    assert on_disk["status"] == "REPO_READY" and on_disk["liveSecurityVerified"] is False and on_disk["liveOnlyEvidence"]


def test_target_rtdb_rules_deny_every_client_write_on_every_domain_root():
    rules = json.load(open(os.path.join(REPO, "platform", "security", "rtdb.rules.target.json")))["rules"]

    def writes(node, path=""):
        for k, v in node.items():
            if k == ".write":
                assert v is False, f"{path}/{k} must be false"
            elif isinstance(v, dict):
                writes(v, f"{path}/{k}")
    writes(rules)
    roots = {"lakes", "lakeFleet", "snapshots", "brains", "validation", "health", "sources", "activity", "species", "speciesProfiles", "scores", "control", "jobs", "engine", "access",
             "validationOps", "schemaVersion", "controlRequests"}
    assert roots <= set(rules) and rules[".write"] is False and rules["access"][".read"] is False
    assert rules["brains"][".write"] is False


def test_production_clients_cannot_be_constructed_unarmed():
    with pytest.raises(PermissionError):
        RtdbRestPublisherClient("https://example-sector-brain.invalid", brain_id="wind")
    c = RtdbRestPublisherClient("https://sector-brain.firebaseio.com", brain_id="wind", armed=True, transport=lambda *a: (200, "null"), tokens=type("T", (), {"token": lambda s: "t"})())
    with pytest.raises(SM.AccessDenied):
        c.update({"scores/wind": 1})                                       # refused BEFORE the transport is reached
    from sector_brain_platform.publisher_live.model import RtdbAmbiguousFailure, RtdbDefiniteFailure
    c4 = RtdbRestPublisherClient("https://sector-brain.firebaseio.com", brain_id="wind", armed=True, transport=lambda *a: (403, "denied"), tokens=type("T", (), {"token": lambda s: "t"})(), attempts=1)
    with pytest.raises(RtdbDefiniteFailure):
        c4.update({"lakes/k/states/wind": {"a": 1}})
    c5 = RtdbRestPublisherClient("https://sector-brain.firebaseio.com", brain_id="wind", armed=True, transport=lambda *a: (503, "x"), tokens=type("T", (), {"token": lambda s: "t"})(),
                                 attempts=1, sleep=lambda s: None)
    with pytest.raises(RtdbAmbiguousFailure):
        c5.update({"lakes/k/states/wind": {"a": 1}})
