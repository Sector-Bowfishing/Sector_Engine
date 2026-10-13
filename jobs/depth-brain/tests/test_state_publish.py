import copy
import json

import pytest
from depth_brain import contract as C
from depth_brain.publish import publish
from depth_brain.state import build_state, input_fingerprint, plan
from depth_brain.writer import DryRunWriter, WriteError
from sector_brain_platform import lake_key
from tests.helpers import NOW, candidate, lake_state


def test_shift_state_shape_and_vocab():
    s, m = build_state(candidate(), lake_state(593.6), NOW)
    assert s["kind"] == "observed" and s["slot"] == "depth" and s["stateSchema"] == C.STATE_SCHEMA
    ed = s["effectiveDepth"]
    assert ed["mode"] == "shiftOnly" and ed["shiftFt"] == -1.4 and ed["evidenceKind"] == "levelDelta" and ed["confidence"] == "HIGH"
    assert "absoluteDepthFt" not in s and "depthFt" not in ed                      # a shift is not a depth
    assert s["coverage"]["sourceTier"] == "UNKNOWN" and s["provenance"]["readiness"] == "CALIBRATION" == m["readiness"]
    assert not s["freshness"]["stale"] and s["freshness"]["evidenceStale"] is False and "freshUntil" not in s["freshness"]   # FINGERPRINT brain
    assert any("not a measured depth" in f for f in s["facts"])
    assert any("SHADOW" in l for l in s["limitations"])


def test_json_serialisable_and_deterministic():
    a, _ = build_state(candidate(), lake_state(), NOW)
    b, _ = build_state(candidate(), lake_state(), NOW)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_missing_lake_state_is_unavailable_not_zero():
    s, m = build_state(candidate(), None, NOW)
    assert s["kind"] == "unavailable" and s["effectiveDepth"]["mode"] == "unknown" and s["effectiveDepth"]["reasons"] == ["LAKE_STATE_MISSING"]
    assert "shiftFt" not in s["effectiveDepth"] and m["readiness"] == "DEGRADED"


def test_stale_lake_input_is_flagged():
    s, m = build_state(candidate(), lake_state(obs="2026-10-13T10:00:00Z"), NOW)           # 9 h old
    assert s["effectiveDepth"]["mode"] == "shiftOnly" and s["freshness"]["evidenceStale"] is True and m["readiness"] == "DEGRADED"
    old, _ = build_state(candidate(), lake_state(obs="2026-10-10T10:00:00Z"), NOW)
    assert old["kind"] == "unavailable" and old["effectiveDepth"]["reasons"] == ["LEVEL_TOO_OLD"]
    st, _ = build_state(candidate(), lake_state(stale=True), NOW)
    assert st["freshness"]["evidenceStale"] is True


def test_blocked_candidate_never_computes_even_with_a_level():
    s, m = build_state(candidate(possible=False, blockedReasons=["DATUM_UNKNOWN"]), lake_state(), NOW)
    assert s["kind"] == "unavailable" and m["readiness"] == "BLOCKED"
    assert s["effectiveDepth"]["reasons"] == ["CANDIDATE_BLOCKED", "DATUM_UNKNOWN"]


def test_unknown_datum_candidate_stays_unknown():
    s, _ = build_state(candidate(status="UNKNOWN", sigma=0.0), lake_state(), NOW)
    assert s["effectiveDepth"]["mode"] == "unknown" and "DATUM_UNKNOWN" in s["effectiveDepth"]["reasons"]


def test_proxy_lake_state_never_yields_shift():
    s, _ = build_state(candidate(), lake_state(kind="PROXY", cap="NEARBY_GAUGE_PROXY"), NOW)
    assert s["kind"] == "unavailable"


def test_tier_d_and_unknown_say_so_and_publish_no_zones():
    for tier in ("D", "UNKNOWN"):
        s, _ = build_state(candidate(tier=tier), lake_state(), NOW)
        assert "referenceZones" not in s and "effectiveZones" not in s
        assert any("No measured or contour depth evidence" in l for l in s["limitations"])


def test_modeled_evidence_cannot_create_zones_even_if_manifest_carries_shares():
    rec = candidate(tier="D", referenceZones={"cumulative": {"3.0": 0.1}, "intervalFt": 2, "coverage": 1, "source": "globathy"})
    s, _ = build_state(rec, lake_state(), NOW)
    assert "referenceZones" not in s


def test_contour_lake_zones_and_unverified_survey_reference():
    rec = candidate(tier="A", evidence={"tier": "A", "kind": "contour", "coverage": 0.9, "intervalFt": 2},
                    referenceZones={"cumulative": {"3.0": 0.1, "6.0": 0.2, "10.0": 0.3}, "intervalFt": 2, "coverage": 0.9, "source": "TWDB", "referenceStatus": "UNVERIFIED"})
    s, _ = build_state(rec, lake_state(), NOW)
    assert s["referenceZones"]["shareUnder3Ft"] == 0.1 and s["referenceZones"]["evidenceKind"] == "contour"
    assert s["effectiveZones"] == {"available": False, "reason": "SURVEY_REFERENCE_POOL_UNVERIFIED"}
    assert s["effectiveDepth"]["mode"] == "shiftOnly"                                  # not upgraded to zoned
    assert s["coverage"]["knownAreaShare"] == 0.9 and s["coverage"]["unknownAreaShare"] == 0.1 and s["coverage"]["contourIntervalFt"] == 2
    rec["referenceZones"]["referenceStatus"] = "VERIFIED"
    s2, _ = build_state(rec, lake_state(593.0), NOW)
    assert s2["effectiveZones"]["available"] and s2["effectiveDepth"]["mode"] == "zoned"


def test_coarse_5ft_survey_publishes_only_the_10ft_band():
    rec = candidate(tier="B", evidence={"tier": "B", "kind": "contour"}, referenceZones={"cumulative": {"10.0": 0.3}, "intervalFt": 5, "coverage": 1, "source": "MN"})
    s, _ = build_state(rec, lake_state(), NOW)
    z = s["referenceZones"]
    assert "shareUnder3Ft" not in z and "share3To6Ft" not in z and z["shareUnder10Ft"] == 0.3


def test_plan_publish_then_skip_then_publish_on_change():
    rec, ls = candidate(), lake_state()
    s, _ = build_state(rec, ls, NOW, manifest_version="m1")
    assert plan(None, rec, ls, "m1")["action"] == "PUBLISH"
    assert plan(s, rec, ls, "m1")["action"] == "SKIP"
    assert plan(s, rec, lake_state(593.4, obs="2026-10-13T19:00:00Z"), "m1")["action"] == "PUBLISH"
    assert plan(s, rec, ls, "m2")["action"] == "PUBLISH"
    assert input_fingerprint(rec, ls, "m1") == input_fingerprint(copy.deepcopy(rec), copy.deepcopy(ls), "m1")


# ── publisher ─────────────────────────────────────────────────────────────────────────────────────────────
def manifest():
    return {"manifestVersion": "t1", "candidates": [
        candidate(lakeId="Guntersville|AL"),
        candidate(lakeId="Lake Hartwell|SC", pool=660.0, rollout="HIGH_CONFIDENCE"),
        candidate(lakeId="Blocked Lake|XX", possible=False, rollout="BLOCKED", blockedReasons=["NO_VERIFIED_LEVEL_BINDING"]),
        candidate(lakeId="Awaiting Lake|YY", rollout="MEDIUM_CONFIDENCE")]}


def test_publish_writes_only_depth_owned_paths_and_skips_unevaluated_states():
    w = DryRunWriter()
    rep = publish(manifest(), {"Guntersville|AL": lake_state(593.6), "Lake Hartwell|SC": lake_state(649.4)}, w, NOW)
    assert rep["ok"], rep["errors"]
    tree = w.tree
    assert tree["lakes"][lake_key("Guntersville|AL")]["states"]["depth"]["effectiveDepth"]["shiftFt"] == -1.4
    assert tree["lakes"][lake_key("Lake Hartwell|SC")]["states"]["depth"]["effectiveDepth"]["shiftFt"] == pytest.approx(-10.6)
    assert lake_key("Blocked Lake|XX") not in tree.get("lakes", {}) and lake_key("Awaiting Lake|YY") not in tree.get("lakes", {})
    ready = {l: tree["lakeFleet"][lake_key(l)]["readiness"]["depth"] for l in ("Guntersville|AL", "Blocked Lake|XX", "Awaiting Lake|YY")}
    assert ready == {"Guntersville|AL": "CALIBRATION", "Blocked Lake|XX": "BLOCKED", "Awaiting Lake|YY": "PROFILED"}
    reg = tree["brains"]["depth"]
    assert reg["status"] == "PROFILED" and reg["stalenessModel"] == "FINGERPRINT" and reg["publishMode"].startswith("shadow") and reg["dependsOn"] == ["lake-brain"]
    assert reg["validation"]["status"] == "NOT_VALIDATED" and reg["models"]["active"] is None
    assert "score" not in reg                                   # Depth never carries an official score
    for patch in w.patches:
        for path in patch:
            assert path.split("/")[0] in ("lakes", "snapshots", "lakeFleet", "brains", "validation", "health", "activity")


def test_second_publish_skips_unchanged_inputs():
    w = DryRunWriter()
    ls = {"Guntersville|AL": lake_state(593.6)}
    m = {"manifestVersion": "t1", "candidates": [candidate()]}
    publish(m, ls, w, NOW)
    r2 = publish(m, ls, w, NOW)
    assert r2["skippedUnchanged"] == 1


def test_writer_refuses_other_brains_paths():
    w = DryRunWriter()
    for bad in ("lakes/Guntersville_AL/states/lake", "lakes/Guntersville_AL/states/wind", "lakeFleet/Guntersville_AL/readiness/lake",
                "brains/lake-brain", "scores/depth", "lakeFleet/Guntersville_AL/stale", "control/x"):
        with pytest.raises(WriteError):
            w.patch({bad: {"x": 1}})


def test_publish_survives_one_bad_lake():
    m = manifest()
    m["candidates"][0]["evidence"] = "not-a-dict"                # malformed record
    w = DryRunWriter()
    rep = publish(m, {"Lake Hartwell|SC": lake_state(649.4), "Guntersville|AL": lake_state()}, w, NOW)
    assert rep["errors"] and rep["health"] == "DEGRADED"
    assert lake_key("Lake Hartwell|SC") in w.tree["lakes"]


def test_activity_event_is_depth_owned_and_pruned_by_own_brain():
    w = DryRunWriter()
    publish(manifest(), {"Guntersville|AL": lake_state()}, w, NOW)
    ev = w.tree["activity"]
    assert ev and all(e["brainId"] == "depth" and "-depth-" in k for k, e in ev.items())


def test_key_collision_is_refused():
    m = {"manifestVersion": "x", "candidates": [candidate(lakeId="A B|XX"), candidate(lakeId="A-B|XX")]}
    rep = publish(m, {}, DryRunWriter(), NOW)
    assert not rep["ok"] and "collision" in rep["errors"][0]
