import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import evaluated_view as ev      # noqa: E402
import movement_outlook as mo      # noqa: E402
import target_readiness as tr      # noqa: E402
import target_set as ts      # noqa: E402
from test_rules_state_validation import BiologicalStateTests, fixture_ruleset, inputs      # noqa: E402


def resp(f, st, band, conf="MEDIUM"):
    return {"featureId": f, "featureState": st, "response": band, "confidence": None if band == "UNKNOWN" else conf, "evidenceBasis": {"ruleIds": ["X-1"]}}


def sp(responses=(), habitat=(), evaluated=True, window=None):
    return {"speciesId": "common_carp", "evaluated": evaluated, "responses": list(responses), "habitat": list(habitat),
            "spawnWindow": {"state": window} if window else {}, **({} if evaluated else {"notEvaluatedReason": "presence outside policy"})}


def hab(c, d="FAVOR", state="ACTIVE", conf="LOW"):
    return {"habitatClass": c, "direction": d, "state": state, "confidence": conf}


class Outlook(unittest.TestCase):
    def test_unevaluated_and_all_unknown_are_unknown_never_favorable(self):
        self.assertEqual(mo.species_outlook(sp(evaluated=False))["state"], "UNKNOWN")
        o = mo.species_outlook(sp([resp("risingStage", "TRUE", "UNKNOWN")]))
        self.assertEqual((o["state"], o["movement"], o["confidence"]), ("UNKNOWN", "UNKNOWN", None))

    def test_favorable_rise_with_templated_reason_and_no_internals(self):
        o = mo.species_outlook(sp([resp("risingStage", "TRUE", "FAVORABLE"), resp("waterTempBand", "C15_18", "FAVORABLE", "HIGH")], [hab("floodedVegetation", conf="MEDIUM")], window="IN_WINDOW"))
        self.assertEqual((o["state"], o["movement"]), ("FAVORABLE_SHALLOW", "MORE_LIKELY_SHALLOW"))
        self.assertIn("the lake level is rising", o["why"])
        self.assertIn("newly flooded vegetation and margins", o["where"])
        self.assertEqual(o["confidence"], "MEDIUM")                      # the weakest contributing confidence
        self.assertNotIn("ruleIds", str(o))
        self.assertEqual(o["claim"], {"level": 3})

    def test_limiting_mixed_and_workable(self):
        self.assertEqual(mo.species_outlook(sp([resp("waterTempBand", "LT_10C", "LIMITING")]))["state"], "LIMITING")
        self.assertEqual(mo.species_outlook(sp([resp("waterTempBand", "LT_10C", "LIMITING"), resp("risingStage", "TRUE", "FAVORABLE")]))["state"], "MIXED")
        w = mo.species_outlook(sp([resp("daypart", "NIGHT", "WORKABLE")]))
        self.assertEqual((w["state"], w["activity"]), ("WORKABLE", "ACTIVITY_UP"))

    def test_habitat_only_moves_to_habitat_and_conflict_is_ignored(self):
        o = mo.species_outlook(sp(habitat=[hab("backwaterHabitat")]))
        self.assertEqual((o["state"], o["movement"]), ("WORKABLE", "MOVES_TO_HABITAT"))
        c = mo.species_outlook(sp(habitat=[{**hab("backwaterHabitat"), "conflict": True}]))
        self.assertEqual(c["state"], "UNKNOWN")

    def test_cold_limits_the_activity_signal_not_the_shallow_signal_wrongly(self):
        o = mo.species_outlook(sp([resp("daypart", "DAY", "LIMITING")]))
        self.assertEqual((o["activity"], o["movement"]), ("ACTIVITY_DOWN", "UNKNOWN"))

    def test_lake_outlook_orders_targets_first_and_flags_knowledge_only(self):
        b = BiologicalStateTests("test_state_shape_and_pilot_internal_status")
        st = b.build()
        roles = {s["speciesId"]: ("TARGET" if s["speciesId"] == "example_fish" else "KNOWLEDGE_ONLY") for s in st["species"]}
        lo = mo.lake_outlook(st, roles)
        self.assertEqual(lo["species"][0]["role"], "TARGET")
        self.assertEqual(lo["claim"], {"level": 3, "maturity": "NOT_VALIDATED"})
        self.assertFalse(lo["consumable"])


class TargetSet(unittest.TestCase):
    def test_partition_is_exact_and_disjoint(self):
        self.assertEqual(ts.check_disjoint(), [])
        ids = ["common_carp", "bighead_carp", "paddlefish", "alligator_gar", "unknown_fish"]
        p = ts.partition(ids)
        self.assertEqual((p["TARGET"], p["SECONDARY"]), (["common_carp"], ["bighead_carp"]))
        self.assertEqual(sorted(p["KNOWLEDGE_ONLY"]), ["alligator_gar", "paddlefish", "unknown_fish"])
        self.assertEqual(sum(len(v) for v in p.values()), len(ids))

    def test_protected_and_non_target_fish_never_drive_readiness(self):
        for s in ("paddlefish", "american_shad", "channel_catfish", "alligator_gar", "black_buffalo"):
            self.assertEqual(ts.role(s), "KNOWLEDGE_ONLY", s)
        self.assertEqual(sorted(ts.TARGET), ["bigmouth_buffalo", "bowfin", "common_carp", "grass_carp", "longnose_gar", "silver_carp", "smallmouth_buffalo", "spotted_gar"])


class Readiness(unittest.TestCase):
    def test_raw_counts_for_targets_only_and_a_missing_target_is_zero(self):
        r = tr.build(fixture_ruleset(), ["example_fish", "no_rules_fish"])
        self.assertEqual(r["targets"], ["example_fish", "no_rules_fish"])
        self.assertGreater(r["perSpecies"]["example_fish"]["usableRules"], 0)
        self.assertEqual(r["perSpecies"]["no_rules_fish"]["usableRules"], 0)
        self.assertEqual(r["perSpecies"]["no_rules_fish"]["conditionFamilies"], 0)
        self.assertEqual(r["perSpecies"]["example_fish"]["approvedRules"], 0)           # nothing is reviewed

    def test_deterministic(self):
        self.assertEqual(tr.build(fixture_ruleset(), ["example_fish"]), tr.build(fixture_ruleset(), ["example_fish"]))


class ViewV2(unittest.TestCase):
    def test_intelligence_view_carries_outlook_freshness_and_validation_without_internals(self):
        b = BiologicalStateTests("test_state_shape_and_pilot_internal_status")
        v = ev.intelligence_view(b.build())
        self.assertEqual(ev.validate_view(v), [])
        self.assertEqual(v["viewVersion"], "biological-evaluated-view-v2")
        self.assertEqual(v["validation"], {"status": "NOT_VALIDATED"})
        self.assertIn("freshness", v)
        for s in v["species"]:
            self.assertIn("movementOutlook", s)
            self.assertNotIn("ruleIds", str(s))
        v["species"][0]["movementOutlook"]["state"] = "MAYBE"
        self.assertTrue(ev.validate_view(v))

    def test_unevaluated_species_outlook_must_be_unknown(self):
        b = BiologicalStateTests("test_state_shape_and_pilot_internal_status")
        v = ev.intelligence_view(b.build())
        bad = next(s for s in v["species"] if s["status"] == "NOT_EVALUATED")
        bad["movementOutlook"]["state"] = "FAVORABLE_SHALLOW"
        self.assertTrue(ev.validate_view(v))


if __name__ == "__main__":
    unittest.main()
