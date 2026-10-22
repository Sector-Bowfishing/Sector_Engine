"""Sector Intelligence Brain publisher tests (stdlib unittest, synthetic data, no network)."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "runtime"))   # brains/sector-intelligence/runtime
import brain_platform as bp                  # noqa: E402
import orchestration as orch                 # noqa: E402
import sector_intelligence_brain as sib      # noqa: E402

NOW = dt.datetime(2026, 10, 12, 23, 0, tzinfo=dt.timezone.utc)
CAT_PATH = os.path.join(os.path.dirname(HERE), "runtime", "catalog.json")


def real_catalog():
    with open(CAT_PATH, "rb") as fh:
        raw = fh.read()
    return sib.load_catalog(raw), sib.catalog_sha(raw)


def reg(bid, *, hours_ago=1.0, stale_after=6, health="HEALTHY", status="BETA", version="1.0", **extra):
    r = {"brainId": bid, "version": version, "status": status, "health": health, "supportedLakeCount": 2,
         "lastSuccessfulRun": bp.iso(NOW - dt.timedelta(hours=hours_ago)), "staleAfterHours": stale_after}
    r.update(extra)
    return r


def upstream(**over):
    base = {
        "lake-brain": {"registry": None, "health": None, "validationStatus": None},
        "water-temp": {"registry": reg("water-temp"), "health": {"status": "HEALTHY"}, "validationStatus": "PARTIAL"},
        "water-clarity": {"registry": reg("water-clarity", stale_after=26), "health": {"status": "HEALTHY"}, "validationStatus": "PARTIAL"},
        "wind": {"registry": reg("wind", stale_after=1.5, hours_ago=0.5), "health": {"status": "HEALTHY"}, "validationStatus": "PARTIAL"},
        "biological-state": {"registry": reg("biological-state", stale_after=None, status="PROFILED", responsibilities={
            "speciesKnowledge": {"status": "PUBLISHED"}, "biologicalState": {"status": "NOT_STARTED", "note": "not built"}}),
            "health": {"status": "HEALTHY"}, "validationStatus": "NOT_VALIDATED"},
    }
    base.update(over)
    return base


SERVICE = {"trafficStatuses": [{"revision": "rev-a", "tag": "x"}, {"revision": "rev-b", "percent": 100}],
           "template": {"containers": [{"image": "repo/img@sha256:abc"}]}}
LINEAGE = {"service": "svc", "tag": "deployed/x", "commit": "c0ffee", "imageDigest": "sha256:abc", "project": "p", "region": "r"}


def build(cat=None, ups=None, fleet=None, published=None, serving=None):
    cat = cat or real_catalog()[0]
    serving = serving or sib.engine_serving(SERVICE, LINEAGE, NOW)
    lakes = ["Alpha Lake|AL", "Beta Reservoir|TN"]
    fleet = fleet if fleet is not None else {
        "Alpha_Lake_AL": {"readiness": {"waterTemp": "BETA"}, "modelVersions": {"waterTemp": "m1"},
                          "slots": {"waterTemp": {"readiness": "BETA", "stale": False, "stateType": "modeled",
                                                  "lastUpdatedAt": bp.iso(NOW - dt.timedelta(hours=10))},
                                    "wind": {"readiness": "CALIBRATION", "stateType": "analysis",
                                             "lastUpdatedAt": bp.iso(NOW - dt.timedelta(hours=0.5))}}}}
    return sib.build_updates(cat=cat, cat_sha="sha", lakes=lakes, fleet=fleet, upstream=ups or upstream(),
                             serving=serving, now=NOW, deployment="test", descriptor=orch.DESCRIPTOR,
                             duration_ms=5, published=published, event_id="e1")


class DependencyTruth(unittest.TestCase):
    def setUp(self):
        self.cat, _ = real_catalog()

    def dep(self, bid, ups):
        u = ups[bid]
        return sib.dependency_status(bid, self.cat["dependencies"][bid], u["registry"], u["health"], u["validationStatus"], self.cat, NOW)

    def test_unregistered_brain_is_not_connected(self):
        d = self.dep("lake-brain", upstream())
        self.assertEqual(d["connectionStatus"], "NOT_CONNECTED")
        self.assertEqual(d["publishingStatus"], "NOT_REGISTERED")
        self.assertFalse(d["exists"])
        self.assertIn("missingReason", d)

    def test_existing_brain_is_never_connected_unless_consumed(self):
        for bid in ("water-temp", "water-clarity", "wind", "biological-state"):
            d = self.dep(bid, upstream())
            self.assertTrue(d["exists"])
            self.assertFalse(d["consumedBySectorIntelligence"])
            self.assertEqual(d["connectionStatus"], "AVAILABLE_NOT_CONSUMED", bid)
            self.assertFalse(d["usedInLastEvaluation"])

    def test_consumed_brain_connects_and_degrades_when_stale(self):
        cat = copy.deepcopy(self.cat)
        for m in cat["implementations"]:
            if m["modelId"] == cat["activeImplementation"]:
                m["readsBrains"] = ["water-temp"]
        fresh = sib.dependency_status("water-temp", cat["dependencies"]["water-temp"], reg("water-temp"), {"status": "HEALTHY"}, None, cat, NOW)
        self.assertEqual(fresh["connectionStatus"], "CONNECTED")
        stale = sib.dependency_status("water-temp", cat["dependencies"]["water-temp"], reg("water-temp", hours_ago=9), {"status": "HEALTHY"}, None, cat, NOW)
        self.assertEqual(stale["connectionStatus"], "CONNECTED_DEGRADED")
        self.assertIn("staleAfterHours", stale["degradedReason"])

    def test_non_active_consumer_does_not_connect(self):
        cat = copy.deepcopy(self.cat)
        for m in cat["implementations"]:
            if m["modelId"] == "ios-fishintel":
                m["readsBrains"] = ["wind"]
        d = sib.dependency_status("wind", cat["dependencies"]["wind"], reg("wind", stale_after=1.5, hours_ago=0.2), {"status": "HEALTHY"}, None, cat, NOW)
        self.assertEqual(d["connectionStatus"], "AVAILABLE_NOT_CONSUMED")
        self.assertEqual(d["consumedBy"], ["ios-fishintel", "normalized-sector-intelligence"])   # the pilot declares its reads
        self.assertFalse(d["consumedByCustomerPath"]); self.assertFalse(d["consumedByPilotEvaluation"])   # …but nothing ran here

    def test_stale_by_the_brains_own_threshold(self):
        d = self.dep("water-temp", upstream(**{"water-temp": {"registry": reg("water-temp", hours_ago=16), "health": {"status": "HEALTHY"}, "validationStatus": None}}))
        self.assertEqual(d["publishingStatus"], "STALE")
        self.assertIn("degradedReason", d)

    def test_version_driven_brain_is_not_aged(self):
        d = self.dep("biological-state", upstream())
        self.assertEqual(d["publishingStatus"], "VERSION_DRIVEN")

    def test_biological_knowledge_and_state_are_separate(self):
        d = self.dep("biological-state", upstream())
        self.assertEqual(d["components"]["speciesKnowledge"]["status"], "PUBLISHED")
        self.assertEqual(d["components"]["biologicalState"]["status"], "NOT_STARTED")

    def test_unhealthy_brain_reported(self):
        d = self.dep("wind", upstream(wind={"registry": reg("wind", stale_after=1.5, hours_ago=0.2), "health": {"status": "FAILED"}, "validationStatus": None}))
        self.assertEqual(d["health"], "FAILED")
        self.assertIn("FAILED", d["degradedReason"])

    def test_summary_counts(self):
        deps = {b: self.dep(b, upstream()) for b in sib.DEPENDENCY_ORDER}
        s = sib.dependency_summary(deps)
        self.assertEqual((s["total"], s["connected"], s["availableNotConsumed"], s["notConnected"]), (5, 0, 4, 1))


class LakeInputs(unittest.TestCase):
    def test_stale_slot_judged_by_brain_threshold(self):
        u = build()
        st = u["/lakes/Alpha_Lake_AL/states/intelligence"]
        self.assertEqual(st["inputs"]["waterTemp"]["status"], "STALE")          # 10 h > 6 h even though slot.stale is False
        self.assertEqual(st["inputs"]["wind"]["status"], "PUBLISHED")
        self.assertEqual(st["inputs"]["lake"]["status"], "NOT_PUBLISHED")
        self.assertEqual(st["inputs"]["biology"]["biologicalState"], "NOT_STARTED")
        self.assertEqual(st["inputCounts"]["consumed"], 0)

    def test_lake_without_fleet_row(self):
        st = build()["/lakes/Beta_Reservoir_TN/states/intelligence"]
        self.assertEqual(st["inputCounts"]["published"], 0)
        self.assertEqual(st["evaluationStatus"], "NOT_EVALUATED")


class PublishedPaths(unittest.TestCase):
    def test_only_intelligence_paths_written(self):
        u = build()
        allowed = ("/lakes/", "/lakeFleet/", "/brains/sector-intelligence", "/health/brains/sector-intelligence",
                   "/validation/sector-intelligence", "/activity/")
        for p in u:
            self.assertTrue(p.startswith(allowed), p)
            if p.startswith("/lakes/"):
                self.assertTrue(p.endswith("/states/intelligence"), p)
            if p.startswith("/lakeFleet/"):
                self.assertTrue(p.endswith("/slots/intelligence") or p.endswith("/lakeId"), p)

    def test_no_evaluation_is_fabricated(self):
        u = build()
        blob = json.dumps(u)
        self.assertFalse(any("/snapshots/" in p for p in u))
        self.assertFalse(any("readiness/intelligence" in p for p in u))
        for key in ("rating", "bestWindow", "drivers", "score"):
            self.assertNotIn(f'"{key}"', blob, key)

    def test_registry_truth(self):
        r = build()["/brains/sector-intelligence"]
        self.assertEqual(r["status"], "DISCOVERED")
        self.assertEqual(r["supportedLakeCount"], 0)
        self.assertEqual(r["evaluatedLakeCount"], 0)
        self.assertEqual(r["directoryLakeCount"], 2)
        self.assertEqual(r["activeModel"]["modelIds"], ["engine-conditions-score"])
        self.assertEqual(list(r["dependencies"]), sib.DEPENDENCY_ORDER)
        self.assertEqual(r["dependencySummary"]["connected"], 0)
        active = [m for m in r["modelRoster"] if m["modelId"] == "engine-conditions-score"][0]
        self.assertEqual((active["lifecycle"], active["certificationStatus"]), ("PRODUCTION", "NOT_VALIDATED"))
        self.assertEqual(active["codeRef"]["deployedRevision"], "rev-b")
        self.assertTrue(any(b["id"] == "DEPENDENCY_NOT_REGISTERED:lake-brain" for b in r["blockers"]))

    def test_validation_not_overstated(self):
        v = build()["/validation/sector-intelligence"]
        self.assertEqual(v["status"], "NOT_VALIDATED")
        self.assertEqual(v["predictiveValidation"]["status"], "NONE")
        self.assertTrue(all(t["kind"] == "SOFTWARE_TEST" for t in v["softwareTests"]))

    def test_no_nulls_or_empty_containers(self):
        def walk(o):
            if isinstance(o, dict):
                self.assertTrue(o)
                for v in o.values():
                    self.assertIsNotNone(v)
                    walk(v)
            elif isinstance(o, list):
                self.assertTrue(o)
                for v in o:
                    walk(v)
        for v in build().values():
            walk(v)

    def test_keys_are_rtdb_legal(self):
        sib.check_keys(build())
        with self.assertRaises(sib.CatalogError):
            sib.check_keys({"/brains/x": {"a.b": 1}})

    def test_activity_only_on_change(self):
        first = build()
        self.assertIn("/activity/e1", first)
        published = first["/brains/sector-intelligence"]
        self.assertNotIn("/activity/e1", build(published=published))
        moved = dict(published, engineServing=dict(published["engineServing"], revision="rev-old"))
        self.assertIn("rev-old -> rev-b", build(published=moved)["/activity/e1"]["title"])


class Serving(unittest.TestCase):
    def test_verified_lineage(self):
        s = sib.engine_serving(SERVICE, LINEAGE, NOW)
        self.assertEqual((s["revision"], s["trafficPercent"], s["lineageVerified"]), ("rev-b", 100, True))

    def test_new_image_is_flagged(self):
        svc = copy.deepcopy(SERVICE)
        svc["template"]["containers"][0]["image"] = "repo/img@sha256:def"
        s = sib.engine_serving(svc, LINEAGE, NOW)
        self.assertFalse(s["lineageVerified"])
        r = build(serving=s)["/brains/sector-intelligence"]
        self.assertTrue(any(b["id"] == "ENGINE_LINEAGE_UNVERIFIED" for b in r["blockers"]))

    def test_unreadable_service(self):
        s = sib.engine_serving(None, LINEAGE, NOW)
        self.assertEqual(s["status"], "UNKNOWN")
        self.assertNotIn("revision", s)


class Plan(unittest.TestCase):
    def test_plan(self):
        self.assertEqual(orch.plan(None, "f", "v")["action"], "PUBLISH")
        pub = {"version": "v", "fingerprint": "f", "health": "HEALTHY"}
        self.assertEqual(orch.plan(pub, "f", "v", published_age_hours=1)["action"], "SKIP")
        self.assertEqual(orch.plan(pub, "g", "v", published_age_hours=1)["action"], "PUBLISH")
        self.assertEqual(orch.plan(pub, "f", "w", published_age_hours=1)["action"], "PUBLISH")
        self.assertEqual(orch.plan(pub, "f", "v", published_age_hours=30)["action"], "PUBLISH")

    def test_fingerprint_moves_with_upstream(self):
        cat, sha = real_catalog()
        srv = sib.engine_serving(SERVICE, LINEAGE, NOW)
        deps = lambda ups: {b: sib.dependency_status(b, cat["dependencies"][b], ups[b]["registry"], ups[b]["health"], None, cat, NOW) for b in sib.DEPENDENCY_ORDER}
        a = sib.fingerprint(sha, srv, deps(upstream()))
        b = sib.fingerprint(sha, srv, deps(upstream(**{"water-temp": {"registry": reg("water-temp", hours_ago=9), "health": {"status": "HEALTHY"}, "validationStatus": None}})))
        self.assertNotEqual(a, b)


class Catalog(unittest.TestCase):
    def test_real_catalog_loads_and_reads_no_brain(self):
        cat, _ = real_catalog()
        self.assertEqual(cat["activeImplementation"], "engine-conditions-score")
        # Only the pilot implementation reads Brains; the customer path (active) reads none.
        self.assertEqual([m["modelId"] for m in cat["implementations"] if m.get("readsBrains")], ["normalized-sector-intelligence"])
        self.assertFalse(next(m for m in cat["implementations"] if m["modelId"] == cat["activeImplementation"]).get("readsBrains"))

    def test_catalog_rejects_unknown_brain(self):
        cat, _ = real_catalog()
        cat["implementations"][0]["readsBrains"] = ["depth"]
        with self.assertRaises(sib.CatalogError):
            sib.load_catalog(json.dumps(cat).encode())

    def test_app_database_refused(self):
        with self.assertRaises(ValueError):
            bp.BrainRtdb("https://sector-9393c-default-rtdb.firebaseio.com", tokens=object())


if __name__ == "__main__":
    unittest.main()


def test_stored_fingerprint_is_the_planned_one():
    """plan() compares the published fingerprint with one computed before the run; build_updates must store that one,
    not a recomputation from the CONNECTED-upgraded dependency view (which republished every orchestrator cycle)."""
    up = build()
    reg = up["/brains/sector-intelligence"]
    assert reg["fingerprint"]
    up2 = sib.build_updates(cat=real_catalog()[0], cat_sha="sha", lakes=["Alpha Lake|AL"], fleet={}, upstream=upstream(),
                            serving=sib.engine_serving(SERVICE, LINEAGE, NOW), now=NOW, deployment="d", descriptor=orch.DESCRIPTOR,
                            duration_ms=1, published=None, event_id="e", fingerprint_value="planned")
    assert up2["/brains/sector-intelligence"]["fingerprint"] == "planned"
