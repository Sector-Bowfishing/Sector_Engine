"""Artifact + publication history storage (CERT-3: ONE private, versioned bucket with prefixes artifacts/ publishes/ scores/ exports/).

Only the INTERFACE and local implementations exist here. No GCS adapter is shipped and no bucket is created: that needs Michael's separate
approval (see PUBLISHER_V1_CUTOVER_REQUIREMENTS.md). The ObjectStore contract mirrors GCS semantics on purpose:
  - every put creates a new GENERATION; older generations stay readable (bucket versioning);
  - `if_generation_match=0` is create-only (immutable objects: artifacts, publication records);
  - `if_generation_match=N` is an optimistic-concurrency overwrite (the per-scope head pointer).

Layout
  artifacts/{brainId}/{artifactId}/artifact.json              immutable   the artifact as the Brain produced it (rollback source)
  publishes/{brainId}/{publishId}/record.json                 immutable   one publication record (also SKIP / REJECTED outcomes)
  publishes/{brainId}/_heads/{artifactSchema}/{scope}.json    versioned   pointer to the latest baseline record for that scope
  scores/ , exports/                                          reserved prefixes (score history, RTDB exports); not written by Publisher V1
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .canonical import canonical_bytes
from .model import DEFAULT_SCOPE
from .refs import artifact_location

PREFIXES = ("artifacts/", "publishes/", "scores/", "exports/")
_SEG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._@-]*")


class StorageError(RuntimeError):
    pass


class PreconditionFailed(StorageError):
    pass


class ArtifactConflict(StorageError):
    pass


def check_key(key: str) -> str:
    if not isinstance(key, str) or not key.startswith(PREFIXES):
        raise StorageError(f"key must start with one of {PREFIXES}: {key!r}")
    for seg in key.split("/"):
        if not _SEG.fullmatch(seg) or seg in (".", ".."):
            raise StorageError(f"illegal key segment {seg!r} in {key!r}")
    return key


class MemoryObjectStore:
    """Versioned in-memory object store (test double with GCS generation semantics)."""

    def __init__(self):
        self._objs: dict[str, list[bytes]] = {}

    def put(self, key: str, data: bytes, *, if_generation_match: int | None = None) -> int:
        check_key(key)
        cur = len(self._objs.get(key, ()))
        if if_generation_match is not None and if_generation_match != cur:
            raise PreconditionFailed(f"{key}: generation is {cur}, expected {if_generation_match}")
        self._objs.setdefault(key, []).append(bytes(data))
        return cur + 1

    def get(self, key: str, generation: int | None = None) -> bytes | None:
        gens = self._objs.get(check_key(key))
        if not gens:
            return None
        if generation is None:
            return gens[-1]
        return gens[generation - 1] if 1 <= generation <= len(gens) else None

    def generation(self, key: str) -> int:
        return len(self._objs.get(check_key(key), ()))

    def list(self, prefix: str) -> list[str]:
        return sorted(k for k in self._objs if k.startswith(prefix))


class LocalDirObjectStore(MemoryObjectStore):
    """Same semantics persisted under a directory: <root>/<key>.g<N>. For tests and local shadow runs only; never a production store."""

    def __init__(self, root):
        super().__init__()
        self.root = Path(root)
        for p in sorted(self.root.rglob("*.g*")) if self.root.exists() else []:
            rel = p.relative_to(self.root).as_posix()
            key, _, g = rel.rpartition(".g")
            self._objs.setdefault(key, [])
            while len(self._objs[key]) < int(g):
                self._objs[key].append(b"")
            self._objs[key][int(g) - 1] = p.read_bytes()

    def put(self, key, data, *, if_generation_match=None):
        gen = super().put(key, data, if_generation_match=if_generation_match)
        dest = self.root / f"{key}.g{gen}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bytes(data))
        return gen


def _seg(v: str, what: str) -> str:
    if not isinstance(v, str) or not _SEG.fullmatch(v):
        raise StorageError(f"illegal {what} {v!r}")
    return v


def artifact_key(brain_id: str, artifact_id: str) -> str:
    _seg(brain_id, "brainId"), _seg(artifact_id.replace(":", "-"), "artifactId")
    return artifact_location(brain_id, artifact_id)


def publish_key(brain_id: str, publish_id: str) -> str:
    return f"publishes/{_seg(brain_id, 'brainId')}/{_seg(publish_id, 'publishId')}/record.json"


def head_key(brain_id: str, schema: str, scope: str = DEFAULT_SCOPE) -> str:
    return f"publishes/{_seg(brain_id, 'brainId')}/_heads/{_seg(schema, 'artifactSchema')}/{_seg(scope, 'scope')}.json"


class PublishHistory:
    """Artifact / publication-record / head-pointer operations on top of an ObjectStore."""

    def __init__(self, store: MemoryObjectStore):
        self.store = store

    # artifacts (immutable)
    def put_artifact(self, brain_id: str, artifact_id: str, artifact: dict) -> str:
        key, data = artifact_key(brain_id, artifact_id), canonical_bytes(artifact)
        try:
            self.store.put(key, data, if_generation_match=0)
        except PreconditionFailed:
            if self.store.get(key) != data:
                raise ArtifactConflict(f"artifact {artifact_id} already exists with different content") from None
        return key

    def artifact_conflicts(self, brain_id: str, artifact_id: str, artifact: dict) -> bool:
        cur = self.store.get(artifact_key(brain_id, artifact_id))
        return cur is not None and cur != canonical_bytes(artifact)

    def read_artifact_bytes(self, brain_id: str, artifact_id: str) -> bytes | None:
        return self.store.get(artifact_key(brain_id, artifact_id))

    def get_artifact(self, brain_id: str, artifact_id: str) -> dict | None:
        b = self.store.get(artifact_key(brain_id, artifact_id))
        return json.loads(b) if b else None

    # publication records (immutable)
    def append_record(self, record: dict) -> str:
        key = publish_key(record["brainId"], record["publishId"])
        self.store.put(key, canonical_bytes(record), if_generation_match=0)
        return key

    def get_record(self, brain_id: str, publish_id: str) -> dict | None:
        b = self.store.get(publish_key(brain_id, publish_id))
        return json.loads(b) if b else None

    def records(self, brain_id: str) -> list[dict]:
        pre = f"publishes/{_seg(brain_id, 'brainId')}/"
        recs = [json.loads(self.store.get(k)) for k in self.store.list(pre) if k.endswith("/record.json")]
        return sorted(recs, key=lambda r: (r.get("evaluatedAt", ""), r["publishId"]))

    # head pointer (versioned; optimistic concurrency)
    def head(self, brain_id: str, schema: str, scope: str = DEFAULT_SCOPE) -> dict | None:
        b = self.store.get(head_key(brain_id, schema, scope))
        return json.loads(b) if b else None

    def advance_head(self, record: dict) -> int:
        """Point the scope's head at `record` (a SHADOW_READY record). Fails if another writer advanced it since `record` was planned."""
        key = head_key(record["brainId"], record["artifactSchema"], record["scope"])
        expect = record["headGeneration"]
        ptr = {k: record[k] for k in ("publishId", "artifactId", "outputFingerprint", "generatedAt", "evaluatedAt", "previousPublishId") if k in record}
        return self.store.put(key, canonical_bytes(ptr), if_generation_match=expect)

    def head_generation(self, brain_id: str, schema: str, scope: str = DEFAULT_SCOPE) -> int:
        return self.store.generation(head_key(brain_id, schema, scope))

    def head_history(self, brain_id: str, schema: str, scope: str = DEFAULT_SCOPE) -> list[dict]:
        key = head_key(brain_id, schema, scope)
        return [json.loads(self.store.get(key, g)) for g in range(1, self.store.generation(key) + 1)]

    # rollback
    def rollback_reference(self, brain_id: str, publish_id: str) -> dict | None:
        """What would restore the state BEFORE `publish_id`: the previous baseline record and its immutable artifact. None for a first publication."""
        rec = self.get_record(brain_id, publish_id)
        if rec is None:
            raise StorageError(f"no publication record {publish_id}")
        prev_id = rec.get("previousPublishId")
        prev = self.get_record(brain_id, prev_id) if prev_id else None
        if prev is None:
            return None
        return {"restorePublishId": prev["publishId"], "artifactId": prev["artifactId"], "artifactKey": artifact_key(brain_id, prev["artifactId"]),
                "artifactStored": self.store.get(artifact_key(brain_id, prev["artifactId"])) is not None,
                "outputFingerprint": prev["outputFingerprint"], "fromPublishId": publish_id}


class AccessDenied(StorageError):
    pass


class ScopedObjectStore:
    """A view of an ObjectStore with the TARGET access model applied in code (IAM enforces the same later; this is defence in depth, not the control).

    There is no delete method at all: immutable history cannot be removed through this interface. `create` prefixes allow create-only puts
    (`if_generation_match=0`); `overwrite` prefixes additionally allow generation-matched overwrites (the versioned head pointer)."""

    def __init__(self, store, *, read=(), create=(), overwrite=()):
        self._s, self._read, self._create, self._over = store, tuple(read), tuple(create), tuple(overwrite)

    def _ok(self, key, prefixes, what):
        check_key(key)
        if not key.startswith(prefixes):
            raise AccessDenied(f"{what} denied on {key}")

    def put(self, key, data, *, if_generation_match=None):
        if if_generation_match == 0:
            self._ok(key, self._create, "create")
        else:
            self._ok(key, self._over, "overwrite")
        return self._s.put(key, data, if_generation_match=if_generation_match)

    def get(self, key, generation=None):
        self._ok(key, self._read, "read")
        return self._s.get(key, generation)

    def generation(self, key):
        self._ok(key, self._read, "read")
        return self._s.generation(key)

    def list(self, prefix):
        if not prefix.startswith(self._read):
            raise AccessDenied(f"list denied on {prefix!r}")
        return self._s.list(prefix)


def brain_view(store, brain_id: str) -> ScopedObjectStore:
    """A specialist Brain: create-only under its OWN artifact prefix, read only that prefix. Nothing else."""
    pre = f"artifacts/{_seg(brain_id, 'brainId')}/"
    return ScopedObjectStore(store, read=(pre,), create=(pre,))


def publisher_view(store, *, may_store_artifacts: bool = False) -> ScopedObjectStore:
    """The Publisher: read artifacts and history, create publication/history records and move the versioned heads. It does not write artifacts/
    (the Brain did) unless `may_store_artifacts` is set for the local direct-evaluate convenience path."""
    return ScopedObjectStore(store, read=("artifacts/", "publishes/"), create=("publishes/",) + (("artifacts/",) if may_store_artifacts else ()),
                             overwrite=("publishes/",))
