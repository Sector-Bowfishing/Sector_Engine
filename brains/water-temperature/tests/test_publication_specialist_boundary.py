"""Specialist boundary on the ORDINARY publication (Cortex BR-03): Water Temperature publishes water temperature state, never a final bowfishing recommendation; Sector Intelligence makes recommendations. The artifact is built from the runner's recorded write set.
This pins that no key anywhere in a real water-temp-publication-v1 artifact names a recommendation, a best place or an opportunity (exact key names). Offline."""
import copy

from water_temp_cert_spec import artifact

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
    art = artifact(1, "2026-07-15T03:00:00Z", None, False)
    assert art["sections"] and recommendation_keys(art) == []


def test_the_guard_detects_an_injected_recommendation():
    art = copy.deepcopy(artifact(1, "2026-07-15T03:00:00Z", None, False))
    m = next(m for s in art["sections"] for m in s["mutations"] if isinstance(m.get("value"), dict))
    m["value"]["recommendation"] = "go here tonight"
    assert recommendation_keys(art) == [(m["path"], "recommendation")]
