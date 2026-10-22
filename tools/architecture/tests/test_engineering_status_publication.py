"""control/engineeringStatusV1 publication gate (engineering-status-ops-v1 1.1.0). One sanitizer and one gate for producer and publisher; the
orchestrator is the only writer, behind --publish-engineering-status (decision O-1). Every refused case publishes an explicit, schema-valid
UNAVAILABLE document, never an older status and never an unmerged branch presented as main."""
import copy
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "cortex_status"))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
import build_engineering_status as B  # noqa: E402
import ops_projection as P  # noqa: E402
from jsonschema_lite import validate  # noqa: E402
from sector_brain_platform import engineering_status_publication as E  # noqa: E402

SHA = "a" * 40
NOW = "2026-10-21T00:00:00Z"
DV = f"brain-orchestrator@{SHA[:12]}"
SCHEMA = json.load(open(os.path.join(ROOT, "contracts", "schemas", "engineering-status-ops-v1.schema.json")))


def _proj(state="MAIN_COMMIT"):
    r = B.build()
    r["source"]["evaluatedCommit"] = SHA
    return P.project(r, branch="main" if state == "MAIN_COMMIT" else "cortex/architecture-standardization-2026-10-20", code_state=state,
                     generated_at=NOW)


def _gate(doc, dv=DV):
    return E.gate(doc, deployed_commit=E.deployed_commit(dv), now_iso=NOW, deployment_version=dv)


def test_a_main_commit_projection_of_the_deployed_commit_is_published_and_schema_valid():
    g = _gate(_proj())
    assert g["state"] == "AVAILABLE" and g["publishedBy"] == {"component": "brain-orchestrator", "deploymentVersion": DV}
    assert validate(g, SCHEMA) == [] and E.leaks(g) == []


@pytest.mark.parametrize("case,expect", [
    ("missing", "no engineering-status projection"),
    ("unmerged", "UNMERGED_BRANCH"),
    ("stale-certification", "certification run does not belong"),
    ("other-commit", "does not match the deployed commit"),
    ("no-deployment-version", "does not match the deployed commit"),
    ("leak", "projection rejected"),
    ("wrong-major", "projection rejected"),
    ("missing-layer", "projection rejected"),
    ("unreadable", "projection rejected"),
])
def test_every_refusal_is_an_explicit_schema_valid_unavailable(case, expect):
    doc, dv = _proj(), DV
    if case == "missing":
        doc = None
    elif case == "unmerged":
        doc = _proj("UNMERGED_BRANCH")
    elif case == "stale-certification":
        doc["generatedFrom"]["certificationCurrent"] = False
    elif case == "other-commit":
        dv = "brain-orchestrator@0123456789ab"
    elif case == "no-deployment-version":
        dv = None
    elif case == "leak":
        doc["brains"][0]["nextWork"] = ["read gs://sector-lake-brain/presence/latest.json"]
    elif case == "wrong-major":
        doc["schemaVersion"] = "2.0.0"
    elif case == "missing-layer":
        del doc["brains"][0]["statusLayers"]["customerConsumable"]
    elif case == "unreadable":
        doc = {"schema": "unreadable"}
    g = _gate(doc, dv)
    assert g["state"] == "UNAVAILABLE" and expect in g["reason"], g
    assert validate(g, SCHEMA) == [] and set(g) <= {"schema", "schemaVersion", "state", "reason", "checkedAt", "publishedBy"}


def test_the_projection_names_its_branch_and_code_state_but_never_claims_production():
    p = _proj("UNMERGED_BRANCH")
    assert p["generatedFrom"]["codeState"] == "UNMERGED_BRANCH" and p["generatedFrom"]["sourceBranch"].startswith("cortex/")
    assert all(b["statusLayers"]["productionActivation"]["status"] != "PASS" for b in p["brains"])
    assert validate(p, SCHEMA) == [] and E.leaks(p) == []                       # the branch ref is allowed in sourceBranch only
    q = copy.deepcopy(p)
    q["brains"][0]["nextWork"] = ["see cortex/architecture-standardization-2026-10-20"]
    assert E.leaks(q)


def test_one_sanitizer_for_producer_and_publisher():
    assert P.leaks is E.leaks and P.FORBIDDEN is E.FORBIDDEN


def test_the_orchestrator_writes_the_node_only_behind_the_o1_flag_and_from_the_gate():
    src = open(os.path.join(ROOT, "jobs", "brain-orchestrator", "orchestrate.py"), encoding="utf-8").read()
    assert '"--publish-engineering-status", action="store_true"' in src                          # OFF by default
    writes = [l for l in src.splitlines() if "ESP.NODE" in l and "update" in l]
    assert writes == ["                db.update({ESP.NODE: es_doc})"]
    assert re.search(r"if a\.publish_engineering_status and not a\.health_only and \(write or a\.dry_run\):.*\n\s*db\.update\(\{ESP\.NODE: es_doc\}\)", src)   # --health-only writes healthV1 only
    assert "es_doc = ESP.gate(ESP.load_staged(HERE)" in src                                       # never anything but the gated, staged projection


def test_the_staging_step_never_ships_the_full_report_and_skips_a_stale_one():
    sh = open(os.path.join(ROOT, "jobs", "brain-orchestrator", "deploy-job.sh"), encoding="utf-8").read()
    assert "rm -f stage/es-full.json" in sh and "--out stage/jobs/brain-orchestrator/engineering-status-ops.json" in sh
    assert "merge-base --is-ancestor HEAD origin/main" in sh and "ES_STATE=UNMERGED_BRANCH" in sh
