"""Reviewer workflow: acceptance re-issues a rule as a new APPROVED version; nothing is edited, self-promoted or auto-approved (synthetic fixtures)."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import rules as rl                      # noqa: E402
import validation_log as vl             # noqa: E402
from test_rules_state_validation import NOW, ev, fixture_ruleset, rule    # noqa: E402
from tools import review                # noqa: E402


def dec(rid="EX-FLW-01", v=1, **kw):
    d = {"ruleId": rid, "ruleVersion": v, "decision": "ACCEPT", "reviewer": "r_mike", "reviewerRole": "OWNER", "date": "2026-10-20", "note": "checked"}
    d.update(kw)
    return d


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.rs = fixture_ruleset()

    def test_accept_reissues_a_new_approved_version_and_retires_the_old_without_editing_it(self):
        old = [r for r in self.rs.rules if r["ruleId"] == "EX-FLW-01"][0]
        h = rl.rule_hash(old)
        rules, retired, ledger, ver = review.apply_decisions(self.rs, [dec()], NOW)
        new = [r for r in rules if r["ruleId"] == "EX-FLW-01" and r["ruleVersion"] == 2][0]
        self.assertEqual((new["status"], new["review"]["reviewer"], new["review"]["reviewerRole"]), ("APPROVED", "r_mike", "OWNER"))
        self.assertEqual(rl.rule_hash([r for r in rules if r["ruleId"] == "EX-FLW-01" and r["ruleVersion"] == 1][0]), h)       # v1 untouched
        self.assertEqual(retired[-1]["supersededBy"], {"ruleId": "EX-FLW-01", "ruleVersion": 2})
        self.assertNotEqual(rl.rule_hash(new), h)
        self.assertEqual(ledger[0]["newVersion"], 2)
        self.assertIn("+review.", ver)
        rl.RuleSet(rules, ver, retired=retired)                                                                              # the result validates

    def test_new_approved_version_needs_a_fresh_freeze_before_any_prediction_uses_it(self):
        rules, retired, _, ver = review.apply_decisions(self.rs, [dec()], NOW)
        rs2 = rl.RuleSet(rules, ver, retired=retired)
        d = tempfile.mkdtemp()
        reg = vl.FrozenRuleRegister(os.path.join(d, "r.jsonl"))
        new = [r for r in rs2.active_rules() if r["ruleId"] == "EX-FLW-01"][0]
        self.assertEqual(new["ruleVersion"], 2)
        self.assertIsNone(reg.get("EX-FLW-01", 2))
        reg.freeze(new, NOW, "t")
        self.assertIsNotNone(reg.get("EX-FLW-01", 2))
        shutil.rmtree(d)

    def test_refusals(self):
        for bad, why in ((dec(reviewer="claude"), "author"), (dec(reviewer=""), "reviewer"), (dec(reviewerRole="ROBOT"), "reviewerRole"), (dec(decision="MAYBE"), "decision"),
                         (dec(date=""), "date"), (dec(rid="EX-FLW-99"), "exist"), (dec(rid="ED-FLW-01", v=1), "RECONCILED")):
            with self.assertRaises(rl.RuleError, msg=why):
                review.apply_decisions(self.rs, [bad], NOW)

    def test_reject_and_changes_do_not_alter_any_rule_but_are_recorded(self):
        rules, retired, ledger, ver = review.apply_decisions(self.rs, [dec(decision="REJECT", note="overclaims"), dec("EX-SPN-01", decision="CHANGES")], NOW)      # legacy spelling still accepted
        self.assertEqual(len(rules), len(self.rs.rules))
        self.assertEqual(ver, self.rs.rules_version)
        self.assertEqual([e["decision"] for e in ledger], ["REJECT", "NEEDS_MORE_EVIDENCE"])
        self.assertTrue(all(r["status"] != "APPROVED" for r in rules))

    def test_needs_more_evidence_spelling_and_common_carp_first(self):
        _, _, ledger, _ = review.apply_decisions(self.rs, [dec(decision="needs more evidence")], NOW)
        self.assertEqual(ledger[0]["decision"], "NEEDS_MORE_EVIDENCE")

        class Fake:
            by_species = {"bighead_carp": [], "spotted_gar": [], "common_carp": [], "zander": []}
        self.assertEqual(review.species_order(Fake)[:2], ["common_carp", "spotted_gar"])

    def test_template_is_blank_and_covers_only_reconciled_rules(self):
        tpl = review.build_template(self.rs)
        self.assertTrue(tpl and all(x["decision"] == "" for x in tpl))
        self.assertTrue(all(self.rs.by_species[next(s for s in self.rs.by_species if any(r["ruleId"] == x["ruleId"] for r in self.rs.by_species[s]))] for x in tpl))

    def test_a_retired_or_already_superseded_rule_cannot_be_accepted_twice(self):
        rules, retired, _, ver = review.apply_decisions(self.rs, [dec()], NOW)
        rs2 = rl.RuleSet(rules, ver, retired=retired)
        with self.assertRaises(rl.RuleError):
            review.apply_decisions(rs2, [dec(v=1)], NOW)                          # v1 is retired

    def test_packet_is_concise_and_marks_excluded_drafts_and_uncounted_evidence(self):
        text = review.build_packet(self.rs, ["example_fish", "draft_fish"])
        self.assertIn("EX-FLW-01 v1", text)
        self.assertIn("Excluded DRAFT rules", text)
        self.assertIn("not counted", review.build_packet(rl.RuleSet([rule("EX-FLW-05", evidence=[ev(1, "a"), ev(2, "b", counts=False, read="SNIPPET-ONLY")])], "t")))
        self.assertIn("APPROVED is **not** VALIDATED", text)
        self.assertLess(len(text), 9000)

    def test_cli_roundtrip_writes_a_valid_rules_directory(self):
        d = tempfile.mkdtemp()
        src, out = os.path.join(d, "src"), os.path.join(d, "out")
        review.write_dir(self.rs.rules, [], [], self.rs.rules_version, src)
        dpath = os.path.join(d, "d.json")
        json.dump([dec()], open(dpath, "w"))
        self.assertEqual(review.main(["x", "apply", src, dpath, out]), 0)
        rs2 = rl.load_rules_dir(out)
        self.assertEqual([r["ruleVersion"] for r in rs2.for_species("example_fish") if r["ruleId"] == "EX-FLW-01"], [2])
        self.assertTrue(os.path.exists(os.path.join(out, "review_ledger.jsonl")))
        self.assertEqual(review.main(["x", "packet", src, os.path.join(d, "p.md")]), 0)
        shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
