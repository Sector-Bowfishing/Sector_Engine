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


class PackagedReleaseResolver:
    """Resolves the lineage of a Brain whose approved knowledge ships inside its image (`knowledge-release.json`, Cortex BR-11). The lineage triple is
    (releaseId, `image:knowledge-release.json`, releaseDigest); the digest is over the manifest's canonical FILE LIST, not over the manifest bytes, so the byte-hash resolver above cannot
    verify it. This one runs the full packaged-release verification (every file's sha256 and size, the file-list digest) and then requires that the artifact declares exactly that
    release, and that the release is APPROVED. Fail closed: any problem is False."""

    def __init__(self, base_dir: str, brain_id: str, *, require_approved: bool = True):
        self._dir, self._brain, self._need_approved = base_dir, brain_id, require_approved

    def __call__(self, knowledge_release: str, manifest_ref: str, manifest_sha256: str) -> bool:
        from ..knowledge_release import MANIFEST, KnowledgeReleaseError, load_release
        try:
            rel = load_release(self._dir, self._brain)
        except (KnowledgeReleaseError, OSError, ValueError):
            return False
        if manifest_ref != f"image:{MANIFEST}" or rel["releaseId"] != knowledge_release or rel["releaseDigest"] != manifest_sha256:
            return False
        return rel["approvalStatus"] == "APPROVED" or not self._need_approved
