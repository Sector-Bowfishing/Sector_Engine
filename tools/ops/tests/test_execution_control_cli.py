"""tools/ops/execution_control.py `brain --max-runs-per-day` builds the right document (dry run, no network)."""
import importlib.util
import os
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ec_cli", os.path.join(HERE, "..", "execution_control.py"))
CLI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CLI)
EC = CLI.EC


def _args(**kw):
    base = dict(cmd="brain", changed_by="t", reason="r", approval_ref=None, brains="", brain="lake-brain", brain_on=None,
                max_starts_per_cycle=2, max_runs_per_day=None, confirm="", dry_run=True)
    base.update(kw)
    return types.SimpleNamespace(**base)


class Main(unittest.TestCase):
    def test_out_of_range_exits_2(self):
        orig = CLI.read
        CLI.read = lambda: None
        try:
            self.assertEqual(CLI.main(["brain", "--changed-by", "t", "--reason", "r", "--brain", "lake-brain",
                                       "--max-runs-per-day", "0", "--dry-run"]), 2)
            self.assertEqual(CLI.main(["brain", "--changed-by", "t", "--reason", "r", "--brain", "lake-brain",
                                       "--max-runs-per-day", "36", "--dry-run"]), 0)
        finally:
            CLI.read = orig


class RunLimit(unittest.TestCase):
    def setUp(self):
        self.ids = sorted(CLI.O.load_manifest()["brains"])
        self.assertIn("lake-brain", self.ids)
        raw = EC.document("ENABLED", brains={b: {"enabled": b == "lake-brain", "limits": {**EC.DEFAULT_LIMITS, "maxRunsPerDay": 12}}
                                             for b in self.ids},
                          changed_by="x", changed_at="2026-11-21T00:00:00Z", approval_ref="ref", reason="r", max_starts_per_cycle=3)
        self.cur = EC.parse(raw)
        self.brains = {b: {"enabled": self.cur["brains"][b]["enabled"], "limits": self.cur["brains"][b]["limits"]} for b in self.ids}

    def test_sets_only_the_limit(self):
        doc = CLI._build(_args(max_runs_per_day=36), self.cur, self.brains, self.ids, "now")
        p = EC.parse(doc)
        self.assertEqual(p["state"], "ENABLED")
        self.assertEqual(p["approvalRef"], "ref")
        self.assertEqual(p["maxStartsPerCycle"], 3)
        self.assertEqual(EC.limits(p, "lake-brain")["maxRunsPerDay"], 36)
        self.assertTrue(EC.brain_enabled(p, "lake-brain"))
        for b in self.ids:
            if b != "lake-brain":
                self.assertEqual(EC.limits(p, b)["maxRunsPerDay"], 12)
                self.assertFalse(EC.brain_enabled(p, b))

    def test_out_of_range_refused(self):
        for n in (0, 97):
            with self.assertRaises(ValueError):
                CLI._build(_args(max_runs_per_day=n), self.cur, self.brains, self.ids, "now")

    def test_needs_an_action(self):
        self.assertIsNone(CLI._build(_args(), self.cur, self.brains, self.ids, "now"))

    def test_disable_still_works(self):
        doc = CLI._build(_args(brain_on=False), self.cur, self.brains, self.ids, "now")
        self.assertFalse(EC.brain_enabled(EC.parse(doc), "lake-brain"))


if __name__ == "__main__":
    unittest.main()
