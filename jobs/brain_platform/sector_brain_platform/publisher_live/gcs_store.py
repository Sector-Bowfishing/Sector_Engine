"""P2: a GCS ObjectStore adapter with the SAME contract as storage.MemoryObjectStore (create-only via generation 0, optimistic overwrite via the last seen
generation, immutable history through bucket versioning). It takes an injected bucket object (the google.cloud.storage Bucket API subset), so the module has
no hard dependency on the cloud library and tests use FakeBucket.

Differences from the in-memory store, by design: GCS generations are opaque large integers (the memory store counts); `generation(key)` returns 0 when the
object does not exist. There is NO delete method: the adapter cannot remove history. Creating the real bucket and its IAM needs separate approval.
"""
from __future__ import annotations

from ..publisher.storage import PreconditionFailed, check_key


class GcsPreconditionFailed(Exception):
    """Raised by a bucket client when if_generation_match fails (stands in for google.api_core.exceptions.PreconditionFailed)."""


class GcsObjectStore:
    def __init__(self, bucket, *, precondition_errors=(GcsPreconditionFailed,)):
        self._b = bucket
        self._pf = tuple(precondition_errors)

    def put(self, key, data, *, if_generation_match=None):
        check_key(key)
        blob = self._b.blob(key)
        try:
            blob.upload_from_string(bytes(data), if_generation_match=if_generation_match)
        except self._pf as e:
            raise PreconditionFailed(f"{key}: {e}") from None
        return blob.generation

    def get(self, key, generation=None):
        check_key(key)
        blob = self._b.blob(key)
        try:
            return blob.download_as_bytes(generation=generation) if generation is not None else blob.download_as_bytes()
        except KeyError:
            return None
        except Exception as e:                      # google NotFound
            if e.__class__.__name__ == "NotFound":
                return None
            raise

    def generation(self, key):
        check_key(key)
        return self._b.blob(key).generation or 0

    def list(self, prefix):
        return sorted(b.name for b in self._b.list_blobs(prefix=prefix))

    @classmethod
    def from_bucket_name(cls, name: str, *, armed: bool = False):
        """Production constructor. Refuses unless explicitly armed; imports the cloud library lazily so this module stays importable without it."""
        if not armed:
            raise PermissionError("GcsObjectStore.from_bucket_name refused: not armed (no production storage is enabled by this change)")
        from google.cloud import storage                                  # noqa: PLC0415
        from google.api_core import exceptions                            # noqa: PLC0415
        return cls(storage.Client().bucket(name), precondition_errors=(exceptions.PreconditionFailed,))
