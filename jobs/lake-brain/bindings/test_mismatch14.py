#!/usr/bin/env python3
"""Tests for the mismatch14 probe, criteria, disposition builder and the generator's recovered-lake path.

    python3 -m unittest discover -s jobs/lake-brain/bindings -p 'test_*.py'      (or pytest)
"""
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(REPO, "jobs", "lake-brain", "data")


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


C = load("mismatch14_criteria", os.path.join(HERE, "mismatch14_criteria.py"))
P = load("mismatch14_probe", os.path.join(HERE, "mismatch14_probe.py"))
D = load("build_mismatch14_dispositions", os.path.join(HERE, "build_mismatch14_dispositions.py"))
B = load("build_bindings_table", os.path.join(HERE, "build_bindings_table.py"))

D0 = dt.date(2024, 1, 1)


def series(n: int, fn) -> dict:
    return {D0 + dt.timedelta(days=i): fn(i) for i in range(n)}


class CriteriaFrozen(unittest.TestCase):
    def test_pre_registered_values_are_not_edited(self):
        # these numbers were fixed before any date-matched comparison ran; changing one needs a new CRITERIA_VERSION and a new disposition run
        self.assertEqual((C.MIN_MATCHED_DAYS, C.WINDOW_DAYS, C.MEDIAN_ABS_FT, C.P95_ABS_FT), (365, 1095, 0.5, 2.0))
        self.assertEqual((C.HISTORY_MAX_STALE_DAYS, C.POOL_TOL_FT), (45, 1.0))
        self.assertEqual((C.SHORT_MIN_DAYS, C.SHORT_MEDIAN_FT, C.SHORT_MAX_FT), (20, 0.1, 0.5))
        self.assertEqual(C.CRITERIA_VERSION, "mismatch14-v1")


class PureFunctions(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(P.percentile([1, 2, 3, 4, 5], 50), 3)
        self.assertAlmostEqual(P.percentile([0, 10], 95), 9.5)
        with self.assertRaises(ValueError):
            P.percentile([], 50)

    def test_daily_median_uses_utc_day_and_drops_non_finite(self):
        ms = lambda d, h: int(dt.datetime(2026, 3, d, h, tzinfo=dt.timezone.utc).timestamp() * 1000)
        out = P.daily_median([(ms(1, 1), 10.0), (ms(1, 23), 20.0), (ms(1, 12), 12.0), (ms(2, 0), 5.0), (ms(2, 3), float("nan")), (ms(2, 4), None)])
        self.assertEqual(out[dt.date(2026, 3, 1)], 12.0)
        self.assertEqual(out[dt.date(2026, 3, 2)], 5.0)

    def test_window_ends_at_history_last_day_capped_at_run_date(self):
        h = series(10, lambda i: 1.0)
        lo, hi = P.window_for(h)
        self.assertEqual(hi, max(h))
        self.assertEqual((hi - lo).days, C.WINDOW_DAYS - 1)
        future = {P.RUN_DATE + dt.timedelta(days=5): 1.0}
        self.assertEqual(P.window_for(future)[1], P.RUN_DATE)
        self.assertIsNone(P.window_for({}))

    def test_overlap_passes_when_series_agree(self):
        live = series(400, lambda i: 600 + (i % 7) * 0.1)
        hist = {d: v + 0.2 for d, v in live.items()}
        r = P.evaluate_overlap(live, hist, P.window_for(hist))
        self.assertTrue(r["O1"] and r["O2"] and r["O3"])
        self.assertEqual(r["matchedDays"], 400)
        self.assertAlmostEqual(r["medianSignedFt"], -0.2, places=3)

    def test_overlap_fails_each_criterion_separately(self):
        base = series(400, lambda i: 600.0)
        short = P.evaluate_overlap(base, base, (D0, D0 + dt.timedelta(days=100)))
        self.assertFalse(short["O1"], "only 101 matched days")
        off = {d: v + 0.55 for d, v in base.items()}
        r = P.evaluate_overlap(base, off, P.window_for(off))
        self.assertTrue(r["O1"] and r["O3"])
        self.assertFalse(r["O2"], "0.55 ft constant offset is beyond the 0.5 ft median tolerance (Rend Lake case)")
        tail = {d: v + (3.0 if i % 10 == 0 else 0.0) for i, (d, v) in enumerate(base.items())}
        r = P.evaluate_overlap(base, tail, P.window_for(tail))
        self.assertTrue(r["O2"])
        self.assertFalse(r["O3"], "10% of days off by 3 ft puts the p95 above 2 ft")
        tw = {d: v - 61.5 for d, v in base.items()}
        r = P.evaluate_overlap(base, tw, P.window_for(tw))
        self.assertFalse(r["O2"] or r["O3"], "a tailwater series 61 ft lower cannot pass")

    def test_overlap_without_matches(self):
        r = P.evaluate_overlap({D0: 1.0}, {D0 + dt.timedelta(days=9): 1.0}, (D0, D0 + dt.timedelta(days=20)))
        self.assertFalse(r["O1"] or r["O2"] or r["O3"])

    def test_short_feed_tie(self):
        rec = series(31, lambda i: 1787.0 + i * 0.01)
        ok = P.evaluate_short(rec, {d: v + 0.03 for d, v in rec.items()})
        self.assertTrue(ok["S1a"])
        self.assertFalse(P.evaluate_short(rec, {d: v + 0.2 for d, v in rec.items()})["S1a"], "median beyond 0.1 ft")
        spike = {d: v for d, v in rec.items()}
        spike[D0] += 0.6
        self.assertFalse(P.evaluate_short(rec, spike)["S1a"], "one day 0.6 ft off breaks the 0.5 ft max")
        self.assertFalse(P.evaluate_short(series(5, lambda i: 1.0), series(5, lambda i: 1.0))["S1a"], "5 days < 20")
        self.assertFalse(P.evaluate_short({}, rec)["S1a"])

    def test_recency(self):
        run = dt.date(2026, 10, 13)
        self.assertTrue(P.evaluate_recency({run - dt.timedelta(days=45): 1.0}, run)["O4"])
        self.assertFalse(P.evaluate_recency({run - dt.timedelta(days=46): 1.0}, run)["O4"])
        self.assertFalse(P.evaluate_recency({}, run)["O4"])

    def test_plausibility(self):
        live = {D0: 6500.0, D0 + dt.timedelta(days=1): 6600.0}
        w = (D0, D0 + dt.timedelta(days=1))
        self.assertTrue(P.plausibility(live, w, 6400.0, 6700.0)["P2"])
        self.assertFalse(P.plausibility(live, w, 6501.5, 6700.0)["P2"])
        self.assertIsNone(P.plausibility(live, w, None, 6700.0)["P2"])

    def test_qa_reproduction_shows_seasonality_inside_one_series(self):
        # a drawdown reservoir: high for a year, low for the last 30 days. The hold-out 'mismatch' appears inside the one series.
        s = series(600, lambda i: 7500.0 if i < 570 else 7410.0)
        q = P.qa_reproduction({D0 + dt.timedelta(days=366 + i): v for i, v in enumerate(s.values())})
        self.assertLess(q["diffFt"], -15)

    def test_read_daily_file_drops_placeholders(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.csv")
            open(p, "w").write("date,ft\n2026-01-01,0.0\n2026-01-02,5123.4\n2026-01-03,\nbad,1\n")
            self.assertEqual(P.read_daily_file(p), {dt.date(2026, 1, 2): 5123.4})

    def test_history_file_mapping(self):
        self.assertTrue(P.hist_file_for({"kind": "riseDaily", "item": "78"}).endswith("rise_78.csv.gz"))
        f = P.hist_file_for({"kind": "cwmsDaily", "office": "MVS", "series": "Lk Shelbyville-Kaskaskia.Elev.Inst.~1Day.0.datman-rev"})
        self.assertTrue(f.endswith("cwms_MVS_Lk_Shelbyville-Kaskaskia.Elev.Inst._1Day.0.datman-rev.csv.gz"))
        self.assertTrue(P.hist_file_for({"kind": "usgsDaily", "site": "1", "param": "62615", "stat": "iv"}).endswith("usgsiv_1_62615.csv.gz"))


def probe_fixture(**over) -> dict:
    t = {"id": "t", "O4": True, "historyLast": "2026-10-11", "staleDays": 2,
         "overlap": {"window": ["a", "b"], "matchedDays": 1095, "O1": True, "O2": True, "O3": True, "medianAbsFt": 0.1, "p95AbsFt": 0.4, "maxAbsFt": 1.0, "medianSignedFt": 0.0},
         "liveWindowRange": {"n": 1095, "min": 5400.0, "max": 5490.0}, "qaReproduction": {}}
    t.update(over)
    return {"tests": [t]}


def spec_fixture(**over) -> dict:
    dec = {"test": "t", "datum": {"relation": "identical-by-construction", "text": "x"},
           "operator": {"fullPoolFt": 5500.0, "minFt": 5300.0, "maxFt": 5520.0, "sources": ["u"]}, "fallback": "NEEDS HUMAN REVIEW", "reason": "r"}
    dec.update(over)
    return {"decision": dec}


class DispositionLogic(unittest.TestCase):
    def test_fixed_only_when_every_gate_passes(self):
        r = D.evaluate_lake("L|ST", spec_fixture(), probe_fixture(), 5500.0)
        self.assertEqual(r["disposition"], "FIXED")
        self.assertTrue(r["reviewRequired"])
        self.assertEqual(r["status"], "MACHINE_VERIFIED_CANDIDATE")
        self.assertEqual(r["datumOffsetFt"], 0.0)

    def test_each_gate_blocks_fixed(self):
        cases = {
            "O1": probe_fixture(overlap={"O1": False, "O2": True, "O3": True}),
            "O2": probe_fixture(overlap={"O1": True, "O2": False, "O3": True}),
            "O3": probe_fixture(overlap={"O1": True, "O2": True, "O3": False}),
            "O4": probe_fixture(O4=False),
            "P2": probe_fixture(liveWindowRange={"n": 3, "min": 289.3, "max": 1787.0}),
        }
        for gate, probe in cases.items():
            r = D.evaluate_lake("L|ST", spec_fixture(), probe, 5500.0)
            self.assertNotEqual(r["disposition"], "FIXED", gate)
            self.assertIn(gate, r["failedCriteria"])
        r = D.evaluate_lake("L|ST", spec_fixture(), probe_fixture(), 5502.5)
        self.assertIn("P1", r["failedCriteria"], "directory full pool 2.5 ft from the operator figure")
        r = D.evaluate_lake("L|ST", spec_fixture(datum={"relation": "fitted-offset", "text": "x"}), probe_fixture(), 5500.0)
        self.assertIn("D1", r["failedCriteria"], "a fitted offset is never a documented datum relation")

    def test_undocumented_operator_range_cannot_be_fixed(self):
        r = D.evaluate_lake("L|ST", spec_fixture(operator={"fullPoolFt": 5500.0, "minFt": None, "maxFt": None}), probe_fixture(), 5500.0)
        self.assertEqual(r["failedCriteria"], ["P2"])
        self.assertEqual(r["disposition"], "NEEDS HUMAN REVIEW")

    def test_access2water_short_feed_cannot_pass_on_one_point(self):
        probe = probe_fixture(a2wTie={"matchedPoints": 1, "diffFt": 0.0})
        r = D.evaluate_lake("L|ST", spec_fixture(shortFeed="a2w"), probe, 5500.0)
        self.assertEqual(r["failedCriteria"], ["S1"])
        self.assertEqual(r["shortFeed"]["matchedDays"], 1)

    def test_nwps_short_feed_uses_the_tie(self):
        good = probe_fixture(s1a={"S1a": True, "matchedDays": 31, "medianAbsFt": 0.0, "maxAbsFt": 0.03})
        bad = probe_fixture(s1a={"S1a": False, "matchedDays": 31})
        self.assertEqual(D.evaluate_lake("L|ST", spec_fixture(shortFeed="nwps"), good, 5500.0)["disposition"], "FIXED")
        self.assertEqual(D.evaluate_lake("L|ST", spec_fixture(shortFeed="nwps"), bad, 5500.0)["failedCriteria"], ["S1"])

    def test_fallback_disposition_comes_from_the_spec(self):
        bad = probe_fixture(O4=False)
        r = D.evaluate_lake("L|ST", spec_fixture(fallback="NO DEFENSIBLE MATCH"), bad, 5500.0)
        self.assertEqual(r["disposition"], "NO DEFENSIBLE MATCH")
        self.assertNotIn("reviewRequired", r)

    def test_p1_p2_helpers(self):
        self.assertTrue(D.p1(6769.0, 6768.0)["P1"], "exactly at the 1.0 ft tolerance")
        self.assertFalse(D.p1(6166.4, 6130.0)["P1"])
        self.assertFalse(D.p1(None, 1.0)["P1"])
        self.assertFalse(D.p2({"n": 0}, 1.0, 2.0)["P2"])


@unittest.skipUnless(os.path.exists(D.OUT), "dispositions not built")
class CommittedDispositions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.load(open(D.OUT))

    def test_all_14_lakes_classified_exactly_once(self):
        self.assertEqual(set(self.doc["lakes"]), set(B.HISTORY_LIVE_MISMATCH))
        self.assertEqual(sum(self.doc["counts"].values()), 14)
        for v in self.doc["lakes"].values():
            self.assertIn(v["disposition"], D.DISPOSITIONS)

    def test_fixed_lakes_are_review_required_candidates_without_offsets(self):
        fixed = [k for k, v in self.doc["lakes"].items() if v["disposition"] == "FIXED"]
        self.assertEqual(sorted(fixed), self.doc["newlyRecovered"])
        for k in fixed:
            v = self.doc["lakes"][k]
            self.assertTrue(v["reviewRequired"])
            self.assertEqual(v["status"], "MACHINE_VERIFIED_CANDIDATE")
            self.assertEqual(v["datumOffsetFt"], 0.0)
            self.assertEqual(v["failedCriteria"], [])
            self.assertLessEqual(v["overlap"]["medianAbsFt"], C.MEDIAN_ABS_FT)
            self.assertLessEqual(v["overlap"]["p95AbsFt"], C.P95_ABS_FT)
            self.assertGreaterEqual(v["overlap"]["matchedDays"], C.MIN_MATCHED_DAYS)

    def test_dispositions_reproduce_from_probe_and_specs(self):
        if not os.path.exists(D.PROBE):
            self.skipTest("probe results not present")
        self.assertEqual(D.main(["--check"]), 0, "run python3 jobs/lake-brain/bindings/build_mismatch14_dispositions.py")

    def test_known_findings(self):
        L = self.doc["lakes"]
        self.assertEqual(L["Buffalo Bill Reservoir|WY"]["fixType"], "live-series-replacement")
        self.assertEqual(L["Buffalo Bill Reservoir|WY"]["correction"]["live"]["station"], "146")
        self.assertEqual(L["Rend Lake|IL"]["disposition"], "NEEDS HUMAN REVIEW")
        self.assertIn("O2", L["Rend Lake|IL"]["failedCriteria"], "0.55 ft > 0.5 ft: the criterion is not relaxed")
        self.assertEqual(L["Bartlett|AZ"]["disposition"], "NO DEFENSIBLE MATCH")
        for a2w in ("Canyon Lake|TX", "Jackson Lake|WY", "Detroit Lake|OR"):
            self.assertIn("S1", L[a2w]["failedCriteria"])


class GeneratorRecoveredPath(unittest.TestCase):
    def test_load_fixed_rejects_lake_outside_the_hold_list(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            json.dump({"lakes": {"Elsewhere|ZZ": {"disposition": "FIXED", "reviewRequired": True, "status": "MACHINE_VERIFIED_CANDIDATE"}}}, open(p, "w"))
            with self.assertRaises(AssertionError):
                B.load_fixed_dispositions(p)

    def test_load_fixed_requires_review_flag(self):
        lake = sorted(B.HISTORY_LIVE_MISMATCH)[0]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            json.dump({"lakes": {lake: {"disposition": "FIXED", "reviewRequired": False, "status": "MACHINE_VERIFIED_CANDIDATE"}}}, open(p, "w"))
            with self.assertRaises(AssertionError):
                B.load_fixed_dispositions(p)
            json.dump({"lakes": {lake: {"disposition": "NEEDS HUMAN REVIEW"}}}, open(p, "w"))
            self.assertEqual(B.load_fixed_dispositions(p), {})
        self.assertEqual(B.load_fixed_dispositions("/nonexistent/x.json"), {})

    def _rec(self):
        return {"status": "MACHINE_VERIFIED", "live": [{"provider": "rise", "station": "152", "series": "152", "datumOffsetFt": 0.0},
                                                         {"provider": "usgs", "station": "9", "series": "00062", "datumOffsetFt": 0.0}],
                "verification": {"probe": {}}}

    def _disp(self, corr=None):
        return {"fixType": "x", "overlap": {"matchedDays": 1}, "operator": {"fullPoolFt": 1.0}, "correction": corr}

    def test_apply_recovery_without_correction_keeps_series_and_status(self):
        r = B.apply_recovery(self._rec(), self._disp())
        self.assertEqual(r["status"], "MACHINE_VERIFIED")
        self.assertEqual(r["live"][0]["station"], "152")
        self.assertTrue(r["recovery"]["reviewRequired"])
        self.assertEqual(r["recovery"]["datumOffsetFt"], 0.0)

    def test_apply_recovery_replaces_series_and_drops_the_replaced_fallback(self):
        corr = {"replaces": {"provider": "rise", "station": "152"},
                "live": {"provider": "rise", "station": "146", "series": "146", "datumOffsetFt": 0.0},
                "history": {"kind": "riseDaily", "item": "146"}, "historyCompleteYears": 73, "historyClass": "SUFFICIENT", "historyFirstYear": 1952,
                "historyNote": "n", "probe": {"lastFt": 1.0}, "evidence": "e"}
        rec = self._rec()
        rec["live"].append({"provider": "rise", "station": "152", "series": "152", "datumOffsetFt": 0.0})
        r = B.apply_recovery(rec, self._disp(corr))
        self.assertEqual([l["station"] for l in r["live"]], ["146", "9"])
        self.assertEqual((r["provider"], r["station"], r["series"]), ("rise", "146", "146"))
        self.assertEqual(r["history"], [{"kind": "riseDaily", "item": "146"}])
        self.assertEqual(r["verification"]["probe"], {"lastFt": 1.0})

    def test_apply_recovery_refuses_a_nonzero_datum_offset(self):
        rec = self._rec()
        rec["live"][0]["datumOffsetFt"] = 0.3
        with self.assertRaises(AssertionError):
            B.apply_recovery(rec, self._disp())

    def test_apply_recovery_refuses_reviewed_status(self):
        rec = self._rec()
        rec["status"] = "REVIEWED"
        with self.assertRaises(AssertionError):
            B.apply_recovery(rec, self._disp())

    @unittest.skipUnless(os.path.exists(os.path.join(DATA, "bindings.proposed.v1.json")), "table not built")
    def test_default_table_never_contains_a_recovered_lake(self):
        main = {b["lakeId"] for b in json.load(open(os.path.join(DATA, "bindings.proposed.v1.json")))["bindings"]}
        ex = {x["lakeId"] for x in json.load(open(os.path.join(DATA, "bindings.proposed.v1.excluded.json")))["excluded"]}
        self.assertEqual(len(main), 196)
        self.assertEqual(main & set(B.HISTORY_LIVE_MISMATCH), set())
        self.assertTrue(set(B.HISTORY_LIVE_MISMATCH) <= ex)

    @unittest.skipUnless(os.path.exists(B.OUT_RECOVERED), "recovered list not built")
    def test_recovered_list_is_separate_machine_verified_and_matches_fixed(self):
        rec = json.load(open(B.OUT_RECOVERED))
        self.assertEqual(rec["schema"], B.RECOVERED_SCHEMA)
        ids = [b["lakeId"] for b in rec["bindings"]]
        self.assertEqual(ids, sorted(B.load_fixed_dispositions()))
        for b in rec["bindings"]:
            self.assertEqual(b["status"], "MACHINE_VERIFIED")
            self.assertTrue(b["recovery"]["reviewRequired"])
            self.assertEqual(b["verification"]["coordinateFlag"], "ok")
        main = {b["lakeId"] for b in json.load(open(os.path.join(DATA, "bindings.proposed.v1.json")))["bindings"]}
        self.assertEqual(set(ids) & main, set())

    def test_held_list_still_blocks_acceptance(self):
        held = load("held_lakes", os.path.join(REPO, "jobs", "lake-brain", "review", "held_lakes.py"))
        self.assertEqual(held.SERIES_MISMATCH, frozenset(B.HISTORY_LIVE_MISMATCH))


if __name__ == "__main__":
    unittest.main()
