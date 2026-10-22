"""intelligence-evaluation-v1: the versioned contract of the pilot evaluation (Cortex BR-13), checked against REAL evaluation output, plus the
2026-10-20 output corrections (D-8): provenance names the Brain version, the evaluation's evidence time is its oldest input, and the catalog's
inventory-mode blockers are not published next to pilot evaluations."""
import json
import os
import sys

import intelligence_support as S
import evaluation as ev
import sector_intelligence_brain as sib

sys.path.insert(0, os.path.join(S.REPO, "tools", "architecture"))
from jsonschema_lite import validate  # noqa: E402

SCHEMA = json.load(open(os.path.join(S.REPO, "brains", "sector-intelligence", "contracts", "intelligence-evaluation-v1.schema.json"), encoding="utf-8"))
U = S.run_updates()
EVALUATION = U["/lakes/Guntersville_AL/states/intelligence"]


def test_real_evaluation_validates_against_its_versioned_contract():
    assert SCHEMA["properties"]["evaluationVersion"]["const"] == ev.EVAL_VERSION
    assert validate(EVALUATION, SCHEMA) == []


def test_contract_rejects_a_rating_and_a_customer_consumer():
    assert validate(dict(EVALUATION, score=7.5), SCHEMA)                                   # closed top level: no score/rating field
    assert validate(dict(EVALUATION, customerPath=dict(EVALUATION["customerPath"], consumesThisEvaluation=True)), SCHEMA)


def test_provenance_names_the_brain_version():
    assert EVALUATION["provenance"]["brainVersion"] == sib.BRAIN_VERSION


def test_evidence_time_is_the_oldest_input_used_never_the_run_time():
    used = [u["generatedAt"] for u in EVALUATION["inputsUsed"].values() if u.get("generatedAt")]
    assert used and EVALUATION["freshness"]["sourceObservationAt"] == min(used)
    assert EVALUATION["freshness"]["sourceObservationAt"] != EVALUATION["generatedAt"]


def test_inventory_mode_blockers_are_not_published_next_to_pilot_evaluations():
    ids = {b["id"] for b in U["/brains/sector-intelligence"]["blockers"]}
    assert not ids & set(sib.PILOT_RESOLVED_BLOCKERS)
    import test_sector_intelligence_brain as T
    inventory_only = T.build()                                                              # no evaluations: the catalog's blockers stay
    assert set(sib.PILOT_RESOLVED_BLOCKERS) <= {b["id"] for b in inventory_only["/brains/sector-intelligence"]["blockers"]}
