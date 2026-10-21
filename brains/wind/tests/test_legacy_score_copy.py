"""Cortex 2.2 FD-09 / Firebase audit C-1: Wind's copy of its FROZEN validation-evidence scores (/brains/wind/scores, /validation/wind/scores) is
labelled as frozen, non-authoritative evidence that names the authoritative node; its values never change; one switch retires it."""
import wind_cert_spec as W
from sector_wind.brain import contract as C
from sector_wind.brain import publish as P

EVIDENCE = {"scores": {"windCertificationScore": 3.1, "windCertificationRubric": "frozen v1", "bowfishingWindIntelligenceScore": 5.4},
            "frozenAt": "2026-10-12T06:16:16Z"}


def _registry_and_validation():
    reg = val = None
    for patch in W._patches():
        reg = patch.get("brains/wind", reg)
        val = patch.get("validation/wind", val)
    return reg, val


def test_published_copy_is_labelled_and_values_unchanged():
    reg, val = _registry_and_validation()
    for scores in (reg["scores"], val["scores"]):
        assert scores["measurement"] == "FROZEN_VALIDATION_EVIDENCE" and scores["authoritative"] is False
        assert scores["authoritativeScorePath"] == "/scores/wind" and scores["status"] == "LEGACY_COMPATIBILITY"
        assert scores["measuredAt"] and scores["windCertificationScore"] == 3.1 and scores["bowfishingWindIntelligenceScore"] == 5.4


def test_label_never_alters_a_score_value():
    out = P.legacy_score_copy(EVIDENCE)
    assert {k: out[k] for k in EVIDENCE["scores"]} == EVIDENCE["scores"] and out["measuredAt"] == EVIDENCE["frozenAt"]


def test_retirement_switch_stops_the_copy(monkeypatch):
    monkeypatch.setattr(C, "PUBLISH_LEGACY_SCORE_COPY", False)
    assert P.legacy_score_copy(EVIDENCE) is None
