#!/usr/bin/env python3
"""Tests for coverage_recovery_plan.py (recomputed counts, ranking, rubric projection).

    python3 -m unittest discover -s jobs/lake-brain/bindings -p 'test_*.py'      (or pytest)
"""
from __future__ import annotations

import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = load("coverage_recovery_plan", os.path.join(HERE, "coverage_recovery_plan.py"))


def lake(blockers, cat="held", prov="x", tier="C", bow=5, **kw):
    return {"lakeId": kw.pop("lid", "L|ST"), "category": cat, "blockers": blockers, "provider": prov, "operator": prov, "bowTier": tier, "bowScore": bow,
            "quality": {"src": True, "plan": False, "flood": False, "hist": True, "base": True}, **kw}


class Taxonomy(unittest.TestCase):
    def test_blockers_map_every_generator_reason(self):
        f = R.blockers_for
        self.assertEqual(f({"history-live-mismatch"}, "rise", "ok", "FIXED"), {"mismatch:FIXED"})
        self.assertEqual(f({"coordinate-flag"}, "a2w", "off_water"), {"coord:off_water"})
        self.assertEqual(f({"coordinate-flag"}, "a2w", "identity_risk"), {"coord:identity_risk"})
        self.assertEqual(f({"coordinate-flag"}, "a2w", ""), {"coord:no_polygon"})
        self.assertEqual(f({"undocumented-provider"}, "sjrwmd", "ok"), {"terms:sjrwmd_nhdes"})
        self.assertEqual(f({"undocumented-provider"}, "nhdes", "ok"), {"terms:sjrwmd_nhdes"})
        self.assertEqual(f({"undocumented-provider"}, "duke", "ok"), {"terms:undocumented"})
        self.assertEqual(f({"provider-not-allowed", "post-hoc"}, "coops", "ok"), {"adapter", "posthoc"})
        self.assertEqual(f({"flagged", "flagged-wave1", "stage-only"}, "usgs", "ok"), {"flag", "stage"})
        self.assertEqual(f({"no-adapter-series"}, "twdb", "ok"), {"adapter"})
        with self.assertRaises(ValueError):
            f({"made-up"}, "x", "ok")

    def test_bow_score_matches_the_research_heuristic(self):
        self.assertEqual(R.bow_score(84.379, "AK", False, "N1a_natural_deep_or_unknown"), (5, "C"))      # Aleknagik, research bowScore 5
        self.assertEqual(R.bow_score(60.0, "TX", True, "R4_open_basin_storage"), (4 + 3 + 1 + 1, "A"))
        self.assertEqual(R.bow_score(None, "CO", False, ""), (0 + 2 + 0 + 1, "C"), "missing area counts as 0.5 km2")
        self.assertEqual(R.bow_score(10.0, "IL", False, "x")[1], "B")

    @unittest.skipUnless(os.path.exists(os.path.join(R.B.DATA, "binding2", "unbound_profile.json")), "research data not present")
    def test_bow_score_reproduces_all_research_values(self):
        prof = json.load(open(os.path.join(R.B.DATA, "binding2", "unbound_profile.json")))
        n = 0
        for x in prof:
            reg = x["hasDam"] == "True" or x["poolBasis"] == "fullPool"
            s, t = R.bow_score(float(x["areaKm2"]) if x["areaKm2"] else None, x["state"], reg, x["lake_class"] or "")
            self.assertEqual((s, t), (x["bowScore"], x["bowTier"]), x["lakeId"])
            n += 1
        self.assertGreater(n, 200)


class Recoverability(unittest.TestCase):
    def test_a_lake_needs_every_blocker_pulled(self):
        L = lake(["coord:off_water", "posthoc"])
        self.assertFalse(R.recoverable(L, {"coord:off_water"}))
        self.assertFalse(R.recoverable(L, {"posthoc"}))
        self.assertTrue(R.recoverable(L, {"coord:off_water", "posthoc", "flag"}))

    def test_eligible_and_blockerless_lakes_are_never_recoverable(self):
        self.assertFalse(R.recoverable(lake([], cat="eligible"), {"posthoc"}))
        self.assertFalse(R.recoverable(lake([]), {"posthoc"}))

    def test_mismatch_lakes_follow_their_own_disposition(self):
        self.assertTrue(R.recoverable(lake(["mismatch:FIXED"]), {"mismatch:FIXED"}))
        self.assertFalse(R.recoverable(lake(["mismatch:NEEDS HUMAN REVIEW"]), {"mismatch:FIXED"}))
        self.assertFalse(R.recoverable(lake(["mismatch:NO DEFENSIBLE MATCH"]), {"mismatch:FIXED", "mismatch:NEEDS HUMAN REVIEW"}))


class Ranking(unittest.TestCase):
    def setUp(self):
        self.old = R.OPPORTUNITIES
        mk = lambda i, pulls, c, e: dict(id=i, name=i, pulls=pulls, confidence=c, effort=e, kind="K", waiting="w", why="y")   # noqa: E731
        R.OPPORTUNITIES = [mk("lowconf_big", ["a"], "L", "S"), mk("hiconf_small", ["b"], "H", "L"), mk("empty", ["c"], "H", "S"), mk("hiconf_easy", ["d"], "H", "S")]
        self.lakes = {f"a{i}|S": lake(["a"], tier="A", lid=f"a{i}|S") for i in range(50)}
        self.lakes["b|S"] = lake(["b"], lid="b|S")
        self.lakes.update({f"d{i}|S": lake(["d"], lid=f"d{i}|S") for i in range(2)})

    def tearDown(self):
        R.OPPORTUNITIES = self.old

    def test_confidence_then_effort_then_size_and_empty_last(self):
        r = R.rank(self.lakes)
        self.assertEqual([x["id"] for x in r], ["hiconf_easy", "hiconf_small", "lowconf_big", "empty"])
        self.assertEqual([x["rank"] for x in r], [1, 2, 3, 4])

    def test_cumulative_counts_a_lake_once_and_in_order(self):
        r = R.rank(self.lakes)
        for L in self.lakes.values():
            L["coordFlag"] = "ok"
        steps = R.cumulative({**self.lakes, **{f"e{i}|ST": lake([], cat="eligible", lid=f"e{i}|ST") for i in range(3)}}, r)
        profiled = [s["profiled"] for s in steps]
        self.assertEqual(profiled, sorted(profiled), "coverage never goes down")
        self.assertEqual(steps[-1]["profiled"], 3 + 50 + 1 + 2)


class Projection(unittest.TestCase):
    def test_pilot_baseline_reproduces_the_published_gate(self):
        q = [{"src": True, "plan": True, "flood": i < 1, "hist": i < 1, "base": i < 1} for i in range(5)]
        p = R.project(q, "NOT_VALIDATED")
        self.assertEqual(p["displayed"], 3.0, "5 of 621 lakes: coverage gate 3.0")
        self.assertEqual(p["uncapped"], 4.3)
        self.assertIn("coverage", p["gates"])

    def test_validation_gate_caps_the_displayed_score_at_five(self):
        q = [{"src": True, "plan": True, "flood": True, "hist": True, "base": True} for _ in range(400)]
        p = R.project(q, "NOT_VALIDATED")
        self.assertEqual(p["displayed"], 5.0)
        self.assertGreater(p["uncapped"], 5.0)
        self.assertEqual(p["gates"], ["validation"])
        self.assertGreater(R.project(q, "PARTIAL")["displayed"], 5.0)

    def test_coverage_ladder_steps(self):
        q = {"src": True, "plan": False, "flood": False, "hist": False, "base": False}
        dims = {n: R.project([q] * n, "NOT_VALIDATED")["coverageDim"] for n in (30, 32, 155, 156, 310, 311, 466, 559)}
        self.assertEqual((dims[30], dims[32]), (1.0, 2.0), "5 % of 621 = 31.05 lakes")
        self.assertEqual((dims[155], dims[156]), (3.0, 5.0))
        self.assertEqual((dims[310], dims[311]), (5.0, 7.0))
        self.assertEqual((dims[466], dims[559]), (9.0, 10.0))


@unittest.skipUnless(os.path.exists(R.OUT), "plan not built")
class CommittedPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.load(open(R.OUT))

    def test_every_directory_lake_is_counted_once(self):
        c = self.d["counts"]
        self.assertEqual(c["directory"], 621)
        self.assertEqual(c["eligible"] + c["heldResearchBound"] + c["unbound"], 621)
        self.assertEqual(c["eligible"], 196)
        self.assertEqual(sum(c["byTaxonomy"].values()), c["heldResearchBound"] + c["unbound"])
        self.assertEqual(sum(x["lakes"] for x in c["blockerSignatures"]), c["heldResearchBound"] + c["unbound"])

    def test_coordinate_flag_counts_for_the_whole_directory(self):
        f = c = self.d["counts"]["coordinateFlagsAllLakes"]
        self.assertEqual((f["identity_risk"], f["off_water"], f["no_polygon"]), (43, 126, 22))
        cross = self.d["counts"]["coordinateFlagCrossTab"]
        self.assertEqual(sum(sum(v.values()) for v in cross.values()), 621)
        self.assertNotIn("eligible", {k for flag, v in cross.items() if flag != "ok" for k in v}, "no eligible lake has a coordinate flag")

    def test_mismatch14_matches_the_dispositions(self):
        disp = json.load(open(R.B.DISPOSITIONS))
        any_b = self.d["counts"]["byAnyBlocker"]
        for k, v in disp["counts"].items():
            self.assertEqual(any_b.get(f"mismatch:{k}", 0), v, k)
        r1 = next(o for o in self.d["opportunities"] if o["id"] == "R1")
        self.assertEqual(r1["lakeIds"], disp["newlyRecovered"])

    def test_t1_reproduction_matches_the_research_scorer(self):
        t1 = self.d["t1Reproduction"]
        self.assertEqual((t1["profiled"], t1["plan"], t1["flood"], t1["hist"], t1["base"]), (273, 0.44, 0.575, 0.934, 0.989))

    def test_projection_is_capped_by_validation_and_never_claims_more(self):
        for s in self.d["cumulative"]:
            self.assertLessEqual(s["projection"]["NOT_VALIDATED"]["displayed"], 5.0, s["step"])
        self.assertIn("PROJECTION ONLY", self.d["note"])

    def test_cumulative_is_monotone_and_never_reaches_unrecoverable_lakes(self):
        prof = [s["profiled"] for s in self.d["cumulative"]]
        self.assertEqual(prof, sorted(prof))
        self.assertEqual(self.d["cumulative"][0]["profiled"], 5)
        self.assertEqual(self.d["cumulative"][1]["profiled"], 196)
        self.assertLess(prof[-1], 621, "Bartlett (NO DEFENSIBLE MATCH) is never recovered")

    def test_padding_with_poor_matches_does_not_raise_the_uncapped_score(self):
        steps = {s["step"]: s for s in self.d["cumulative"]}
        last = self.d["cumulative"][-1]["projection"]["NOT_VALIDATED"]["uncapped"]
        best = max(s["projection"]["NOT_VALIDATED"]["uncapped"] for s in self.d["cumulative"])
        self.assertLess(last, best)

    def test_opportunities_are_ranked_by_the_stated_order(self):
        ops = self.d["opportunities"]
        key = lambda r: (r["lakes"] == 0, -R.CONF[r["confidence"]], R.EFF[r["effort"]], -r["bowA"], -r["lakes"], -r["reuse"])   # noqa: E731
        self.assertEqual([o["id"] for o in ops], [o["id"] for o in sorted(ops, key=key)])
        self.assertEqual(ops[0]["id"], "R1")

    @unittest.skipUnless(os.path.exists(R.B.Inputs.__init__.__code__.co_filename), "inputs")
    def test_reproducible(self):
        try:
            R.B.Inputs()
        except SystemExit:
            self.skipTest("research inputs not present")
        self.assertEqual(R.main(["--check"]), 0, "run python3 jobs/lake-brain/bindings/coverage_recovery_plan.py")


if __name__ == "__main__":
    unittest.main()
