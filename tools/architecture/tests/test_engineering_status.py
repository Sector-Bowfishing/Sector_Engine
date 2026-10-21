"""engineering-status-v1 (Cortex 2.1 adoption 2026-10-20): the machine-readable report for Sector Ops is generated only from committed records, is
current, validates against its schema and never claims more than the records: no Brain without a package reports production status, every blocker
names a recorded decision, and verification entries that did not run say NOT_RUN. The generator is offline (no network, clock or git)."""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "cortex_status"))
import build_engineering_status as B  # noqa: E402


def test_the_committed_report_is_current_and_valid():
    assert B.main(["--check"]) == 0


def test_every_control_manifest_brain_is_reported_once():
    r = B.build()
    manifest = json.load(open(os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")))["brains"]
    assert sorted(b["brainId"] for b in r["brains"]) == sorted(manifest)


def test_branch_only_brains_claim_no_production_status_and_no_certification():
    for b in B.build()["brains"]:
        if b["packageStatus"] == "BRANCH_ONLY":
            assert all(m["production"] == "NOT_APPLICABLE" for m in b["memory"]), b["brainId"]
            assert b["structuralCertification"]["status"] == "FAIL"


def test_blockers_name_recorded_decisions_and_unrun_checks_say_not_run():
    r = B.build()
    ids = {d["id"] for d in r["decisions"]}
    for b in r["brains"]:
        assert set(b["blockers"]) <= ids, b["brainId"]
    for v in r["verification"]:
        if v["result"] == "PASS":
            assert v.get("failed", 0) == 0
        if v["result"] == "NOT_RUN":
            assert "passed" not in v and v.get("note")


def test_the_report_pins_the_same_cortex_as_claude_md():
    assert B.build()["standards"]["pin"] == re.search(r"^Cortex pin:\s*(\S+)", open(os.path.join(ROOT, "CLAUDE.md")).read(), re.M).group(1)


def test_the_generator_is_offline():
    src = open(B.__file__, encoding="utf-8").read()
    for forbidden in ("urllib", "requests", "socket", "subprocess", "datetime", "time.time", "firebase", "google.cloud"):
        assert forbidden not in src, forbidden
