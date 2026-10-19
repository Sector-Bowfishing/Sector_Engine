"""S1 — the score trigger. The Platform scorer stays authoritative and separate; the Publisher never scores and never calls it.

A publication is *observable* as `/brains/<id>/publication` = {artifactId, status, ...} written by the Publisher in the SAME atomic update as the data.
The Orchestrator already decides "did a Brain change?" by comparing a per-Brain token with the one it stored last cycle (`lastSeen`). This module defines that
token so a COMPLETE publication with a new artifactId changes it, while a SKIP (no write), a failed or PARTIAL publication (publication.artifactId unchanged,
or status != COMPLETE) does not. Brains with no publication node keep exactly today's token (lastSuccessfulRun): behaviour is unchanged until a Publisher
publishes, and a Brain's change moves ONLY that Brain's token, so no other Brain's score path is triggered.
"""
from __future__ import annotations


def seen_token(brain_node):
    """The change token for one `/brains/<id>` node (legacy: lastSuccessfulRun; plus the COMPLETE publication's artifactId when present)."""
    node = brain_node if isinstance(brain_node, dict) else {}
    legacy = node.get("lastSuccessfulRun")
    pub = node.get("publication")
    if isinstance(pub, dict) and pub.get("status") == "COMPLETE" and isinstance(pub.get("artifactId"), str):
        return f"{legacy}|pub:{pub['artifactId']}"
    return legacy


def changed_brains(brains: dict, last_seen: dict) -> list:
    """Brains whose token differs from the one recorded last cycle (sorted). `brains` is the live `/brains` node."""
    brains = brains or {}
    last_seen = last_seen or {}
    return sorted(b for b in brains if seen_token(brains[b]) != last_seen.get(b))
