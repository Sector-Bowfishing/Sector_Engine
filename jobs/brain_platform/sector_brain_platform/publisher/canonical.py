"""Canonical representation and fingerprints (BRAIN_IDENTITY_AND_LINEAGE_V1 section 2, "Fingerprint rules").

outputFingerprint = sha256 of the canonical JSON (sorted keys, UTF-8, no insignificant whitespace) of the MATERIAL content, volatile
fields excluded. The Publisher RECOMPUTES it here; it never trusts the value a Brain declares.
"""
from __future__ import annotations

import hashlib
import json

#: The shared default volatile list (lineage doc section 2). A schema may ADD fields (SchemaSpec.volatile_extra); it can never remove these.
DEFAULT_VOLATILE = frozenset({"generatedAt", "publishedAt", "checkedAt", "ageHours", "durationMs"})
FLOAT_DIGITS = 9           # same float-noise tolerance as the platform's input fingerprints (fingerprint.py)


def _strip(o, volatile):
    if isinstance(o, dict):
        return {k: _strip(v, volatile) for k, v in sorted(o.items()) if k not in volatile}
    if isinstance(o, (list, tuple)):
        return [_strip(v, volatile) for v in o]
    if isinstance(o, float):
        return round(o, FLOAT_DIGITS)
    return o


def canonical_bytes(obj) -> bytes:
    """Canonical JSON bytes. Raises ValueError on NaN/Infinity and TypeError on non-JSON types (no `default=str` coercion)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def material(brain_id: str, artifact_schema: str, mutations: list[dict], extra_volatile=()) -> dict:
    """The material content of an artifact: identity of the scope plus its mutations (order-independent), volatile fields removed."""
    volatile = DEFAULT_VOLATILE | frozenset(extra_volatile)
    ms = []
    for m in sorted(mutations, key=lambda m: m["path"]):
        e = {"op": m["op"], "path": m["path"]}
        if m["op"] == "SET":
            e["value"] = _strip(m.get("value"), volatile)
        ms.append(e)
    return {"brainId": brain_id, "artifactSchema": artifact_schema, "mutations": ms}


def output_fingerprint(brain_id: str, artifact_schema: str, mutations: list[dict], extra_volatile=()) -> str:
    return sha256_ref(canonical_bytes(material(brain_id, artifact_schema, mutations, extra_volatile)))
