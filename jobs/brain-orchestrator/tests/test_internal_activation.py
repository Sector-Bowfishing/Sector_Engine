"""Internal operation (2026-10-22) on the LIVE execution manifest: what one orchestrator cycle starts, and the isolated SHADOW lane."""
import datetime as dt
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR          # noqa: E402
from test_control_plane import FakeDb, tree, ago, NOW, enabled_control   # noqa: E402,F401  (reuse the in-memory RTDB and the stale-world tree)
from sector_brain_platform import orchestration as O, shadow_lane as SL   # noqa: E402

pytestmark = pytest.mark.live_manifest


def _shadow_output(bid, approval="NOT_RECORDED"):
    slot = {"depth": "depth", "vegetation": "vegetation"}[bid]
    return {"brainId": bid, "slot": slot, "report": {"ok": True, "evaluated": 2, "unavailable": 1, "writes": 3},
            "release": {"releaseId": f"{bid}-cand-1", "releaseDigest": "sha256:" + "a" * 64, "approvalStatus": approval, "store": "PACKAGED_IN_IMAGE"},
            "approvedPath": {"status": "ABSTAIN", "reason": "BLOCKED_AWAITING_APPROVED_RELEASE"},
            "patches": [{f"lakes/Guntersville_AL/states/{slot}": {"readiness": "DEGRADED", "kind": "observed", "secretValue": 1.23,
                                                                   "agency": {"pct": 40}}}], "inputs": {"liveLakeStates": 5}}


@pytest.fixture
def live_cycle(monkeypatch):
    calls = {"start": [], "inproc": [], "shadow": []}

    def setup(t, shadow=None):
        db = FakeDb(t)
        monkeypatch.setattr(OR, "BrainRtdb", lambda *a, **k: db)
        monkeypatch.setattr(OR, "TokenProvider", lambda *a, **k: object())
        monkeypatch.setattr(OR, "check_schema", lambda d: None)
        monkeypatch.setattr(OR, "sync_jobs", lambda *a, **k: ({}, {}, 0))
        monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: {"action": "SKIP", "reasons": ["nothing to do"]})
        monkeypatch.setattr(OR, "start_job", lambda b, tokens: calls["start"].append(b) or {"brainId": b, "how": "cloud-run-job", "ok": True,
                                                                                          "execution": f"x/{b}-e1", "startedAt": OR.iso(NOW)})
        monkeypatch.setattr(OR, "run_in_process", lambda b, timeout=1800: calls["inproc"].append(b) or {"brainId": b, "how": "in-process", "ok": True, "seconds": 1, "tail": ""})
        monkeypatch.setattr(OR.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})())
        monkeypatch.setattr(OR, "run_shadow", lambda b, timeout=900: calls["shadow"].append(b) or (shadow or {}).get(b) or {"brainId": b, "ok": True, "exit": 0,
                                                                                                                          "seconds": 1.0, "output": _shadow_output(b)})
        return db
    return setup, calls


def test_live_board_activates_the_internal_pipelines_and_nothing_else():
    m = O.load_manifest()
    act = O.effective_activity(m)
    assert act["water-temp"] == act["sector-intelligence"] == act["biological-state"] == act["wind"] == act["water-clarity"] == "ACTIVE"
    assert act["depth"] == act["vegetation"] == "PARKED"                               # approved path abstains; SHADOW lane runs instead
    assert all(m["brains"][b]["customerPublication"] is False for b in m["brains"])  # internal only
    for b in ("water-temp", "water-clarity"):
        assert O.schedule_policy(m["brains"][b], "PRE_PRODUCTION")[0] and m["brains"][b]["schedule"]["class"] == "ORCHESTRATOR_OWNED"
        assert m["brains"][b]["schedule"]["exception"]["maxMonthlyUsd"] <= 2
    assert m["brains"]["water-temp"]["scopes"] == ["pilots"] and m["brains"]["water-temp"]["allowFleetRunNow"] is False   # never 621 lakes
    assert {b: m["brains"][b]["shadowLane"]["cadenceHours"] for b in ("depth", "vegetation")} == {"depth": 24, "vegetation": 168}


def test_a_cycle_starts_only_due_active_pilot_jobs(live_cycle):
    setup, calls = live_cycle
    t = tree()
    t["brains"]["water-clarity"] = {"lastSuccessfulRun": ago(200), "staleAfterHours": 26, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"}
    setup(t)
    assert OR.main([]) == 0
    assert sorted(calls["start"]) == ["water-clarity", "water-temp"]                 # stale + ACTIVE + orchestrator-owned
    assert "wind" not in calls["start"] and "lake-brain" not in calls["start"]       # scheduler-owned / MAINTENANCE
    assert calls["shadow"] == []                                                    # the shadow lane only runs with its flag


def test_fresh_pilot_jobs_are_not_started(live_cycle):
    setup, calls = live_cycle
    t = tree()
    t["brains"]["water-temp"]["lastSuccessfulRun"] = ago(1)
    t["brains"]["water-clarity"] = {"lastSuccessfulRun": ago(2), "staleAfterHours": 26, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"}
    setup(t)
    assert OR.main([]) == 0 and calls["start"] == []                                 # no redundant execution


def test_a_scoped_job_success_stops_hourly_reruns_while_the_fleet_registry_stays_old(live_cycle, monkeypatch):
    """Defect found in the first live cycles (2026-10-22): a pilot-scoped Water Temp run does not restate the 621-lake registry, so its
    lastSuccessfulRun stayed 2026-10-14 and the job would have been due every hour. /jobs/water-temp-brain.lastSuccessfulAt now counts."""
    setup, calls = live_cycle
    t = tree()
    t["brains"]["water-temp"]["lastSuccessfulRun"] = ago(196)                       # fleet registry, untouched by scoped runs
    t["brains"]["water-clarity"] = {"lastSuccessfulRun": ago(2), "staleAfterHours": 26, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"}
    t["jobs"] = {"water-temp-brain": {"lastSuccessfulAt": ago(1)}}
    setup(t)
    assert OR.main([]) == 0 and calls["start"] == []
    t2 = tree()
    t2["brains"]["water-temp"]["lastSuccessfulRun"] = ago(196)
    t2["brains"]["water-clarity"] = {"lastSuccessfulRun": ago(2), "staleAfterHours": 26, "stalenessModel": "TIME", "status": "CALIBRATION", "version": "1"}
    t2["jobs"] = {"water-temp-brain": {"lastSuccessfulAt": ago(7)}}
    calls["start"].clear()
    db = setup(t2)
    monkeypatch.setattr(OR, "sync_jobs", lambda *a, **k: (t2["jobs"], {}, 0))       # this cycle's /jobs records feed the control plane
    assert OR.main([]) == 0 and calls["start"] == ["water-temp"]                     # due again after its 6 h rule
    row = db.tree["control"]["orchestratorV1"]["brains"]["water-temp"]
    assert "scoped run" in row["lastSuccessfulRunBasis"]                             # the control plane labels the scoped basis


def test_shadow_lane_publishes_only_an_isolated_experimental_summary(live_cycle):
    setup, calls = live_cycle
    db = setup(tree())
    assert OR.main(["--run-shadow-lane"]) == 0
    assert sorted(calls["shadow"]) == ["depth", "vegetation"]
    for bid in ("depth", "vegetation"):
        doc = db.tree["control"]["shadowLaneV1"][bid]
        assert SL.problems(doc) == [] and doc["classification"] == doc["lane"] == "INTERNAL_EXPERIMENTAL" and doc["authoritative"] is False
        assert doc["approvedPath"]["status"] == "ABSTAIN" and doc["candidateRelease"]["approvalStatus"] == "NOT_RECORDED"
        assert doc["lakes"]["Guntersville_AL"] == {"readiness": "DEGRADED", "kind": "observed"}           # allowlist: no values, no agency block
    written = {p for w in db.writes for p in w}
    assert not any(p.startswith(("lakes/", "lakeFleet/", "snapshots/", "brains/depth", "brains/vegetation", "scores/", "species/")) for p in written)


def test_shadow_lane_respects_its_cadence_and_force(live_cycle):
    setup, calls = live_cycle
    t = tree()
    t["control"] = {"executionControlV1": enabled_control(), **{"shadowLaneV1": {"depth": {"runAt": ago(2)}, "vegetation": {"runAt": ago(24)}}}}
    setup(t)
    assert OR.main(["--run-shadow-lane"]) == 0 and calls["shadow"] == []            # depth 24 h, vegetation 168 h: neither due
    assert OR.main(["--run-shadow-lane", "--force-shadow-lane"]) == 0 and sorted(calls["shadow"]) == ["depth", "vegetation"]


def test_shadow_lane_refuses_an_approved_release_and_records_failures(live_cycle):
    setup, calls = live_cycle
    db = setup(tree(), shadow={"depth": {"brainId": "depth", "ok": True, "exit": 0, "seconds": 1.0, "output": _shadow_output("depth", "APPROVED")},
                               "vegetation": {"brainId": "vegetation", "ok": False, "exit": 2, "error": "REFUSED: KnowledgeReleaseError: tampered"}})
    assert OR.main(["--run-shadow-lane"]) == 0                                      # never breaks the cycle
    sl = (db.tree.get("control") or {}).get("shadowLaneV1") or {}
    assert "schema" not in (sl.get("depth") or {})                                   # an APPROVED release belongs on the approved path
    assert "tampered" in sl["vegetation"]["lastFailure"]["error"]


def test_dry_run_computes_but_writes_nothing(live_cycle):
    setup, calls = live_cycle
    db = setup(tree())
    assert OR.main(["--dry-run", "--run-shadow-lane"]) == 0
    assert db.writes == [] and calls["start"] == []


def test_a_cycle_publishes_the_four_dimensions_with_live_internal_operation(live_cycle, monkeypatch):
    """engineering-status-ops-v1 1.2.0 (D-IA-2 Option B): the gated projection gains each Brain's LIVE runtime readiness and internal operation."""
    import json as _json
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    sys.path.insert(0, os.path.join(root, "tools", "cortex_status"))
    import build_engineering_status as B
    import ops_projection as P
    r = B.build()
    r["source"]["evaluatedCommit"] = "a" * 40
    proj = P.project(r, code_state="MAIN_COMMIT")
    proj["generatedFrom"]["certificationCurrent"] = True                             # the gate's certification rule is tested elsewhere
    setup, calls = live_cycle
    t = tree()
    t["control"] = {"executionControlV1": enabled_control(), **{"shadowLaneV1": {"depth": {"schema": "brain-shadow-lane-v1", "lane": "INTERNAL_EXPERIMENTAL", "executionMode": "INTERNAL",
                                               "experimental": True, "runAt": ago(2), "lakeCount": 5, "lakes": {}}}}}
    db = setup(t)
    monkeypatch.setattr(OR.ESP, "load_staged", lambda here: _json.loads(_json.dumps(proj)))
    monkeypatch.setattr(OR.CP, "scheduler_states", lambda tokens: {"brain-orchestrator": "ENABLED", "wind-hourly": "ENABLED", "lake-brain-ledger-daily": "ENABLED"})
    monkeypatch.setenv("DEPLOYMENT_VERSION", "brain-orchestrator@" + "a" * 12)
    assert OR.main(["--publish-engineering-status"]) == 0
    doc = db.tree["control"]["engineeringStatusV1"]
    assert doc["state"] == "AVAILABLE" and doc["schemaVersion"] == "1.3.0" and doc["operationsAsOf"]
    ops = {b["brainId"]: b["operations"] for b in doc["brains"]}
    assert set(ops) == set(O.load_manifest()["brains"])
    assert all(o["internalOperation"]["status"] in OR.BOPS.INTERNAL and o["runtimeReadiness"]["status"] in OR.BOPS.RUNTIME for o in ops.values())
    assert ops["depth"]["internalOperation"]["status"] == "SHADOW" and ops["depth"]["shadowLane"]["experimental"] is True
    assert ops["vegetation"]["internalOperation"]["status"] == "NOT_VERIFIED"         # no shadow run on record: never assumed
    assert all(o["customerEligibility"]["status"] == "NOT_ELIGIBLE" for o in ops.values())
    assert OR.ESP.leaks(doc) == []
