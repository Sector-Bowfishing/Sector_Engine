"""Brain Orchestrator decision model + control state (orchestrator-control-v1). Uses the committed execution manifest and small synthetic ones."""
import copy
import os
import datetime as dt
import json

import pytest

from sector_brain_platform import orchestration as O, control_state as C, fingerprint as F

NOW = dt.datetime(2026, 10, 14, 18, 0, tzinfo=dt.timezone.utc)


def iso(h_ago):
    return (NOW - dt.timedelta(hours=h_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


#: Orchestration-ALGORITHM scenario edges for the Biological Brain as a downstream consumer (wake-on-change, waves, optional-stale handling).
#: The COMMITTED manifest declares none for Fish: the Fish runtime consumes no other Brain's state, and the platform must not claim
#: relationships a registered Brain does not declare (dependency_declarations.drift; Fish Structural Certification V1). These scenarios
#: test the decision model, not Fish's contract, so they re-attach the former provisional edges to a COPY of the committed manifest.
SCENARIO_FISH_EDGES = [
    {"id": "wind", "requirement": "OPTIONAL", "maxAgeHours": 6, "onStale": "DEPENDENCY_STALE", "provisional": True},
    {"id": "water-temp", "requirement": "OPTIONAL", "maxAgeHours": 48, "onStale": "DEPENDENCY_STALE", "provisional": True},
    {"id": "water-clarity", "requirement": "OPTIONAL", "maxAgeHours": 72, "onStale": "DEPENDENCY_STALE", "provisional": True},
    {"id": "lake-brain", "requirement": "OPTIONAL", "maxAgeHours": 24, "onStale": "DEPENDENCY_STALE", "provisional": True},
]


def committed_manifest():
    return O.load_manifest()


#: Decision-model scenarios run on a FROZEN copy of the pre-activation manifest (2026-10-20: Water Temp, Intelligence PARKED; Clarity MANUAL) so
#: they keep testing parking, change gating and policy semantics independently of which Brains the live board has activated. The live board
#: (internal activation 2026-10-22) is asserted separately on committed_manifest().
PRE_ACTIVATION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "control_manifest_pre_activation_2026-10-20.json")


def manifest():
    m = O.load_manifest(PRE_ACTIVATION)
    m["brains"]["biological-state"]["dependencies"] = copy.deepcopy(SCENARIO_FISH_EDGES)
    return m


def ctx(m=None, states=None, activity=None, running=None, out_fps=None, last_in_fps=None, mode="PRE_PRODUCTION"):
    m = m or manifest()
    return {"manifest": m, "mode": mode, "now": NOW, "states": states or {}, "activity": activity or O.effective_activity(m), "running": running or {},
            "out_fps": out_fps or {}, "last_in_fps": last_in_fps or {}}


def fresh_states(m, hours=1.0):
    return {b: {"lastSuccessfulRun": iso(hours)} for b in m["brains"]}


def tiny(**brains):
    """A synthetic manifest: {id: (activity, deps, allowed)}."""
    m = {"engineMode": "PRE_PRODUCTION", "brains": {}, "jobs": {}}
    for bid, (act, deps, allowed) in brains.items():
        m["brains"][bid] = {"displayName": bid, "group": "FOUNDATION", "lifecycle": "SHADOW", "activityState": act, "allowedTriggers": allowed,
                            "dependencies": [{"id": d, "requirement": "OPTIONAL", "maxAgeHours": 24, "onStale": "DEPENDENCY_STALE"} for d in deps],
                            "schedule": {"class": "MANUAL"}, "costClass": "LOW", "freshness": {"stalenessModel": "FINGERPRINT"}, "customerPublication": False}
    return m


# ------------------------------------------------------------------------------------------------ manifest, mode, graph
def test_committed_manifest_is_valid_and_graph_is_acyclic():
    m = committed_manifest()
    assert O.validate_manifest(m) == []
    g = O.validate_graph(m)
    assert g["errors"] == [] and g["warnings"] == [] and set(g["order"]) == set(m["brains"])
    assert g["order"].index("lake-brain") < g["order"].index("depth") and g["order"].index("biological-state") < g["order"].index("sector-intelligence")
    assert m["brains"]["biological-state"]["dependencies"] == []        # Fish consumes no other Brain; brains/fish/brain.json declares none


def test_scenario_manifest_with_fish_as_downstream_consumer_is_valid_and_acyclic():
    m = manifest()
    assert O.validate_manifest(m) == []
    g = O.validate_graph(m)
    assert g["errors"] == [] and g["warnings"] == []
    assert g["order"].index("wind") < g["order"].index("biological-state") < g["order"].index("sector-intelligence")


def test_current_board_is_configuration_not_code():
    m = manifest()
    act = O.effective_activity(m)
    assert {b for b, s in act.items() if s == "ACTIVE"} == {"wind", "biological-state", "water-clarity"}
    assert {b for b, s in act.items() if s == "PARKED"} == {"water-temp", "depth", "vegetation", "sector-intelligence"}
    assert act["lake-brain"] == "MAINTENANCE"
    m2 = copy.deepcopy(m); m2["brains"]["depth"]["activityState"] = "ACTIVE"
    assert O.effective_activity(m2)["depth"] == "ACTIVE"                                  # change the config, not the code
    assert O.effective_activity(m, {"wind": {"activityState": "PARKED"}})["wind"] == "PARKED"    # accepted override


def test_cycle_detection_fails_closed_and_missing_metadata_is_visible():
    m = tiny(a=("ACTIVE", ["b"], ["MANUAL"]), b=("ACTIVE", ["c"], ["MANUAL"]), c=("ACTIVE", ["a"], ["MANUAL"]))
    g = O.validate_graph(m)
    assert any("cycle" in e for e in g["errors"]) and g["order"] == []
    m = tiny(a=("ACTIVE", ["ghost"], ["MANUAL"]))
    assert any("unknown Brain" in e for e in O.validate_graph(m)["errors"])
    m = tiny(a=("ACTIVE", ["a"], ["MANUAL"]))
    assert any("depends on itself" in e for e in O.validate_graph(m)["errors"])
    m = tiny(a=("ACTIVE", [], ["MANUAL"])); del m["brains"]["a"]["dependencies"]
    assert O.validate_graph(m)["warnings"] and not O.validate_graph(m)["errors"]
    with pytest.raises(O.ManifestError):
        O.plan_waves(["a", "b"], tiny(a=("ACTIVE", ["b"], []), b=("ACTIVE", ["a"], [])))


def test_manifest_forbids_customer_publication_in_pre_production():
    m = manifest(); m["brains"]["wind"]["customerPublication"] = True
    assert any("customerPublication" in e for e in O.validate_manifest(m))
    assert O.publish_allowed("PRE_PRODUCTION", {"customerPublication": True, "lifecycle": "PRODUCTION"}) is False
    assert O.publish_allowed("PRODUCTION", {"customerPublication": True, "lifecycle": "SHADOW"}) is False


def test_non_pre_production_mode_fails_closed():
    d = O.decide_brain("wind", "MANUAL", ctx(mode="PRODUCTION"))
    assert d["decision"] == "BLOCKED_POLICY" and d["reasonCode"] == "MODE_UNDEFINED"


# ------------------------------------------------------------------------------------------------ schedule evaluation and policy
def test_wind_hourly_is_a_preserved_validation_exception_owned_by_the_legacy_scheduler():
    m = manifest(); w = m["brains"]["wind"]
    assert w["schedule"]["class"] == "VALIDATION_EXCEPTION" and w["schedule"]["cron"] == "5 * * * *"
    ok, why = O.schedule_policy(w, "PRE_PRODUCTION")
    assert ok and "approved" in why
    d = O.decide_brain("wind", "SCHEDULE", ctx(m, fresh_states(m, 5)))
    assert d["decision"] == "SKIP_LEGACY_OWNED"             # the orchestrator never double-starts it, and never disables it either
    assert O.decide_brain("wind", "VALIDATION", ctx(m))["decision"] == "RUN"


def test_pre_production_recurring_schedule_needs_gate_cost_stop_and_unrecreatable_evidence():
    b = copy.deepcopy(manifest()["brains"]["wind"])
    for k in ("gate", "notReconstructable", "maxMonthlyUsd", "stop", "approvedAt"):
        b2 = copy.deepcopy(b); del b2["schedule"]["exception"][k]
        ok, why = O.schedule_policy(b2, "PRE_PRODUCTION")
        assert not ok and k in why
    m = tiny(x=("ACTIVE", [], ["SCHEDULE"]))
    m["brains"]["x"]["schedule"] = {"class": "ORCHESTRATOR_OWNED", "owner": "ORCHESTRATOR"}
    d = O.decide_brain("x", "SCHEDULE", ctx(m))
    assert d["decision"] == "BLOCKED_POLICY" and d["reasonCode"] == "RECURRING_OFF_BY_DEFAULT"
    assert O.schedule_policy(b, "PRODUCTION")[0] is False


def test_biological_has_no_cron_and_runs_only_on_manual_input_or_dependency_triggers():
    m = manifest(); b = m["brains"]["biological-state"]
    assert "SCHEDULE" not in b["allowedTriggers"] and b["schedule"]["class"] == "INPUT_DRIVEN" and not b["schedule"].get("cron")
    assert not [j for j in m["jobs"].values() if j.get("brainId") == "biological-state"]       # no cloud job at all
    d = O.decide_brain("biological-state", "SCHEDULE", ctx(m))
    assert d["decision"] == "SKIP_NOT_DUE" and d["reasonCode"] == "NO_SCHEDULE_INTENT"
    assert O.decide_brain("biological-state", "MANUAL", ctx(m, fresh_states(m)))["decision"] == "RUN"


def test_time_due_schedule_for_an_orchestrator_owned_approved_job():
    m = tiny(x=("ACTIVE", [], ["SCHEDULE"]))
    m["brains"]["x"]["freshness"] = {"staleAfterHours": 3}
    m["brains"]["x"]["schedule"] = {"class": "ORCHESTRATOR_OWNED", "owner": "ORCHESTRATOR",
                                    "exception": {"gate": "g", "notReconstructable": "n", "maxMonthlyUsd": 1, "stop": "s", "approvedAt": "2026-10-14"}}
    assert O.decide_brain("x", "SCHEDULE", ctx(m, {"x": {"lastSuccessfulRun": iso(1)}}))["decision"] == "SKIP_NOT_DUE"
    assert O.decide_brain("x", "SCHEDULE", ctx(m, {"x": {"lastSuccessfulRun": iso(4)}}))["decision"] == "RUN"
    assert O.decide_brain("x", "SCHEDULE", ctx(m, {}))["decision"] == "RUN"                  # never run


# ------------------------------------------------------------------------------------------------ active / parked / maintenance
def test_parked_brains_do_not_wake_automatically_but_manual_is_allowed():
    m = manifest(); s = fresh_states(m)
    d = O.decide_brain("sector-intelligence", "DEPENDENCY_CHANGED", ctx(m, s), upstream={"brainId": "wind", "change": "CHANGED"})
    assert d["decision"] == "SKIP_PARKED"
    assert O.decide_brain("sector-intelligence", "INPUT_CHANGED", ctx(m, s))["decision"] == "SKIP_NOT_DUE"      # not even an accepted trigger
    assert O.decide_brain("sector-intelligence", "MANUAL", ctx(m, s))["decision"] == "RUN"
    assert O.decide_brain("water-temp", "SCHEDULE", ctx(m, s))["decision"] in ("SKIP_NOT_DUE", "SKIP_PARKED")
    assert O.decide_brain("water-temp", "RECOVERY", ctx(m, s))["decision"] in ("SKIP_PARKED", "BLOCKED_POLICY")


def test_maintenance_runs_only_approved_operations_and_never_expands_downstream():
    m = manifest(); s = fresh_states(m)
    assert O.decide_brain("lake-brain", "VALIDATION", ctx(m, s))["decision"] == "RUN"        # the ledger capture
    d = O.decide_brain("lake-brain", "INPUT_CHANGED", ctx(m, s))
    assert d["decision"] in ("SKIP_PARKED", "SKIP_NOT_DUE")                                   # not allowed trigger or limited maintenance: no expansion
    for cons in ("depth", "vegetation"):
        assert O.decide_brain(cons, "DEPENDENCY_CHANGED", ctx(m, s), upstream={"brainId": "lake-brain", "change": "CHANGED"})["decision"] != "RUN"


def test_parked_brain_with_validation_exception_only_runs_validation():
    m = manifest(); m["brains"]["water-temp"]["allowedTriggers"].append("VALIDATION")
    assert O.decide_brain("water-temp", "VALIDATION", ctx(m))["decision"] == "SKIP_PARKED"   # no approved exception -> stays parked


# ------------------------------------------------------------------------------------------------ dependency freshness, state read vs run
def test_fresh_parked_dependency_is_read_not_woken():
    m = manifest()
    s = fresh_states(m, 1)
    d = O.decide_brain("biological-state", "MANUAL", ctx(m, s))
    assert d["decision"] == "RUN"
    rows = {r["id"]: r for r in d["dependencyState"]}
    assert rows["water-temp"]["status"] == "FRESH" and rows["water-temp"]["action"] == "READ_EXISTING"   # Water Temp is PARKED and stays untouched
    assert "runDependencies" not in d


def test_stale_optional_dependency_does_not_block_but_is_recorded():
    m = manifest()
    s = fresh_states(m, 1); s["water-temp"] = {"lastSuccessfulRun": iso(500)}
    d = O.decide_brain("biological-state", "MANUAL", ctx(m, s))
    row = next(r for r in d["dependencyState"] if r["id"] == "water-temp")
    assert d["decision"] == "RUN" and row["status"] == "STALE" and row["action"] == "IGNORED_OPTIONAL"


def test_required_dependency_policies():
    m = manifest()
    stale = {"lake-brain": {"lastSuccessfulRun": iso(1000)}}
    assert O.decide_brain("depth", "MANUAL", ctx(m, stale))["decision"] == "MANUAL_APPROVAL"       # Depth's policy for a stale Lake
    m["brains"]["depth"]["dependencies"][0]["onStale"] = "DEPENDENCY_STALE"
    d = O.decide_brain("depth", "MANUAL", ctx(m, stale))
    assert d["decision"] == "BLOCKED_DEPENDENCY" and "lake-brain" in d["reason"]
    m["brains"]["depth"]["dependencies"][0]["onStale"] = "RUN_DEPENDENCY"
    d = O.decide_brain("depth", "MANUAL", ctx(m, stale))                                            # lake-brain is MAINTENANCE: not woken implicitly
    assert d["decision"] == "BLOCKED_DEPENDENCY" and "not woken" in d["reason"]
    act = O.effective_activity(m); act["lake-brain"] = "ACTIVE"
    d = O.decide_brain("depth", "MANUAL", ctx(m, stale, activity=act))
    assert d["decision"] == "WAITING" and d["runDependencies"] == ["lake-brain"]
    assert O.decide_brain("depth", "MANUAL", ctx(m, {}))["decision"] != "RUN"                       # missing upstream state is not fresh


def test_unknown_dependency_freshness_stays_unknown_and_blocks_a_required_edge():
    dep = {"id": "x", "requirement": "REQUIRED", "onStale": "DEPENDENCY_STALE"}
    assert O.dep_status(dep, {"lastSuccessfulRun": iso(1)}, NOW) == "UNKNOWN"
    assert O.dep_status(dep, {"lastSuccessfulRun": iso(1), "stale": False}, NOW) == "FRESH"
    assert O.dep_status(dep, None, NOW) == "MISSING"


# ------------------------------------------------------------------------------------------------ material change
def test_classify_change_keeps_unknown_unknown():
    assert O.classify_change("a", "a") == "UNCHANGED" and O.classify_change("a", "b") == "CHANGED"
    assert O.classify_change(None, "b") == "CHANGED" and O.classify_change("a", None) == "UNKNOWN" and O.classify_change(None, None) == "UNKNOWN"


def test_no_material_change_means_downstream_does_not_run():
    m = manifest(); s = fresh_states(m)
    fps = {"wind": "w1"}
    c = ctx(m, s, out_fps=fps)
    ev = O.evaluate_world(c, prev_out_fps={"wind": "w1"})
    assert ev["changes"]["wind"] == "UNCHANGED"
    bio = [d for d in ev["decisions"] if d["brainId"] == "biological-state" and d["trigger"] == "DEPENDENCY_CHANGED"][0]
    intel = [d for d in ev["decisions"] if d["brainId"] == "sector-intelligence" and d["trigger"] == "DEPENDENCY_CHANGED"][0]
    assert bio["decision"] in ("SKIP_UNCHANGED", "SKIP_UNKNOWN_CHANGE") and intel["decision"] in ("SKIP_PARKED", "SKIP_UNCHANGED")
    d = O.decide_brain("biological-state", "DEPENDENCY_CHANGED", c, upstream={"brainId": "wind", "change": "UNCHANGED"})
    assert d["decision"] == "SKIP_UNCHANGED" and d["reasonCode"] == "NO_MATERIAL_CHANGE"


def test_material_change_wakes_only_active_consumers_that_accept_it():
    m = manifest(); s = fresh_states(m)
    c = ctx(m, s, out_fps={"wind": "w2"})
    ev = O.evaluate_world(c, prev_out_fps={"wind": "w1"})
    assert ev["changes"]["wind"] == "CHANGED"
    by = {d["brainId"]: d for d in ev["decisions"] if d["trigger"] == "DEPENDENCY_CHANGED"}
    assert by["biological-state"]["decision"] == "RUN" and by["biological-state"]["reasonCode"] == "DEPENDENCY_CHANGED"
    assert by["sector-intelligence"]["decision"] == "SKIP_PARKED"                      # parked consumer is not woken
    assert ev["runs"] == ["biological-state"]


def test_consumer_input_fingerprint_equal_to_last_processed_skips():
    m = manifest(); s = fresh_states(m)
    c = ctx(m, s, out_fps={"wind": "w2"})
    first = O.decide_brain("biological-state", "DEPENDENCY_CHANGED", c, upstream={"brainId": "wind", "change": "CHANGED"})
    assert first["decision"] == "RUN"
    c2 = ctx(m, s, out_fps={"wind": "w2"}, last_in_fps={"biological-state": first["inputFingerprint"]})
    again = O.decide_brain("biological-state", "DEPENDENCY_CHANGED", c2, upstream={"brainId": "wind", "change": "CHANGED"})
    assert again["decision"] == "SKIP_UNCHANGED" and again["reasonCode"] == "INPUT_FP_UNCHANGED"


def test_changed_field_relevance_filter():
    m = manifest(); m["brains"]["biological-state"]["dependencies"][0]["usesFields"] = ["readinessCounts"]
    s = fresh_states(m)
    c = ctx(m, s, out_fps={"wind": "w2"})
    c["changed_fields"] = {"wind": ["version"]}
    ev = O.evaluate_world(c, prev_out_fps={"wind": "w1"})
    bio = [d for d in ev["decisions"] if d["brainId"] == "biological-state" and d["trigger"] == "DEPENDENCY_CHANGED"][0]
    # wind changed, but Biological's other deps (UNKNOWN fingerprints) are not CHANGED -> no run because the only changed edge is not used
    assert bio["decision"] != "RUN"


def test_first_observation_without_baseline_is_unknown_and_never_cascades():
    m = manifest(); s = fresh_states(m)
    ev = O.evaluate_world(ctx(m, s, out_fps={"wind": "w2", "biological-state": "b1"}), prev_out_fps=None)
    assert set(ev["changes"].values()) == {"UNKNOWN"} and ev["runs"] == []


def test_output_fingerprint_sources():
    m = manifest()
    reg = {"fingerprint": "9b8a26aa7170b04d"}
    assert O.output_fingerprint(m["brains"]["sector-intelligence"], reg) == ("9b8a26aa7170b04d", "BRAIN_OWNED")
    w = m["brains"]["wind"]
    a = O.output_fingerprint(w, {"version": "1", "readinessCounts": {"a": 1}, "lastSuccessfulRun": "t1"})
    b = O.output_fingerprint(w, {"version": "1", "readinessCounts": {"a": 1}, "lastSuccessfulRun": "t2"})
    assert a == b and a[1] == "REGISTRY_PROJECTION"                                 # run time is not material
    assert O.output_fingerprint(w, {"version": "2", "readinessCounts": {"a": 1}})[0] != a[0]
    assert O.output_fingerprint(w, {}) == (None, "UNKNOWN")


# ------------------------------------------------------------------------------------------------ concurrency
def test_independent_brains_run_in_parallel_and_dependents_wait_a_wave():
    m = manifest()
    assert O.plan_waves(["wind", "water-clarity"], m) == [["water-clarity", "wind"]]
    waves = O.plan_waves(["wind", "water-clarity", "biological-state", "sector-intelligence"], m)
    assert waves[0] == ["water-clarity", "wind"] and waves[1] == ["biological-state"] and waves[2] == ["sector-intelligence"]
    assert O.plan_waves([], m) == []


def test_duplicate_run_is_prevented_by_single_flight_and_locks():
    m = manifest(); s = fresh_states(m)
    d = O.decide_brain("wind", "MANUAL", ctx(m, s, running={"wind|*": {}}))
    assert d["decision"] == "WAITING" and d["reasonCode"] == "ALREADY_RUNNING"
    assert O.decide_brain("water-clarity", "MANUAL", ctx(m, s, running={"water-clarity|guntersville": {}}), scope="guntersville")["decision"] == "WAITING"
    assert O.decide_brain("water-clarity", "MANUAL", ctx(m, s, running={"water-clarity|guntersville": {}}), scope="lake-hartwell")["decision"] == "RUN"   # other scope is independent
    ok, locks = O.acquire_lock({}, "wind|*", "e1", NOW)
    assert ok
    ok2, locks2 = O.acquire_lock(locks, "wind|*", "e2", NOW + dt.timedelta(minutes=5))
    assert not ok2 and locks2 == locks
    ok3, locks3 = O.acquire_lock(locks, "wind|*", "e2", NOW + dt.timedelta(minutes=45))        # expired lock is replaced
    assert ok3 and locks3["wind|*"]["executionId"] == "e2" and locks3["wind|*"]["sequence"] == 2


def test_stale_execution_cannot_commit_over_a_newer_one():
    assert O.may_commit("2026-10-14T10:00:00Z", "2026-10-14T09:00:00Z") is False
    assert O.may_commit("2026-10-14T10:00:00Z", "2026-10-14T10:00:00Z") is True
    assert O.may_commit(None, "2026-10-14T09:00:00Z") is True


# ------------------------------------------------------------------------------------------------ retry, cost
def test_failure_classes_and_bounded_retry():
    assert O.classify_failure("HTTP 503 from provider") == "TRANSIENT_PROVIDER"
    assert O.classify_failure("Container killed: out of memory") == "TRANSIENT_RUNTIME"
    assert O.classify_failure("schema changed: empty response") == "INVALID_INPUT"
    assert O.classify_failure("permission denied 403") == "PERMANENT_CONFIG"
    assert O.classify_failure("upstream dependency blocked") == "DEPENDENCY_BLOCKED"
    pol = {"maxAttempts": 3, "backoffMinutes": [5, 15, 45]}
    r1 = O.retry_decision("TRANSIENT_PROVIDER", 1, pol, NOW)
    assert r1["retry"] and r1["nextAttemptAt"] == "2026-10-14T18:05:00Z"
    assert O.retry_decision("TRANSIENT_RUNTIME", 2, pol, NOW)["nextAttemptAt"] == "2026-10-14T18:15:00Z"
    assert O.retry_decision("TRANSIENT_RUNTIME", 3, pol, NOW)["retry"] is False                    # bounded
    for fc in ("INVALID_INPUT", "PERMANENT_CONFIG", "DEPENDENCY_BLOCKED"):
        assert O.retry_decision(fc, 1, pol, NOW)["retry"] is False
    with pytest.raises(ValueError):
        O.retry_decision("WHATEVER", 1, pol, NOW)


def test_cost_estimate_is_labelled_and_unknown_is_never_zero():
    c = O.estimate_cost({"cpu": 1, "memoryGiB": 2, "tasks": 1}, 198)
    assert c["basis"] == "ESTIMATED" and 0.005 < c["usd"] < 0.007                                    # ~ $0.0057 per Wind run
    assert O.estimate_cost(None, 10) == {"usd": None, "basis": "UNKNOWN"} and O.estimate_cost({"cpu": 1}, None)["usd"] is None
    heavy = O.estimate_cost({"cpu": 4, "memoryGiB": 16, "tasks": 8}, 3100)
    assert 3.0 < heavy["usd"] < 3.7
    ex = [{"startedAt": "2026-10-14T01:00:00Z", "cost": c}, {"startedAt": "2026-10-14T02:00:00Z", "cost": {"usd": None, "basis": "UNKNOWN"}},
          {"startedAt": "2026-10-13T02:00:00Z", "cost": c}]
    r = O.cost_rollup(ex, "2026-10-14")
    assert r["executions"] == 2 and r["unknownExecutions"] == 1 and r["lowerBound"] is True and r["usd"] == c["usd"]
    assert O.cost_rollup([], "2026-10-14") == {"day": "2026-10-14", "executions": 0, "usd": None, "basis": "UNKNOWN", "unknownExecutions": 0, "lowerBound": False}


# ------------------------------------------------------------------------------------------------ control requests
def req(action, bid="wind", **kw):
    return {"requestId": "r1", "requestedBy": "michael", "action": action, "brainId": bid, **kw}


def test_run_now_is_scoped_and_validated_by_policy():
    m = manifest(); c = ctx(m, fresh_states(m))
    r = O.evaluate_request(req("RUN_NOW", "water-clarity"), c)
    assert r["decision"] == "REJECTED" and "explicit scope" in r["reasons"][0]
    r = O.evaluate_request(req("RUN_NOW", "water-clarity", scope="guntersville"), c)
    assert r["decision"] == "ACCEPTED" and "manualCommand" in r and "lake-surface-dispatch" in r["manualCommand"]     # executor cannot scope this job
    assert O.evaluate_request(req("RUN_NOW", "water-clarity", scope="fleet"), c)["decision"] == "REJECTED"             # fleet-wide not allowed for Clarity
    assert O.evaluate_request(req("RUN_NOW", "water-clarity", scope="621-lakes"), c)["decision"] == "REJECTED"
    assert O.evaluate_request(req("RUN_NOW", "biological-state", scope="guntersville"), c)["decision"] == "ACCEPTED"
    assert O.evaluate_request(req("RUN_NOW", "ghost", scope="x"), c)["decision"] == "REJECTED"
    assert O.evaluate_request({"action": "RUN_NOW"}, c)["decision"] == "REJECTED"                                       # no identity
    assert O.evaluate_request(req("DROP_TABLE"), c)["decision"] == "REJECTED"                                          # closed action set


def test_run_now_respects_duplicate_prevention_and_dependency_policy():
    m = manifest(); c = ctx(m, fresh_states(m), running={"biological-state|guntersville": {}})
    r = O.evaluate_request(req("RUN_NOW", "biological-state", scope="guntersville"), c)
    assert r["decision"] == "REJECTED" and "WAITING" in r["reasons"][0]
    c = ctx(m, {"lake-brain": {"lastSuccessfulRun": iso(1000)}})
    r = O.evaluate_request(req("RUN_NOW", "depth", scope="x"), c)
    assert r["decision"] == "REJECTED"                                                                                  # depth has no scopes configured / dependency approval


def test_pause_resume_set_manual_and_protected_actions():
    m = manifest(); c = ctx(m)
    assert O.evaluate_request(req("PAUSE", "biological-state"), c)["effect"] == {"activityState": "PARKED"}
    assert O.evaluate_request(req("RESUME", "depth"), c)["effect"] == {"activityState": "ACTIVE"}
    assert O.evaluate_request(req("SET_MANUAL", "lake-brain"), c)["effect"] == {"scheduleClass": "MANUAL"}
    # pausing validation capture is protected
    r = O.evaluate_request(req("PAUSE", "wind"), c)
    assert r["decision"] == "NEEDS_CONFIRMATION" and r["protected"]
    ok = O.evaluate_request(req("PAUSE", "wind", confirm={"by": "michael", "phrase": "CONFIRM DISABLE_VALIDATION_CAPTURE wind"}), c)
    assert ok["decision"] == "ACCEPTED"
    # fail closed for the rest of the protected set, even when confirmed
    for a in ("SET_ENGINE_MODE", "ACTIVATE_PRODUCTION", "PUBLISH_CUSTOMER", "PROMOTE_LIFECYCLE"):
        assert O.evaluate_request(req(a, "wind"), c)["decision"] == "NEEDS_CONFIRMATION"
        conf = {"by": "michael", "phrase": f"CONFIRM {a} wind"}
        r = O.evaluate_request(req(a, "wind", confirm=conf), c)
        assert r["decision"] == "REJECTED" and "reviewed change" in r["reasons"][0]
        assert O.evaluate_request(req(a, "wind", confirm={"by": "someone-else", "phrase": conf["phrase"]}), c)["decision"] == "NEEDS_CONFIRMATION"
    assert O.evaluate_request(req("CHANGE_PROTECTED_SCHEDULE", "wind", confirm={"by": "michael", "phrase": "CONFIRM CHANGE_PROTECTED_SCHEDULE wind"}), c)["decision"] == "ACCEPTED"


# ------------------------------------------------------------------------------------------------ ledgers and history
def test_execution_ledger_is_bounded_and_records_why():
    started = NOW - dt.timedelta(minutes=3)
    e = O.execution_record("exec-1", "wind", "SCHEDULE", "due by schedule", started, NOW, "SUCCEEDED", input_fp="abc",
                           output_changed="UNCHANGED", resources={"cpu": 1, "memoryGiB": 2, "tasks": 1},
                           downstream=[{"brainId": "biological-state", "decision": "SKIP_UNCHANGED"}])
    assert e["trigger"] == "SCHEDULE" and e["reason"] and e["durationSeconds"] == 180 and e["cost"]["basis"] == "ESTIMATED"
    assert e["downstream"] == [{"brainId": "biological-state", "decision": "SKIP_UNCHANGED"}]
    items = []
    for i in range(O.EXECUTION_LEDGER_MAX + 25):
        items = O.append_bounded(items, {"executionId": f"e{i}"}, O.EXECUTION_LEDGER_MAX, "executionId")
    assert len(items) == O.EXECUTION_LEDGER_MAX and items[0]["executionId"] == f"e{O.EXECUTION_LEDGER_MAX + 24}"
    assert len(O.append_bounded(items, {"executionId": "e90"}, O.EXECUTION_LEDGER_MAX, "executionId")) == O.EXECUTION_LEDGER_MAX      # de-duplicated


def test_infer_trigger_for_legacy_scheduled_executions():
    assert O.infer_trigger(dt.datetime(2026, 10, 14, 5, 5, 17, tzinfo=dt.timezone.utc), "5 * * * *") == "SCHEDULE"
    assert O.infer_trigger(dt.datetime(2026, 10, 14, 5, 40, tzinfo=dt.timezone.utc), "5 * * * *") == "UNKNOWN"      # a manual run mid-hour is not claimed as scheduled
    assert O.infer_trigger(dt.datetime(2026, 10, 14, 12, 1, tzinfo=dt.timezone.utc), "0 12 * * *") == "SCHEDULE"
    assert O.infer_trigger(dt.datetime(2026, 10, 14, 13, 1, tzinfo=dt.timezone.utc), "0 12 * * *") == "UNKNOWN"
    assert O.infer_trigger(NOW, None) == "UNKNOWN"


def world(m, states=None, prev_fps=None, out_fps=None):
    c = ctx(m, states or fresh_states(m), out_fps=out_fps)
    return O.evaluate_world(c, prev_fps)


def test_decision_history_records_changes_not_every_cycle():
    m = manifest()
    ev = world(m)
    latest, recent = C.merge_decisions({}, {}, ev["decisions"])
    n = len(recent)
    assert n == len(ev["decisions"]) or n <= O.DECISION_LEDGER_MAX
    later = [dict(d, at="2026-10-14T19:00:00Z", decisionId=d["decisionId"] + "-2") for d in ev["decisions"]]
    latest2, recent2 = C.merge_decisions(latest, recent, later)
    assert latest2 == latest and len(recent2) == n                    # identical verdicts: nothing rewritten, nothing appended
    flipped = [dict(d) for d in ev["decisions"]]; flipped[0].update(decision="RUN", reasonCode="X", reason="now due", at="2026-10-14T20:00:00Z", decisionId="d-x")
    latest3, recent3 = C.merge_decisions(latest, recent, flipped)
    assert len(recent3) == n + 1 and "d-x" in recent3
    big_latest, big_recent = {}, {}
    for i in range(300):
        d = dict(ev["decisions"][0], decisionId=f"d{i}", at=f"2026-10-15T00:{i % 60:02d}:00Z", decision="RUN", reason=f"r{i}")
        big_latest, big_recent = C.merge_decisions(big_latest, big_recent, [d])
    assert len(big_recent) <= O.DECISION_LEDGER_MAX


# ------------------------------------------------------------------------------------------------ control state schema
def build(m=None, **kw):
    m = m or manifest()
    ev = world(m, kw.pop("states", None), kw.pop("prev_fps", None), kw.pop("out_fps", None))
    args = dict(registries={}, health={}, scores={}, jobs={}, evaluation=ev)
    args.update(kw)
    return C.build_control_state(m, "PRE_PRODUCTION", NOW, **args)


def test_control_state_answers_the_product_questions():
    m = manifest()
    jobs = {"wind-hourly": {"schedulerState": "ENABLED", "cron": "5 * * * *", "schedule": "5 * * * * UTC", "nextScheduledAt": "2026-10-14T19:05:00Z", "runtimeStatus": "HEALTHY",
                            "lastStartedAt": "2026-10-14T18:05:00Z", "durationMs": 177000},
            "lake-brain-ledger-daily": {"schedulerState": "ENABLED", "cron": "0 12 * * *", "nextScheduledAt": "2026-10-15T12:00:00Z"},
            "brain-orchestrator": {"schedulerState": "PAUSED", "cron": "50 * * * *"}}
    regs = {"wind": {"lastSuccessfulRun": iso(0.2), "status": "CALIBRATION", "health": "HEALTHY", "version": "1", "readinessCounts": {"a": 1}}}
    st = build(m, jobs=jobs, registries=regs, scores={"wind": {"value": 3.3, "basis": "COMPUTED"}}, health={"wind": {"status": "HEALTHY"}}, prev_fps={"wind": "x"})
    s = st["summary"]
    assert s["engineMode"] == "PRE_PRODUCTION" and s["version"] == "orchestrator-control-v1" and s["customerPublication"] is False
    assert s["activeBrains"] == ["biological-state", "water-clarity", "wind"] and "water-temp" in s["parkedBrains"] and s["maintenanceBrains"] == ["lake-brain"]
    assert s["nextDue"] == "2026-10-14T19:05:00Z" and s["lastCycle"]["decisionCounts"]
    w = st["brains"]["wind"]
    assert w["executionMode"] == "VALIDATION_EXCEPTION" and w["scoreRef"] == {"path": "/scores/wind", "canonicalScore": 3.3, "scoreStatus": "COMPUTED"}
    assert w["exception"]["stop"] and w["exception"]["maxMonthlyUsd"] == 5 and "gate" in w["exception"]
    assert w["nextDue"] == "2026-10-14T19:05:00Z" and w["customerPublication"] is False and w["decisions"]["SCHEDULE"]["decision"] == "SKIP_LEGACY_OWNED"
    assert st["brains"]["biological-state"]["executionMode"] == "INPUT_DRIVEN" and "nextDue" not in st["brains"]["biological-state"]
    assert st["jobs"]["wind-hourly"]["enabled"] is True and st["jobs"]["lake-surface-dispatch"]["classification"] == "PAUSED"
    assert st["jobs"]["wind-hourly"]["validationOnly"] is True and st["jobs"]["wind-hourly"]["customerImpact"] is False
    assert st["cost"]["enabledMonthlyEstimateUsd"] == pytest.approx(4.1 + 0.08, abs=0.01)           # only enabled jobs
    assert "errors" not in st["graph"] and st["summary"]["graphValid"] is True
    assert "wind__biological-state" in st["edges"] and st["edges"]["wind__biological-state"]["kind"] == "SOFT"


def test_unknown_stays_unknown_in_control_state():
    st = build()
    for b in st["brains"].values():
        assert "scoreRef" not in b and "lastRun" not in b and "nextDue" not in b and "outputFingerprint" not in b
        assert b["outputChanged"] == "UNKNOWN"                                    # no baseline: explicitly unknown, not 'false'
        assert "inputChanged" not in b
        assert "ageHours" not in b.get("freshness", {}) and "stale" not in b.get("freshness", {})
        assert b["costToday"]["usd"] is None if "usd" in b["costToday"] else True
    assert "usd" not in st["summary"]["costToday"] and st["summary"]["costToday"]["basis"] == "UNKNOWN"
    assert "health" not in st                                      # no health published -> nothing invented


def test_control_state_is_json_clean_rtdb_safe_and_free_of_secrets():
    st = build()
    text = json.dumps(st)
    import re
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k; yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    assert not [k for k in keys(st) if re.search(r"[.$#\[\]/]", k)], "illegal RTDB key"
    assert not re.search(r"secret|token|apikey|password|@", text, re.I)
    assert all(x not in text for x in ("NaN", "Infinity"))
    assert C._strip(st) == st                                                       # no empty containers / nulls that RTDB would drop


def test_executions_are_bounded_and_replace_by_id():
    started = NOW - dt.timedelta(minutes=2)
    first = O.execution_record("e1", "wind", "SCHEDULE", "due", started, None, "RUNNING")
    st1 = build(new_executions=[first])
    assert st1["executions"]["e1"]["status"] == "RUNNING"
    done = O.execution_record("e1", "wind", "SCHEDULE", "due", started, NOW, "SUCCEEDED", resources={"cpu": 1, "memoryGiB": 2, "tasks": 1})
    st2 = build(new_executions=[done], prev=st1)
    assert st2["executions"]["e1"]["status"] == "SUCCEEDED" and len(st2["executions"]) == 1                # re-observed execution replaces itself
    assert st2["summary"]["costToday"]["executions"] == 1 and st2["summary"]["costToday"]["usd"] > 0
    many = [O.execution_record(f"x{i}", "wind", "SCHEDULE", "due", started - dt.timedelta(minutes=i), NOW, "SUCCEEDED") for i in range(200)]
    assert len(build(new_executions=many)["executions"]) == O.EXECUTION_LEDGER_MAX


def test_publication_is_content_aware_and_ignores_evaluation_timestamps():
    st = build()
    first = C.changed_paths(st, None)
    assert f"{C.NODE}/summary" in first and len(first) >= 8
    def at(h, prev):
        return C.build_control_state(manifest(), "PRE_PRODUCTION", NOW + dt.timedelta(hours=h), registries={}, health={}, scores={}, jobs={},
                                     evaluation=O.evaluate_world(dict(ctx(), now=NOW + dt.timedelta(hours=h))), prev=prev, trigger="SCHEDULE")
    baseline = at(1, st)                                   # the second evaluation establishes input-fingerprint baselines once
    assert C.changed_paths(at(2, baseline), baseline) == {}                                  # nothing material changed: nothing written (no hourly churn)
    def early(hour, prev):
        t = dt.datetime(2026, 10, 14, hour, 0, tzinfo=dt.timezone.utc)
        return C.build_control_state(manifest(), "PRE_PRODUCTION", t, registries={}, health={}, scores={}, jobs={}, evaluation=O.evaluate_world(dict(ctx(), now=t)), prev=prev)
    b1 = early(1, st); b2 = early(2, b1)
    assert C.changed_paths(early(3, b2), b2) == {}                                            # same day, 1 h later, nothing changed
    assert list(C.changed_paths(early(9, b2), b2)) == [f"{C.NODE}/summary"]                  # heartbeat: only the summary timestamp, only every 6 h
    changed = C.build_control_state(manifest(), "PRE_PRODUCTION", NOW, registries={}, health={}, scores={}, jobs={}, evaluation=O.evaluate_world(ctx()),
                                    prev=st, overrides={"depth": {"activityState": "ACTIVE"}})
    paths = C.changed_paths(changed, st)
    assert f"{C.NODE}/overrides" in paths and f"{C.NODE}/summary" in paths and f"{C.NODE}/edges" not in paths
    gone = dict(changed); gone.pop("blockers", None)
    assert all(v is None for p, v in C.changed_paths(gone, dict(changed, blockers={"00": {"x": 1}})).items() if p.endswith("/blockers"))


def test_clarity_is_targeted_and_heavy_fleet_work_stays_off():
    m = manifest(); c = m["brains"]["water-clarity"]
    assert c["costClass"] == "HEAVY" and c["schedule"]["class"] == "PAUSED" and "SCHEDULE" not in c["allowedTriggers"]
    assert c["scopes"] == ["guntersville", "lake-hartwell"] and c["allowFleetRunNow"] is False
    d = O.decide_brain("water-clarity", "SCHEDULE", ctx(m))
    assert d["decision"] == "SKIP_NOT_DUE"                                         # never woken by the scheduler loop
    assert O.decide_brain("water-clarity", "VALIDATION", ctx(m, fresh_states(m)))["decision"] == "RUN"        # validation-driven, targeted, supported
    jobs = {j: v for j, v in m["jobs"].items() if v["brainId"] == "water-clarity"}
    assert all(v["classification"] == "PAUSED" for v in jobs.values())


def test_every_decision_record_says_why_and_never_publishes():
    ev = world(manifest())
    for d in ev["decisions"]:
        assert d["decision"] in O.DECISIONS and d["trigger"] in O.TRIGGERS and d["reason"] and d["reasonCode"] and d["publish"] is False
        assert d["decisionId"].startswith("d-2026")
    ids = [d["decisionId"] for d in ev["decisions"]]
    assert len(ids) == len(set(ids)), "decision ids must be unique within a cycle"


def test_manifest_has_exactly_one_scheduling_authority():
    """Central scheduling 2026-10-23 (Cortex 2.7.0 PL-15): the ONLY Cloud Scheduler in the execution manifest is brain-orchestrator's. Wind and Lake
    are started by the orchestrator through their jobs; their own schedulers are recorded as deprecated (PAUSED). Every Brain job has no scheduler."""
    m = committed_manifest()
    scheduled = {j for j, v in m["jobs"].items() if v.get("scheduler") and v["classification"] in ("VALIDATION_EXCEPTION", "ORCHESTRATOR_OWNED", "LEGACY")}
    assert scheduled == {"brain-orchestrator"}
    for jid in ("water-temp-brain", "water-clarity-brain", "wind-hourly", "lake-brain"):
        assert m["jobs"][jid]["classification"] == "ORCHESTRATOR_OWNED" and m["jobs"][jid]["scheduler"] is None    # orchestrator-started only
    assert m["jobs"]["wind-hourly"]["deprecatedScheduler"] == "wind-hourly"
    assert m["jobs"]["lake-brain-ledger-daily"]["deprecatedScheduler"] == "lake-brain-ledger-daily" and m["jobs"]["lake-brain-ledger-daily"]["classification"] == "PAUSED"
    for jid in ("lake-surface-dispatch", "lake-surface-daily", "hydrology-hourly", "clarity-current-hourly", "clarity-candidate-shadow", "water-temp-tva-archive"):
        assert m["jobs"][jid]["classification"] == "PAUSED"                                                       # cost freeze unchanged
    for bid, b in m["brains"].items():                                              # every Brain's automatic execution goes through the orchestrator
        sch = b.get("schedule") or {}
        assert sch.get("owner") != "LEGACY_SCHEDULER" and sch.get("class") != "VALIDATION_EXCEPTION", bid
    import os
    pol = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "brains", "platform", "cost-freeze", "schedule-policy.json")))
    assert set(pol["allowEnabled"]) == scheduled                                    # one source of truth for what may be scheduled


def test_conformance_fixture_matches_code_for_ops():
    import os
    fx = json.load(open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "contracts", "conformance", "orchestrator_control_v1.json")))
    assert fx["version"] == O.CONTROL_VERSION == "orchestrator-control-v1"
    for key, val in (("engineModes", O.ENGINE_MODES), ("activityStates", O.ACTIVITY_STATES), ("triggers", O.TRIGGERS), ("decisions", O.DECISIONS),
                     ("scheduleClasses", O.SCHEDULE_CLASSES), ("failureClasses", O.FAILURE_CLASSES), ("requestActions", O.REQUEST_ACTIONS),
                     ("protectedActions", O.PROTECTED_ACTIONS), ("costBasis", O.COST_BASIS), ("groups", O.GROUPS)):
        assert tuple(fx[key]) == val, key
    assert tuple(fx["sections"]) == C.SECTIONS and fx["path"] == C.NODE
    assert fx["retention"]["executions"] == O.EXECUTION_LEDGER_MAX and fx["retention"]["decisions"] == O.DECISION_LEDGER_MAX


def test_sample_payloads_validate_against_the_contract():
    import os
    d = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "brains", "platform", "orchestrator")
    st = json.load(open(os.path.join(d, "sample_control_state_live_2026-10-14.json")))
    assert set(st) <= set(C.SECTIONS) and st["summary"]["engineMode"] == "PRE_PRODUCTION" and st["summary"]["customerPublication"] is False
    assert all(b["decisions"]["SCHEDULE"]["decision"] in O.DECISIONS for b in st["brains"].values())
    assert all(e["kind"] in ("HARD", "SOFT") for e in st["edges"].values())
    rq = json.load(open(os.path.join(d, "sample_control_request.json")))
    assert rq["runNowResult"]["decision"] in O.REQUEST_DECISIONS and rq["fleetRejected"]["decision"] == "REJECTED"


def test_scheduler_truth_comes_from_cloud_scheduler_not_the_job_record():
    """An event-driven job record says enabled=True while its own Cloud Scheduler job is PAUSED (lake-surface-daily): the scheduler state wins."""
    m = manifest()
    jobs = {"lake-surface-daily": {"enabled": True, "executionMode": "EVENT_DRIVEN"}, "wind-hourly": {"schedulerState": "PAUSED"}}
    states = {"lake-surface-daily": "PAUSED", "wind-hourly": "ENABLED"}
    j, s = C.build_jobs(m, jobs, [], states)
    assert s["lake-surface-daily"]["enabled"] is False and s["wind-hourly"]["enabled"] is True        # live Scheduler beats the stale /jobs record
    j2, s2 = C.build_jobs(m, jobs, [], None)
    assert "enabled" not in s2["lake-surface-daily"]                                                   # no scheduler state at all: unknown, not "enabled"
    assert s2["wind-hourly"]["enabled"] is False                                                       # record's schedulerState is used when no live state
