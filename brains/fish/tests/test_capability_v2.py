"""Fish Biological Capability V2: evaluator + shared scorer on SYNTHETIC species (FISH_BIOLOGICAL_CAPABILITY_V2.md).

The evaluator executes the real Fish runtime; the shared platform scorer awards points. Expected outputs below follow from the synthetic rules'
own conditions and the rubric text, never from a desired number."""
import copy
import datetime as dt
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import bio_state as bs
import biological_assessment as ba
import brain_platform  # noqa: F401  (shared platform package on the path)
import capability_eval as ce
import capability_fixtures as F
import evaluated_view as evv
import movement_outlook as mo
from sector_brain_platform import fish_capability as fc

NOW = "2026-10-19T00:00:00Z"


def evaluate(rs=None, profiles=None, cohorts=None, knowledge=None, **kw):
    return ce.evaluate(ruleset=rs or F.ruleset(), profiles=profiles or F.profiles(), cohorts=cohorts or F.cohorts(), knowledge=knowledge or dict(F.KNOWLEDGE),
                       evaluated_at=NOW, **kw)


def score(ev, cohorts=None, **kw):
    return fc.build_result(ev, F.rubric(), cohorts or F.cohorts(), generated_at=NOW, **kw)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = evaluate()
        cls.res = score(cls.ev)

    def crit(self, sid, cid):
        return self.ev["species"][sid]["criteria"][cid]


class SpeciesCapability(Base):
    def test_species_biology_executes_and_missing_knowledge_scores_zero_not_unscored(self):          # 1, 11, 27
        self.assertEqual(self.crit("alpha_fish", "BIO-1")["result"], "PASS")
        g = self.ev["species"]["gamma_fish"]
        self.assertEqual(g["evaluationStatus"], "ASSESSED")
        self.assertEqual(g["criteria"]["BIO-1"]["fraction"], 0.0)
        self.assertEqual(g["criteria"]["BIO-1"]["blocker"]["blocker"], "MISSING_KNOWLEDGE")
        self.assertEqual(self.res["species"]["gamma_fish"]["capabilityScore"], 0.0)
        self.assertIsNone(self.res["species"]["na_fish"]["capabilityScore"])             # NOT_ASSESSED: explicitly unscored, never 0

    def test_species_specific_difference(self):          # 2
        self.assertEqual(self.crit("alpha_fish", "BIO-3")["fraction"], 1.0)
        self.assertEqual(self.crit("beta_fish", "BIO-3")["fraction"], 0.5)
        self.assertEqual(self.crit("beta_fish", "BIO-3")["detail"]["identicalSignatureSpecies"], ["twin_fish"])

    def test_habitat_and_depth_preferences(self):          # 3, 4
        self.assertEqual(self.crit("alpha_fish", "HAB-3")["fraction"], 1.0)                 # KNOWS_DEPTH_PREFERENCE (depth-class rule executed)
        self.assertEqual(self.crit("alpha_fish", "HAB-4")["fraction"], 1.0)                 # CAN_EVALUATE_SUPPLIED_DEPTH
        self.assertEqual(self.crit("beta_fish", "HAB-4")["fraction"], 0.0)                  # HAS_NO_DEPTH_RULE
        self.assertEqual(self.crit("beta_fish", "HAB-3")["detail"]["depthKnowledge"], "HAS_NO_DEPTH_RULE")
        self.assertEqual(self.crit("alpha_fish", "HAB-2")["fraction"], 1.0)                 # habitat switches off out of season / without the rise
        self.assertEqual(self.crit("beta_fish", "HAB-2")["fraction"], 0.0)                  # a year-round, unconditional preference is not conditional

    def test_temperature_and_water_level_changes_move_the_output(self):          # 5, 6, 7
        for cid in ("ENV-1", "ENV-2"):
            d = self.crit("alpha_fish", cid)["detail"]
            self.assertEqual(d["execution"], 1.0, cid)
            self.assertTrue(all(t["contrastChanges"] for t in d["rulesTested"] if t["fired"]), cid)
        t1 = self.crit("alpha_fish", "ENV-1")["detail"]["annualCoverageMonths"]
        self.assertEqual(t1, [1, 2, 3, 4, 5, 6, 11, 12])                                    # months the temperature rules really answer
        self.assertAlmostEqual(self.crit("alpha_fish", "ENV-1")["fraction"], 0.5 + 0.5 * 8 / 12, places=6)

    def test_spawn_window_and_seasonal_transitions(self):          # 8, 9
        for cid in ("SPN-1", "SPN-2", "SPN-3", "SPN-4"):
            self.assertEqual(self.crit("alpha_fish", cid)["fraction"], 1.0, cid)
        p = self.crit("alpha_fish", "SPN-4")["detail"]["checks"]
        self.assertTrue(p["regionRestrictedWindowDoesNotFireOutOfRegion"])                # a south-only window is UNKNOWN in the west
        self.assertEqual(self.crit("beta_fish", "SPN-1")["fraction"], 0.0)

    def test_day_night_behaviour_vs_catchability_and_conflict(self):          # 10, 12
        self.assertEqual(self.crit("alpha_fish", "DN-2")["detail"]["evidenceKind"], "BEHAVIORAL")
        self.assertEqual(self.crit("alpha_fish", "DN-2")["fraction"], 1.0)
        c = self.ev["species"]["conflict_fish"]["criteria"]
        self.assertEqual(c["DN-1"]["fraction"], 0.25)                                       # conflict surfaced (0.5 x 0.5), no coverage credit
        self.assertEqual(c["DN-1"]["blocker"]["blocker"], "CONTRADICTORY_EVIDENCE")
        self.assertEqual(c["DN-2"]["fraction"], 0.0)                                        # no claim -> no evidence-kind credit

    def test_unused_knowledge_is_classified(self):          # 27
        self.assertEqual(self.ev["species"]["gated_fish"]["criteria"]["BIO-1"]["blocker"]["blocker"], "REVIEW_BLOCKED")
        self.assertEqual(self.ev["species"]["draft_fish"]["criteria"]["ENV-2"]["blocker"]["blocker"], "KNOWLEDGE_NOT_IN_RUNTIME")
        self.assertEqual(self.ev["species"]["gamma_fish"]["criteria"]["ENV-1"]["blocker"]["blocker"], "KNOWLEDGE_NOT_IN_RUNTIME")   # domain 6/10, no rule

    def test_universal_unknown_earns_no_abstention_credit(self):          # 33
        for sid in ("gamma_fish", "gated_fish", "draft_fish"):
            for cid in ce.ABSTENTION_CRITERIA:
                self.assertEqual(self.ev["species"][sid]["criteria"][cid]["fraction"], 0.0, (sid, cid))
        self.assertEqual(self.crit("alpha_fish", "DN-3")["fraction"], 1.0)                  # broad knowledge: full credit for correct abstention
        b = self.crit("beta_fish", "DN-3")                                                   # one core family of five: abstention credit scales to 1/5
        self.assertAlmostEqual(b["fraction"], 0.2, places=6)
        self.assertEqual(b["detail"]["unscaledFraction"], 1.0)

    def test_narrow_spawn_only_knowledge_earns_narrow_credit(self):          # rubric 2.1 corrections A + B
        c = self.ev["species"]["spawn_fish"]["criteria"]
        self.assertEqual(c["SPN-2"]["fraction"], 1.0)                                       # the window and its temperature trigger are real
        self.assertEqual(c["SPN-1"]["fraction"], 0.5)                                       # ...but Fish cannot say what the fish does while spawning
        self.assertEqual(c["SPN-3"]["fraction"], 0.0)                                       # spawn state alone is not seasonal behaviour
        self.assertAlmostEqual(c["APP-1"]["fraction"], 0.5, places=6)                       # spawn-state-only application is halved
        for cid in ce.ABSTENTION_CRITERIA:
            self.assertLessEqual(c[cid]["fraction"], 0.2 + 1e-9, cid)
        sp = self.res["species"]["spawn_fish"]
        self.assertLess(sp["categoryScores"]["spawnSeason"]["earned"], 2.0)
        self.assertLess(sp["capabilityScore"], 4.0)
        for cid in ("SPN-1", "SPN-3"):                                                     # a species with behaviour around its window keeps full credit
            self.assertEqual(self.crit("alpha_fish", cid)["fraction"], 1.0, cid)

    def test_input_safety_scales_with_environmental_breadth(self):
        self.assertEqual(self.crit("alpha_fish", "ENV-4")["fraction"], 1.0)                # temperature + hydrology + clarity executed
        self.assertNotIn("breadthScale", self.crit("alpha_fish", "ENV-4")["detail"])

    def test_knowledge_application_runs_the_full_pipeline(self):          # 13 (application)
        d = self.crit("alpha_fish", "APP-1")
        self.assertEqual(d["fraction"], 1.0)
        self.assertEqual(d["detail"]["scenario"]["month"], 4)                               # built from alpha's own spawn window
        self.assertEqual(self.crit("gamma_fish", "APP-1")["fraction"], 0.0)

    def test_evaluation_is_deterministic_and_identified(self):          # 38
        again = evaluate()
        self.assertEqual(again["evaluationId"], self.ev["evaluationId"])
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.ev, sort_keys=True))
        self.assertEqual(self.ev["outcomeKind"], "SCENARIO_BEHAVIOR_PASSED")


class Scoring(Base):
    def test_species_score_is_the_sum_of_weight_times_fraction(self):          # 21
        rub = fc.criteria_index(F.rubric())
        s = self.res["species"]["alpha_fish"]
        want = sum(rub[c]["weight"] * self.crit("alpha_fish", c)["fraction"] for c in rub)
        self.assertAlmostEqual(s["capabilityScore"], round(want, 6), places=6)
        self.assertAlmostEqual(sum(v["earned"] for v in s["categoryScores"].values()), s["capabilityScore"], places=5)
        self.assertTrue(all(m["blocker"] for m in s["missingCapabilities"]))

    def test_target_and_all_assessed_aggregates_are_plain_means_of_the_fixed_rosters(self):          # 22, 23, 25
        for cid, roster in (("TARGET", ["alpha_fish", "beta_fish", "gamma_fish"]), ("ALL_ASSESSED", F.ASSESSED)):
            a = self.res["aggregates"][cid]
            vals = [self.res["species"][s]["capabilityScore"] for s in roster]
            self.assertEqual(a["status"], "COMPLETE")
            self.assertAlmostEqual(a["value"], sum(vals) / len(vals), places=5)
            self.assertEqual(a["eligibleSpecies"], len(roster))
            self.assertEqual(a["lowest"]["speciesId"], min(roster, key=lambda s: (self.res["species"][s]["capabilityScore"], s)))
            self.assertEqual(a["below5"], sum(v < 5 for v in vals))
        self.assertEqual(self.res["aggregates"]["TARGET"]["bottomQuartileMean"], 0.0)       # gamma_fish stays visible at the bottom
        self.assertEqual(self.res["brain"]["overallBiologicalCapability"]["definition"], "ALL_ASSESSED")

    def test_failed_evaluation_makes_the_aggregate_incomplete_not_smaller(self):          # 26
        real = ce.evaluate_species

        def boom(h, sid, *a, **k):
            if sid == "beta_fish":
                raise RuntimeError("synthetic failure")
            return real(h, sid, *a, **k)
        with mock.patch.object(ce, "evaluate_species", boom):
            ev = evaluate()
        self.assertEqual(ev["species"]["beta_fish"]["evaluationStatus"], "EVALUATION_FAILED")
        res = score(ev)
        t = res["aggregates"]["TARGET"]
        self.assertEqual((t["status"], t["value"], t["evaluated"]), ("INCOMPLETE", None, 2))
        self.assertEqual(t["unscored"], {"beta_fish": "EVALUATION_FAILED"})
        self.assertLess(t["bounds"]["ifUnscoredWere0"], t["bounds"]["ifUnscoredWere10"])
        self.assertIsNotNone(res["species"]["alpha_fish"]["capabilityScore"])               # available results are preserved

    def test_unknown_species_in_roster_is_reported_not_dropped(self):          # 13, 24
        coh = F.cohorts(target=("alpha_fish", "ghost_fish"))
        ev = evaluate(cohorts=coh)
        self.assertEqual(ev["species"]["ghost_fish"]["evaluationStatus"], "EVALUATION_FAILED")
        self.assertEqual(score(ev, cohorts=coh)["aggregates"]["TARGET"]["status"], "INCOMPLETE")

    def test_fixed_roster_and_versions_are_enforced(self):          # 24, 28
        ev = copy.deepcopy(self.ev)
        del ev["species"]["beta_fish"]
        self.assertTrue(any("missing from the evidence" in e for e in fc.validate_evidence(ev, F.rubric(), F.cohorts())))
        self.assertTrue(any("cohortsVersion" in e for e in fc.validate_evidence(self.ev, F.rubric(), F.cohorts(version="other-v9"))))
        ev = copy.deepcopy(self.ev)
        ev["rubricId"] = "SOMETHING_ELSE"
        self.assertTrue(fc.validate_evidence(ev, F.rubric(), F.cohorts()))
        with self.assertRaises(ValueError):
            score(ev)

    def test_grouped_or_unresolved_taxa_are_unscored_outside_the_rosters(self):          # cohort v2 rule
        coh = F.cohorts()
        coh["cohorts"]["ALL_ASSESSED"]["species"] = [s for s in F.ASSESSED if s != "gamma_fish"]
        coh["cohorts"]["TARGET"]["species"] = ["alpha_fish", "beta_fish"]
        coh["notIndividuallyAssessable"] = {"gamma_fish": "synthetic grouped row"}
        ev = evaluate(cohorts=coh)
        self.assertEqual(ev["species"]["gamma_fish"]["evaluationStatus"], "INSUFFICIENT_EVIDENCE")
        res = score(ev, cohorts=coh)
        self.assertIsNone(res["species"]["gamma_fish"]["capabilityScore"])
        self.assertEqual(res["aggregates"]["ALL_ASSESSED"]["eligibleSpecies"], len(F.ASSESSED) - 1)
        self.assertEqual(next(b for b in res["researchBacklog"] if b["speciesId"] == "gamma_fish")["recommendedNextAction"], "RESOLVE_TAXONOMY")
        bad = copy.deepcopy(coh)
        bad["cohorts"]["ALL_ASSESSED"]["species"].append("gamma_fish")
        self.assertTrue(any("not individually assessable" in e for e in fc.validate_evidence(ev, F.rubric(), bad)))

    def test_knowledge_version_must_be_uniform_inside_an_aggregate(self):          # 29
        sp = self.res["species"]
        a = fc.aggregate("TARGET", F.cohorts()["cohorts"]["TARGET"], sp, F.rubric(), cohorts_version="v", knowledge_versions={"a", "b"})
        self.assertEqual(a["status"], "INCOMPLETE")

    def test_not_assessed_policy_is_enforced(self):          # 14
        ev = copy.deepcopy(self.ev)
        ev["species"]["na_fish"] = copy.deepcopy(ev["species"]["alpha_fish"])
        self.assertTrue(any("NOT_ASSESSED by policy" in e for e in fc.validate_evidence(ev, F.rubric(), F.cohorts())))

    def test_no_handwritten_scores_or_out_of_range_fractions(self):          # 33, 35
        ev = copy.deepcopy(self.ev)
        ev["species"]["beta_fish"]["capabilityScore"] = 9.9
        self.assertTrue(any("score field" in e for e in fc.validate_evidence(ev, F.rubric(), F.cohorts())))
        ev = copy.deepcopy(self.ev)
        ev["species"]["beta_fish"]["criteria"]["BIO-1"]["fraction"] = 1.5
        self.assertTrue(any("fraction" in e for e in fc.validate_evidence(ev, F.rubric(), F.cohorts())))
        ev = copy.deepcopy(self.ev)
        ev["species"]["beta_fish"]["criteria"]["DN-1"] = {"result": "NOT_APPLICABLE", "fraction": None}
        self.assertTrue(any("without a reviewed exemption" in e for e in fc.validate_evidence(ev, F.rubric(), F.cohorts())))
        for k in fc.FORBIDDEN_EVIDENCE_KEYS:             # the evaluator itself never writes points
            self.assertNotIn(f'"{k}"', json.dumps(self.ev["species"]))

    def test_candidate_authority_and_inactive_publication(self):          # 35
        self.assertEqual(self.res["authority"]["status"], "CANDIDATE")
        self.assertEqual(self.res["authority"]["publication"], "INACTIVE")
        r = F.rubric()
        r["status"] = "APPROVED"
        c = F.cohorts()
        c["status"] = "APPROVED"
        self.assertEqual(fc.build_result(self.ev, r, c, generated_at=NOW)["authority"]["status"], "AUTHORITATIVE_APPROVED")

    def test_confidence_and_readiness_are_statuses_that_never_move_the_score(self):          # 19, 20
        s = self.res["species"]["alpha_fish"]
        self.assertIn(s["scientificConfidence"]["status"], ("RESEARCH_UNREVIEWED_NOT_FIELD_VALIDATED", "PARTLY_REVIEWED_NOT_FIELD_VALIDATED"))
        live = evaluate(brain={"lifecycle": "LIVE", "publisherRequired": {"cutoverStatus": "LIVE"}, "customerIntegrationMode": "full"}, observations=50)
        r2 = score(live)
        self.assertEqual(r2["species"]["alpha_fish"]["capabilityScore"], s["capabilityScore"])
        self.assertEqual(r2["aggregates"]["ALL_ASSESSED"]["value"], self.res["aggregates"]["ALL_ASSESSED"]["value"])
        self.assertEqual(self.res["brain"]["productionReadiness"]["status"], "NOT_READY")

    def test_backlog_ranks_targets_first_and_keeps_everyone(self):          # 25 (visibility), 16 (prioritisation)
        b = self.res["researchBacklog"]
        self.assertEqual(len(b), len(self.ev["species"]))
        self.assertEqual({x["speciesId"] for x in b if x["rank"] <= 3}, {"alpha_fish", "beta_fish", "gamma_fish"})
        na = next(x for x in b if x["speciesId"] == "na_fish")
        self.assertEqual(na["recommendedNextAction"], "POLICY_HOLD")


class Improvement(unittest.TestCase):
    """Scores move when Fish becomes demonstrably more (or less) capable; history is never edited."""

    def test_genuine_improvement_raises_species_and_aggregates_with_exact_deltas(self):          # 30, 31
        before = score(evaluate())
        rs = F.base_rules() + [F.resp("BE-TMP-01", "beta_fish", "waterTempBand", ["C21_26", "C26_30"], "FAVORABLE", months=[5, 6, 7, 8, 9])]
        after = score(evaluate(rs=F.ruleset(rs, version="syn.2"), knowledge=dict(F.KNOWLEDGE, researchVersion="0000-00-00.2")), previous=before)
        cr = after["changeRecord"]
        row = next(x for x in cr["species"] if x["speciesId"] == "beta_fish")
        self.assertGreater(row["delta"], 0)
        self.assertAlmostEqual(row["delta"], after["species"]["beta_fish"]["capabilityScore"] - before["species"]["beta_fish"]["capabilityScore"], places=6)
        self.assertIn("ENV-1", {c["criterion"] for c in row["criteriaChanged"]})
        self.assertGreater(cr["aggregates"]["TARGET"]["delta"], 0)                            # one species' improvement is visible immediately
        self.assertEqual(before["species"]["beta_fish"]["capabilityScore"], cr["species"][[x["speciesId"] for x in cr["species"]].index("beta_fish")]["from"])

    def test_regression_lowers_the_score(self):          # 32
        before = score(evaluate())
        rs = [r for r in F.base_rules() if r["ruleId"] != "AL-NGT-01"]
        after = score(evaluate(rs=F.ruleset(rs, version="syn.3")), previous=before)
        row = next(x for x in after["changeRecord"]["species"] if x["speciesId"] == "alpha_fish")
        self.assertLess(row["delta"], 0)
        self.assertLess(after["changeRecord"]["aggregates"]["ALL_ASSESSED"]["delta"], 0)

    def test_small_improvement_is_not_lost_to_rounding(self):          # 20 (precision)
        before = score(evaluate())
        rs = F.base_rules() + [F.resp("AL-CLR-02", "alpha_fish", "clarityBand", ["CLEAR"], "WORKABLE", months=[7])]
        after = score(evaluate(rs=F.ruleset(rs, version="syn.4")), previous=before)
        d = after["changeRecord"]["aggregates"]["ALL_ASSESSED"]["delta"]
        self.assertIsNotNone(d)
        self.assertEqual(round(before["aggregates"]["ALL_ASSESSED"]["value"], 1), round(after["aggregates"]["ALL_ASSESSED"]["value"], 1))
        self.assertGreaterEqual(d, 0)                                                         # exact delta kept even when the display does not move

    def test_rubric_change_is_not_comparable(self):
        a = score(evaluate())
        b = copy.deepcopy(a)
        b["rubricVersion"] = "9.9.9"
        self.assertFalse(fc.compare(a, b)["comparable"])


class RuntimeDefects(unittest.TestCase):
    """Audit 2026-10-19 output defects A and B, and the Fish/Intelligence boundary."""

    def state(self, inputs=None, presence=None, month=4, daypart=None):
        pres = presence or {s: {"presenceState": "established"} for s in ("alpha_fish", "beta_fish")}
        info = {s: {"assessment": "ASSESSED"} for s in pres}
        return bs.build_lake_state("EX|ST", region="south", waterbody_type="run_of_river", now=dt.datetime(2026, month, 15, 12, tzinfo=dt.timezone.utc),
                                   inputs=inputs or ce.inputs_for(), daypart=daypart, presence=pres, ruleset=F.ruleset(), species_info=info)

    def test_zero_environmental_inputs_is_a_low_seasonal_prior_with_reasons(self):          # 16, 17
        st = self.state()
        o = mo.species_outlook(next(s for s in st["species"] if s["speciesId"] == "alpha_fish"), 4)
        self.assertNotEqual(o["state"], "UNKNOWN")
        self.assertEqual((o["basis"], o["confidence"]), ("SEASONAL_PRIOR", "LOW"))
        self.assertIn(mo.SEASONAL_PRIOR_WHY, o["why"])
        self.assertTrue(o["confidenceLimitations"])
        warm = self.state(ce.inputs_for(temp_f=64.0, stage="RISING"))
        o2 = mo.species_outlook(next(s for s in warm["species"] if s["speciesId"] == "alpha_fish"), 4)
        self.assertEqual(o2["basis"], "CURRENT_CONDITIONS")

    def test_presence_suppressed_species_says_why(self):          # 15
        st = self.state(presence={"alpha_fish": {"presenceState": "historical"}})
        v = evv.intelligence_view(st)
        row = v["species"][0]
        self.assertEqual(row["status"], "NOT_EVALUATED")
        self.assertIn("relevance policy", row["notEvaluatedReason"])
        self.assertEqual(evv.validate_view(v), [])
        a = ba.build_assessments(st, F.ruleset(), knowledge_version="k")
        self.assertIn("relevance policy", a["species"][0]["notEvaluatedReason"])

    def test_explanations_are_required(self):          # 18
        v = evv.intelligence_view(self.state(ce.inputs_for(temp_f=64.0, stage="RISING")))
        self.assertEqual(evv.validate_view(v), [])
        bad = copy.deepcopy(v)
        sp = next(s for s in bad["species"] if s["movementOutlook"]["state"] != "UNKNOWN")
        sp["movementOutlook"]["why"] = []
        self.assertTrue(any("must say why" in e for e in evv.validate_view(bad)))

    def test_assessment_contract_never_carries_a_bowfishing_decision(self):          # boundary
        a = ba.build_assessments(self.state(ce.inputs_for(temp_f=64.0, stage="RISING"), daypart="NIGHT"), F.ruleset(), knowledge_version="k",
                                 supplied_depth={"depthM": 0.3})
        self.assertEqual(ba.validate_assessment(a), [])
        al = next(s for s in a["species"] if s["speciesId"] == "alpha_fish")
        self.assertEqual(al["depthTendencies"]["suppliedDepth"]["interpretation"], "WITHIN_PREFERRED_DEPTH")
        self.assertTrue(al["evidenceReferences"])
        for k in ("lat", "rank", "recommendation", "opportunityScore", "bankId"):
            bad = copy.deepcopy(a)
            bad["species"][0][k] = 1
            self.assertTrue(any("boundary" in e for e in ba.validate_assessment(bad)), k)

    def test_evidence_kind_classification(self):
        mk = lambda st: [{"evidence": [{"counts": True, "studyType": st}]}]      # noqa: E731
        self.assertEqual(ba.evidence_kind(mk("acoustic telemetry")), "BEHAVIORAL")
        self.assertEqual(ba.evidence_kind(mk("paired day/night electrofishing")), "CATCHABILITY")
        self.assertEqual(ba.evidence_kind(mk("reference")), "UNCLASSIFIED")
        self.assertEqual(ba.evidence_kind([]), "NONE")


class Boundaries(unittest.TestCase):
    def test_capability_code_never_touches_rtdb_publisher_network_or_an_llm(self):          # 36, 38
        import ast
        rt = os.path.join(F.REPO, "brains", "fish", "runtime")
        srcs = [os.path.join(rt, f) for f in ("capability_eval.py", "capability_run.py", "biological_assessment.py")]
        srcs.append(os.path.join(F.REPO, "jobs", "brain_platform", "sector_brain_platform", "fish_capability.py"))
        banned = ("rtdb", "publisher", "publisher_live", "publication", "gcp", "urllib", "requests", "http", "socket", "anthropic", "openai", "ollama", "google")
        for p in srcs:
            for node in ast.walk(ast.parse(open(p).read())):
                names = [a.name for a in node.names] if isinstance(node, (ast.Import, ast.ImportFrom)) else []
                mod = node.module or "" if isinstance(node, ast.ImportFrom) else ""
                for n in names + [mod]:
                    self.assertFalse(any(part in banned for part in n.split(".")), (os.path.basename(p), n))

    def test_existing_maturity_rubric_is_untouched(self):          # 34
        legacy = json.load(open(os.path.join(F.REPO, "docs", "brains", "scoring", "biological-state-score-v1.json")))
        self.assertEqual(legacy.get("scoreVersion", legacy.get("rubricId", legacy.get("id"))) is not None, True)
        from sector_brain_platform import scoring
        self.assertTrue(callable(scoring.score_biological))
        self.assertNotIn("fish_capability", open(scoring.__file__).read())


class LocalEntryPoint(unittest.TestCase):
    """Pulse-compatible: one local command, a synthetic private-shaped bundle, local files only."""

    def test_capability_run_end_to_end_on_a_synthetic_bundle(self):          # 38
        import test_biological_brain as T
        import capability_run as cr
        d, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        try:
            rules_ = F.base_rules()
            by = {}
            for r in rules_:
                by.setdefault(r["speciesId"], []).append(r)
            extra, files = {}, []
            import hashlib
            for sid, rs in by.items():
                raw = json.dumps({"speciesId": sid, "rules": rs}).encode()
                extra[f"rules/{sid}.json"] = raw
                files.append({"path": f"{sid}.json", "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
            extra["rules/rules_manifest.json"] = json.dumps({"schemaVersion": 1, "rulesVersion": "syn.1", "files": files,
                                                             "seasonAssertions": {"AL-CLR-01": "YEAR_ROUND", "BE-HAB-01": "YEAR_ROUND", "TW-HAB-01": "YEAR_ROUND"}}).encode()
            profs = [dict(T.synthetic_profile(s), assessment="ASSESSED") for s in F.ASSESSED] + [T.not_assessed("na_fish")]
            T.write_bundle(d, profs, extra=extra)
            coh = os.path.join(out, "cohorts.json")
            json.dump(F.cohorts(), open(coh, "w"))
            rc = cr.main(["--bundle", d, "--out", out, "--cohorts", coh, "--now", NOW])
            self.assertEqual(rc, 0)
            res = json.load(open(os.path.join(out, "result.json")))
            self.assertEqual(res["aggregates"]["TARGET"]["status"], "COMPLETE")
            self.assertEqual(res["authority"]["publication"], "INACTIVE")
            self.assertIn("Research backlog", open(os.path.join(out, "report.md")).read())
            overlay = {"overlayId": "cand-1", "status": "HYPOTHETICAL_CANDIDATE", "seasonAssertions": {"GA-HYD-01": "YEAR_ROUND"}}
            json.dump(overlay, open(os.path.join(out, "overlay.json"), "w"))
            out2 = os.path.join(out, "cand")
            rc2 = cr.main(["--bundle", d, "--out", out2, "--cohorts", coh, "--now", NOW, "--overlay", os.path.join(out, "overlay.json"),
                           "--previous", os.path.join(out, "result.json")])
            self.assertEqual(rc2, 0)
            res2 = json.load(open(os.path.join(out2, "result.json")))
            self.assertTrue(res2["knowledgeVersion"].endswith("+cand-1"))
            g = next(x for x in res2["changeRecord"]["species"] if x["speciesId"] == "gated_fish")
            self.assertGreater(g["delta"], 0)                                    # a reviewer's season assertion makes gated knowledge executable
            with self.assertRaises(SystemExit):
                cr.main(["--bundle", d, "--out", out2, "--cohorts", coh, "--expect-manifest-sha", "f" * 64])
        finally:
            shutil.rmtree(d)
            shutil.rmtree(out)


if __name__ == "__main__":
    unittest.main()


class Schemas(unittest.TestCase):
    """The Ops-facing result and the Intelligence-facing assessment validate against their published JSON Schemas."""

    @staticmethod
    def validator():
        import sys as _s
        _s.path.insert(0, os.path.join(F.REPO, "tools", "architecture"))
        from jsonschema_lite import validate
        return validate

    def test_result_matches_the_ops_schema(self):          # 37
        validate = self.validator()
        schema = json.load(open(os.path.join(F.REPO, "contracts", "schemas", "fish-capability-result-v2.schema.json")))
        res = score(evaluate())
        self.assertEqual(validate(res, schema), [])
        bad = copy.deepcopy(res)
        bad["authority"]["status"] = "PRODUCTION"
        self.assertTrue(validate(bad, schema))

    def test_assessment_matches_the_intelligence_schema(self):
        validate = self.validator()
        schema = json.load(open(os.path.join(F.REPO, "brains", "fish", "contracts", "fish-biological-assessment-v1.json")))
        st = RuntimeDefects().state(ce.inputs_for(temp_f=64.0, stage="RISING"), daypart="NIGHT",
                                    presence={"alpha_fish": {"presenceState": ce.EVALUATION_PRESENCE}, "beta_fish": {"presenceState": "historical"}})
        a = ba.build_assessments(st, F.ruleset(), knowledge_version="k", supplied_depth={"depthClass": "LT_0_5M"})
        self.assertEqual(validate(a, schema), [])


class PublishableEvidence(unittest.TestCase):
    def test_sanitised_evidence_reproduces_the_result_and_carries_no_private_detail(self):          # public-repo boundary
        import re
        ev = evaluate()
        pub = ce.publishable_evidence(ev)
        self.assertEqual(score(pub)["aggregates"], score(ev)["aggregates"])
        self.assertEqual(pub["evaluationId"], ev["evaluationId"])
        txt = json.dumps(pub)
        self.assertIsNone(re.search(r'"[A-Z]{2,4}-[A-Z]{2,5}-\d{2}[A-Za-z]?"', txt))           # no rule ids
        for k in ('"detail"', '"scenario"', '"behavior"', '"rulesByFamily"', '"annualCoverage"', '"results"'):
            self.assertNotIn(k, txt)
