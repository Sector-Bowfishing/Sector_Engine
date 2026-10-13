import json
import os
import re
from datetime import datetime, timezone

import pytest

from helpers import REF, patch, scene
from vegetation_brain import contract as C
from vegetation_brain import observer as O
from vegetation_brain import state as S
from vegetation_brain.language import assert_clean, headline

NOW = datetime(2025, 7, 22, 12, 0, tzinfo=timezone.utc)
CAND = {"lakeId": "Test Lake|AL", "tier": "HIGH", "readiness": "PROFILED", "reasons": [], "areaKm2": 40.0, "geometryConfidence": "HIGH", "geometryVersion": "v1"}
BED = patch((30, 60), (30, 60))


def obs_present():
    return O.observe([scene("s1", REF, plant=BED), scene("s2", REF, plant=BED), scene("s3", REF, plant=BED)], REF, mode="P")


def build(cand=CAND, obs=None, **kw):
    return S.build_state(cand, obs, NOW, **kw)


# ---------------------------------------------------------------- state shape and honesty
def test_unobserved_lake_is_unknown_not_none():
    st, meta = build()
    assert st["surfaceVegetation"]["status"] == "UNKNOWN" and st["kind"] == "unavailable"
    assert st["headline"] == C.LANGUAGE["NONE"]
    assert meta["readiness"] == "PROFILED"
    assert st["validation"]["state"] == "NOT_VALIDATED"


def test_blocked_lake_has_reason_and_no_observation():
    cand = {**CAND, "tier": "UNKNOWN", "readiness": "BLOCKED", "reasons": ["NO_GEOMETRY"], "areaKm2": None, "geometryConfidence": "MISSING"}
    st, meta = build(cand)
    assert meta["readiness"] == "BLOCKED"
    assert st["surfaceVegetation"]["statusReason"] == "NO_GEOMETRY"


def test_present_but_not_validated_is_only_likely_never_observed_never_grass_here():
    st, meta = build(obs=obs_present())
    sv = st["surfaceVegetation"]
    assert sv["status"] == "PRESENT"
    assert st["headline"] == C.LANGUAGE["LIKELY"]
    assert "grass" not in st["headline"].lower()
    assert sv["broadType"] == "SURFACE_REACHING_MIXED" and sv["typeBasis"] == "NOT_CLASSIFIED"
    assert sv["confidence"]["level"] in ("LOW", "MEDIUM") and sv["confidence"]["score"] <= S.VALIDATION_CAP["NOT_VALIDATED"]
    assert meta["readiness"] == "CALIBRATION"


def test_observed_wording_requires_partial_validation():
    st, _ = build(obs=obs_present(), validation={"state": "PARTIAL"})
    assert st["headline"] == C.LANGUAGE["OBSERVED"]


def test_submerged_is_never_observed_whatever_the_inputs():
    for validation in ("NOT_VALIDATED", "VALIDATED"):
        st, _ = build(obs=obs_present(), validation={"state": validation},
                      context={"depth": {"tier": "A", "evidenceKind": "measured"}, "clarity": {"secchiM": 3.0, "confidence": 0.9}})
        assert st["submergedVegetation"]["observed"] is False and st["submergedVegetation"]["status"] == "NOT_OBSERVABLE"
        assert st["surfaceVegetation"]["broadType"] != "SUBMERGED"
        assert "submerged" not in json.dumps(st["surfaceVegetation"]).lower()


def test_density_not_calibrated_until_gate_and_percentages_never_published():
    st, _ = build(obs=obs_present())
    assert st["surfaceVegetation"]["coverageClass"] == "NOT_CALIBRATED"
    assert "coverShare" not in st["surfaceVegetation"] and "coverPercent" not in st["surfaceVegetation"]
    st2, _ = build(obs=obs_present(), context={"density": {"gatePassed": True, "thresholds": {"moderate": 0.05, "dense": 0.25}}})
    assert st2["surfaceVegetation"]["coverageClass"] in ("SPARSE", "MODERATE", "DENSE")


def test_seasonal_unknown_until_backtest_gate():
    st, _ = build(obs=obs_present(), context={"seasonal": {"state": "PEAK", "gatePassed": False}})
    assert st["seasonalState"]["state"] == "UNKNOWN" and st["seasonalState"]["backtestGate"] == "NOT_PASSED"
    st2, _ = build(obs=obs_present(), context={"seasonal": {"state": "PEAK", "gatePassed": True}})
    assert st2["seasonalState"]["state"] == "PEAK"


def test_old_observation_is_stale_and_headline_says_no_reliable_observation():
    old = O.observe([scene("o", REF, plant=BED)] * 3, REF, mode="P")
    st, meta = S.build_state(CAND, old, datetime(2025, 10, 30, tzinfo=timezone.utc))
    assert meta["stale"] and st["headline"] == C.LANGUAGE["NONE"]
    assert meta["readiness"] == "DEGRADED"
    assert st["freshness"]["evidenceStale"] is True


def test_confidence_capped_by_validation_state_and_geometry():
    hi = S.confidence("SATELLITE_PERSISTENCE", "NOT_VALIDATED", coverage=1.0, geometry_conf="HIGH", persistence_n=5)
    assert hi["score"] <= 0.45 and hi["basis"] == "RULE_BASED_NOT_CALIBRATED"
    ok = S.confidence("SATELLITE_PERSISTENCE", "PARTIAL", coverage=1.0, geometry_conf="HIGH", persistence_n=5)
    low = S.confidence("SATELLITE_PERSISTENCE", "PARTIAL", coverage=1.0, geometry_conf="LOW", persistence_n=5)
    assert ok["score"] > low["score"]


def test_product_language_closed_set_and_forbidden_phrases():
    for v in C.LANGUAGE.values():
        assert_clean(v)
    for bad in ("Grass is here", "hydrilla spotted", "submerged vegetation observed"):
        with pytest.raises(ValueError):
            assert_clean(bad)
    assert headline("PRESENT", "NOT_VALIDATED", stale=False, potential_only=True) == C.LANGUAGE["POTENTIAL"]


# ---------------------------------------------------------------- potential habitat
def test_potential_habitat_semantics_always_potential_only():
    st, _ = build()
    ph = st["potentialHabitat"]
    assert ph["potentialOnly"] is True and ph["observed"] is False
    assert ph["status"] == "NOT_EVALUATED" and "DEPTH_BRAIN_UNAVAILABLE" in ph["reasons"]
    assert ph["headline"] == C.LANGUAGE["POTENTIAL"]


def test_potential_habitat_refuses_modeled_depth():
    for kind, tier in (("modeled", "D"), ("proxy", "D"), ("measured", "D"), (None, None)):
        with pytest.raises(ValueError):
            S.assert_allowed_potential_basis(kind, tier)
    ph = S.potential_habitat({"tier": "D", "evidenceKind": "modeled", "source": "GLOBathy"}, {"secchiM": 2.0}, None)
    assert ph["status"] == "NOT_EVALUATED" and "DEPTH_EVIDENCE_NOT_ALLOWED" in ph["reasons"]


def test_potential_habitat_with_real_depth_and_clarity_has_ci_and_stays_potential():
    ph = S.potential_habitat({"tier": "B", "evidenceKind": "contour"}, {"secchiM": 2.0, "confidence": 0.7}, {"poolAnomalyFt": -1.2})
    assert ph["status"] == "EVALUATED" and ph["potentialOnly"] is True and ph["observed"] is False
    c = ph["maxColonizationDepthFt"]
    assert c["lowFt"] < c["centralFt"] < c["highFt"]
    assert abs(c["centralFt"] - 9.2) < 0.3          # Canfield pooled: SD 2 m -> 2.8 m = 9.2 ft


def test_clarity_does_not_become_vegetation():
    st, _ = build(context={"clarity": {"secchiM": 4.0, "confidence": 0.9}})
    assert st["surfaceVegetation"]["status"] == "UNKNOWN"      # clear water alone never yields detection


# ---------------------------------------------------------------- cross-brain contracts (read-only context)
def test_context_is_consumed_by_reference_not_recomputed():
    ctx = {"lake": {"poolAnomalyFt": 1.5, "confidence": "high"}, "depth": None, "clarity": {"secchiM": 1.5, "confidence": 0.8},
           "temp": {"waterTempF": 71.0}, "wind": {"surfaceDisturbed": False}}
    st, _ = build(obs=obs_present(), context=ctx)
    cons = st["context"]["consumed"]
    assert cons["lake"]["consumed"] and cons["clarity"]["consumed"] and not cons["depth"]["consumed"]
    blob = json.dumps(st)
    for owned_elsewhere in ("poolAnomalyFt\": 1.5", "waterTempF", "differenceFromNormalPool"):
        # Lake/Temp numbers are not republished in the surface state (potentialHabitat may echo pool anomaly only when EVALUATED)
        assert owned_elsewhere not in json.dumps(st["surfaceVegetation"])


def test_wind_disturbance_lowers_confidence_but_vegetation_computes_no_wind():
    a, _ = build(obs=obs_present(), validation={"state": "PARTIAL"}, context={"wind": {"surfaceDisturbed": False}})
    b, _ = build(obs=obs_present(), validation={"state": "PARTIAL"}, context={"wind": {"surfaceDisturbed": True}})
    assert b["surfaceVegetation"]["confidence"]["score"] < a["surfaceVegetation"]["confidence"]["score"]
    assert "windSpeed" not in json.dumps(b)


def test_temp_context_does_not_create_a_competing_temperature_model():
    st, _ = build(obs=obs_present(), context={"temp": {"waterTempF": 80.0, "gdd10": 900}})
    assert st["seasonalState"]["state"] == "UNKNOWN"           # temperature alone never sets a seasonal state


def test_intelligence_block_separates_plant_state_from_value_and_shootability():
    st, _ = build(obs=obs_present())
    fi = st["forIntelligence"]
    assert {"presence", "broadType", "coverageClass", "seasonalState", "observationAgeDays", "evidenceKind", "confidence", "stale"} <= set(fi)
    assert not ({"habitatValue", "shootability", "obstruction", "fishUse", "species"} & set(fi))
    assert "Intelligence" in fi["separation"]


def test_biological_owns_species_preference_nothing_species_in_state():
    st, _ = build(obs=obs_present())
    blob = json.dumps(st).lower()
    for sp in ("carp", "buffalo", "gar", "bass", "hydrilla", "milfoil", "lily", "lotus"):
        assert sp not in blob


# ---------------------------------------------------------------- fingerprint
def test_fingerprint_changes_with_scene_and_context():
    a, _ = build(obs=obs_present())
    b, _ = build(obs=obs_present(), context={"wind": {"surfaceDisturbed": True}})
    assert a["provenance"]["inputFingerprint"] != b["provenance"]["inputFingerprint"]


# ---------------------------------------------------------------- private / public boundary
def test_package_source_has_no_credentials_or_private_paths():
    root = os.path.join(os.path.dirname(__file__), "..", "vegetation_brain")
    pat = re.compile(r"(AKIA[0-9A-Z]{12}|-----BEGIN|api[_-]?key\s*[=:]\s*['\"][A-Za-z0-9]{16,}|/Users/|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,})")
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".py", ".json", ".csv", ".md")):
                txt = open(os.path.join(dp, f)).read()
                assert not pat.search(txt), f"{f} matches a secret/private-path pattern"


def test_single_unaccepted_pass_is_never_published_as_presence():
    one = O.observe([scene("s", REF, plant=BED)], REF, mode="S")
    assert one.evidence_kind == "SATELLITE_SINGLE_PASS"
    st, _ = build(obs=one)
    assert st["surfaceVegetation"]["status"] == "UNKNOWN" and st["surfaceVegetation"]["statusReason"] == "PASS_NOT_ACCEPTED"


def test_limitations_state_interior_only_and_burst_risk():
    st, _ = build(obs=obs_present())
    text = " ".join(st["limitations"]).lower()
    assert "interior-only" in text and "burst" in text and "presence-only" in text
