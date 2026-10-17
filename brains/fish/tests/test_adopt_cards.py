import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import adopt_cards as ac      # noqa: E402
import rules as rl      # noqa: E402
from test_movement_cards import sp as card_fixture      # noqa: E402


def card(types=("AGENCY", "PEER_REVIEWED")):
    c = card_fixture()
    c["speciesId"] = "example_fish"
    c["sources"] = [{"id": f"S{i + 1}", "type": t, "url": f"https://site{i}.example.gov/x", "title": f"T{i}", "supports": ["spawn", "temperature", "seasonal"]} for i, t in enumerate(types)]
    return c


def cand(ids=("S1", "S2"), conf="MEDIUM", reg="MEDIUM"):
    return {"id": "EX-C01", "when": ["spring"], "then": "Fish move shallow.", "direction": "MORE_LIKELY_SHALLOW", "kind": "RESPONSE", "featureHints": [], "confidence": conf,
            "regionalConfidence": reg, "sourceIds": list(ids)}


SPEC_R = {"kind": "R", "f": "risingStage", "st": ["TRUE"], "resp": "FAVORABLE", "months": [3, 4, 5], "beh": "RUN", "stmt": "Rising stage moves fish."}
READ = {"example_fish:S1": "READ-FULL", "example_fish:S2": "READ-ABSTRACT"}


class Ranges(unittest.TestCase):
    def test_f_range_becomes_band_states_never_a_point(self):
        lo, hi = ac.parse_temp_range("water temperature about 60-72 F")
        self.assertEqual((lo, hi), (15.6, 22.2))
        self.assertEqual(ac.temp_states(lo, hi), ["C15_18", "C18_21"])      # 1.2 C of C21_26 is a sliver, not a band

    def test_open_ended_ranges(self):
        self.assertEqual(ac.parse_temp_range("water below about 50 F"), (None, 10.0))
        self.assertEqual(ac.temp_states(None, 10.0), ["LT_10C"])
        self.assertEqual(ac.parse_temp_range("water above ~75 F")[1], None)
        self.assertEqual(ac.temp_states(23.9, None), ["C21_26", "C26_30", "GE_30C"])

    def test_celsius_and_unparsable_and_no_false_precision(self):
        self.assertEqual(ac.parse_temp_range("12-19 C"), (12.0, 19.0))
        self.assertIsNone(ac.parse_temp_range("spring"))
        self.assertTrue(all(isinstance(s, str) for s in ac.temp_states(15.6, 22.2)))      # states, not decimals
        self.assertEqual(ac.temp_states(14.9, 15.2), [])                                  # a sliver of a band is not a band


class Rules(unittest.TestCase):
    def test_provenance_and_status_follow_verification(self):
        r = ac.build_rule(SPEC_R, cand(), card(), READ, "EX-MV-01")
        self.assertEqual((r["status"], r["confidence"]), ("RECONCILED", "MEDIUM"))
        self.assertEqual(r["provenance"]["candidateId"], "EX-C01")
        self.assertEqual([e["sourceNo"] for e in r["evidence"]], ["S1", "S2"])
        self.assertEqual(rl.validate_rule(r), [])

    def test_unread_sources_never_count_and_leave_a_draft(self):
        r = ac.build_rule(SPEC_R, cand(), card(), {}, "EX-MV-01")
        self.assertEqual(r["status"], "DRAFT")
        self.assertTrue(all(not e["counts"] for e in r["evidence"]))
        r2 = ac.build_rule(SPEC_R, cand(), card(), {"example_fish:S1": "NOT_SUPPORTED", "example_fish:S2": "UNREACHABLE"}, "EX-MV-01")
        self.assertEqual(r2["status"], "DRAFT")

    def test_confidence_is_capped_by_independent_streams(self):
        one = ac.build_rule(SPEC_R, cand(("S1",), "HIGH"), card(), READ, "EX-MV-01")
        self.assertEqual(one["confidence"], "LOW")
        c = card(("AGENCY", "AGENCY"))
        c["sources"][1]["url"] = c["sources"][0]["url"]                      # same publisher domain = one stream
        same = ac.build_rule(SPEC_R, cand(("S1", "S2"), "HIGH"), c, READ, "EX-MV-01")
        self.assertEqual(same["confidence"], "LOW")

    def test_anecdotal_sources_never_count(self):
        r = ac.build_rule(SPEC_R, cand(("S1", "S2")), card(("ANECDOTAL", "AGENCY")), READ, "EX-MV-01")
        self.assertEqual([e["counts"] for e in r["evidence"]], [False, True])

    def test_general_vs_regional_confidence_are_separate(self):
        r = ac.build_rule(SPEC_R, cand(reg="LOW"), card(), READ, "EX-MV-01")
        self.assertEqual(r["transferability"]["southeastReservoir"], "UNTESTED")
        self.assertEqual(r["provenance"]["generalConfidence"], "MEDIUM")
        self.assertEqual(ac.build_rule(SPEC_R, cand(reg="MEDIUM"), card(), READ, "EX-MV-01")["transferability"]["southeastReservoir"], "PARTIAL")

    def test_all_three_kinds_and_bad_specs(self):
        h = ac.build_rule({"kind": "H", "cls": "floodedVegetation", "dir": "FAVOR", "req": [("risingStage", ["TRUE"])], "months": [4], "stmt": "x"}, cand(), card(), READ, "EX-MV-02")
        self.assertEqual(h["requires"], [{"featureId": "risingStage", "states": ["TRUE"]}])
        p = ac.build_rule({"kind": "P", "c": (15.6, 22.2), "months": [4, 5], "stmt": "x"}, cand(), card(), READ, "EX-MV-03")
        self.assertEqual(p["phenology"]["tempC"], {"min": 15.6, "max": 22.2})
        with self.assertRaises(ValueError):
            ac.build_rule({"kind": "P", "c": (20.0, 20.0), "months": [4], "stmt": "x"}, cand(), card(), READ, "EX-MV-04")      # a point is not a range
        with self.assertRaises(ValueError):
            ac.build_rule({**SPEC_R, "f": "notAFeature"}, cand(), card(), READ, "EX-MV-05")

    def test_deduplication(self):
        a = ac.build_rule(SPEC_R, cand(), card(), READ, "EX-MV-01")
        b = ac.build_rule(SPEC_R, cand(), card(), READ, "EX-MV-02")
        self.assertEqual(ac.dedupe_key(a), ac.dedupe_key(b))
        self.assertEqual(ac.find_duplicate(b, [a])["ruleId"], "EX-MV-01")
        other = ac.build_rule({**SPEC_R, "resp": "LIMITING"}, cand(), card(), READ, "EX-MV-03")
        self.assertIsNone(ac.find_duplicate(other, [a]))


class Dispositions(unittest.TestCase):
    def test_every_candidate_needs_exactly_one_valid_disposition(self):
        cands = [{"id": "A"}, {"id": "B"}]
        ok = {"A": {"disposition": "REJECT_WEAK_EVIDENCE", "why": "x"}, "B": {"disposition": "ACCEPT_AS_DRAFT_RULE", "why": "x", "spec": SPEC_R}}
        self.assertEqual(ac.validate_dispositions(cands, ok), [])
        self.assertTrue(ac.validate_dispositions(cands, {"A": ok["A"]}))
        self.assertTrue(ac.validate_dispositions(cands, {**ok, "B": {"disposition": "ACCEPT_AS_DRAFT_RULE", "why": "x"}}))
        self.assertTrue(ac.validate_dispositions(cands, {**ok, "C": ok["A"]}))
        self.assertTrue(ac.validate_dispositions(cands, {**ok, "A": {"disposition": "MAYBE", "why": "x"}}))


class Domains(unittest.TestCase):
    def test_source_caps_and_unknown_handling(self):
        c = card(("AGENCY", "PEER_REVIEWED", "ANECDOTAL"))
        none = ac.domain_scores(c, {})
        self.assertEqual(none["seasonalLocationReproduction"]["score"], 0)                 # nothing inspected earns nothing
        self.assertGreater(none["seasonalLocationReproduction"]["unverifiedSources"], 0)
        one = ac.domain_scores(c, {"example_fish:S1": "READ-FULL"})
        self.assertLessEqual(one["seasonalLocationReproduction"]["score"], 6)
        two = ac.domain_scores(c, READ)
        self.assertGreater(two["seasonalLocationReproduction"]["score"], 6)
        self.assertLessEqual(two["seasonalLocationReproduction"]["score"], 8)
        self.assertEqual(two["seasonalLocationReproduction"]["anecdotalIgnored"], 1)

    def test_partially_supported_source_counts_only_for_the_topics_its_note_affirms(self):
        c = card(("AGENCY",))
        c["sources"][0]["supports"] = ["spawn", "temperature"]
        v = {"example_fish:S1": "NOT_SUPPORTED"}
        self.assertEqual(ac.domain_scores(c, v)["seasonalLocationReproduction"]["score"], 0)
        d = ac.domain_scores(c, v, None, {"example_fish:S1": ["spawn"]})
        self.assertGreater(d["seasonalLocationReproduction"]["score"], 0)      # the spawn topic is affirmed
        self.assertEqual(d["temperatureOxygen"]["score"], 0)                    # the temperature topic is not
        self.assertEqual(d["seasonalLocationReproduction"]["independentInspectedStreams"], 1)

    def test_never_lowers_an_existing_score_and_food_is_kept(self):
        existing = {"seasonalLocationReproduction": {"score": 9}, "foodFeedingLocation": {"score": 4}}
        d = ac.domain_scores(card(), READ, existing)
        self.assertEqual(d["seasonalLocationReproduction"]["score"], 9)
        self.assertTrue(d["seasonalLocationReproduction"]["keptExisting"])
        self.assertEqual(d["foodFeedingLocation"]["score"], 4)

    def test_regional_confidence_does_not_change_a_general_domain_score(self):
        a, b = card(), card()
        b["card"]["regionalConfidence"] = "HIGH"
        self.assertEqual(ac.domain_scores(a, READ), ac.domain_scores(b, READ))


if __name__ == "__main__":
    unittest.main()
