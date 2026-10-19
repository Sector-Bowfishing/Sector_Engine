"""Atomic apply, manifest-last ordering and authoritative readback.

ATOMICITY MODEL
  * Normal case: the whole plan (artifact paths + projections + the publication record) is ONE multi-location RTDB update: it lands entirely or not at all.
  * Plans above `max_update_bytes` are applied in chunks, MANIFEST-LAST: every data chunk first; the publication record (the authoritative marker: artifactId,
    status COMPLETE) travels ONLY in the final chunk. Before the first chunk a small `publication/pending` marker records the in-flight artifact. A failure at any
    point before the final chunk leaves `publication.artifactId` (and `status`) of the PREVIOUS release untouched, so the previous release stays authoritative;
    the data paths written so far are non-authoritative and the same artifact can be re-applied (idempotent) to finish.
"""
from __future__ import annotations

import json

from ..publisher.canonical import canonical_bytes
from .model import COMPLETE, RtdbAmbiguousFailure


def _norm(o):
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_norm(v) for v in o]
    if isinstance(o, float) and o == int(o):
        return int(o)
    return o


def canonical_equal(a, b) -> bool:
    return canonical_bytes(_norm(a)) == canonical_bytes(_norm(b))


def chunk_updates(updates: dict, pub_key: str, max_bytes: int) -> list:
    """Split a plan into chunks of at most `max_bytes` (a single key larger than the limit gets its own chunk). The publication record is held back and
    returned as the LAST chunk on its own: manifest-last."""
    data = {k: v for k, v in sorted(updates.items()) if k != pub_key}
    chunks, cur, size = [], {}, 0
    for k, v in data.items():
        n = len(canonical_bytes({k: v}))
        if cur and size + n > max_bytes:
            chunks.append(cur)
            cur, size = {}, 0
        cur[k] = v
        size += n
    if cur:
        chunks.append(cur)
    return chunks + [{pub_key: updates[pub_key]}]


def apply_plan(rtdb, updates: dict, pub_key: str, *, max_update_bytes: int, pending_marker: dict):
    """-> ('SINGLE'|'CHUNKED', n_calls). Raises Rtdb*Failure from the client unchanged; the caller decides recovery by readback."""
    if len(canonical_bytes(updates)) <= max_update_bytes:
        rtdb.update(updates)
        return "SINGLE", 1
    chunks = chunk_updates(updates, pub_key, max_update_bytes)
    rtdb.update({f"{pub_key}/pending": pending_marker})       # in-flight marker; the previous artifactId/status are untouched
    calls = 1
    for ch in chunks:
        rtdb.update(ch)                                       # the final chunk replaces the whole publication node: marker + pending gone, new release authoritative
        calls += 1
    return "CHUNKED", calls


def readback(rtdb, expected: dict) -> list:
    """Authoritative read of every planned key. Returns the keys whose live value differs from the plan (empty = verified)."""
    bad = []
    for k, want in sorted(expected.items()):
        have = rtdb.get(k)
        if (want is None and have is not None) or (want is not None and not canonical_equal(have, want)):
            bad.append(k)
    return bad


def is_ambiguous(e: Exception) -> bool:
    return isinstance(e, RtdbAmbiguousFailure)
