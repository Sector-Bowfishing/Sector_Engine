import math
from datetime import timedelta

import pytest
from depth_brain import contract as C
from depth_brain.datum import DatumAssessment
from depth_brain.shift import LevelObservation, ReferencePool, compute_shift, apply_shift
from tests.helpers import NOW

OK = DatumAssessment("SAME_DATUM", 0.1)


def ref(pool=595.0, conf="high", basis="fullPool", a=OK):
    return ReferencePool(pool, basis, conf, "NGVD29", True, "t", a)


def lvl(e=593.6, age_h=1.0, cap="DIRECT_OPERATOR_POOL", kind="OBSERVED", unit="ft", datum=None, diff=None):
    return LevelObservation(e, unit, datum, NOW - timedelta(hours=age_h), cap, kind, diff)


def test_negative_delta_sign_convention():
    r = compute_shift(lvl(593.6), ref(), NOW)
    assert r.mode == "shiftOnly" and r.shift_ft == pytest.approx(-1.4)          # lake LOWER than pool -> negative
    assert apply_shift(4.0, r.shift_ft) == pytest.approx(2.6)                    # a 4 ft reference flat is now ~2.6 ft


def test_positive_delta():
    r = compute_shift(lvl(596.2), ref(), NOW)
    assert r.shift_ft == pytest.approx(1.2) and apply_shift(4.0, r.shift_ft) == pytest.approx(5.2)


def test_zero_delta():
    r = compute_shift(lvl(595.0), ref(), NOW)
    assert r.shift_ft == pytest.approx(0.0) and r.resolvable is False


def test_dry_when_shift_exceeds_reference_depth():
    assert apply_shift(4.0, -9.1) < 0


def test_missing_reference_pool():
    assert compute_shift(lvl(), ReferencePool(None), NOW).reasons == ["MISSING_REFERENCE_POOL"]
    assert compute_shift(lvl(), None, NOW).mode == "unknown"


def test_missing_current_level():
    assert compute_shift(None, ref(), NOW).reasons == ["MISSING_CURRENT_LEVEL"]
    assert compute_shift(lvl(e=None), ref(), NOW).reasons == ["MISSING_CURRENT_LEVEL"]
    assert compute_shift(lvl(e=float("nan")), ref(), NOW).mode == "unknown"


def test_stale_level_flagged_then_refused():
    r = compute_shift(lvl(age_h=7), ref(), NOW)
    assert r.mode == "shiftOnly" and r.evidence_stale and "levelObservationOlderThanFreshWindow" in r.flags
    old = compute_shift(lvl(age_h=60), ref(), NOW)
    assert old.mode == "unknown" and old.reasons == ["LEVEL_TOO_OLD"]


def test_future_observation_refused():
    assert compute_shift(lvl(age_h=-3), ref(), NOW).reasons == ["OBSERVATION_IN_FUTURE"]


def test_proxy_or_nearby_gauge_never_yields_a_shift():
    assert compute_shift(lvl(kind="PROXY", cap="NEARBY_GAUGE_PROXY"), ref(), NOW).reasons == ["LEVEL_NOT_DIRECT_OBSERVATION"]
    assert compute_shift(lvl(cap="NEARBY_GAUGE_PROXY"), ref(), NOW).reasons == ["LEVEL_SOURCE_NOT_DIRECT"]
    assert compute_shift(lvl(cap=None), ref(), NOW).mode == "unknown"


def test_unit_must_be_feet():
    assert compute_shift(lvl(unit="m"), ref(), NOW).reasons == ["LEVEL_UNIT_NOT_FEET"]


def test_reference_must_be_a_pool_elevation_with_adequate_confidence():
    assert compute_shift(lvl(), ref(basis="naturalSurface"), NOW).reasons == ["REFERENCE_NOT_A_POOL_ELEVATION"]
    assert compute_shift(lvl(), ref(conf="low"), NOW).reasons == ["REFERENCE_POOL_CONFIDENCE_LOW"]
    assert compute_shift(lvl(), ref(conf=None), NOW).mode == "unknown"


def test_incompatible_or_unknown_datum_gives_unknown_not_a_number():
    for st, reason in (("UNKNOWN", "DATUM_UNKNOWN"), ("INCOMPATIBLE", "DATUM_INCOMPATIBLE")):
        r = compute_shift(lvl(), ref(a=DatumAssessment(st)), NOW)
        assert r.mode == "unknown" and r.reasons == [reason] and r.shift_ft is None
    assert compute_shift(lvl(), ref(a=None), NOW).reasons == ["DATUM_UNKNOWN"]


def test_live_datum_conflict_with_audit_refuses():
    r = compute_shift(lvl(datum="NAVD88"), ref(), NOW, manifest_level_datum="NGVD29")
    assert r.reasons == ["LEVEL_DATUM_CONFLICT"]
    ok = compute_shift(lvl(datum="NGVD29"), ref(), NOW, manifest_level_datum="NGVD29")
    assert ok.mode == "shiftOnly"
    assert compute_shift(lvl(datum=None), ref(), NOW, manifest_level_datum="NGVD29").mode == "shiftOnly"   # TVA stamps no datum


def test_converted_datum_applies_conversion_to_the_level():
    a = DatumAssessment("CONVERTED", 0.3, 0.4, ["x"])
    r = compute_shift(lvl(593.6), ref(a=a), NOW)
    assert r.shift_ft == pytest.approx(593.6 + 0.4 - 595.0)
    assert r.sigma_parts["datum"] == 0.3


def test_implausible_shift_is_a_datum_or_unit_error():
    r = compute_shift(lvl(e=595.0 - 150), ref(), NOW)
    assert r.reasons == ["IMPLAUSIBLE_SHIFT"]


def test_uncertainty_propagation_is_quadrature_of_components():
    r = compute_shift(lvl(), ref(conf="high"), NOW)
    exp = math.sqrt(C.SIGMA_POOL["high"] ** 2 + C.SIGMA_LEVEL["DIRECT_OPERATOR_POOL"] ** 2 + C.SIGMA_DATUM["SAME_DATUM"] ** 2)
    assert r.sigma_ft == pytest.approx(exp) and r.confidence == "HIGH"
    m = compute_shift(lvl(), ref(conf="medium"), NOW)
    assert m.sigma_ft > 1.0 and m.confidence == "MEDIUM" and m.sigma_ft > r.sigma_ft
    s = compute_shift(lvl(), ref(conf="high", a=DatumAssessment("SAME_SOURCE", 0.0)), NOW)
    assert s.sigma_ft < r.sigma_ft


def test_resolvable_flag_needs_two_sigma():
    assert compute_shift(lvl(593.6), ref(), NOW).resolvable is True          # -1.4 vs sigma 0.29
    assert compute_shift(lvl(594.8), ref(), NOW).resolvable is False         # -0.2


def test_lake_brain_disagreement_is_flagged_not_hidden():
    r = compute_shift(lvl(593.6, diff=-2.4), ref(), NOW)
    assert any(f.startswith("lakeBrainDeltaDisagrees") for f in r.flags)
    assert not compute_shift(lvl(593.6, diff=-1.4), ref(), NOW).flags


def test_deterministic():
    a = compute_shift(lvl(), ref(), NOW).as_dict()
    b = compute_shift(lvl(), ref(), NOW).as_dict()
    assert a == b


def test_as_dict_unknown_has_reasons_and_no_numbers():
    d = compute_shift(None, ref(), NOW).as_dict()
    assert d["mode"] == "unknown" and "shiftFt" not in d and d["reasons"]
