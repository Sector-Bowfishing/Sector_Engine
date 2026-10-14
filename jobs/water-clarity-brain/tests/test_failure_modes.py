"""Water Clarity Brain: failure, refusal and no-op behaviour (stdlib unittest; no network).

Covers the honesty cases the readiness campaign requires: future timestamps, bad units,
duplicate scenes, partial dependency failure, unchanged-input fingerprint and its limits."""
import copy
import datetime as dt
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ["CLARITY_PRIVATE_CATALOG"] = os.path.join(HERE, "fixtures", "catalog.overlay.example.json")
import clarity_brain as cb  # noqa: E402

NOW = dt.datetime(2026, 10, 12, 6, 30, tzinfo=dt.timezone.utc)
fx = lambda n: json.load(open(os.path.join(HERE, "fixtures", n)))
GUNT, LATEST, META = fx("engine_guntersville_rain_decay.json"), fx("bucket_guntersville_latest.json"), fx("bucket_guntersville_meta.json")


def sat_at(now=NOW, **summary):
    latest = copy.deepcopy(LATEST)
    latest["summary"].update(summary)
    return cb.satellite_evidence(latest, META, True, 16, now)


class Refusals(unittest.TestCase):
    def test_future_observation_is_invalid_not_fresh(self):
        s = LATEST["summary"]
        before = dt.datetime.fromisoformat(s["time"].replace("Z", "+00:00")) - dt.timedelta(days=3)
        sat = cb.satellite_evidence(LATEST, META, True, 16, before)
        self.assertEqual(sat["status"], "INVALID")
        self.assertEqual(sat["reasonCode"], "OBSERVATION_IN_FUTURE")
        self.assertNotIn("visibilityAtMedianFnu", sat)
        self.assertIn("satelliteInvalid:OBSERVATION_IN_FUTURE", cb.quality_flags(cb.engine_estimate(GUNT, "x"), sat))

    def test_unparseable_time_is_invalid(self):
        sat = sat_at(time="not-a-time", date=None)
        self.assertEqual(sat["status"], "INVALID")

    def test_bad_turbidity_units_are_refused(self):
        for bad in (-3.0, float("nan"), float("inf"), 1e9, "4.2", True):
            with self.subTest(p50=bad):
                sat = sat_at(fnuP50=bad)
                self.assertEqual(sat["status"], "INVALID", bad)
                self.assertEqual(sat["reasonCode"], "TURBIDITY_OUT_OF_RANGE")

    def test_invalid_satellite_never_marks_satellite_available(self):
        sat = sat_at(fnuP50=-1.0)
        lake = {"id": "Guntersville|AL"}
        prof = cb.build_profile(lake, cb.engine_estimate(GUNT, lake["id"]), sat, True, NOW)
        self.assertFalse(prof["satelliteAvailable"])
        self.assertFalse(prof["spatialModelSupported"])

    def test_state_still_builds_when_satellite_invalid(self):
        sat = sat_at(fnuP50=-1.0)
        est = cb.engine_estimate(GUNT, "Guntersville|AL")
        st = cb.build_state("Guntersville|AL", est, sat, [], None, NOW, "rev")
        self.assertEqual(st["satellite"]["status"], "INVALID")
        self.assertFalse(st["mapLayerAvailable"])


class Fingerprint(unittest.TestCase):
    def fp(self, now=NOW, cond=GUNT, **summary):
        est = cb.engine_estimate(cond, "Guntersville|AL")
        latest = copy.deepcopy(LATEST)
        latest["summary"].update(summary)
        sat = cb.satellite_evidence(latest, META, True, 16, now)
        layers, _ = cb.map_layers(latest, META)
        return cb.input_fingerprint(est, sat, layers, "rev1")

    def test_stable_as_time_passes(self):
        self.assertEqual(self.fp(NOW), self.fp(NOW + dt.timedelta(hours=5)))

    def test_changes_on_new_scene(self):
        self.assertNotEqual(self.fp(), self.fp(date="2026-10-13", time="2026-10-13T16:40:00Z"))

    def test_changes_on_new_turbidity(self):
        self.assertNotEqual(self.fp(), self.fp(fnuP50=LATEST["summary"]["fnuP50"] + 1))

    def test_changes_when_scene_ages_out(self):
        self.assertNotEqual(self.fp(NOW), self.fp(NOW + dt.timedelta(days=30)))

    def test_changes_with_engine_estimate(self):
        c = copy.deepcopy(GUNT)
        c["clarityVisibility"]["centralFt"] = c["clarityVisibility"]["centralFt"] + 0.5
        self.assertNotEqual(self.fp(), self.fp(cond=c))

    def test_duplicate_scene_listing_does_not_change_fingerprint(self):
        a = self.fp()
        est = cb.engine_estimate(GUNT, "x")
        latest = copy.deepcopy(LATEST)
        pas = copy.deepcopy(META)
        sat = cb.satellite_evidence(latest, pas, True, 16, NOW)
        sat2 = dict(sat, sceneIds=list(sat.get("sceneIds") or []))
        layers, _ = cb.map_layers(latest, META)
        self.assertEqual(cb.input_fingerprint(est, sat, layers, "rev1"), cb.input_fingerprint(est, sat2, layers, "rev1"))
        self.assertEqual(a, cb.input_fingerprint(cb.engine_estimate(GUNT, "Guntersville|AL"), sat, layers, "rev1"))

    def test_noop_writes_are_small_and_leaf_only(self):
        w = cb.noop_writes("Guntersville|AL", "abc", NOW)
        self.assertLess(len(json.dumps(w)), 2000)
        self.assertFalse(any(k.endswith("/states/waterClarity") or k.endswith("/profiles/waterClarity") for k in w))
        self.assertFalse(w["/lakeFleet/Guntersville_AL/slots/waterClarity/stale"])

    def test_state_and_slot_carry_fingerprint(self):
        est = cb.engine_estimate(GUNT, "Guntersville|AL")
        sat = cb.satellite_evidence(LATEST, META, True, 16, NOW)
        st = cb.build_state("Guntersville|AL", est, sat, [], None, NOW, "rev1")
        w = cb.lake_writes("Guntersville|AL", None, st, NOW)
        self.assertEqual(w["/lakeFleet/Guntersville_AL/slots/waterClarity"]["inputFingerprint"], st["inputFingerprint"])


if __name__ == "__main__":
    unittest.main()
