"""No presence record from the Lake Brain means UNKNOWN, never absent (Sector_Ops #22 roadmap item 4)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import rules as rl      # noqa: E402
from test_rules_state_validation import NOW, inputs      # noqa: E402
import bio_state as bs      # noqa: E402


def _state(presence, roster):
    rs = rl.RuleSet([], "t.1")
    return rs, bs.build_lake_state("Example|ST", region="south", waterbody_type="run_of_river", now=NOW, inputs=inputs(temp_f=64.4, lake_trend="RISING"),
                                   daypart="NIGHT", presence=presence, ruleset=rs, species_info={}, roster=roster)


def test_roster_species_without_a_record_is_listed_unknown_not_dropped():
    rs, st = _state({"common_carp": {"presenceState": "established"}}, ["common_carp", "bigmouth_buffalo"])
    by = {s["speciesId"]: s for s in st["species"]}
    assert by["bigmouth_buffalo"]["presence"]["presenceState"] == bs.PRESENCE_UNKNOWN
    assert by["bigmouth_buffalo"]["evaluated"] is False and "UNKNOWN (not absent)" in by["bigmouth_buffalo"]["notEvaluatedReason"]
    assert st["summary"]["speciesPresent"] == 1 and st["summary"]["speciesPresenceUnknown"] == 1
    assert [s["speciesId"] for s in st["species"]] == sorted(by)


def test_no_presence_at_all_means_every_roster_species_is_unknown():
    _, st = _state({}, ["common_carp", "bigmouth_buffalo"])
    assert {s["presence"]["presenceState"] for s in st["species"]} == {bs.PRESENCE_UNKNOWN}
    assert st["summary"]["speciesPresent"] == 0 and st["summary"]["speciesEvaluated"] == 0


def test_without_a_roster_the_output_is_unchanged():
    _, st = _state({"common_carp": {"presenceState": "established"}}, None)
    assert [s["speciesId"] for s in st["species"]] == ["common_carp"] and st["summary"]["speciesPresenceUnknown"] == 0
