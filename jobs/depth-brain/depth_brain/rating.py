"""Operator elevation-area ratings (USACE CWMS `Elev;Area`) as exact depth-share evidence: RATING-ZONE-RULES-1
(docs/brains/depth/DEPTH_STAGE_AREA_RATING_RULES.md).

A rating gives the water-surface area A(z) at every elevation z. With the reference pool P:
    S(x) = (A(P) - A(P - x)) / A(P)        share of the reference-pool surface whose bottom lies within x ft below P
which is exactly the cumulative depth-share function that contour surveys approximate. It says HOW MUCH of the lake is that shallow, never WHERE.
Below the rating's lowest elevation nothing is known: S(x) is then bounded by [S at the rating floor, 1], never extrapolated."""
from __future__ import annotations

import json
import os
from functools import lru_cache

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stage_area_curves.json")


@lru_cache(maxsize=4)
def load_curves(path: str = DATA) -> dict:
    return (json.load(open(path)) if os.path.exists(path) else {}).get("lakes", {})


def _interp(elev: list, area: list, z: float) -> float:
    if z <= elev[0]:
        return float(area[0])
    if z >= elev[-1]:
        return float(area[-1])
    lo, hi = 0, len(elev) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if elev[mid] <= z:
            lo = mid
        else:
            hi = mid
    f = (z - elev[lo]) / (elev[hi] - elev[lo])
    return float(area[lo] + f * (area[hi] - area[lo]))


def share_bounds(curve: dict, pool_ft: float, x: float) -> tuple[float, float]:
    """Bounds on S(x). Exact (lo == hi) inside the rating; [S(floor), 1] when P - x is below the rating's lowest elevation."""
    if x <= 0:
        return 0.0, 0.0
    e, a = curve["elevFt"], curve["areaAc"]
    aP = _interp(e, a, pool_ft)
    if aP <= 0:
        return 0.0, 1.0
    z = pool_ft - x
    if z >= e[0]:
        s = (aP - _interp(e, a, z)) / aP
        return s, s
    floor = (aP - float(a[0])) / aP
    return max(0.0, min(1.0, floor)), 1.0


def cumulative_at(curve: dict, pool_ft: float, edges=(3.0, 6.0, 10.0)) -> dict:
    """S at the edges the rating fully resolves (P - edge inside the stored rating)."""
    out = {}
    for x in edges:
        lo, hi = share_bounds(curve, pool_ft, x)
        if abs(hi - lo) < 1e-12:
            out[x] = round(lo, 4)
    return out


def _norm_datum(v):
    from .datum import normalize_datum
    return normalize_datum(str(v).replace("-", "")) if v else None


# Cross-check of rating-derived shares against INDEPENDENT contour surveys (20 lakes, 60 edges, contour interval <= 5 ft; research/depth/stage_area_doc.py):
# median |difference| 0.036, 90th percentile 0.104, max 0.141. The rating is exact as published; whether it still describes the lake (age, sedimentation) is not
# knowable here, so every rating-derived share carries this tolerance beside its bounds. It is a reported accuracy, not a bound.
RATING_SHARE_TOLERANCE_ABS = 0.11
CONTOUR_DISAGREE_MAX = 0.10      # RATING-ZONE-RULES-1 R6: a rating and a contour survey of the same lake must agree within 0.10 of the surface at every common edge


def rating_reference_zones(curve: dict | None, pool_ft, ref_datum, ref_datum_verified, datum_status, contour_cum: dict | None = None) -> tuple[dict | None, str]:
    """-> (referenceZones record or None, reason). Pure; every refusal names its rule."""
    if not curve:
        return None, "NO_RATING"
    if pool_ft is None or abs(float(curve["poolFt"]) - float(pool_ft)) > 1e-6:
        return None, "R3_POOL_NOT_THE_RATING_POOL"
    rd = _norm_datum(ref_datum)
    nd = _norm_datum(curve.get("ratingNativeDatum"))
    if nd is not None and rd is not None and nd != rd:
        return None, "R2_RATING_DATUM_DIFFERS"
    # R2: the rating must be in the pool's elevation frame. Either the rating sits at the CWMS location that holds the level SERIES and the pool/series relationship is
    # SAME_SOURCE (one CWMS record: the frame needs no name) or SAME_DATUM (both stamped), or the rating sits at the location of the verified, NAMED pool datum.
    if curve.get("matchedBy") in ("series-location", "tsc-table"):                  # tsc-table: survey-derived Reclamation table in the project datum; the lake's datum status itself rests on the RISE storage-consistency fit
        if datum_status not in ("SAME_SOURCE", "SAME_DATUM"):
            return None, "R2_SERIES_POOL_RELATIONSHIP_NOT_ESTABLISHED"
    elif not ref_datum_verified or rd not in ("NGVD29", "NAVD88"):
        return None, "R2_REFERENCE_DATUM_NOT_VERIFIED"
    cum = cumulative_at(curve, float(pool_ft))
    if not cum:
        return None, "R3_RATING_DOES_NOT_REACH_3FT_BELOW_POOL"
    if contour_cum:
        for k, v in contour_cum.items():
            if float(k) in cum and abs(cum[float(k)] - float(v)) > CONTOUR_DISAGREE_MAX:
                return None, "R6_RATING_CONTOUR_DISAGREE"
    eff = curve["effectiveDate"]
    return {"cumulative": {str(k): v for k, v in cum.items()}, "intervalFt": None, "coverage": 1.0, "source": f"USACE CWMS rating {curve['ratingId']}",
            "referenceStatus": "VERIFIED", "referencePoolFt": float(pool_ft), "referencePoolDatum": rd or nd, "kind": "stage-area-rating",
            "rating": {"id": curve["ratingId"], "office": curve["office"], "effectiveDate": eff, "vintageKnown": not eff.startswith("1970-01-01"), "url": curve.get("url"),
                       "matchedBy": curve.get("matchedBy"), "elevRangeFt": [curve["elevMinFt"], curve["elevMaxFt"]]},
            "note": "shares of the reference-pool surface from the operator's published elevation-area rating (how much, never where)"}, "ok"
