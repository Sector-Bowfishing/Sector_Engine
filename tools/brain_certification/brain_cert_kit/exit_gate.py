"""PRODUCTION_EXIT_GATE_V1 — the reusable evidence contract a Brain must satisfy before `publisherRequired.cutoverStatus` may become CUTOVER_COMPLETE.

This module is DATA + a pure evaluator. It performs no I/O against any database and contains no live-mutation test: live checks (mode LIVE) are executed by a
reviewed cutover runbook against a real Publisher and recorded as an evidence record; this module only decides whether that record is complete and consistent.
OFFLINE checks are provable today against the SHADOW Publisher / in-memory stores and are the ones a Brain's own suite can already run.

An evidence record (JSON) lives at brains/<dir>/contracts/production-exit-evidence.json once a cutover is attempted:
    {"standard": "production-exit-gate-v1", "brainId": "...", "checks": {"X01": {"status": "PASS", "evidenceRef": "...", "mode": "LIVE"}, ...}}
"""
from __future__ import annotations

import json
import os
import re

STANDARD = "production-exit-gate-v1"
OFFLINE, LIVE = "OFFLINE", "LIVE"
STATUSES = ("PASS", "FAIL", "NOT_RUN")
CUTOVER_STATUSES = ("SHADOW", "CUTOVER_IN_PROGRESS", "CUTOVER_COMPLETE")

# (id, slug, mode, pass criterion)
CHECKS = (
    ("X01", "artifact_accepted", OFFLINE, "a valid sealed artifact is accepted by the Publisher (no rejection code)"),
    ("X02", "brain_identity", OFFLINE, "an artifact carrying another brainId is rejected; accepted artifact brainId == brain.json brainId"),
    ("X03", "schema", OFFLINE, "an artifact with an unregistered or mismatched schema is rejected"),
    ("X04", "path_ownership", OFFLINE, "every key of the write plan is inside the Brain's declared path families; a cross-domain key is rejected"),
    ("X05", "deterministic_fingerprint", OFFLINE, "the same domain truth yields the same fingerprint across runs; volatile fields do not move it"),
    ("X06", "unchanged_skips", OFFLINE, "an unchanged artifact SKIPs and produces zero live writes"),
    ("X07", "changed_publishes", LIVE, "a changed artifact publishes and the authoritative readback shows the change"),
    ("X08", "unrelated_paths_untouched", LIVE, "a before/after export shows no path outside the plan's write set changed"),
    ("X09", "atomic_write", LIVE, "the write set lands as ONE multi-location update (or manifest-last PARTIAL->COMPLETE); a forced mid-write failure leaves the prior state intact"),
    ("X10", "publication_metadata", LIVE, "/brains/<id>/publication carries artifactId, fingerprint, status COMPLETE, lineage and release identity matching the artifact"),
    ("X11", "health_correct", LIVE, "healthV1 for the Brain is neither blanked nor wrongly HEALTHY after cutover; no Brain-authored process health remains authoritative"),
    ("X12", "score_ownership", LIVE, "/scores/<id> is still written only by the scorer; score before == after under the same scoreType/scoreVersion, or the difference is separately approved"),
    ("X13", "rollback", LIVE, "the previous publication is restored through the reviewed rollback path and readback equals the pre-cutover export"),
    ("X14", "legacy_writer_cannot_reenter", OFFLINE, "the Brain's runtime has zero RTDB write sites for Publisher-owned paths; brain.json cutoverStatus and the AST write pin agree"),
    ("X15", "readback_matches_publication", LIVE, "an independent authoritative read of every planned path equals the published artifact content"),
    ("X16", "write_denial", LIVE, "tested denials: the specialist identity, Ops and a cross-domain identity cannot write; the Publisher identity can (rules AND IAM) — exit evidence F"),
)
CHECK_IDS = tuple(c[0] for c in CHECKS)


#: Where the repository half of each check is proven. Tier: OFFLINE = provable with no client at all (validators, AST, registry);
#: REPO_FAKE = proven against FAKE RTDB/object-store clients (the live code path, not a live database); LIVE_ONLY = cannot be claimed without an approved cutover.
#: Every named test must exist (a test pins this), so the matrix cannot drift from the code.
PARITY = "brain_cert_kit/live_parity.py"
PLATFORM = "jobs/brain_platform/tests/"
REPO_COVERAGE = {
    "X01": ("OFFLINE", (PARITY + "::test_live_parity_artifact_publishes_with_correct_identity_and_metadata",)),
    "X02": ("OFFLINE", (PARITY + "::test_live_parity_identity_schema_and_lifecycle_are_enforced",)),
    "X03": ("OFFLINE", (PARITY + "::test_live_parity_identity_schema_and_lifecycle_are_enforced",)),
    "X04": ("OFFLINE", (PARITY + "::test_live_parity_plan_stays_inside_the_brains_families_and_protected_paths_are_rejected", PLATFORM + "test_publisher_live_security.py::test_the_publisher_can_never_write_platform_foreign_or_orchestrator_owned_paths_for_wind")),
    "X05": ("OFFLINE", (PARITY + "::test_live_parity_fingerprint_is_deterministic_and_unchanged_artifacts_skip",)),
    "X06": ("OFFLINE", (PARITY + "::test_live_parity_fingerprint_is_deterministic_and_unchanged_artifacts_skip", PLATFORM + "test_publisher_live.py::test_unchanged_artifact_skips_with_no_live_write_and_no_score_signal")),
    "X07": ("REPO_FAKE", (PARITY + "::test_live_parity_changed_artifact_publishes_with_readback_and_score_signal",)),
    "X08": ("REPO_FAKE", (PARITY + "::test_live_parity_unrelated_brains_and_platform_paths_are_untouched",)),
    "X09": ("REPO_FAKE", (PARITY + "::test_live_parity_oversize_plan_is_manifest_last_and_failure_keeps_the_previous_release", PLATFORM + "test_publisher_live.py::test_oversize_plans_are_applied_manifest_last_and_a_mid_failure_keeps_the_previous_release_authoritative")),
    "X10": ("REPO_FAKE", (PARITY + "::test_live_parity_artifact_publishes_with_correct_identity_and_metadata",)),
    "X11": ("REPO_FAKE", (PARITY + "::test_live_parity_health_and_score_ownership_are_preserved",)),
    "X12": ("REPO_FAKE", (PARITY + "::test_live_parity_health_and_score_ownership_are_preserved", PLATFORM + "test_publication_trigger.py::test_end_to_end_publish_skip_failure_against_the_live_publisher")),
    "X13": ("REPO_FAKE", (PARITY + "::test_live_parity_rollback_restores_the_previous_state_exactly", PLATFORM + "test_publisher_live.py::test_rollback_restores_the_previous_publication_removes_new_paths_and_retriggers_scoring")),
    "X14": ("OFFLINE", (PARITY + "::test_live_parity_legacy_writer_reentry_is_detected_and_reserved_children_survive", "tests/test_exit_gate.py::test_cutover_complete_is_refused_while_a_legacy_write_site_remains_active")),
    "X15": ("REPO_FAKE", (PARITY + "::test_live_parity_changed_artifact_publishes_with_readback_and_score_signal", PLATFORM + "test_publisher_live.py::test_a_lost_response_after_commit_is_verified_by_readback_not_assumed")),
    "X16": ("LIVE_ONLY", (PLATFORM + "test_publisher_live_security.py::test_principal_matrix_specialist_ops_denied_in_target_publisher_success_and_current_reality_is_visible",)),
}
#: X16 has REPO_READY evidence (fake-client denial/success + target rules + IAM plan) but its pass criterion (real rules AND real IAM) is LIVE_ONLY.
LIVE_ONLY_PORTIONS = {cid: "the real-database/real-identity half" for cid, (tier, _t) in REPO_COVERAGE.items() if tier in ("REPO_FAKE", "LIVE_ONLY")}


def repo_status():
    """{id: {tier, repoProven, liveStillRequired}}: what the repository can show today versus what only an approved cutover can."""
    return {cid: {"tier": tier, "repoProven": True, "liveStillRequired": tier != "OFFLINE", "tests": list(tests)} for cid, (tier, tests) in REPO_COVERAGE.items()}


LEGACY_WRITE_SUFFIXES = ("rtdb.update", "_db.update", "db.update")


def legacy_write_sites(brain_dir, brain_id=None):
    """Every direct database write site left in a Brain's runtime: AST call sites of the write primitives PLUS any literal that builds a WHOLE Brain node key
    (`brains/<id>` / `health/brains/<id>`, even through an f-string), which a child-level Publisher must never share ownership of."""
    from .env import walk_files, write_sites
    runtime = os.path.join(brain_dir, "runtime")
    with open(os.path.join(brain_dir, "brain.json"), encoding="utf-8") as f:
        bid = brain_id or json.load(f).get("brainId")
    whole = re.compile(r"""["']/?(?:health/)?brains/(?:%s|\{[^}]*\})["']""" % re.escape(bid))
    sites, nodes = set(), []
    for path in walk_files(runtime, (".py",)):
        sites |= write_sites(path, LEGACY_WRITE_SUFFIXES)
        for i, line in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
            if whole.search(line) and "assert" not in line:
                nodes.append((os.path.basename(path), i))
    return {"writeSites": sorted(sites), "wholeNodeKeys": nodes}


def evaluate(evidence, brain_id=None):
    """Pure verdict over an evidence record. PASS only if every check is PASS with a non-empty evidenceRef, modes match the definition, brainId matches, and
    nothing unknown is present. Returns {"verdict": "PASS"|"BLOCKED", "problems": [...], "missing": [...]}."""
    problems, missing = [], []
    if not isinstance(evidence, dict):
        return {"verdict": "BLOCKED", "problems": ["evidence is not an object"], "missing": list(CHECK_IDS)}
    if evidence.get("standard") != STANDARD:
        problems.append(f"standard must be {STANDARD}")
    if brain_id is not None and evidence.get("brainId") != brain_id:
        problems.append(f"brainId {evidence.get('brainId')!r} != {brain_id!r}")
    checks = evidence.get("checks") if isinstance(evidence.get("checks"), dict) else {}
    for unknown in sorted(set(checks) - set(CHECK_IDS)):
        problems.append(f"unknown check {unknown}")
    for cid, _slug, mode, _crit in CHECKS:
        c = checks.get(cid)
        if not isinstance(c, dict):
            missing.append(cid)
            continue
        if c.get("status") not in STATUSES:
            problems.append(f"{cid}: invalid status {c.get('status')!r}")
        elif c["status"] != "PASS":
            missing.append(cid)
        elif not (isinstance(c.get("evidenceRef"), str) and c["evidenceRef"].strip()):
            problems.append(f"{cid}: PASS without evidenceRef")
        if c.get("mode") not in (None, mode):
            problems.append(f"{cid}: mode {c.get('mode')!r} != {mode}")
    return {"verdict": "PASS" if not problems and not missing else "BLOCKED", "problems": problems, "missing": missing}


def cutover_guard(brain_dir, brain_id=None):
    """Raise AssertionError if brain.json claims CUTOVER_COMPLETE (or CUTOVER_IN_PROGRESS is invalid) without a PASSing evidence record."""
    with open(os.path.join(brain_dir, "brain.json"), encoding="utf-8") as f:
        brain = json.load(f)
    pub = brain.get("publisherRequired") or {}
    status = pub.get("cutoverStatus")
    assert status in CUTOVER_STATUSES, f"cutoverStatus {status!r} is not one of {CUTOVER_STATUSES}"
    if status == "SHADOW":
        return {"cutoverStatus": status, "gate": "NOT_REQUIRED_WHILE_SHADOW"}
    path = os.path.join(brain_dir, "contracts", "production-exit-evidence.json")
    assert os.path.isfile(path), f"cutoverStatus {status} requires {path} (PRODUCTION_EXIT_GATE_V1)"
    with open(path, encoding="utf-8") as f:
        verdict = evaluate(json.load(f), brain_id or brain.get("brainId"))
    if status == "CUTOVER_COMPLETE":
        assert verdict["verdict"] == "PASS", f"CUTOVER_COMPLETE without a complete exit record: {verdict}"
        left = legacy_write_sites(brain_dir, brain_id or brain.get("brainId"))
        assert not left["writeSites"] and not left["wholeNodeKeys"], f"CUTOVER_COMPLETE while a legacy writer remains active (X14): {left}"
    return {"cutoverStatus": status, "gate": verdict["verdict"]}
