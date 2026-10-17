import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import movement_cards as mc      # noqa: E402


def card(filled=True):
    t = "Moves shallow in spring" if filled else ""
    return {"seasonalMovement": {s: t for s in mc.SEASONS}, "spawn": {"timing": t, "temperatureF": {"min": 60, "max": 75, "peak": 68, "note": ""} if filled else {"min": None, "max": None, "peak": None, "note": "UNKNOWN"}, "habitat": t, "shallowMovement": t},
            "temperatureResponse": {k: t for k in ("triggers", "preSpawn", "spawn", "summer", "coldSlowdown")}, "depthBehavior": {k: t for k in ("shallowWhen", "deepWhen", "usefulDepthHabitat")},
            "hydrologyResponse": {k: t for k in ("rising", "falling", "floodedShoreline", "current", "discharge", "backwaterConnectivity")}, "vegetationAssociation": t, "coverAndSubstrate": t,
            "clarityLightResponse": {k: t for k in ("brightSun", "lowLight", "turbid", "clear")}, "dayNightBehavior": {k: t for k in ("day", "dusk", "night", "dawn")},
            "currentPreference": {k: t for k in ("mainRiver", "reservoir", "creekTributary", "backwaterSlough", "shorelineFlat", "channelEdge")},
            "bowfisherTakeaway": "A bowfisher looking for this fish should concentrate on warm flats when spring warms.", "generalConfidence": "HIGH", "regionalConfidence": "UNKNOWN"}


def sp(filled=True, score=9, src="AGENCY"):
    return {"speciesId": "x", "sectorLabel": "X", "passLevel": "DEEP", "card": card(filled), "componentScores": {c: {"score": score, "why": ""} for c in mc.WEIGHTS},
            "ruleCandidates": [{"id": "X-C01", "when": ["a"], "then": "b", "direction": "MORE_LIKELY_SHALLOW", "kind": "RESPONSE", "confidence": "HIGH", "sourceIds": ["S1"]}],
            "sources": [{"id": "S1", "type": src, "url": "https://example.gov/x"}]}


class Score(unittest.TestCase):
    def test_weights_sum_to_100(self):
        self.assertEqual(sum(mc.WEIGHTS.values()), 100)

    def test_full_card_scores_agent_value_and_empty_card_scores_zero(self):
        self.assertEqual(mc.knowledge_score(sp(True, 9))["score"], 9.0)
        self.assertEqual(mc.knowledge_score(sp(False, 9))["score"], 0.0)       # agent cannot award points for content that is not there

    def test_unknown_text_is_not_filled(self):
        c = card()
        c["seasonalMovement"] = {s: "UNKNOWN" for s in mc.SEASONS}
        self.assertEqual(mc.filled_fraction(c, "seasonal"), 0.0)

    def test_anecdotal_only_caps_at_three(self):
        r = mc.knowledge_score(sp(True, 9, "ANECDOTAL"))
        self.assertEqual((r["score"], r["sourceCapped"]), (3.0, True))

    def test_score_is_deterministic_and_regional_unknown_does_not_reduce_it(self):
        a, b = sp(), sp()
        b["card"]["regionalConfidence"] = "HIGH"
        self.assertEqual(mc.knowledge_score(a)["score"], mc.knowledge_score(b)["score"])
        self.assertEqual(mc.knowledge_score(a), mc.knowledge_score(sp()))

    def test_validation_and_dedupe_and_mismatch(self):
        self.assertEqual(mc.validate_species(sp()), [])
        bad = sp()
        bad["ruleCandidates"][0]["sourceIds"] = ["S9"]
        self.assertTrue(mc.validate_species(bad))
        a, b = sp(), sp()
        b["speciesId"] = "y"
        self.assertEqual(sorted(mc.dedupe_sources([a, b])["example.gov/x"]["species"]), ["x", "y"])
        m = mc.mismatch([{"bk": 8, "v2": 1.0, "important": True}, {"bk": 5, "v2": 2.0}, {"bk": 7, "v2": 6.0}])
        self.assertEqual((m["bk_ge_6_but_v2_lt_3"], m["bk_ge_7"], m["important_well_understood"]), (1, 2, 1))


if __name__ == "__main__":
    unittest.main()
