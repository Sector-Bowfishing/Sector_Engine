"""P4: baseline reconciliation. The shadow baseline is the last SHADOW_READY, NOT live. Before the first live publish of a scope an operator reads live (GET
only), diffs it against the artifact's plan and records a DELIBERATE acknowledgement (approval reference, diff hash, the live artifact id). The first publish
after that is therefore a reviewed change, never an accidental full rewrite. Afterwards the live head carries `live: true` and no acknowledgement is needed.
"""
from __future__ import annotations

import json

from ..publisher.canonical import canonical_bytes, sha256_ref
from ..publisher.storage import PreconditionFailed, _seg
from .apply import canonical_equal


def ack_key(brain_id: str, schema: str, scope: str) -> str:
    return f"publishes/{_seg(brain_id, 'brainId')}/_baseline/{_seg(schema, 'artifactSchema')}/{_seg(scope, 'scope')}.json"


def diff_against_live(rtdb, brain_id: str, updates: dict) -> dict:
    """GET-only comparison of a plan's keys with what is live. `unplannedLive`: children present live under the Brain's registry/health nodes that the plan
    does not write (stale children persist unless a typed DELETE removes them)."""
    equal, differing, missing = [], [], []
    for k, want in sorted(updates.items()):
        have = rtdb.get(k)
        if want is None:
            (equal if have is None else differing).append(k)
        elif have is None:
            missing.append(k)
        elif canonical_equal(have, want):
            equal.append(k)
        else:
            differing.append(k)
    unplanned = []
    for node in (f"brains/{brain_id}", f"health/brains/{brain_id}"):
        live = rtdb.get(node)
        if isinstance(live, dict):
            planned_children = {k.split("/")[-1] for k in updates if k.startswith(node + "/") and k.count("/") == node.count("/") + 1}
            whole_planned = node in updates
            unplanned += sorted(f"{node}/{c}" for c in live if c not in planned_children and not whole_planned and c not in ("publication", "certification"))
    return {"equal": equal, "differing": differing, "missingLive": missing, "unplannedLive": unplanned,
            "diffSha256": sha256_ref(canonical_bytes({"differing": differing, "missingLive": missing, "unplannedLive": unplanned}))}


def acknowledge(store, brain_id: str, schema: str, scope: str, *, diff: dict, approval_ref: str, now: str, live_artifact_id: str | None = None) -> str:
    if not (isinstance(approval_ref, str) and approval_ref.strip()):
        raise ValueError("a baseline acknowledgement needs an approval reference")
    key = ack_key(brain_id, schema, scope)
    body = {"approvalRef": approval_ref, "acknowledgedAt": now, "diffSha256": diff["diffSha256"], "differing": len(diff["differing"]),
            "missingLive": len(diff["missingLive"]), "unplannedLive": len(diff["unplannedLive"]), "liveArtifactId": live_artifact_id}
    try:
        store.put(key, canonical_bytes(body), if_generation_match=store.generation(key))
    except PreconditionFailed:
        raise
    return key


def acknowledgement(store, brain_id: str, schema: str, scope: str):
    b = store.get(ack_key(brain_id, schema, scope))
    return json.loads(b) if b else None


def is_reconciled(store, brain_id: str, schema: str, scope: str, head) -> bool:
    return bool(head and head.get("live")) or acknowledgement(store, brain_id, schema, scope) is not None
