from datetime import datetime, timezone
from sector_wind.brain import quick_observation as Q, field_schema as FS

NOW = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)
OK = {"schema": Q.SCHEMA, "tripId": "G|2026-10-19|mc", "lakeId": "Guntersville|AL", "bankId": "E-0042", "observedAtUtc": "2026-10-20T02:30:00Z", "observer": "mc",
      "exposureObserved": "PARTIAL", "surfaceObserved": "MODERATE", "sawPrediction": False}


def test_valid_quick_record_and_each_rule_fails_closed():
    assert Q.validate_quick(OK, NOW) == []
    for k, v in (("sawPrediction", None), ("exposureObserved", "HIGH"), ("surfaceObserved", "wavy"), ("observedAtUtc", "2026-10-21T00:00:00Z"), ("tripId", "")):
        assert Q.validate_quick({**OK, k: v}, NOW), k
    assert Q.validate_quick({**OK, "prediction": "x"}, NOW) and Q.validate_quick({k: v for k, v in OK.items() if k != "bankId"}, NOW)
    assert Q.validate_quick({**{k: v for k, v in OK.items() if k != "bankId"}, "lat": 34.4, "lon": -86.3}, NOW) == []


def test_bridge_to_frozen_v2_validates_and_flags_derived_fields():
    v2 = Q.to_v2(OK, NOW)
    assert v2["bankImpactObserved"] == "CROSS" and v2["roughnessObserved"] == "choppy" and v2["derived"] == ["boatability", "observerConfidence"]
    assert FS.validate_observation(v2, NOW) == []
    assert Q.to_v2({**OK, "surfaceObserved": "UNKNOWN"}, NOW) is None and Q.to_v2({**OK, "sawPrediction": None}, NOW) is None


def test_model_vocabulary_and_exposure_agreement_with_dangerous_miss():
    assert [Q.model_to_product(x) for x in ("DIRECT", "CROSS", "PROTECTED", "EXPOSED", "UNKNOWN")] == ["EXPOSED", "PARTIAL", "PROTECTED", "EXPOSED", "UNKNOWN"]
    r = Q.exposure_agreement([("PROTECTED", "PROTECTED"), ("PROTECTED", "EXPOSED"), ("EXPOSED", "PROTECTED"), ("PARTIAL", "EXPOSED"), ("UNKNOWN", "EXPOSED")])
    assert r["observations"] == 5 and r["called"] == 4 and r["unknownShare"] == 0.2 and r["exact"] == 0.25 and r["withinOne"] == 0.5
    assert r["dangerousMiss"] == 1 and r["protectedCalls"] == 2 and r["dangerousMissRate"] == 0.5 and r["lostOpportunity"] == 1


def test_nearest_bank_within_radius_only():
    banks = [{"id": "a", "anchor": [34.400, -86.300]}, {"id": "b", "anchor": [34.410, -86.300]}]
    assert Q.nearest_bank(34.4003, -86.3, banks)[0]["id"] == "a"
    assert Q.nearest_bank(34.45, -86.3, banks)[0] is None
