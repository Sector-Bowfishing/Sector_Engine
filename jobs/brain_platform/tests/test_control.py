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
    f = o["fleet"]
    assert (f["lakes"], f["evaluatedByIntelligence"], f["staleSlots"], f["readinessBySlot"]) == (2, 1, {"wind": 1}, {"wind": {"CALIBRATION": 1}})
    assert f["staleLakes"] == 1 and f["withSlots"] == 2 and f["publishedBySlot"]["wind"] == 2 and f["summarizedAt"] == o["updatedAt"]
    assert o["sources"]["noaa-nbm-v5"]["stale"] is True and o["sources"]["noaa-nbm-v5"]["failures24h"] == 0
    assert [w["brainId"] for w in o["workNext"]][:2] == ["wind", "sector-intelligence"]
    assert o["brains"]["lake-brain"]["status"] == "NOT_REGISTERED"
    writes = {"control/overview": o, **{f"control/fleet/{k}": fleet_rollup(k, r, NOW) for k, r in fleet.items()}}
    assert_owned(writes, "brain-platform")


def test_brain_summary_mirrors_uncapped_gates_and_dimensions():
    """Ops must be able to show WHY a displayed score is capped without reading /scores/{id}: Engine mirrors the facts."""
    score = {"value": 3.0, "uncapped": 6.3, "scale": 10, "basis": "COMPUTED", "scoreVersion": "lake-brain-score-v1",
             "scoreBlockers": [{"gate": "coverage", "cap": 3.0, "why": "5 of 621 lakes profiled (1 % < 10 %)"},
                               {"gate": "validation", "cap": 5.0, "why": "validation NOT_VALIDATED"},
                               {"dimension": "validation", "why": "/validation/lake-brain: NOT_VALIDATED"}],
             "scoreBreakdown": {"coverage": {"value": 1.0, "weight": 20, "status": "SCORED", "evidence": "long text stays on /scores"},
                                "validation": {"value": 0.0, "weight": 15, "status": "SCORED"}}}
    reg = {"displayName": "Lake Brain", "status": "CALIBRATION", "lastSuccessfulRun": ISO(1), "staleAfterHours": 3}
    s = brain_summary("lake-brain", reg, None, None, score, {}, NOW)
    assert s["score"]["uncapped"] == 6.3 and s["score"]["value"] == 3.0
    assert s["score"]["gates"] == [{"gate": "coverage", "cap": 3.0, "why": "5 of 621 lakes profiled (1 % < 10 %)"},
                                   {"gate": "validation", "cap": 5.0, "why": "validation NOT_VALIDATED"}]  # dimension rows are not gates
    assert s["dimensions"]["coverage"] == {"value": 1.0, "scale": 10, "weight": 20, "status": "SCORED"}  # no evidence text
    # nothing published -> nothing invented
    bare = brain_summary("lake-brain", reg, None, None, {"value": 3.0}, {}, NOW)
    assert "dimensions" not in bare and "gates" not in bare["score"] and "uncapped" not in bare["score"]


# ---- freshness semantics (Cortex 2.2 FD-07; Firebase remediation 2026-10-21) -----------------------------------------------------------------
from sector_brain_platform.control import STALE_BY_AGE, STALE_BY_FLAG, fleet_summary, slot_max_age  # noqa: E402

LATE = dt.datetime(2026, 10, 21, 15, 0, tzinfo=dt.timezone.utc)          # nine days after the slots below were written


def _paused_clarity_row():
    """Production shape on 2026-10-21: Clarity paused since 2026-10-12, so its slot still says stale=false; Wind is current."""
    return {"lakeId": "x", "lastUpdatedAt": "2026-10-12T09:00:00Z",                                     # orphaned parent: must be ignored
            "slots": {"waterClarity": {"lastUpdatedAt": "2026-10-12T09:00:00Z", "stale": False},
                      "wind": {"lastUpdatedAt": "2026-10-21T14:07:00Z", "stale": False},
                      "depth": {"lastUpdatedAt": "2026-10-01T00:00:00Z", "stale": False}}}


def test_policy_age_marks_a_paused_brains_slot_stale_and_says_why():
    max_age = {"waterClarity": 26.0, "wind": 1.5}
    r = fleet_rollup("x", _paused_clarity_row(), LATE, max_age)
    assert r["stale"] is True and r["staleSlots"] == {"waterClarity": STALE_BY_AGE} and r["staleRule"] == "SLOT_FLAG_OR_POLICY_AGE"
    assert r["lastUpdatedAt"] == "2026-10-21T14:07:00Z"                     # publication time of the newest slot, never the orphaned parent
    assert r["rolledUpAt"] == "2026-10-21T15:00:00Z"                       # projection time is separate


def test_brain_flag_still_wins_and_fresh_slots_stay_fresh():
    row = _paused_clarity_row()
    row["slots"]["wind"]["stale"] = True
    r = fleet_rollup("x", row, dt.datetime(2026, 10, 12, 10, 0, tzinfo=dt.timezone.utc), {"waterClarity": 26.0, "wind": 1.5})
    assert r["staleSlots"] == {"wind": STALE_BY_FLAG}                     # Clarity is 1 h old: fresh; the shadow Depth slot never counts


def test_without_a_policy_the_rollup_keeps_the_persisted_flag_rule():
    r = fleet_rollup("x", _paused_clarity_row(), LATE)
    assert r["stale"] is False and r["staleRule"] == "SLOT_FLAG" and "staleSlots" not in r


def test_slot_max_age_comes_from_the_effective_policy_and_ignores_non_time_models():
    m = slot_max_age({"wind": {"freshness": {"stalenessModel": "TIME", "staleAfterHours": 1.5}},
                      "biological-state": {"freshness": {"stalenessModel": "VERSION"}}},
                     {"water-clarity": {"staleAfterHours": 26}, "lake-brain": {"stalenessModel": "FINGERPRINT"}})
    assert m == {"wind": 1.5, "waterClarity": 26.0}


def test_fleet_summary_counts_age_stale_slots_separately():
    fs = fleet_summary({"x": _paused_clarity_row()}, LATE, max_age={"waterClarity": 26.0, "wind": 1.5})
    assert fs["staleLakes"] == 1 and fs["staleSlots"] == {"waterClarity": 1} and fs["staleSlotsByAge"] == {"waterClarity": 1}


def test_recorded_health_is_not_presented_as_current_when_the_brain_is_stale():
    reg = {"stalenessModel": "TIME", "staleAfterHours": 26, "lastSuccessfulRun": "2026-10-12T09:00:00Z"}
    s = brain_summary("water-clarity", reg, {"status": "HEALTHY", "lastRun": "2026-10-12T09:00:00Z"}, None, None, {}, LATE)
    assert s["health"] == "HEALTHY" and s["healthBasis"] == "RECORDED_AT_LAST_EXECUTION"
    assert s["stale"] is True and s["healthCurrent"] is False


def test_lake_slot_is_not_aged_from_its_profile_timestamp():
    """Production 2026-10-22: Lake's fleet slot lastUpdatedAt is the profile update time (2026-10-13) while the state was published
    2026-10-21T12:02Z under a 26 h policy. Aging the slot by it marked 5 fresh pilot lakes stale; the Lake slot is exempt from AGE."""
    m = slot_max_age({"lake-brain": {"freshness": {"staleAfterHours": 26}}, "wind": {"freshness": {"stalenessModel": "TIME", "staleAfterHours": 1.5}}}, {})
    assert "lake" not in m and m["wind"] == 1.5
    row = {"lakeId": "x", "slots": {"lake": {"lastUpdatedAt": "2026-10-13T18:53:14Z", "stale": False},
                                    "wind": {"lastUpdatedAt": "2026-10-21T14:07:00Z", "stale": False}}}
    r = fleet_rollup("x", row, LATE, m)
    assert r["stale"] is False and "staleSlots" not in r
    row["slots"]["lake"]["stale"] = True
    assert fleet_rollup("x", row, LATE, m)["staleSlots"] == {"lake": STALE_BY_FLAG}           # Lake's own flag still counts
