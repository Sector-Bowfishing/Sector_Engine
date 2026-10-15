"""The atomic multi-location update plan.

ONE deterministic dict {rtdb key -> value} holding every artifact path plus the publication record. Built entirely in memory before anything is
persisted or handed to a sink, so a failure while building leaves no partial state. A `None` (RTDB delete) appears ONLY for an explicit DELETE
mutation; the builder asserts this invariant itself rather than trusting the validator.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical import canonical_bytes, sha256_ref
from .paths import to_rtdb_key


class PlanInvariantError(AssertionError):
    pass


@dataclass(frozen=True)
class UpdatePlan:
    brain_id: str
    updates: dict                     # rtdb key -> value | None (explicit delete); sorted by key
    deletes: tuple                    # keys deleted by explicit DELETE operations
    artifact_patch_sha256: str        # hash of the artifact's own paths (excludes the publication record)
    update_sha256: str                # hash of the whole update, publication record included
    path_count: int                   # artifact paths (excludes the publication record)
    patch_bytes: int
    publication_key: str

    def canonical(self) -> bytes:
        return canonical_bytes(self.updates)


def artifact_patch(mutations: list[dict]) -> dict:
    patch = {}
    for m in sorted(mutations, key=lambda m: m["path"]):
        patch[to_rtdb_key(m["path"])] = m["value"] if m["op"] == "SET" else None
    return patch


def path_fingerprints(mutations: list[dict]) -> dict:
    return {to_rtdb_key(m["path"]): (sha256_ref(canonical_bytes(m["value"])) if m["op"] == "SET" else "DELETE")
            for m in sorted(mutations, key=lambda m: m["path"])}


def rtdb_record(record: dict):
    """The record as RTDB would keep it: None and empty containers dropped (they would be implicit deletes / vanish on write)."""
    if isinstance(record, dict):
        return {k: v2 for k, v in record.items() if (v2 := rtdb_record(v)) not in (None, {}, [])}
    if isinstance(record, list):
        return [x for x in (rtdb_record(v) for v in record) if x not in (None, {}, [])]
    return record


def build_update_plan(brain_id: str, mutations: list[dict], record: dict) -> UpdatePlan:
    patch = artifact_patch(mutations)
    explicit = {to_rtdb_key(m["path"]) for m in mutations if m["op"] == "DELETE"}
    stray = sorted(k for k, v in patch.items() if v is None and k not in explicit)
    if stray:
        raise PlanInvariantError(f"null in the patch without an explicit DELETE: {stray}")
    pub_key = f"brains/{brain_id}/publication"
    if pub_key in patch or any(k.startswith(pub_key + "/") or pub_key.startswith(k + "/") for k in patch):
        raise PlanInvariantError("artifact patch collides with the Publisher-owned publication record")
    updates = dict(sorted({**patch, pub_key: rtdb_record(record)}.items()))
    return UpdatePlan(brain_id, updates, tuple(sorted(explicit)), sha256_ref(canonical_bytes(patch)), sha256_ref(canonical_bytes(updates)),
                      len(patch), len(canonical_bytes(patch)), pub_key)
