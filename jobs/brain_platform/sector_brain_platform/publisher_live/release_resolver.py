"""P6: the release resolver. The shadow validator only checked that knowledgeRelease / manifestRef / manifestSha256 were well-formed; with a resolver it VERIFIES them.

`reader(manifest_ref) -> bytes | None` is injected: in production it reads the private release store with a read-only identity (not wired or enabled here); tests inject a
dict. Fail closed: an unreadable manifest, a hash that does not match, an unparsable manifest or a manifest that does not name the declared release is UNRESOLVED.
"""
from __future__ import annotations

import hashlib
import json

RELEASE_KEYS = ("researchVersion", "releaseId", "release", "knowledgeRelease")


class ManifestReleaseResolver:
    def __init__(self, reader):
        self._read = reader

    def __call__(self, knowledge_release: str, manifest_ref: str, manifest_sha256: str) -> bool:
        try:
            data = self._read(manifest_ref)
        except Exception:
            return False
        if not isinstance(data, (bytes, bytearray)):
            return False
        if "sha256:" + hashlib.sha256(bytes(data)).hexdigest() != manifest_sha256:
            return False
        try:
            doc = json.loads(data)
        except ValueError:
            return False
        named = [doc.get(k) for k in RELEASE_KEYS if isinstance(doc, dict) and k in doc]
        return bool(named) and all(n == knowledge_release for n in named)
