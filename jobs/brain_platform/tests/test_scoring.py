"""Scoring rubrics: today's published state must score honestly; a mature state must climb the ladders."""
import datetime as dt
import json
import os

from sector_brain_platform import score_lake, score_biological, score_intelligence, frozen_score, ladder

NOW = dt.datetime(2026, 10, 12, 12, 0, tzinfo=dt.timezone.utc)
FIX = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "brains", "scoring")


def pilot_profile(sufficient=False, guide=True, zone=True, level="DIRECT_OPERATOR_POOL"):
    return {"sourceCapability": {"level": level, "bindingStatus": "REVIEWED"},
            "operatingPools": {"guideCurve": {"available": guide}, "operatingZoneSource": "TVA" if zone else None},
            "historicalCoverage": {"baselineStatus": "SUFFICIENT" if sufficient else "INSUFFICIENT"}}


def test_ladder():
    assert [ladder(x) for x in (0, 0.001, 0.05, 0.10, 0.25, 0.5, 0.75, 0.9, 1.0)] == [0, 1, 2, 3, 5, 7, 9, 10, 10]
    assert ladder(None) == 0


def test_lake_today_is_capped_by_coverage_but_breakdown_shows_pilot_quality():
    profiles = {"Guntersville_AL": pilot_profile(), "Wheeler_AL": pilot_profile(), "Wilson_AL": pilot_profile(guide=False),
                "Pickwick_Lake_TN": pilot_profile(), "Lake_Hartwell_SC": pilot_profile(sufficient=True)}
    states = {k: {"kind": "OBSERVED", "floodPoolState": "NORMAL"} for k in profiles}
    s = score_lake({"registry": {"health": "HEALTHY", "directoryLakeCount": 621}, "validation": {"status": "NOT_VALIDATED"},
                    "health": {"status": "HEALTHY"}, "profiles": profiles, "states": states}, NOW)
    assert s["value"] == 3.0 and s["basis"] == "COMPUTED"
    b = s["scoreBreakdown"]
    assert b["sourceAuthority"]["value"] == 10 and b["operatorPlan"]["value"] == 10 and b["trendQuality"]["value"] == 10
    assert b["historyQuality"]["value"] == 2 and b["coverage"]["value"] == 1 and b["validation"]["value"] == 0
    assert s["uncapped"] == 4.7 and s["completenessPct"] == 100
    assert {g.get("gate") for g in s["scoreBlockers"] if "gate" in g} == {"coverage", "validation"}
    assert s["scoreBlockers"][0]["cap"] == 3.0


def test_lake_mature_state_climbs():
    profiles = {f"L{i}": pilot_profile(sufficient=True) for i in range(600)}
    states = {k: {"kind": "observed", "floodPoolState": "NORMAL"} for k in profiles}
    s = score_lake({"registry": {"health": "HEALTHY", "directoryLakeCount": 621}, "validation": {"status": "VALIDATED"},
                    "health": {"status": "HEALTHY"}, "profiles": profiles, "states": states}, NOW)
    assert s["value"] == 10.0 and s["scoreBlockers"] == []


def test_lake_unknown_when_nothing_published():
    s = score_lake({"registry": {}, "validation": None, "health": None, "profiles": {}, "states": {}, "directoryLakeCount": 621}, NOW)
    assert s["value"] == 0.0
    assert s["scoreBreakdown"]["sourceAuthority"]["status"] == "UNKNOWN"
    assert s["completenessPct"] < 100
    assert any(g.get("gate") == "health" for g in s["scoreBlockers"])


def species(score, maturity="RESEARCH", contradictions=0, assessed=True):
    return {"assessment": "ASSESSED" if assessed else "NOT_ASSESSED", "researchMaturity": maturity,
            "knowledge": {"rubric": "species-v2", "overallRounded": score}, "contradictionCount": contradictions}


def test_biological_today():
    sp = {f"s{i}": species(v, contradictions=c) for i, (v, c) in enumerate([(3.5, 3), (4.0, 0), (2.5, 1), (5.0, 0)])}
    sp["s_na"] = species(0, assessed=False)
    reg = {"responsibilities": {"speciesKnowledge": {"speciesCount": 5, "assessedCount": 4, "notAssessedCount": 1},
                                "biologicalState": {"status": "NOT_STARTED"}}}
    s = score_biological({"registry": reg, "species": sp, "intelligenceRegistry": {"dependencies": {"biological-state": {"connectionStatus": "NOT_CONNECTED"}}}}, NOW)
    b = s["scoreBreakdown"]
    assert b["registryCompleteness"]["value"] == 10 and b["assessedCoverage"]["value"] == 8 and b["knowledgeDepth"]["value"] == 3.8
    assert b["evidenceQuality"]["value"] == 2 and b["biologicalStateImpl"]["value"] == 0 and b["regionalTransfer"]["status"] == "UNKNOWN"
    assert b["contradictionsGaps"]["value"] == 8.0 and b["productionIntegration"]["value"] == 0
    assert s["completenessPct"] == 95
    assert s["value"] <= 4.0 and s["scoreBlockers"][0]["cap"] == 4.0
    assert s["uncapped"] < 10 and s["value"] == min(s["uncapped"], 4.0)


def test_biological_is_not_an_average_of_species_scores():
    sp = {f"s{i}": species(10.0, maturity="VALIDATED") for i in range(10)}
    reg = {"responsibilities": {"speciesKnowledge": {"speciesCount": 10, "assessedCount": 10, "notAssessedCount": 0},
                                "biologicalState": {"status": "NOT_STARTED"}}}
    s = score_biological({"registry": reg, "species": sp, "intelligenceRegistry": {}}, NOW)
    assert s["value"] == 4.0, "perfect species knowledge still capped: no Biological State"


def test_intelligence_today_is_one():
    reg = {"health": "HEALTHY", "evaluatedLakeCount": 0, "supportedLakeCount": 0, "schedule": {"cadence": "none"},
           "dependencies": {b: {"connectionStatus": "NOT_CONNECTED"} for b in ("lake-brain", "water-temp", "water-clarity", "wind", "biological-state")}}
    s = score_intelligence({"registry": reg, "validation": {"status": "NOT_VALIDATED"}, "health": {"status": "HEALTHY"}, "directoryLakeCount": 621}, NOW)
    assert s["value"] == 1.0
    assert s["scoreBreakdown"]["dependencyHandling"]["value"] == 10 and s["scoreBreakdown"]["runtime"]["value"] == 5
    assert s["scoreBreakdown"]["synthesisQuality"]["status"] == "UNKNOWN" and s["scoreBreakdown"]["provenance"]["status"] == "UNKNOWN"
    assert s["completenessPct"] == 80
    assert [g["gate"] for g in s["scoreBlockers"] if "gate" in g] == ["evaluations", "connectivity", "validation"]


def test_frozen_scores_pass_through_verbatim():
    fz = json.load(open(os.path.join(FIX, "frozen-scores.json")))
    for bid, expect in (("water-temp", 3.0), ("water-clarity", 8.0), ("wind", 3.1)):
        s = frozen_score(fz[bid])
        assert s["value"] == expect and s["basis"] == "FROZEN" and s["scale"] == 10
        assert s["scoreVersion"] and s["scoreRubric"] and s["scoreUpdatedAt"] and s["scoreBlockers"]


from sector_brain_platform import score_engine


def _engine_facts(consumed=0, validated=False, lineage=True, failed=False):
    deps = {b: {"connectionStatus": "CONNECTED" if i < consumed else "NOT_CONNECTED"}
            for i, b in enumerate(("lake-brain", "water-temp", "water-clarity", "wind", "biological-state"))}
    val = {b: {"status": "VALIDATED" if validated else "NOT_VALIDATED"} for b in deps} | {"sector-intelligence": {"status": "NOT_VALIDATED"}}
    val["water-temp"] = {"status": "VALIDATED" if validated else "GLOBAL_HOLDOUT_ONLY"}
    health = {b: {"status": "FAILED" if (failed and b == "wind") else "HEALTHY"} for b in list(deps) + ["sector-intelligence"]}
    fleet = {f"L{i}": {"waterTemp": "PRODUCTION", "intelligence": "DISCOVERED"} for i in range(600)} | {f"X{i}": {"intelligence": "DISCOVERED"} for i in range(21)}
    return {"intelligenceRegistry": {"dependencies": deps, "engineServing": {"lineageVerified": lineage}}, "validation": val,
            "healthBrains": health, "healthJobs": {"wind-hourly": {"status": "HEALTHY"}}, "fleetReadiness": fleet}


def test_engine_score_today_is_gate_capped_and_explainable():
    scores = {"lake-brain": {"value": 3.0}, "water-temp": {"value": 3.0}, "water-clarity": {"value": 8.0}, "wind": {"value": 3.1},
              "biological-state": {"value": 3.5}, "sector-intelligence": {"value": 1.0}}
    e = score_engine(_engine_facts(), scores, NOW)
    d = e["dimensions"]
    assert d["specialistBrainMaturity"]["value"] == 4.1 and d["integrationCompleteness"]["value"] == 0
    assert d["lakeCoverage"]["value"] == 9.7 and d["scientificValidation"]["value"] == 0.8
    assert d["runtimeReliability"]["value"] == 10 and d["productionConsistency"]["value"] == 10
    assert d["platformHealth"]["status"] == "UNKNOWN" and e["completenessPct"] == 90
    assert e["engineScore"] == 4.0 and e["uncapped"] == 4.1
    assert e["blockers"][0]["gate"] == "synthesisDisconnected" and e["strongestArea"] in ("runtimeReliability", "productionConsistency")
    assert e["weakestArea"] == "integrationCompleteness" and e["brainScores"]["wind"] == 3.1


def test_engine_score_is_not_an_average_of_brain_scores():
    scores = {b: {"value": 9.0} for b in ("lake-brain", "water-temp", "water-clarity", "wind", "biological-state", "sector-intelligence")}
    e = score_engine(_engine_facts(consumed=0, validated=True), scores, NOW)
    assert e["engineScore"] == 4.0, "nines everywhere still capped while Intelligence consumes nothing"
    e2 = score_engine(_engine_facts(consumed=5, validated=True, lineage=True), scores, NOW)
    assert e2["engineScore"] > 8.0 and e2["blockers"] == []
    e3 = score_engine(_engine_facts(consumed=5, validated=True, lineage=False), scores, NOW)
    assert e3["engineScore"] == 3.0
    e4 = score_engine(_engine_facts(consumed=5, validated=True, failed=True), scores, NOW)
    assert e4["engineScore"] == 5.0


def test_engine_score_unknown_specialist_leaves_maturity_unknown():
    e = score_engine(_engine_facts(), {"lake-brain": {"value": 3.0}}, NOW)
    assert e["dimensions"]["specialistBrainMaturity"]["status"] == "UNKNOWN" and e["brainScores"]["wind"] is None


def _bio_with_transfer(ts):
    sp = {f"s{i}": species(4.0) for i in range(4)}
    reg = {"responsibilities": {"speciesKnowledge": {"speciesCount": 4, "assessedCount": 4, "notAssessedCount": 0},
                                "biologicalState": {"status": "IN_PROGRESS"}}}
    if ts is not None:
        reg["transferSummary"] = ts
    return score_biological({"registry": reg, "species": sp, "intelligenceRegistry": {}}, NOW)


def test_regional_transfer_unknown_without_summary_keeps_v1():
    s = _bio_with_transfer(None)
    assert s["scoreBreakdown"]["regionalTransfer"]["status"] == "UNKNOWN" and s["scoreVersion"] == "biological-state-score-v1"


def test_regional_transfer_scored_from_summary():
    s = _bio_with_transfer({"usableRules": 48, "byTransferability": {"TRANSFERS": 0, "PARTIAL": 28, "UNTESTED": 20}})
    d = s["scoreBreakdown"]["regionalTransfer"]
    assert d["status"] == "SCORED" and d["value"] == 2.9 and s["scoreVersion"] == "biological-state-score-v1.1"
    full = _bio_with_transfer({"usableRules": 4, "byTransferability": {"TRANSFERS": 4, "PARTIAL": 0, "UNTESTED": 0}})
    assert full["scoreBreakdown"]["regionalTransfer"]["value"] == 10.0


def test_regional_transfer_malformed_is_unknown_never_guessed():
    for bad in ({"usableRules": 0, "byTransferability": {}}, {"usableRules": 4, "byTransferability": {"TRANSFERS": 9}},
                {"usableRules": "4", "byTransferability": {"TRANSFERS": 1}}, {"usableRules": 4, "byTransferability": {"TRANSFERS": -1}}, "x"):
        assert _bio_with_transfer(bad)["scoreBreakdown"]["regionalTransfer"]["status"] == "UNKNOWN", bad
