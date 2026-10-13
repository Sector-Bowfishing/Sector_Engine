"""Control plane: Engine computes what Ops shows; unknown stays absent; the platform writer owns it."""
import datetime as dt

from sector_brain_platform import assert_owned, brain_stale, brain_summary, fleet_rollup, overview

NOW = dt.datetime(2026, 10, 12, 12, 0, tzinfo=dt.timezone.utc)
ISO = lambda h: (NOW - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731


def test_brain_stale_is_engine_time_rule():
    assert brain_stale({"staleAfterHours": 3, "lastSuccessfulRun": ISO(1)}, None, NOW) == (False, None)
    stale, why = brain_stale({"staleAfterHours": 3, "lastSuccessfulRun": ISO(5)}, None, NOW)
    assert stale is True and "> 3 h" in why
    assert brain_stale({"stalenessModel": "VERSION", "lastSuccessfulRun": ISO(500)}, None, NOW) == (False, None)
    assert brain_stale({"staleAfterHours": 3}, None, NOW) == (None, "no successful run recorded")
    assert brain_stale(None, None, NOW) == (None, "not registered")


def test_brain_summary_collects_without_inventing():
    reg = {"displayName": "Water Temperature", "status": "CALIBRATION", "health": "HEALTHY", "staleAfterHours": 6,
           "lastSuccessfulRun": ISO(30), "supportedLakeCount": 621, "directoryLakeCount": 621,
           "readinessCounts": {"CALIBRATION": 621}, "versions": [{"version": "surface-energy-balance-v2", "status": "CURRENT"}],
           "researchCandidate": {"candidate": "Water Temp V2", "status": "RESEARCH", "promoted": False},
           "platform": {"conformant": True, "implementation": "SectorEngine.Brain (Swift)"}}
    s = brain_summary("water-temp", reg, {"status": "HEALTHY", "lastRun": ISO(30)}, {"status": "GLOBAL_HOLDOUT_ONLY"},
                      {"value": 3.0, "scale": 10, "basis": "FROZEN", "scoreVersion": "v", "scoreBlockers": [{"gate": "level4", "why": "truth"}],
                       "nextScoreOpportunity": "protected truth"}, {}, NOW)
    assert s["stale"] is True and s["scheduled"] is False and s["score"]["value"] == 3.0
    assert s["activeModel"] == {"modelId": "surface-energy-balance-v2", "status": "PRODUCTION"}
    assert s["candidateModel"]["promoted"] is False and s["validation"]["status"] == "GLOBAL_HOLDOUT_ONLY"
    assert s["blockers"] == ["level4: truth"] and s["coverage"]["onLadder"] == 621 and s["platform"]["conformant"]
    unreg = brain_summary("wind", None, None, None, None, {}, NOW)
    assert unreg["status"] == "NOT_REGISTERED" and unreg["stale"] is None and "score" not in unreg


def test_fleet_rollup_from_slots():
    row = {"lakeId": "A|AL", "readiness": {"waterTemp": "CALIBRATION", "wind": "CALIBRATION"},
           "slots": {"waterTemp": {"stale": True, "issueCount": 1, "lastUpdatedAt": ISO(2)},
                     "wind": {"stale": False, "evidenceStale": True, "issueCount": 0, "generatedAt": ISO(1)}}}
    r = fleet_rollup("A_AL", row, NOW)
    assert r["lastUpdatedAt"] == ISO(1) and r["stale"] is True and r["evidenceStale"] is True and r["issueCount"] == 1 and r["slotsPublished"] == 2
    assert fleet_rollup("X", None, NOW) is None
    assert "stale" not in fleet_rollup("E", {"lakeId": "E|AL"}, NOW)      # no slots → unknown stays absent


def test_overview_is_owned_by_the_platform_writer_and_explains_work_next():
    brains = {"sector-intelligence": {"status": "CALIBRATION", "stalenessModel": "FINGERPRINT", "engineServing": {"revision": "r1", "lineageVerified": True},
                                      "dependencies": {b: {"connectionStatus": "CONNECTED"} for b in ("lake-brain", "water-temp", "water-clarity", "wind", "biological-state")}},
              "wind": {"status": "CALIBRATION", "staleAfterHours": 1.5, "lastSuccessfulRun": ISO(0.5), "platform": {"conformant": True}}}
    scores = {"wind": {"value": 3.1, "nextScoreOpportunity": "field validation"}, "sector-intelligence": {"value": 4.5, "nextScoreOpportunity": "validate"}}
    fleet = {"A_AL": {"lakeId": "A|AL", "readiness": {"wind": "CALIBRATION"}, "slots": {"wind": {"stale": False}, "intelligence": {"kind": "evaluated"}}},
             "B_AL": {"lakeId": "B|AL", "slots": {"wind": {"stale": True}}}}
    o = overview(brains=brains, health={"wind": {"status": "HEALTHY"}}, validation={}, scores=scores,
                 engine={"engineScore": 6.1, "engineScoreVersion": "engine-score-v1", "dimensions": {"x": {"value": 1, "weight": 10, "status": "SCORED"}}, "blockers": []},
                 fleet=fleet, sources={"noaa-nbm-v5": {"ownerBrainId": "wind", "staleThresholdHours": 3, "latestObservationAt": ISO(5)}},
                 health_sources={"noaa-nbm-v5": {"status": "HEALTHY", "failures24h": 0}}, jobs={}, now=NOW)
    assert o["engine"]["score"] == 6.1 and o["engine"]["dependencyCompleteness"]["consumed"] == 5 and o["engine"]["dependencyCompleteness"]["consumedByCustomerPath"] == 0
    assert o["engine"]["worstBrainHealth"] == "UNKNOWN" and o["engine"]["brainsConformant"] == 1
    assert o["fleet"] == {"lakes": 2, "evaluatedByIntelligence": 1, "staleSlots": {"wind": 1}, "readinessBySlot": {"wind": {"CALIBRATION": 1}}}
    assert o["sources"]["noaa-nbm-v5"]["stale"] is True and o["sources"]["noaa-nbm-v5"]["failures24h"] == 0
    assert [w["brainId"] for w in o["workNext"]][:2] == ["wind", "sector-intelligence"]
    assert o["brains"]["lake-brain"]["status"] == "NOT_REGISTERED"
    writes = {"control/overview": o, **{f"control/fleet/{k}": fleet_rollup(k, r, NOW) for k, r in fleet.items()}}
    assert_owned(writes, "brain-platform")
