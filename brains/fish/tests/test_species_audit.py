import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import species_audit as sa      # noqa: E402
from test_rules_state_validation import fixture_ruleset      # noqa: E402


def row(overall=3.0, assessment="ASSESSED", dom_status="SCORED"):
    return {"displayName": "Example fish", "scientificName": "Exempli gratia", "assessment": assessment, "researchMaturity": "RESEARCH",
            "knowledge": {"overallExact": overall, "overallRounded": round(overall), "domains": {"habitatDepthCover": {"score": 4, "status": dom_status}}}}


class Audit(unittest.TestCase):
    def test_unknown_stays_unknown_and_is_not_zero(self):
        c = sa.components(row(), None)
        self.assertIsNone(c["evidenceQuality"])
        self.assertIsNone(c["regionalTransfer"])
        self.assertEqual(c["responseCoverage"], 0.0)                       # no rules is a measured zero for an assessed species
        self.assertEqual(sa.audit_score(c)["score"], round((55 * 3.0 + 20 * 0.0) / 75, 2))
        self.assertEqual(sa.audit_score(c)["completeness"], 0.75)
        self.assertEqual(sa.domain_view(row(dom_status="UNKNOWN")), {"habitatDepthCover": "UNKNOWN"})

    def test_not_assessed_is_not_scored_not_zero(self):
        r = sa.species_record("tilapia_unresolved", row(assessment="NOT_ASSESSED"), None)
        self.assertIsNone(r["auditScore"])
        self.assertFalse(r["inBiologicalScore"])
        self.assertEqual(r["scoreType"], "NOT_SCORED")

    def test_good_desk_knowledge_is_not_erased_by_missing_validation(self):
        r = sa.species_record("common_carp", row(7.0), None)
        self.assertGreater(r["auditScore"], 4)
        self.assertEqual(r["validation"], "NOT_VALIDATED")

    def test_rule_stats_and_scoring_from_rules(self):
        rs = fixture_ruleset()
        st = sa.rule_stats(rs)
        self.assertEqual(st["example_fish"]["usable"], rs.counts("example_fish")["usable"])
        self.assertEqual(sa.rule_stats(rs), st)                             # deterministic
        c = sa.components(row(), st["example_fish"])
        self.assertIsNotNone(c["evidenceQuality"])
        self.assertEqual(sa.audit_score(c), sa.audit_score(dict(c)))

    def test_every_species_exactly_once_with_one_primary_group(self):
        ids = ["a_fish", "striped_mullet", "american_shad", "tilapia_unresolved"]
        recs = [sa.species_record(i, row(), None) for i in ids]
        self.assertEqual(sa.check_accounting(recs, ids), [])
        self.assertEqual(sa.check_accounting(recs + [recs[0]], ids)[0], "a_fish: appears 2 times")
        g = {x: sa.group_view(recs, x)["total"] for x in sa.GROUPS}
        self.assertEqual(sum(g.values()), len(ids))                         # no double count between groups

    def test_cross_habitat_flags_and_review_marker(self):
        self.assertEqual(sa.habitat_for("striped_mullet")["primaryGroup"], "SALTWATER")
        self.assertTrue(sa.habitat_for("striped_mullet")["groupingReviewRequired"])
        self.assertEqual(sa.habitat_for("american_shad")["habitatFlag"], "ANADROMOUS")
        self.assertEqual(sa.habitat_for("tilapia_unresolved")["habitatFlag"], "CROSS_HABITAT")
        self.assertEqual(sa.habitat_for("common_carp")["habitatFlag"], "FRESHWATER_ONLY")

    def test_subset_facts_recounts_and_does_not_mutate_input(self):
        facts = {"registry": {"responsibilities": {"speciesKnowledge": {"speciesCount": 3, "assessedCount": 2, "notAssessedCount": 1}}},
                 "species": {"a": {"assessment": "ASSESSED"}, "b": {"assessment": "ASSESSED"}, "c": {"assessment": "NOT_ASSESSED"}}}
        sub = sa.subset_facts(facts, lambda k: k != "b")
        self.assertEqual(sub["registry"]["responsibilities"]["speciesKnowledge"], {"speciesCount": 2, "assessedCount": 1, "notAssessedCount": 1})
        self.assertEqual(facts["registry"]["responsibilities"]["speciesKnowledge"]["speciesCount"], 3)

    def test_audit_never_changes_official_state(self):
        import inspect
        src = inspect.getsource(sa)
        self.assertNotIn("write(", src)
        self.assertNotIn("open(", src)


if __name__ == "__main__":
    unittest.main()
