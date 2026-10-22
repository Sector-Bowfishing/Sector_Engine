import pytest
from depth_brain.datum import assess, normalize_datum, provider_level_datum
from depth_research.candidates import load_provider_table


def test_normalize():
    assert normalize_datum("NGVD 29") == "NGVD29" and normalize_datum("navd88") == "NAVD88"
    assert normalize_datum(None) is None and normalize_datum("unrecorded") is None and normalize_datum("weird") is None


def test_same_source_is_compatible_without_datum_strings():
    a = assess(None, None, same_source=True)
    assert a.status == "SAME_SOURCE" and a.usable and a.sigma_ft == 0.0


def test_same_known_datum():
    a = assess("NGVD29", "NGVD29")
    assert a.status == "SAME_DATUM" and a.usable and a.sigma_ft > 0


def test_unknown_either_side_is_unknown():
    assert assess(None, "NGVD29").status == "UNKNOWN"
    assert assess("NGVD29", None).status == "UNKNOWN"
    assert not assess("NGVD29", None).usable


def test_unverified_datum_is_treated_as_unknown():
    assert assess("NGVD29", "NGVD29", level_datum_verified=False).status == "UNKNOWN"
    assert assess("NGVD29", "NGVD29", reference_datum_verified=False).status == "UNKNOWN"


def test_different_datums_without_conversion_are_incompatible():
    a = assess("NGVD29", "NAVD88")
    assert a.status == "INCOMPATIBLE" and not a.usable


def test_conversion_direction():
    # NAVD88 elevation = NGVD29 elevation + c.  Level in NGVD29, reference in NAVD88 -> add c to the level.
    a = assess("NGVD29", "NAVD88", navd88_minus_ngvd29_ft=0.4)
    assert a.status == "CONVERTED" and a.conversion_ft == pytest.approx(0.4) and a.usable and a.sigma_ft > 0
    b = assess("NAVD88", "NGVD29", navd88_minus_ngvd29_ft=0.4)
    assert b.conversion_ft == pytest.approx(-0.4)


def test_local_and_project_datums_are_not_proof_of_equality():
    assert assess("LOCAL", "LOCAL").status == "UNKNOWN"
    assert assess("PROJECT", "PROJECT").status == "UNKNOWN"
    assert assess("LOCAL", "NGVD29").status == "INCOMPATIBLE"


def test_per_site_is_unknown():
    assert assess("PER_SITE", "NGVD29").status == "UNKNOWN"


def test_provider_table_missing_provider_is_unknown():
    d, ver, raw = provider_level_datum({"providers": {}}, "nobody")
    assert d is None and ver is False


def test_provider_table_requires_verified_doc():
    t = {"providers": {"tva": {"levelDatum": "NGVD29", "levelDatumBasis": "inferred"}, "cwms": {"levelDatum": "NGVD29", "levelDatumBasis": "verified_doc"}}}
    assert provider_level_datum(t, "tva") == ("NGVD29", False, "NGVD29")
    assert provider_level_datum(t, "cwms")[1] is True


def test_load_missing_table_is_empty_not_error(tmp_path):
    assert load_provider_table(str(tmp_path / "nope.json"))["providers"] == {}
