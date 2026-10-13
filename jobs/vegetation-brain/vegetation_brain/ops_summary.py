"""Engine-side Ops summary for the Vegetation registry node (`/brains/vegetation`). Pure; every number is computed from the fleet
manifest, the research-maturity inputs and the run - nothing is hardcoded for Ops to echo.

Ops owns presentation; this module only makes canonical truth available in fields Ops already types (`blockers[]`, `readinessCounts`,
`breakdowns{str:{str:num}}`) plus additive objects. `research.maturity` is a RESEARCH number: `official` is always false and
`scoreStatus` is NOT_ESTABLISHED (no /scores/vegetation exists)."""
from __future__ import annotations

from collections import Counter

from . import contract as C
from . import maturity as M


def primary_blocker(fm: dict, validation_state: str) -> str:
    return (f"validation: {validation_state}; only {fm['observableLakes']} of {fm['totalLakes']} lakes are observable by the surface observer "
            f"and {fm['withIndependentTruth']} have independent truth; submerged vegetation is not observable")


def registry_extras(manifest: dict, observed_lakes: int, rep: dict | None = None, validation: dict | None = None,
                    inputs: dict | None = None) -> dict:
    cands = manifest["candidates"]
    ev = M.evaluate(manifest, inputs, observed_lakes=observed_lakes)
    fm = ev["fleet"]
    vstate = (validation or {}).get("state", "NOT_VALIDATED")
    blockers = [
        primary_blocker(fm, vstate),
        "Submerged vegetation: not observable with Sentinel-2 at fleet scale (research); potential habitat is a separate, potentialOnly product",
        "Potential habitat needs Depth Brain evidence (tier A/B/C measured or contour) and a Clarity Secchi; neither is live",
        "Density and seasonal states withheld until their pre-registered gates pass",
        "External truth requests not yet sent (TVA, SFWMD, TPWD, WI DNR, FWC); UMN dataset needs a browser download",
    ]
    return {
        "directoryLakeCount": fm["totalLakes"],
        "fleet": {"totalLakes": fm["totalLakes"], "observableLakes": fm["observableLakes"], "observedLakes": observed_lakes,
                  "withIndependentTruth": fm["withIndependentTruth"], "geometrySource": "lake-registry (canonical)"},
        "breakdowns": {"observability": dict(Counter(x["tier"] for x in cands)),
                       "readiness": dict(Counter(x["readiness"] for x in cands)),
                       "geometryConfidence": dict(Counter(x["geometryConfidence"] for x in cands))},
        "research": {"maturity": ev["overall"], "official": False, "rubricVersion": ev["rubricVersion"],
                     "criticalBelowThreshold": ev["criticalBelowThreshold"], "meetsProductionPolicy": ev["meetsProductionPolicy"],
                     "note": "research-only rubric; Vegetation has no official score and no /scores/vegetation node"},
        "scoreStatus": "NOT_ESTABLISHED",
        "validationLadder": {"state": vstate, "gates": "docs/brains/vegetation/VEGETATION_VALIDATION_PREREGISTRATION.md"},
        "primaryBlocker": primary_blocker(fm, vstate),
        "scope": {"observes": "surface-reaching aquatic vegetation", "submergedObserved": False, "potentialHabitat": "potentialOnly"},
        "orchestration": {"status": "NOT_STARTED", "registered": False, "scheduled": False, "note": "shadow CLI only"},
        "contractVersion": C.STATE_SCHEMA, "manifestVersion": manifest.get("manifestVersion"),
        "lastDryRun": {"evaluated": (rep or {}).get("evaluated"), "unavailable": (rep or {}).get("unavailable")} if rep else None,
        "statusBasis": ("Shadow foundation: surface-vegetation observer and state contract only. NOT_VALIDATED, no official score, not scheduled, "
                        "no live write. " + f"{fm['observableLakes']} of {fm['totalLakes']} lakes are observable; {observed_lakes} have an offline observation."),
        "blockers": blockers,
    }
