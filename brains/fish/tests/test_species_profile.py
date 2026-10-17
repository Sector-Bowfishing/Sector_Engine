import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import movement_outlook as mo      # noqa: E402
import profile_bundle as pb      # noqa: E402
import rules as rl      # noqa: E402
import species_profile as sp      # noqa: E402
import target_set as ts      # noqa: E402
from test_movement_cards import sp as card_body      # noqa: E402
from test_rules_state_validation import ev, rule      # noqa: E402

GEN = {"researchVersion": "t.1", "rulesVersion": "t.1-rules", "featuresVersion": "biological-features-v1"}


def mk_rules(sid="example_fish"):
    spn = rule("EX-SPN-01", sid=sid, kind="PHENOLOGY", applicability={"months": [4, 5, 6], "regions": ["any"]}, phenology={"event": "spawn", "tempC": {"min": 15.0, "max": 24.0}})
    del spn["feature"], spn["response"]
    hab = rule("EX-HAB-01", sid=sid, kind="HABITAT", habitat={"habitatClass": "shallowVegetatedHabitat", "direction": "FAVOR"}, applicability={"months": [4, 5, 6], "regions": ["any"]})
    del hab["feature"], hab["response"]
    rise = rule("EX-HYD-01", sid=sid, feature={"featureId": "risingStage", "states": ["TRUE"]}, response="FAVORABLE", applicability={"months": [3, 4, 5, 6, 7], "regions": ["any"]})
    cold = rule("EX-COLD-01", sid=sid, feature={"featureId": "waterTempBand", "states": ["LT_10C"]}, response="LIMITING", applicability={"months": [11, 12, 1, 2, 3], "regions": ["any"]})
    nightrise = rule("EX-NGT-01", sid=sid, feature={"featureId": "daypart", "states": ["NIGHT"]}, response="WORKABLE", applicability={"regions": ["any"]})
    return [spn, hab, rise, cold, nightrise]


def mk_card(seasons_only=False, verified=True):
    c = copy.deepcopy(card_body())
    c.update({"speciesId": "example_fish", "sectorLabel": "Example fish", "passLevel": "DEEP", "componentScores": {k: {"score": 8, "why": ""} for k in ("seasonal", "spawn", "temperature", "depth", "hydrology", "vegetationHabitat", "nightLight", "current")},
              "sources": [{"id": "S1", "type": "AGENCY", "url": "https://a.example.gov/x", "title": "A", "publisher": "A", "supports": ["spawn", "temperature", "seasonal", "hydrology", "depth", "habitat", "nightLight", "current", "clarity"], "verification": "READ-FULL" if verified else "UNREACHABLE"},
                          {"id": "S2", "type": "PEER_REVIEWED", "url": "https://b.example.edu/y", "title": "B", "publisher": "B", "supports": ["spawn", "temperature", "seasonal", "hydrology", "depth", "habitat", "nightLight", "current", "clarity"], "verification": "READ-ABSTRACT" if verified else "NOT_SUPPORTED"},
                          {"id": "S3", "type": "ANECDOTAL", "url": "https://forum.example.com/z", "title": "forum", "publisher": "forum", "supports": ["spawn"], "verification": "READ-FULL"}]})
    c["card"]["spawn"]["timing"] = "Spring, April-June in the Southeast"
    c["card"]["seasonalMovement"] = {k: "x" for k in ("winter", "preSpawn", "spawn", "postSpawn", "summer", "fall")}
    if seasons_only:
        c["card"]["spawn"]["timing"] = "UNKNOWN"
    return c


def prof(sid="example_fish", rules=None, card=None, **kw):
    p = {"displayName": "Example fish", "scientificName": "Exempli gratia", "assessment": "ASSESSED", "knowledge": {"overallExact": 6.0}, "movement": {"bowfisherKnowledge": 6.5, "passLevel": "DEEP", "cardVersion": "t"}}
    return sp.build_profile(sid, profile=p, card=card if card is not None else mk_card(), rules=rules if rules is not None else mk_rules(sid), generated_from=GEN, season_assertions={"EX-NGT-01": "YEAR_ROUND"}, **kw)


class Structure(unittest.TestCase):
    def test_valid_profile_has_twelve_ordered_months_and_every_section(self):
        p = prof()
        self.assertEqual(sp.validate_profile(p), [])
        self.assertEqual([m["month"] for m in p["yearlyMovement"]["months"]], list(sp.MONTHS))
        for s in sp.SECTIONS:
            self.assertIn(s, p)

    def test_every_species_role_produces_a_valid_profile_even_with_nothing_known(self):
        for sid in list(ts.TARGET) + list(ts.SECONDARY) + list(ts.KNOWLEDGE_ONLY):
            p = sp.build_profile(sid, profile={"assessment": "NOT_ASSESSED"}, card=None, rules=[], generated_from=GEN)
            self.assertEqual(sp.validate_profile(p), [], sid)
            self.assertEqual(p["summary"]["knowledgeStatus"], "NOT_ASSESSED")

    def test_unknown_is_preserved_never_turned_into_zero(self):
        p = sp.build_profile("bowfin", profile={"assessment": "ASSESSED"}, card=None, rules=[], generated_from=GEN)
        self.assertTrue(all(v["status"] == "UNKNOWN" and v["completeness"] is None for v in p["knowledgeCoverage"].values()))
        self.assertTrue(all(m["movementStates"] == ["UNKNOWN"] and m["precision"] == "UNKNOWN" and m["confidence"] == "UNKNOWN" for m in p["yearlyMovement"]["months"]))
        self.assertIsNone(p["yearlyMovement"]["spawnWindowMonths"])


class Months(unittest.TestCase):
    def test_seasonal_precision_is_preserved_and_months_are_not_invented(self):
        p = prof(rules=[], card=mk_card(seasons_only=True))
        self.assertIsNone(p["yearlyMovement"]["spawnWindowMonths"])
        precs = {m["month"]: m["precision"] for m in p["yearlyMovement"]["months"]}
        self.assertNotIn("MONTH", precs.values())                            # nothing here is month-bounded
        self.assertEqual(precs["JAN"], "SEASONAL")
        self.assertEqual(precs["APR"], "UNKNOWN")                            # spring phases are not resolved to months
        self.assertTrue(all(m["spawnState"] == "UNKNOWN" for m in p["yearlyMovement"]["months"]))

    def test_spawn_window_comes_from_the_rule_and_gates_spawn_state(self):
        p = prof()
        by = {m["month"]: m for m in p["yearlyMovement"]["months"]}
        self.assertEqual(p["yearlyMovement"]["spawnWindowMonths"], ["APR", "MAY", "JUN"])
        self.assertEqual(p["yearlyMovement"]["spawnWindowBasis"], "RULE")
        self.assertEqual((by["MAY"]["spawnState"], by["OCT"]["spawnState"]), ("ACTIVE_WINDOW", "OUTSIDE_WINDOW"))
        self.assertEqual((by["MAY"]["shallowLikelihood"], by["MAY"]["precision"]), ("HIGH", "MONTH"))
        self.assertNotIn("SPAWN", by["OCT"]["movementStates"])
        self.assertEqual(by["OCT"]["hydrologyContext"], "UNKNOWN")           # the spring rise rule contributes nothing in October

    def test_month_text_is_parsed_only_when_a_range_is_named(self):
        self.assertEqual(sp.parse_months("April-June in the Southeast"), [4, 5, 6])
        self.assertEqual(sp.parse_months("late Feb to Apr"), [2, 3, 4])
        self.assertEqual(sp.parse_months("Nov-Feb"), [11, 12, 1, 2])
        self.assertIsNone(sp.parse_months("spring when water warms"))
        p = prof(rules=[], card=mk_card())
        self.assertEqual(p["yearlyMovement"]["spawnWindowBasis"], "CARD_TEXT")

    def test_condition_modifiers_are_separate_from_the_base_pattern(self):
        p = prof()
        ids = {m["id"] for m in p["yearlyMovement"]["conditionModifiers"]}
        self.assertIn("EX-HYD-01", ids)
        self.assertNotIn("EX-SPN-01", ids)                                    # the spawn window is base pattern, not a modifier
        self.assertEqual(p["yearlyMovement"]["months"][9]["month"], "OCT")


class SeasonalSafety(unittest.TestCase):
    def test_unbounded_rule_without_an_assertion_is_flagged_and_does_not_fire(self):
        r = mk_rules()
        p = sp.build_profile("example_fish", profile={"assessment": "ASSESSED"}, card=mk_card(), rules=r, generated_from=GEN)       # no assertions
        night = next(x for x in p["rulesSummary"] if x["ruleId"] == "EX-NGT-01")
        self.assertEqual((night["seasonReview"], night["fires"]), ("NOT_ESTABLISHED", False))
        self.assertIn("EX-NGT-01", p["yearlyMovement"]["unboundedSeasonalModifiers"])

    def test_outlook_cannot_contradict_the_profile(self):
        p = prof()
        sp_state = {"speciesId": "example_fish", "evaluated": True, "spawnWindow": {"state": "OUTSIDE"},
                    "responses": [{"featureId": "risingStage", "featureState": "TRUE", "response": "FAVORABLE", "confidence": "MEDIUM", "evidenceBasis": {"ruleIds": ["EX-HYD-01"]}}], "habitat": []}
        o = mo.species_outlook(sp_state, month=10)
        self.assertTrue(sp.outlook_contradictions(o, p, 10))                  # a rise rule bounded Mar-Jul contributing in October is a contradiction
        self.assertEqual(sp.outlook_contradictions(o, p, 5), [])


class Axes(unittest.TestCase):
    def test_general_and_regional_confidence_are_separate(self):
        a, b = mk_card(), mk_card()
        b["card"]["regionalConfidence"] = "LOW"
        pa, pb_ = prof(card=a), prof(card=b)
        self.assertEqual(pa["summary"]["generalConfidence"], pb_["summary"]["generalConfidence"])
        self.assertNotEqual(pa["summary"]["regionalConfidence"], pb_["summary"]["regionalConfidence"])
        self.assertEqual(pa["knowledgeCoverage"]["spawn"], pb_["knowledgeCoverage"]["spawn"])

    def test_review_and_field_states_are_independent_of_knowledge(self):
        base = prof()
        reviewed = sp.build_profile("example_fish", profile={"assessment": "ASSESSED"}, card=mk_card(), rules=mk_rules(), ledger={"EX-SPN-01": "ACCEPT", "EX-HYD-01": "REJECT"}, generated_from=GEN,
                                    season_assertions={"EX-NGT-01": "YEAR_ROUND"}, validation={"observations": {"example_fish": 3}, "trips": {"example_fish": 2}, "lastObservation": {"example_fish": "2027-04-01 20:00"}})
        r = {x["ruleId"]: x["review"] for x in reviewed["rulesSummary"]}
        self.assertEqual((r["EX-SPN-01"], r["EX-HYD-01"], r["EX-COLD-01"]), ("ACCEPTED", "REJECTED", "UNREVIEWED"))
        self.assertEqual(reviewed["validationSummary"]["status"], "OBSERVATIONS_IN_PROGRESS")
        self.assertEqual((reviewed["validationSummary"]["observations"], reviewed["validationSummary"]["trips"]), (3, 2))
        self.assertEqual(base["knowledgeCoverage"], reviewed["knowledgeCoverage"])           # knowledge display unchanged by review or field state
        self.assertEqual(base["validationSummary"]["status"], "NOT_VALIDATED")

    def test_lake_presence_is_never_part_of_a_profile(self):
        p = prof()
        self.assertEqual(sp.validate_profile(p), [])
        bad = copy.deepcopy(p)
        bad["identity"]["speciesPresence"] = {"x": 1}
        self.assertTrue(any("presence" in x for x in sp.validate_profile(bad)))


class Gaps(unittest.TestCase):
    def test_gaps_priorities_and_research_status_are_deterministic(self):
        a, b = prof(card=mk_card(verified=False)), prof(card=mk_card(verified=False))
        self.assertEqual(a["knowledgeGaps"], b["knowledgeGaps"])
        self.assertTrue(a["knowledgeGaps"])
        self.assertTrue(all(g["researchStatus"] == "RESEARCH_NOT_AUTHORIZED" for g in a["knowledgeGaps"]))
        night = next(g for g in a["knowledgeGaps"] if g["category"] == "night")
        self.assertIn("after dark", night["ifWeLearnThis"])

    def test_priority_follows_importance_tier_and_gap_and_protected_fish_are_not_researched(self):
        weak = {"status": "WEAK", "completeness": 3.0}
        self.assertEqual(sp.research_priority("common_carp", "TARGET", "night", weak)[0], "HIGH")
        self.assertEqual(sp.research_priority("common_carp", "TARGET", "clarity", weak)[0], "LOW")
        self.assertEqual(sp.research_priority("goldfish", "KNOWLEDGE_ONLY", "night", weak)[0], "LOW")
        self.assertEqual(sp.research_priority("paddlefish", "KNOWLEDGE_ONLY", "night", weak), ("DO_NOT_RESEARCH", 0.0))
        self.assertEqual(sp.research_priority("common_carp", "TARGET", "night", {"status": "STRONG", "completeness": 9.0})[0], "LOW")
        self.assertEqual(sp.research_priority("common_carp", "TARGET", "depth", {"status": "UNKNOWN", "completeness": None})[0], "HIGH")

    def test_unverified_sources_make_coverage_weak_not_unknown_and_anecdote_never_counts(self):
        p = prof(card=mk_card(verified=False))
        spawn = p["knowledgeCoverage"]["spawn"]
        self.assertEqual((spawn["status"], spawn["evidence"]), ("WEAK", "UNVERIFIED"))
        self.assertEqual(p["evidenceSummary"]["anecdotalIgnored"], 1)
        self.assertEqual(prof()["knowledgeCoverage"]["spawn"]["evidence"], "MULTI_SOURCE")


class Linkage(unittest.TestCase):
    def test_every_claim_id_resolves_to_provenance(self):
        p = prof()
        claims = p["evidenceSummary"]["claims"]
        for m in p["yearlyMovement"]["months"]:
            for c in m["claimIds"]:
                self.assertIn(c, claims)
        for r in p["rulesSummary"]:
            self.assertEqual(claims[r["ruleId"]]["type"], "RULE")
        self.assertNotIn("forum", json.dumps(p["evidenceSummary"]["sources"]))                 # anecdotal sources are not listed as evidence
        self.assertEqual(p["evidenceSummary"]["strongestSource"]["verification"], "READ-FULL")

    def test_rules_carry_status_review_field_and_plain_english(self):
        p = prof()
        r = next(x for x in p["rulesSummary"] if x["ruleId"] == "EX-HYD-01")
        self.assertEqual((r["status"], r["review"], r["field"], r["seasonality"]), ("RECONCILED", "UNREVIEWED", "NOT_VALIDATED", "BOUNDED"))
        self.assertIn("Mar-Jul", r["when"])
        self.assertTrue(r["expects"] and r["bowfisherMeaning"])

    def test_role_and_do_not_research_flags(self):
        self.assertEqual(prof("common_carp")["identity"]["role"], "TARGET")
        pp = prof("paddlefish")
        self.assertEqual(pp["identity"]["role"], "KNOWLEDGE_ONLY")
        self.assertIn("doNotResearch", pp["identity"])
        self.assertTrue(all(g["researchPriority"] == "DO_NOT_RESEARCH" for g in pp["knowledgeGaps"]))


class OpsSafety(unittest.TestCase):
    def test_serialisation_is_deterministic_and_private_data_is_refused(self):
        a, b = json.dumps(prof(), sort_keys=True), json.dumps(prof(), sort_keys=True)
        self.assertEqual(a, b)
        bad = prof()
        bad["evidenceSummary"]["sources"][0]["url"] = "gs://" + "private-bucket/x"
        self.assertTrue(any("private data" in x for x in sp.validate_profile(bad)))
        bad2 = prof()
        bad2["spawn"]["statements"].append({"text": "see /Us" + "ers/me/notes"})
        self.assertTrue(any("private data" in x for x in sp.validate_profile(bad2)))

    def test_internal_compilation_urls_are_not_exposed(self):
        c = mk_card()
        c["sources"][0].update({"type": "PACKET", "url": "packets" + "/example.md", "title": "packets" + "/example.md S1"})
        p = prof(card=c)
        self.assertEqual(sp.validate_profile(p), [])
        self.assertIsNone(next(s for s in p["evidenceSummary"]["sources"] if s["id"] == "S1")["url"])

    def test_coverage_matrix_lists_targets_first_with_structured_cells(self):
        profs = {"goldfish": prof("goldfish"), "common_carp": prof("common_carp"), "bighead_carp": prof("bighead_carp")}
        m = pb.coverage_matrix(profs)
        self.assertEqual([r["speciesId"] for r in m["species"]], ["common_carp", "bighead_carp", "goldfish"])
        self.assertEqual(set(m["species"][0]["categories"]), set(sp.CATEGORIES))
        self.assertIn(m["species"][0]["categories"]["spawn"]["coverage"], sp.COVERAGE)

    @unittest.skipUnless(os.environ.get("BIO_PRIVATE_BUNDLE"), "needs the private staged bundle (BIO_PRIVATE_BUNDLE=dir)")
    def test_every_canonical_species_in_the_private_bundle_profiles_cleanly(self):
        import biological_brain as bb
        d = os.environ["BIO_PRIVATE_BUNDLE"]
        b = bb.load_bundle(lambda p: open(os.path.join(d, p), "rb").read())
        profs = pb.profiles_from_bundle(b)
        self.assertEqual(set(profs), set(b.profiles))
        for sid, p in profs.items():
            self.assertEqual(sp.validate_profile(p), [], sid)


if __name__ == "__main__":
    unittest.main()
