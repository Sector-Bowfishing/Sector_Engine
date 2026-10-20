"""Pilot evaluation: consumes real-shaped specialist states, keeps provenance, degrades safely, invents nothing."""
import copy
import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "runtime"))   # brains/sector-intelligence/runtime
import brain_platform as bp            # noqa: E402
import evaluation as ev                # noqa: E402
import sector_intelligence_brain as sib  # noqa: E402
from test_sector_intelligence_brain import NOW, build, real_catalog, upstream, reg, SERVICE, LINEAGE  # noqa: E402

GEN = bp.iso(NOW - dt.timedelta(hours=1))


def snapshot():
    """Shaped like the live /snapshots/Guntersville_AL/latest on 2026-10-12."""
    return {
        "lakeId": "Guntersville|AL",
        "lakeState": {"kind": "OBSERVED", "levelState": "IN_ZONE", "trendState": "STABLE", "historicalState": "INSUFFICIENT_HISTORY",
                      "floodPoolState": "UNKNOWN", "currentElevationFt": 593.69, "differenceFromGuideFt": -0.5, "baselineStatus": "INSUFFICIENT",
                      "freshness": {"generatedAt": GEN, "stale": False}, "provenance": {"brainVersion": "1.0.0", "modelVersion": "lake-level-rules-v1", "generatedAt": GEN, "readiness": "CALIBRATION"}},
        "waterTemperature": {"kind": "modeled", "currentTempF": 76.2, "trend24hF": -0.2, "lakeLocalDate": "2026-10-12", "stale": False, "evidenceStale": False,
                             "provenance": {"brainVersion": "1.0", "modelVersion": "surface-energy-balance-v2", "generatedAt": GEN, "readiness": "CALIBRATION"}},
        "waterClarity": {"stateType": "RAINFALL_MODELED", "clarityFt": 2.56, "clarityUnit": "ft", "basis": "MODEL", "activeModel": "rain-decay-v0",
                         "provenance": {"brainVersion": "1.1.0", "modelVersion": "rain-decay-v0", "generatedAt": GEN, "readiness": "BETA"}},
        "wind": {"kind": "analysis", "stale": False, "gustMph": 3.9, "analysis": {"sustainedMph": 0.4, "product": "RTMA-RU 2.5 km", "analysisTime": GEN},
                 "observation": {"sustainedMph": 1.0, "station": "KHSV"}, "provenance": {"brainVersion": "wind-brain-1.0.0", "modelVersion": "wind-candidate-2026.10.stage2-baseline", "generatedAt": GEN, "readiness": "CALIBRATION"}},
    }


PRESENCE = {"common_carp": {"presenceState": "established", "confidence": "high", "nativeStatus": "introduced", "researchVersion": "p1"},
            "spotted_gar": {"presenceState": "established", "confidence": "medium", "nativeStatus": "native", "researchVersion": "p1"},
            "mystery_fish": {"presenceState": "reported", "confidence": "low", "researchVersion": "p1"}}
SPECIES = {"common_carp": {"assessment": "ASSESSED", "researchMaturity": "RESEARCH", "knowledge": {"rubric": "species-v2", "overallRounded": 7.0}, "researchVersion": "s1"},
           "spotted_gar": {"assessment": "ASSESSED", "researchMaturity": "NOT_STARTED", "knowledge": {"rubric": "species-v2", "overallRounded": 1.0}, "researchVersion": "s1"}}


def deps_all_present():
    cat, _ = real_catalog()
    ups = upstream(**{"lake-brain": {"registry": reg("lake-brain", stale_after=3, status="CALIBRATION"), "health": {"status": "HEALTHY"}, "validationStatus": "NOT_VALIDATED"}})
    return cat, ups, {b: sib.dependency_status(b, cat["dependencies"][b], ups[b]["registry"], ups[b]["health"], ups[b]["validationStatus"], cat, NOW) for b in sib.DEPENDENCY_ORDER}


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.cat, self.ups, self.deps = deps_all_present()
        self.serving = sib.engine_serving(SERVICE, LINEAGE, NOW)

    def evaluate(self, snap=None, presence=PRESENCE, species=SPECIES):
        return ev.evaluate("Guntersville|AL", snapshot=snap if snap is not None else snapshot(), fleet_row=None, presence=presence,
                           species=species, deps=self.deps, cat=self.cat, serving=self.serving, now=NOW)

    def test_consumes_real_states_with_full_provenance(self):
        e = self.evaluate()
        self.assertEqual(e["kind"], "evaluated"); self.assertEqual(e["evaluationVersion"], ev.EVAL_VERSION)
        self.assertEqual(set(e["inputsUsed"]), {"lake", "waterTemp", "waterClarity", "wind", "biology"})
        self.assertEqual(e["inputsUsed"]["waterTemp"], {"brainId": "water-temp", "brainVersion": "1.0", "modelVersion": "surface-energy-balance-v2", "generatedAt": GEN, "status": "PUBLISHED"})
        self.assertEqual(e["inputs"]["lake"]["kind"], "observed")                 # legacy uppercase normalized
        self.assertEqual(e["inputs"]["waterClarity"]["kind"], "modeled")          # from stateType
        self.assertEqual(e["inputs"]["wind"]["values"]["sustainedMph"], 0.4)
        self.assertEqual([d["slot"] for d in e["drivers"]], ["lake", "waterTemp", "waterClarity", "wind", "biology"])
        self.assertIn("water 76.2 °F (modeled)", e["drivers"][1]["fact"])
        self.assertEqual(e["provenance"]["readiness"], "CALIBRATION")
        self.assertEqual({s["sourceId"] for s in e["provenance"]["sources"]}, {"lake-brain@1.0.0", "water-temp@1.0", "water-clarity@1.1.0", "wind@wind-brain-1.0.0", "biological-state@1.0"})
        self.assertEqual(e["validation"]["status"], "NOT_VALIDATED")
        self.assertFalse(e["customerPath"]["consumesThisEvaluation"])
        self.assertNotIn("customerScore", e["synthesis"]); self.assertNotIn("score", e)

    def test_biology_is_presence_joined_with_knowledge_and_gaps_are_limiting(self):
        e = self.evaluate()
        b = e["inputs"]["biology"]
        self.assertEqual(b["speciesCount"], 3); self.assertEqual(b["knowledgeMedian"], 4.0)
        self.assertEqual(b["species"]["common_carp"]["knowledgeScore"], 7.0)
        self.assertEqual(b["knowledgeMissingFor"], ["mystery_fish"])
        self.assertEqual(b["status"], "DEGRADED")
        self.assertIn("biology", e["degradedInputs"])
        self.assertTrue(any("knowledge not started" in f for f in e["limitingFactors"]))
        self.assertTrue(any("no species knowledge for 1" in f for f in e["limitingFactors"]))

    def test_missing_and_stale_inputs_degrade_safely(self):
        snap = snapshot(); del snap["wind"]
        snap["waterTemperature"]["provenance"]["generatedAt"] = bp.iso(NOW - dt.timedelta(hours=30))
        e = self.evaluate(snap, presence=None)
        self.assertEqual(e["inputs"]["wind"]["status"], "NOT_PUBLISHED"); self.assertNotIn("wind", e["inputsUsed"])
        self.assertEqual(e["inputs"]["waterTemp"]["status"], "STALE"); self.assertTrue(e["inputs"]["waterTemp"]["stale"])
        self.assertEqual(e["inputs"]["biology"]["status"], "NOT_PUBLISHED")
        self.assertEqual(e["degradedInputs"], ["biology", "waterTemp", "wind"])
        self.assertTrue(e["freshness"]["evidenceStale"]); self.assertFalse(e["freshness"]["stale"])
        self.assertIn("DEGRADED_INPUTS", e["provenance"]["qualityFlags"])
        self.assertEqual(e["synthesis"]["inputsFresh"], 2)

    def test_nothing_published_evaluates_to_all_not_published(self):
        e = self.evaluate({}, presence=None, species=None)
        self.assertEqual(e.get("inputsUsed", {}), {})                      # empty values are stripped: absent == empty, never a silent skip
        self.assertEqual(len(e["degradedInputs"]), 5); self.assertEqual(e.get("drivers", []), [])

    def test_build_updates_writes_pilot_state_and_registry_truthfully(self):
        e = self.evaluate()
        up = build(ups=self.ups)                                            # no evaluations: inventory only
        self.assertEqual(up["/brains/sector-intelligence"]["evaluatedLakeCount"], 0)
        self.assertEqual(up["/brains/sector-intelligence"]["dependencies"]["wind"]["connectionStatus"], "AVAILABLE_NOT_CONSUMED")
        cat, _ = real_catalog()
        up = sib.build_updates(cat=cat, cat_sha="sha", lakes=["Guntersville|AL", "Beta Reservoir|TN"], fleet={}, upstream=self.ups,
                               serving=self.serving, now=NOW, deployment="test", descriptor={}, duration_ms=1, published=None,
                               event_id=bp.event_id(NOW, sib.BRAIN_ID, 0), evaluations={"Guntersville|AL": e},
                               evaluation_errors={"Beta Reservoir|TN": "boom"}, inputs_fp=ev.inputs_fingerprint({"Guntersville|AL": e}))
        reg_ = up["/brains/sector-intelligence"]
        self.assertEqual(reg_["evaluatedLakeCount"], 1); self.assertEqual(reg_["status"], "CALIBRATION")
        self.assertEqual(reg_["dependencies"]["wind"]["connectionStatus"], "CONNECTED")
        self.assertTrue(reg_["dependencies"]["wind"]["consumedByPilotEvaluation"]); self.assertFalse(reg_["dependencies"]["wind"]["consumedByCustomerPath"])
        self.assertTrue(reg_["dependencies"]["wind"]["usedInLastEvaluation"])
        self.assertFalse(reg_["evaluation"]["customerConsumes"]); self.assertEqual(reg_["evaluation"]["errors"], {"Beta Reservoir|TN": "boom"})
        self.assertEqual(up["/lakes/Guntersville_AL/states/intelligence"]["kind"], "evaluated")
        self.assertEqual(up["/snapshots/Guntersville_AL/latest/sectorIntelligence"]["evaluationVersion"], ev.EVAL_VERSION)
        self.assertEqual(up["/lakeFleet/Guntersville_AL/slots/intelligence"]["kind"], "evaluated")
        self.assertEqual(up["/lakes/Beta_Reservoir_TN/states/intelligence"]["kind"], "not_evaluated")
        self.assertEqual(up["/lakeFleet/Beta_Reservoir_TN/slots/intelligence"]["lastError"], "boom")
        bp.assert_owned({k.lstrip("/"): v for k, v in up.items()}, sib.BRAIN_ID)

    def test_inputs_fingerprint_changes_with_upstream(self):
        e1 = self.evaluate()
        snap = snapshot(); snap["wind"]["provenance"]["generatedAt"] = bp.iso(NOW)
        e2 = self.evaluate(snap)
        self.assertNotEqual(ev.inputs_fingerprint({"a": e1}), ev.inputs_fingerprint({"a": e2}))


if __name__ == "__main__":
    unittest.main()
