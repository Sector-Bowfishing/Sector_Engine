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
    return {"cutoverStatus": status, "gate": verdict["verdict"]}
