"""Pilot evidence layer (intelligence-eval-v2 / intelligence-evidence-v1).

Every species response band below is a TEST FIXTURE. It is not biology, is not published by any Brain, and makes no
claim about any fish. It exists only to exercise the rating logic that consumes an approved Biological band.
"""
import copy
import datetime as dt
import itertools
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import brain_platform as bp                 # noqa: E402
import evaluation as ev                     # noqa: E402
import evidence as evd                      # noqa: E402
import sector_intelligence_brain as sib     # noqa: E402
from test_sector_intelligence_brain import NOW, real_catalog, SERVICE, LINEAGE   # noqa: E402
from test_evaluation import snapshot, PRESENCE, SPECIES, deps_all_present, GEN    # noqa: E402

G_OK = {"status": "EVALUATED", "hits": []}


def band_fixture(tier="VALIDATED", status="APPROVED", deciding=("waterTempF", "clarityFt"), supporting=("windSustainedMph",)):
    """TEST FIXTURE band: shapes only."""
    return {"status": status, "evidenceTier": tier, "version": "fixture-1", "decidingFactors": list(deciding), "supportingFactors": list(supporting),
            "bands": {"waterTempF": {"unit": "°F", "numeric": [{"lt": 50, "state": "BLOCKING"}, {"lt": 60, "state": "LIMITING"}, {"lt": 70, "state": "WORKABLE"}], "else": "FAVORABLE"},
                      "clarityFt": {"unit": "ft", "numeric": [{"lt": 1.0, "state": "BLOCKING"}, {"lt": 2.0, "state": "LIMITING"}, {"lt": 3.0, "state": "WORKABLE"}], "else": "FAVORABLE"},
                      "windSustainedMph": {"unit": "mph", "numeric": [{"lt": 8, "state": "FAVORABLE"}, {"lt": 14, "state": "LIMITING"}], "else": "BLOCKING"},
                      "lakeLevelTrend": {"unit": "", "categorical": {"RISING": "FAVORABLE", "STABLE": "WORKABLE", "FALLING": "LIMITING"}}}}


def with_bands(species_nodes=None, tier="VALIDATED"):
    sp = copy.deepcopy(species_nodes if species_nodes is not None else SPECIES)
    sp["common_carp"]["responseBands"] = band_fixture(tier=tier)
    return sp


class Base(unittest.TestCase):
    def setUp(self):
        self.cat, self.ups, self.deps = deps_all_present()
        self.serving = sib.engine_serving(SERVICE, LINEAGE, NOW)

    def evaluate(self, snap=None, presence=PRESENCE, species=SPECIES, now=NOW):
        return ev.evaluate("Guntersville|AL", snapshot=snap if snap is not None else snapshot(), fleet_row=None, presence=presence,
                           species=species, deps=self.deps, cat=self.cat, serving=self.serving, now=now)


# --- 1 ---------------------------------------------------------------------------------------------------------
class UnknownNeverImproves(Base):
    def test_exhaustive_every_state_vector(self):
        """Replacing ANY known state (including BLOCKING) by UNKNOWN never raises the rating."""
        order = evd.RATINGS
        states = ("FAVORABLE", "WORKABLE", "LIMITING", "BLOCKING", None)
        checked = 0
        for conf in ("INSUFFICIENT", "LOW", "MEDIUM", "HIGH"):
            for gate in (G_OK, {"status": "NOT_EVALUATED", "hits": []}):
                for dec in itertools.product(states, repeat=3):
                    for sup in itertools.product(states[:4] + (None,), repeat=1):
                        base = evd.rate(list(dec), list(sup), gates=gate, confidence=conf)[0]
                        for i, s in enumerate(dec):
                            if s is None:
                                continue
                            d2 = list(dec); d2[i] = None
                            self.assertLessEqual(order.index(evd.rate(d2, list(sup), gates=gate, confidence=conf)[0]), order.index(base), (dec, sup, conf, i))
                            checked += 1
                        for j, s in enumerate(sup):
                            if s is None:
                                continue
                            s2 = list(sup); s2[j] = None
                            self.assertLessEqual(order.index(evd.rate(list(dec), s2, gates=gate, confidence=conf)[0]), order.index(base), (dec, sup, conf, j))
                            checked += 1
        self.assertGreater(checked, 3000)

    def test_unknown_below_poor_by_construction(self):
        self.assertLess(evd.RATINGS.index("UNRANKED"), evd.RATINGS.index("POOR"))

    def named_case(self, tweak, label):
        sp = with_bands()
        snap = snapshot(); tweak(snap)
        return self.evaluate(snap, species=sp)["evidence"]["species"]["common_carp"], label

    def test_poor_temperature_stays_poor_or_worse_when_unknown(self):
        cold = snapshot(); cold["waterTemperature"]["currentTempF"] = 44.0
        poor = self.evaluate(cold, species=with_bands())["evidence"]["species"]["common_carp"]
        self.assertEqual(poor["rating"], "POOR")
        unk = snapshot(); unk["waterTemperature"].pop("currentTempF")
        gone = self.evaluate(unk, species=with_bands())["evidence"]["species"]["common_carp"]
        self.assertLessEqual(evd.RATINGS.index(gone["rating"]), evd.RATINGS.index(poor["rating"]))
        self.assertEqual(gone["rating"], "UNRANKED")
        self.assertEqual(gone["factorStates"]["waterTempF"], "UNKNOWN")

    def test_poor_lake_level_stays_poor_or_worse_when_unknown(self):
        sp = with_bands(); sp["common_carp"]["responseBands"] = band_fixture(deciding=("lakeLevelTrend", "waterTempF"), supporting=())
        falling = snapshot(); falling["lakeState"]["trendState"] = "FALLING"
        lim = self.evaluate(falling, species=sp)["evidence"]["species"]["common_carp"]
        self.assertEqual(lim["factorStates"]["lakeLevelTrend"], "LIMITING")
        gone = snapshot(); gone["lakeState"].pop("trendState")
        unk = self.evaluate(gone, species=sp)["evidence"]["species"]["common_carp"]
        self.assertLessEqual(evd.RATINGS.index(unk["rating"]), evd.RATINGS.index(lim["rating"]))
        self.assertEqual(unk["factorStates"]["lakeLevelTrend"], "UNKNOWN")

    def test_vegetation_absent_manufactures_no_habitat_value(self):
        sp = with_bands(); sp["common_carp"]["responseBands"] = band_fixture(deciding=("waterTempF", "vegetation"), supporting=())
        sp["common_carp"]["responseBands"]["bands"]["vegetation"] = {"unit": "", "categorical": {"dense": "FAVORABLE"}}
        a = self.evaluate(species=sp)["evidence"]["species"]["common_carp"]
        self.assertEqual(a["factorStates"]["vegetation"], "UNKNOWN")
        self.assertEqual(a["rating"], "UNRANKED")
        self.assertNotIn("vegetation", [e["factorId"] for e in a["explanation"]["positive"]])
        self.assertEqual(a["confidence"], "INSUFFICIENT")

    def test_missing_data_never_creates_higher_confidence(self):
        full = self.evaluate(species=with_bands())["evidence"]["species"]["common_carp"]
        snap = snapshot(); del snap["waterClarity"]
        less = self.evaluate(snap, species=with_bands())["evidence"]["species"]["common_carp"]
        self.assertLessEqual(evd.CONF.index(less["confidence"]), evd.CONF.index(full["confidence"]))
        self.assertEqual(less["confidence"], "INSUFFICIENT")


# --- 2 ---------------------------------------------------------------------------------------------------------
class ConfidenceIsWeakestLink(Base):
    def test_five_weak_signals_cannot_make_high(self):
        weak = snapshot()
        for k in ("lakeState", "waterTemperature", "waterClarity", "wind"):
            weak[k]["kind"] = "proxy"; weak[k].pop("stateType", None)
        a = self.evaluate(weak, species=with_bands())["evidence"]
        for f in a["factors"].values():
            if f["known"]:
                self.assertIn(f["confidence"], ("LOW", "INSUFFICIENT"))
        self.assertIn(a["species"]["common_carp"]["confidence"], ("LOW", "INSUFFICIENT"))

    def test_agreement_adds_nothing(self):
        one = evd.factor_confidence(known=True, kind="modeled", stale=False, evidence_stale=False, support="LAKE", lead_hours=0,
                                    area_decision=False, brain_confidence=None, readiness=None)[0]
        self.assertEqual(one, "MEDIUM")
        # a measured temperature next to a modeled clarity: overall is the modeled one
        snap = snapshot(); snap["waterTemperature"]["kind"] = "measured"
        a = self.evaluate(snap, species=with_bands())["evidence"]["species"]["common_carp"]
        self.assertEqual(a["weakestConfidenceFactor"]["factorId"], "clarityFt")
        self.assertEqual(a["confidence"], "MEDIUM")

    def test_modeled_basis_is_retained_and_explained(self):
        f = self.evaluate()["evidence"]["factors"]["waterTempF"]
        self.assertEqual(f["kind"], "modeled"); self.assertEqual(f["confidence"], "MEDIUM")
        self.assertTrue(any("modeled" in b for b in f["confidenceBasis"]))

    def test_confidence_is_not_a_fixed_countdown(self):
        a = self.evaluate(species=with_bands())["evidence"]["species"]["common_carp"]
        snap = snapshot(); snap["waterClarity"]["clarityFt"] = 3.5
        b = self.evaluate(snap, species=with_bands())["evidence"]["species"]["common_carp"]
        self.assertEqual(a["confidence"], b["confidence"])                    # same evidence quality, same confidence
        self.assertTrue(a["confidenceBasis"])                                  # and it always carries a basis

    def test_band_tier_caps_confidence(self):
        for tier, expect in (("RESEARCH", "LOW"), ("REVIEWED", "MEDIUM"), ("VALIDATED", "MEDIUM")):   # evidence itself is MEDIUM (modeled)
            a = self.evaluate(species=with_bands(tier=tier))["evidence"]["species"]["common_carp"]
            self.assertEqual(a["confidence"], expect, tier)
        a = self.evaluate(species=with_bands(tier="RESEARCH"))["evidence"]["species"]["common_carp"]
        self.assertTrue(any("tier RESEARCH" in b for b in a["confidenceBasis"]))

    def test_presence_evidence_caps_confidence(self):
        pres = copy.deepcopy(PRESENCE); pres["common_carp"]["presenceState"] = "reported"
        a = self.evaluate(presence=pres, species=with_bands())["evidence"]["species"]["common_carp"]
        self.assertEqual(a["confidence"], "LOW")

    def test_top_rating_needs_gates_and_confidence(self):
        snap = snapshot()
        for k in ("lakeState", "waterTemperature", "waterClarity", "wind"):
            snap[k]["kind"] = "measured"
        snap["waterTemperature"]["currentTempF"] = 75.0; snap["waterClarity"]["clarityFt"] = 4.0; snap["wind"]["analysis"]["sustainedMph"] = 2.0
        a = self.evaluate(snap, species=with_bands())["evidence"]["species"]["common_carp"]
        self.assertEqual(a["confidence"], "HIGH")
        self.assertEqual(a["rating"], "WORTH_A_LOOK")                                  # gates NOT_EVALUATED in the pilot
        self.assertTrue(any("gates were not evaluated" in c for c in a["caveats"]))
        a2 = evd.assess_species("common_carp", PRESENCE["common_carp"], with_bands()["common_carp"],
                                evd.build_factors({"lake": {}, "waterTemp": {}, "waterClarity": {}, "wind": {}}, None), G_OK)
        self.assertEqual(a2["rating"], "UNRANKED")


# --- 3,4 -------------------------------------------------------------------------------------------------------
class StaleAndMissing(Base):
    def test_stale_evidence_is_identified_and_lowers_confidence(self):
        snap = snapshot(); snap["waterTemperature"]["provenance"]["generatedAt"] = bp.iso(NOW - dt.timedelta(hours=30))
        e = self.evaluate(snap, species=with_bands())["evidence"]
        f = e["factors"]["waterTempF"]
        self.assertTrue(f["stale"]); self.assertIn("waterTempF", e["summary"]["staleFactors"])
        self.assertEqual(f["confidence"], "LOW")                                   # modeled MEDIUM, minus one level
        sp = e["species"]["common_carp"]
        self.assertEqual([s["factorId"] for s in sp["explanation"]["stale"]], ["waterTempF"])
        self.assertEqual(sp["weakestConfidenceFactor"]["factorId"], "waterTempF")

    def test_evidence_stale_flag_from_brain_is_honoured(self):
        snap = snapshot(); snap["waterTemperature"]["evidenceStale"] = True
        f = self.evaluate(snap)["evidence"]["factors"]["waterTempF"]
        self.assertTrue(f["evidenceStale"]); self.assertEqual(f["confidence"], "LOW")

    def test_missing_brain_input_stays_unknown(self):
        snap = snapshot(); del snap["wind"]
        e = self.evaluate(snap)["evidence"]
        f = e["factors"]["windSustainedMph"]
        self.assertFalse(f["known"]); self.assertEqual(f["state"], "UNKNOWN"); self.assertEqual(f["confidence"], "INSUFFICIENT")
        self.assertNotIn("value", f)
        self.assertIn("windSustainedMph", e["summary"]["unknownFactors"])

    def test_nothing_published_is_all_unknown(self):
        e = self.evaluate({}, presence=None, species=None)["evidence"]
        self.assertEqual(e["summary"]["knownFactors"], 0); self.assertEqual(e["summary"]["ratingsIssued"], 0)
        self.assertTrue(all(f["state"] == "UNKNOWN" and not f["known"] for f in e["factors"].values()))


# --- 5,6,7 -----------------------------------------------------------------------------------------------------
class PlaceholdersAndOwnership(Base):
    def test_depth_absent_remains_unknown(self):
        f = self.evaluate()["evidence"]["factors"]["effectiveDepthFt"]
        self.assertFalse(f["known"]); self.assertEqual(f["state"], "UNKNOWN"); self.assertIn("Depth Brain is not published", f["reason"])

    def test_vegetation_absent_remains_unknown(self):
        f = self.evaluate()["evidence"]["factors"]["vegetation"]
        self.assertFalse(f["known"]); self.assertEqual(f["state"], "UNKNOWN"); self.assertIn("Vegetation Brain is not published", f["reason"])

    def test_a_future_depth_or_vegetation_state_in_the_snapshot_is_still_not_consumed(self):
        """No ratified DepthZoneState/VegetationZoneState shape exists, so nothing in the snapshot may be read as one."""
        snap = snapshot()
        snap["depth"] = {"kind": "modeled", "meanFt": 4.0, "provenance": {"brainVersion": "x", "generatedAt": GEN}}
        snap["vegetation"] = {"kind": "observed", "presence": "dense", "provenance": {"brainVersion": "x", "generatedAt": GEN}}
        e = self.evaluate(snap)["evidence"]
        for fid in ("effectiveDepthFt", "vegetation"):
            self.assertFalse(e["factors"][fid]["known"])
        self.assertNotIn("value", e["factors"]["vegetation"])

    def test_wind_exposure_is_a_dependency_gap_not_a_derived_value(self):
        snap = snapshot(); snap["wind"]["exposure"] = {"protectedPct": 40, "exposedPct": 10}
        f = self.evaluate(snap)["evidence"]["factors"]["windExposure"]
        self.assertFalse(f["known"]); self.assertEqual(f["state"], "UNKNOWN")
        self.assertIn("not zone-specific", f["detail"]["note"])
        self.assertNotIn("value", f)

    def test_missing_biological_band_is_unsupported_and_unranked(self):
        e = self.evaluate()["evidence"]                              # SPECIES fixture has knowledge scores only
        cc = e["species"]["common_carp"]
        self.assertEqual(cc["bandStatus"], "UNSUPPORTED"); self.assertEqual(cc["rating"], "UNRANKED"); self.assertEqual(cc["confidence"], "INSUFFICIENT")
        self.assertEqual(cc["weakestConfidenceFactor"]["factorId"], "responseBands")
        self.assertEqual(e["summary"]["ratingsIssued"], 0)
        self.assertEqual(e["summary"]["speciesByBandStatus"], {"UNSUPPORTED": 3})
        self.assertNotIn("factorStates", cc)                        # no thresholds were applied, none invented

    def test_unapproved_or_malformed_bands_are_unsupported(self):
        for mutate in (lambda b: b.update(status="DRAFT"), lambda b: b.update(evidenceTier="GUESS"),
                       lambda b: b["bands"]["waterTempF"].update(unit="°C"),
                       lambda b: b["bands"]["waterTempF"].update(numeric=[{"lt": 60, "state": "LIMITING"}, {"lt": 50, "state": "BLOCKING"}]),
                       lambda b: b.update(decidingFactors=[]), lambda b: b.update(decidingFactors=["madeUpFactor"])):
            sp = copy.deepcopy(SPECIES); b = band_fixture(); mutate(b); sp["common_carp"]["responseBands"] = b
            a = self.evaluate(species=sp)["evidence"]["species"]["common_carp"]
            self.assertEqual(a["bandStatus"], "UNSUPPORTED", b)
            self.assertEqual(a["rating"], "UNRANKED")

    def test_species_without_a_node_and_historical_species_are_not_guessed(self):
        pres = copy.deepcopy(PRESENCE); pres["old_fish"] = {"presenceState": "historical", "confidence": "high"}
        pres["odd_fish"] = {"presenceState": "somethingNew", "confidence": "high"}
        e = self.evaluate(presence=pres)["evidence"]["species"]
        self.assertEqual(e["mystery_fish"]["bandStatus"], "UNSUPPORTED")
        self.assertEqual(e["old_fish"]["bandStatus"], "NOT_ASSESSED"); self.assertEqual(e["odd_fish"]["bandStatus"], "NOT_ASSESSED")

    def test_species_are_evaluated_separately(self):
        sp = with_bands(); sp["spotted_gar"]["responseBands"] = band_fixture(deciding=("windSustainedMph",), supporting=())
        sp["spotted_gar"]["responseBands"]["bands"]["windSustainedMph"] = {"unit": "mph", "numeric": [{"lt": 0.1, "state": "FAVORABLE"}], "else": "BLOCKING"}
        e = self.evaluate(species=sp)["evidence"]["species"]
        self.assertNotEqual(e["common_carp"]["rating"], e["spotted_gar"]["rating"])
        self.assertEqual(e["spotted_gar"]["rating"], "POOR")                       # same lake, same wind: different fish, different answer

    def test_future_lead_time_is_unknown_not_carried_forecast(self):
        snap = snapshot()
        ev_ = ev.evaluate("Guntersville|AL", snapshot=snap, fleet_row=None, presence=PRESENCE, species=with_bands(), deps=self.deps,
                          cat=self.cat, serving=self.serving, now=NOW)
        inputs = ev_["inputs"]
        e = evd.build_evidence(inputs=inputs, snapshot=snap, presence=PRESENCE, species=with_bands(), lead_hours=12.0, horizons={"windSustainedMph": 24.0})
        self.assertEqual(e["checkpoint"], "+12h")
        t = e["factors"]["waterTempF"]
        self.assertFalse(t["known"]); self.assertIn("carried", t); self.assertNotIn("value", t)
        self.assertTrue(e["factors"]["windSustainedMph"]["known"])
        self.assertLessEqual(evd.CONF.index(e["factors"]["windSustainedMph"]["confidence"]), evd.CONF.index("MEDIUM"))
        self.assertEqual(e["species"]["common_carp"]["rating"], "UNRANKED")


# --- 8,9,10 ----------------------------------------------------------------------------------------------------
class ProvenanceExplanationDeterminism(Base):
    def test_provenance_survives_synthesis(self):
        e = self.evaluate(species=with_bands())["evidence"]
        for fid in ("lakeLevelTrend", "waterTempF", "clarityFt", "windSustainedMph"):
            src = e["factors"][fid]["source"]
            self.assertTrue(src["brainId"] and src["brainVersion"] and src["generatedAt"], fid)
        self.assertEqual(e["factors"]["waterTempF"]["source"]["modelVersion"], "surface-energy-balance-v2")
        a = e["species"]["common_carp"]
        for entry in a["explanation"].get("positive", []) + a["explanation"].get("limiting", []) + a["explanation"].get("blocking", []):
            self.assertRegex(entry["source"], r"^[a-z\-]+@[\w.\-]+$")
        self.assertEqual(a["bandVersion"], "fixture-1")

    def test_explanation_identifies_limiting_blocking_unknown_stale_and_weakest(self):
        sp = with_bands(); sp["common_carp"]["responseBands"] = band_fixture(deciding=("waterTempF", "clarityFt", "lakeLevelTrend"), supporting=("windSustainedMph",))
        sp["common_carp"]["responseBands"]["bands"]["lakeLevelTrend"] = {"unit": "", "categorical": {"STABLE": "WORKABLE"}}
        snap = snapshot(); snap["waterTemperature"]["currentTempF"] = 55.0; snap["wind"]["analysis"]["sustainedMph"] = 20.0
        snap["waterClarity"]["provenance"]["generatedAt"] = bp.iso(NOW - dt.timedelta(hours=100))
        a = self.evaluate(snap, species=sp)["evidence"]["species"]["common_carp"]
        ex = a["explanation"]
        self.assertEqual([x["factorId"] for x in ex["limiting"]], ["waterTempF"])
        self.assertEqual([x["factorId"] for x in ex["blocking"]], ["windSustainedMph"])
        self.assertEqual([x["factorId"] for x in ex["stale"]], ["clarityFt"])
        self.assertEqual(ex["counts"], {"positive": 2, "limiting": 1, "blocking": 1, "unknown": 0, "stale": 1})
        self.assertIn("lakeLevelTrend", [x["factorId"] for x in ex["positive"]])
        self.assertIn(a["weakestConfidenceFactor"]["factorId"], ("clarityFt",))
        self.assertTrue(a["weakestConfidenceFactor"]["reason"])
        self.assertEqual(a["rating"], "LOW_PRIORITY")
        self.assertIn("windSustainedMph", a["affectedRating"])                    # a supporting factor that mattered
        self.assertTrue(self.evaluate(snap, species=sp)["evidence"]["factors"]["windSustainedMph"]["affectedRating"])

    def test_explanation_lines_are_templates_over_records(self):
        e = self.evaluate(species=with_bands())["evidence"]
        a = e["species"]["common_carp"]
        for entry in a["explanation"].get("positive", []) + a["explanation"].get("limiting", []):
            f = e["factors"][entry["factorId"]]
            self.assertEqual(entry["value"], f["value"]); self.assertEqual(entry["kind"], f["kind"])
            self.assertTrue(entry["reason"].startswith(f["name"]))

    def test_deterministic(self):
        a = json.dumps(self.evaluate(species=with_bands()), sort_keys=True)
        b = json.dumps(self.evaluate(species=with_bands()), sort_keys=True)
        self.assertEqual(a, b)
        self.assertEqual(ev.inputs_fingerprint({"x": json.loads(a)}), ev.inputs_fingerprint({"x": json.loads(b)}))

    def test_rtdb_safe_and_json_serialisable(self):
        e = self.evaluate(species=with_bands())
        json.dumps(e, allow_nan=False)
        sib.check_keys({"/lakes/Guntersville_AL/states/intelligence": e})
        size = len(json.dumps(e, separators=(",", ":")))
        self.assertLess(size, 40_000, size)


# --- 11,12 -----------------------------------------------------------------------------------------------------
class Isolation(Base):
    def test_evaluation_stays_internal_and_scoreless(self):
        e = self.evaluate(species=with_bands())
        self.assertFalse(e["customerPath"]["consumesThisEvaluation"])
        self.assertEqual(e["customerPath"]["implementation"], "engine-conditions-score")
        self.assertNotIn("score", e); self.assertNotIn("score", e["evidence"]); self.assertNotIn("score", e["evidence"]["summary"])
        self.assertIn("NO_CUSTOMER_SCORE", e["provenance"]["qualityFlags"]); self.assertIn("EVIDENCE_LAYER_PILOT", e["provenance"]["qualityFlags"])
        self.assertEqual(e["validation"]["status"], "NOT_VALIDATED")
        self.assertEqual(e["evidence"]["gates"]["status"], "NOT_EVALUATED")

    def test_published_registry_still_says_customer_does_not_consume(self):
        e = self.evaluate()
        up = sib.build_updates(cat=self.cat, cat_sha="sha", lakes=["Guntersville|AL"], fleet={}, upstream=self.ups, serving=self.serving, now=NOW,
                               deployment="test", descriptor={}, duration_ms=1, published=None, event_id=bp.event_id(NOW, sib.BRAIN_ID, 0),
                               evaluations={"Guntersville|AL": e}, inputs_fp=ev.inputs_fingerprint({"Guntersville|AL": e}))
        reg = up["/brains/sector-intelligence"]
        self.assertFalse(reg["evaluation"]["customerConsumes"])
        for dep in reg["dependencies"].values():
            self.assertFalse(dep["consumedByCustomerPath"])
        self.assertEqual(reg["evaluation"]["version"], "intelligence-eval-v2")
        sib.check_keys(up)

    def test_evidence_module_has_no_io_and_no_customer_imports(self):
        with open(os.path.join(os.path.dirname(HERE), "evidence.py")) as fh:
            src = fh.read()
        imports = set(re.findall(r"^\s*(?:import|from)\s+([\w.]+)", src, re.M))
        self.assertEqual(imports - {"__future__"}, set(), imports)            # stdlib-free: pure functions only
        for banned in ("urllib", "requests", "open(", "datetime.now", "time.time", "random", "Conditions", "/conditions"):
            self.assertNotIn(banned, src.replace("not read by the customer path", ""), banned)

    def test_evaluation_module_only_adds_the_evidence_import(self):
        with open(os.path.join(os.path.dirname(HERE), "evaluation.py")) as fh:
            src = fh.read()
        self.assertEqual(set(re.findall(r"^import (\w+)", src, re.M)) - {"datetime", "hashlib", "json", "statistics", "brain_platform", "evidence"}, set())


if __name__ == "__main__":
    unittest.main()
