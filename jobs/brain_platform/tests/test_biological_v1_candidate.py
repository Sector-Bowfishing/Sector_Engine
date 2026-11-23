"""Candidate fixes B and D for biological-state-score-v1 (inactive). v1 itself must be unchanged."""
import datetime as dt

from sector_brain_platform import scoring
from sector_brain_platform.biological_v1_candidate import score_biological_v1_2_candidate as cand

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)


def facts(n=27, validated=0, contr=None):
    sp = {}
    for i in range(n):
        sp[f"s{i}"] = {"assessment": "ASSESSED", "researchMaturity": "VALIDATED" if i < validated else "RESEARCH",
                       "knowledge": {"overallRounded": 4.0}, **({"contradictionCount": contr[i]} if contr and contr[i] is not None else {})}
    reg = {"responsibilities": {"speciesKnowledge": {"speciesCount": n, "assessedCount": n, "notAssessedCount": 0},
                                "biologicalState": {"status": "IN_PROGRESS"}}}
    return {"registry": reg, "species": sp, "validation": {}, "intelligenceRegistry": {"dependencies": {"biological-state": {"connectionStatus": "CONNECTED"}}}}


def test_first_validated_species_lowers_v1_but_not_the_candidate():
    b0, b1 = scoring.score_biological(facts(), NOW), scoring.score_biological(facts(validated=1), NOW)
    assert b1["uncapped"] < b0["uncapped"]                                    # the documented v1 defect B, still present in v1
    c0, c1 = cand(facts(), NOW), cand(facts(validated=1), NOW)
    assert c1["uncapped"] >= c0["uncapped"]
    z = [0] * 27                                                              # counts recorded: fix D changes nothing, so all-RESEARCH equals v1
    assert cand(facts(contr=z), NOW)["uncapped"] == scoring.score_biological(facts(contr=z), NOW)["uncapped"]
    assert c1["candidate"]["status"] == "CANDIDATE_INACTIVE"


def test_null_contradiction_counts_are_unknown_not_zero():
    f = facts(contr=[None] * 27)
    assert scoring.score_biological(f, NOW)["scoreBreakdown"]["contradictionsGaps"]["value"] == 10.0      # v1: no data looks perfect
    assert cand(f, NOW)["scoreBreakdown"]["contradictionsGaps"]["status"] == "UNKNOWN"
    g = cand(facts(contr=[5] + [None] * 26), NOW)["scoreBreakdown"]["contradictionsGaps"]
    assert g["value"] == 0.0                                                  # only species that record a count are averaged


def test_v1_is_not_modified():
    assert "biological_v1_candidate" not in open(scoring.__file__).read()
