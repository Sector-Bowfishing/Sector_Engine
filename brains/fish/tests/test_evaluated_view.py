"""Intelligence-facing view, state claims block, and fingerprint/WRITE-SKIP behaviour."""
import datetime as dt
import unittest

import bio_state as bs
import evaluated_view as ev
import orchestration as orch
from test_rules_state_validation import BiologicalStateTests, inputs      # shared fixtures


class View(unittest.TestCase):
    def setUp(self):
        self.b = BiologicalStateTests("test_state_shape_and_pilot_internal_status")
        self.state = self.b.build()

    def test_claims_block_separates_level_from_maturity(self):
        c = self.state["claims"]
        self.assertEqual([c[k]["level"] for k in ("inputs", "features", "speciesResponses")], [1, 2, 3])
        self.assertEqual(c["speciesResponses"]["maturity"], "NOT_VALIDATED")

    def test_view_is_valid_flat_and_not_consumable_while_pilot(self):
        v = ev.intelligence_view(self.state)
        self.assertEqual(ev.validate_view(v), [])
        self.assertFalse(v["consumable"])
        self.assertEqual(v["claim"], {"level": 3, "maturity": "NOT_VALIDATED"})
        self.assertNotIn("evidence", str(v).lower())
        for sp in v["species"]:
            self.assertNotIn("reason", sp)

    def test_view_validator_rejects_misclassification(self):
        v = ev.intelligence_view(self.state)
        v["claim"]["level"] = 2
        self.assertTrue(ev.validate_view(v))

    def test_fingerprint_ignores_clock_and_changes_with_material_input(self):
        later = dict(self.state, generatedAt="2030-01-01T00:00:00Z")
        self.assertEqual(bs.state_fingerprint(self.state), bs.state_fingerprint(later))
        self.assertEqual(orch.plan_state(bs.state_fingerprint(self.state), bs.state_fingerprint(later))["action"], "SKIP")
        changed = self.b.build(inp=inputs(temp_f=50, lake_trend="FALLING"))
        self.assertEqual(orch.plan_state(bs.state_fingerprint(self.state), bs.state_fingerprint(changed))["action"], "WRITE")
        self.assertEqual(orch.plan_state(None, bs.state_fingerprint(self.state))["action"], "WRITE")


if __name__ == "__main__":
    unittest.main()
