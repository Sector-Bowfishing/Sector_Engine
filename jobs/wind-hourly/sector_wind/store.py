"""Archive storage. LocalStore is the default and the only store used in Stage 2.

GcsStore exists so the Cloud Run Job can be deployed later, but it refuses to construct
unless SECTOR_WIND_GCS_APPROVED=yes AND the bucket is not one of the shared production
buckets. Writing to Cloud Storage needs Michael's approval (Stage 2 cloud checkpoint)."""
from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timezone

SHARED_BUCKETS_NEVER = {"sector-lake-surface", "sector-clarity-candidate", "sector-9393c.appspot.com"}


class LocalStore:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _p(self, key: str) -> str:
        p = os.path.join(self.root, key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def put_json(self, key: str, obj) -> int:
        data = json.dumps(obj, separators=(",", ":")).encode()
        if key.endswith(".gz"):
            data = gzip.compress(data, mtime=0)
        tmp = self._p(key) + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, self._p(key))
        return len(data)

    def get_json(self, key: str):
        p = os.path.join(self.root, key)
        if not os.path.exists(p):
            return None
        raw = open(p, "rb").read()
        if key.endswith(".gz"):
            raw = gzip.decompress(raw)
        return json.loads(raw)

    def exists(self, key: str) -> bool:
        return os.path.exists(os.path.join(self.root, key))

    def list(self, prefix: str) -> list[str]:
        base = os.path.join(self.root, prefix)
        out = []
        for dp, _, fs in os.walk(base):
            for f in fs:
                if not f.endswith(".tmp"):
                    out.append(os.path.relpath(os.path.join(dp, f), self.root))
        return sorted(out)

    def append_ledger(self, entry: dict) -> None:
        entry = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **entry}
        with open(self._p("ledger/ingest.jsonl"), "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    def read_ledger(self) -> list[dict]:
        p = os.path.join(self.root, "ledger/ingest.jsonl")
        if not os.path.exists(p):
            return []
        return [json.loads(l) for l in open(p) if l.strip()]


class GcsStore(LocalStore):  # same interface; staged through a local spool then uploaded
    def __init__(self, bucket: str, prefix: str, spool: str = "/tmp/sector-wind-spool"):
        if os.environ.get("SECTOR_WIND_GCS_APPROVED") != "yes":
            raise PermissionError("GCS writes need Michael's approval: set SECTOR_WIND_GCS_APPROVED=yes only after it is given")
        if bucket in SHARED_BUCKETS_NEVER:
            raise PermissionError(f"refusing to write the shared bucket {bucket}")
        from google.cloud import storage  # imported only when approved
        super().__init__(spool)
        self.bucket = storage.Client().bucket(bucket)
        self.prefix = prefix.strip("/")

    def put_json(self, key: str, obj) -> int:
        n = super().put_json(key, obj)
        blob = self.bucket.blob(f"{self.prefix}/{key}")
        blob.upload_from_filename(os.path.join(self.root, key),
                                  content_type="application/json",
                                  content_encoding="gzip" if key.endswith(".gz") else None)
        return n


def open_store(spec: str):
    """'local:/path' or 'gs://bucket/prefix'."""
    if spec.startswith("gs://"):
        b, _, pre = spec[5:].partition("/")
        return GcsStore(b, pre or "wind/v1")
    return LocalStore(spec.removeprefix("local:"))
