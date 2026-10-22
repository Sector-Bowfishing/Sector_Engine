"""Cortex 2.6.0 four dimensions (IO-01, IO-08): live runtime readiness + internal operation from execution evidence, never from science."""
import datetime as dt

from sector_brain_platform import brain_operations as BO
from sector_brain_platform.engineering_status_publication import leaks

NOW = dt.datetime(2026, 10, 22, 16, tzinfo=dt.timezone.utc)
T = lambda h: (NOW - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")
WT = {"activityState": "ACTIVE", "freshness": {"staleAfterHours": 6}, "schedule": {"class": "ORCHESTRATOR_OWNED", "scheduler": "brain-orchestrator"}}
WIND = {"activityState": "ACTIVE", "freshness": {"staleAfterHours": 1.5}, "schedule": {"class": "VALIDATION_EXCEPTION", "scheduler": "wind-hourly"}}
FISH = {"activityState": "ACTIVE", "freshness": {"stalenessModel": "VERSION"}, "schedule": {"class": "INPUT_DRIVEN"}}
DEPTH = {"activityState": "PARKED", "shadowLane": {"enabled": True, "cadenceHours": 24}}
ON = {"brain-orchestrator": "ENABLED", "wind-hourly": "ENABLED"}
SHADOW = {"schema": "brain-shadow-lane-v1", "lane": "INTERNAL_EXPERIMENTAL", "executionMode": "INTERNAL", "experimental": True, "runAt": T(5),
          "lakeCount": 3, "readinessCounts": {"DEGRADED": 3}, "lakes": {"A": {"kind": "observed"}, "B": {"kind": "unavailable"}, "C": {"kind": "observed"}},
          "candidateRelease": {"releaseId": "depth-cand-1", "releaseDigest": "sha256:" + "a" * 64, "approvalStatus": "NOT_RECORDED"},
          "approvedPath": {"status": "ABSTAIN", "reason": "BLOCKED_AWAITING_APPROVED_RELEASE (G-1)"}, "outputDigest": "sha256:" + "b" * 64}


def live(b, row=None, sched=ON, shadow=None, plan=None):
    return BO.live("x", b, row, scheduler_states=sched, shadow_doc=shadow, plan=plan, now=NOW)


def test_time_brain_is_active_only_with_an_enabled_trigger_and_a_recent_success():
    ok = live(WT, {"lastExecution": {"at": T(2), "status": "SUCCEEDED"}, "lastSuccessfulRun": T(2)})
    assert ok["internalOperation"]["status"] == "ACTIVE" and ok["runtimeReadiness"]["status"] == "READY"
    assert ok["internalOperation"]["expectedIntervalHours"] == 6 and ok["internalOperation"]["lastExecutionKind"] == "RUN"
    stale = live(WT, {"lastExecution": {"at": T(20), "status": "SUCCEEDED"}, "lastSuccessfulRun": T(20)})
    assert stale["internalOperation"]["status"] == "NOT_VERIFIED"                        # 20 h > 1.5 x 6 h
    paused = live(WT, {"lastExecution": {"at": T(1), "status": "SUCCEEDED"}, "lastSuccessfulRun": T(1)}, sched={"brain-orchestrator": "PAUSED"})
    assert paused["internalOperation"]["status"] == "PAUSED"                             # a paused scheduler is never ACTIVE (PL-04)
    unknown = live(WT, {"lastExecution": {"at": T(1), "status": "SUCCEEDED"}, "lastSuccessfulRun": T(1)}, sched={})
    assert unknown["internalOperation"]["status"] == "NOT_VERIFIED"
    assert live(WIND, {"lastSuccessfulRun": T(1)}, sched={"wind-hourly": "ENABLED"})["internalOperation"]["scheduler"] == "wind-hourly"


def test_a_failed_execution_is_failed_and_not_ready_and_nothing_is_invented():
    f = live(WT, {"lastExecution": {"at": T(1), "status": "FAILED"}, "lastSuccessfulRun": T(3)})
    assert f["internalOperation"]["status"] == "FAILED" and f["runtimeReadiness"]["status"] == "NOT_READY"
    none = live(WT, {})
    assert none["internalOperation"]["status"] == "NOT_VERIFIED" and none["runtimeReadiness"]["status"] == "NOT_VERIFIED"
    assert none["health"] == "UNKNOWN" and none["inputFreshness"]["verdict"] == "UNKNOWN"   # absence is UNKNOWN, never HEALTHY


def test_event_driven_brain_counts_its_hourly_plan_check_and_a_successful_noop_run():
    a = live(FISH, {"lastExecution": {"at": T(30), "status": "SKIPPED"}}, plan={"action": "SKIP"})
    io = a["internalOperation"]
    assert io["status"] == "ACTIVE" and io["lastExecutionKind"] == "PLAN_CHECK" and io["expectedIntervalHours"] == 1.0
    assert io["lastFullRunAt"] == T(30) and io["lastFullRunResult"] == "SKIPPED" and "nothing new to publish" in io["basis"]
    assert live(FISH, {"lastExecution": {"at": T(30), "status": "SUCCEEDED"}})["internalOperation"]["status"] == "NOT_VERIFIED"   # no plan check
    assert live(FISH, {"lastExecution": {"at": T(30), "status": "SUCCEEDED"}}, plan={"action": "ERROR"})["internalOperation"]["status"] == "DEGRADED"


def test_shadow_brain_is_shadow_not_active_and_its_summary_is_counts_only():
    s = live(DEPTH, {}, shadow=SHADOW)
    assert s["internalOperation"]["status"] == "SHADOW" and s["internalOperation"]["lane"] == "INTERNAL_EXPERIMENTAL"
    assert live(DEPTH, {}, shadow={**SHADOW, "runAt": T(40)})["internalOperation"]["status"] == "NOT_VERIFIED"      # > 1.5 x 24 h
    failed = live(DEPTH, {}, shadow={**SHADOW, "lastFailure": {"at": T(1)}})
    assert failed["internalOperation"]["status"] == "FAILED" and failed["runtimeReadiness"]["status"] == "NOT_READY"
    assert live(DEPTH, {}, shadow=None)["internalOperation"]["status"] == "NOT_VERIFIED"
    ss = BO.shadow_summary(SHADOW)
    assert ss["observedLakes"] == 2 and ss["outputKinds"] == {"observed": 2, "unavailable": 1} and ss["candidateApproval"] == "NOT_RECORDED"
    assert ss["experimental"] is True and ss["authoritative"] is False and ss["customerEligible"] is False
    assert "lakes" not in ss and leaks(ss) == []                                         # no lake values, no digests


def test_parked_without_a_shadow_lane_is_paused():
    assert live({**WT, "activityState": "PARKED"}, {"lastSuccessfulRun": T(1)})["internalOperation"]["status"] == "PAUSED"


def test_overlay_keeps_the_static_dimensions_and_marks_unknown_brains():
    doc = {"state": "AVAILABLE", "brains": [
        {"brainId": "water-temp", "operations": {"scientificValidation": {"status": "PARTIAL", "label": "X"}, "knowledgeRelease": {"state": "NONE"},
                                                 "customerEligibility": {"status": "NOT_ELIGIBLE"}}},
        {"brainId": "depth", "operations": {"scientificValidation": {"status": "NOT_STARTED", "label": "Y"}, "knowledgeRelease": {"state": "CANDIDATE"},
                                            "customerEligibility": {"status": "NOT_ELIGIBLE"}}},
        {"brainId": "ghost", "operations": {}}]}
    m = {"brains": {"water-temp": WT, "depth": DEPTH}}
    rows = {"water_temp": {"brainId": "water-temp", "lastSuccessfulRun": T(1), "lastExecution": {"at": T(1), "status": "SUCCEEDED"}}}
    out = BO.overlay(doc, m, rows, scheduler_states=ON, shadow_docs={"depth": SHADOW}, plans={}, now=NOW)
    ops = {b["brainId"]: b["operations"] for b in out["brains"]}
    assert ops["water-temp"]["scientificValidation"]["status"] == "PARTIAL" and ops["water-temp"]["internalOperation"]["status"] == "ACTIVE"
    assert ops["depth"]["internalOperation"]["status"] == "SHADOW" and ops["depth"]["shadowLane"]["lakeCount"] == 3
    assert ops["ghost"]["internalOperation"]["status"] == "NOT_DEPLOYED"
    assert BO.counts(out) == {"ACTIVE": 1, "SHADOW": 1, "NOT_DEPLOYED": 1} and doc["brains"][0]["operations"].get("internalOperation") is None
    assert leaks(out) == []


def test_absent_evidence_is_omitted_never_published_as_null():
    for out in (live(DEPTH, {}, shadow=None), live(WT, {}), live(FISH, {}, plan=None)):
        assert None not in out["internalOperation"].values() and "reason" not in out.get("inputFreshness", {})
