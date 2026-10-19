"""Brain Score Explanation V1: the explanation restates the published evaluation honestly and never moves a score.

Fixture = the production /scores blocks read on 2026-10-19 (Wind 3.3, Fish 5.1, Water Clarity 8.0 research candidate, ...)."""
import copy
import json
import os
import sys

import pytest

from sector_brain_platform import score_explanation as sx
from sector_brain_platform.publication import judge

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
from jsonschema_lite import validate  # noqa: E402

LIVE = {k: v for k, v in json.load(open(os.path.join(HERE, "score_explanation_live_2026-10-19.json"))).items() if not k.startswith("_")}
SCHEMA = json.load(open(os.path.join(ROOT, "contracts", "schemas", "brain-score-explanation.schema.json")))


def ex(bid, block=None, prev=None, **kw):
    return sx.explain(bid, copy.deepcopy(block if block is not None else LIVE[bid]), prev, **kw)


@pytest.mark.parametrize("bid", sorted(LIVE))
def test_every_live_explanation_validates_and_binds_to_its_block(bid):
    e = ex(bid)
    assert validate(e, SCHEMA) == []
    assert e["forScore"]["value"] == LIVE[bid]["value"] and e["forScore"]["scoreVersion"] == LIVE[bid]["scoreVersion"]
    assert e["evaluationId"] == sx.evaluation_id(LIVE[bid])
    blob = json.dumps(e)
    assert "gs://" not in blob and "/Users/" not in blob                            # private locations never pass through


def test_schema_rejects_a_foreign_or_broken_explanation():
    e = ex("wind")
    assert validate({**e, "contract": "v0"}, SCHEMA)
    assert validate({**e, "evaluationId": "abc"}, SCHEMA)
    bad = copy.deepcopy(e); bad["improvements"][0]["status"] = "DONE"
    assert validate(bad, SCHEMA)


def test_wind_contributions_reproduce_the_published_uncapped_score():
    e = ex("wind")
    assert e["rubric"]["formula"] == sx.LINEAR and len(e["components"]) == 10
    assert abs(sum(c["earned"] for c in e["components"]) - LIVE["wind"]["uncapped"]) < 0.05
    by = {c["id"]: c for c in e["components"]}
    assert by["Exposure (field)"]["possible"] == 2.0 and by["Exposure (field)"]["earned"] == 0.0
    assert by["Fetch method"]["headroom"] == 0.0


def test_wind_improvements_come_from_its_real_deficiencies():
    e = ex("wind")
    keys = [i["key"] for i in e["improvements"]]
    assert keys[:2] == ["dimension:Exposure (field)", "dimension:Surface (field)"]          # 2.0 points of headroom each
    assert "dimension:Fetch method" not in keys and "dimension:Coverage" not in keys        # full credit: nothing to improve
    speed = next(i for i in e["improvements"] if i["key"] == "dimension:Wind speed")
    assert speed["status"] == "BLOCKED" and any(b.get("gate") == "h2" for b in speed["blockers"])   # H2 holdout sealed
    cap6 = next(i for i in e["improvements"] if i["key"] == "gate:fieldValidation@6")
    assert cap6["impact"]["kind"] == "LIFTS_CAP" and cap6["impact"]["points"] == 0           # not binding below the cap
    assert all(i["priority"] in ("HIGH", "MEDIUM", "LOW") for i in e["improvements"])


def test_wind_path_to_7_is_arithmetic_not_a_promise():
    t = ex("wind")["target"]
    assert t["current"] == 3.3 and t["gap"] == 3.7 and t["reached"] is False
    pw = t["pathway"]
    assert pw["status"] == "ARITHMETIC_PATH_EXISTS" and pw["validated"] is False
    assert [c["cap"] for c in pw["capsToLift"]] == [6.0]                                  # 7.0 cap does not block reaching 7.0
    assert pw["requiredUncappedGain"] == 3.73 and "not yet fully validated" in pw["why"]


def test_fish_overall_explanation_keeps_unknown_unknown_and_names_the_cap():
    e = ex("biological-state")
    reg = next(c for c in e["components"] if c["id"] == "regionalTransfer")
    assert reg["status"] == "UNKNOWN" and "value" not in reg and reg["earned"] == 0.0
    imp = next(i for i in e["improvements"] if i["key"] == "dimension:regionalTransfer")
    assert imp["impact"]["kind"] == "UP_TO_UNCAPPED_IF_MEASURED"
    assert [c["gate"] for c in e["target"]["pathway"]["capsToLift"]] == ["speciesValidation"]
    assert e["target"]["gap"] == 1.9


def test_fish_research_gaps_are_linked_by_id_with_their_register_status():
    gaps = {"FISH-EVI-001": {"status": "OPEN", "title": "All assessed species are at RESEARCH"}}
    e = ex("biological-state", gaps=gaps)
    ev = next(i for i in e["improvements"] if i["key"] == "dimension:evidenceQuality")
    assert {"id": "FISH-EVI-001", "status": "OPEN", "title": "All assessed species are at RESEARCH"} in ev["researchGaps"]


def test_water_clarity_is_a_candidate_score_with_no_production_path():
    e = ex("water-clarity")
    assert e["scope"] == "CANDIDATE" and "components" not in e and e["rubric"]["formula"] == "UNKNOWN"
    assert e["target"]["pathway"]["status"] == "NOT_EVALUABLE"
    [imp] = e["improvements"]
    assert imp["key"] == "gate:deployment" and imp["status"] == "BLOCKED" and imp["priority"] == "UNRANKED" and "impact" not in imp


def test_breakdown_that_does_not_reproduce_the_score_gets_no_invented_contributions():
    b = copy.deepcopy(LIVE["biological-state"]); b["uncapped"] = 9.0
    e = ex("biological-state", b)
    assert e["rubric"]["formula"] == "UNVERIFIED"
    assert all("earned" not in c and "headroom" not in c for c in e["components"])
    assert all(i["priority"] == "UNRANKED" and "impact" not in i for i in e["improvements"] if i["key"].startswith("dimension:"))
    assert e["target"]["pathway"]["status"] == "NOT_EVALUABLE"


def test_target_reached_is_not_pushed_higher():
    b = copy.deepcopy(LIVE["sector-intelligence"])
    b.update(value=7.4, uncapped=7.4, scoreBlockers=[])
    for d in b["scoreBreakdown"].values():
        d.update(value=7.4, status="SCORED")
    t = ex("sector-intelligence", b)["target"]
    assert t["reached"] is True and t["gap"] == 0 and t["pathway"]["status"] == "REACHED"


def test_binding_cap_is_only_the_lowest_and_reports_its_displayed_gain():
    e = ex("lake-brain")                                                                  # 3.0 coverage cap, 5.0 validation cap, uncapped 6.3
    caps = {c["cap"]: c for c in e["caps"]}
    assert caps[3.0]["binding"] and not caps[5.0]["binding"] and caps[5.0]["belowUncapped"]
    cov = next(i for i in e["improvements"] if i["key"] == "gate:coverage@3")
    assert cov["impact"]["points"] == 2.0 and cov["priority"] == "HIGH" and cov["rank"] == 1


def test_change_record_resolves_improvements_and_reports_regressions_honestly():
    old = copy.deepcopy(LIVE["biological-state"])
    old["explanation"] = ex("biological-state", old)
    new = copy.deepcopy(old); new.pop("explanation")
    new["scoreBreakdown"]["biologicalStateValidation"].update(value=10.0)
    new["scoreBreakdown"]["knowledgeDepth"].update(value=3.5)                             # one up, one down
    new["uncapped"] = round(sum(d["value"] * d["weight"] for d in new["scoreBreakdown"].values() if d.get("value") is not None) / 100, 1)
    new["value"] = new["uncapped"]
    new["scoreBlockers"] = [b for b in new["scoreBlockers"] if b.get("dimension") != "biologicalStateValidation"]
    e = ex("biological-state", new, old)
    ch = e["change"]
    assert ch["previousEvaluationId"] == old["explanation"]["evaluationId"] != e["evaluationId"]
    assert ch["direction"] == "UP" and ch["delta"] == round(new["value"] - 5.1, 1)
    assert {"id": "biological-state/dimension:biologicalStateValidation", "title": "Validate per-lake Biological State"} in ch["resolved"]
    assert all(i["key"] != "dimension:biologicalStateValidation" for i in e["improvements"])     # resolved leaves the active list
    down = copy.deepcopy(old); down.pop("explanation"); down["value"] = 4.8
    assert ex("biological-state", down, old)["change"]["direction"] == "DOWN"


def test_unchanged_value_held_by_a_cap_says_so():
    old = copy.deepcopy(LIVE["lake-brain"]); old["explanation"] = ex("lake-brain", old)
    new = copy.deepcopy(old); new.pop("explanation")
    new["scoreBreakdown"]["floodDroughtContext"]["value"] = 6.0; new["uncapped"] = 6.5
    ch = ex("lake-brain", new, old)["change"]
    assert ch["direction"] == "UNCHANGED" and ch["why"].startswith("displayed value held at the coverage cap 3")


def test_evaluation_id_ignores_timestamps_and_the_explanation_itself():
    a = copy.deepcopy(LIVE["wind"])
    b = copy.deepcopy(a); b["scoreUpdatedAt"] = "2030-01-01T00:00:00Z"; b["explanation"] = {"x": 1}
    assert sx.evaluation_id(a) == sx.evaluation_id(b)
    c = copy.deepcopy(a); c["value"] = 3.4
    assert sx.evaluation_id(a) != sx.evaluation_id(c)


def test_is_current_detects_an_old_explanation_beside_a_new_score():
    b = copy.deepcopy(LIVE["wind"]); b["explanation"] = ex("wind", b)
    assert sx.is_current(b)
    b["value"] = 3.4
    assert not sx.is_current(b)


def test_an_explanation_never_makes_a_score_look_changed_to_the_guard():
    pub = copy.deepcopy(LIVE["water-clarity"]); pub["explanation"] = ex("water-clarity", pub)
    assert judge(copy.deepcopy(LIVE["water-clarity"]), pub)["verdict"] == "SAME"           # frozen block re-emitted each run: no CONFLICT


def test_private_locations_in_published_text_never_pass_through():
    b = copy.deepcopy(LIVE["water-clarity"])
    b["scoreRubric"] = "bars (private detail: " + "gs:" + "//bucket/archive/x)"
    b["scoreBlockers"][0]["why"] = "see /Users/someone/notes.md"
    e = ex("water-clarity", b)
    assert e["rubric"]["refVisibility"] == "PARTLY_PRIVATE" and e["rubric"]["ref"] == "bars (private detail: [private record])"
    assert "/Users/" not in json.dumps(e) and "gs:" + "//" not in json.dumps(e)
