"""A real publish() run over the packaged catalog, answered from the hand-built fixtures: what is written, for which lakes, and that every
state validates against generation-dam-state-v1. Offline."""
import json
import os

from generation_brain import contract as C
from generation_support import NOW, REPO, run

import jsonschema  # noqa: E402  (research/tools/requirements.txt)

SCHEMA = json.load(open(os.path.join(REPO, "brains", "generation", "contracts", "generation-dam-state-v1.schema.json")))


def validate(instance, schema):
    return [e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(instance)]


def test_only_lakes_with_a_bound_allowed_source_get_a_state():
    rep, w, f = run()
    lakes = w.tree["lakes"]
    assert set(lakes) == {"Guntersville_AL", "Wheeler_AL"}                   # Bull Shoals: SWPA access check open; Lake Murray: permission required
    assert rep["readinessCounts"] == {"CALIBRATION": 1, "DEGRADED": 1}
    assert all(p != "swpa" for p, _, _ in f.requests)


def test_guntersville_state_is_the_operators_picture_and_validates():
    _, w, _ = run()
    s = w.tree["lakes"]["Guntersville_AL"]["states"]["generation"]
    assert validate(s, SCHEMA) == []
    assert s["kind"] == C.OBSERVED and s["release"]["status"] == C.GENERATING and s["release"]["dischargeCfs"] == 19500.0
    assert s["schedule"]["now"]["unitsOn"] == 1 and s["schedule"]["nextShutdownAt"] == "2026-11-22T21:00:00Z"
    assert s["freshness"]["tier"] == C.TIER_TRANSITION and s["freshness"]["recheckMinutes"] == 60
    assert s["agencies"] == ["Tennessee Valley Authority"] and s["lane"] == "INTERNAL"
    assert w.tree["snapshots"]["Guntersville_AL"]["latest"]["generation"] == s


def test_a_failed_source_publishes_an_honest_unavailable_state():
    _, w, _ = run()
    s = w.tree["lakes"]["Wheeler_AL"]["states"]["generation"]
    assert validate(s, SCHEMA) == []
    assert s["kind"] == C.UNAVAILABLE and s["release"]["status"] == C.UNKNOWN and s["release"]["dischargeCfs"] is None
    assert s["sources"][0]["ok"] is False and s["freshness"]["stale"] is True


def test_a_dam_is_not_read_again_before_its_next_check():
    rep, w, f = run()
    n = len(f.requests)
    rep2, _, f2 = run(writer=w)
    assert rep2["notDue"] == 2 and rep2["evaluated"] == 0 and len(f2.requests) == 0 and n > 0
    rep3, _, _ = run(now=NOW.replace(hour=21), writer=w)                   # Guntersville (TRANSITION, 60 min) is due; Wheeler (UNKNOWN, 120) is not
    assert rep3["evaluated"] == 1 and rep3["notDue"] == 1
    rep4, _, f4 = run(now=NOW.replace(hour=22), writer=w)
    assert rep4["evaluated"] == 2 and len(f4.requests) > 0


def test_fleet_scope_records_why_other_dam_lakes_have_no_state():
    rep, w, _ = run(scope="fleet")
    fleet = w.tree["lakeFleet"]
    assert fleet["Bull_Shoals_Lake_AR"]["readiness"]["generation"] == "ACCESS_BLOCKED"
    assert fleet["Lake_Murray_SC_SC"]["readiness"]["generation"] == "NOT_BOUND"
    assert "states" not in (w.tree["lakes"].get("Bull_Shoals_Lake_AR") or {})


def test_registry_reports_coverage_and_stays_disabled():
    _, w, _ = run()
    reg = w.tree["brains"]["generation"]
    assert reg["orchestration"]["status"] == "DISABLED" and reg["scoreStatus"] == "NOT_ESTABLISHED"
    assert reg["fleet"]["damLakeCount"] == 4 and reg["fleet"]["directoryLakeCount"] == 621 and reg["fleet"]["noDamLakeCount"] == 220   # 4 = the test catalog
    assert reg["sourceAccess"]["swpa"]["status"] == "ACCESS_CHECK_REQUIRED" and "swpa" not in reg["sourceIds"]
    assert reg["knowledgeRelease"]["approvalStatus"] == "NOT_RECORDED"
