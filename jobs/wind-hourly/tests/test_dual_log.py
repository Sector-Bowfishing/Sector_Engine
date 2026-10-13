import json
from datetime import datetime, timezone

import pytest

from sector_wind import dual_log as DL
from sector_wind.brain import contract as C

UTC = timezone.utc
T0 = datetime(2026, 9, 20, 18, 0, tzinfo=UTC)           # pre-H2
V0 = datetime(2026, 9, 21, 2, 0, tzinfo=UTC)
CUST = {"speedMph": 6.0, "directionDeg": 225, "gustMph": 9.0, "fetchedAt": "2026-09-20T18:00:02Z", "host": "primary"}
CAND = {"speedMph": 4.0, "directionDeg": 250, "p90Mph": 10.5, "forecastInit": "2026-09-20T12:00:00Z"}


def test_record_fields_and_disagreement_is_not_accuracy():
    r = DL.build_record("Guntersville|AL", T0, V0, CUST, CAND, {"published": True, "generatedAt": "2026-09-20T18:06:00Z", "stale": False})
    assert r["schema"] == DL.SCHEMA and r["forecastHorizonHours"] == 8.0 and r["forecastInitAgeHours"] == 6.0
    assert r["comparison"]["kind"] == "PROVIDER_DISAGREEMENT" and r["comparison"]["accuracyClaim"] is False and r["truth"] is None
    assert r["comparison"]["speedDiffMph"] == -2.0 and r["comparison"]["directionDiffDeg"] is None and r["candidateProvider"]["riskFlag"] is True      # candidate 4 mph: direction not compared
    both = DL.build_record("L|XX", T0, V0, CUST, {**CAND, "speedMph": 6.5})
    assert both["comparison"]["directionDiffDeg"] == 25
    assert r["customerProvider"]["category"] == "light" and r["candidateProvider"]["category"] == "calm" and r["comparison"]["categoryAgree"] is False
    assert r["candidateProvider"]["stale"] is True                                      # 6 h old cycle > 3 h rule


def test_direction_not_compared_below_5mph_and_unknown_stays_null():
    r = DL.build_record("L|XX", T0, V0, {**CUST, "speedMph": 3.0}, CAND)
    assert r["comparison"]["directionDiffDeg"] is None
    down = DL.build_record("L|XX", T0, V0, None, CAND)
    assert down["customerProvider"]["available"] is False and down["customerProvider"]["speedMph"] is None and down["comparison"]["speedDiffMph"] is None
    assert down["comparison"]["categoryAgree"] is None                                  # not False: unknown
    none = DL.build_record("L|XX", T0, V0, CUST, None)
    assert none["candidateProvider"]["available"] is False and none["candidateProvider"]["riskFlag"] is None


def test_fallback_host_is_recorded():
    r = DL.build_record("L|XX", T0, V0, {**CUST, "host": "fallback"}, CAND)
    assert r["customerProvider"]["usedFallbackHost"] is True


def test_truth_attaches_only_for_pre_h2_and_within_30_minutes():
    r = DL.build_record("Guntersville|AL", T0, V0, CUST, CAND)
    obs = {"station": "HSV", "observedAt": "2026-09-21T02:00:00Z", "speedMph": 8.0, "directionDeg": 230, "distanceKm": 19.0}
    t = DL.attach_truth(r, obs, now=datetime(2026, 12, 1, tzinfo=UTC))
    assert t["truth"]["landReferenced"] is True and t["comparison"]["kind"] == "ACCURACY_ELIGIBLE" and t["comparison"]["accuracyClaim"] is False
    assert t["comparison"]["customerSpeedErrMph"] == -2.0 and t["comparison"]["candidateSpeedErrMph"] == -4.0
    assert r["truth"] is None and r["comparison"]["kind"] == "PROVIDER_DISAGREEMENT"       # original untouched
    with pytest.raises(ValueError):
        DL.attach_truth(r, {**obs, "observedAt": "2026-09-21T03:00:00Z"})


def test_h2_window_records_cannot_get_truth_before_the_seal_opens():
    r = DL.build_record("Guntersville|AL", datetime(2026, 10, 20, 18, tzinfo=UTC), datetime(2026, 10, 21, 2, tzinfo=UTC), CUST, CAND)
    obs = {"station": "HSV", "observedAt": "2026-10-21T02:00:00Z", "speedMph": 8.0, "directionDeg": 230}
    with pytest.raises(PermissionError, match="H2 window"):
        DL.attach_truth(r, obs, now=datetime(2026, 12, 31, 23, 59, tzinfo=UTC))
    DL.attach_truth(r, obs, now=datetime(2027, 1, 2, tzinfo=UTC))                          # allowed once the seal opens


def test_growth_model_matches_the_design_claims():
    g = DL.growth_model()
    assert g["rowsPerDayFleet"] == 14904 and g["objectsPerDay"] == 24 and g["extraProviderCallsPerDay_designed"] == 240 and g["extraProviderCallsPerDay_fleetHourlyOpenMeteo"] == 14904
    assert g["gzMBPerMonth"] < 100
