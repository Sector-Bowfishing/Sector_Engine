"""engineering-status-ops-v1: the sanitized Sector Ops projection is schema-valid, carries no evidence strings or internal references, refuses
an unstamped report, refuses (never silently redacts) a leaking field, and cannot write anywhere."""
import copy
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "cortex_status"))
import build_engineering_status as B  # noqa: E402
import ops_projection as P  # noqa: E402
from jsonschema_lite import validate  # noqa: E402

SHA = "f" * 40


def _stamped():
    r = B.build()
    r["source"]["evaluatedCommit"] = SHA
    return r


def test_the_projection_is_schema_valid_and_leak_free():
    proj = P.project(_stamped())
    assert list(validate(proj, json.load(open(P.SCHEMA)))) == []
    assert P.leaks(proj) == []
    assert proj["generatedFrom"]["sourceCommit"] == SHA and len(proj["brains"]) == 8


def test_no_evidence_strings_reach_the_browser():
    text = json.dumps(P.project(_stamped()))
    assert '"evidence"' not in text and "productionBasis" not in text and "recovery" not in text


def test_an_unstamped_report_is_refused():
    with pytest.raises(SystemExit):
        P.project(B.build())                        # the committed report carries a short commit, not the CI-stamped one


@pytest.mark.parametrize("leak", ["gs://sector-biology-private/biology/v1", "see brains/fish/runtime/run.py", "/Users/someone/x",
                                  "token ghp_abcdefghijklmnop", "branch cortex/architecture-standardization-2026-10-20"])
def test_a_leaking_field_is_refused_not_redacted(leak):
    r = _stamped()
    r = copy.deepcopy(r)
    r["brains"][0]["nextWork"] = [leak]
    assert P.leaks(P.project(r)), leak


def test_the_projection_tool_has_no_write_capability():
    src = open(P.__file__, encoding="utf-8").read()
    for forbidden in ("firebase", "urllib", "requests", "http.client", "socket", "BrainRtdb", "subprocess"):
        assert forbidden not in src.replace("Firebase write", ""), forbidden
