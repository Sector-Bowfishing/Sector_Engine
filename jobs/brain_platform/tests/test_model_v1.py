"""Sector Brain Model v1 invariants (docs/brains/platform/). Useful tests, not ceremony: each pins a rule that has failed or could fail."""
import json, os

import pytest

from sector_brain_platform import model_v1 as M, fingerprint as F, publication as P, dependencies as D, field_validation as V, control_contract as C
from sector_brain_platform.model_v1 import ModelError

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


# ---- claims: level and maturity are independent axes ----------------------------------------------------------------------
def test_claim_level_is_independent_of_validation_maturity():
    c = {"id": "species-response", "level": 3, "maturity": "NOT_VALIDATED"}
    for m in ("CALIBRATION", "VALIDATED"):
        out = M.advance_maturity(c, m)
        assert out["level"] == 3 and out["maturity"] == m          # validating a Level 3 claim never makes it anything else
    assert c["level"] == 3


def test_maturity_must_make_sense_at_its_level():
    with pytest.raises(ModelError):
        M.validate_claim({"id": "x", "level": 1, "maturity": "CALIBRATION"})          # we do not calibrate a provider reading
    with pytest.raises(ModelError):
        M.validate_claim({"id": "x", "level": 3, "maturity": "PROVIDER_VERIFIED"})
    for lvl in M.CLAIM_LEVELS:                                                        # "no verdict" states legal everywhere
        for m in ("NOT_ASSESSED", "UNAVAILABLE", "NOT_OBSERVABLE", "WITHHELD"):
            M.validate_claim({"id": "x", "level": lvl, "maturity": m})
    with pytest.raises(ModelError):
        M.validate_claim({"id": "x", "level": 4, "maturity": "VALIDATED"})
    with pytest.raises(ModelError):
        M.validate_claim({"id": "x", "level": True, "maturity": "VALIDATED"})


def test_maturity_vocabulary_is_closed_and_every_level_subset_is_inside_it():
    for lvl, ms in M.MATURITY_BY_LEVEL.items():
        assert set(ms) <= set(M.CLAIM_MATURITY)
    assert set(M.MATURITY_RANK) == set(M.CLAIM_MATURITY)
    with pytest.raises(ModelError):
        M.validate_claim({"id": "x", "level": 3, "maturity": "PRODUCTION"})          # lifecycle word is not a claim maturity


# ---- vocabularies are closed and disjoint where they must be ---------------------------------------------------------------
def test_lifecycle_and_execution_vocabularies_are_closed():
    assert M.LIFECYCLE == ("RESEARCH", "PROFILED", "SHADOW", "CALIBRATION", "PRODUCTION_READY", "PRODUCTION")
    assert M.EXECUTION_TYPES == ("PROVIDER_INGESTION", "DEPENDENCY_DRIVEN", "PROSPECTIVE_VALIDATION", "MAINTENANCE", "MANUAL_SHADOW")
    assert not set(M.EXECUTION_TYPES) & set(M.JOB_EXECUTION_MODES)                   # executionType is not the /jobs executionMode
    assert set(M.LIFECYCLE) & set(M.CLAIM_MATURITY) == {"CALIBRATION"}                # the one shared word, documented in LIFECYCLE_MODEL.md
    assert not set(M.CLAIM_MATURITY) & {"PRODUCTION", "PRODUCTION_READY", "SHADOW", "RESEARCH", "PROFILED"}


def test_every_legacy_lifecycle_value_maps_into_v1_and_ambiguity_is_flagged():
    from sector_brain_platform import enums
    for v in set(enums.READINESS_LADDER) | set(enums.MODEL_LIFECYCLE) | {"IN_PROGRESS", "ACTIVE_PRODUCTION", "RESEARCH_CANDIDATE", "PRODUCTION_EVIDENCE"}:
        got, amb = M.map_legacy_lifecycle(v)
        assert got in M.LIFECYCLE + M.LIFECYCLE_CONDITIONS
    assert M.map_legacy_lifecycle("BETA") == ("CALIBRATION", True)
    assert M.map_legacy_lifecycle("PROFILED") == ("PROFILED", False)
    assert M.map_legacy_lifecycle("SHADOW") == ("SHADOW", False)
    with pytest.raises(ModelError):
        M.map_legacy_lifecycle("SOMETHING_NEW")                                       # never guessed


def test_conformance_fixture_matches_code():
    fx = json.load(open(os.path.join(REPO, "contracts", "conformance", "model_v1.json")))
    assert tuple(fx["claimLevels"]) == M.CLAIM_LEVELS and tuple(fx["claimMaturity"]) == M.CLAIM_MATURITY
    assert tuple(fx["lifecycle"]) == M.LIFECYCLE and tuple(fx["executionTypes"]) == M.EXECUTION_TYPES
    assert fx["legacyLifecycleMap"] == M.LEGACY_LIFECYCLE_MAP and tuple(fx["unknownKinds"]) == M.UNKNOWN_KINDS
    assert {int(k): tuple(v) for k, v in fx["maturityByLevel"].items()} == M.MATURITY_BY_LEVEL
    assert fx["production"] == {"overallMin": 8.0, "criticalMin": 7.5}
    assert tuple(fx["validationStatus"]) == M.VALIDATION_STATUS and "FAILED" in M.VALIDATION_STATUS and "NOT_STARTED" in M.VALIDATION_STATUS


# ---- production policy is unchanged ---------------------------------------------------------------------------------------
def test_production_policy_unchanged_and_unknown_never_passes():
    assert M.PRODUCTION_OVERALL_MIN == 8.0 and M.PRODUCTION_CRITICAL_MIN == 7.5
    assert M.production_ready(8.0, {"a": 7.5})[0] is True
    assert M.production_ready(7.9, {"a": 9.0})[0] is False
    assert M.production_ready(8.5, {"a": 7.4})[0] is False
    ok, why = M.production_ready(9.0, {"a": None})
    assert ok is False and "unknown" in why[0]
    assert M.production_ready(None, {})[0] is False


# ---- unknown is not zero ----------------------------------------------------------------------------------------------------
def test_unknown_is_distinct_from_zero_false_and_empty():
    assert M.known(0) and M.known(False) and M.known("") and not M.known(None)
    assert M.unknown_marker("NOT_OBSERVABLE")["unknown"] == "NOT_OBSERVABLE"
    assert len(set(M.UNKNOWN_KINDS)) == 5
    with pytest.raises(ModelError):
        M.unknown_marker("ZERO")


# ---- zero-concurrency helper ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("req,n,exp", [(0, 10, 1), (-3, 10, 1), (None, 10, 1), ("x", 5, 1), (8, 0, 1), (8, 3, 3), (100, 1000, 16), (4, 10, 4)])
def test_bounded_workers_is_never_zero(req, n, exp):
    from concurrent.futures import ThreadPoolExecutor
    w = M.bounded_workers(req, n)
    assert w == exp
    with ThreadPoolExecutor(max_workers=w) as pool:                                  # the Lake bug: max_workers=0 raises ValueError
        assert list(pool.map(lambda x: x, range(3))) == [0, 1, 2]


# ---- fingerprints ----------------------------------------------------------------------------------------------------------------
def test_fingerprint_excludes_volatile_fields_and_noops_when_unchanged():
    a = {"providerObservedAt": "2026-10-13T18:00:00Z", "rulesVersion": "v2", "generatedAt": "2026-10-13T19:00:00Z", "ageHours": 1.2,
         "nested": {"stateVersion": "s7", "requestedAt": "x", "value": 0.1 + 0.2}}
    b = {"nested": {"value": 0.3, "stateVersion": "s7", "requestedAt": "y"}, "ageHours": 9.9, "generatedAt": "later", "rulesVersion": "v2",
         "providerObservedAt": "2026-10-13T18:00:00Z"}
    assert F.fingerprint(a) == F.fingerprint(b)                                       # volatile + key order + float noise ignored
    first = F.decide(a, None)
    assert first["action"] == "RUN"
    again = F.decide(b, first["fingerprint"])
    assert again["action"] == "SKIP"                                                  # no material input change: skip
    c = dict(a, rulesVersion="v3")
    assert F.decide(c, first["fingerprint"])["action"] == "RUN"                       # a material ingredient moved


def test_fingerprint_distinguishes_zero_from_absent():
    assert F.fingerprint({"x": 0}) != F.fingerprint({})
    assert F.fingerprint({"x": 0}) != F.fingerprint({"x": None})


# ---- score publication safety ---------------------------------------------------------------------------------------------------
def blk(value, at, version="v1", **kw):
    return {"value": value, "scale": 10, "basis": "COMPUTED", "scoreVersion": version, "scoreUpdatedAt": at, "scoreBreakdown": {}, **kw}


WIND_NEW = blk(3.3, "2026-10-13T21:13:49Z", "wind-certification-rubric-v1", uncapped=3.27)
WIND_OLD = blk(3.1, "2026-10-12T06:16:16Z", "wind-certification-rubric-v1")


def test_stale_score_cannot_overwrite_a_newer_one():
    j = P.judge(WIND_OLD, WIND_NEW)
    assert j["verdict"] == "STALE"
    eff, held = P.apply_guard({"wind": WIND_OLD}, {"wind": WIND_NEW})
    assert eff["wind"] is WIND_NEW and held[0]["brainId"] == "wind" and held[0]["verdict"] == "STALE"


def test_judge_verdicts():
    assert P.judge(WIND_NEW, None)["verdict"] == "NEW"
    assert P.judge(dict(WIND_NEW, scoreUpdatedAt="2026-10-14T00:00:00Z"), WIND_NEW)["verdict"] == "SAME"      # timestamp-only change: no write
    assert P.judge(blk(3.4, "2026-10-14T00:00:00Z", "wind-certification-rubric-v1"), WIND_NEW)["verdict"] == "ADVANCE"
    assert P.judge(blk(3.4, WIND_NEW["scoreUpdatedAt"]), WIND_NEW)["verdict"] == "CONFLICT"
    undated = {k: v for k, v in blk(9.0, "x").items() if k != "scoreUpdatedAt"}
    assert P.judge(undated, WIND_NEW)["verdict"] == "UNDATED"                                                 # age unprovable: held
    assert P.judge(undated, {"value": 1, "scoreVersion": "v1"})["verdict"] == "ADVANCE"                       # published has no age either
    # RTDB read-back drops empty containers: must not look like a change
    readback = {k: v for k, v in blk(3.3, "2026-10-13T00:00:00Z").items() if k != "scoreBreakdown"}
    assert P.judge(blk(3.3, "2026-10-15T00:00:00Z", scoreBlockers=[]), readback)["verdict"] == "SAME"


def test_updating_one_brain_cannot_regress_the_others():
    """Lake / Biological / Depth publishing with a stale frozen Wind artifact in their image: only the intended Brain moves."""
    published = {"wind": WIND_NEW, "lake-brain": blk(5.0, "2026-10-13T00:00:00Z"), "biological-state": blk(4.0, "2026-10-13T00:00:00Z"),
                 "water-temp": blk(3.0, "2026-10-11T00:00:00Z", basis="FROZEN")}
    for intended, newer in (("lake-brain", blk(5.4, "2026-10-14T00:00:00Z")), ("biological-state", blk(4.6, "2026-10-14T00:00:00Z"))):
        cand = dict(published, wind=WIND_OLD)                # the specialist branch carries the OLD Wind artifact
        cand[intended] = newer
        eff, held = P.apply_guard(cand, published)
        assert [h["brainId"] for h in held] == ["wind"]
        assert P.regressions(published, eff, intended=[intended]) == []
        assert eff[intended]["value"] == newer["value"] and eff["wind"]["value"] == 3.3
    # without the guard the regression is detected by the checker
    assert P.regressions(published, dict(published, wind=WIND_OLD), intended=["lake-brain"]) == ["wind: 3.3 -> 3.1"]


def test_publishing_one_brain_cannot_silently_replace_anothers_newer_score():
    published = {"lake-brain": blk(5.0, "2026-10-14T10:00:00Z"), "wind": WIND_NEW}
    cand = {"lake-brain": blk(2.0, "2026-10-12T00:00:00Z"), "wind": WIND_NEW}        # an image baked two days ago
    eff, held = P.apply_guard(cand, published)
    assert eff["lake-brain"]["value"] == 5.0 and held and held[0]["brainId"] == "lake-brain"


def test_recorded_override_allows_a_deliberate_correction_and_is_reported():
    eff, held = P.apply_guard({"wind": WIND_OLD}, {"wind": WIND_NEW}, allow=["wind"])
    assert eff["wind"] is WIND_OLD and held[0].get("overridden") is True


# ---- dependency + freshness authority ---------------------------------------------------------------------------------------------
def dep(**kw):
    return {"id": "lake-brain", "requirement": "REQUIRED", "fallback": "WITHHOLD", **kw}


def test_owner_freshness_is_authoritative_and_stricter_rules_need_a_reason():
    fresh = {"freshness": {"stale": False, "evidenceStale": False, "ageHours": 20}}
    assert D.evaluate(dep(), fresh)["status"] == "SATISFIED"                          # 20 h old, owner says fresh: consumer does not relabel it
    with pytest.raises(ModelError):
        D.validate_dependency(dep(stricterMaxAgeHours=6))                              # undocumented stricter rule refused
    strict = dep(stricterMaxAgeHours=6, stricterReason="Depth effective-depth claim needs same-day level")
    r = D.evaluate(strict, fresh)
    assert r["status"] == "UNSATISFIED" and "Depth effective-depth" in r["reasons"][0]
    assert D.evaluate(dep(), {"freshness": {"stale": True}})["reasons"] == ["owner reports state stale"]


def test_dependency_fallbacks_and_maturity():
    assert D.evaluate(dep(requirement="OPTIONAL"), None)["status"] == "DEGRADED"
    assert D.evaluate(dep(fallback="DEGRADE"), None)["status"] == "DEGRADED"
    assert D.evaluate(dep(), None)["status"] == "UNSATISFIED"
    need = dep(minClaimMaturity="DESK_VALIDATED")
    assert D.evaluate(need, {"claimMaturity": "NOT_VALIDATED"})["status"] == "UNSATISFIED"
    assert D.evaluate(need, {"claimMaturity": "VALIDATED"})["status"] == "SATISFIED"
    assert D.evaluate(need, {})["status"] == "UNSATISFIED"                            # unknown maturity does not pass
    with pytest.raises(ModelError):
        D.validate_dependency({"id": "x", "requirement": "MAYBE", "fallback": "SKIP"})


# ---- shared field validation envelope --------------------------------------------------------------------------------------------
def trip(**blocks):
    return {"tripId": "t1", "lakeId": "Guntersville|AL", "zoneId": "z3", "timestamp": "2026-10-13T12:00:00Z", "location": {"lat": 34.4, "lon": -86.3},
            "observer": "obs-7f3a", "conditionsRef": "snap/abc", "consentVersion": "ledger-2026-10", "blocks": blocks or {"depth": {"observedSonarDepthFt": 0}}}


def test_one_envelope_many_blocks_and_zero_is_a_real_value():
    V.validate_trip(trip(depth={"observedSonarDepthFt": 0, "dryOrWet": "dry", "shootable": False}, wind={"observedExposure": {"unknown": "NOT_OBSERVABLE"}}))
    V.validate_trip(trip(wind={"providerWindMph": 8.5}, biological={"species": ["gar"], "encounters": 0}))


def test_trip_rejects_null_missing_envelope_and_foreign_fields():
    with pytest.raises(ModelError):
        V.validate_trip(trip(depth={"observedSonarDepthFt": None}))                    # null must not read as zero
    bad = trip(); del bad["consentVersion"]
    with pytest.raises(ModelError):
        V.validate_trip(bad)
    with pytest.raises(ModelError):
        V.validate_trip(trip(depth={"windMph": 3}))
    with pytest.raises(ModelError):
        V.validate_trip(trip(sonar={"x": 1}))                                          # unregistered Brain block
    with pytest.raises(ModelError):
        V.validate_trip(trip(depth={"shootable": 1}))                                  # int is not bool


# ---- control contract ------------------------------------------------------------------------------------------------------------------
def test_control_summary_rejects_bare_score_and_inflated_display():
    ok = {"brainId": "wind", "lifecycle": "CALIBRATION", "canonicalScore": 3.3, "underlyingScore": 3.27, "displayedScore": 3.3, "scoreStatus": "COMPUTED"}
    C.validate_control(ok)
    for bad in (dict(ok, score=3.3), dict(ok, displayedScore=4.0), dict(ok, lifecycle="BETA"), dict(ok, customerReadiness="YES")):
        with pytest.raises(ModelError):
            C.validate_control(bad)


def test_existing_control_summary_maps_onto_v1_names_without_inventing_fields():
    live = {"status": "BETA", "health": "HEALTHY", "score": {"value": 3.0, "uncapped": 4.3, "basis": "COMPUTED"}, "blockers": [], "version": "1"}
    out = C.from_control_summary("lake-brain", live)
    assert out["lifecycle"] == "CALIBRATION" and out["legacyLifecycle"] == "BETA" and out["lifecycleMappingAmbiguous"] is True
    assert (out["canonicalScore"], out["underlyingScore"], out["displayedScore"]) == (3.0, 4.3, 3.0)
    assert "blockers" not in out and "coverage" not in out                              # empty / absent are omitted, never defaulted
    C.validate_control(out)
    assert "score" not in out


def test_unscored_brain_has_no_score_fields_not_zero():
    out = C.from_control_summary("depth", {"status": "PROFILED"})
    assert "canonicalScore" not in out and "displayedScore" not in out
