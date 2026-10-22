"""Specialist boundary on the ORDINARY publication (Cortex BR-03): Fish publishes species biology state, never a final bowfishing
recommendation; Sector Intelligence makes recommendations. The Intelligence-facing assessment has its own, stricter guard (`biological_assessment.FORBIDDEN_KEYS`, test_capability_v2.py).
This pins that no key anywhere in a real fish-publication-v1 artifact names a recommendation, a best place or an opportunity.
Exact key names, not substrings: research-gap metadata such as `changesRecommendation` is not a recommendation. Synthetic, offline."""
import copy

import fish_support as F

RECOMMENDATION_KEYS = frozenset({
    "recommendation", "recommendations", "recommendedLocation", "recommendedLocations", "recommendedAction", "verdict",
    "bestPlace", "bestPlaces", "bestSpot", "bestSpots", "bestLocation", "bestLocations", "whereToFish", "goFishing",
    "opportunity", "opportunities", "opportunityScore", "rankedAreas", "fishingScore", "bowfishingScore",
})


def _keys(v):
    if isinstance(v, dict):
        for k, x in v.items():
            yield k
            yield from _keys(x)
    elif isinstance(v, list):
        for x in v:
            yield from _keys(x)


def recommendation_keys(artifact):
    return sorted({(m["path"], k) for s in artifact["sections"] for m in s["mutations"] for k in _keys(m.get("value")) if k in RECOMMENDATION_KEYS})




def test_publication_carries_no_recommendation_fields():
    art = F.build().artifact
    assert art["sections"] and recommendation_keys(art) == []


def test_the_guard_detects_an_injected_recommendation():
    art = copy.deepcopy(F.build().artifact)
    m = next(m for s in art["sections"] for m in s["mutations"] if isinstance(m.get("value"), dict))
    m["value"]["recommendation"] = "go here tonight"
    assert recommendation_keys(art) == [(m["path"], "recommendation")]
