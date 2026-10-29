"""Cortex 3.1 data ownership as the Engine enforces it: Brains produce; the Publisher is the target writer; the Orchestrator owns operational records; the Scorer owns scores."""
import pytest

from sector_brain_platform import data_ownership as DO
from sector_brain_platform.keys import BRAINS
from sector_brain_platform.ownership import OwnershipError, PLATFORM_WRITER, assert_owned, path_allowed
from sector_brain_platform.publisher_live.security_model import ORCHESTRATOR, PUBLISHER, SCORER, SPECIALIST, rtdb_write_allowed


def test_the_engine_ownership_table_has_no_conflict_with_the_cortex_registry():
    assert DO.audit() == []


def test_roles_are_separate_orchestrator_owns_control_scorer_owns_scores_nobody_overlaps():
    for p in ("control/orchestratorV1", "control/fleet/probe_lake", "jobs/x", "health/engine/api", "health/rtdb"):
        assert rtdb_write_allowed(ORCHESTRATOR, p) and not rtdb_write_allowed(SCORER, p), p
    for p in ("scores/wind", "scores/engine", "engine/score"):
        assert rtdb_write_allowed(SCORER, p) and not rtdb_write_allowed(ORCHESTRATOR, p), p
    for role in (ORCHESTRATOR, SCORER):
        assert not rtdb_write_allowed(role, "lakes/probe_lake/states/wind"), role              # neither platform role writes Brain intelligence
        assert not rtdb_write_allowed(role, "species/bluegill")


def test_only_the_publisher_writes_brain_intelligence_in_the_target_and_it_never_writes_platform_paths():
    assert rtdb_write_allowed(PUBLISHER, "lakes/probe_lake/states/wind", brain_id="wind")
    for p in ("scores/wind", "control/orchestratorV1", "jobs/x", "health/jobs/x", "brains/wind/score"):
        assert not rtdb_write_allowed(PUBLISHER, p, brain_id="wind"), p
    assert not rtdb_write_allowed(SPECIALIST, "lakes/probe_lake/states/wind", brain_id="wind", phase="TARGET")      # target: a specialist writes nothing
    assert rtdb_write_allowed(SPECIALIST, "lakes/probe_lake/states/wind", brain_id="wind", phase="CURRENT")        # today: direct writers stay operational until their cutover


def test_existing_direct_writers_keep_every_path_production_uses():
    for b, p in (("wind", "lakes/k/states/wind"), ("lake-brain", "lakes/k/states/lake"), ("water-temp", "lakeFleet/k/slots/waterTemp"), ("biological-state", "species/bluegill"),
                 ("wind", "brains/wind/lastSuccessfulRun"), ("wind", "brains/wind/scores"), ("sector-intelligence", "snapshots/k/latest/sectorIntelligence"), ("depth", "validation/depth/x"),
                 ("water-clarity", "health/brains/water-clarity/status"), ("lake-brain", "lakes/k/speciesPresence/x")):
        assert path_allowed(b, p), (b, p)
    assert path_allowed(PLATFORM_WRITER, "scores/wind") and path_allowed(PLATFORM_WRITER, "control/orchestratorV1") and path_allowed(PLATFORM_WRITER, "jobs/probe")


def test_whole_node_and_shared_key_overwrites_are_refused():
    assert not path_allowed("biological-state", "species")                                 # the whole /species root
    assert not path_allowed("wind", "brains/wind/score") and not path_allowed("depth", "brains/depth/scores")
    with pytest.raises(OwnershipError):
        assert_owned({"brains/wind": {"status": "OK", "score": {"value": 1}}}, "wind")      # a whole-node write that would erase the scorer's field
    assert_owned({"brains/wind": {"status": "OK", "scores": {"x": 1}}}, "wind")             # the registered LEGACY wind family is allowed
    assert_owned({"brains/wind/status": "OK"}, "wind")


def test_external_admin_families_are_never_a_platform_write():
    assert not path_allowed(PLATFORM_WRITER, "access/opsUsers/u1") and not path_allowed(PLATFORM_WRITER, "control/executionControlV1")
    assert not any(path_allowed(b, "control/executionControlV1") or path_allowed(b, "access/opsUsers/u1") for b in BRAINS)


def test_brains_cannot_write_other_brains_keys():
    for a in BRAINS:
        for b in BRAINS:
            if a != b:
                assert not path_allowed(a, f"brains/{b}/status") and not path_allowed(a, f"validation/{b}/x") and not path_allowed(a, f"health/brains/{b}/status")


def test_pre_cutover_direct_writers_are_reported_as_information_with_their_publisher_target():
    fams = {x["family"]: x for x in DO.pre_cutover_direct_writes()}
    assert {"fam.brains", "fam.species", "fam.lake-states", "fam.lakefleet", "fam.snapshots", "fam.validation", "fam.activity", "fam.lake-brain-node"} <= set(fams)
    assert all(x["targetWriter"] == "platform.publisher-live" for x in fams.values())
    assert "fam.scores" not in fams and "fam.control-orchestrator-v1" not in fams                  # scores and control never go through the Publisher


def test_registry_lookup_resolves_children_to_their_family_and_writer():
    assert DO.registered_writer("/brains/wind/publication")["family"] == "fam.brains"
    assert DO.registered_writer("/lakeFleet/k/lastUpdatedAt")["family"] == "fam.lakefleet-last-updated" and DO.registered_writer("/lakeFleet/k/lastUpdatedAt")["current"] == "none"
    assert DO.registered_writer("/scores/wind")["current"] == "platform.scorer"
    assert DO.registered_writer("/health/brains/wind")["target"] == "platform.orchestrator"
    assert DO.registered_writer("/nope")["current"] == "UNREGISTERED"
