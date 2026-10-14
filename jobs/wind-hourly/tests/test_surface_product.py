from sector_wind.brain import surface_product as SP
from sector_wind.brain import field_schema as FS


def test_predicted_mapping_and_unknown_rules():
    assert [SP.predicted_class(c) for c in (1, 2, 3, 4, 5)] == ["CALM", "CALM", "MODERATE", "MODERATE", "ROUGH"]
    assert SP.predicted_class(5, confidence="boundary") == "UNKNOWN"
    assert SP.predicted_class(2, tier="POINT_ONLY") == "UNKNOWN"
    assert SP.predicted_class(2, below_resolution=True) == "UNKNOWN"
    assert SP.predicted_class(2, wind_available=False) == "UNKNOWN" and SP.predicted_class(9) == "UNKNOWN"


def test_every_field_roughness_value_maps():
    assert [SP.observed_class(r) for r in FS.ROUGHNESS] == ["CALM", "CALM", "MODERATE", "ROUGH"] and SP.observed_class("x") is None


def test_agreement_counts_unknown_as_coverage_and_flags_dangerous_miss():
    r = SP.agreement([("CALM", "CALM"), ("MODERATE", "ROUGH"), ("CALM", "ROUGH"), ("UNKNOWN", "ROUGH"), ("ROUGH", "ROUGH")])
    assert r["observations"] == 5 and r["called"] == 4 and r["unknownShare"] == 0.2
    assert r["exact"] == 0.5 and r["withinOne"] == 0.75 and r["roughCalledCalm"] == 1 and r["roughObserved"] == 3
    assert SP.agreement([])["exact"] is None
