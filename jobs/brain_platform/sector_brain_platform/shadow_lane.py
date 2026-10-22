"""Isolated SHADOW lane for Brains that have no APPROVED knowledge release (internal operation, 2026-10-22).

A Brain's approved serving path keeps refusing unapproved knowledge (BLOCKED_AWAITING_APPROVED_RELEASE). The shadow lane runs the Brain's OWN
runtime against its CANDIDATE release into an in-memory writer (nothing is written to Brain-owned paths) and publishes only a compact,
explicitly experimental summary to the platform-owned control plane:

    /control/shadowLaneV1/{brainId}     schema brain-shadow-lane-v1, lane INTERNAL_EXPERIMENTAL, executionMode INTERNAL, experimental true

The summary is never authoritative, never customer-eligible, never read by the scorer or by Sector Intelligence. It carries the candidate
release identity (id, digest, approval status), the approved path's status (ABSTAIN + reason), per-lake readiness/kind only (an allowlist:
no values, no agency or internal-only fields), counts, and a SHA-256 of the full in-memory output for provenance. Stdlib only; no clock
(callers pass `now`). Cortex 2.5.0 operations.md: IO-02 (INTERNAL mode), IO-03 (candidate artifact, never loaded as approved), IO-05
(lane marking; never reaches customer paths, recommendation feeds, approved pointers or scores), IO-06 (isolated internal publication)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json

NODE_ROOT = "control/shadowLaneV1"
SCHEMA = "brain-shadow-lane-v1"
SCHEMA_VERSION = "1.0.0"
CLASSIFICATION = "INTERNAL_EXPERIMENTAL"
LANE = "INTERNAL_EXPERIMENTAL"                                       # Cortex 2.5.0 output lane (IO-05)
EXECUTION_MODE = "INTERNAL"                                          # Cortex 2.5.0 execution mode (IO-02): runs labelled without an approved release
LAKE_FIELDS = ("readiness", "kind", "stateType", "status")          # allowlist copied per lake; everything else stays out of the summary
MAX_LAKES = 100
HISTORY = 10
CONSUMERS = ("sector-ops (read-only display, labelled EXPERIMENTAL)",)
FORBIDDEN_CONSUMERS = ("customer apps and the customer Engine API", "sector-intelligence", "brain-scores (no score is ever derived from it)")


def node(brain_id: str) -> str:
    return f"{NODE_ROOT}/{brain_id}"


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def flatten(patches: list) -> dict:
    """The in-memory writer's multi-path patches, applied in order -> {path: value}."""
    out: dict = {}
    for p in patches or []:
        if isinstance(p, dict):
            out.update({k.strip("/"): v for k, v in p.items()})
    return out


def _lake_rows(flat: dict, slot: str) -> dict:
    rows = {}
    for path, val in sorted(flat.items()):
        parts = path.split("/")
        if len(parts) == 4 and parts[0] == "lakes" and parts[2] == "states" and parts[3] == slot and isinstance(val, dict):
            prov = val.get("provenance") if isinstance(val.get("provenance"), dict) else {}
            row = {f: val.get(f) for f in LAKE_FIELDS if isinstance(val.get(f), (str, int, float, bool))}
            if "readiness" not in row and isinstance(prov.get("readiness"), str):
                row["readiness"] = prov["readiness"]
            rows[parts[1]] = row
    return dict(list(rows.items())[:MAX_LAKES])


def summarize(brain_id: str, slot: str, patches: list, report: dict, release: dict, approved_path: dict, now_iso: str,
              deployment_version: str | None = None, prev: dict | None = None) -> dict:
    flat = flatten(patches)
    lakes = _lake_rows(flat, slot)
    counts: dict = {}
    for r in lakes.values():
        counts[r.get("readiness") or "UNKNOWN"] = counts.get(r.get("readiness") or "UNKNOWN", 0) + 1
    digest = "sha256:" + hashlib.sha256(canonical(flat)).hexdigest()
    rep = {k: report.get(k) for k in ("ok", "evaluated", "observed", "unavailable", "skippedUnchanged", "writes") if report.get(k) is not None}
    errors = [str(e)[:200] for e in (report.get("errors") or [])][:5]
    hist = [h for h in ((prev or {}).get("history") or []) if isinstance(h, dict)][-(HISTORY - 1):]
    hist.append({"runAt": now_iso, "outputDigest": digest, "lakes": len(lakes)})
    doc = {
        "schema": SCHEMA, "schemaVersion": SCHEMA_VERSION, "classification": CLASSIFICATION, "brainId": brain_id, "lane": LANE,
        "executionMode": EXECUTION_MODE, "experimental": True, "knowledgeState": "CANDIDATE", "authoritative": False, "customerEligible": False, "consumers": list(CONSUMERS), "forbiddenConsumers": list(FORBIDDEN_CONSUMERS),
        "candidateRelease": {k: release.get(k) for k in ("releaseId", "releaseDigest", "approvalStatus", "store") if release.get(k) is not None},
        "approvedPath": {k: approved_path.get(k) for k in ("status", "reason") if approved_path.get(k) is not None},
        "runAt": now_iso, "report": rep, "readinessCounts": counts, "lakes": lakes, "lakeCount": len(lakes), "outputDigest": digest,
        "retention": f"latest summary only; history keeps the last {HISTORY} runs; the full in-memory output is not stored (digest only)",
        "history": hist,
    }
    if errors:
        doc["errors"] = errors
    if deployment_version:
        doc["publishedBy"] = {"component": "brain-orchestrator", "deploymentVersion": deployment_version}
    return doc


def due(prev: dict | None, cadence_hours: float, now: dt.datetime) -> bool:
    """A shadow run is due when none ran yet or the last one is at least `cadence_hours` old."""
    last = (prev or {}).get("runAt")
    if not last:
        return True
    try:
        t = dt.datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    except ValueError:
        return True
    return (now - t).total_seconds() / 3600 >= float(cadence_hours)


def problems(doc: dict) -> list[str]:
    """Contract checks a writer runs before publishing (refuse rather than publish a mislabelled document)."""
    p = []
    if doc.get("schema") != SCHEMA or doc.get("classification") != CLASSIFICATION:
        p.append("not a brain-shadow-lane-v1 INTERNAL_EXPERIMENTAL document")
    if (doc.get("authoritative") is not False or doc.get("customerEligible") is not False or doc.get("lane") != LANE
            or doc.get("executionMode") != EXECUTION_MODE or doc.get("experimental") is not True):
        p.append("shadow output must be non-authoritative, non-customer, experimental, lane INTERNAL_EXPERIMENTAL, mode INTERNAL")
    if (doc.get("candidateRelease") or {}).get("approvalStatus") == "APPROVED":
        p.append("an APPROVED release belongs on the approved serving path, not in the shadow lane")
    for k, row in (doc.get("lakes") or {}).items():
        extra = set(row) - set(LAKE_FIELDS)
        if extra:
            p.append(f"lake {k}: fields outside the allowlist {sorted(extra)}")
    return p
