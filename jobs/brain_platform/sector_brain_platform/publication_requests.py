"""Publication requests: the hand-off from the Orchestrator to the recurring Publisher job (Cortex 3.1 PL-19, FD-15). LOCAL contract; nothing here is wired into a cycle.

The Orchestrator verifies a Brain's sealed artifact and records a REQUEST under its own prefix of the private artifact store:

    exports/orchestrator/publication-requests/{brainId}/{artifactId}.json      (create-only; one per artifact; schema sector-publication-request-v1)

The recurring Publisher job (jobs/brain-publisher/publish_job.py, its own identity) READS requests, publishes each through the existing LivePublisher and leaves the outcome in the
Publisher's immutable history (`publishes/{brainId}/{publishId}/record.json`), which the Orchestrator already imports (`PublicationCoordinator.import_publisher_history`).
Neither side gains a write path into the other's prefix: the Orchestrator writes requests only; the Publisher job writes `publishes/` only.

Rules (tested): a request carries a reference, never content or a database path; a request is accepted only for a Brain the reviewed cutover document marks CENTRAL with an
approvalRef that equals the request's; malformed or foreign requests are reported, never published; an artifact whose stored digest differs from the request is never published.
"""
from __future__ import annotations

import json

from .publisher.canonical import canonical_bytes, sha256_ref
from .publisher.model import Rejected
from .publisher.refs import ArtifactRef, artifact_location
from .publisher.storage import ScopedObjectStore

SCHEMA = "sector-publication-request-v1"
PREFIX = "exports/orchestrator/publication-requests/"
LIVE_MODE = "LIVE"                 # the live package's LIVE_MODE, restated: platform modules never import that package (boundary test); the job tests pin equality
FINAL_NOT_APPLIED = ("SKIP", "REJECTED", "FAILED_VALIDATION")      # live-mode records the Publisher keeps for a decided artifact that changed nothing
FIELDS = ("schema", "brainId", "artifactId", "location", "sha256", "executionId", "artifactSchema", "approvalRef", "requestedAt", "runId")


def request_key(brain_id: str, artifact_id: str) -> str:
    return f"{PREFIX}{brain_id}/{artifact_id.replace(':', '-')}.json"


def build_request(ref: ArtifactRef, *, approval_ref: str, requested_at: str, run_id: str) -> dict:
    ref.validate()
    if not (isinstance(approval_ref, str) and approval_ref.strip()):
        raise ValueError("a publication request needs the Brain's cutover approvalRef")
    return {"schema": SCHEMA, "brainId": ref.brain_id, "artifactId": ref.artifact_id, "location": ref.location, "sha256": ref.sha256, "executionId": ref.execution_id,
            "artifactSchema": ref.expected_schema, "approvalRef": approval_ref, "requestedAt": requested_at, "runId": run_id}


def write_request(orchestrator_store, request: dict) -> tuple[str, bool]:
    """Create-only. -> (key, created). An existing identical request is idempotent (False); a different request for the same artifact is an error (never overwritten)."""
    key = request_key(request["brainId"], request["artifactId"])
    have = orchestrator_store.get(key)
    if have is not None:
        if json.loads(have) != request:
            raise ValueError(f"{key} already holds a different request")
        return key, False
    orchestrator_store.put(key, canonical_bytes(request), if_generation_match=0)
    return key, True


def publisher_job_view(store) -> ScopedObjectStore:
    """The recurring Publisher job: the Publisher's own view (read artifacts/ and publishes/, write publishes/ only) plus READ of the request prefix. It can create nothing under
    artifacts/ or exports/ and cannot touch the Orchestrator's ledger."""
    return ScopedObjectStore(store, read=("artifacts/", "publishes/", PREFIX), create=("publishes/",), overwrite=("publishes/",))


def parse_request(raw: bytes | None, key: str, cutover: dict) -> tuple[ArtifactRef | None, dict | None]:
    """-> (ref, None) for an acceptable request, else (None, problem). `cutover` is publication_stage.load_cutover()[0]."""
    def problem(kind, why):
        return None, {"key": key, "kind": kind, "why": why}
    try:
        req = json.loads(raw) if raw is not None else None
    except ValueError:
        return problem("REQUEST_UNREADABLE", "not JSON")
    if not isinstance(req, dict) or req.get("schema") != SCHEMA or set(req) != set(FIELDS):
        return problem("REQUEST_SCHEMA", f"expected {SCHEMA} with exactly {list(FIELDS)}")
    if key != request_key(req["brainId"], req["artifactId"]):
        return problem("REQUEST_KEY", "stored under a key that does not match its Brain and artifact")
    entry = cutover.get(req["brainId"]) or {}
    if entry.get("state") != "CENTRAL":
        return problem("REQUEST_NOT_CENTRAL", f"{req['brainId']} is not CENTRAL in the reviewed cutover document")
    if entry.get("approvalRef") != req["approvalRef"]:
        return problem("REQUEST_APPROVAL_MISMATCH", "approvalRef differs from the cutover document")
    ref = ArtifactRef(req["brainId"], req["artifactId"], req["location"], req["sha256"], req["executionId"], req["artifactSchema"])
    try:
        ref.validate()
    except Rejected as e:
        return problem("REQUEST_REF_INVALID", str(e)[:200])
    if ref.location != artifact_location(ref.brain_id, ref.artifact_id):
        return problem("REQUEST_REF_INVALID", "non-canonical location")
    return ref, None


def pending(store, brain_id: str, cutover: dict) -> tuple[list, list]:
    """Requests for one Brain that the Publisher's history does not yet show as decided. -> ([(requestedAt, ArtifactRef)], problems), oldest first."""
    decided = set()
    for k in store.list(f"publishes/{brain_id}/"):
        if k.endswith("/record.json"):
            try:
                r = json.loads(store.get(k))
            except (TypeError, ValueError):
                continue
            if r.get("mode") != LIVE_MODE:
                continue                                           # a shadow record never decides a live request
            if (r.get("result") == "PUBLISHED" and r.get("live") and r.get("status") == "COMPLETE") or r.get("result") in FINAL_NOT_APPLIED:
                decided.add(r.get("artifactId"))
    out, problems = [], []
    for k in sorted(store.list(f"{PREFIX}{brain_id}/")):
        raw = store.get(k)
        ref, prob = parse_request(raw, k, cutover)
        if prob:
            problems.append(prob)
            continue
        if ref.artifact_id in decided:
            continue
        data = store.get(ref.location)
        if data is None or sha256_ref(data) != ref.sha256:
            problems.append({"key": k, "kind": "ARTIFACT_DIGEST_MISMATCH" if data is not None else "ARTIFACT_MISSING", "why": "the stored artifact is not the requested one"})
            continue
        out.append((json.loads(raw)["requestedAt"], ref))
    return sorted(out, key=lambda x: x[0]), problems
