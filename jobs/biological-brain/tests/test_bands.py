"""Biological response-band contract (biological-response-bands-v1): synthetic fixtures only."""
import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import bands                       # noqa: E402
import features as ft              # noqa: E402
import rules as rl                 # noqa: E402
from test_rules_state_validation import ev, fixture_ruleset, rule    # noqa: E402

GEN = "2026-10-14T00:00:00Z"


def compile_(rules, sid="example_fish"):
    return bands.compile_species_bands(sid, rules, generated_at=GEN, rules_version="t.1")


class BandContractTests(unittest.TestCase):
    def test_compiles_valid_object_with_every_required_field(self):
        rb = compile_(fixture_ruleset().rules)
        self.assertEqual(bands.validate_response_bands(rb), [])
        b = next(x for x in rb["bands"] if x["featureId"] == "warmRise")
        for k in ("bandId", "featureId", "featureStates", "behavior", "band", "context", "confidence", "confidenceBasis", "evidenceKind", "ruleVersion",
                  "transferability", "sourceCount", "validationTier", "reason", "limitations"):
            self.assertIn(k, b, k)
        self.assertEqual((b["band"], b["confidence"], b["sourceCount"], b["evidenceKind"], b["validationTier"]), ("FAVORABLE", "LOW", 1, "DIRECT", "T1"))
        self.assertEqual(b["context"]["regions"], ["south"])
        self.assertEqual(b["context"]["months"], [3, 4, 5])
        self.assertEqual(b["ruleVersion"]["versions"], {"EX-FLW-01": 1})
        self.assertEqual(rb["spawn"][0]["tempC"], {"min": 17.0, "max": 24.0})
        self.assertIn("a range", rb["spawn"][0]["reason"])

    def test_status_is_proposed_until_every_rule_is_approved_and_never_validated(self):
        rb = compile_(fixture_ruleset().rules)
        self.assertEqual((rb["status"], rb["evidenceTier"]), ("PROPOSED", "RESEARCH"))
        approved = [dict(r, status="APPROVED", review={"reviewer": "r", "date": "2026-10-14"}) for r in fixture_ruleset().rules if r["speciesId"] == "example_fish"]
        rb2 = compile_(approved)
        self.assertEqual((rb2["status"], rb2["evidenceTier"]), ("APPROVED", "REVIEWED"))
        self.assertEqual(bands.validate_response_bands(rb2), [])
        rb2["evidenceTier"] = "VALIDATED"
        self.assertTrue(any("VALIDATED" in m for m in bands.validate_response_bands(rb2)))
        rb2["evidenceTier"] = "RESEARCH"
        self.assertTrue(bands.validate_response_bands(rb2))             # APPROVED with RESEARCH tier is inconsistent
        part = [approved[0]] + [dict(r) for r in fixture_ruleset().rules if r["speciesId"] == "example_fish"][1:]
        self.assertEqual(compile_(part)["status"], "PROPOSED")           # one unapproved rule keeps the whole object PROPOSED

    def test_draft_rules_never_enter_a_band_and_a_species_without_usable_rules_has_no_object(self):
        self.assertIsNone(compile_(fixture_ruleset().rules, "draft_fish"))
        self.assertIsNone(compile_(fixture_ruleset().rules, "unknown_fish"))
        mixed = [rule("EX-FLW-01"), rule("EX-FLW-02", status="DRAFT", evidence=[ev(1, "s", counts=False, read="SNIPPET-ONLY")],
                                         feature={"featureId": "coldRise", "states": ["TRUE"]})]
        rb = compile_(mixed)
        self.assertEqual([b["bandId"] for b in rb["bands"]], ["EX-FLW-01"])
        self.assertNotIn("coldRise", rb["coveredFeatures"])

    def test_overlapping_disagreeing_rules_resolve_to_one_unknown_conflict_band(self):
        rb = compile_([rule("EX-FLW-01", response="FAVORABLE"), rule("EX-FLW-02", response="LIMITING")])
        self.assertEqual(len(rb["bands"]), 1)
        b = rb["bands"][0]
        self.assertEqual((b["band"], b["conflict"], b["confidence"]), ("UNKNOWN", True, None))
        self.assertEqual(b["conflictsWith"], ["EX-FLW-01", "EX-FLW-02"])
        self.assertEqual(bands.validate_response_bands(rb), [])

    def test_non_overlapping_contexts_do_not_conflict(self):
        spring = rule("EX-FLW-01", response="FAVORABLE", applicability={"months": [3, 4], "regions": ["south"]})
        autumn = rule("EX-FLW-02", response="LIMITING", applicability={"months": [10, 11], "regions": ["south"]})
        north = rule("EX-FLW-03", response="LIMITING", applicability={"months": [3, 4], "regions": ["north"]})
        rb = compile_([spring, autumn, north])
        self.assertEqual(sorted(b["band"] for b in rb["bands"]), ["FAVORABLE", "LIMITING", "LIMITING"])
        self.assertFalse(any(b["conflict"] for b in rb["bands"]))
        self.assertTrue(any(b["conflict"] for b in compile_([rule("EX-FLW-01", response="FAVORABLE", applicability={"regions": ["any"]}),
                                                           rule("EX-FLW-02", response="LIMITING", applicability={"months": [3], "regions": ["south"]})])["bands"]))

    def test_confidence_cannot_exceed_the_evidence_cap_and_a_band_needs_counting_evidence(self):
        rb = compile_([rule("EX-FLW-01")])
        rb["bands"][0]["confidence"] = "HIGH"
        self.assertTrue(any("exceeds the cap" in m for m in bands.validate_response_bands(rb)))
        rb = compile_([rule("EX-FLW-01")])
        rb["bands"][0]["sourceCount"] = 0
        self.assertTrue(any("sourceCount" in m for m in bands.validate_response_bands(rb)))

    def test_malformed_bands_are_rejected(self):
        base = compile_([rule("EX-FLW-01")])
        for mutate in (lambda r: r["bands"][0].__setitem__("band", "GREAT"), lambda r: r["bands"][0].__setitem__("featureId", "backwaterHabitat"),
                       lambda r: r["bands"][0].__setitem__("featureStates", ["MAYBE"]), lambda r: r["bands"][0].__setitem__("transferability", "YES"),
                       lambda r: r["bands"][0].__setitem__("validationTier", "T9"), lambda r: r["bands"][0].__setitem__("evidenceKind", "SURE"),
                       lambda r: r.__setitem__("contractVersion", "v0"), lambda r: r.__setitem__("bands", []) or r.__setitem__("habitatPreferences", []) or r.__setitem__("spawn", []),
                       lambda r: r["bands"][0].__setitem__("band", "UNKNOWN")):
            rb = copy.deepcopy(base)
            mutate(rb)
            self.assertTrue(bands.validate_response_bands(rb), mutate)

    def test_no_free_text_rule_statement_or_evidence_is_carried(self):
        r = rule("EX-FLW-01", statement="SECRET species knowledge sentence", conflicts=["private conflict text"])
        blob = repr(compile_([r]))
        self.assertNotIn("SECRET", blob)
        self.assertNotIn("private conflict text", blob)
        self.assertNotIn("synthetic", blob)                  # evidence packet name
        self.assertIn("documented conflicting evidence", blob)

    def test_stage_proxy_and_unpublished_input_limitations_are_stated(self):
        rb = compile_([rule("EX-FLW-01", feature={"featureId": "risingStage", "states": ["TRUE"]}),
                       rule("EX-FLW-02", feature={"featureId": "rapidDischargeIncrease", "states": ["TRUE"]})])
        lim = {b["featureId"]: b["limitations"] for b in rb["bands"]}
        self.assertIn("lake pool trend is a proxy for river/tributary stage", lim["risingStage"])
        self.assertIn("input not yet published by any Brain", lim["rapidDischargeIncrease"])

    def test_unsupported_feature_is_unknown_by_absence_at_runtime(self):
        rs = fixture_ruleset()
        ctx = {"month": 4, "region": "south", "waterbodyType": "run_of_river"}
        out = rl.evaluate_responses(rs.for_species("example_fish"), ft.evaluate_features({}), ctx)
        covered = {b["featureId"] for b in compile_(rs.rules)["bands"]}
        self.assertEqual({o["featureId"] for o in out} - {"daypart"}, covered - {"daypart"})      # compile and runtime cover the same features


class EvaluatedBandTests(unittest.TestCase):
    ctx = {"month": 4, "region": "south", "waterbodyType": "run_of_river"}

    def test_every_band_in_a_real_state_output_validates(self):
        from test_rules_state_validation import BiologicalStateTests
        s = BiologicalStateTests().build()
        n = 0
        for sp in s["species"]:
            for r in sp.get("responses", []):
                n += 1
                self.assertEqual(bands.validate_evaluated_band(r), [], r)
        self.assertGreater(n, 0)

    def test_unknown_conflict_and_missing_provenance_forms(self):
        rs = fixture_ruleset()
        unk = rl.evaluate_responses(rs.for_species("example_fish"), ft.evaluate_features({}), self.ctx)
        for r in unk:
            self.assertEqual(bands.validate_evaluated_band(r), [])
        conflict = rl.evaluate_responses([rule("EX-FLW-01", response="FAVORABLE"), rule("EX-FLW-02", response="LIMITING")], ft.evaluate_features({"waterTemp": {"status": "PUBLISHED", "values": {"currentTempF": 70.0}}, "lake": {"status": "PUBLISHED", "values": {"trendState": "RISING"}}}), self.ctx)
        self.assertEqual(conflict[0]["response"], "UNKNOWN")
        self.assertEqual(bands.validate_evaluated_band(conflict[0]), [])
        good = rl.evaluate_responses([rule("EX-FLW-01")], ft.evaluate_features({"waterTemp": {"status": "PUBLISHED", "values": {"currentTempF": 70.0}}, "lake": {"status": "PUBLISHED", "values": {"trendState": "RISING"}}}), self.ctx)[0]
        for mutate in (lambda b: b.pop("transferability"), lambda b: b.__setitem__("confidence", "HIGH"), lambda b: b["evidenceBasis"].__setitem__("independentStreams", 0),
                       lambda b: b.__setitem__("response", "GREAT"), lambda b: b.__setitem__("featureState", "MAYBE"), lambda b: b["regionApplicability"].__setitem__("applies", False)):
            import copy
            bb = copy.deepcopy(good)
            mutate(bb)
            self.assertTrue(bands.validate_evaluated_band(bb), mutate)


if __name__ == "__main__":
    unittest.main()
