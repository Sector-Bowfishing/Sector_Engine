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

    def flush_ledger(self) -> None:
        pass

    def read_ledger(self) -> list[dict]:
        p = os.path.join(self.root, "ledger/ingest.jsonl")
        if not os.path.exists(p):
            return []
        return [json.loads(l) for l in open(p) if l.strip()]


class GcsStore:
    """Cloud Storage archive with the LocalStore interface. Every write raises on failure (no
    silent GCS failures). The ledger is buffered per run and flushed to its own object
    (ledger/runs/<run>.jsonl), because objects can't be appended to."""
    def __init__(self, bucket: str, prefix: str):
        if os.environ.get("SECTOR_WIND_GCS_APPROVED") != "yes":
            raise PermissionError("GCS writes need Michael's approval: set SECTOR_WIND_GCS_APPROVED=yes only after it is given")
        if bucket in SHARED_BUCKETS_NEVER:
            raise PermissionError(f"refusing to write the shared bucket {bucket}")
        from google.cloud import storage  # imported only when approved
        self.bucket = storage.Client().bucket(bucket)
        self.prefix = prefix.strip("/")
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + os.urandom(3).hex()
        self._ledger: list[dict] = []
        self.root = f"gs://{bucket}/{self.prefix}"

    def _k(self, key: str) -> str:
        return f"{self.prefix}/{key}"

    def put_json(self, key: str, obj) -> int:
        data = json.dumps(obj, separators=(",", ":")).encode()
        blob = self.bucket.blob(self._k(key))
        if key.endswith(".gz"):
            data = gzip.compress(data, mtime=0)
            blob.upload_from_string(data, content_type="application/gzip")
        else:
            blob.upload_from_string(data, content_type="application/json")
        return len(data)

    def get_json(self, key: str):
        blob = self.bucket.blob(self._k(key))
        if not blob.exists():
            return None
        raw = blob.download_as_bytes(raw_download=True)
        if key.endswith(".gz") or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return json.loads(raw)

    def exists(self, key: str) -> bool:
        return self.bucket.blob(self._k(key)).exists()

    def list(self, prefix: str) -> list[str]:
        n = len(self.prefix) + 1
        return sorted(b.name[n:] for b in self.bucket.client.list_blobs(self.bucket, prefix=self._k(prefix)))

    def append_ledger(self, entry: dict) -> None:
        self._ledger.append({"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "run": self.run_id, **entry})

    def flush_ledger(self) -> None:
        if self._ledger:
            body = "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in self._ledger)
            self.bucket.blob(self._k(f"ledger/runs/{self.run_id}.jsonl")).upload_from_string(body, content_type="application/x-ndjson")

    def read_ledger(self) -> list[dict]:
        out = []
        for k in self.list("ledger/runs/"):
            out += [json.loads(l) for l in self.bucket.blob(self._k(k)).download_as_text().splitlines() if l.strip()]
        return out


def open_store(spec: str):
    """'local:/path' or 'gs://bucket/prefix'."""
    if spec.startswith("gs://"):
        b, _, pre = spec[5:].partition("/")
        return GcsStore(b, pre or "wind/v1")
    return LocalStore(spec.removeprefix("local:"))
