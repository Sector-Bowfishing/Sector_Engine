"""The preregistered criterion is frozen: the document hash is pinned, the constants match it, and the analysis refuses to speak below the minimum sample."""
import hashlib
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.dirname(HERE), "runtime")      # brains/fish/runtime (the production package)
sys.path.insert(0, ROOT)
import prereg_analysis as pa   # noqa: E402

DOC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(ROOT))), "docs", "brains", "biological-adoption")
DOC = os.path.join(DOC_DIR, "BIOLOGICAL_VALIDATION_PREREGISTRATION_v1.md")


def obs(i, trip, zone, minutes, shootable, t="2026-05-02T02:00:00Z"):
    return {"observationId": f"o{i}", "tripId": trip, "observerId": "u1", "lakeId": "L|ST", "observedAt": t, "speciesId": "common_carp", "speciesIdConfidence": "CONFIRMED",
            "encountered": shootable > 0, "count": shootable, "shootableCount": shootable, "effortMinutes": minutes, "zone": zone, "observerConfidence": "HIGH"}


PRED = {"predictionId": "p", "lakeId": "L|ST", "speciesId": "common_carp", "predictedAt": "2026-05-01T20:00:00Z", "expected": {"habitat": ["backwaterHabitat"]}}


class FrozenPreregTests(unittest.TestCase):
    def test_document_hash_is_pinned(self):
        want = open(os.path.join(DOC_DIR, "BIOLOGICAL_VALIDATION_PREREGISTRATION_v1.sha256")).read().split()[0]
        self.assertEqual(hashlib.sha256(open(DOC, "rb").read()).hexdigest(), want, "the frozen preregistration was edited: write a v2 file instead")

    def test_constants_match_the_frozen_text(self):
        t = open(DOC).read()
        self.assertEqual(pa.MIN_TRIPS, 30)
        for needle in ("below 30 independent trips", "at least 10 effort-hours", "at least 10 trips that contain both", "at least 1.5", "10,000 resamples", "fixed seed 20261014",
                       "no more than 36 h", "Non-encounters are effort", "common carp, spotted gar, silver carp, longnose gar"):
            self.assertIn(needle, t, needle)
        self.assertEqual((pa.MIN_HOURS_EACH_GROUP, pa.MIN_PAIRED_TRIPS, pa.POINT_ESTIMATE_MIN, pa.BOOTSTRAP_N, pa.SEED, pa.MATCH_WINDOW_H), (10.0, 10, 1.5, 10000, 20261014, 36.0))
        self.assertEqual(pa.CONFIRMATORY_SPECIES, ("common_carp", "spotted_gar", "silver_carp", "longnose_gar"))

    def test_below_minimum_sample_gives_no_verdict_and_no_ratio(self):
        r = pa.analyse([PRED], [obs(1, "t1", "backwaterHabitat", 120, 5), obs(2, "t1", "channelBorder", 120, 0)], "common_carp", "L|ST")
        self.assertEqual((r["status"], r["verdict"]), ("BELOW_MINIMUM_SAMPLE", None))
        self.assertNotIn("ratio", r)
        self.assertTrue(any("independent trips" in x for x in r["reasons"]))

    @staticmethod
    def day(i, hour):
        import datetime as dt
        return (dt.datetime(2026, 5, 1, hour, tzinfo=dt.timezone.utc) + dt.timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def build(self, fav, oth, n_trips=35):
        """n_trips outings; each has a prediction at 20:00 and two zones fished that night (favoured, other) with the given shootable counts."""
        preds = [dict(PRED, predictionId=f"p{i}", predictedAt=self.day(i, 20)) for i in range(n_trips)]
        o = []
        for i in range(n_trips):
            o.append(obs(i * 2, f"t{i}", "backwaterHabitat", 60, fav, self.day(i + 1, 1)))
            o.append(obs(i * 2 + 1, f"t{i}", "channelBorder", 60, oth, self.day(i + 1, 2)))
        return preds, o

    def test_analysis_with_enough_data_is_deterministic_and_applies_the_frozen_rule(self):
        preds, o = self.build(3, 1)
        a = pa.analyse(preds, o, "common_carp", "L|ST", n_boot=500)
        b = pa.analyse(preds, o, "common_carp", "L|ST", n_boot=500)
        self.assertEqual(a, b)                                                           # fixed seed: reproducible
        self.assertEqual(a["status"], "CRITERION_MET")
        self.assertAlmostEqual(a["ratio"], 3.0)
        self.assertGreater(a["interval"][0], 1.0)
        self.assertEqual((a["independentTrips"], a["pairedTrips"]), (35, 35))

    def test_equal_rates_are_not_met_and_a_reverse_effect_is_flagged(self):
        preds, flat = self.build(1, 1)
        r = pa.analyse(preds, flat, "common_carp", "L|ST", n_boot=300)
        self.assertEqual((r["status"], r["verdict"]), ("CRITERION_NOT_MET", "NOT_MET"))
        preds, rev = self.build(1, 3)
        r2 = pa.analyse(preds, rev, "common_carp", "L|ST", n_boot=300)
        self.assertEqual(r2["status"], "CRITERION_NOT_MET")
        self.assertLess(r2["ratio"], 1.0)
        self.assertTrue(r2["reverseEffect"])

    def test_a_good_ratio_below_the_point_estimate_floor_is_not_met(self):
        preds, o = self.build(5, 4)                       # ratio 1.25: interval above 1 but below the frozen 1.5 floor
        r = pa.analyse(preds, o, "common_carp", "L|ST", n_boot=300)
        self.assertEqual(r["status"], "CRITERION_NOT_MET")

    def test_k_comparisons_widens_the_interval(self):
        preds, o = self.build(3, 1)
        one = pa.analyse(preds, o, "common_carp", "L|ST", k_comparisons=1, n_boot=400)
        eight = pa.analyse(preds, o, "common_carp", "L|ST", k_comparisons=8, n_boot=400)
        self.assertGreater(eight["intervalLevel"], one["intervalLevel"])

    def test_group_level_ids_and_a_missing_shootable_count_never_produce_a_ratio(self):
        g = dict(obs(1, "t1", "backwaterHabitat", 60, 3), speciesIdConfidence="GROUP_ONLY", speciesGroup="carp_asian")
        self.assertEqual(pa.matched_rows([PRED], [g], "common_carp", "L|ST"), [])
        miss = dict(obs(2, "t2", "backwaterHabitat", 60, 1)); miss.pop("shootableCount")
        r = pa.analyse([PRED], [miss], "common_carp", "L|ST")
        self.assertEqual(r["status"], "BELOW_MINIMUM_SAMPLE")


if __name__ == "__main__":
    unittest.main()
