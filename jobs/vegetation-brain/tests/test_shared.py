from datetime import date, datetime, timezone

import pytest

from vegetation_brain import contract as C
from vegetation_brain import shared as SH
from vegetation_brain import state as S

REF = date(2026, 10, 10)
NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
CAND = {"lakeId": "Big|AL", "tier": "HIGH", "readiness": "PROFILED", "reasons": [], "areaKm2": 266.8, "geometryConfidence": "HIGH", "geometryVersion": "v1"}


def clarity_json(d, grass, measured, bank=8.0, ids=("S2A_X",)):
    return {"pass": {"date": d, "platform": "sentinel-2a", "sceneIds": list(ids)}, "grassPct": grass, "measuredPct": measured,
            "fill": {"grassToBankPct": bank, "grassUnderCloudPct": 0.5}}


def P(d, grass=20.0, measured=50.0, bank=8.0, codes=None):
    return SH.pass_from_clarity_json(clarity_json(d, grass, measured, bank, (f"S_{d}",)), codes)


def test_bed_to_bank_strip_is_removed_from_the_observed_share():
    p = P("2026-10-08", grass=20.0, bank=8.0)
    assert p.observed_grass_pct == pytest.approx(12.0)
    assert P("2026-10-08", grass=3.0, bank=8.0).observed_grass_pct == 0.0           # never negative


def test_png_code_shares_give_known_share_and_refusals():
    codes = {255: 600, 3: 100, 2: 200, 1: 100, 0: 5000}                              # off-lake cells ignored
    p = P("2026-10-08", codes=codes)
    assert p.known_pct == pytest.approx(70.0)
    obs = SH.observe_shared([p], REF, 100.0)
    assert obs.refusal_shares["CLOUD_OR_HAZE"] == pytest.approx(0.2) and obs.refusal_shares["UNREADABLE_WATER"] == pytest.approx(0.1)
    assert set(obs.refusal_shares) <= set(C.REFUSALS)


def test_persistence_median_and_present_when_area_large_enough():
    passes = [P("2026-10-01", grass=18, measured=50), P("2026-10-05", grass=22, measured=45), P("2026-10-08", grass=21, measured=52)]
    obs = SH.observe_shared(passes, REF, 266.8)
    assert obs.evidence_kind == "SATELLITE_PERSISTENCE" and obs.persistence == "MEDIAN_OF_ACCEPTED"
    assert obs.shared_presence[0] == "PRESENT" and obs.observed_share_pct == pytest.approx(13.0)
    assert obs.observed_area_km2 == pytest.approx(0.13 * 266.8, rel=1e-3)


def test_a_burst_pass_is_excluded_and_a_lone_pass_cannot_be_burst_checked():
    passes = [P("2026-10-01", grass=10), P("2026-10-05", grass=11), P("2026-10-08", grass=12), P("2026-10-09", grass=70)]
    obs = SH.observe_shared(passes, REF, 100.0)
    assert any("burst" in n for n in obs.notes) and obs.observed_share_pct < 10
    lone = SH.observe_shared([P("2026-10-08")], REF, 100.0)
    assert lone.evidence_kind == "SATELLITE_ACCEPTED_PASS" and lone.persistence == "INSUFFICIENT"
    assert any("burst check" in n for n in lone.notes)


def test_low_coverage_is_unknown_not_none_and_fallback_is_flagged():
    cloudy = SH.observe_shared([P("2026-10-08", grass=1, measured=10)], REF, 100.0)
    assert cloudy.evidence_kind == "NONE" and cloudy.shared_presence[0] == "UNKNOWN"
    fb = SH.observe_shared([P("2026-10-08", grass=1, measured=30)], REF, 100.0)
    assert fb.low_coverage_fallback and fb.shared_presence[0] == "UNKNOWN"          # a fallback pass can never assert NOT_OBSERVED
    clear = SH.observe_shared([P("2026-10-08", grass=0.0, measured=80, bank=0.0)], REF, 100.0)
    assert clear.shared_presence[0] == "NOT_OBSERVED"


def test_no_max_composite_and_out_of_window_ignored():
    with pytest.raises(ValueError):
        SH.observe_shared([], REF, 10.0, mode="max")
    assert SH.observe_shared([P("2026-08-01")], REF, 10.0).shared_presence == ("UNKNOWN", "NO_SCENE")


def test_state_from_shared_evidence_is_likely_never_observed_and_names_its_source():
    passes = [P("2026-10-01", grass=18), P("2026-10-05", grass=22), P("2026-10-08", grass=21)]
    st, meta = S.build_state(CAND, SH.observe_shared(passes, REF, 266.8), NOW)
    sv = st["surfaceVegetation"]
    assert sv["status"] == "PRESENT" and st["headline"] == C.LANGUAGE["LIKELY"]
    assert sv["source"]["sourceId"] == C.SHARED_SOURCE_ID and sv["observedAreaKm2"] > 0
    assert st["provenance"]["sources"][0]["sourceType"] == "sharedEvidence"
    assert st["submergedVegetation"]["observed"] is False and sv["coverageClass"] == "NOT_CALIBRATED"
    assert st["claimMaturity"]["surfaceVegetationPresence"]["state"] == "NOT_VALIDATED"
    assert sv["confidence"]["score"] <= S.VALIDATION_CAP["NOT_VALIDATED"]
    assert len(__import__("json").dumps(st)) < 12000                                  # the state stays compact


def test_fingerprint_changes_when_a_new_pass_arrives_and_not_otherwise():
    a = SH.observe_shared([P("2026-10-01", grass=18), P("2026-10-05", grass=22), P("2026-10-08", grass=21)], REF, 266.8)
    a2 = SH.observe_shared([P("2026-10-01", grass=18), P("2026-10-05", grass=22), P("2026-10-08", grass=21)], REF, 266.8)
    b = SH.observe_shared([P("2026-10-01", grass=18), P("2026-10-05", grass=22), P("2026-10-08", grass=21), P("2026-10-09", grass=40, measured=60)], REF, 266.8)
    fa = S.input_fingerprint(CAND, a, {}, "t")
    assert fa == S.input_fingerprint(CAND, a2, {}, "t") and fa != S.input_fingerprint(CAND, b, {}, "t")
