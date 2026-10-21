"""Engine-side Ops summary for the Vegetation registry node (`/brains/vegetation`). Pure; every number is computed from the fleet
manifest, the research-maturity inputs and the run - nothing is hardcoded for Ops to echo.

Ops owns presentation; this module only makes canonical truth available in fields Ops already types (`blockers[]`, `readinessCounts`,
`breakdowns{str:{str:num}}`) plus additive objects. Vegetation publishes NO maturity number and no score (`scoreStatus` NOT_ESTABLISHED; no
/scores/vegetation exists): the research maturity rubric is offline research tooling (research/tools/vegetation_research/maturity.py)."""
from __future__ import annotations

from collections import Counter

from . import contract as C
from .metrics import fleet_metrics


def primary_blocker(fm: dict, validation_state: str) -> str:
    return (f"validation: {validation_state}; only {fm['observableLakes']} of {fm['totalLakes']} lakes are observable by the surface observer "
            f"and {fm['withIndependentTruth']} have independent truth; submerged vegetation is not observable")


def registry_extras(manifest: dict, observed_lakes: int, rep: dict | None = None, validation: dict | None = None,
                    truth_backed_lakes: int = 0, shadow: dict | None = None, release: dict | None = None) -> dict:
    """release: the verified knowledge release summary (knowledge.Knowledge.summary()), published as lineage (id, digest, approval)."""
    cands = manifest["candidates"]
    fm = fleet_metrics(manifest, observed_lakes, truth_backed_lakes)
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
        "fleet": {"totalLakes": fm["totalLakes"], "observableLakes": fm["observableLakes"], "observedLakes": observed_lakes, "truthBackedLakes": truth_backed_lakes,
                  "withIndependentTruth": fm["withIndependentTruth"], "geometrySource": "lake-registry (canonical)"},
        "breakdowns": {"observability": dict(Counter(x["tier"] for x in cands)),
                       "readiness": dict(Counter(x["readiness"] for x in cands)),
                       "geometryConfidence": dict(Counter(x["geometryConfidence"] for x in cands))},
        "research": {"maturity": "OFFLINE_RESEARCH_ONLY", "official": False,
                     "note": "the research maturity rubric runs offline (research tooling); Vegetation has no official score and no /scores/vegetation node"},
        "knowledgeRelease": release,
        "shadow": shadow,
        "level1": {"agencyLakes": truth_backed_lakes, "sources": ["fwc-ltm-pac-pvi", "sfwmd-okeechobee-littoral"], "internalOnly": True, "note": "agency observations shown as-is; licence for customer use unconfirmed"},
        "scoreStatus": "NOT_ESTABLISHED",
        "validationLadder": {"state": vstate, "gates": "preregistration (research/tools/vegetation_research/records/VEGETATION_VALIDATION_PREREGISTRATION.md)"},
        "primaryBlocker": primary_blocker(fm, vstate),
        "scope": {"observes": "surface-reaching aquatic vegetation", "submergedObserved": False, "potentialHabitat": "potentialOnly"},
        "orchestration": {"status": "NOT_STARTED", "registered": False, "scheduled": False, "note": "shadow CLI only"},
        "contractVersion": C.STATE_SCHEMA, "manifestVersion": manifest.get("manifestVersion"),
        "lastDryRun": {"evaluated": (rep or {}).get("evaluated"), "unavailable": (rep or {}).get("unavailable")} if rep else None,
        "statusBasis": ("Shadow foundation: surface-vegetation observer and state contract only. NOT_VALIDATED, no official score, not scheduled, "
                        "no live write. " + f"{fm['observableLakes']} of {fm['totalLakes']} lakes are observable; {observed_lakes} have an offline observation."),
        "blockers": blockers,
    }
