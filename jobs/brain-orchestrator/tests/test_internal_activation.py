"""Internal operation (2026-10-22) on the LIVE execution manifest: what one orchestrator cycle starts, and the isolated SHADOW lane."""
import datetime as dt
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import orchestrate as OR          # noqa: E402
from test_control_plane import FakeDb, tree, ago, NOW   # noqa: E402,F401  (reuse the in-memory RTDB and the stale-world tree)
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
    t["control"] = {"shadowLaneV1": {"depth": {"runAt": ago(2)}, "vegetation": {"runAt": ago(24)}}}
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
