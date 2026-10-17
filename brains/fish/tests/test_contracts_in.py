"""Cross-Brain consumption contracts: Temp/Lake sanity, Depth shares, Vegetation habitat state (synthetic fixtures only)."""
import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import contracts_in as ci   # noqa: E402

NOW = dt.datetime(2026, 6, 10, 12, 0, tzinfo=dt.timezone.utc)


def depth_state(mode="shiftOnly", resolvable=False, eff_available=False, age_h=2, shares=(0.2, 0.3, 0.25), stale=False, conf="HIGH"):
    st = {"stateSchema": "sector-brain-depth-state-v1", "effectiveDepth": {"mode": mode, "shiftFt": -1.0, "uncertaintyFt": 0.4, "confidence": conf, "resolvable": resolvable},
          "referenceZones": {"shareUnder3Ft": shares[0], "share3To6Ft": shares[1], "share6To10Ft": shares[2]},
          "freshness": {"stale": stale}, "provenance": {"generatedAt": (NOW - dt.timedelta(hours=age_h)).isoformat()}}
    if eff_available:
        st["effectiveZones"] = {"available": True, "shareUnder3Ft": {"lo": 0.30, "hi": 0.40}, "share3To6Ft": {"lo": 0.25, "hi": 0.35}, "share6To10Ft": {"lo": 0.15, "hi": 0.25}}
    return st


class TempLakeTests(unittest.TestCase):
    def test_implausible_temperature_is_unknown_not_a_signal(self):
        self.assertEqual(ci.sane_temperature(76.1, -0.1), (76.1, -0.1))
        self.assertEqual(ci.sane_temperature(-40, 3), (None, 3.0))
        self.assertEqual(ci.sane_temperature(212, 99), (None, None))
        self.assertEqual(ci.sane_temperature(True, "x"), (None, None))

    def test_lake_trend_vocabulary_is_closed(self):
        self.assertEqual(ci.lake_trend("RISING_RAPIDLY"), "RISING_RAPIDLY")
        self.assertEqual(ci.lake_trend("SURGING"), "UNKNOWN")
        self.assertEqual(ci.lake_trend(None), "UNKNOWN")

    def test_pool_trend_is_not_tributary_discharge(self):
        import features as ft
        i = {"lake": {"status": "PUBLISHED", "values": {"trendState": "RISING_RAPIDLY"}}}
        self.assertEqual(ft.evaluate_features(i)["rapidDischargeIncrease"]["state"], "UNKNOWN")      # pool trend never populates the discharge feature
        self.assertEqual(ft.evaluate_features(i)["risingStage"]["state"], "TRUE")


class NormalizeInputsTests(unittest.TestCase):
    def snap(self, **kw):
        gen = (NOW - dt.timedelta(hours=1)).isoformat()
        s = {"lakeState": {"trendState": "RISING", "provenance": {"generatedAt": gen}},
             "waterTemperature": {"currentTempF": 70.0, "trend24hF": 0.5, "provenance": {"generatedAt": gen}},
             "waterClarity": {"clarityFt": 2.5, "provenance": {"generatedAt": gen}}}
        for k, v in kw.items():
            s[k].update(v)
        return s

    def test_valid_snapshot_passes_through(self):
        import bio_state as bs
        n = bs.normalize_inputs(self.snap(), NOW)
        self.assertEqual(n["waterTemp"]["values"], {"currentTempF": 70.0, "trend24hF": 0.5})
        self.assertEqual(n["lake"]["values"]["trendState"], "RISING")

    def test_implausible_or_unrecognised_values_become_missing_features(self):
        import bio_state as bs
        import features as ft
        n = bs.normalize_inputs(self.snap(waterTemperature={"currentTempF": 500.0}, lakeState={"trendState": "SURGING"}), NOW)
        self.assertNotIn("currentTempF", n["waterTemp"]["values"])
        self.assertNotIn("trendState", n["lake"]["values"])
        f = ft.evaluate_features(n)
        self.assertEqual((f["waterTempBand"]["state"], f["stageTrend"]["state"], f["warmRise"]["state"]), ("UNKNOWN", "UNKNOWN", "UNKNOWN"))


class DepthContractTests(unittest.TestCase):
    def test_unrecognised_stale_or_unknown_depth_is_unknown(self):
        self.assertEqual(ci.normalize_depth(None, NOW)["status"], "NOT_PUBLISHED")
        self.assertEqual(ci.normalize_depth({"stateSchema": "other"}, NOW)["status"], "NOT_PUBLISHED")
        self.assertEqual(ci.normalize_depth(depth_state(stale=True), NOW)["status"], "STALE")
        self.assertEqual(ci.normalize_depth(depth_state(age_h=60), NOW)["status"], "STALE")
        d = ci.normalize_depth(depth_state(mode="unknown"), NOW)
        self.assertIsNone(d["shares"])
        self.assertEqual(ci.depth_availability(d, "LT_0_5M")["state"], "UNKNOWN")

    def test_reference_shares_used_only_when_level_is_not_resolvably_different(self):
        ok = ci.normalize_depth(depth_state(resolvable=False), NOW)
        self.assertEqual(ok["sharesBasis"], "reference(level not resolvably different)")
        moved = ci.normalize_depth(depth_state(resolvable=True), NOW)
        self.assertIsNone(moved["shares"])                                            # reference edges no longer describe today's water
        self.assertEqual(ci.depth_availability(moved, "M0_5_1_5")["state"], "UNKNOWN")
        eff = ci.normalize_depth(depth_state(resolvable=True, eff_available=True), NOW)
        self.assertEqual(eff["sharesBasis"], "effective")

    def test_depth_availability_is_bounded_never_a_point(self):
        d = ci.normalize_depth(depth_state(shares=(0.2, 0.3, 0.25)), NOW)
        a = ci.depth_availability(d, "LT_0_5M")
        self.assertEqual((a["state"], a["lower"], a["upper"]), ("BOUNDED", 0.0, 0.2))
        b = ci.depth_availability(d, "M0_5_1_5")
        self.assertEqual((b["lower"], b["upper"]), (0.0, 0.5))
        c = ci.depth_availability(d, "M1_5_3")
        self.assertEqual((c["lower"], c["upper"]), (0.0, 0.55))
        g = ci.depth_availability(d, "GT_3M")
        self.assertAlmostEqual(g["lower"], 0.25, places=4)                            # 1 - (0.2+0.3+0.25)
        self.assertAlmostEqual(g["upper"], 0.5, places=4)
        self.assertEqual(ci.depth_availability(d, "BOTTOMLESS")["state"], "UNKNOWN")

    def test_effective_zone_bounds_propagate(self):
        d = ci.normalize_depth(depth_state(resolvable=True, eff_available=True), NOW)
        a = ci.depth_availability(d, "M0_5_1_5")
        self.assertAlmostEqual(a["upper"], 0.75, places=4)                            # u3.hi 0.40 + m36.hi 0.35
        self.assertEqual(a["basis"], "effective")

    def test_low_confidence_depth_is_degraded(self):
        self.assertEqual(ci.normalize_depth(depth_state(conf="LOW"), NOW)["status"], "DEGRADED")


class VegetationContractTests(unittest.TestCase):
    def cell(self, **kw):
        c = {"class": "SUBMERGED", "density": "MODERATE", "tier": "OBSERVED_SATELLITE", "observedAt": (NOW - dt.timedelta(days=10)).isoformat(), "confidence": "MEDIUM"}
        c.update(kw)
        return c

    def test_observed_vegetation_is_true_and_clear_is_false(self):
        self.assertEqual(ci.vegetation_habitat_state(self.cell(), "shallowVegetatedHabitat", NOW)["state"], "TRUE")
        self.assertEqual(ci.vegetation_habitat_state(self.cell(**{"class": "NONE_SIGNIFICANT", "density": "NONE"}), "shallowVegetatedHabitat", NOW)["state"], "FALSE")
        self.assertEqual(ci.vegetation_habitat_state(self.cell(**{"class": "FLOODED_TERRESTRIAL"}), "floodedVegetation", NOW)["state"], "TRUE")
        self.assertEqual(ci.vegetation_habitat_state(self.cell(), "floodedVegetation", NOW)["state"], "FALSE")           # submerged plants are not flooded terrestrial

    def test_models_priors_refusals_and_stale_observations_are_never_presence(self):
        for kw in ({"tier": "POTENTIAL_HABITAT"}, {"tier": "SEASONAL_EXPECTATION"}, {"tier": "PRIOR_MAPPED"}, {"class": "UNKNOWN"}, {"class": "KELP"},
                   {"observedAt": (NOW - dt.timedelta(days=200)).isoformat()}, {"observedAt": (NOW + dt.timedelta(days=3)).isoformat()}, {"observedAt": None}, {"density": None}):
            self.assertEqual(ci.vegetation_habitat_state(self.cell(**kw), "shallowVegetatedHabitat", NOW)["state"], "UNKNOWN", kw)
        self.assertEqual(ci.vegetation_habitat_state(None, "shallowVegetatedHabitat", NOW)["state"], "UNKNOWN")
        self.assertEqual(ci.vegetation_habitat_state(self.cell(), "backwaterHabitat", NOW)["state"], "UNKNOWN")           # not vegetation-owned

    def test_age_limit_is_an_explicit_engineering_default(self):
        old = self.cell(observedAt=(NOW - dt.timedelta(days=30)).isoformat())
        self.assertEqual(ci.vegetation_habitat_state(old, "shallowVegetatedHabitat", NOW)["state"], "TRUE")
        self.assertEqual(ci.vegetation_habitat_state(old, "shallowVegetatedHabitat", NOW, max_age_days=20)["state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
