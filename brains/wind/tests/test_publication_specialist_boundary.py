"""Specialist boundary on the ORDINARY publication (Cortex BR-03): Wind publishes wind and surface state, never a final bowfishing
recommendation; Sector Intelligence makes recommendations. The Intelligence-facing assessment has its own, stricter guard (`assessment/schema.py` FORBIDDEN_KEY, test_wind_exposure_assessment.py).
This pins that no key anywhere in a real wind-publication-v1 artifact names a recommendation, a best place or an opportunity.
Exact key names, not substrings: research-gap metadata such as `changesRecommendation` is not a recommendation. Synthetic, offline."""
import copy

from test_publish_artifact import build, patches  # noqa: F401  (module fixture: real publish() output)

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




def test_publication_carries_no_recommendation_fields(patches):
    art = build(patches).artifact
    assert art["sections"] and recommendation_keys(art) == []


def test_the_guard_detects_an_injected_recommendation(patches):
    art = copy.deepcopy(build(patches).artifact)
    m = next(m for s in art["sections"] for m in s["mutations"] if isinstance(m.get("value"), dict))
    m["value"]["recommendation"] = "go here tonight"
    assert recommendation_keys(art) == [(m["path"], "recommendation")]
