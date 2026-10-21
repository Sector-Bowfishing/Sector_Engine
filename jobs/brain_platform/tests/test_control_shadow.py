"""SHADOW Brains in the control plane (Depth, Vegetation): visible, never scored, never part of a roll-up. A shadow slot on a lake never makes
the lake stale or adds issues; a shadow registry never enters worst-health, conformance or dependency completeness."""
import datetime as dt

from sector_brain_platform import control as C

NOW = dt.datetime(2026, 10, 20, 15, 0, tzinfo=dt.timezone.utc)
STALE = {"stale": True, "issueCount": 7, "lastUpdatedAt": "2026-10-01T00:00:00Z", "readiness": "CALIBRATION"}
FRESH = {"stale": False, "issueCount": 0, "lastUpdatedAt": "2026-10-20T14:00:00Z", "readiness": "PRODUCTION"}


def _overview(brains, fleet=None):
    return C.overview(brains=brains, health={}, validation={}, scores={"depth": {"value": 9.9}}, engine=None, fleet=fleet or {}, sources={},
                      health_sources={}, jobs={}, now=NOW)


def test_shadow_brains_are_depth_and_vegetation_and_never_upstream():
    assert set(C.SHADOW_BRAINS) == {"depth", "vegetation"}
    assert not set(C.SHADOW_BRAINS) & set(C.ALL_BRAINS)


def test_a_registered_shadow_brain_is_visible_without_a_score():
    ov = _overview({"depth": {"status": "SHADOW", "schedule": {"jobId": "x"}, "research": {"maturity": "offline"}}})
    d = ov["brains"]["depth"]
    assert ov["shadowBrains"] == ["depth"] and d["shadow"] is True and d["scoreStatus"] == "NOT_ESTABLISHED"
    assert "score" not in d and d["scheduled"] is False                     # a registry schedule hint never makes a shadow Brain "scheduled"


def test_an_unregistered_shadow_brain_is_absent():
    ov = _overview({})
    assert "depth" not in ov["brains"] and "vegetation" not in ov["brains"] and "shadowBrains" not in ov


def test_a_stale_shadow_slot_never_makes_a_lake_stale_or_adds_issues():
    row = {"lakeId": "Test|ST", "slots": {"depth": STALE, "vegetation": STALE, "lake": FRESH}}
    r = C.fleet_rollup("Test_ST", row, NOW)
    assert r["stale"] is False and r["issueCount"] == 0 and r["slotsPublished"] == 3
    fs = C.fleet_summary({"Test_ST": row}, NOW)
    base = C.fleet_summary({"Test_ST": {"lakeId": "Test|ST", "slots": {"lake": FRESH}}}, NOW)
    assert {k: v for k, v in fs.items() if k != "publishedBySlot"} == {k: v for k, v in base.items() if k != "publishedBySlot"}
    assert fs["publishedBySlot"] == {"depth": 1, "vegetation": 1, "lake": 1}
