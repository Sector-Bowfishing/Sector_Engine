"""User-facing semantics for the two different things Wind says about a bank (V2 clarification; physics unchanged).

WIND EXPOSURE  — how much room the wind has to BUILD WAVES at this bank: the frozen exposure rank, which is the chop class of
                 the modeled significant wave height Hm0 (CEM over the 9-ray effective fetch). Geometry + wind + duration.
PREDICTED SURFACE — what the water surface is expected to LOOK like: the frozen scoring map P = max(chop class, texture floor).
                 The texture floor is the wind's own roughening of the surface (cat's paws, ripples, broken texture) that appears
                 even where fetch is too short for waves to build.

They are compatible but different. The Oct 19 audit case (bank GT-001172 at 15 mph SW: exposure PROTECTED, surface "Light chop")
is not a physics inconsistency: waves cannot build (0.7 in), but 15 mph wind still textures the surface. The real defect was
terminology: the frozen chop label for class 1 is "Protected", the same word as the exposure rank, so one bank read as both
"protected" and "light chop". V2 keeps every frozen class and bound, renames only the surface label of class 1 ("Flat"), names
the exposure ranks as exposure, and states which mechanism drives the surface (`driver`).
"""
from __future__ import annotations

from .. import bowfishing as BF
from ..brain.contract import cardinal, mph

EXPOSURE_LABEL = {
    "PROTECTED": "Sheltered",
    "LOW_EXPOSURE": "Low exposure",
    "MODERATE_EXPOSURE": "Moderate exposure",
    "HIGH_EXPOSURE": "High exposure",
    "EXTREME_EXPOSURE": "Extreme exposure",
    "UNKNOWN": "Unknown",
}
EXPOSURE_MEANING = {
    "PROTECTED": "modeled waves under 1 in: too little fetch for wind waves to build",
    "LOW_EXPOSURE": "modeled waves 1-3 in",
    "MODERATE_EXPOSURE": "modeled waves 3-6 in",
    "HIGH_EXPOSURE": "modeled waves 6-12 in",
    "EXTREME_EXPOSURE": "modeled waves 12 in or more",
    "UNKNOWN": "fetch unknown at this bank (below the fetch-raster resolution); never treated as sheltered",
}
SHELTERED = ("PROTECTED", "LOW_EXPOSURE")
EXPOSED = ("HIGH_EXPOSURE", "EXTREME_EXPOSURE")
SURFACE_LABEL = {1: "Flat", 2: "Ripple", 3: "Light chop", 4: "Moderate chop", 5: "Rough"}   # frozen classes; class 1 renamed from "Protected"

# How the modeled surface may affect SEEING and SHOOTING fish. Interpretation of the surface class only.
FISHING_IMPACT = {
    1: ("SURFACE_NOT_LIMITING", "Surface disturbance is unlikely to limit seeing fish."),
    2: ("MINOR", "Light ripple: a small effect on seeing into the water."),
    3: ("REDUCED", "Light chop is likely to make fish below the surface harder to spot."),
    4: ("POOR", "Moderate chop is likely to make spotting and shooting fish difficult."),
    5: ("VERY_POOR", "Rough water: spotting fish is very difficult; boat handling and safety need their own judgment."),
}
FISHING_IMPACT_CAVEAT = ("Wind only changes the surface. Water clarity, light, fish presence, access and safety are not assessed by "
                         "Wind Brain. Surface classes are modeled and not field-validated.")


def _in(x: float) -> float:
    """Wave heights to 0.1 in: the model has no finer skill (buoy MAE about 5.6 in)."""
    return round(float(x), 1)


def surface_driver(chop: int, surface: int) -> str:
    return "WAVES" if surface == chop else "WIND_TEXTURE"


def describe(r: dict, lake_id: str, speed_ms: float, duration_h: float) -> dict:
    """V2 bank result from one frozen `bowfishing.evaluate_bank` row (plus `relativeLakePercentile` when ranked)."""
    code = r["exposureRank"]
    base = {"bankId": r["bankId"], "lakeId": lake_id, "anchor": r.get("anchor"), "region": r.get("region"),
            "windExposure": {"code": code, "label": EXPOSURE_LABEL[code], "meaning": EXPOSURE_MEANING[code]}}
    if code == "UNKNOWN":
        return {**base, "relativeExposure": None, "predictedSurface": None, "fishingImpact": None, "fetch": None,
                "confidence": "unknown", "explanation": "Fetch is unknown at this bank (below the fetch-raster resolution), so its "
                                                        "exposure is unknown. Wind Brain never treats an unknown bank as sheltered."}
    p, chop = r["predictedSurfaceClass"], r["chopClass"]
    drv = surface_driver(chop, p)
    imp = FISHING_IMPACT[p]
    lo, hi = r["predictedHm0RangeIn"]
    pct = r.get("relativeLakePercentile")
    return {**base,
            "relativeExposure": None if pct is None else {"lakePercentile": pct,
                                                          "basis": "effective-fetch percentile among this lake's resolvable banks for this wind direction (0 = most sheltered)"},
            "predictedSurface": {"class": p, "label": SURFACE_LABEL[p], "driver": drv, "waveHeightIn": _in(r["predictedHm0In"]),
                                 "waveHeightRangeIn": [_in(min(lo, r["predictedHm0In"])), _in(max(hi, r["predictedHm0In"]))],
                                 "windTexture": BF.TEXTURE[r["predictedTextureClass"]], "modeled": True},
            "fishingImpact": {"code": imp[0], "text": imp[1]},
            "fetch": {"effectiveM": r["effectiveFetchM"], "directM": r["directFetchM"], "raysM": r["effectiveFetchRays"]},
            "confidence": r["confidence"],
            "explanation": explain(r, code, p, drv, speed_ms, duration_h)}


def explain(r: dict, code: str, p: int, drv: str, speed_ms: float, duration_h: float) -> str:
    wind = f"{mph(speed_ms):g} mph {cardinal(r['windFromDeg'])} wind"
    reason = r["reason"][len("sheltered: "):] if r["reason"].startswith("sheltered: ") else r["reason"]
    lo, hi = r["predictedHm0RangeIn"]
    s = f"{EXPOSURE_LABEL[code]} {'from' if code == 'PROTECTED' else 'to'} the {wind}: {reason}. "
    s += f"Modeled waves about {_in(r['predictedHm0In']):g} in (range {_in(lo):g}-{_in(hi):g} in) after {duration_h:g} h of steady wind"
    if drv == "WIND_TEXTURE":
        s += f"; waves stay small, but the wind itself roughens the surface ({BF.TEXTURE[r['predictedTextureClass']].lower()} texture), so the surface reads {SURFACE_LABEL[p].lower()}"
    else:
        s += f", so the surface reads {SURFACE_LABEL[p].lower()}"
    if r["confidence"] == "boundary":
        s += ". The class sits near a boundary: a little more or less wind or fetch changes it"
    return s + "."
