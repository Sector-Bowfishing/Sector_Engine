"""Fleet metrics computed from the candidate manifest only (counts and shares, no judgment). Used by the Ops summary.

The research maturity RUBRIC that used to sit next to these numbers is offline research tooling (research/tools/depth_research/maturity.py):
Depth publishes no maturity number and no score; the shared scorer is the only score authority and has no Depth entry."""
from __future__ import annotations

from collections import Counter


def _g(d, *path, default=None):
    """Tolerant nested get: a malformed candidate must degrade a metric, never crash a publish."""
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return default if d is None else d


def fleet_metrics(manifest: dict) -> dict:
    c = manifest["candidates"]
    n = len(c)
    ok = [x for x in c if _g(x, "shiftPossible", default=False)]
    ds = Counter(_g(x, "datum", "status", default="UNKNOWN") for x in ok)
    tier_ab = [x for x in c if _g(x, "evidence", "tier") in ("A", "B")]
    return {
        "totalLakes": n,
        "shiftPossible": len(ok),
        "shiftPossibleShare": round(len(ok) / n, 4) if n else 0.0,
        "pilotVerified": sum(1 for x in c if x.get("rollout") == "PILOT_VERIFIED"),
        "highConfidence": sum(1 for x in c if x.get("rollout") == "HIGH_CONFIDENCE"),
        "mediumConfidence": sum(1 for x in c if x.get("rollout") == "MEDIUM_CONFIDENCE"),
        "blocked": sum(1 for x in c if x.get("rollout") == "BLOCKED"),
        "verifiedDatum": ds.get("SAME_SOURCE", 0) + ds.get("SAME_DATUM", 0),
        "inferredOperatorSystem": ds.get("SAME_OPERATOR_SYSTEM", 0),
        "convertedDatum": ds.get("CONVERTED", 0),
        "datumStatus": dict(ds),
        "plausibleBlockedByDatum": sum(1 for x in c if _g(x, "reference", "basis") == "fullPool" and _g(x, "reference", "confidence") in ("high", "medium")
                                       and _g(x, "levelSource", "status", default="NONE") != "NONE" and not _g(x, "shiftPossible", default=False)),
        "tierAB": len(tier_ab),
        "referenceZoneLakes": sum(1 for x in c if "referenceZones" in x and _g(x, "referenceZones", "kind", default="contour") == "contour"),
        "effectiveZoneEligible": sum(1 for x in c if _g(x, "referenceZones", "kind", default="contour") == "contour" and _g(x, "referenceZones", "referenceStatus") == "VERIFIED" and _g(x, "shiftPossible", default=False)),
        # operator elevation-area ratings (RATING-ZONE-RULES-1): exact shares by construction, NOT validated against an independent table; counted apart from the contour lakes
        "ratingZoneLakes": sum(1 for x in c if _g(x, "referenceZones", "kind") == "stage-area-rating"),
        "ratingZoneEligible": sum(1 for x in c if _g(x, "referenceZones", "kind") == "stage-area-rating" and _g(x, "shiftPossible", default=False)),
        "licenceAllowedAB": sum(1 for x in tier_ab if _g(x, "licence", "customerDerivedMetricsAllowed") == "true"),
        "manifestVersion": manifest.get("manifestVersion"),
    }
