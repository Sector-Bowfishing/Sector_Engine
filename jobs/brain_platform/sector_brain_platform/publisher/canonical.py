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


#: Version of the semantic-fingerprint algorithm. A baseline made under a different algorithm is never treated as "equal" (it compares as changed).
ALGORITHM = "sector-semantic-fingerprint-v2"


def material(brain_id: str, artifact_schema: str, mutations: list[dict], extra_volatile=(), volatile_paths=()) -> dict:
    """The SEMANTIC material of one section: its identity plus its mutations (order-independent), with
      * volatile KEYS removed at any depth inside values (shared defaults + the schema's volatile contract), and
      * SET mutations whose path matches a volatile PATH family left out entirely (a volatile scalar child addressed by path).
    DELETE operations are always material: a volatile contract can never hide a deletion.
    Excluded by construction: lineage (generatedAt, executionId, artifactId, codeVersion, ...), freshness, the artifact hash, and all Publisher metadata."""
    volatile = DEFAULT_VOLATILE | frozenset(extra_volatile)
    ms = []
    for m in sorted(mutations, key=lambda m: m["path"]):
        if m["op"] == "SET" and any(f.match(m["path"]) for f in volatile_paths):
            continue
        e = {"op": m["op"], "path": m["path"]}
        if m["op"] == "SET":
            e["value"] = _strip(m.get("value"), volatile)
        ms.append(e)
    return {"algorithm": ALGORITHM, "brainId": brain_id, "artifactSchema": artifact_schema, "mutations": ms}


def output_fingerprint(brain_id: str, artifact_schema: str, mutations: list[dict], extra_volatile=(), volatile_paths=()) -> str:
    return sha256_ref(canonical_bytes(material(brain_id, artifact_schema, mutations, extra_volatile, volatile_paths)))


def bundle_fingerprint(brain_id: str, bundle_schema: str, sections: list[tuple]) -> str:
    """Fingerprint of a multi-section artifact: the section fingerprints (schema, scope, fp) in canonical order. Same sections + same section content = same hash."""
    body = {"algorithm": ALGORITHM, "brainId": brain_id, "artifactSchema": bundle_schema,
            "sections": [{"artifactSchema": sc, "scope": scope, "outputFingerprint": fp} for sc, scope, fp in sorted(sections)]}
    return sha256_ref(canonical_bytes(body))
