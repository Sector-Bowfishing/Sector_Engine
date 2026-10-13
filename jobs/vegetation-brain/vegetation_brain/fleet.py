"""Fleet observability from the CANONICAL Lake Registry (docs/brains/LAKE_REGISTRY_GEOMETRY_CONTRACT.md).

Vegetation keeps NO polygon library of its own: it reads `registry/lakes.v1.json` (index only; geometry objects are fetched
per lake by the observer when it runs). Tier rules:

  geometry null                               -> UNKNOWN  (BLOCKED: NO_GEOMETRY)
  area >= AREA_HIGH_KM2 (5)                   -> HIGH
  AREA_MEDIUM_KM2 (0.5) <= area < 5           -> MEDIUM   (10 m pixels mix with shore; density caveats)
  area < 0.5                                  -> LOW      (BLOCKED: TOO_NARROW / too small)
  geometryConfidence LOW                      -> one tier lower (HIGH->MEDIUM, MEDIUM->LOW), reason GEOMETRY_LOW

Observability is about whether the SURFACE observer can look at the lake. It says nothing about submerged vegetation,
which no tier can observe."""
from __future__ import annotations

import json
from collections import Counter

from . import contract as C

TIERS = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
_DOWN = {"HIGH": "MEDIUM", "MEDIUM": "LOW", "LOW": "LOW"}


def observability(entry: dict) -> dict:
    lid = entry["lakeId"]
    conf = (entry.get("geometryConfidence") or {}).get("level", "MISSING")
    area = entry.get("areaKm2")
    reasons: list[str] = []
    if entry.get("geometry") is None or area is None:
        return {"lakeId": lid, "tier": "UNKNOWN", "readiness": "BLOCKED", "reasons": ["NO_GEOMETRY"], "areaKm2": None, "geometryConfidence": conf}
    tier = "HIGH" if area >= C.AREA_HIGH_KM2 else "MEDIUM" if area >= C.AREA_MEDIUM_KM2 else "LOW"
    if tier == "LOW":
        reasons.append("TOO_NARROW")
    elif tier == "MEDIUM":
        reasons.append("MIXED_PIXELS")
    if conf == "LOW":
        reasons.append("GEOMETRY_LOW")
        tier = _DOWN[tier]
    readiness = "BLOCKED" if (tier == "LOW" and area < C.AREA_MEDIUM_KM2) else "PROFILED"
    return {"lakeId": lid, "tier": tier, "readiness": readiness, "reasons": reasons, "areaKm2": area, "geometryConfidence": conf}


def build_manifest(registry: dict, ground_truth: dict | None = None, version: str = "unversioned") -> dict:
    """registry: parsed `lakes.v1.json`. ground_truth: {lakeId: [flags]} from validation reports (optional)."""
    rows = []
    for e in registry["lakes"]:
        o = observability(e)
        o.update({"name": e.get("name"), "state": e.get("state"), "region": (e.get("classification") or {}).get("region"),
                  "lakeClass": (e.get("classification") or {}).get("lakeClass"),
                  "geometryVersion": e.get("geometryVersion"), "lakeKey": e.get("lakeKey"),
                  "groundTruth": sorted((ground_truth or {}).get(e["lakeId"], []))})
        rows.append(o)
    summ = {
        "totalLakes": len(rows),
        "tiers": dict(Counter(r["tier"] for r in rows)),
        "readiness": dict(Counter(r["readiness"] for r in rows)),
        "geometryConfidence": dict(Counter(r["geometryConfidence"] for r in rows)),
        "downgradedByGeometry": sum(1 for r in rows if "GEOMETRY_LOW" in r["reasons"]),
        "withIndependentTruth": sum(1 for r in rows if r["groundTruth"]),
    }
    return {"schema": "sector-vegetation-fleet-v1", "manifestVersion": version, "registryGeneratedAt": registry.get("generatedAt"),
            "registryGeometryVersion": registry.get("geometryVersion"), "summary": summ, "candidates": rows,
            "note": "Observability of SURFACE vegetation only. No tier means submerged vegetation can be observed."}


def load_registry(path: str) -> dict:
    with open(path) as f:
        return json.load(f)
