import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import review_plain as rp      # noqa: E402
import review      # noqa: E402
from test_rules_state_validation import fixture_ruleset      # noqa: E402


class Plain(unittest.TestCase):
    def test_months_phrase_runs_and_wrap(self):
        self.assertEqual(rp.months_phrase([3, 4, 5]), "Mar-May")
        self.assertEqual(rp.months_phrase([11, 12, 1, 2, 3]), "Nov-Mar")
        self.assertEqual(rp.months_phrase(None), "any time of year")
        self.assertEqual(rp.months_phrase([2, 5]), "Feb, May")

    def test_package_has_three_decisions_no_jargon_and_a_matching_blank_sheet(self):
        rs = fixture_ruleset()
        md, sheet = rp.package([r for r in rs.rules], {"example_fish": "Example fish"})
        self.assertIn("ACCEPT / REJECT / NEEDS_MORE_EVIDENCE", md)
        self.assertNotIn("featureId", md)
        self.assertTrue(sheet and all(x["decision"] == "" for x in sheet))
        usable = [r for r in rs.rules if r["status"] in ("RECONCILED", "APPROVED")]
        self.assertEqual(len(sheet), len(usable))                                   # drafts are never put in front of a reviewer
        self.assertEqual(md.count("| ACCEPT / REJECT"), len(usable))

    def test_each_rule_kind_renders_a_condition_conclusion_and_meaning(self):
        for r in fixture_ruleset().rules:
            if r["status"] != "RECONCILED":
                continue
            self.assertTrue(rp.condition(r) and rp.conclusion(r) and rp.meaning(r), r["ruleId"])
            self.assertIn("independent inspected", rp.strength(r))

    def test_answer_sheet_is_accepted_by_the_apply_tool_when_filled(self):
        import datetime as dt
        rs = fixture_ruleset()
        _, sheet = rp.package(rs.rules, {})
        row = dict(sheet[0], decision="ACCEPT", reviewer="Pat Reviewer", reviewerRole="OWNER", date="2026-10-14")
        row.pop("fish")
        rules, retired, ledger, ver = review.apply_decisions(rs, [row], dt.datetime(2026, 10, 14, tzinfo=dt.timezone.utc))
        self.assertEqual(ledger[0]["decision"], "ACCEPT")


if __name__ == "__main__":
    unittest.main()
