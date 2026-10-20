"""Brain operational truth (docs/brains/platform/BRAIN_OPERATIONAL_TRUTH_V1.md): one freshness verdict per Brain, separate timestamps, reasons
behind WARNING, canonical lifecycle vs legacy status, lake coverage split. Production-SHAPED payloads; synthetic lake ids and no species presence."""
import datetime as dt

from sector_brain_platform import operational_truth as OT, control as C, control_state as CS, orchestration as O

NOW = dt.datetime(2026, 10, 20, 15, 0, tzinfo=dt.timezone.utc)


def iso(h_ago):
    return (NOW - dt.timedelta(hours=h_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


MANIFEST = O.load_manifest()
MB = MANIFEST["brains"]

# Shapes as read from production on 2026-10-20 (GET); lake ids synthetic.
LAKE_REG = {"status": "ACTIVE", "health": "WARNING", "stalenessModel": "TIME", "staleAfterHours": 3, "lastSuccessfulRun": iso(5),
            "directoryLakeCount": 40, "supportedLakeCount": 12}
LAKE_HEALTH = {"status": "WARNING", "lastRun": iso(5), "lastSuccess": iso(5)}
SOURCES = {"usace-cwms-pool": {"ownerBrainId": "lake-brain", "health": "FAILED", "lakeCount": 1, "latestObservationAt": None, "failuresLastRun": 1},
           "usgs-gage": {"ownerBrainId": "lake-brain", "health": "HEALTHY", "lakeCount": 11, "latestObservationAt": iso(5)},
           "noaa-temp": {"ownerBrainId": "water-temp", "health": "FAILED", "lakeCount": 3}}
CLARITY_REG = {"status": "BETA", "health": "HEALTHY", "lastSuccessfulRun": iso(10), "supportedLakeCount": 8}
FISH_REG = {"status": "ACTIVE", "health": "HEALTHY", "stalenessModel": "VERSION", "lastSuccessfulRun": iso(30), "researchVersion": "2026-10-17.1",
            "supportedLakeCount": 0, "responsibilities": {"biologicalState": {"pilotLakes": ["lake-a", "lake-b", "lake-c", "lake-d", "lake-e"]}}}
INTEL_REG = {"status": "ACTIVE", "dependencies": {"biological-state": {"consumedByCustomerPath": False, "connectionStatus": "NOT_CONNECTED"}}}
FLEET = {"lake-a": {"slots": {"lake": {"lastUpdatedAt": iso(6)}, "waterClarity": {"generatedAt": iso(11)}}},
         "lake-b": {"slots": {"lake": {"lastUpdatedAt": iso(5)}, "wind": "not-a-dict"}}}


# ------------------------------------------------------------------ item 1 + 3: one policy, one verdict
def test_lake_policy_is_the_manifest_and_reports_the_declared_rule():
    p = OT.effective_policy(MB["lake-brain"], LAKE_REG)
    assert p["source"] == "ORCHESTRATOR_MANIFEST" and p["model"] == "TIME" and p["staleAfterHours"] == MB["lake-brain"]["freshness"]["staleAfterHours"]
    assert p["declaredStaleAfterHours"] == 3 and p.get("note")


def test_both_planes_give_lake_the_same_verdict():
    ov = C.brain_summary("lake-brain", LAKE_REG, LAKE_HEALTH, None, None, {}, NOW, manifest_brain=MB["lake-brain"], sources=SOURCES, source_health={})
    st = build(registries={"lake-brain": LAKE_REG}, health={"lake-brain": LAKE_HEALTH})["brains"]["lake-brain"]["freshness"]
    assert ov["freshness"]["verdict"] == st["verdict"] == "FRESH"          # 5 h old under the 26 h operating policy; was stale (3 h) on one plane only
    assert ov["stale"] is False and st["stale"] is False and ov["staleAfterHours"] == st["staleAfterHours"]
    assert ov["freshness"]["declaredStaleAfterHours"] == st["declaredStaleAfterHours"] == 3


def test_time_verdicts_and_missing_evidence_is_unknown():
    p = {"model": "TIME", "staleAfterHours": 6, "source": "ORCHESTRATOR_MANIFEST"}
    assert OT.verdict(p, last_successful_run=iso(7), now=NOW)["verdict"] == "STALE"
    assert OT.verdict(p, last_successful_run=iso(1), now=NOW)["verdict"] == "FRESH"
    v = OT.verdict(p, last_successful_run=None, now=NOW)
    assert v["verdict"] == "UNKNOWN" and v["stale"] is None
    assert OT.verdict({"source": "NONE"}, last_successful_run=iso(1), now=NOW)["verdict"] == "UNKNOWN"


def test_version_verdict_comes_from_the_brain_plan():
    p = OT.effective_policy(MB["biological-state"], FISH_REG)
    assert p["model"] == "VERSION"
    assert OT.verdict(p, last_successful_run=iso(30), now=NOW, plan={"action": "SKIP"})["verdict"] == "FRESH"
    st = OT.verdict(p, last_successful_run=iso(30), now=NOW, plan={"action": "PUBLISH", "reasons": ["release 2026-10-18.1 newer"]})
    assert st["verdict"] == "STALE" and "2026-10-18.1" in st["reason"]
    assert OT.verdict(p, last_successful_run=iso(30), now=NOW)["verdict"] == "UNKNOWN"     # no plan: never FRESH by default


def test_fingerprint_verdict():
    p = {"model": "FINGERPRINT", "source": "ORCHESTRATOR_MANIFEST"}
    assert OT.verdict(p, last_successful_run=iso(1), now=NOW, input_fingerprint="a", last_processed_fingerprint="a")["verdict"] == "FRESH"
    assert OT.verdict(p, last_successful_run=iso(1), now=NOW, input_fingerprint="b", last_processed_fingerprint="a")["verdict"] == "STALE"
    u = OT.verdict(p, last_successful_run=iso(1), now=NOW, input_fingerprint="a")
    assert u["verdict"] == "UNKNOWN" and "manual runs" in u["reason"]


def test_every_manifest_brain_gets_a_verdict_on_the_orchestrator_plane():
    st = build(registries={"lake-brain": LAKE_REG, "biological-state": FISH_REG}, plans={"biological-state": {"action": "SKIP"}})
    for bid in MB:
        f = st["brains"][bid]["freshness"]
        assert f["verdict"] in OT.VERDICTS and f.get("model") in OT.MODELS, bid
    assert st["brains"]["biological-state"]["freshness"]["verdict"] == "FRESH"


def test_overview_mirrors_orchestrator_verdict_for_non_time_models_only():
    orch = {"freshness": {"verdict": "FRESH", "stale": False, "reason": "Brain plan: SKIP"}}
    ov = C.brain_summary("biological-state", FISH_REG, {"status": "HEALTHY"}, None, None, {}, NOW, manifest_brain=MB["biological-state"],
                         orchestrator_brain=orch)
    assert ov["freshness"]["verdict"] == "FRESH" and ov["freshness"]["mirroredFrom"].endswith("biological-state/freshness")
    alone = C.brain_summary("biological-state", FISH_REG, {"status": "HEALTHY"}, None, None, {}, NOW, manifest_brain=MB["biological-state"])
    assert alone["freshness"]["verdict"] == "UNKNOWN" and alone.get("stale") is None          # was "not stale" without evidence
    lake = C.brain_summary("lake-brain", {**LAKE_REG, "lastSuccessfulRun": iso(40)}, LAKE_HEALTH, None, None, {}, NOW, manifest_brain=MB["lake-brain"],
                           orchestrator_brain={"freshness": {"verdict": "FRESH", "stale": False}})
    assert lake["freshness"]["verdict"] == "STALE"                                        # TIME is computed, never mirrored


def test_paused_schedule_and_stale_verdict_are_independent():
    st = build(registries={"lake-brain": {**LAKE_REG, "lastSuccessfulRun": iso(40)}},
               jobs={"brain-orchestrator": {"schedulerState": "PAUSED", "cron": "*/15 * * * *"}}, scheduler_states={"brain-orchestrator": "PAUSED"})
    assert st["summary"]["scheduler"]["state"] == "PAUSED"
    lb = st["brains"]["lake-brain"]
    assert lb["freshness"]["verdict"] == "STALE" and lb["freshness"]["stale"] is True and lb["scheduleClass"] == MB["lake-brain"]["schedule"]["class"]


# ------------------------------------------------------------------ item 1: WARNING reason
def test_lake_warning_reason_is_derived_from_its_own_sources():
    r = OT.health_reasons("lake-brain", LAKE_HEALTH, SOURCES, {})
    assert r["basis"] == "DERIVED_FROM_PUBLISHED_FACTS"
    assert r["reasons"] == ["source usace-cwms-pool FAILED (1 lake); no observation; 1 failure(s) last run"]   # other Brains' sources excluded


def test_brain_reported_reasons_win_and_healthy_has_none():
    r = OT.health_reasons("lake-brain", {**LAKE_HEALTH, "reasons": ["lake-x: primary source unavailable, on fallback source usgs-x"]}, SOURCES, {})
    assert r == {"basis": "BRAIN_REPORTED", "reasons": ["lake-x: primary source unavailable, on fallback source usgs-x"]}
    assert OT.health_reasons("lake-brain", {"status": "HEALTHY"}, SOURCES, {}) is None
    assert OT.health_reasons("wind", {"status": "WARNING"}, {}, {})["basis"] == "UNEXPLAINED"


def test_source_health_plane_overrides_registry_health():
    r = OT.health_reasons("lake-brain", LAKE_HEALTH, {"usace-cwms-pool": {**SOURCES["usace-cwms-pool"], "health": "HEALTHY"}},
                          {"usace-cwms-pool": {"status": "DEGRADED"}})
    assert r["reasons"][0].startswith("source usace-cwms-pool DEGRADED")


def test_orchestrator_plane_carries_overview_reasons():
    ov = {"lake-brain": {"healthReasons": {"basis": "DERIVED_FROM_PUBLISHED_FACTS", "reasons": ["x"]}, "lastDataUpdate": {"at": iso(5), "basis": "NEWEST_LAKE_STATE"}}}
    lb = build(registries={"lake-brain": LAKE_REG}, health={"lake-brain": LAKE_HEALTH}, overview_brains=ov)["brains"]["lake-brain"]
    assert lb["healthReasons"]["reasons"] == ["x"] and lb["lastDataUpdate"]["basis"] == "NEWEST_LAKE_STATE"
    alone = build(registries={"lake-brain": LAKE_REG}, health={"lake-brain": LAKE_HEALTH})["brains"]["lake-brain"]
    assert alone["healthReasons"]["basis"] == "UNEXPLAINED" and alone["health"] == "WARNING"     # WARNING kept, never softened


# ------------------------------------------------------------------ item 2: lifecycle
def test_clarity_status_is_canonical_lifecycle_with_legacy_beside_it():
    ov = C.brain_summary("water-clarity", CLARITY_REG, {"status": "HEALTHY"}, None, None, {}, NOW, manifest_brain=MB["water-clarity"])
    assert ov["status"] == MB["water-clarity"]["lifecycle"] == "CALIBRATION" and ov["legacyStatus"] == "BETA"
    st = build(registries={"water-clarity": CLARITY_REG})["brains"]["water-clarity"]
    assert st["lifecycle"] == "CALIBRATION" and st["legacyStatus"] == "BETA"
    same = C.brain_summary("water-clarity", {**CLARITY_REG, "status": "CALIBRATION"}, None, None, None, {}, NOW, manifest_brain=MB["water-clarity"])
    assert "legacyStatus" not in same
    assert C.brain_summary("water-clarity", CLARITY_REG, None, None, None, {}, NOW)["status"] == "BETA"      # no manifest: registry word, unchanged


# ------------------------------------------------------------------ item 4: timestamps
def test_newest_slot_updates_and_data_update():
    sn = OT.newest_slot_updates(FLEET)
    assert sn == {"lake": iso(5), "waterClarity": iso(11)}
    assert OT.data_update("lake-brain", {"model": "TIME"}, LAKE_REG, sn) == {"at": iso(5), "basis": "NEWEST_LAKE_STATE"}
    fish = OT.data_update("biological-state", {"model": "VERSION"}, FISH_REG, sn)
    assert fish == {"at": iso(30), "basis": "VERSION_PUBLISH_RUN", "version": "2026-10-17.1"}
    assert OT.data_update("wind", {"model": "TIME"}, {}, sn) is None


def test_overview_publishes_four_distinct_timestamps():
    ov = C.overview(brains={"lake-brain": {**LAKE_REG, "lastSuccessfulRun": iso(4)}}, health={"lake-brain": {**LAKE_HEALTH, "lastRun": iso(2)}},
                    validation={}, scores={"lake-brain": {"value": 5.0, "scoreUpdatedAt": iso(1)}}, engine=None, fleet=FLEET, sources=SOURCES,
                    health_sources={}, jobs={}, now=NOW, manifest=MANIFEST)
    lb = ov["brains"]["lake-brain"]
    assert lb["lastExecution"]["at"] == iso(2) and lb["lastSuccessfulRun"] == iso(4) and lb["lastDataUpdate"]["at"] == iso(5)
    assert lb["lastScoreEvaluation"] == iso(1)
    assert lb["healthReasons"]["reasons"][0].startswith("source usace-cwms-pool FAILED")


# ------------------------------------------------------------------ item 5: Fish coverage split
def test_fish_coverage_split_pilot_vs_published_vs_customer():
    assert OT.coverage_split("biological-state", FISH_REG, INTEL_REG) == {"internalPilotLakes": 5, "publishedLakes": 0, "customerEnabledLakes": 0}
    ov = C.brain_summary("biological-state", FISH_REG, None, None, None, {}, NOW, manifest_brain=MB["biological-state"], intelligence_registry=INTEL_REG)
    assert ov["coverage"]["internalPilotLakes"] == 5 and ov["coverage"]["supported"] == 0 and ov["coverage"]["customerEnabledLakes"] == 0
    assert OT.coverage_split("wind", {}, INTEL_REG) is None


def build(**kw):
    ev = O.evaluate_world({"manifest": MANIFEST, "mode": "PRE_PRODUCTION", "now": NOW, "states": kw.get("registries") or {},
                           "activity": O.effective_activity(MANIFEST, None), "running": {}, "out_fps": None, "last_in_fps": {}})
    args = dict(registries={}, health={}, scores={}, jobs={}, evaluation=ev)
    args.update(kw)
    return CS.build_control_state(MANIFEST, "PRE_PRODUCTION", NOW, **args)


def test_time_reason_does_not_embed_the_age():
    p = {"model": "TIME", "staleAfterHours": 6, "source": "ORCHESTRATOR_MANIFEST"}
    assert OT.verdict(p, last_successful_run=iso(1), now=NOW)["reason"] == OT.verdict(p, last_successful_run=iso(2), now=NOW)["reason"]


def test_overview_without_orchestrator_verdict_says_so():
    ov = C.brain_summary("sector-intelligence", {"status": "CALIBRATION"}, None, None, None, {}, NOW, manifest_brain=MB["sector-intelligence"])
    assert ov["freshness"]["verdict"] == "UNKNOWN" and "orchestrator plane" in ov["freshness"]["reason"]


def test_last_score_evaluation_is_the_published_block_time_on_both_planes():
    sc = {"value": 3.0, "scoreUpdatedAt": iso(0)}                       # candidate: this run's clock
    ov = C.overview(brains={"lake-brain": LAKE_REG}, health={}, validation={}, scores={"lake-brain": sc}, engine=None, fleet={}, sources={},
                    health_sources={}, jobs={}, now=NOW, manifest=MANIFEST, score_published_at={"lake-brain": iso(150)})
    st = build(registries={"lake-brain": LAKE_REG}, scores={"lake-brain": {"value": 3.0, "scoreUpdatedAt": iso(150)}})
    assert ov["brains"]["lake-brain"]["lastScoreEvaluation"] == st["brains"]["lake-brain"]["lastScoreEvaluation"] == iso(150)


def test_a_failed_brain_plan_is_unknown_not_fresh():
    p = OT.effective_policy(MB["biological-state"], FISH_REG)
    v = OT.verdict(p, last_successful_run=iso(30), now=NOW, plan={"action": "SKIP", "planError": True, "reasons": ["--plan timed out after 600s"]})
    assert v["verdict"] == "UNKNOWN" and v["stale"] is None and "timed out" in v["reason"]
