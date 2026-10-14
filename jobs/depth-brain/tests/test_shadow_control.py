"""Shadow Brain in the control plane: visible, explicit about having no score, and excluded from every roll-up.
Also the pilot-only write scope, ownership, no-op behaviour, and that reading the control plane computes nothing / calls nothing."""
import copy
import datetime as dt
import json
import os
import socket

import pytest
from sector_brain_platform import control as CP, lake_key
from depth_brain import contract as C
from depth_brain import maturity as M
from depth_brain.publish import publish
from depth_brain.writer import DryRunWriter, WriteError
from tests.helpers import NOW, candidate, lake_state

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = json.load(open(os.path.join(HERE, "depth_brain", "data", "candidates.json")))
PILOTS = [c["lakeId"] for c in MAN["candidates"] if c["rollout"] == "PILOT_VERIFIED"]


def pilot_states(elev_offset=-1.4):
    out = {}
    for c in MAN["candidates"]:
        if c["rollout"] == "PILOT_VERIFIED":
            out[c["lakeId"]] = {"kind": "OBSERVED", "sourceCapability": c["levelSource"]["capability"] or "DIRECT_OPERATOR_POOL", "currentElevationFt": c["reference"]["poolFt"] + elev_offset,
                                "unit": "ft", "observationTime": "2026-10-14T18:00:00Z", "freshness": {"stale": False}, "provenance": {"brainVersion": "1.0.0"}}
    return out


NOW2 = dt.datetime(2026, 10, 14, 19, 0, tzinfo=dt.timezone.utc)


def published_tree(scope="pilots"):
    w = DryRunWriter()
    rep = publish(MAN, pilot_states(), w, NOW2, scope=scope)
    assert rep["ok"], rep["errors"]
    return w, rep


def healthy_reg(b):
    return {"brainId": b, "displayName": b, "health": "HEALTHY", "status": "BETA", "version": "1", "supportedLakeCount": 5,
            "platform": {"conformant": True, "implementation": "x"}}


def control(w, depth_health=None):
    brains = {b: healthy_reg(b) for b in CP.ALL_BRAINS}
    brains["depth"] = w.tree["brains"]["depth"]
    health = {b: {"status": "HEALTHY"} for b in CP.ALL_BRAINS}
    health["depth"] = {"status": depth_health or w.tree["health"]["brains"]["depth"]["status"]}
    return CP.overview(brains=brains, health=health, validation={"depth": w.tree["validation"]["depth"]}, scores={}, engine=None, fleet=w.tree.get("lakeFleet", {}),
                       sources={}, health_sources={}, jobs={}, now=NOW2), brains, health


# ── registration + explicit no-score semantics ─────────────────────────────────────────────────────────────────
def test_depth_is_registered_as_a_shadow_brain_with_no_official_score():
    w, _ = published_tree()
    ov, _, _ = control(w)
    d = ov["brains"]["depth"]
    assert d["shadow"] is True and d["scoreStatus"] == "NOT_ESTABLISHED"
    assert "score" not in d and "officialScore" not in d                                    # RTDB has no null: absent + scoreStatus says why
    assert d["research"]["official"] is False and isinstance(d["research"]["maturity"], (int, float))
    assert d["status"] == "PROFILED" and d["validation"]["status"] == "NOT_VALIDATED"
    assert ov["shadowBrains"] == ["depth"]


def test_control_numbers_are_generated_not_hardcoded():
    w, _ = published_tree()
    d = control(w)[0]["brains"]["depth"]
    fm = M.fleet_metrics(MAN)
    assert d["fleet"]["shiftPossible"] == fm["shiftPossible"] and d["fleet"]["verifiedDatum"] == fm["verifiedDatum"]
    assert d["fleet"]["highConfidence"] == fm["highConfidence"] and d["fleet"]["mediumConfidence"] == fm["mediumConfidence"] and d["fleet"]["blocked"] == fm["blocked"]
    assert d["fleet"]["effectiveZoneEligible"] == fm["effectiveZoneEligible"] and d["fleet"]["pilotVerified"] == len(PILOTS) == 5
    assert d["research"]["maturity"] == M.evaluate(MAN)["overall"]
    assert d["lakeDependency"]["liveLakeStates"] == 5 and d["lakeDependency"]["awaitingLakeBrain"] == fm["shiftPossible"] - 5
    assert d["coverage"]["supported"] == 5 and d["scheduled"] is False
    assert d["orchestration"]["status"] == "NOT_STARTED" and d["fieldValidation"]["status"] == "NOT_STARTED"
    assert any("datum" in b.lower() for b in d["blockers"]) and any("Lake fleet-state" in b for b in d["blockers"]) and any("Field validation" in b for b in d["blockers"])
    assert any("Licensing" in b for b in d["blockers"]) and any("Orchestration" in b for b in d["blockers"])


def test_manifest_change_changes_the_control_numbers():
    w1, _ = published_tree()
    m2 = copy.deepcopy(MAN)
    for c in m2["candidates"]:
        if c["rollout"] == "HIGH_CONFIDENCE":
            c["rollout"], c["shiftPossible"] = "BLOCKED", False
            break
    w2 = DryRunWriter()
    publish(m2, pilot_states(), w2, NOW2)
    assert control(w2)[0]["brains"]["depth"]["fleet"]["shiftPossible"] == control(w1)[0]["brains"]["depth"]["fleet"]["shiftPossible"] - 1


# ── roll-ups never include the shadow Brain ──────────────────────────────────────────────────────────────────────
def test_shadow_health_does_not_move_engine_rollups():
    w, _ = published_tree()
    ok, _, _ = control(w, depth_health="HEALTHY")
    bad, _, _ = control(w, depth_health="FAILED")
    for k in ("worstBrainHealth", "brainsConformant", "dependencyCompleteness"):
        assert ok["engine"][k] == bad["engine"][k]
    assert ok["engine"]["worstBrainHealth"] == "HEALTHY"
    assert bad["brains"]["depth"]["health"] == "FAILED"                                      # still visible as its own entry
    assert all(x["brainId"] != "depth" for x in ok.get("workNext", []))


def test_depth_slot_never_makes_a_lake_stale_or_adds_issues():
    row = {"lakeId": "A|XX", "readiness": {"lake": "BETA", "depth": "CALIBRATION"},
           "slots": {"lake": {"stale": False, "issueCount": 0, "generatedAt": "2026-10-14T18:00:00Z"},
                     "depth": {"stale": True, "evidenceStale": True, "issueCount": 7, "generatedAt": "2026-10-14T19:00:00Z"}}}
    r = CP.fleet_rollup("A_XX", row, NOW2)
    assert r.get("stale") is False and not r.get("evidenceStale") and "issueCount" not in r or r["issueCount"] == 0
    assert r["slotsPublished"] == 2 and r["lastUpdatedAt"] == "2026-10-14T18:00:00Z"
    fs = CP.fleet_summary({"A_XX": row}, NOW2)
    assert fs["publishedBySlot"]["depth"] == 1 and fs["readinessBySlot"]["depth"] == {"CALIBRATION": 1}
    assert "staleSlots" not in fs and fs.get("issueCount", 0) == 0 and fs.get("staleLakes", 0) == 0


def test_a_blocked_row_would_raise_an_ops_alert_so_none_is_written():
    w, _ = published_tree()
    counts = control(w)[0]["fleet"]["readinessBySlot"]["depth"]
    assert counts == {"CALIBRATION": 5} and "BLOCKED" not in counts


# ── pilot-only scope ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_pilot_scope_writes_only_pilot_lakes():
    w, rep = published_tree()
    assert set(rep["lakes"]) == set(PILOTS) and len(PILOTS) == 5
    assert set(w.tree["lakeFleet"]) == {lake_key(l) for l in PILOTS}
    assert set(w.tree["lakes"]) == {lake_key(l) for l in PILOTS}
    reg = w.tree["brains"]["depth"]
    assert reg["readinessCounts"] == {"CALIBRATION": 5} and reg["supportedLakeCount"] == 5 and reg["scope"] == "pilots"


def test_fleet_scope_is_analysis_only_and_explicit():
    w, rep = published_tree(scope="fleet")
    assert len(w.tree["lakeFleet"]) == 621
    with pytest.raises(ValueError):
        publish(MAN, {}, DryRunWriter(), NOW2, scope="everything")


def test_cli_refuses_a_live_fleet_scope():
    import depth_brain.__main__ as cli
    with pytest.raises(SystemExit):
        cli.main(["publish", "--lake-states", "file:/nonexistent", "--rtdb", "https://sector-brain.firebaseio.com", "--yes-write-shadow", "--scope", "fleet"])


# ── no-op behaviour, missing input, ownership, no customer publication ──────────────────────────────────────────────────────
def test_second_run_with_unchanged_inputs_rewrites_no_lake_state():
    w = DryRunWriter()
    publish(MAN, pilot_states(), w, NOW2)
    n = len(w.patches)
    publish(MAN, pilot_states(), w, NOW2 + dt.timedelta(minutes=30))
    later = w.patches[n:]
    assert not any(p.startswith("lakes/") or p.startswith("snapshots/") for patch in later for p in patch)           # fingerprint unchanged -> no-op for states


def test_missing_lake_input_for_a_pilot_publishes_unavailable_not_a_number():
    w = DryRunWriter()
    states = pilot_states(); gone = PILOTS[0]; del states[gone]
    rep = publish(MAN, states, w, NOW2)
    st = w.tree["lakes"][lake_key(gone)]["states"]["depth"]
    assert st["kind"] == "unavailable" and st["effectiveDepth"]["reasons"] == ["LAKE_STATE_MISSING"] and "shiftFt" not in st["effectiveDepth"]
    assert w.tree["lakeFleet"][lake_key(gone)]["readiness"]["depth"] == "DEGRADED" and rep["health"] in ("HEALTHY", "DEGRADED")


def test_shadow_writer_owns_only_depth_paths():
    w = DryRunWriter()
    for bad in ("control/overview", "control/overview/brains/depth", "scores/depth", "lakes/Guntersville_AL/states/lake", "conditions/x", "lakeFleet/Guntersville_AL/stale"):
        with pytest.raises(WriteError):
            w.patch({bad: {"x": 1}})
    _, _ = published_tree()
    w2, _ = published_tree()
    roots = {p.split("/")[0] for patch in w2.patches for p in patch}
    assert roots <= {"lakes", "snapshots", "lakeFleet", "brains", "validation", "health", "activity"}


def test_no_official_score_node_and_validation_not_validated():
    w, _ = published_tree()
    assert "scores" not in w.tree and "score" not in w.tree["brains"]["depth"]
    assert w.tree["validation"]["depth"]["status"] == "NOT_VALIDATED" and w.tree["brains"]["depth"]["validation"]["status"] == "NOT_VALIDATED"
    assert w.tree["brains"]["depth"]["scoreStatus"] == "NOT_ESTABLISHED"


# ── reading the control plane computes nothing and calls nothing ─────────────────────────────────────────────────────────────
def test_building_and_reading_the_control_summary_makes_no_network_call(monkeypatch):
    w, _ = published_tree()

    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    ov, _, _ = control(w)                                              # pure function of already-published nodes
    from depth_brain import ops_summary
    ops_summary.registry_extras(MAN, 5)
    assert ov["brains"]["depth"]["scoreStatus"] == "NOT_ESTABLISHED"


def test_ops_read_path_has_no_depth_compute_entry_point():
    """Ops reads cached RTDB nodes. Nothing in the Engine's request path imports Depth: no Swift/server code references depth_brain."""
    root = os.path.abspath(os.path.join(HERE, "..", ".."))
    hits = []
    for d in ("Sources",):
        for dp, _, fs in os.walk(os.path.join(root, d)):
            for f in fs:
                if f.endswith((".swift", ".py")) and "depth_brain" in open(os.path.join(dp, f), errors="ignore").read():
                    hits.append(os.path.join(dp, f))
    assert hits == []


def test_control_summary_carries_lifecycle_claims_and_execution():
    w, _ = published_tree()
    d = control(w)[0]["brains"]["depth"]
    assert d["lifecycle"] == "SHADOW" and d["execution"]["type"] == "DEPENDENCY_DRIVEN" and d["execution"]["clock"] is False
    assert {c["id"] for c in d["claims"]["claims"]} >= {"levelShift", "knownFlatClass", "effectiveZoneBounds"}
    assert "score" not in d and d["scoreStatus"] == "NOT_ESTABLISHED"
