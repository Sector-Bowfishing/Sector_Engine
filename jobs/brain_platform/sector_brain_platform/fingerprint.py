"""Input fingerprints (docs/brains/platform/EXECUTION_MODEL.md section 5).

A fingerprint is a hash of the MATERIAL inputs of a Brain run. Same fingerprint => the run would produce the same state => SKIP.
Volatile, non-semantic fields never enter it. Brains choose their own ingredients; the mechanics are shared.
"""
from __future__ import annotations

import hashlib
import json

# Keys that change on every run without changing meaning. Excluded at any depth.
VOLATILE_KEYS = frozenset({"generatedAt", "ageHours", "inputAgeHours", "requestedAt", "requestTimestamp", "evaluatedAt", "updatedAt",
                           "scoreUpdatedAt", "rolledUpAt", "summarizedAt", "syncedAt", "fetchedAt", "lastRun", "now", "nextCheckAt",
                           "freshUntil", "refreshReason", "durationMs", "runId", "executionId"})


def _strip(o, volatile):
    if isinstance(o, dict):
        return {k: _strip(v, volatile) for k, v in sorted(o.items()) if k not in volatile}
    if isinstance(o, (list, tuple)):
        return [_strip(v, volatile) for v in o]
    if isinstance(o, float):
        return round(o, 9)
    return o


def fingerprint(material: dict, extra_volatile=()) -> str:
    """Stable 16-hex digest of `material` with volatile keys removed. Key order and tiny float noise do not matter."""
    body = _strip(material, VOLATILE_KEYS | set(extra_volatile))
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()[:16]


def decide(material: dict, previous: str | None, extra_volatile=()) -> dict:
    """{action: RUN|SKIP, fingerprint, reason}. No previous fingerprint = RUN (first run); same fingerprint = SKIP."""
    fp = fingerprint(material, extra_volatile)
    if previous is None:
        return {"action": "RUN", "fingerprint": fp, "reason": "no previous fingerprint"}
    if previous == fp:
        return {"action": "SKIP", "fingerprint": fp, "reason": "no material input changed"}
    return {"action": "RUN", "fingerprint": fp, "reason": "material input changed"}
