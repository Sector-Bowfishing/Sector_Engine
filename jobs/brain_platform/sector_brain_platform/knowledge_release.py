"""Packaged knowledge releases (Cortex 2.1 BR-11: approved persistent memory). Stdlib only; no network, no clock.

A Brain whose approved operational knowledge ships INSIDE its runtime image (configuration, catalogs, frozen evidence) declares it in ONE manifest,
`knowledge-release.json`, next to the runtime entry point:

    {"schemaVersion": "1.0.0", "brainId": "wind", "releaseId": "wind-knowledge-2026-10-20.1",
     "store": "PACKAGED_IN_IMAGE", "owner": "wind",
     "approval": {"status": "APPROVED" | "NOT_RECORDED", "record": "<repo path of the approval/certification record, or null>",
                  "scope": ["INTERNAL", "CALIBRATION", "CUSTOMER"] (optional subset), "customerEligible": false (optional)},
     "files": [{"path": "lakes.json", "sha256": "<hex>", "bytes": 1234}, ...],
     "releaseDigest": "sha256:<hex over the canonical file list>"}

`load_release()` verifies the manifest and every file on load. Anything missing, unreadable or mismatched raises KnowledgeReleaseError: the caller
stops (fail closed) and never falls back to research data, an unversioned file or a default. A release is immutable: changing a file means a new
releaseId and a regenerated manifest (tools/knowledge/build_release_manifest.py), reviewed like any other change.

Brains whose knowledge lives elsewhere keep their own verified loaders (Fish: the hash-verified private bundle; Lake: compiled reviewed bindings and
the fingerprinted presence release). This module does not replace them.
"""
from __future__ import annotations

import hashlib
import json
import os

MANIFEST = "knowledge-release.json"
SCHEMA_VERSION = "1.0.0"
STORES = ("PACKAGED_IN_IMAGE",)
APPROVAL_STATUSES = ("APPROVED", "NOT_RECORDED")
APPROVAL_SCOPES = ("INTERNAL", "CALIBRATION", "CUSTOMER")


class KnowledgeReleaseError(RuntimeError):
    """The approved knowledge release is missing, unreadable, incompatible or fails verification."""


def file_sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def release_digest(files: list[dict]) -> str:
    """Digest over the canonical (sorted) file list: path, sha256, bytes. Independent of manifest formatting."""
    canon = json.dumps(sorted(({"path": f["path"], "sha256": f["sha256"], "bytes": f["bytes"]} for f in files), key=lambda f: f["path"]),
                       sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canon.encode()).hexdigest()


def describe_files(base_dir: str, paths: list[str]) -> list[dict]:
    out = []
    for p in sorted(paths):
        full = os.path.join(base_dir, p)
        out.append({"path": p, "sha256": file_sha256(full), "bytes": os.path.getsize(full)})
    return out


def load_release(base_dir: str, brain_id: str) -> dict:
    """Verify the packaged release in `base_dir` and return {releaseId, releaseDigest, approvalStatus, approvalRecord, approvalScope, customerEligible, store, files}.
    approvalScope is None when the manifest declares no scope; customerEligible is True only when the manifest says so and the scope includes CUSTOMER.
    Raises KnowledgeReleaseError on any problem; the caller must not continue without approved memory."""
    mpath = os.path.join(base_dir, MANIFEST)
    try:
        with open(mpath, encoding="utf-8") as fh:
            m = json.load(fh)
    except FileNotFoundError as e:
        raise KnowledgeReleaseError(f"knowledge release manifest missing: {MANIFEST}") from e
    except (OSError, ValueError) as e:
        raise KnowledgeReleaseError(f"knowledge release manifest unreadable: {e}") from e
    if m.get("schemaVersion") != SCHEMA_VERSION:
        raise KnowledgeReleaseError(f"incompatible knowledge release schemaVersion {m.get('schemaVersion')!r} (loader reads {SCHEMA_VERSION})")
    if m.get("brainId") != brain_id:
        raise KnowledgeReleaseError(f"knowledge release belongs to {m.get('brainId')!r}, not {brain_id!r}")
    if m.get("store") not in STORES or not m.get("releaseId") or not isinstance(m.get("files"), list) or not m["files"]:
        raise KnowledgeReleaseError("knowledge release manifest is incomplete (store, releaseId, files)")
    approval = m.get("approval") or {}
    if approval.get("status") not in APPROVAL_STATUSES:
        raise KnowledgeReleaseError(f"knowledge release approval status {approval.get('status')!r} is not one of {APPROVAL_STATUSES}")
    if approval["status"] == "APPROVED" and not approval.get("record"):
        raise KnowledgeReleaseError("an APPROVED knowledge release must name its approval record")
    scope = approval.get("scope")
    if scope is not None and (not isinstance(scope, list) or not scope or any(x not in APPROVAL_SCOPES for x in scope)):
        raise KnowledgeReleaseError(f"knowledge release approval scope {scope!r} is not a non-empty subset of {APPROVAL_SCOPES}")
    if approval.get("customerEligible") is True and scope is not None and "CUSTOMER" not in scope:
        raise KnowledgeReleaseError("a knowledge release cannot be customer-eligible without CUSTOMER in its approval scope")
    for f in m["files"]:
        full = os.path.normpath(os.path.join(base_dir, f.get("path", "")))
        if not full.startswith(os.path.normpath(base_dir) + os.sep):
            raise KnowledgeReleaseError(f"knowledge release file escapes the release directory: {f.get('path')!r}")
        try:
            size, digest = os.path.getsize(full), file_sha256(full)
        except OSError as e:
            raise KnowledgeReleaseError(f"knowledge release file missing or unreadable: {f.get('path')}") from e
        if digest != f.get("sha256") or size != f.get("bytes"):
            raise KnowledgeReleaseError(f"knowledge release file fails verification (sha256/bytes): {f.get('path')}")
    if release_digest(m["files"]) != m.get("releaseDigest"):
        raise KnowledgeReleaseError("knowledge release digest does not match its file list")
    return {"releaseId": m["releaseId"], "releaseDigest": m["releaseDigest"], "store": m["store"], "owner": m.get("owner"),
            "approvalStatus": approval["status"], "approvalRecord": approval.get("record"), "approvalScope": scope,
            "customerEligible": approval.get("customerEligible") is True and scope is not None and "CUSTOMER" in scope, "files": [f["path"] for f in m["files"]]}


def lineage_triple(release: dict | None) -> tuple[str, str, str]:
    """(knowledgeRelease, manifestRef, manifestSha256) for a Publisher artifact lineage; NONE when the Brain has no packaged release."""
    if not release:
        return ("NONE", "NONE", "NONE")
    return (release["releaseId"], f"image:{MANIFEST}", release["releaseDigest"])         # Publisher format: sha256:<64 hex>
