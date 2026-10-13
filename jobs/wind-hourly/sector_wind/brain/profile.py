"""WindProfile: what WindBrain knows about how wind acts on one lake (changes rarely). Geometry facts come from the
frozen fetch tables; nothing here is a fishing judgement (no 'good shoreline', no protected fishing spots)."""
from __future__ import annotations

import numpy as np

from .. import bowfishing as BF
from . import contract as C
from .state import decode_fetch_table

FETCH_MODEL = {
    "method": "SPM 1984 / CEM straight-line effective fetch: mean of 9 rays at ±12° (3° spacing), 120 FROM-bearings, "
              "first-land intersection, islands as land, 30 m standoff, 10 m raster, 30 km max (no 5 km cap)",
    "geometrySource": "USGS NHD high-resolution waterbody polygons",
    "frozenIn": C.CANDIDATE_MODEL,
}
EXPOSURE_MODEL = {
    "method": "exposure rank from modeled Hm0 (frozen CEM, effective fetch, wind) — physical, not a fishing judgement",
    "ranks": {"PROTECTED": "Hm0 < 1 in", "LOW_EXPOSURE": "1-3 in", "MODERATE_EXPOSURE": "3-6 in", "HIGH_EXPOSURE": "6-12 in",
              "EXTREME_EXPOSURE": ">= 12 in", "UNKNOWN": "bank below raster resolution (never treated as sheltered)"},
    "definitionRef": "docs/intelligence/wind/bowfishing/WIND_BOWFISHING_SCORE_V1.md (frozen)",
}
SURFACE_MODEL = {
    "growth": "CEM EM 1110-2-1100 Part II-2 eqs II-2-36..39 (fetch/duration-limited, fully-developed cap; no depth cap without depth)",
    "duration": "frozen M0 rule: consecutive hours |Δdir| <= 22.5°, speed 0.7-1.3x, >= 1 m/s; 0.5-12 h",
    "chopClasses": {"Protected": "< 1 in", "Ripple": "1-3 in", "Light chop": "3-6 in", "Moderate chop": "6-12 in", "Rough": ">= 12 in"},
    "texture": "Cox-Munk wind-speed texture classes (boundaries 1.0 / 3.0 / 5.5 m/s); local wind shelter NOT modeled",
    "fieldValidated": False,
    "memoryModel": "none promoted (M3 SWAN-falsified for reservoirs; M4 failed its pre-registered promotion rule)",
}
KNOWN_LIMITATIONS = [
    "Surface/exposure physics are not field-validated at bank scale (Wind Certification caps 6 and 7).",
    "Atmospheric validation is land-only (airport METAR); no over-water reference yet.",
    "NBM is 3-4 m/s low on >= 15 mph hours; it has never forecast a >= 15 mph event in the validation corpus.",
    "Texture uses the unsheltered grid wind: tree/bank wind shelter is not modeled.",
    "One representative point (directory coordinate) is used for the lake-level wind value.",
]
DIRS8 = {"N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}


def geometry_facts(fetch_obj: dict) -> dict:
    """Pure geometry from the frozen table: median effective fetch per direction and the dominant open direction."""
    banks, table = decode_fetch_table(fetch_obj)
    ok = [i for i, b in enumerate(banks) if not b.get("belowResolution")]
    med = {d: round(float(np.median([BF.nine_ray(table[i], deg) for i in ok]))) for d, deg in DIRS8.items()} if ok else {}
    dom = max(med, key=med.get) if med else None
    return {"banks": len(banks), "resolvableBanks": len(ok), "belowResolutionShare": round(1 - len(ok) / len(banks), 4) if banks else None,
            "medianEffectiveFetchByDirectionM": med,
            "dominantExposure": {"fromDirection": dom, "medianEffectiveFetchM": med.get(dom),
                                 "meaning": "wind direction with the longest median effective fetch across bank segments (geometry only)"} if dom else None,
            "tableSha256": fetch_obj.get("tableSha256"), "geometrySha256": (fetch_obj.get("geometry") or {}).get("sha256")}


def build_profile(lake_id: str, now_iso: str, readiness: str, geometry: dict | None, geometry_source: dict | None,
                  forcing: dict | None, qa: dict | None, flags: list[str]) -> dict:
    lk = C.lake_key(lake_id)
    return {
        "profileSchema": C.PROFILE_SCHEMA, "lakeId": lake_id, "schemaVersion": C.SCHEMA_VERSION, "profileVersion": 1, "updatedAt": now_iso,
        "brainVersion": C.BRAIN_VERSION, "readiness": readiness, "readinessMeaning": C.READINESS_DEFINITIONS[readiness],
        "geometry": {**(geometry_source or {}), **({k: geometry[k] for k in ("banks", "resolvableBanks", "belowResolutionShare", "tableSha256", "geometrySha256")} if geometry else {})} or None,
        "fetchQa": qa,
        "fetchModel": FETCH_MODEL if geometry else None,
        "exposureModel": EXPOSURE_MODEL if geometry else None,
        "surfaceConditionModel": SURFACE_MODEL if geometry else None,
        "dominantExposure": geometry["dominantExposure"] if geometry else None,
        "medianEffectiveFetchByDirectionM": geometry["medianEffectiveFetchByDirectionM"] if geometry else None,
        "protectedAreas": None,                     # not computed: would be a location judgement for Sector Intelligence
        "forcing": forcing,                         # null = no live forcing archived for this lake
        "activeProductionModel": C.PRODUCTION_MODEL,
        "researchCandidate": C.RESEARCH_CANDIDATE,
        "validation": {"ref": f"/lakes/{lk}/validation/{C.BRAIN_ID}"} if forcing else {"ref": f"/validation/{C.BRAIN_ID}", "lakeLevel": None},
        "qualityFlags": flags,
        "knownLimitations": KNOWN_LIMITATIONS,
    }
