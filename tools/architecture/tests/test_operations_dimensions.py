"""engineering-status-ops-v1 1.2.0 (owner decision D-IA-2, Option B): every Brain carries the four independent Cortex 2.6.0 dimensions additively,
the legacy operationalReadiness layer is kept unchanged and documented as release readiness, the Engine score is classified ENGINEERING_SCORE
(D-IA-1), values outside the Cortex vocabulary are refused, and the published shape converts into a Cortex ops-check status document."""
import copy
import datetime as dt
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "cortex_status"))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
import build_engineering_status as B  # noqa: E402
import ops_projection as P  # noqa: E402
import operations_status as OS  # noqa: E402
from jsonschema_lite import validate  # noqa: E402
from sector_brain_platform import brain_operations as BO, engineering_status_publication as ESP  # noqa: E402

IDS = {"biological-state", "wind", "water-clarity", "lake-brain", "water-temp", "sector-intelligence", "depth", "vegetation"}
NOW = dt.datetime(2026, 10, 22, 16, tzinfo=dt.timezone.utc)


def _proj():
    r = B.build()
    r["source"]["evaluatedCommit"] = "f" * 40
    return P.project(r, code_state="MAIN_COMMIT")


def test_every_brain_carries_the_static_dimensions_and_the_legacy_layer_is_kept():
    p = _proj()
    assert p["schemaVersion"] == "1.3.0" and {b["brainId"] for b in p["brains"]} == IDS
    assert list(validate(p, json.load(open(P.SCHEMA)))) == [] and P.leaks(p) == []
    for b in p["brains"]:
        o = b["operations"]
        assert o["customerEligibility"]["status"] == "NOT_ELIGIBLE" and "approvalRef" not in o["customerEligibility"]
        assert o["scientificValidation"]["status"] in BO.SCIENCE and o["knowledgeRelease"]["state"] in BO.KNOWLEDGE
        assert "INTERNAL" in o["executionModes"] and o["limitations"]
        assert "runtimeReadiness" not in o and "internalOperation" not in o           # live dimensions come only from the orchestrator
        assert set(b["statusLayers"]) == set(ESP.LAYERS)                              # legacy layers unchanged (compatibility)
    assert "RELEASE_READINESS" in p["legacyLayers"]["operationalReadiness"]


def test_scores_are_classified_and_the_engine_score_is_an_engineering_score():
    p = _proj()
    assert p["engineScore"]["measurement"] == "ENGINEERING_SCORE" and p["engineScore"]["rubric"] == "engine-score-v1"
    by = {b["brainId"]: b["operations"]["scores"] for b in p["brains"]}
    assert by["depth"] == [] and by["vegetation"] == []                               # no score is invented for an unscored Brain
    assert {s["measurement"] for s in by["wind"]} == {"SCIENTIFIC_MATURITY", "DOMAIN_CAPABILITY"}
    assert all(s["measurement"] != "ENGINEERING_SCORE" for v in by.values() for s in v)


def test_every_score_reference_resolves_to_a_number_in_the_scores_node_shape():
    """Found in final verification (2026-10-22): /scores/wind.measurements.windCapability is an OBJECT ({value, categories, ...}); a reference
    must name the numeric field, or a consumer shows nothing. Fields are dotted paths ending at a number-valued key."""
    shape = {"wind": {"value": 3.3, "measurements": {"windCapability": {"value": 6.7, "basis": "COMPUTED"}}}}
    for b in _proj()["brains"]:
        for s in b["operations"]["scores"]:
            v = shape.get(s["source"].rsplit("/", 1)[-1])
            if v is None:
                continue
            for part in s.get("field", "value").split("."):
                v = v.get(part) if isinstance(v, dict) else None
            assert isinstance(v, (int, float)), (b["brainId"], s)


def test_values_outside_the_cortex_vocabulary_are_refused(monkeypatch):
    real = B._operations
    monkeypatch.setattr(B, "_operations", lambda bid, o, bj, mb: real(bid, {**o, "scientificValidation": {"status": "PRODUCTION_READY", "label": "X"}}, bj, mb))
    with pytest.raises(SystemExit):
        B.build()
    with pytest.raises(SystemExit):
        real("x", {"scientificValidation": {"status": "IN_PROGRESS", "label": "X"}, "knowledgeRelease": {"state": "CANDIDATE"},
                   "scores": [{"measurement": "CAPABILITY", "source": "/scores/x"}]}, {}, {"customerPublication": False})


def test_customer_eligibility_needs_the_manifest_to_agree_and_an_approval_reference():
    o = {"scientificValidation": {"status": "IN_PROGRESS", "label": "X"}, "knowledgeRelease": {"state": "CANDIDATE"}}
    bj = {"operations": {"customerPublication": {"status": "NOT_ELIGIBLE"}}}
    assert B._operations("x", o, bj, {"customerPublication": True})["customerEligibility"]["status"] == "NOT_VERIFIED"
    with pytest.raises(SystemExit):
        B._operations("x", o, {"operations": {"customerPublication": {"status": "ELIGIBLE"}}}, {"customerPublication": False})


def test_the_live_document_is_schema_valid_leak_free_and_passes_the_cortex_status_shape():
    p = _proj()
    m = {"brains": {"wind": {"activityState": "ACTIVE", "freshness": {"staleAfterHours": 1.5}, "schedule": {"class": "VALIDATION_EXCEPTION", "scheduler": "wind-hourly"}},
                    "depth": {"activityState": "PARKED", "shadowLane": {"enabled": True, "cadenceHours": 24}}}}
    rows = {"wind": {"brainId": "wind", "lastSuccessfulRun": "2026-10-22T15:05:00Z", "lastExecution": {"at": "2026-10-22T15:05:00Z", "status": "SUCCEEDED"},
                     "lastDataUpdate": {"at": "2026-10-22T15:05:00Z", "basis": "TIME"}}}
    shadow = {"depth": {"schema": "brain-shadow-lane-v1", "lane": "INTERNAL_EXPERIMENTAL", "executionMode": "INTERNAL", "experimental": True, "runAt": "2026-10-22T06:00:00Z",
                        "lakeCount": 1, "lakes": {"A": {"kind": "observed"}}, "candidateRelease": {"releaseId": "c", "approvalStatus": "NOT_RECORDED"}}}
    live = BO.overlay({**p, "state": "AVAILABLE"}, m, rows, scheduler_states={"wind-hourly": "ENABLED", "brain-orchestrator": "ENABLED"},
                      shadow_docs=shadow, plans={}, now=NOW)
    assert list(validate(live, json.load(open(P.SCHEMA)))) == [] and ESP.leaks(live) == []
    st = OS.convert(live)
    by = {b["brainId"]: b for b in st["brains"]}
    assert len(st["brains"]) == 8 and by["wind"]["internalOperation"]["status"] == "ACTIVE" and by["depth"]["internalOperation"]["status"] == "SHADOW"
    assert by["depth"]["outputs"][0]["lane"] == "INTERNAL_EXPERIMENTAL" and {"mode": "APPROVED_SCIENCE", "knowledgeState": "CANDIDATE", "outcome": "REFUSED"} in by["depth"]["runs"]
    assert "combinedReadiness" not in by["depth"] and by["depth"]["releaseReadiness"]["status"] == "BLOCKED"   # release readiness, beside the dimensions
    assert all(b["customerEligibility"]["status"] == "NOT_ELIGIBLE" for b in st["brains"])


def test_a_pre_1_2_document_is_refused_by_the_converter():
    p = _proj()
    old = copy.deepcopy({**p, "state": "AVAILABLE"})
    for b in old["brains"]:
        b.pop("operations")
    with pytest.raises(SystemExit):
        OS.convert(old)
