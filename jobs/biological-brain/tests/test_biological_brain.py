"""Biological Brain tests (stdlib unittest; no network).

  cd jobs/biological-brain && python3 -m unittest discover -s tests -v

Every fixture is SYNTHETIC (fake species, fake scores) and built in a temp dir, so no proprietary Sector biology
lives in this public repository.
"""
import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import biological_brain as bb      # noqa: E402
import brain_platform as bp        # noqa: E402
import orchestration as orch       # noqa: E402
import run                         # noqa: E402

NOW = dt.datetime(2026, 10, 12, 18, 0, tzinfo=dt.timezone.utc)
SCORES = [6, 5, 4, 3, 2, 1, 0, 2]      # synthetic; weighted = (120+100+60+45+20+10+0+10)/100 = 3.65 -> 3.5


def synthetic_profile(sid="example_fish", scores=SCORES):
    doms = {}
    for (did, label, w), s in zip(bb.DOMAINS, scores):
        doms[did] = dict(label=label, weight=w, score=s, status="SCORED" if s else "UNKNOWN", potentialGainPerPoint=round(w / 100, 2),
                         basis=["synthetic"], contradictions=["c1"] if s == 6 else [], limits=[])
    exact = sum(s * w for (_, _, w), s in zip(bb.DOMAINS, scores)) / 100
    return dict(schemaVersion=1, speciesId=sid, displayName="Example fish", scientificName="Exemplum piscis", aliases=["Example fish", "sample fish"],
                appKeys={"iosSpeciesGroupLabel": "Example Group"}, taxonomyStatus="RESOLVED", taxonomyNotes=[], assessment="ASSESSED",
                researchMaturity="RESEARCH", researchVersion="0000-00-00.1", scoringVersion="species-v2", lastReviewedAt="2026-10-12",
                knowledge=dict(rubric="species-v2", overallExact=round(exact, 2), overallRounded=bb.round_half(exact), domains=doms,
                               strongest=["seasonalLocationReproduction"], weakest=["dayNightMovement"], unknownDomains=["clarityLightWind"]),
                rules=[{"ruleId": "EX-1"}], evidence=dict(relationshipRecordCount=3), gaps=["gap one", "gap two", "gap three", "gap four"],
                nextResearchPriority="gap one", policyNote="synthetic", separateAssessments={}, discrepancies=["DISC-X"],
                history=[dict(date="2026-10-11", rubric="species-v2", overallRounded=3.5, overallExact=3.65, reason="synthetic")])


def not_assessed(sid="example_group"):
    return dict(schemaVersion=1, speciesId=sid, displayName="Example group", scientificName="Exempla spp.", aliases=[], appKeys={},
                taxonomyStatus="GROUP_TOO_COARSE", assessment="NOT_ASSESSED", researchMaturity="NOT_STARTED", researchVersion="0000-00-00.1",
                scoringVersion="species-v2", knowledge=dict(rubric="species-v2", overallExact=None, overallRounded=None, domains={}),
                rules=[], evidence={}, gaps=[], history=[])


def write_bundle(root, profiles, research_version="0000-00-00.1", tamper=None):
    rel = f"releases/{research_version}"
    base = os.path.join(root, rel)
    os.makedirs(os.path.join(base, "species"), exist_ok=True)
    files = []

    def put(path, obj):
        data = json.dumps(obj).encode()
        open(os.path.join(base, path), "wb").write(data)
        files.append(dict(path=path, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), visibility="private"))
    for p in profiles:
        put(f"species/{p['speciesId']}.json", p)
    put("registry.json", dict(schemaVersion=1, researchVersion=research_version, species=[dict(speciesId=p["speciesId"], profile=f"species/{p['speciesId']}.json") for p in profiles],
                              speciesGroups={"example": dict(label="Example Group", members=[profiles[0]["speciesId"]])}))
    put("discrepancies.json", dict(discrepancies=[dict(id="DISC-X", status="OPEN", species=[profiles[0]["speciesId"]], title="synthetic discrepancy", decision="none", **{"class": "TEST"})]))
    manifest = dict(schemaVersion=1, brainId="biological-state", researchVersion=research_version, scoringVersion="species-v2", files=files,
                    knownLimitations=["synthetic"])
    mdata = json.dumps(manifest).encode()
    open(os.path.join(base, "manifest.json"), "wb").write(mdata)
    if tamper:
        tamper(base)
    json.dump(dict(schemaVersion=1, brainId="biological-state", researchVersion=research_version, manifest=f"{rel}/manifest.json",
                   manifestSha256=hashlib.sha256(mdata).hexdigest()), open(os.path.join(root, "latest.json"), "w"))


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def load(self):
        return bb.load_bundle(run.local_reader(self.dir))

    def test_valid_bundle_loads_and_passes_values_through(self):
        write_bundle(self.dir, [synthetic_profile(), not_assessed()])
        b = self.load()
        self.assertEqual(b.research_version, "0000-00-00.1")
        self.assertEqual(b.profiles["example_fish"]["knowledge"]["overallExact"], 3.65)
        self.assertEqual(b.profiles["example_fish"]["knowledge"]["overallRounded"], 3.5)

    def test_tampered_artifact_is_refused(self):
        def tamper(base):
            with open(os.path.join(base, "species", "example_fish.json"), "a") as fh:
                fh.write(" ")
        write_bundle(self.dir, [synthetic_profile()], tamper=tamper)
        with self.assertRaisesRegex(bb.BundleError, "hash/size mismatch"):
            self.load()

    def test_overall_must_equal_weighted_sum(self):
        p = synthetic_profile(); p["knowledge"]["overallExact"] = 3.9
        write_bundle(self.dir, [p])
        with self.assertRaisesRegex(bb.BundleError, "weighted sum"):
            self.load()

    def test_rounding_ties_up(self):
        self.assertEqual(bb.round_half(3.25), 3.5)
        self.assertEqual(bb.round_half(6.75), 7.0)
        self.assertEqual(bb.round_half(6.74), 6.5)
        p = synthetic_profile(); p["knowledge"]["overallRounded"] = 4.0
        write_bundle(self.dir, [p])
        with self.assertRaisesRegex(bb.BundleError, "overallRounded"):
            self.load()

    def test_unknown_iff_zero(self):
        p = synthetic_profile(); p["knowledge"]["domains"]["clarityLightWind"]["status"] = "SCORED"
        write_bundle(self.dir, [p])
        with self.assertRaisesRegex(bb.BundleError, "UNKNOWN exactly when"):
            self.load()

    def test_weights_and_dimensions_are_v2(self):
        p = synthetic_profile(); p["knowledge"]["domains"]["foodFeedingLocation"]["weight"] = 15
        write_bundle(self.dir, [p])
        with self.assertRaisesRegex(bb.BundleError, "weight"):
            self.load()
        p = synthetic_profile(); p["knowledge"]["domains"].pop("clarityLightWind")
        write_bundle(self.dir, [p])
        with self.assertRaisesRegex(bb.BundleError, "v2 dimensions"):
            self.load()

    def test_fractional_scores_refused(self):
        p = synthetic_profile(); p["knowledge"]["domains"]["habitatDepthCover"]["score"] = 3.5
        write_bundle(self.dir, [p])
        with self.assertRaisesRegex(bb.BundleError, "whole number"):
            self.load()

    def test_no_silent_promotion(self):
        p = synthetic_profile(); p["researchMaturity"] = "VALIDATED"
        write_bundle(self.dir, [p])
        with self.assertRaisesRegex(bb.BundleError, "not used yet"):
            self.load()

    def test_species_id_snake_case(self):
        p = synthetic_profile(sid="Example-Fish")
        write_bundle(self.dir, [p])
        with self.assertRaisesRegex(bb.BundleError, "snake_case"):
            self.load()

    def test_not_assessed_carries_no_scores(self):
        n = not_assessed(); n["knowledge"]["overallExact"] = 0.0
        write_bundle(self.dir, [synthetic_profile(), n])
        with self.assertRaisesRegex(bb.BundleError, "NOT_ASSESSED"):
            self.load()


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        write_bundle(self.dir, [synthetic_profile(), not_assessed()])
        self.b = bb.load_bundle(run.local_reader(self.dir))

    def tearDown(self):
        shutil.rmtree(self.dir)

    def updates(self, published=None, existing=None):
        return bb.build_updates(self.b, now=NOW, uri_root="gs://bucket/biology/v1", deployment="brain/biological@test", descriptor=orch.DESCRIPTOR,
                                duration_ms=5, published=published, existing_species=existing, event_id="e1")

    def test_paths_written(self):
        up = self.updates()
        self.assertEqual(sorted(up), sorted(["/species/example_fish", "/species/example_group", "/brains/biological-state",
                                             "/validation/biological-state", "/health/brains/biological-state", "/activity/e1"]))
        bb.check_keys(up)

    def test_species_summary_is_lightweight_and_honest(self):
        s = self.updates()["/species/example_fish"]
        self.assertEqual(s["knowledge"]["overallExact"], 3.65)
        self.assertEqual(s["knowledge"]["domains"]["clarityLightWind"]["status"], "UNKNOWN")
        self.assertNotIn("basis", s["knowledge"]["domains"]["habitatDepthCover"])     # detail stays private
        self.assertNotIn("rules", s)
        self.assertEqual(s["ruleCount"], 1)
        self.assertEqual(len(s["topGaps"]), 3)
        self.assertEqual(s["openDiscrepancies"]["DISC-X"]["status"], "OPEN")
        self.assertTrue(s["profileRef"].startswith("gs://bucket/"))
        self.assertLess(len(json.dumps(s)), 8000)

    def test_unknown_values_are_absent_not_defaulted(self):
        s = self.updates()["/species/example_group"]
        self.assertNotIn("overallExact", s["knowledge"])
        self.assertNotIn("domains", s["knowledge"])
        self.assertEqual(s["assessment"], "NOT_ASSESSED")

        def no_none(o):
            if isinstance(o, dict):
                for v in o.values(): no_none(v)
            elif isinstance(o, list):
                for v in o: no_none(v)
            else:
                self.assertIsNotNone(o)
        for v in self.updates().values():
            no_none(v)

    def test_registry_entry_separates_concepts(self):
        r = self.updates()["/brains/biological-state"]
        self.assertEqual(r["displayName"], "Biological Brain")
        self.assertEqual(r["brainId"], "biological-state")
        self.assertEqual(r["supportedLakeCount"], 0)
        self.assertEqual(r["responsibilities"]["biologicalState"]["status"], "NOT_STARTED")
        self.assertEqual(r["breakdowns"]["researchMaturity"], {"RESEARCH": 1, "NOT_STARTED": 1})
        self.assertEqual(self.updates()["/validation/biological-state"]["status"], "NOT_VALIDATED")
        self.assertNotIn("readinessCounts", r)
        self.assertEqual(r["rubric"]["dimensionOrder"], bb.DOMAIN_IDS)

    def test_retired_species_removed_and_event_only_on_version_change(self):
        up = self.updates(published={"researchVersion": "0000-00-00.1"}, existing={"example_fish", "old_fish"})
        self.assertIsNone(up["/species/old_fish"])
        self.assertNotIn("/activity/e1", up)

    def test_illegal_keys_refused(self):
        with self.assertRaises(bb.BundleError):
            bb.check_keys({"/species/x": {"a.b": 1}})


class PlanTests(unittest.TestCase):
    P = {"researchVersion": "v2", "manifestSha256": "abc"}

    def test_first_publish(self):
        self.assertEqual(orch.plan(None, self.P, "b1")["action"], "PUBLISH")

    def test_skip_when_unchanged(self):
        pub = {"researchVersion": "v2", "manifestSha256": "abc", "version": "b1", "health": "HEALTHY"}
        self.assertEqual(orch.plan(pub, self.P, "b1")["action"], "SKIP")

    def test_publish_on_version_or_manifest_change(self):
        pub = {"researchVersion": "v1", "manifestSha256": "abc", "version": "b1", "health": "HEALTHY"}
        self.assertEqual(orch.plan(pub, self.P, "b1")["action"], "PUBLISH")
        pub = {"researchVersion": "v2", "manifestSha256": "zzz", "version": "b1", "health": "HEALTHY"}
        self.assertEqual(orch.plan(pub, self.P, "b1")["action"], "PUBLISH")

    def test_descriptor_has_no_schedule_and_state_not_started(self):
        self.assertTrue(orch.DESCRIPTOR["schedule"].startswith("none"))
        self.assertEqual(orch.DESCRIPTOR["components"]["biologicalState"]["status"], "NOT_STARTED")


class PlatformTests(unittest.TestCase):
    def test_refuses_app_databases(self):
        for url in ("https://sector-9393c-default-rtdb.firebaseio.com", "https://sector-dev-1f4d0.firebaseio.com"):
            with self.assertRaises(ValueError):
                bp.BrainRtdb(url, tokens=object())


class CliTests(unittest.TestCase):
    def test_offline_dry_run_writes_updates_file(self):
        d = tempfile.mkdtemp()
        try:
            write_bundle(os.path.join(d, "b"), [synthetic_profile()]) if os.makedirs(os.path.join(d, "b")) is None else None
            rc = run.main(["--dry-run", "--offline", "--bundle", os.path.join(d, "b"), "--out", os.path.join(d, "out")])
            self.assertEqual(rc, 0)
            up = json.load(open(os.path.join(d, "out", "updates.json")))
            self.assertIn("/species/example_fish", up)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()


class PlatformConformanceTests(PayloadTests):
    """The brain writes only paths it owns (Brain Platform contract §5) with a contract event id (§7)."""

    def test_every_write_is_owned_and_the_event_id_names_this_brain(self):
        up = bb.build_updates(self.b, now=NOW, uri_root="gs://bucket/biology/v1", deployment="brain/biological@test",
                              descriptor=orch.DESCRIPTOR, duration_ms=5, published=None, existing_species=None,
                              event_id=bp.event_id(NOW, bb.BRAIN_ID, 0))
        bp.assert_owned({k.lstrip("/"): v for k, v in up.items()}, bb.BRAIN_ID)
        ev = [v for k, v in up.items() if k.startswith("/activity/")]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["kind"], "brain.registered")
        self.assertIn(ev[0]["kind"], bp.ACTIVITY_KIND)
        self.assertTrue(up[f"/brains/{bb.BRAIN_ID}"]["platform"]["conformant"])
