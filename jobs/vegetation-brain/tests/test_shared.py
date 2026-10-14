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


# ---------------------------------------------------------------- zones: where the persistent surface vegetation is
import numpy as np  # noqa: E402

CORNERS = {"west": -86.0, "east": -85.9, "north": 34.6, "south": 34.5}


def codes(h=120, w=120, grass=((20, 40, 20, 50),), cloud=None):
    a = np.full((h, w), 255, "uint8")
    for r0, r1, c0, c1 in grass:
        a[r0:r1, c0:c1] = 3
    if cloud:
        r0, r1, c0, c1 = cloud
        a[r0:r1, c0:c1] = 2
    return a


def test_persistent_bed_becomes_a_zone_with_area_and_centroid_inside_the_extent():
    stack = [codes(), codes(), codes()]
    z = SH.zones_from_codes(stack, CORNERS, 36.0, min_km2=0.0001)
    assert z["status"] == "OK" and len(z["zones"]) == 1
    zone = z["zones"][0]
    assert zone["persistence"] == pytest.approx(1.0, abs=0.06) and zone["looks"] == 3
    assert CORNERS["west"] < zone["centroid"][0] < CORNERS["east"] and CORNERS["south"] < zone["centroid"][1] < CORNERS["north"]
    import math
    expect = 20 * 30 * (36.0 * math.cos(math.radians(34.55))) ** 2 / 1e6
    assert zone["areaKm2"] == pytest.approx(expect, rel=0.15)


def test_a_one_pass_blob_is_not_persistent_and_cloud_is_not_a_look():
    stack = [codes(grass=()), codes(grass=()), codes(grass=((70, 90, 70, 90),))]
    assert SH.zones_from_codes(stack, CORNERS, 36.0, min_km2=0.0001)["zones"] == []
    cloudy = [codes(cloud=(20, 40, 20, 50)), codes(cloud=(20, 40, 20, 50)), codes()]
    # only one pass looked at the bed: fewer than ZONE_MIN_KNOWN looks => no zone
    assert SH.zones_from_codes(cloudy, CORNERS, 36.0, min_km2=0.0001)["zones"] == []


def test_two_beds_are_ranked_by_area_and_limited_to_top_five():
    stack = [codes(grass=((10, 30, 10, 30), (60, 100, 60, 110))) for _ in range(3)]
    zs = SH.zones_from_codes(stack, CORNERS, 36.0, min_km2=0.0001)["zones"]
    assert len(zs) == 2 and zs[0]["areaKm2"] > zs[1]["areaKm2"]
    many = [codes(h=300, w=300, grass=tuple((r, r + 6, c, c + 6) for r in range(10, 280, 24) for c in range(10, 280, 24))) for _ in range(3)]
    assert len(SH.zones_from_codes(many, CORNERS, 36.0, min_km2=0.0001)["zones"]) == 5


def test_frame_mismatch_and_empty_input_are_refused_honestly():
    assert SH.zones_from_codes([], CORNERS, 36.0)["status"] == "NO_PASSES"
    assert SH.zones_from_codes([codes(), codes(h=60, w=60)], CORNERS, 36.0)["status"] == "FRAME_MISMATCH"


def test_zones_in_the_state_stay_compact_and_change_the_fingerprint():
    passes = [P("2026-10-01", grass=18), P("2026-10-05", grass=22), P("2026-10-08", grass=21)]
    o1 = SH.observe_shared(passes, REF, 266.8)
    o2 = SH.observe_shared(passes, REF, 266.8)
    o2.zones = SH.zones_from_codes([codes()] * 3, CORNERS, 36.0, min_km2=0.0001)
    s1, _ = S.build_state(CAND, o1, NOW)
    s2, _ = S.build_state(CAND, o2, NOW)
    assert s2["surfaceVegetation"]["zones"]["zones"] and len(__import__("json").dumps(s2)) < 14000
    assert s1["provenance"]["inputFingerprint"] != s2["provenance"]["inputFingerprint"]


# ---------------------------------------------------------------- amendment A6: presence ladder tied to the pre-registered tolerance
def _obs(grass, bank=0.0, measured=60.0):
    return SH.observe_shared([P("2026-10-08", grass=grass, measured=measured, bank=bank)], REF, 200.0)


def test_presence_ladder_present_unknown_not_observed():
    assert _obs(8.0).shared_presence[0] == "PRESENT"                       # 8 % > 2 % tolerance
    assert _obs(1.5).shared_presence == ("UNKNOWN", "BELOW_NOISE_TOLERANCE")   # between 0.5 and 2 %: not separable from noise, not 'none'
    assert _obs(0.3).shared_presence[0] == "NOT_OBSERVED"                  # <= 0.5 % on a real look
    assert _obs(2.0).shared_presence[0] == "UNKNOWN"                       # exactly the tolerance is not above it


def test_bank_strip_cannot_create_presence_and_fallback_cannot_assert_none():
    assert _obs(9.0, bank=8.5).shared_presence[0] != "PRESENT"             # 0.5 % observed after removing the painted strip
    fb = SH.observe_shared([P("2026-10-08", grass=0.0, measured=30.0, bank=0.0)], REF, 200.0)
    assert fb.low_coverage_fallback and fb.shared_presence[0] == "UNKNOWN"


def test_threshold_constants_come_from_the_preregistered_tolerance():
    from vegetation_brain import validation as V
    assert C.SHARED_PRESENT_MIN_SHARE_PCT == V.PARTIAL_MAX_FPR * 100
    assert C.SHARED_NOT_OBSERVED_MAX_SHARE_PCT < C.SHARED_PRESENT_MIN_SHARE_PCT
    assert "BELOW_NOISE_TOLERANCE" in C.REFUSALS and "BELOW_NOISE_TOLERANCE" in C.REFUSAL_DOC
