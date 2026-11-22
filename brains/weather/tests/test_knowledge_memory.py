"""Approved-memory behaviour (Cortex BR-10/11): the pre-stated thresholds come only from the verified release; a missing or tampered release
refuses (no fallback copy in code)."""
import json
import os
import shutil

import pytest

from sector_weather import contract as C, knowledge as K


def test_the_contract_thresholds_are_the_verified_release(tmp_path):
    rel, doc = K.load()
    assert rel["releaseId"] == "weather-knowledge-candidate-2026-11-22.1" and rel["approvalStatus"] == "NOT_RECORDED"
    assert C.THRESHOLDS == doc["changeRules"] and C.THRESHOLDS_VERSION == doc["thresholdsVersion"] == "weather-change-thresholds-v1"
    assert C.TIER_WINDOW_MIN == doc["freshness"]["tierWindowMin"]
    assert set(doc["reasons"]) == set(doc["changeRules"])                 # every threshold carries its stated reason


def test_a_tampered_release_refuses(tmp_path):
    d = tmp_path / "knowledge"
    shutil.copytree(K.RELEASE_DIR, d)
    p = d / K.THRESHOLDS_FILE
    doc = json.loads(p.read_text())
    doc["changeRules"]["pressureFastInHgPer3h"] = 0.03                    # a silent edit of a pre-stated threshold
    p.write_text(json.dumps(doc))
    with pytest.raises(K.KnowledgeReleaseError):
        K.load(str(d))


def test_a_missing_release_refuses(tmp_path):
    with pytest.raises(K.KnowledgeReleaseError):
        K.load(str(tmp_path))
