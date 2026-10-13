"""Biological State lifecycle is derived from verified capability, never set by hand (synthetic fixtures only)."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import biological_brain as bb      # noqa: E402
import bio_state as bs             # noqa: E402
import capability                  # noqa: E402
import features as ft              # noqa: E402
import rules as rl                 # noqa: E402
import run                         # noqa: E402
import validation_log as vl        # noqa: E402
from test_biological_brain import NOW, not_assessed, synthetic_profile, write_bundle   # noqa: E402
from test_rules_state_validation import fixture_ruleset, inputs                       # noqa: E402

T0 = dt.datetime(2026, 4, 20, 3, 0, tzinfo=dt.timezone.utc)


def capability_files(tamper=None):
    rs = fixture_ruleset()
    rules = rs.rules
    by_sp = {}
    for r in rules:
        by_sp.setdefault(r["speciesId"], []).append(r)
    files, man_files = {}, []
    for sid, rr in by_sp.items():
        raw = json.dumps({"speciesId": sid, "rules": rr}).encode()
        files[f"rules/{sid}.json"] = raw
        man_files.append({"path": f"{sid}.json"})
    files["rules/rules_manifest.json"] = json.dumps({"rulesVersion": rs.rules_version, "files": man_files}).encode()
    d = tempfile.mkdtemp()
    reg = vl.FrozenRuleRegister(os.path.join(d, "r.jsonl"))
    for r in rules:
        if r["status"] in rl.USABLE_STATUSES:
            reg.freeze(r, T0, "t")
    files["validation/frozen_rules.jsonl"] = open(os.path.join(d, "r.jsonl"), "rb").read()
    shutil.rmtree(d)
    st = bs.build_lake_state("Example|ST", region="south", waterbody_type="run_of_river", now=T0, inputs=inputs(temp_f=70, lake_trend="RISING"),
                             daypart="NIGHT", presence={"example_fish": {"presenceState": "established"}}, ruleset=rs,
                             species_info={"example_fish": {"assessment": "ASSESSED"}})
    files["state/pilot_Example_ST.json"] = json.dumps(st).encode()
    if tamper:
        tamper(files)
    return files


class CapabilityTests(unittest.TestCase):
    def test_no_rules_means_not_started_and_the_old_behaviour(self):
        c = capability.assess({})
        self.assertEqual((c["status"], c["validation"]), ("NOT_STARTED", "NOT_STARTED"))

    def test_verified_capability_is_in_progress_never_live_or_validated(self):
        c = capability.assess(capability_files())
        self.assertEqual(c["blockers"], [])
        self.assertEqual((c["status"], c["validation"]), ("IN_PROGRESS", "NOT_STARTED"))
        self.assertEqual(c["facts"]["pilotLakes"], ["Example|ST"])
        self.assertNotIn(c["status"], ("LIVE", "VALIDATED"))

    def blockers(self, tamper):
        c = capability.assess(capability_files(tamper))
        self.assertEqual(c["status"], "NOT_STARTED")
        return " | ".join(c["blockers"])

    def test_each_missing_or_tampered_piece_returns_to_not_started(self):
        self.assertIn("frozen rule register", self.blockers(lambda f: f.pop("validation/frozen_rules.jsonl")))
        self.assertIn("register invalid", self.blockers(lambda f: f.__setitem__("validation/frozen_rules.jsonl", f["validation/frozen_rules.jsonl"].replace(b'"frozenBy": "t"', b'"frozenBy": "x"'))))
        self.assertIn("pilot", self.blockers(lambda f: f.pop("state/pilot_Example_ST.json")))

        def wrong_rules_version(f):
            st = json.loads(f["state/pilot_Example_ST.json"])
            st["provenance"]["rulesVersion"] = "other"
            f["state/pilot_Example_ST.json"] = json.dumps(st).encode()
        self.assertIn("does not verify", self.blockers(wrong_rules_version))

        def consumed(f):
            st = json.loads(f["state/pilot_Example_ST.json"])
            st["customerPath"]["consumed"] = True
            f["state/pilot_Example_ST.json"] = json.dumps(st).encode()
        self.assertIn("does not verify", self.blockers(consumed))

        def no_inputs(f):
            st = json.loads(f["state/pilot_Example_ST.json"])
            st["inputs"] = {k: {"status": "NOT_PUBLISHED"} for k in st["inputs"]}
            f["state/pilot_Example_ST.json"] = json.dumps(st).encode()
        self.assertIn("published specialist input", self.blockers(no_inputs))

    def test_a_rule_changed_after_freezing_is_not_covered(self):
        def edit_rule(f):
            d = json.loads(f["rules/example_fish.json"])
            d["rules"][0]["response"] = "LIMITING"
            f["rules/example_fish.json"] = json.dumps(d).encode()
        self.assertIn("not frozen with a matching hash", self.blockers(edit_rule))

    def test_draft_only_rules_do_not_count(self):
        def only_draft(f):
            d = json.loads(f["rules/draft_fish.json"])
            f.clear()
            f["rules/draft_fish.json"] = json.dumps(d).encode()
            f["rules/rules_manifest.json"] = json.dumps({"rulesVersion": "t.1", "files": [{"path": "draft_fish.json"}]}).encode()
        self.assertIn("no RECONCILED/APPROVED rule", self.blockers(only_draft))


class PublisherReflectsCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def updates(self, extra):
        write_bundle(self.dir, [synthetic_profile(), not_assessed()], extra=extra)
        b = bb.load_bundle(run.local_reader(self.dir))
        return b, bb.build_updates(b, now=NOW, uri_root="local:x", deployment="t", descriptor={}, duration_ms=1, published=None, existing_species=set(), event_id="e1")

    def test_without_capability_artifacts_publisher_is_unchanged(self):
        _, up = self.updates({})
        r = up["/brains/biological-state"]["responsibilities"]["biologicalState"]
        self.assertEqual(r["status"], "NOT_STARTED")
        self.assertNotIn("validationFoundation", up["/validation/biological-state"])

    def test_with_verified_capability_state_is_in_progress_and_validation_stays_not_validated(self):
        b, up = self.updates(capability_files())
        r = up["/brains/biological-state"]["responsibilities"]["biologicalState"]
        self.assertEqual((r["status"], r["validation"]), ("IN_PROGRESS", "NOT_STARTED"))
        self.assertEqual(up["/validation/biological-state"]["status"], "NOT_VALIDATED")
        self.assertEqual(up["/validation/biological-state"]["validationFoundation"]["frozenRules"], 3)
        self.assertIn("/brains/biological-state", up)
        # no per-lake state path and no customer path is ever written
        self.assertFalse([p for p in up if p.startswith("/lakes/") or p.startswith("/snapshots/") or p.startswith("/conditions")])

    def test_registry_publishes_generic_facts_for_ops(self):
        _, up = self.updates(capability_files())
        facts = {f["label"]: f["value"] for f in up["/brains/biological-state"]["facts"]}
        self.assertEqual(facts["Usable rules"], 3)
        self.assertEqual(facts["Frozen rules"], 3)
        self.assertEqual(facts["Observations logged"], 0)
        self.assertEqual(facts["Independent trips"], 0)
        self.assertEqual(facts["Validated species"], 0)
        self.assertEqual(facts["Pilot lakes"], "Example|ST")
        _, none = self.updates({})
        self.assertNotIn("facts", none["/brains/biological-state"])                    # unchanged when there is no capability

    def test_public_payload_has_counts_only_never_rule_text(self):
        _, up = self.updates(capability_files())
        blob = json.dumps(up)
        self.assertNotIn('"statement"', blob)
        sp = json.dumps(up["/species/example_fish"])
        for private_text in ('"statement"', '"evidenceId"', '"packet"', '"streamId"', '"conflicts"'):
            self.assertNotIn(private_text, sp)
        self.assertEqual(up["/species/example_fish"]["machineRules"], {"usable": 3, "draft": 0})
        import bands
        rb = up["/species/example_fish"]["responseBands"]
        self.assertEqual(bands.validate_response_bands(rb), [])
        self.assertEqual(rb["status"], "PROPOSED")             # no rule is APPROVED, so no band is APPROVED
        self.assertLess(len(sp), 16000)

    def test_canonical_scorer_moves_only_because_capability_exists(self):
        sys.path.insert(0, os.path.join(HERE, "..", "..", "brain_platform"))
        from sector_brain_platform import scoring
        for extra, expect_status in (({}, "NOT_STARTED"), (capability_files(), "IN_PROGRESS")):
            _, up = self.updates(extra)
            facts = {"registry": up["/brains/biological-state"], "species": {k.split("/")[-1]: v for k, v in up.items() if k.startswith("/species/")}}
            sc = scoring.score_biological(facts, NOW)
            bd = sc["scoreBreakdown"]["biologicalStateImpl"]
            self.assertEqual(facts["registry"]["responsibilities"]["biologicalState"]["status"], expect_status)
            self.assertEqual(bd["value"], 4 if expect_status == "IN_PROGRESS" else 0)
            if expect_status == "NOT_STARTED":
                self.assertTrue(any(g["gate"] == "biologicalState" for g in sc["scoreBlockers"] if "gate" in g))
            else:
                self.assertFalse(any(g.get("gate") == "biologicalState" for g in sc["scoreBlockers"]))
                self.assertTrue(any(g.get("gate") == "speciesValidation" for g in sc["scoreBlockers"]))      # the 6.0 cap still binds


if __name__ == "__main__":
    unittest.main()


class StageBundleTests(unittest.TestCase):
    def test_stage_a_release_with_capability_and_load_it_with_the_fail_closed_loader(self):
        src = tempfile.mkdtemp()
        out = tempfile.mkdtemp()
        try:
            write_bundle(src, [synthetic_profile(), not_assessed()])
            from tools.stage_bundle import stage
            b = stage(os.path.join(src, "releases", "0000-00-00.1"), out, "0000-00-01.1", extra_files=capability_files(), now=NOW)
            self.assertEqual(b.research_version, "0000-00-01.1")
            self.assertEqual(b.capability["status"], "IN_PROGRESS")
            self.assertTrue(json.load(open(os.path.join(out, "latest.json")))["staged"])
            with self.assertRaises(bb.BundleError):                       # an extra file may never overwrite a source artifact
                stage(os.path.join(src, "releases", "0000-00-00.1"), tempfile.mkdtemp(), "0000-00-02.1", extra_files={"registry.json": b"{}"})
        finally:
            shutil.rmtree(src), shutil.rmtree(out)


class AuditBundleTests(unittest.TestCase):
    def stage(self, extra):
        src, out = tempfile.mkdtemp(), tempfile.mkdtemp()
        write_bundle(src, [synthetic_profile(), synthetic_profile("draft_fish"), not_assessed()])
        from tools.stage_bundle import stage
        man_patch = {"counts": {"machineRules": {"total": 4, "usable": 3, "retired": 0}}}
        stage(os.path.join(src, "releases", "0000-00-00.1"), out, "0000-00-01.1", extra_files=extra, manifest_patch=man_patch, now=NOW)
        shutil.rmtree(src)
        return out

    def test_a_consistent_candidate_passes_every_check(self):
        from tools.audit_bundle import audit
        out = self.stage(capability_files())
        try:
            rep = audit(out)
            self.assertTrue(rep["ok"], [c for c in rep["checks"] if not c["ok"]])
            self.assertEqual(rep["capability"], "IN_PROGRESS")
        finally:
            shutil.rmtree(out)

    def test_wrong_declared_counts_and_missing_register_fail(self):
        from tools.audit_bundle import audit
        files = capability_files()
        files.pop("validation/frozen_rules.jsonl")
        out = self.stage(files)
        try:
            rep = audit(out)
            self.assertFalse(rep["ok"])
            self.assertTrue(any(not c["ok"] and "frozen register" in c["check"] for c in rep["checks"]))
        finally:
            shutil.rmtree(out)

    def test_a_draft_rule_cannot_become_usable_silently(self):
        from tools.audit_bundle import audit
        files = capability_files()
        d = json.loads(files["rules/draft_fish.json"])
        d["rules"][0]["status"] = "RECONCILED"               # promoted without evidence: the validator must refuse the whole rules set
        files["rules/draft_fish.json"] = json.dumps(d).encode()
        out = self.stage(files)
        try:
            rep = audit(out)
            self.assertFalse(rep["ok"])
        finally:
            shutil.rmtree(out)
