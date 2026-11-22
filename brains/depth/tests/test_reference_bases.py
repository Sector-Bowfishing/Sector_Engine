"""Reference bases seriesMedian (same gauge, seasonal median) and lowWaterDatum (Great Lakes LWD, IGLD 1985).
Owner decision, Michael, 2026-11-22 (Sector_Ops #51 comment 7075545102)."""
import json
import os

import pytest
from depth_brain import contract as C
from depth_brain.datum import assess, normalize_datum
from depth_brain.shift import LevelObservation, ReferencePool, compute_shift
from depth_brain.state import build_state, input_fingerprint
from helpers import NOW, candidate, lake_state

from datetime import datetime, timezone

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
OBS = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)
BAND = {"p02": 588.0, "p10": 589.0, "p50": 590.0, "p90": 591.5, "p98": 592.0, "basisYears": 20, "windowDays": 7, "sampleCount": 290}


def series_candidate(**kw):
    rec = candidate(pool=None, conf=None, basis="seriesMedian", status="SAME_SERIES", sigma=0.0, level_datum=None, lakeId=kw.pop("lakeId", "Natural Lake|MN"), **kw)
    rec["reference"].update({"datum": None, "source": "lake-brain states/lake seasonalBand.p50 (this gauge's own history)"})
    rec["rollout"] = "MEDIUM_CONFIDENCE"
    return rec


def lwd_candidate(**kw):
    rec = candidate(pool=569.2, conf="high", basis="lowWaterDatum", status="SAME_DATUM", sigma=0.1, level_datum="IGLD85", lakeId=kw.pop("lakeId", "Lake Erie|OH"), **kw)
    rec["reference"].update({"datum": "IGLD85", "source": "Great Lakes Low Water Datum (erie), IGLD 1985: NOAA CO-OPS and CHS"})
    rec["rollout"] = "MEDIUM_CONFIDENCE"
    return rec


def series_state(elev=588.6, band=BAND, **kw):
    s = lake_state(elev, datum=None, cap="DIRECT_LAKE_GAUGE", **kw)
    if band is not None:
        s["seasonalBand"] = dict(band)
    return s


def lvl(elev, band=BAND, fallback=False, diff=None):
    return LevelObservation(elev, "ft", None, OBS, "DIRECT_LAKE_GAUGE", "OBSERVED", diff, seasonal_band=band, source_fallback=fallback)


def sref():
    return ReferencePool(None, "seriesMedian", None, None, assessment=assess(None, None, same_series=True))


# ── datum ────────────────────────────────────────────────────────────────────────────────────────────
def test_same_series_is_usable_with_zero_datum_sigma_and_igld85_normalizes():
    a = assess(None, None, same_series=True)
    assert a.status == "SAME_SERIES" and a.usable and a.sigma_ft == 0.0 == C.SIGMA_DATUM["SAME_SERIES"]
    for s in ("IGLD85", "IGLD 1985", "igld_1985", "IGLD-85"):
        assert normalize_datum(s) == "IGLD85", s
    assert normalize_datum("IGLD") is None                    # 1955 / 1985 / 2020 differ: a bare IGLD is unknown
    assert assess("IGLD85", "IGLD 1985").status == "SAME_DATUM"
    assert assess("IGLD85", "NAVD88").status == "INCOMPATIBLE"


# ── seriesMedian shift ───────────────────────────────────────────────────────────────────────────────
def test_series_median_shift_is_level_minus_the_gauges_own_seasonal_median():
    r = compute_shift(lvl(588.6), sref(), NOW)
    assert r.mode == "shiftOnly" and r.shift_ft == pytest.approx(-1.4) and r.reference_ft == 590.0
    assert r.sigma_parts["pool"] == C.SIGMA_SERIES_MEDIAN and r.sigma_parts["datum"] == 0.0
    d = r.as_dict()
    assert d["referenceBasis"] == "seriesMedian" and d["referenceFt"] == 590.0


@pytest.mark.parametrize("band,fallback,reason", [
    (None, False, "SERIES_MEDIAN_UNAVAILABLE"),
    ({**BAND, "basisYears": 9}, False, "SERIES_HISTORY_TOO_SHORT"),
    ({**BAND, "basisYears": 2, "sampleCount": 30}, False, "SERIES_HISTORY_TOO_SHORT"),
    ({**BAND, "windowDays": 15}, False, "SERIES_MEDIAN_WINDOW_MISMATCH"),
    ({**BAND, "sampleCount": 99}, False, "SERIES_MEDIAN_TOO_FEW_SAMPLES"),
    ({**BAND, "p50": float("nan")}, False, "SERIES_MEDIAN_UNAVAILABLE"),
    (BAND, True, "SERIES_LEVEL_FROM_FALLBACK_SOURCE"),
])
def test_series_median_refuses_without_enough_of_the_same_gauges_history(band, fallback, reason):
    r = compute_shift(lvl(588.6, band, fallback), sref(), NOW)
    assert r.mode == "unknown" and r.reasons == [reason] and r.shift_ft is None


def test_series_median_needs_the_same_series_datum_status_and_vice_versa():
    ref = ReferencePool(None, "seriesMedian", None, None, assessment=assess("NGVD29", "NGVD29"))
    assert compute_shift(lvl(588.6), ref, NOW).reasons == ["SERIES_REFERENCE_NOT_SAME_SERIES"]
    full = ReferencePool(595.0, "fullPool", "high", "NGVD29", assessment=assess(None, None, same_series=True))
    assert compute_shift(lvl(588.6), full, NOW).reasons == ["DATUM_UNKNOWN"]


def test_series_median_skips_lakes_difference_from_full_pool_cross_check():
    r = compute_shift(lvl(588.6, diff=-6.4), sref(), NOW)
    assert r.mode == "shiftOnly" and not any(f.startswith("lakeBrainDeltaDisagrees") for f in r.flags)


def test_other_reference_bases_are_still_refused():
    for basis in ("naturalSurface", None, "operatingZone"):
        r = compute_shift(lvl(588.6), ReferencePool(590.0, basis, "high", "NGVD29", assessment=assess("NGVD29", "NGVD29")), NOW)
        assert r.reasons == ["REFERENCE_NOT_A_POOL_ELEVATION"]


# ── lowWaterDatum shift ──────────────────────────────────────────────────────────────────────────────
def test_low_water_datum_shift_and_no_full_pool_cross_check():
    ref = ReferencePool(569.2, "lowWaterDatum", "high", "IGLD85", True, assessment=assess("IGLD85", "IGLD85"))
    r = compute_shift(LevelObservation(571.4, "ft", "IGLD85", OBS, "DIRECT_LAKE_GAUGE", "OBSERVED", -0.6), ref, NOW, "IGLD85")
    assert r.mode == "shiftOnly" and r.shift_ft == pytest.approx(2.2) and r.confidence == "HIGH"
    assert not any(f.startswith("lakeBrainDeltaDisagrees") for f in r.flags)
    assert r.as_dict()["referenceBasis"] == "lowWaterDatum"


def test_low_water_datum_requires_an_igld85_reference_and_level():
    bad = ReferencePool(569.2, "lowWaterDatum", "high", "NAVD88", True, assessment=assess("IGLD85", "IGLD85"))
    assert compute_shift(LevelObservation(571.4, "ft", "IGLD85", OBS, "DIRECT_LAKE_GAUGE", "OBSERVED"), bad, NOW).reasons == ["REFERENCE_DATUM_NOT_IGLD85"]
    ref = ReferencePool(569.2, "lowWaterDatum", "high", "IGLD85", True, assessment=assess("IGLD85", "IGLD85"))
    r = compute_shift(LevelObservation(571.4, "ft", "NAVD88", OBS, "DIRECT_LAKE_GAUGE", "OBSERVED"), ref, NOW, "IGLD85")
    assert r.reasons == ["LEVEL_DATUM_CONFLICT"]


# ── states ───────────────────────────────────────────────────────────────────────────────────────────
ZONES = {"cumulative": {"3.0": 0.1, "6.0": 0.2, "10.0": 0.3}, "intervalFt": 2, "coverage": 0.9, "source": "MN", "referenceStatus": "VERIFIED",
         "referencePoolFt": 590.0, "referencePoolDatum": "NGVD29"}
EV = {"tier": "A", "researchTier": "A", "kind": "contour", "coverage": 0.9, "intervalFt": 2}


def test_series_median_state_names_the_reference_and_withholds_zones():
    st, meta = build_state(series_candidate(evidence=EV, referenceZones=ZONES), series_state(), NOW, manifest_version="fixture")
    assert st["kind"] == "observed" and meta["readiness"] == "CALIBRATION"
    ed = st["effectiveDepth"]
    assert ed["mode"] == "shiftOnly" and ed["shiftFt"] == -1.4 and ed["referenceBasis"] == "seriesMedian" and ed["referenceFt"] == 590.0
    ref = st["reference"]
    assert ref["referencePoolBasis"] == "seriesMedian" and "referencePoolFt" not in ref and "not from full pool" in ref["referenceMeaning"].lower()
    assert ref["seriesMedian"]["windowDays"] == 7 and ref["seriesMedian"]["minBasisYears"] == 10 and ref["seriesMedian"]["band"]["basisYears"] == 20
    assert "referenceZones" not in st and "effectiveZones" not in st
    assert any("withheld" in x for x in st["limitations"]) and any("seasonal median" in x for x in st["limitations"])
    assert "usual level for this time of year" in st["facts"][0]
    assert st["provenance"]["datumEvidence"]["status"] == "SAME_SERIES"


def test_series_median_state_refuses_with_short_history():
    st, meta = build_state(series_candidate(), series_state(band={**BAND, "basisYears": 6}), NOW)
    assert st["kind"] == "unavailable" and st["effectiveDepth"]["reasons"] == ["SERIES_HISTORY_TOO_SHORT"] and meta["readiness"] == "DEGRADED"


def test_series_median_fingerprint_follows_the_band_and_full_pool_fingerprint_does_not():
    rec = series_candidate()
    assert input_fingerprint(rec, series_state(), "m") != input_fingerprint(rec, series_state(band={**BAND, "p50": 590.1}), "m")
    full = candidate()
    assert input_fingerprint(full, series_state(), "m") == input_fingerprint(full, series_state(band={**BAND, "p50": 590.1}), "m")


def test_low_water_datum_state_and_zones_withheld():
    st, _ = build_state(lwd_candidate(evidence=EV, referenceZones=ZONES), lake_state(571.4, datum="IGLD85", cap="DIRECT_LAKE_GAUGE"), NOW)
    assert st["effectiveDepth"]["shiftFt"] == 2.2 and st["reference"]["referencePoolBasis"] == "lowWaterDatum"
    assert "charted depths" in st["facts"][0] and "Low Water Datum" in st["facts"][0]
    assert "effectiveZones" not in st and "referenceZones" not in st


def test_full_pool_states_keep_their_v1_shape():
    """Datum-verified fullPool lakes are unchanged: no new keys, same shift (the golden fixtures in test_contract_fixtures pin the whole state)."""
    st, _ = build_state(candidate(), lake_state(593.6), NOW, manifest_version="fixture")
    assert "referenceBasis" not in st["effectiveDepth"] and "referenceMeaning" not in st["reference"] and "seriesMedian" not in st["reference"]
    assert json.load(open(os.path.join(FIX, "shift_only_observed.json"))) == json.loads(json.dumps(st, sort_keys=True))
