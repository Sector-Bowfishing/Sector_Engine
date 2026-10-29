"""A stdlib-only Cloud Storage object store (JSON REST API) with the SAME contract as `publisher.storage.MemoryObjectStore`: create-only via generation 0, optimistic overwrite
via the last seen generation, `get(key, generation)`, `generation(key)` (0 when absent), `list(prefix)`. There is NO delete method.

It exists so the scale-to-zero Orchestrator image (stdlib + numpy only) can read sealed artifacts and keep its own coordination records in the private artifact bucket. What the
caller may do is decided twice: in code by the scoped view the stage wraps around this store, and in IAM by the identity's conditional bindings. `transport` is injectable (tests).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .publisher.storage import PreconditionFailed, StorageError, check_key

API = "https://storage.googleapis.com"


class GcsRestObjectStore:
    def __init__(self, bucket: str, tokens, transport=None, timeout_s: float = 60.0):
        if not bucket or "/" in bucket:
            raise ValueError("bucket must be a bucket name")
        self.bucket, self._tokens, self._timeout = bucket, tokens, timeout_s
        self._t = transport or self._urllib

    def _urllib(self, method, url, body, headers):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _call(self, method, url, body=None, ctype=None):
        h = {"Authorization": f"Bearer {self._tokens.token()}"}
        if ctype:
            h["Content-Type"] = ctype
        return self._t(method, url, body, h)

    def _obj(self, key):
        return f"{API}/storage/v1/b/{self.bucket}/o/{urllib.parse.quote(check_key(key), safe='')}"

    def put(self, key, data, *, if_generation_match=None):
        q = {"uploadType": "media", "name": check_key(key)}
        if if_generation_match is not None:
            q["ifGenerationMatch"] = str(int(if_generation_match))
        st, body = self._call("POST", f"{API}/upload/storage/v1/b/{self.bucket}/o?" + urllib.parse.urlencode(q), bytes(data), "application/json")
        if st == 412:
            raise PreconditionFailed(f"{key}: generation precondition failed")
        if not 200 <= st < 300:
            raise StorageError(f"put {key} -> {st}: {body[:160]!r}")
        return int(json.loads(body)["generation"])

    def get(self, key, generation=None):
        url = self._obj(key) + "?alt=media" + (f"&generation={int(generation)}" if generation is not None else "")
        st, body = self._call("GET", url)
        if st == 404:
            return None
        if not 200 <= st < 300:
            raise StorageError(f"get {key} -> {st}: {body[:160]!r}")
        return body

    def generation(self, key):
        st, body = self._call("GET", self._obj(key) + "?fields=generation")
        if st == 404:
            return 0
        if not 200 <= st < 300:
            raise StorageError(f"generation {key} -> {st}: {body[:160]!r}")
        return int(json.loads(body)["generation"])

    def list(self, prefix):
        names, token = [], None
        while True:
            q = {"prefix": prefix, "fields": "items(name),nextPageToken"}
            if token:
                q["pageToken"] = token
            st, body = self._call("GET", f"{API}/storage/v1/b/{self.bucket}/o?" + urllib.parse.urlencode(q))
            if not 200 <= st < 300:
                raise StorageError(f"list {prefix} -> {st}: {body[:160]!r}")
            d = json.loads(body)
            names += [i["name"] for i in d.get("items", [])]
            token = d.get("nextPageToken")
            if not token:
                return sorted(names)
