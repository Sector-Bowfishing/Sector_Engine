"""Biological rules, condition features, response bands, pilot Biological State and validation-foundation tests.

  cd jobs/biological-brain && python3 -m unittest discover -s tests -v

Every fixture is SYNTHETIC (fake species, fake rules). Real species rules live only in the PRIVATE bundle; the one optional
test that reads them is skipped unless BIOLOGY_PRIVATE_RULES points at a staged rules directory.
"""
import copy
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import bio_state as bs          # noqa: E402
import features as ft           # noqa: E402
import rules as rl              # noqa: E402
import validation_log as vl     # noqa: E402

NOW = dt.datetime(2026, 4, 20, 3, 0, tzinfo=dt.timezone.utc)


def ev(i, stream, counts=True, read="READ-ABSTRACT", southeast=False, directness="DIRECT"):
    return {"evidenceId": f"E{i}", "packet": "synthetic", "sourceNo": f"S{i}", "readStatus": read, "streamId": stream, "directness": directness,
            "counts": counts, "southeast": southeast}


def rule(rid="EX-FLW-01", sid="example_fish", **kw):
    r = {"schemaVersion": 1, "ruleId": rid, "ruleVersion": 1, "speciesId": sid, "kind": "RESPONSE", "status": "RECONCILED",
         "confidence": "LOW", "transferability": {"southeastReservoir": "PARTIAL"}, "applicability": {"months": [3, 4, 5], "regions": ["south"]},
         "feature": {"featureId": "warmRise", "states": ["TRUE"]}, "response": "FAVORABLE", "behavior": "RUN",
         "evidence": [ev(1, "stream-a")]}
    r.update(kw)
    return r


def inputs(temp_f=64.4, trend=0.5, lake_trend="RISING", clarity=2.5, status="PUBLISHED"):
    mk = lambda v: {"status": status, "values": v}      # noqa: E731
    return {"waterTemp": mk({"currentTempF": temp_f, "trend24hF": trend}), "lake": mk({"trendState": lake_trend}),
            "waterClarity": mk({"clarityFt": clarity})}


class FeatureTests(unittest.TestCase):
    def test_temperature_band_boundaries_lower_inclusive(self):
        for c, band in [(9.99, "LT_10C"), (10.0, "C10_15"), (14.99, "C10_15"), (15.0, "C15_18"), (17.99, "C15_18"), (18.0, "C18_21"),
                        (20.99, "C18_21"), (21.0, "C21_26"), (26.0, "C26_30"), (30.0, "GE_30C")]:
            self.assertEqual(ft.temp_band(c), band, c)

    def test_f_to_c_does_not_drift_on_boundaries(self):
        self.assertEqual(ft.temp_band(ft.f_to_c(59.0)), "C15_18")      # exactly 15 C
        self.assertEqual(ft.temp_band(ft.f_to_c(58.9)), "C10_15")
        self.assertEqual(ft.temp_band(ft.f_to_c(64.4)), "C18_21")      # exactly 18 C

    def test_warm_rise_three_valued_logic(self):
        f = ft.evaluate_features(inputs(temp_f=59.0, lake_trend="RISING"))
        self.assertEqual((f["warmRise"]["state"], f["coldRise"]["state"]), ("TRUE", "FALSE"))
        f = ft.evaluate_features(inputs(temp_f=58.0, lake_trend="RISING_RAPIDLY"))
        self.assertEqual((f["warmRise"]["state"], f["coldRise"]["state"]), ("FALSE", "TRUE"))
        f = ft.evaluate_features(inputs(temp_f=70, lake_trend="FALLING"))
        self.assertEqual((f["warmRise"]["state"], f["coldRise"]["state"]), ("FALSE", "FALSE"))

    def test_missing_or_stale_input_is_unknown_not_guessed(self):
        f = ft.evaluate_features(inputs(status="STALE"))
        for k in ("waterTempBand", "stageTrend", "warmRise", "coldRise", "clarityBand"):
            self.assertEqual(f[k]["state"], "UNKNOWN", k)
        f = ft.evaluate_features({})
        self.assertEqual(f["warmRise"]["state"], "UNKNOWN")
        # rising unknown but water known cold -> coldRise unknown, warmRise FALSE (logical AND with a known false)
        f = ft.evaluate_features({"waterTemp": {"status": "PUBLISHED", "values": {"currentTempF": 50.0, "trend24hF": 0.0}}})
        self.assertEqual((f["warmRise"]["state"], f["coldRise"]["state"]), ("FALSE", "UNKNOWN"))

    def test_rapid_discharge_is_unknown_until_a_brain_publishes_it(self):
        self.assertEqual(ft.evaluate_features(inputs())["rapidDischargeIncrease"]["state"], "UNKNOWN")
        i = inputs()
        i["lake"]["values"]["tributaryDischargeTrend"] = "RISING_RAPIDLY"
        self.assertEqual(ft.evaluate_features(i)["rapidDischargeIncrease"]["state"], "TRUE")

    def test_crossing_within_24h(self):
        f = ft.evaluate_features(inputs(temp_f=60.0, trend=3.0))       # 56.1 -> 60.0 F: crosses 15 C (59 F)
        self.assertEqual(f["temperatureCrossing15C"]["state"], "UP_24H")
        self.assertEqual(f["temperatureCrossing18C"]["state"], "NONE_24H")
        f = ft.evaluate_features(inputs(temp_f=58.0, trend=-3.0))
        self.assertEqual(f["temperatureCrossing15C"]["state"], "DOWN_24H")

    def test_trend_noise_floor(self):
        self.assertEqual(ft.evaluate_features(inputs(trend=0.9))["temperatureTrend"]["state"], "STEADY")
        self.assertEqual(ft.evaluate_features(inputs(trend=1.0))["temperatureTrend"]["state"], "WARMING")
        self.assertEqual(ft.evaluate_features(inputs(trend=-1.0))["temperatureTrend"]["state"], "COOLING")

    def test_spawn_window_boundaries_inclusive_and_unknowns(self):
        w = {"months": [4, 5, 6], "tempC": {"min": 20.0, "max": 30.0}}
        self.assertEqual(ft.spawn_window(5, 20.0, w)["state"], "IN_WINDOW")
        self.assertEqual(ft.spawn_window(5, 30.0, w)["state"], "IN_WINDOW")
        self.assertEqual(ft.spawn_window(5, 19.99, w)["state"], "MONTH_ONLY")
        self.assertEqual(ft.spawn_window(9, 25.0, w)["state"], "TEMP_ONLY")
        self.assertEqual(ft.spawn_window(1, 5.0, w)["state"], "OUTSIDE")
        self.assertEqual(ft.spawn_window(5, None, w)["state"], "UNKNOWN")
        self.assertEqual(ft.spawn_window(1, None, w)["state"], "OUTSIDE")      # month alone is enough to rule it out
        self.assertEqual(ft.spawn_window(5, 25.0, None)["state"], "UNKNOWN")


class RuleContractTests(unittest.TestCase):
    def test_valid_rule_parses(self):
        self.assertEqual(rl.validate_rule(rule()), [])

    def test_rule_identity_and_versioning(self):
        rs = rl.RuleSet([rule("EX-FLW-01"), rule("EX-FLW-02")], "t.1")
        self.assertEqual({r["ruleId"] for r in rs.for_species("example_fish")}, {"EX-FLW-01", "EX-FLW-02"})
        with self.assertRaises(rl.RuleError):
            rl.RuleSet([rule("EX-FLW-01"), rule("EX-FLW-01")], "t.1")             # duplicate (ruleId, version)
        v2 = rule("EX-FLW-01", ruleVersion=2)
        rl.RuleSet([rule("EX-FLW-01"), v2], "t.2")                               # a new version is a distinct identity
        self.assertNotEqual(rl.rule_hash(rule()), rl.rule_hash(v2))
        self.assertEqual(rl.rule_hash(rule()), rl.rule_hash(copy.deepcopy(rule())))

    def test_bad_ids_features_and_states_rejected(self):
        self.assertTrue(rl.validate_rule(rule("bad id")))
        self.assertTrue(rl.validate_rule(rule(feature={"featureId": "notAFeature", "states": ["TRUE"]})))
        self.assertTrue(rl.validate_rule(rule(feature={"featureId": "warmRise", "states": ["MAYBE"]})))
        self.assertTrue(rl.validate_rule(rule(response="GREAT")))
        self.assertTrue(rl.validate_rule(rule(feature={"featureId": "backwaterHabitat", "states": ["TRUE"]})))     # area class needs a HABITAT rule

    def test_snippet_only_evidence_can_never_count(self):
        bad = rule(evidence=[ev(1, "s", counts=True, read="SNIPPET-ONLY")])
        self.assertTrue(any("never count" in m for m in rl.validate_rule(bad)))
        only_snippet = rule(evidence=[ev(1, "s", counts=False, read="SNIPPET-ONLY")])
        self.assertTrue(any("counting, read source" in m for m in rl.validate_rule(only_snippet)))
        self.assertEqual(rl.validate_rule(rule(status="DRAFT", evidence=[ev(1, "s", counts=False, read="SNIPPET-ONLY")])), [])

    def test_confidence_is_capped_by_independent_streams(self):
        two_papers_one_cohort = rule(confidence="MEDIUM", evidence=[ev(1, "cohort-x"), ev(2, "cohort-x")])
        self.assertTrue(any("exceeds" in m for m in rl.validate_rule(two_papers_one_cohort)))
        two = rule(confidence="MEDIUM", evidence=[ev(1, "a"), ev(2, "b")])
        self.assertEqual(rl.validate_rule(two), [])
        three_partial = rule(confidence="HIGH", evidence=[ev(1, "a"), ev(2, "b"), ev(3, "c")])
        self.assertTrue(any("exceeds" in m for m in rl.validate_rule(three_partial)))       # HIGH needs transfer to the Southeast
        three_transfers = rule(confidence="HIGH", transferability={"southeastReservoir": "TRANSFERS"},
                               evidence=[ev(1, "a", southeast=True), ev(2, "b"), ev(3, "c")])
        self.assertEqual(rl.validate_rule(three_transfers), [])

    def test_transfers_needs_a_southeast_stream_and_approved_needs_reviewer(self):
        self.assertTrue(rl.validate_rule(rule(transferability={"southeastReservoir": "TRANSFERS"})))
        self.assertTrue(rl.validate_rule(rule(status="APPROVED")))
        self.assertEqual(rl.validate_rule(rule(status="APPROVED", review={"reviewer": "r", "date": "2026-10-13"})), [])

    def test_phenology_is_a_range_never_a_single_optimum(self):
        ph = rule("EX-SPN-01", kind="PHENOLOGY", phenology={"event": "spawn", "tempC": {"min": 17.0, "max": 21.0}})
        del ph["feature"], ph["response"]
        self.assertEqual(rl.validate_rule(ph), [])
        ph["phenology"]["tempC"] = {"min": 20.0, "max": 20.0}
        self.assertTrue(rl.validate_rule(ph))
        ph["phenology"] = {"event": "spawn", "tempC": {"min": 17.0, "max": 21.0}, "optimalC": 19.0}
        self.assertTrue(rl.validate_rule(ph))

    def test_rules_bundle_hash_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            import hashlib
            body = json.dumps({"speciesId": "example_fish", "rules": [rule()]}).encode()
            open(os.path.join(d, "example_fish.json"), "wb").write(body)
            man = {"rulesVersion": "t.1", "files": [{"path": "example_fish.json", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}]}
            json.dump(man, open(os.path.join(d, "rules_manifest.json"), "w"))
            self.assertEqual(rl.load_rules_dir(d).rules_version, "t.1")
            open(os.path.join(d, "example_fish.json"), "wb").write(body + b" ")
            with self.assertRaises(rl.RuleError):
                rl.load_rules_dir(d)


class ResponseBandTests(unittest.TestCase):
    ctx = {"month": 4, "region": "south", "waterbodyType": "run_of_river"}

    def feats(self, **kw):
        return ft.evaluate_features(inputs(**kw))

    def test_matching_rule_gives_a_band_with_full_provenance(self):
        out = rl.evaluate_responses([rule()], self.feats(temp_f=70, lake_trend="RISING"), self.ctx)
        self.assertEqual(len(out), 1)
        b = out[0]
        self.assertEqual((b["featureId"], b["featureState"], b["response"], b["confidence"]), ("warmRise", "TRUE", "FAVORABLE", "LOW"))
        self.assertEqual(b["evidenceBasis"]["ruleIds"], ["EX-FLW-01"])
        self.assertEqual(b["transferability"], "PARTIAL")
        self.assertEqual(b["regionApplicability"]["ruleRegions"], ["south"])
        self.assertEqual(b["seasonApplicability"]["ruleMonths"], [3, 4, 5])
        self.assertIn(b["response"], rl.RESPONSES)

    def test_seasonal_and_regional_applicability(self):
        r = rule()
        self.assertEqual(rl.evaluate_responses([r], self.feats(temp_f=70), {**self.ctx, "month": 9}), [])
        self.assertEqual(rl.evaluate_responses([r], self.feats(temp_f=70), {**self.ctx, "region": "north"}), [])
        self.assertEqual(len(rl.evaluate_responses([r], self.feats(temp_f=70), {**self.ctx, "month": 5})), 1)
        lake_only = rule(applicability={"months": [4], "regions": ["south"], "waterbodyTypes": ["natural_lake"]})
        self.assertEqual(rl.evaluate_responses([lake_only], self.feats(temp_f=70), self.ctx), [])
        self.assertEqual(rl.applicable(rule(lifeStage="JUVENILE"), self.ctx), (False, "lifeStage"))

    def test_unknown_input_yields_unknown_band_not_a_guess(self):
        out = rl.evaluate_responses([rule()], ft.evaluate_features(inputs(status="STALE")), self.ctx)
        self.assertEqual(out[0]["response"], "UNKNOWN")
        self.assertIn("input unknown", out[0]["reason"])
        self.assertNotIn("confidence", out[0])

    def test_state_not_covered_by_any_rule_is_unknown(self):
        out = rl.evaluate_responses([rule()], self.feats(temp_f=70, lake_trend="FALLING"), self.ctx)    # warmRise FALSE; rule covers TRUE only
        self.assertEqual(out[0]["response"], "UNKNOWN")
        self.assertIn("no rule covers", out[0]["reason"])

    def test_conflicting_evidence_resolves_to_unknown_with_the_conflict_named(self):
        a = rule("EX-FLW-01", response="FAVORABLE")
        b = rule("EX-FLW-02", response="LIMITING")
        out = rl.evaluate_responses([a, b], self.feats(temp_f=70), self.ctx)
        self.assertEqual(out[0]["response"], "UNKNOWN")
        self.assertTrue(out[0]["conflict"])
        self.assertIn("EX-FLW-01=FAVORABLE", out[0]["reason"])
        self.assertIn("EX-FLW-02=LIMITING", out[0]["reason"])

    def test_agreeing_rules_corroborate_and_degraded_input_lowers_confidence(self):
        a = rule("EX-FLW-01", confidence="MEDIUM", evidence=[ev(1, "a"), ev(2, "b")])
        b = rule("EX-FLW-02", confidence="LOW", evidence=[ev(3, "c")])
        out = rl.evaluate_responses([a, b], self.feats(temp_f=70), self.ctx)[0]
        self.assertEqual((out["response"], out["confidence"], out["evidenceBasis"]["independentStreams"]), ("FAVORABLE", "MEDIUM", 3))
        deg = rl.evaluate_responses([a], ft.evaluate_features(inputs(temp_f=70, status="DEGRADED")), self.ctx)[0]
        self.assertEqual(deg["confidence"], "LOW")

    def test_habitat_rules_requires_gate_and_conflicts(self):
        def hab(rid, direction="FAVOR", requires=None, cls="backwaterHabitat"):
            r = rule(rid, kind="HABITAT", habitat={"habitatClass": cls, "direction": direction, "depthClass": "M0_5_1_5"}, requires=requires or [])
            del r["feature"], r["response"]
            return r
        f = self.feats(temp_f=70, lake_trend="RISING")
        out = rl.evaluate_habitat([hab("EX-HAB-01", requires=[{"featureId": "risingStage", "states": ["TRUE"]}])], f, self.ctx)
        self.assertEqual((out[0]["state"], out[0]["habitatClass"]), ("ACTIVE", "backwaterHabitat"))
        self.assertEqual(rl.evaluate_habitat([hab("EX-HAB-01", requires=[{"featureId": "risingStage", "states": ["FALSE"]}])], f, self.ctx), [])
        unk = rl.evaluate_habitat([hab("EX-HAB-01", requires=[{"featureId": "rapidDischargeIncrease", "states": ["TRUE"]}])], f, self.ctx)
        self.assertEqual((unk[0]["state"], unk[0]["unknownInputs"]), ("CONDITIONAL_UNKNOWN", ["rapidDischargeIncrease"]))
        both = rl.evaluate_habitat([hab("EX-HAB-01"), hab("EX-HAB-02", direction="AVOID")], f, self.ctx)
        self.assertTrue(all(h.get("conflict") for h in both))


def fixture_ruleset():
    spn = rule("EX-SPN-01", kind="PHENOLOGY", applicability={"months": [4, 5, 6], "regions": ["south"]},
               phenology={"event": "spawn", "tempC": {"min": 17.0, "max": 24.0}})
    del spn["feature"], spn["response"]
    night = rule("EX-NGT-01", feature={"featureId": "daypart", "states": ["NIGHT"]}, response="FAVORABLE",
                 applicability={"regions": ["south"]})
    draft = rule("ED-FLW-01", sid="draft_fish", status="DRAFT", evidence=[ev(1, "s", counts=False, read="SNIPPET-ONLY")])
    return rl.RuleSet([rule(), spn, night, draft], "t.1")


class BiologicalStateTests(unittest.TestCase):
    presence = {"example_fish": {"presenceState": "established", "confidence": "high"},
                "draft_fish": {"presenceState": "reported"},
                "old_fish": {"presenceState": "historical"}, "no_rules_fish": {"presenceState": "established"}}

    def build(self, inp=None, daypart="NIGHT", now=NOW):
        return bs.build_lake_state("Example|ST", region="south", waterbody_type="run_of_river", now=now, inputs=inp or inputs(temp_f=70, lake_trend="RISING"),
                                   daypart=daypart, presence=self.presence, ruleset=fixture_ruleset(),
                                   species_info={"example_fish": {"researchMaturity": "RESEARCH", "knowledgeScore": 3.5}})

    def test_state_shape_and_pilot_internal_status(self):
        s = self.build()
        self.assertEqual((s["status"], s["kind"], s["customerPath"]), ("PILOT_INTERNAL", "biological-state", {"consumed": False}))
        self.assertEqual(s["validation"]["status"], "NOT_VALIDATED")
        self.assertEqual(s["provenance"]["rulesVersion"], "t.1")
        ex = next(x for x in s["species"] if x["speciesId"] == "example_fish")
        self.assertTrue(ex["evaluated"])
        self.assertEqual(ex["seasonState"], {"calendarSeason": "SPRING", "spawnWindow": "IN_WINDOW"})      # 21.1 C, April
        self.assertEqual(ex["nightMovementSupported"], "TRUE")
        self.assertEqual(ex["knowledge"]["rules"], {"usable": 3, "draft": 0, "total": 3})
        self.assertTrue(any(r["featureId"] == "warmRise" and r["response"] == "FAVORABLE" for r in ex["responses"]))

    def test_presence_outside_policy_is_reported_not_dropped(self):
        s = self.build()
        old = next(x for x in s["species"] if x["speciesId"] == "old_fish")
        self.assertFalse(old["evaluated"])
        self.assertIn("relevance policy", old["notEvaluatedReason"])

    def test_draft_only_species_has_no_bands_and_says_why(self):
        s = self.build()
        d = next(x for x in s["species"] if x["speciesId"] == "draft_fish")
        self.assertEqual(d["responses"], [])
        self.assertTrue(any("draft rule" in u for u in d["unknowns"]))
        self.assertEqual(d["nightMovementSupported"], "UNKNOWN")
        n = next(x for x in s["species"] if x["speciesId"] == "no_rules_fish")
        self.assertTrue(any("no usable" in u for u in n["unknowns"]))

    def test_missing_upstream_inputs_make_features_unknown_and_are_listed(self):
        s = self.build(inp=normalize_empty())
        self.assertEqual(s["features"]["warmRise"]["state"], "UNKNOWN")
        ex = next(x for x in s["species"] if x["speciesId"] == "example_fish")
        self.assertTrue(any(r["response"] == "UNKNOWN" for r in ex["responses"]))
        self.assertTrue(any("NOT_PUBLISHED" in u for u in s["unknowns"]))
        self.assertTrue(any("rapidDischargeIncrease" in u for u in s["unknowns"]))

    def test_night_rule_unknown_when_daypart_unknown(self):
        s = self.build(daypart=None)
        ex = next(x for x in s["species"] if x["speciesId"] == "example_fish")
        self.assertEqual(ex["nightMovementSupported"], "UNKNOWN")

    def test_normalize_inputs_staleness_and_missing(self):
        snap = {"lakeState": {"trendState": "RISING", "provenance": {"generatedAt": "2026-04-20T01:00:00Z"}},
                "waterTemperature": {"currentTempF": 64.0, "trend24hF": 0.2, "provenance": {"generatedAt": "2026-04-10T01:00:00Z"}}}
        n = bs.normalize_inputs(snap, NOW)
        self.assertEqual(n["lake"]["status"], "PUBLISHED")
        self.assertEqual(n["waterTemp"]["status"], "STALE")         # 10 days old
        self.assertEqual(n["waterClarity"]["status"], "NOT_PUBLISHED")
        self.assertEqual(ft.evaluate_features(n)["waterTempBand"]["state"], "UNKNOWN")


def normalize_empty():
    return bs.normalize_inputs({}, NOW)


class ValidationFoundationTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.reg = vl.FrozenRuleRegister(os.path.join(self.d, "register.jsonl"))
        self.rule = rule()
        self.fz = self.reg.freeze(self.rule, NOW, "tester")
        self.log = vl.PredictionLog(os.path.join(self.d, "pred.jsonl"), self.reg)

    def pred(self, **kw):
        p = {"lakeId": "Example|ST", "speciesId": "example_fish", "predictedAt": "2026-04-20T03:00:00Z",
             "ruleRefs": [{"ruleId": "EX-FLW-01", "ruleVersion": 1, "ruleSha256": self.fz["ruleSha256"]}],
             "seasonState": {"calendarSeason": "SPRING"}, "expected": {"habitat": ["backwaterHabitat"], "spawnState": "IN_WINDOW"},
             "confidence": "LOW", "evidenceBasis": {"rulesVersion": "t.1"}}
        p.update(kw)
        return p

    def test_frozen_rule_cannot_change_but_can_be_reregistered_identically(self):
        self.assertEqual(self.reg.freeze(self.rule, NOW, "tester")["entryHash"], self.fz["entryHash"])        # idempotent
        changed = copy.deepcopy(self.rule)
        changed["response"] = "LIMITING"
        with self.assertRaises(vl.LogError):
            self.reg.freeze(changed, NOW, "tester")
        changed["ruleVersion"] = 2
        self.reg.freeze(changed, NOW, "tester")                                                                # a new version is allowed
        self.assertEqual(self.reg.verify(), 2)

    def test_draft_or_invalid_rules_cannot_be_frozen(self):
        with self.assertRaises(vl.LogError):
            self.reg.freeze(rule("EX-FLW-09", status="DRAFT", evidence=[ev(1, "s", counts=False, read="SNIPPET-ONLY")]), NOW, "t")

    def test_prediction_requires_a_frozen_rule_with_matching_hash_and_time(self):
        self.log.append(self.pred())
        with self.assertRaises(vl.LogError):
            self.log.append(self.pred(ruleRefs=[{"ruleId": "EX-FLW-01", "ruleVersion": 1, "ruleSha256": "0" * 64}], speciesId="other_fish"))
        with self.assertRaises(vl.LogError):
            self.log.append(self.pred(ruleRefs=[{"ruleId": "EX-FLW-77", "ruleVersion": 1, "ruleSha256": "x"}], speciesId="third_fish"))
        with self.assertRaises(vl.LogError):                                        # prediction time before the freeze
            self.log.append(self.pred(predictedAt="2026-01-01T00:00:00Z", speciesId="fourth_fish"))

    def test_prediction_log_is_append_only_and_tamper_evident(self):
        e1 = self.log.append(self.pred())
        with self.assertRaises(vl.LogError):
            self.log.append(self.pred())                                            # no duplicates
        e2 = self.log.append(self.pred(speciesId="second_fish"))
        self.assertEqual(e2["prevHash"], e1["entryHash"])
        self.assertEqual(self.log.verify(), 2)
        path = os.path.join(self.d, "pred.jsonl")
        raw = open(path).read()
        open(path, "w").write(raw.replace('"LOW"', '"HIGH"', 1))                    # rewrite a recorded prediction after the fact
        with self.assertRaises(vl.LogError):
            vl.PredictionLog(path, self.reg)
        open(path, "w").write(raw)
        lines = raw.splitlines()
        open(path, "w").write("\n".join(reversed(lines)) + "\n")                    # reorder
        with self.assertRaises(vl.LogError):
            self.log.verify()
        self.assertFalse(hasattr(self.log, "update") or hasattr(self.log, "delete"))

    def test_invalid_prediction_is_refused(self):
        for bad in (self.pred(expected={"habitat": ["notAClass"]}), self.pred(expected={"surprise": 1}), self.pred(confidence="CERTAIN"),
                    {k: v for k, v in self.pred().items() if k != "ruleRefs"}):
            with self.assertRaises(vl.LogError):
                self.log.append(bad)

    def test_predictions_from_state_use_only_frozen_rules(self):
        rs = fixture_ruleset()
        for r in rs.rules:
            if r["status"] in rl.USABLE_STATUSES:
                self.reg.freeze(r, NOW, "t")
        state = BiologicalStateTests().build()
        preds = vl.predictions_from_state(state, self.reg, {r["ruleId"]: r for r in rs.rules}, NOW)
        self.assertEqual([p["speciesId"] for p in preds], ["example_fish"])
        for p in preds:
            self.log.append(p)
        self.assertEqual(self.log.verify(), 1)

    OBS = {"observationId": "o1", "tripId": "t1", "observerId": "u_ab12", "lakeId": "Example|ST", "observedAt": "2026-04-20T22:00:00Z",
           "speciesId": "example_fish", "speciesIdConfidence": "CONFIRMED", "encountered": True, "count": 3, "effortMinutes": 90,
           "zone": "backwaterHabitat", "depthClass": "M0_5_1_5", "vegetation": "FLOODED", "waterTempF": 66, "levelContext": "RISING",
           "observerConfidence": "HIGH", "notes": "pod near flooded grass"}

    def test_observation_schema_validation(self):
        self.assertEqual(vl.validate_observation(self.OBS), [])
        cases = {"encountered must be a boolean": {"encountered": "yes"}, "count must be 0": {"encountered": False, "count": 4},
                 "requires count >= 1": {"count": 0}, "effortMinutes": {"effortMinutes": 0}, "zone": {"zone": "somewhere"},
                 "speciesIdConfidence": {"speciesIdConfidence": "SURE"}, "GROUP_ONLY/UNCERTAIN needs speciesGroup": {"speciesIdConfidence": "GROUP_ONLY"},
                 "contact details": {"observerId": "mike@example.com"}, "notes max": {"notes": "x" * 281}, "waterTempF": {"waterTempF": 5}}
        for needle, patch in cases.items():
            errs = vl.validate_observation({**self.OBS, **patch})
            self.assertTrue(any(needle in m for m in errs), (needle, errs))
        self.assertTrue(vl.validate_observation({k: v for k, v in self.OBS.items() if k != "tripId"}))

    def test_non_encounters_with_effort_are_valid_evidence(self):
        o = {**self.OBS, "observationId": "o2", "encountered": False, "count": 0}
        self.assertEqual(vl.validate_observation(o), [])
        g = {**self.OBS, "observationId": "o3", "speciesIdConfidence": "GROUP_ONLY", "speciesGroup": "gar"}
        self.assertEqual(vl.validate_observation(g), [])

    def test_observation_store_is_append_only_and_tamper_evident(self):
        st = vl.ObservationStore(os.path.join(self.d, "obs.jsonl"))
        st.append(self.OBS)
        with self.assertRaises(vl.LogError):
            st.append(self.OBS)
        path = os.path.join(self.d, "obs.jsonl")
        raw = open(path).read()
        self.assertIn('"count": 3', raw)
        open(path, "w").write(raw.replace('"count": 3', '"count": 9'))
        with self.assertRaises(vl.LogError):
            vl.ObservationStore(path)

    def test_evaluation_refuses_to_claim_validation_from_a_small_sample(self):
        p = self.log.append(self.pred())
        res = vl.evaluate([p], [dict(self.OBS)])
        self.assertEqual((res["comparisons"], res["encounterComparisons"], res["independentTrips"]), (1, 1, 1))
        self.assertEqual(res["claim"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(res["hitRate"], 1.0)
        self.assertGreater(res["lift"], 1.0)

    def test_evaluation_never_scores_group_level_or_pre_prediction_observations_and_counts_trips_once(self):
        p = self.log.append(self.pred())
        group = {**self.OBS, "observationId": "g", "speciesIdConfidence": "GROUP_ONLY", "speciesGroup": "gar"}
        before = {**self.OBS, "observationId": "b", "observedAt": "2026-04-19T00:00:00Z"}
        same_trip = {**self.OBS, "observationId": "o9", "zone": "tailwaterHabitat"}
        res = vl.evaluate([p], [group, before, dict(self.OBS), same_trip])
        self.assertEqual(res["comparisons"], 2)
        self.assertEqual(res["independentTrips"], 1)            # one trip = one evidence stream
        self.assertEqual(res["hitRate"], 0.5)


class SchemaAndLeakTests(unittest.TestCase):
    def test_committed_schemas_match_the_code(self):
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_schemas.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_feature_a_rule_can_use_is_documented_and_has_an_owner(self):
        for fid, spec in ft.REGISTRY.items():
            self.assertTrue(spec["meaning"] and spec["owner"] and spec["availability"] in ("PUBLISHED", "NOT_PUBLISHED", "AREA"), fid)

    def test_no_private_rules_or_evidence_in_the_public_tree(self):
        """Real species rules/evidence are private. Rule JSON may exist in this tree only under tests/ (synthetic)."""
        bad = []
        for dp, _, fs in os.walk(ROOT):
            if os.sep + "tests" in dp or "__pycache__" in dp or os.sep + "out" in dp:
                continue
            for f in fs:
                p = os.path.join(dp, f)
                txt = open(p, "r", errors="ignore").read()
                if f.endswith(".json") and '"ruleId"' in txt and "schemas" not in dp:
                    bad.append(f"rule file in public tree: {p}")
                if f.endswith(".py") and ("Sector_Research_Data" in txt or "PACKET_BRIEF" in txt):
                    bad.append(f"private path referenced in code: {p}")
                if f.endswith((".json", ".md", ".py")) and "gs://sector-biology-private/biology/v1/releases/" in txt and "tests" not in p:
                    bad.append(f"private release path: {p}")
        self.assertEqual(bad, [])

    def test_fixtures_are_synthetic(self):
        for r in fixture_ruleset().rules:
            self.assertEqual(r["evidence"][0]["packet"], "synthetic")

    @unittest.skipUnless(os.environ.get("BIOLOGY_PRIVATE_RULES"), "set BIOLOGY_PRIVATE_RULES to a staged private rules directory")
    def test_private_rules_validate_if_present(self):
        rs = rl.load_rules_dir(os.environ["BIOLOGY_PRIVATE_RULES"])
        self.assertGreater(len(rs.rules), 0)
        for sid, rules in rs.by_species.items():
            for r in rules:
                if r["status"] in rl.USABLE_STATUSES:
                    self.assertTrue(any(e["counts"] for e in r["evidence"]), r["ruleId"])


if __name__ == "__main__":
    unittest.main()
