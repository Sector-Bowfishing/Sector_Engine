#!/usr/bin/env python3
"""Tests for twdb_dryrun.py (the Python twin of the Swift TWDB adapter), the TWDB support in build_bindings_table.py /
scripts/generate-lake-bindings.py, and the invariants of the committed dry run.

    python3 -m unittest discover -s jobs/lake-brain/bindings -p 'test_*.py'

Fixtures are the recorded responses the Swift tests use (Tests/SectorEngineTests/Fixtures/TWDB). No network."""
from __future__ import annotations

import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FIX = os.path.join(REPO, "Tests", "SectorEngineTests", "Fixtures", "TWDB")
DATA = os.path.join(REPO, "jobs", "lake-brain", "data")


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


D = load("twdb_dryrun", os.path.join(HERE, "twdb_dryrun.py"))
B = load("build_bindings_table", os.path.join(HERE, "build_bindings_table.py"))
G = load("generate_lake_bindings", os.path.join(REPO, "scripts", "generate-lake-bindings.py"))


def fx(name: str) -> str:
    with open(os.path.join(FIX, name), errors="replace") as f:
        return f.read()


class ParseTests(unittest.TestCase):
    def test_recorded_thirty_day_file(self):
        p = D.parse_file(fx("amistad-30day.csv"), "NGVD29")
        self.assertEqual((p["reservoir"], p["datum"], len(p["days"])), ("Amistad Reservoir", "NGVD29", 31))
        self.assertEqual(p["days"][-1], ("2026-10-13", 1059.79))

    def test_datum_label_must_match(self):
        self.assertEqual(D.parse_file(fx("travis-30day.csv"))["datum"], "NAVD88 +0.6")
        with self.assertRaisesRegex(D.TWDBError, "is not the binding's datum"):
            D.parse_file(fx("travis-30day.csv"), "NGVD29")
        D.parse_file(fx("travis-30day.csv"), "navd88 +0.6")
        with self.assertRaisesRegex(D.TWDBError, "NGVD29 -43.3"):
            D.parse_file(fx("elephant-butte-2026-glitch.csv"), "NGVD29")

    def test_unit_html_empty(self):
        meters = fx("amistad-30day.csv").replace("water_level: feet above vertical datum", "water_level: meters above vertical datum")
        with self.assertRaisesRegex(D.TWDBError, "not feet"):
            D.parse_file(meters, "NGVD29")
        with self.assertRaisesRegex(D.TWDBError, "not a TWDB CSV"):
            D.parse_file(fx("not-found.html"))
        with self.assertRaisesRegex(D.TWDBError, "not a TWDB CSV"):
            D.parse_file("")

    def test_blank_and_zero_rows_are_dropped(self):
        c = D.parse_file(fx("canyon-blank-rows.csv"), "NGVD29")
        self.assertEqual((c["days"][0][0], len(c["days"]), c["blank"]), ("1988-10-01", 5, 6))
        s = D.parse_file(fx("sam-rayburn-1988-zeros.csv"), "NGVD29")
        self.assertTrue(all(v > 0 for _, v in s["days"]))
        self.assertGreater(s["nonPositive"], 0)

    def test_glitch_runs_match_the_swift_expectations(self):
        a = D.parse_file(fx("amistad-2008-glitch.csv"), "NGVD29")
        self.assertNotIn("2008-11-30", [d for d, _ in a["days"]])
        self.assertTrue(all(v > 1100 for _, v in a["days"]))
        e = D.parse_file(fx("elephant-butte-2026-glitch.csv"), "NGVD29 -43.3")
        dates = [d for d, _ in e["days"]]
        for gone in ("2026-09-08", "2026-09-09", "2026-09-10"):
            self.assertNotIn(gone, dates)
        self.assertIn("2026-09-07", dates)
        self.assertEqual(dates[-1], "2026-10-13")
        c = D.parse_file(fx("caddo-2012-spike.csv"), "NGVD29")
        self.assertNotIn("2012-10-22", [d for d, _ in c["days"]])
        self.assertEqual(len(c["days"]), 13)

    def test_despike_edges(self):
        ramp = D.despike([("2026-01-01", 619.27), ("2026-01-02", 675.65), ("2026-01-03", 697.0), ("2026-01-04", 698.0)])
        self.assertEqual([v for _, v in ramp], [619.27, 675.65, 697.0, 698.0])
        held = D.despike([("2026-01-01", 100.0), ("2026-01-02", 100.1), ("2026-01-03", 130.0)])
        self.assertEqual([d for d, _ in held], ["2026-01-01", "2026-01-02"])
        confirmed = D.despike([("2026-01-01", 100.0), ("2026-01-02", 100.1), ("2026-01-03", 130.0), ("2026-01-04", 131.0)])
        self.assertEqual(len(confirmed), 4)
        four = D.despike([("2026-01-01", 100), ("2026-01-02", 140), ("2026-01-03", 141), ("2026-01-04", 140), ("2026-01-05", 139),
                          ("2026-01-06", 101), ("2026-01-07", 101.5)])
        self.assertEqual(len(four), 7, "a four day run is not a glitch")
        # a gap in the dates breaks adjacency: the lone point is not confirmed by neighbours that are days away
        gap = D.despike([("2026-01-01", 100.0), ("2026-01-02", 140.0), ("2026-01-05", 100.5), ("2026-01-06", 100.6)])
        self.assertEqual(len(gap), 4)

    def test_headerless_file_needs_the_one_year_file(self):
        with self.assertRaisesRegex(D.TWDBError, "no vertical datum"):
            D.parse_file(fx("possum-kingdom-headerless.csv"), "NGVD29")
        h = D.parse_file(fx("possum-kingdom-headerless.csv"), "NGVD29", allow_headerless=True)
        y = D.parse_file(fx("possum-kingdom-1year.csv"), "NGVD29")
        self.assertTrue(h["headerless"])
        self.assertTrue(D.corroborates(h["days"], y["days"]))
        shifted = [(d, v + 1.0) for d, v in y["days"]]
        self.assertFalse(D.corroborates(h["days"], shifted))
        self.assertFalse(D.corroborates(h["days"], y["days"][:50]), "fewer than 200 shared days")

    def test_complete_years(self):
        days = [(f"2024-{m:02d}-{d:02d}", 1.0) for m in range(1, 13) for d in range(1, 27)]
        self.assertEqual(D.complete_years(days, "2026-10-13"), 0, "312 days is below 90 % of 366")
        import datetime as dt
        full = [((dt.date(2024, 1, 1) + dt.timedelta(days=i)).isoformat(), 1.0) for i in range(366)]
        self.assertEqual(D.complete_years(full, "2026-10-13"), 1)
        self.assertEqual(D.complete_years(full, "2024-10-13"), 0, "the current year never counts")


class MatchTests(unittest.TestCase):
    def test_slug_and_names(self):
        self.assertEqual(D.slug_of("CedarCreek"), "cedar-creek")
        self.assertEqual(D.slug_of("Amistad"), "amistad")
        self.assertEqual(D.slug_of("PossumKingdom"), "possum-kingdom")
        self.assertEqual(D.norm_name("Falcon Reservoir"), D.norm_name("Falcon Lake"))
        self.assertEqual(D.norm_name("Elephant Butte Lake"), D.norm_name("Elephant Butte Reservoir"))
        self.assertNotEqual(D.norm_name("Caddo Lake"), D.norm_name("Cross Lake"))

    def test_match_needs_name_and_distance(self):
        recent = json.load(open(os.path.join(FIX, "recent-conditions-excerpt.json")))
        directory = [
            {"id": "Amistad Reservoir|TX", "name": "Amistad Reservoir", "lat": 29.5, "lon": -101.15, "state": "TX", "fullPoolFt": 1117},
            {"id": "Lake Travis|TX", "name": "Lake Travis", "lat": 30.42, "lon": -97.92, "state": "TX", "fullPoolFt": 681},
            {"id": "Far Away Amistad|XX", "name": "Amistad Reservoir", "lat": 45.0, "lon": -100.0, "state": "XX", "fullPoolFt": 1},
            {"id": "Other Lake|TX", "name": "Other Lake", "lat": 29.5, "lon": -101.15, "state": "TX", "fullPoolFt": 1},
        ]
        m = D.match_directory(directory, recent)
        self.assertEqual({x["lake"]["id"]: x["slug"] for x in m}, {"Amistad Reservoir|TX": "amistad", "Lake Travis|TX": "travis"})


class TableSupportTests(unittest.TestCase):
    def test_default_table_is_untouched_by_twdb_support(self):
        proposed = json.load(open(os.path.join(DATA, "bindings.proposed.v1.json")))["bindings"]
        self.assertGreater(len(proposed), 100, "sanity: the table is loaded")
        self.assertEqual([b["lakeId"] for b in proposed if b["provider"] == "twdb" or any(l["provider"] == "twdb" for l in b["live"])], [])
        self.assertEqual([b["lakeId"] for b in proposed if any(h["kind"] == "twdbDaily" for h in b["history"])], [])
        self.assertFalse(os.path.exists(os.path.join(DATA, "accepted_batch.json")))
        excluded = {e["lakeId"]: e for e in json.load(open(os.path.join(DATA, "bindings.proposed.v1.excluded.json")))["excluded"]}
        for lake in ("Amistad Reservoir|TX", "Falcon Lake|TX"):
            self.assertEqual(excluded[lake]["researchProvider"], "twdb")
            self.assertEqual(excluded[lake]["primaryReason"], "post-hoc", "still excluded: eligibility rules are unchanged")
        self.assertIn("twdb", B.ADAPTER_PROVIDERS)
        self.assertIn("twdb", G.ADAPTER_PROVIDERS)

    def test_live_ref_and_history_source_for_a_twdb_row(self):
        row = {"provider": "twdb", "station": "CedarCreek", "series_or_param": "water_level", "capability_class": "DIRECT_LAKE_GAUGE"}
        ref = B.live_ref_for(None, row, {})
        self.assertEqual((ref["provider"], ref["station"], ref["series"], ref["cadenceMin"], ref["lagMin"]),
                         ("twdb", "cedar-creek", "water_level@NGVD29", 1440, 1440))
        self.assertIsNone(B.live_ref_for(None, {**row, "station": "NoSuchReservoir"}, {}))
        src, why = B.parse_hist_series(None, "twdb:cedar-creek", row, {})
        self.assertEqual(src, {"kind": "twdbDaily", "slug": "cedar-creek", "datum": "NGVD29", "offsetFt": 0.0})
        self.assertIsNone(B.parse_hist_series(None, "twdb:nowhere", row, {})[0])

    def test_generator_carries_a_twdb_record_into_the_runtime_shape(self):
        rec = {"lakeId": "X Lake|TX", "capability": "DIRECT_LAKE_GAUGE", "timeZone": "America/Chicago",
               "live": [D.twdb_live_ref("cedar-creek", "NGVD29")],
               "history": [{**D.twdb_history_source("cedar-creek", "NGVD29"), "note": "dropped"}],
               "historyCompleteYears": 29, "historyClass": "SUFFICIENT",
               "verification": {"criteriaVersion": "binding-review-v1", "researchStatus": "VERIFIED", "wave": "w1", "checksPassed": ["R1"], "probedAt": "t"}}
        c = G.compact(rec)
        self.assertEqual(c["live"][0]["provider"], "twdb")
        self.assertEqual(c["live"][0]["series"], "water_level@NGVD29")
        self.assertEqual(c["history"], [{"kind": "twdbDaily", "slug": "cedar-creek", "datum": "NGVD29"}])
        rec["live"][0]["provider"] = "nipsco"
        with self.assertRaises(AssertionError):
            G.compact(rec)


class TermsGateTests(unittest.TestCase):
    def test_fetch_is_disabled_without_the_env_var(self):
        saved = os.environ.pop("SECTOR_TWDB_TERMS_OK", None)
        try:
            with self.assertRaises(SystemExit) as cm:
                D.main(["--fetch"])
            self.assertIn("robots.txt", str(cm.exception))
            self.assertIn("Disallow: *.csv", str(cm.exception))
        finally:
            if saved is not None:
                os.environ["SECTOR_TWDB_TERMS_OK"] = saved


class CommittedDryRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.load(open(os.path.join(HERE, "twdb_dryrun.v1.json")))

    def test_summary_invariants(self):
        s = self.doc["summary"]
        lakes = self.doc["lakes"]
        self.assertEqual(s["directoryLakes"], 621)
        self.assertEqual(s["directoryLakesMatched"], len(lakes))
        self.assertEqual(s["texasDirectoryLakes"], 15)
        self.assertEqual(s["texasDirectoryLakesMatched"], sum(1 for x in lakes if x["lakeId"].endswith("|TX")))
        self.assertEqual(s["twdbPrimaryRowsInPublishedTable"], [])
        self.assertEqual(s["newTwdbPrimaryCandidatesUnderUnchangedRules"], [], "TWDB-primary rows exist only as post-hoc / flagged research rows")
        for x in lakes:
            self.assertIn(x["role"], ("none-today", "backup-and-history"))
            if x["role"] == "backup-and-history":
                self.assertEqual(x["table"]["state"], "proposed")
                self.assertEqual(x["proposedAdditions"]["liveFallback"]["provider"], "twdb")
            else:
                self.assertIsNone(x["proposedAdditions"])
            self.assertTrue(x["fileHeaderMatchesName"], x["lakeId"])
        self.assertEqual(sorted(s["proposedLiveRelayFallbacks"]), sorted(x["lakeId"] for x in lakes if x["role"] == "backup-and-history"))
        self.assertTrue(set(s["proposedHistoryAdditions"]) <= set(s["proposedLiveRelayFallbacks"]))

    def test_thresholds_are_the_pre_registered_ones(self):
        t = self.doc["thresholds"]
        self.assertEqual((t["glitchFt"], t["continuityFt"], t["liveAgreeFt"], t["poolAgreeFt"], t["completeYearShare"]), (15.0, 15.0, 0.25, 2.0, 0.9))

    def test_offline_rebuild_matches_the_committed_files(self):
        if not os.path.isdir(D.RAW) or not os.path.exists(os.path.join(D.DATA, "directory_lakes_2026-10-13.json")):
            self.skipTest("raw TWDB files / research data not present")
        doc = D.build()
        self.assertEqual(json.dumps(doc, indent=1, sort_keys=True) + "\n", open(D.OUT_JSON).read())
        self.assertEqual(D.to_csv(doc), open(D.OUT_CSV).read())


if __name__ == "__main__":
    unittest.main()
