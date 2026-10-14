"""RATING-ZONE-RULES-1: exact depth shares from operator elevation-area ratings (docs/brains/depth/DEPTH_STAGE_AREA_RATING_RULES.md)."""
import json
import os

import pytest
from depth_brain import rating as R
from depth_brain import zones as Z
from depth_brain.state import build_state
from helpers import NOW, lake_state

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = {c["lakeId"]: c for c in json.load(open(os.path.join(HERE, "depth_brain", "data", "candidates.json")))["candidates"]}
CURVES = R.load_curves()

# a synthetic bowl: area (acres) = 100 * (z - 90) for z in 90..110 ft; pool 100 -> A(P) = 1000
SYN = {"elevFt": [90.0 + i for i in range(21)], "areaAc": [100.0 * i for i in range(21)], "poolFt": 100.0, "ratingId": "SYN.Elev;Area.Standard.Production", "office": "XXX",
       "effectiveDate": "2020-01-01", "ratingNativeDatum": "NGVD-29", "elevMinFt": 90.0, "elevMaxFt": 110.0, "matchedBy": "pool-location"}


def test_share_function_is_exact_inside_the_rating():
    lo, hi = R.share_bounds(SYN, 100.0, 3.0)
    assert lo == hi and abs(lo - 0.3) < 1e-12                      # (1000 - 700) / 1000
    assert R.cumulative_at(SYN, 100.0) == {3.0: 0.3, 6.0: 0.6, 10.0: 1.0}


def test_share_is_never_extrapolated_below_the_rating():
    lo, hi = R.share_bounds(SYN, 100.0, 12.0)                      # P - 12 = 88 is below the lowest rated elevation (90)
    assert (lo, hi) == (1.0, 1.0) or (lo < hi and hi == 1.0)
    cum = R.cumulative_at({**SYN, "elevFt": SYN["elevFt"][4:], "areaAc": SYN["areaAc"][4:], "elevMinFt": 94.0}, 100.0)
    assert cum == {3.0: 0.3, 6.0: 0.6}                             # the 10 ft edge is not resolved by a rating whose lowest point is 6 ft below the pool


def test_effective_zones_from_a_rating_are_exact():
    rz, why = R.rating_reference_zones(SYN, 100.0, "NGVD29", True, "SAME_SOURCE")
    assert why == "ok" and rz["kind"] == "stage-area-rating"
    z = Z.ReferenceZones({float(k): v for k, v in rz["cumulative"].items()}, None, 1.0, "C", rz["source"], None, 100.0, "NGVD29", "VERIFIED", [], curve=SYN, kind=rz["kind"])
    out = Z.effective_zones(z, -2.0, 0.0)                          # level 98: A(98) = 800
    sh = out["shares"]
    assert abs(sh["dry"]["lo"] - 0.2) < 1e-9 and sh["dry"]["lo"] == sh["dry"]["hi"]
    assert abs(sh["under3"]["lo"] - 0.3) < 1e-9                    # (A(98) - A(95)) / A(100) = 0.3
    assert abs(sh["threeToSix"]["lo"] - 0.3) < 1e-9
    assert abs(sh["sixToTen"]["lo"] - 0.2) < 1e-9                  # (A(92) - A(88)) with A(<90)=0 -> 0.2 ... bounded below by the floor
    total = sh["dry"]["lo"] + sh["under3"]["lo"] + sh["threeToSix"]["lo"] + sh["sixToTen"]["lo"] + sh.get("deeper", {"lo": 0})["lo"]
    assert total <= 1.0 + 1e-9


@pytest.mark.parametrize("kw,why", [
    (dict(pool_ft=101.0), "R3_POOL_NOT_THE_RATING_POOL"),
    (dict(ref_datum="NAVD88"), "R2_RATING_DATUM_DIFFERS"),
    (dict(ref_verified=False), "R2_REFERENCE_DATUM_NOT_VERIFIED"),
])
def test_rating_refusals_name_their_rule(kw, why):
    args = dict(pool_ft=100.0, ref_datum="NGVD29", ref_verified=True)
    args.update(kw)
    rz, got = R.rating_reference_zones(SYN, args["pool_ft"], args["ref_datum"], args["ref_verified"], "SAME_SOURCE")
    assert rz is None and got == why


def test_series_location_rating_needs_an_established_series_pool_relationship():
    c = {**SYN, "matchedBy": "series-location"}
    assert R.rating_reference_zones(c, 100.0, None, False, "UNKNOWN")[1] == "R2_SERIES_POOL_RELATIONSHIP_NOT_ESTABLISHED"
    assert R.rating_reference_zones(c, 100.0, None, False, "SAME_SOURCE")[1] == "ok"


def test_rating_and_contour_that_disagree_by_more_than_a_tenth_are_withheld():
    assert R.rating_reference_zones(SYN, 100.0, "NGVD29", True, "SAME_SOURCE", {3.0: 0.18})[1] == "R6_RATING_CONTOUR_DISAGREE"      # 0.3 vs 0.18
    assert R.rating_reference_zones(SYN, 100.0, "NGVD29", True, "SAME_SOURCE", {3.0: 0.25})[1] == "ok"


def test_shipped_curves_are_monotone_and_hold_the_pool():
    assert len(CURVES) >= 50
    for lid, c in CURVES.items():
        e, a = c["elevFt"], c["areaAc"]
        assert e == sorted(e) and all(x >= -1e-9 for x in a) and e[0] <= c["poolFt"] - 3.0 <= c["poolFt"] <= e[-1], lid
        assert all(a[i + 1] >= a[i] - 0.01 * max(a) for i in range(len(a) - 1)), lid
        assert c["ratingId"] and c["url"].startswith(("https://cwms-data.usace.army.mil/", "https://www.usbr.gov/tsc/")), lid


def test_every_rating_zone_in_the_manifest_is_backed_by_a_shipped_curve_at_the_same_pool():
    rated = [c for c in MAN.values() if (c.get("referenceZones") or {}).get("kind") == "stage-area-rating"]
    assert len(rated) >= 60
    for c in rated:
        z, cv = c["referenceZones"], CURVES[c["lakeId"]]
        assert cv["poolFt"] == z["referencePoolFt"] == c["reference"]["poolFt"]
        assert set(c["evidence"]["contourSources"]) & {"USACE_CWMS", "USBR_TSC"} and c["evidence"]["tier"] in ("A", "B", "C")
        for k, v in z["cumulative"].items():
            lo, hi = R.share_bounds(cv, cv["poolFt"], float(k))
            assert lo == hi and abs(lo - v) < 5e-4


def test_state_for_a_rating_lake_reports_exact_dry_share_and_claims_only_shares():
    lid = "Cheney Reservoir|KS"
    rec = MAN[lid]
    cv = CURVES[lid]
    P = cv["poolFt"]
    state, meta = build_state(rec, lake_state(elev=P - 2.0, datum=None, cap=rec["levelSource"]["capability"]), NOW, manifest_version="t")
    assert state["kind"] == "observed" and state["referenceZones"]["evidenceKind"] == "stage-area-rating"
    ez = state["effectiveZones"]
    assert ez["available"]
    e, a = cv["elevFt"], cv["areaAc"]
    expect = (R._interp(e, a, P) - R._interp(e, a, P - 2.0)) / R._interp(e, a, P)
    dry = ez["shares"]["dry"]
    assert dry["lo"] <= expect <= dry["hi"] + 1e-3 and dry["hi"] - dry["lo"] < 0.1       # sigma widens the bound slightly; the centre is the exact value
    assert "support" in state["referenceZones"] and state["referenceZones"]["support"]["ratingId"]
    blob = json.dumps(state)
    assert "polygon" not in blob and "flat" not in blob.lower().replace("flatten", "")


def test_a_manifest_rating_without_its_curve_yields_no_zones(monkeypatch):
    lid = "Cheney Reservoir|KS"
    rec = json.loads(json.dumps(MAN[lid]))
    monkeypatch.setattr(R, "load_curves", lambda *a, **k: {})
    state, _ = build_state(rec, lake_state(elev=rec["reference"]["poolFt"] - 2.0, datum=None, cap=rec["levelSource"]["capability"]), NOW, manifest_version="t")
    assert "effectiveZones" not in state


def test_rating_shares_carry_their_reported_tolerance_and_contours_do_not():
    rz, _ = R.rating_reference_zones(SYN, 100.0, "NGVD29", True, "SAME_SOURCE")
    z = Z.ReferenceZones({float(k): v for k, v in rz["cumulative"].items()}, None, 1.0, "C", rz["source"], None, 100.0, "NGVD29", "VERIFIED", [], curve=SYN, kind=rz["kind"])
    assert Z.effective_zones(z, -1.0, 0.1)["shareToleranceAbs"] == R.RATING_SHARE_TOLERANCE_ABS == 0.11
    zc = Z.ReferenceZones({3.0: 0.3, 6.0: 0.6, 10.0: 1.0}, 1.0, 1.0, "A", "TWDB", 2010, 100.0, "NGVD29", "VERIFIED", [])
    assert "shareToleranceAbs" not in Z.effective_zones(zc, -1.0, 0.1)


def test_reported_tolerance_covers_the_ninetieth_percentile_of_the_independent_cross_check():
    import csv
    rows = list(csv.DictReader(open(os.path.join(HERE, "depth_brain", "data", "inputs", "contour_truth_lakes.csv"))))
    diffs = []
    for r in rows:
        lid = r["lakeId"]
        if lid not in CURVES or not r.get("interval_ft") or float(r["interval_ft"]) > 5:
            continue
        try:
            ct = {3.0: float(r["shr_0_3"]), 6.0: float(r["shr_0_3"]) + float(r["shr_3_6"]), 10.0: float(r["shr_0_3"]) + float(r["shr_3_6"]) + float(r["shr_6_10"])}
        except (TypeError, ValueError):
            continue
        cum = R.cumulative_at(CURVES[lid], CURVES[lid]["poolFt"])
        diffs += [abs(cum[k] - ct[k]) for k in cum]
    diffs.sort()
    assert len(diffs) >= 55 and R.RATING_SHARE_TOLERANCE_ABS >= diffs[int(0.9 * len(diffs))] - 1e-9


def test_local_project_stage_equals_a_rating_datum_only_with_a_per_lake_paired_series_proof():
    eq = json.load(open(os.path.join(HERE, "depth_brain", "data", "local_datum_equivalence.json")))["lakes"]
    assert len(eq) >= 8
    for lid, e in eq.items():
        assert e["n"] >= 20 and abs(e["meanFt"]) <= 0.10 and e["sdFt"] <= 0.25 and e["localEquals"] in ("NGVD29", "NAVD88"), lid
    local = {**SYN, "matchedBy": "series-location", "ratingNativeDatum": "NGVD-29"}
    assert R.rating_reference_zones(local, 100.0, "LOCAL", True, "SAME_SOURCE")[1] == "R2_RATING_DATUM_DIFFERS"                      # no proof, no zones
    rz, why = R.rating_reference_zones(local, 100.0, "LOCAL", True, "SAME_SOURCE", None, {"localEquals": "NGVD29", "usgsSite": "x", "usgsParam": "62614", "n": 100, "meanFt": 0.0, "sdFt": 0.03})
    assert why == "ok" and rz["localDatumEquivalence"]["localEquals"] == "NGVD29"
    assert R.rating_reference_zones(local, 100.0, "LOCAL", True, "SAME_SOURCE", None, {"localEquals": "NAVD88"})[1] == "R2_RATING_DATUM_DIFFERS"   # equality to the wrong datum proves nothing


def test_flooded_margin_from_a_rating_is_exact_and_never_extrapolated():
    assert R.flooded_margin(SYN, 100.0, 3.0) == (0.3, 0.3)                       # (A(103) - A(100)) / A(100) = (1300 - 1000) / 1000
    assert R.flooded_margin(SYN, 100.0, 0.0) == (0.0, 0.0)
    assert R.flooded_margin(SYN, 100.0, 11.0) is None                            # P + 11 is above the highest rated elevation (110)
    rz, _ = R.rating_reference_zones(SYN, 100.0, "NGVD29", True, "SAME_SOURCE")
    z = Z.ReferenceZones({float(k): v for k, v in rz["cumulative"].items()}, None, 1.0, "C", rz["source"], None, 100.0, "NGVD29", "VERIFIED", [], curve=SYN, kind=rz["kind"])
    out = Z.effective_zones(z, 2.0, 0.0)
    assert out["floodedMarginShare"] == {"lo": 0.2, "hi": 0.2} and "floodedMarginUnquantified" not in out
    assert Z.effective_zones(z, 12.0, 0.0)["floodedMarginUnquantified"] is True
    zc = Z.ReferenceZones({3.0: 0.3, 6.0: 0.6, 10.0: 1.0}, 1.0, 1.0, "A", "TWDB", 2010, 100.0, "NGVD29", "VERIFIED", [])
    assert Z.effective_zones(zc, 2.0, 0.0)["floodedMarginUnquantified"] is True   # contour lakes keep the honest 'unquantified'
