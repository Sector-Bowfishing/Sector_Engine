#!/usr/bin/env python3
"""Tests for build_bindings_table.py and scripts/generate-lake-bindings.py.

    python3 -m unittest discover -s jobs/lake-brain/bindings -p 'test_*.py'

Unit tests need no data. The table tests read the committed bindings.proposed.v1.json (and, when the research checkout is present,
re-derive eligibility from it)."""
from __future__ import annotations

import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(REPO, "jobs", "lake-brain", "data")


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = load("build_bindings_table", os.path.join(HERE, "build_bindings_table.py"))
G = load("generate_lake_bindings", os.path.join(REPO, "scripts", "generate-lake-bindings.py"))


class UnitTests(unittest.TestCase):
    def test_time_zones(self):
        self.assertEqual(B.timezone_for("AL", 34.4, -86.3)[0], "America/Chicago")
        self.assertEqual(B.timezone_for("SC", 34.5, -82.8)[0], "America/New_York")
        self.assertEqual(B.timezone_for("TN", 36.2, -83.9)[0], "America/New_York", "East Tennessee")
        self.assertEqual(B.timezone_for("TN", 35.0, -88.2)[0], "America/Chicago")
        self.assertEqual(B.timezone_for("AZ", 34.4, -114.3)[0], "America/Phoenix")
        self.assertEqual(B.timezone_for("ID", 48.5, -116.9)[0], "America/Los_Angeles", "Priest Lake is Pacific")
        self.assertEqual(B.timezone_for("KY", 36.9, -88.1)[0], "America/Chicago", "Kentucky Lake")
        self.assertEqual(B.timezone_for("FL", 30.7, -85.9)[0], "America/Chicago")

    def test_interval_and_cadence(self):
        self.assertEqual(B.interval_minutes("Bankhead.Elev.Inst.15Minutes.0.Raw-USGS"), 15)
        self.assertEqual(B.interval_minutes("Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS"), 1440)
        self.assertEqual(B.interval_minutes("X.Elev.Inst.~1Day.0.MRS"), 1440)
        self.assertEqual(B.live_cadence("Bankhead.Elev.Inst.15Minutes.0.Raw-USGS"), 60, "never finer than hourly")
        self.assertEqual(B.live_cadence("X.Elev.Inst.1Day.0.v"), 1440)

    def test_history_extension_components(self):
        comps, bad = B.parse_hx_components("hads:PSLI1; usgs:12393000_00065_32400_dv(+2434.40ft over 68d, sd 0.05)")
        self.assertEqual(bad, [])
        self.assertEqual(comps[0], {"kind": "hadsDaily", "lid": "PSLI1", "pe": "HP", "offsetFt": 0.0})
        self.assertEqual(comps[1]["kind"], "usgsDaily")
        self.assertEqual((comps[1]["site"], comps[1]["param"], comps[1]["stat"], comps[1]["offsetFt"]), ("12393000", "00065", "32400", 2434.40))
        comps, bad = B.parse_hx_components("rvd:NKJT1")
        self.assertEqual(comps, [])
        self.assertEqual(bad, ["rvd:NKJT1"], "RVDHUN text is not an admitted history source")
        comps, bad = B.parse_hx_components("cwms:NWDP_HOPI.Elev-Lake.Inst.1Hour.0.GOES-REV; cwms:NWDP_HOPI.Elev-Lake.Inst.1Hour.0.NWSRADIO-REV(+0)")
        self.assertEqual([c["office"] for c in comps], ["NWDP", "NWDP"])
        self.assertEqual(comps[0]["series"], "HOPI.Elev-Lake.Inst.1Hour.0.GOES-REV")

    def test_exclusion_lists(self):
        for p in ("nipsco", "njwsa", "duke", "wps-hydro", "alliant", "srp", "cnppid", "nppd", "utahlake", "aep", "eccc", "mncsg", "sjrwmd", "nhdes"):
            self.assertIn(p, B.UNDOCUMENTED)
            self.assertNotIn(p, B.ALLOW_PROVIDERS)
        self.assertEqual(len(B.HISTORY_LIVE_MISMATCH), 14)
        self.assertTrue(B.ALLOW_PROVIDERS >= {"tva", "cwms", "cwms-saw", "usgs", "a2w", "rise", "nwps", "twdb"})

    def test_generator_refuses_unknown_accepted_ids(self):
        # accepted_batch.json formats
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "accepted_batch.json")
            old = G.ACCEPTED
            try:
                G.ACCEPTED = p
                self.assertEqual(G.load_accepted(), ([], None), "a missing file is an EMPTY list")
                json.dump(["B|ST", "A|ST"], open(p, "w"))
                self.assertEqual(G.load_accepted(), (["A|ST", "B|ST"], None))
                json.dump({"lakeIds": [{"lakeId": "A|ST"}], "reviewedAt": "2026-10-20"}, open(p, "w"))
                self.assertEqual(G.load_accepted(), (["A|ST"], "2026-10-20"))
                json.dump(["Nowhere|ZZ"], open(p, "w"))
                with self.assertRaises(SystemExit):
                    G.render()
            finally:
                G.ACCEPTED = old


@unittest.skipUnless(os.path.exists(os.path.join(DATA, "bindings.proposed.v1.json")), "table not built")
class TableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.load(open(os.path.join(DATA, "bindings.proposed.v1.json")))
        cls.ex = json.load(open(os.path.join(DATA, "bindings.proposed.v1.excluded.json")))
        cls.rows = {b["lakeId"]: b for b in cls.doc["bindings"]}

    def test_nothing_is_reviewed(self):
        self.assertEqual({b["status"] for b in self.rows.values()}, {"MACHINE_VERIFIED"})

    def test_strict_rows_only(self):
        for b in self.rows.values():
            v = b["verification"]
            self.assertEqual(v["criteriaVersion"], "binding-review-v1")
            self.assertIn(v["wave"], ("w1", "w2-v1"))
            self.assertIn(v["researchStatus"], ("VERIFIED", "VERIFIED_CORROBORATED"))
            self.assertFalse(any("v1.1" in c for c in v["checksPassed"]))
            self.assertEqual(v["coordinateFlag"], "ok")
            self.assertIn(b["researchProvider"], B.ALLOW_PROVIDERS)
            self.assertNotIn(b["researchProvider"], B.UNDOCUMENTED)
            self.assertIn(b["provider"], B.ADAPTER_PROVIDERS)
            for l in b["live"]:
                self.assertIn(l["provider"], B.ADAPTER_PROVIDERS)
                if l["provider"] == "usgs":
                    self.assertIn(l["series"], B.ELEV_USGS_PARAMS)

    def test_decisions(self):
        for lake in ("Clinton Lake|IL", "Red Lake|MN", "Lake Shafer|IN", "Bartlett|AZ", "Lake Taneycomo|MO", "Rend Lake|IL"):
            self.assertNotIn(lake, self.rows)
        ex = {x["lakeId"]: x for x in self.ex["excluded"]}
        for lake in B.HISTORY_LIVE_MISMATCH:
            self.assertIn(lake, ex)
            self.assertIn("history/live series mismatch >15 ft - hold pending datum resolution", [r["detail"] for r in ex[lake]["reasons"]])
        self.assertEqual(sum(1 for x in ex.values() if any(r["code"] == "flagged-wave1" for r in x["reasons"])), 57)
        self.assertEqual(set(self.rows) & set(ex), set())
        for x in ex.values():
            self.assertTrue(x["reasons"], x["lakeId"])

    def test_counts_are_consistent(self):
        c = self.doc["counts"]
        self.assertEqual(c["eligible"], len(self.rows))
        self.assertEqual(sum(c["byProvider"].values()), len(self.rows))
        self.assertEqual(c["excludedResearchBound"], self.ex["count"])
        self.assertEqual(sum(c["excludedByPrimaryReason"].values()), self.ex["count"])
        self.assertEqual(len(self.rows) + self.ex["count"], 427, "every research-bound lake is either proposed or excluded")

    def test_pilots_are_reproduced(self):
        self.assertEqual(len(self.doc["pilotReproduction"]), 5)
        for p in self.doc["pilotReproduction"]:
            self.assertTrue(p["matches"])

    def test_plan_evidence_is_strict_and_verified(self):
        n = 0
        for b in self.rows.values():
            p = b["plan"]
            if not p:
                continue
            n += 1
            self.assertTrue(p["verifiedMatch"])
            self.assertTrue(p["planStrict"] or p["floodStrict"])
            roles = {l["role"] for l in p["levels"]}
            if "zoneTop" in roles or "zoneBottom" in roles:
                self.assertTrue({"zoneTop", "zoneBottom"} <= roles, f"{b['lakeId']}: a zone needs both edges")
            for l in p["levels"]:
                if l["role"] == "guideCurve":
                    self.assertTrue(l["seasonal"], f"{b['lakeId']}: a guide curve is seasonal")
                if l["kind"] == "static":
                    self.assertIsNotNone(l["valueFt"])
        self.assertGreater(n, 50)

    def test_generated_swift_is_current(self):
        swift = os.path.join(REPO, "Sources", "SectorEngine", "LakeBrain", "LakeSourceBindingsGenerated.swift")
        self.assertEqual(open(swift).read(), G.render(), "run python3 scripts/generate-lake-bindings.py")

    def test_table_is_reproducible(self):
        if not os.path.exists(B.Inputs().files["verified_bindings_v2.csv"]):
            self.skipTest("research inputs not present")
        self.assertEqual(B.main(["--check"]), 0, "run python3 jobs/lake-brain/bindings/build_bindings_table.py")


if __name__ == "__main__":
    unittest.main()
