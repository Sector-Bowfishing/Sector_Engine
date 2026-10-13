"""Water Clarity Brain tests (stdlib unittest; no network).

  cd jobs/water-clarity-brain && python3 -m unittest discover -s tests -v

Fixtures are trimmed real responses captured 2026-10-12 from production
(sector-engine-00072-way /conditions and gs://sector-lake-surface).
"""
import copy
import datetime as dt
import json
import math
import re
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
# Tests never read the real private overlay: they merge a synthetic one (same mechanics).
os.environ["CLARITY_PRIVATE_CATALOG"] = os.path.join(HERE, "fixtures", "catalog.overlay.example.json")
import brain_platform as bp      # noqa: E402
import clarity_brain as cb       # noqa: E402
import run                       # noqa: E402

NOW = dt.datetime(2026, 10, 12, 6, 30, tzinfo=dt.timezone.utc)


def fx(name):
    return json.load(open(os.path.join(HERE, "fixtures", name)))


GUNT = fx("engine_guntersville_rain_decay.json")
KY = fx("engine_kentucky_discharge_gauge.json")
ALEK = fx("engine_aleknagik_openmeteo.json")
LATEST = fx("bucket_guntersville_latest.json")
META = fx("bucket_guntersville_meta.json")


def gauge_cond(trend="falling", algal=False):
    """An in-situ turbidity-gauge answer, shaped exactly like the engine's DTO."""
    c = copy.deepcopy(GUNT)
    c["clarityVisibility"] = {"centralFt": 3.21, "lowFt": None if algal else 1.33, "highFt": None if algal else 4.45,
                              "confidence": "medium", "model": "secchi-power-v1", "source": "inSituGauge",
                              "provenance": "USGS 03575100 Tennessee River measuring 7.1 FNU",
                              "limitations": ["Visibility converted from turbidity (validated on 81,661 WQP pairs: median error 1.2 ft); the range is the conversion's 80% spread, not the gauge's."]}
    c["clarityGauges"] = [{"siteCode": "03575100", "siteName": "x", "parameterCode": "63680", "parameterName": "Turbidity",
                           "role": "turbidity", "value": 7.1, "unit": "FNU", "trend": trend, "change": -0.4, "distanceMiles": 2.0,
                           "latitude": 34.5, "longitude": -86.2, "driving": True}]
    return c


def assert_rtdb_safe(tc, obj, path="$"):
    """RTDB rejects NaN/inf and keys with . $ # [ ] /."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            tc.assertFalse(any(ch in k for ch in ".$#[]/"), f"bad key {k!r} at {path}")
            assert_rtdb_safe(tc, v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_rtdb_safe(tc, v, f"{path}[{i}]")
    elif isinstance(obj, float):
        tc.assertTrue(math.isfinite(obj), f"non-finite at {path}")


class LakeKeys(unittest.TestCase):
    def test_slug_matches_bucket_and_ops(self):
        self.assertEqual(bp.lake_key("Guntersville|AL"), "Guntersville_AL")
        self.assertEqual(bp.lake_key("Lake St. Clair|MI"), "Lake_St_Clair_MI")
        self.assertEqual(bp.lake_key("Eufaula / W.F. George|AL"), "Eufaula_W_F_George_AL")
        self.assertEqual(LATEST["files"]["meta"].split("/")[1], bp.lake_key("Guntersville|AL"))

    def test_collision_fails_the_write(self):
        with self.assertRaises(ValueError):
            bp.lake_keys(["A.B|AL", "A B|AL"])

    def test_every_lake_node_stores_canonical_id(self):
        w = cb.lake_writes("Lake St. Clair|MI", None, None, NOW, "boom")
        self.assertEqual(w["/lakeFleet/Lake_St_Clair_MI/lakeId"], "Lake St. Clair|MI")


class ProductionParity(unittest.TestCase):
    """The Brain restates production; it never recomputes the customer number."""

    def test_rain_decay_restated_exactly(self):
        e = cb.engine_estimate(GUNT, "Guntersville|AL")
        v = GUNT["clarityVisibility"]
        self.assertEqual(e["stateType"], "RAINFALL_MODELED")
        self.assertEqual(e["clarityFt"], round(v["centralFt"], 2))
        self.assertIsNone(e["lowFt"])
        self.assertEqual(e["engine"]["model"], v["model"])
        self.assertEqual(e["engine"]["confidenceLabel"], v["confidence"])
        self.assertEqual(e["engine"]["limitations"], v["limitations"])
        self.assertEqual(e["recentRainfallIn72h"], round(GUNT["clarityRain"]["watershed72hIn"], 2))

    def test_gauge_path_is_production_and_keeps_engine_range(self):
        e = cb.engine_estimate(gauge_cond(), "Guntersville|AL")
        self.assertEqual(e["stateType"], "GAUGE_OBSERVED")
        self.assertEqual((e["lowFt"], e["highFt"]), (1.33, 4.45))
        self.assertEqual(cb.READINESS_BY_STATE[e["stateType"]], "PRODUCTION")

    def test_trend_only_from_driving_turbidity_gauge(self):
        self.assertEqual(cb.engine_estimate(gauge_cond("falling"), "x")["trend"], "IMPROVING")
        self.assertEqual(cb.engine_estimate(gauge_cond("rising"), "x")["trend"], "WORSENING")
        self.assertEqual(cb.engine_estimate(gauge_cond("steady"), "x")["trend"], "STABLE")
        self.assertEqual(cb.engine_estimate(GUNT, "x")["trend"], "UNKNOWN")
        self.assertEqual(cb.engine_estimate(KY, "x")["trend"], "UNKNOWN")    # discharge gauge, not driving

    def test_satellite_conversion_is_secchi_power_v1(self):
        sat = cb.satellite_evidence(LATEST, META, True, 16, NOW)
        fnu = LATEST["summary"]["fnuP50"]
        central = 11.123 * fnu ** -0.637
        self.assertAlmostEqual(sat["visibilityAtMedianFnu"]["centralFt"], round(central, 2))
        self.assertAlmostEqual(sat["visibilityAtMedianFnu"]["lowFt"], round(central * 10 ** -0.356, 2))
        self.assertFalse(sat["inCustomerEstimate"])

    def test_no_confidence_percentages_anywhere(self):
        s = cb.build_state("Guntersville|AL", cb.engine_estimate(GUNT, "Guntersville|AL"),
                           cb.satellite_evidence(LATEST, META, True, 16, NOW), [], None, NOW, "rev")
        text = json.dumps(s)
        self.assertNotIn('"confidence":', text)               # only the engine's own label, as confidenceLabel
        self.assertEqual(s["engine"]["confidenceLabel"], "low")
        self.assertIsNone(s["clarityClass"])

    def test_strong_is_not_manufactured(self):
        s = cb.build_state("Guntersville|AL", cb.engine_estimate(GUNT, "Guntersville|AL"),
                           cb.satellite_evidence(LATEST, META, True, 16, NOW), [], None, NOW, "rev")
        self.assertFalse(s["strong"]["evaluated"])
        self.assertEqual(s["strong"]["state"], "NOT_EVALUATED")
        self.assertEqual(s["strong"]["policyId"], "stage19-strong")
        for k in ("strong", "evidenceCount", "fullAuthorityEvidenceCount", "consensusWindowDays", "authority"):
            self.assertIsNone(s["strong"][k])

    def test_r31_never_publishes_a_state(self):
        r31 = next(m for m in cb.CATALOG["models"] if m["modelId"] == "r3.1")
        self.assertEqual((r31["lifecycle"], r31["certificationStatus"], r31["deploymentStatus"]), ("CANDIDATE", "CERTIFIED", "NOT_DEPLOYED"))
        self.assertFalse(r31["publishesLakeState"])
        self.assertFalse(r31["servesCustomers"])
        self.assertEqual(cb.CATALOG["certifications"]["r3_1"]["result"], "ALL_FROZEN_BARS_PASS")
        self.assertNotIn("r3.1", cb.CATALOG["activeModel"]["modelIds"])
        s = cb.build_state("x", cb.engine_estimate(GUNT, "x"), cb.satellite_evidence(None, None, False, None, NOW), [], None, NOW, "r")
        self.assertNotEqual(s["provenance"]["modelVersion"], "r3.1")


class Serialization(unittest.TestCase):
    def test_state_and_profile_are_rtdb_safe(self):
        for cond in (GUNT, KY, ALEK, gauge_cond(), gauge_cond(algal=True), None):
            est = cb.engine_estimate(cond, "Guntersville|AL")
            sat = cb.satellite_evidence(LATEST, META, True, 16, NOW)
            layers, geo = cb.map_layers(LATEST, META)
            s = cb.build_state("Guntersville|AL", est, sat, layers, geo, NOW, "rev")
            p = cb.build_profile({"id": "Guntersville|AL"}, est, sat, True, NOW)
            for o in (s, p):
                assert_rtdb_safe(self, o)
                json.dumps(o, allow_nan=False)
            for k in ("clarityFt", "clarityClass", "trend", "satelliteObservationAt", "spatialCoveragePct", "layers", "provenance"):
                self.assertIn(k, s)                                # Ops WaterClarityState fields
            for k in ("brainId", "generatedAt", "readiness", "qualityFlags", "validationRef", "modelVersion"):
                self.assertIn(k, s["provenance"])

    def test_layers_are_references_not_rasters(self):
        layers, geo = cb.map_layers(LATEST, META)
        self.assertEqual([l["id"] for l in layers], ["clarity", "satellite-footprint", "distance-to-reading", "algal-ndci"])
        self.assertTrue(all(l["url"].startswith("https://storage.googleapis.com/sector-lake-surface/") for l in layers))
        self.assertEqual(geo["encoding"]["kind"], "log10")
        self.assertLess(len(json.dumps(layers)), 2000)

    def test_registry_validation_sources_serialize(self):
        est = cb.engine_estimate(GUNT, "Guntersville|AL")
        st = cb.build_state("Guntersville|AL", est, cb.satellite_evidence(LATEST, META, True, 16, NOW), [], None, NOW, "rev")
        reg = cb.registry_entry({"Guntersville|AL": {"state": st}}, {}, NOW, "HEALTHY", None, "rev", ["Guntersville|AL"], bp.iso(NOW))
        for o in (reg, cb.CATALOG["validation"]["production"], cb.source_records({"Guntersville|AL": {"state": st}}, NOW, None)):
            assert_rtdb_safe(self, o)
        self.assertEqual(reg["readinessCounts"], {"BETA": 1})
        self.assertEqual(reg["candidateModel"]["modelId"], "r3.1")
        self.assertEqual(reg["activeModel"]["modelIds"], ["secchi-power-v1", "rain-decay-v0"])
        paths = reg["sensorAuthority"]["byProcessingPath"]
        self.assertEqual(paths["r3-usgs-aqr"]["sensors"]["S2C"], "FULL")
        self.assertEqual(paths["r0-acolite-l1c"]["sensors"]["S2C"], "LOWER")     # never promoted on the ACOLITE path
        self.assertEqual(paths["lake-surface-l2a-red"]["sensors"]["S2C"], "UNTIERED")
        self.assertEqual({v["status"] for v in reg["versions"]}, {"CURRENT", "CANDIDATE", "SHADOW"})


class PublicSafety(unittest.TestCase):
    """catalog.json is in the PUBLIC Sector_Engine repo: status-level facts only. Detailed
    research results live in the private overlay (catalog.private.json, gitignored)."""
    RAW = json.load(open(os.path.join(os.path.dirname(HERE), "catalog.json")))
    PRIVATE_KEYS = {"bars", "populations", "strongSharePctByConfiguration", "temporaryDependencies",
                    "deploymentPrerequisites", "frozenAt", "artifacts", "evidence", "researchScore", "byClass"}

    def keys(self, o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from self.keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from self.keys(v)

    def test_no_detailed_research_in_public_catalog(self):
        cand = {k: v for k, v in self.RAW.items() if k in ("certifications", "sensorAuthority", "models", "processingPaths")}
        self.assertFalse(self.PRIVATE_KEYS & set(self.keys(cand)))
        self.assertFalse(self.PRIVATE_KEYS & set(self.keys(self.RAW["validation"]["candidates"])))
        v = self.RAW["validation"]["candidates"]["r3_1"]
        self.assertEqual((v["metrics"], v["sampleCount"], v["lakeCount"]), ({}, None, None))

    def test_no_research_identifiers_in_public_files(self):
        root = os.path.dirname(HERE)
        text = "".join(open(os.path.join(root, f)).read() for f in ("catalog.json", "clarity_brain.py", "run.py", "README.md"))
        for token in ("b4ceae23", "9e87e5ba", "04966766", "LAKE_SECCHI_PRIOR", "STATION_HISTORY", "AQR_GBM", "Guntersville survey", "RESERVE"):
            self.assertNotIn(token, text)

    def test_overlay_merges_detail_and_absence_is_public_only(self):
        self.assertEqual(cb.CATALOG_DETAIL, "PRIVATE_OVERLAY_LOADED")
        self.assertEqual(cb.CATALOG["certifications"]["r3_1"]["bars"][0]["barId"], "EXAMPLE_BAR")
        self.assertEqual(next(m for m in cb.CATALOG["models"] if m["modelId"] == "r3.1")["method"], "EXAMPLE_METHOD")
        self.assertEqual(cb.CATALOG["certifications"]["r3_1"]["certificationStatus"], "CERTIFIED")      # public kept
        with mock.patch.dict(os.environ, {"CLARITY_PRIVATE_CATALOG": "/nonexistent/overlay.json"}):
            cat, detail = cb.load_catalog()
        self.assertEqual(detail, "PRIVATE_OVERLAY_UNAVAILABLE")
        self.assertNotIn("bars", cat["certifications"]["r3_1"])
        self.assertEqual(cat["candidateModel"]["modelId"], "r3.1")


class SemanticOnly(unittest.TestCase):
    """The Engine publishes facts and codes; Sector Ops owns display labels."""
    PROSE_KEYS = {"statusLabel", "label", "summary", "role", "note", "notes", "statusNote", "meaning", "why", "reason", "basis", "temporary"}
    CONTRACT_LABELS = {("layers", "label")}          # Ops v1 contract field, kept for compatibility

    def walk(self, o, parent=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in self.PROSE_KEYS and (parent, k) not in self.CONTRACT_LABELS and isinstance(v, str) \
                        and re.search(r"\s", v):                                    # single-token codes are fine; free text is not
                    self.fail(f"display/prose field {parent}.{k} = {v!r}")
                self.walk(v, k)
        elif isinstance(o, list):
            for v in o:
                self.walk(v, parent)

    def test_registry_and_catalog_have_no_display_labels(self):
        est = cb.engine_estimate(GUNT, "Guntersville|AL")
        st = cb.build_state("Guntersville|AL", est, cb.satellite_evidence(LATEST, META, True, 16, NOW), *cb.map_layers(LATEST, META), NOW, "rev")
        reg = cb.registry_entry({"Guntersville|AL": {"state": st}}, {}, NOW, "HEALTHY", None, "rev", ["Guntersville|AL"], None)
        self.walk(reg)
        self.walk(cb.CATALOG["validation"])
        self.walk(cb.source_records({"Guntersville|AL": {"state": st}}, NOW, None))

    def test_state_and_profile_carry_codes_not_prose(self):
        est = cb.engine_estimate(gauge_cond(), "Guntersville|AL")
        sat = cb.satellite_evidence(LATEST, META, True, 16, NOW)
        st = cb.build_state("Guntersville|AL", est, sat, *cb.map_layers(LATEST, META), NOW, "rev")
        self.assertEqual(st["trendBasis"]["relation"], "INVERSE")
        self.assertEqual(st["satellite"]["authority"], "UNTIERED")          # S2C pass on the production path
        self.assertEqual(st["candidateModel"]["deploymentStatus"], "NOT_DEPLOYED")
        self.assertEqual(st["activeModel"], "secchi-power-v1")
        self.assertEqual(st["readiness"], "PRODUCTION")
        self.walk({k: v for k, v in st.items() if k != "engine"})       # engine.* is production's own text, restated
        p = cb.build_profile({"id": "Guntersville|AL"}, est, sat, True, NOW)
        self.walk({k: v for k, v in p.items() if k != "engineLimitations"})


class MissingAndStale(unittest.TestCase):
    def test_missing_rain_is_fallback_and_degraded(self):
        c = copy.deepcopy(GUNT)
        c["clarityVisibility"].update(source="noRainData", provenance="No turbidity gauge and no rain data")
        c["clarityRain"] = None
        e = cb.engine_estimate(c, "x")
        self.assertEqual(e["stateType"], "FALLBACK_NEUTRAL")
        self.assertEqual(cb.READINESS_BY_STATE[e["stateType"]], "DEGRADED")
        self.assertIn("noMeasurement", cb.quality_flags(e, {"status": "NONE"}))

    def test_open_meteo_fallback_is_flagged(self):
        e = cb.engine_estimate(ALEK, "Aleknagik|AK")
        self.assertEqual(e["rainfallSource"], "OPEN_METEO_POINT_48H")
        self.assertIsNone(e["recentRainfallIn72h"])                # the 48 h value is only in engine text
        self.assertIn("rainfallFallback:open-meteo-48h", cb.quality_flags(e, {"status": "FRESH"}))

    def test_missing_satellite(self):
        self.assertEqual(cb.satellite_evidence(None, None, True, None, NOW)["status"], "NONE")
        self.assertEqual(cb.satellite_evidence(LATEST, META, False, 16, NOW)["status"], "UNSUPPORTED")
        layers, geo = cb.map_layers(None, None)
        self.assertEqual(layers, [])
        self.assertIsNone(geo)

    def test_stale_satellite(self):
        later = NOW + dt.timedelta(days=20)
        sat = cb.satellite_evidence(LATEST, META, True, 16, later)
        self.assertEqual(sat["status"], "STALE")
        self.assertTrue(any(f.startswith("satelliteStale:") for f in cb.quality_flags(cb.engine_estimate(GUNT, "x"), sat)))

    def test_missed_lake_keeps_state_and_ages_to_stale(self):
        fresh = {"lastUpdatedAt": bp.iso(NOW - dt.timedelta(hours=3))}
        old = {"lastUpdatedAt": bp.iso(NOW - dt.timedelta(hours=40))}
        self.assertFalse(list(cb.stale_carry("A|AL", fresh, NOW).values())[0])
        self.assertTrue(list(cb.stale_carry("A|AL", old, NOW).values())[0])
        w = cb.lake_writes("A|AL", None, None, NOW, "timeout")
        self.assertNotIn("/lakes/A_AL/states/waterClarity", w)      # never blanks the last good state

    def test_partial_engine_payload(self):
        c = {"clarityVisibility": {"centralFt": 2.0, "model": "rain-decay-v0", "source": "rainDecayModel"}}
        e = cb.engine_estimate(c, "x")
        s = cb.build_state("x", e, cb.satellite_evidence(None, None, True, None, NOW), [], None, NOW, None)
        self.assertEqual(s["clarityFt"], 2.0)
        self.assertIsNone(s["engine"]["confidenceLabel"])
        self.assertTrue(e["resolvedLakeMissing"])
        self.assertFalse(e["resolvedLakeMismatch"])

    def test_malformed_engine_payload_is_unavailable(self):
        for bad in ({}, {"clarityVisibility": None}, None):
            self.assertEqual(cb.engine_estimate(bad, "x")["stateType"], "UNAVAILABLE")
        e = cb.engine_estimate({"clarityVisibility": {"centralFt": "nan?", "source": "mystery"}}, "x")
        self.assertEqual(e["stateType"], "UNAVAILABLE")

    def test_unknown_readiness_counts(self):
        prev = {"A_AL": {"slots": {"waterClarity": {"lastUpdatedAt": bp.iso(NOW)}}}}   # no readiness written
        reg = cb.registry_entry({}, prev, NOW, "HEALTHY", None, None, ["A|AL"], None)
        self.assertEqual(reg["readinessCounts"], {})
        self.assertEqual(reg["staleLakeCount"], 0)


class FakeTransport:
    def __init__(self, script=None):
        self.calls, self.script = [], list(script or [])

    def __call__(self, method, url, body):
        self.calls.append((method, url, json.loads(body) if body else None))
        if self.script:
            r = self.script.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        return 200, "null"


class Publisher(unittest.TestCase):
    def setUp(self):
        os.environ["BRAIN_ACCESS_TOKEN"] = "test-token"

    def test_refuses_app_databases(self):
        for url in ("https://sector-9393c-default-rtdb.firebaseio.com", "https://sector-dev-1f4d0.firebaseio.com"):
            with self.assertRaises(ValueError):
                bp.BrainRtdb(url)

    def test_multipath_patch_writes_only_leaves_of_shared_nodes(self):
        t = FakeTransport()
        db = bp.BrainRtdb("https://sector-brain.firebaseio.com", transport=t, backoff_s=0)
        est = cb.engine_estimate(GUNT, "Guntersville|AL")
        st = cb.build_state("Guntersville|AL", est, cb.satellite_evidence(LATEST, META, True, 16, NOW), [], None, NOW, "r")
        db.update(cb.lake_writes("Guntersville|AL", None, st, NOW))
        method, url, body = t.calls[0]
        self.assertEqual(method, "PATCH")
        self.assertTrue(url.startswith("https://sector-brain.firebaseio.com/.json?"))
        self.assertNotIn("snapshots/Guntersville_AL/latest", body)              # never replaces the shared snapshot
        self.assertIn("snapshots/Guntersville_AL/latest/waterClarity", body)
        self.assertNotIn("lakeFleet/Guntersville_AL", body)
        self.assertIn("lakeFleet/Guntersville_AL/readiness/waterClarity", body)
        self.assertTrue(all(k.split("/")[0] in ("lakes", "snapshots", "lakeFleet") for k in body))

    def test_retries_5xx_then_raises(self):
        t = FakeTransport([(503, "x"), (503, "x"), (503, "x"), (503, "x")])
        db = bp.BrainRtdb(transport=t, retries=3, backoff_s=0)
        with self.assertRaises(bp.BrainRtdbError):
            db.update({"/a": 1})
        self.assertEqual(len(t.calls), 4)

    def test_recovers_after_transient_failure(self):
        t = FakeTransport([ConnectionResetError("reset"), (200, "null")])
        db = bp.BrainRtdb(transport=t, retries=3, backoff_s=0)
        db.update({"/a": 1})
        self.assertEqual(len(t.calls), 2)

    def test_does_not_retry_rejections(self):
        t = FakeTransport([(401, "Unauthorized"), (200, "null")])
        db = bp.BrainRtdb(transport=t, retries=3, backoff_s=0)
        with self.assertRaises(bp.BrainRtdbError):
            db.update({"/a": 1})
        self.assertEqual(len(t.calls), 1)

    def test_schema_mismatch_blocks_the_run(self):
        db = bp.BrainRtdb(transport=FakeTransport([(200, "2")]), backoff_s=0)
        with self.assertRaises(bp.BrainRtdbError):
            bp.check_schema(db)
        db = bp.BrainRtdb(transport=FakeTransport([(200, "null")]), backoff_s=0)
        self.assertIsNone(bp.check_schema(db))

    def test_prune_touches_only_this_brains_events(self):
        old = bp.iso(NOW - dt.timedelta(days=40))
        act = {"a": {"brainId": "water-clarity", "at": old}, "b": {"brainId": "water-temp", "at": old},
               "c": {"brainId": "water-clarity", "at": bp.iso(NOW)}}
        self.assertEqual(cb.prune_activity(act, NOW), {"/activity/a": None})


DIRECTORY = [{"id": "Guntersville|AL", "lat": 34.42, "lon": -86.25}, {"id": "Kentucky Lake|KY", "lat": 36.6, "lon": -88.07},
             {"id": "Aleknagik|AK", "lat": 59.3, "lon": -158.6}]


class EndToEnd(unittest.TestCase):
    """run.main with every network edge faked."""

    def run_main(self, transport, engine):
        os.environ["BRAIN_ACCESS_TOKEN"] = "test-token"
        bucket = {"latest": LATEST, "meta": META, "passCount": 16}
        real_init = bp.BrainRtdb.__init__

        def init(self_, url=bp.BRAIN_RTDB_URL, tokens=None, transport_=None, **kw):
            real_init(self_, url, tokens, transport=transport, backoff_s=0)
        with mock.patch.object(run, "load_directory", return_value=DIRECTORY * 1), \
             mock.patch.object(run, "polygon_ids", return_value={"Guntersville|AL", "Kentucky Lake|KY"}), \
             mock.patch.object(run, "bucket_lake", side_effect=lambda lid: bucket if lid == "Guntersville|AL" else {"latest": None, "meta": None, "passCount": None}), \
             mock.patch.object(run, "engine_conditions", side_effect=engine), \
             mock.patch.object(run, "engine_revision", return_value="sector-engine-test"), \
             mock.patch.object(run, "lake_surface_run", return_value=None), \
             mock.patch.object(run, "job_health", return_value={"status": "HEALTHY"}), \
             mock.patch.object(bp.BrainRtdb, "__init__", init), \
             mock.patch.object(sys, "argv", ["run.py", "--batch", "2"]):
            return run.main()

    def test_one_lake_failing_does_not_stop_the_others(self):
        t = FakeTransport()

        def engine(lake):
            if lake["id"] == "Kentucky Lake|KY":
                raise TimeoutError("engine timeout")
            return {"Guntersville|AL": GUNT, "Aleknagik|AK": ALEK}[lake["id"]]
        rc = self.run_main(t, engine)
        writes = {}
        for m, _, body in t.calls:
            if m == "PATCH":
                writes.update(body)
        for path, value in writes.items():                              # path keys are multi-location paths;
            assert_rtdb_safe(self, value, path)                         # every nested key and value must be RTDB-legal
        self.assertIn("lakes/Guntersville_AL/states/waterClarity", writes)
        self.assertIn("lakes/Aleknagik_AK/states/waterClarity", writes)
        ky = writes["lakes/Kentucky_Lake_KY/states/waterClarity"]       # first run: no previous state to keep
        self.assertEqual(ky["stateType"], "UNAVAILABLE")
        self.assertEqual(ky["provenance"]["readiness"], "DEGRADED")
        self.assertIn(rc, (0, 2))
        self.assertEqual(writes["brains/water-clarity"]["supportedLakeCount"], 3)

    def test_brain_rtdb_outage_exits_without_touching_production(self):
        t = FakeTransport([OSError("unreachable")] * 50)
        calls = []

        def engine(lake):
            calls.append(lake["id"])
            return GUNT
        rc = self.run_main(t, engine)
        self.assertEqual(rc, 1)                 # aborted at the schema check
        self.assertEqual(calls, [])             # nothing else ran; production endpoints are only ever read
        self.assertTrue(all(m in ("GET", "PATCH") for m, _, _ in t.calls))


if __name__ == "__main__":
    unittest.main()
