import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import rules as rl      # noqa: E402
from test_rules_state_validation import NOW, inputs, rule      # noqa: E402
import bio_state as bs      # noqa: E402


def state_with(rules, assertions, now=NOW):
    rs = rl.RuleSet(rules, "t.1", season_assertions=assertions)
    return bs.build_lake_state("Example|ST", region="south", waterbody_type="run_of_river", now=now, inputs=inputs(temp_f=64.4, lake_trend="RISING"), daypart="DAY",
                               presence={"example_fish": {"presenceState": "established"}}, ruleset=rs,
                               species_info={"example_fish": {"researchMaturity": "RESEARCH", "knowledgeScore": 3.5, "assessment": "ASSESSED"}})


class SeasonalSafety(unittest.TestCase):
    def rise(self, months=None, rid="EX-FLW-01"):
        r = rule(rid, feature={"featureId": "risingStage", "states": ["TRUE"]}, response="FAVORABLE", applicability={"regions": ["any"], **({"months": months} if months else {})})
        return r

    def test_unbounded_rule_without_an_assertion_does_not_fire_and_says_so(self):
        st = state_with([self.rise()], {})
        ex = st["species"][0]
        self.assertEqual([r for r in ex["responses"] if r["response"] != "UNKNOWN"], [])
        self.assertEqual(ex["knowledge"]["rules"]["seasonGated"], 1)
        self.assertTrue(any("no season established" in u for u in ex["unknowns"]))

    def test_year_round_assertion_lets_it_fire_and_needs_review_does_not(self):
        fired = [r for r in state_with([self.rise()], {"EX-FLW-01": "YEAR_ROUND"})["species"][0]["responses"] if r["response"] != "UNKNOWN"]
        self.assertEqual(fired[0]["response"], "FAVORABLE")
        self.assertEqual([r for r in state_with([self.rise()], {"EX-FLW-01": "NEEDS_REVIEW"})["species"][0]["responses"] if r["response"] != "UNKNOWN"], [])
        with self.assertRaises(rl.RuleError):
            rl.RuleSet([self.rise()], "t", season_assertions={"EX-FLW-01": "SOMETIMES"})

    def test_spring_rule_does_not_fire_in_october_even_when_temperature_and_rise_match(self):
        import datetime as dt
        spring = self.rise([3, 4, 5, 6, 7])
        apr = state_with([spring], {}, dt.datetime(2026, 4, 20, 3, tzinfo=dt.timezone.utc))["species"][0]
        octo = state_with([spring], {}, dt.datetime(2026, 10, 20, 3, tzinfo=dt.timezone.utc))["species"][0]
        self.assertTrue([r for r in apr["responses"] if r["response"] == "FAVORABLE"])
        self.assertEqual([r for r in octo["responses"] if r["response"] == "FAVORABLE"], [])

    def test_spawn_windows_are_always_seasonal_and_never_gated(self):
        spn = rule("EX-SPN-01", kind="PHENOLOGY", applicability={"months": [4, 5], "regions": ["any"]}, phenology={"event": "spawn", "tempC": {"min": 15.0, "max": 24.0}})
        del spn["feature"], spn["response"]
        self.assertTrue(rl.RuleSet([spn], "t").season_ok(spn))


if __name__ == "__main__":
    unittest.main()
