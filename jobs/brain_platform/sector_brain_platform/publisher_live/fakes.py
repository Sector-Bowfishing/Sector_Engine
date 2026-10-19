"""Fake clients for tests and offline parity proofs. No network, no credentials. Importing this module is the ONLY way tests touch a 'database'."""
from __future__ import annotations

import copy
import json

from .model import RtdbAmbiguousFailure, RtdbDefiniteFailure


def _norm(o):
    """What RTDB would hand back: integral floats become ints, key order irrelevant."""
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_norm(v) for v in o]
    if isinstance(o, float) and o == int(o):
        return int(o)
    return o


class FakeRtdb:
    """In-memory tree with RTDB multi-location update semantics (atomic per call; None deletes) and fault injection.

    fail_next: list of ('definite'|'ambiguous_before'|'ambiguous_after', n) – the n-th upcoming update() call fails that way.
      definite          -> raises RtdbDefiniteFailure, nothing applied
      ambiguous_before  -> raises RtdbAmbiguousFailure, nothing applied (the request never landed)
      ambiguous_after   -> applies, THEN raises RtdbAmbiguousFailure (the response was lost)
    corrupt_after_apply: a callable(tree) run after a successful apply (simulates a divergent authoritative read).
    """

    def __init__(self, tree=None):
        self.tree = copy.deepcopy(tree) if tree else {}
        self.updates: list[dict] = []          # every update() payload, for assertions about write sets
        self.calls = 0
        self.faults: list[tuple] = []
        self.corrupt_after_apply = None
        self.reads: list[str] = []

    def inject(self, kind: str, nth: int = 1):
        self.faults.append((kind, self.calls + nth))

    def get(self, path):
        self.reads.append(path)
        node = self.tree
        for p in [p for p in path.split("/") if p]:
            if not isinstance(node, dict) or p not in node:
                return None
            node = node[p]
        return copy.deepcopy(node)

    def _apply(self, clean):
        for path, val in clean.items():
            parts = [p for p in path.split("/") if p]
            node = self.tree
            for p in parts[:-1]:
                if not isinstance(node.get(p), dict):
                    node[p] = {}
                node = node[p]
            if val is None:
                node.pop(parts[-1], None)
                chain = [self.tree]                                   # RTDB has no empty nodes: prune parents left empty by a delete
                for p in parts[:-1]:
                    chain.append(chain[-1].get(p) if isinstance(chain[-1], dict) else None)
                for i in range(len(parts) - 1, 0, -1):
                    if isinstance(chain[i], dict) and not chain[i]:
                        chain[i - 1].pop(parts[i - 1], None)
            else:
                node[parts[-1]] = _norm(copy.deepcopy(val))

    def update(self, updates):
        self.calls += 1
        clean = {k.lstrip("/"): v for k, v in updates.items()}
        json.dumps(clean, allow_nan=False)
        kind = next((k for k, n in self.faults if n == self.calls), None)
        if kind == "definite":
            raise RtdbDefiniteFailure("injected definite failure")
        if kind == "ambiguous_before":
            raise RtdbAmbiguousFailure("injected: request lost")
        self.updates.append(clean)
        self._apply(clean)
        if self.corrupt_after_apply:
            self.corrupt_after_apply(self.tree)
        if kind == "ambiguous_after":
            raise RtdbAmbiguousFailure("injected: response lost after commit")

    # test helpers
    def snapshot(self):
        return copy.deepcopy(self.tree)

    def write_keys(self):
        return sorted({k for u in self.updates for k in u})


class FakeBlob:
    def __init__(self, bucket, name):
        self.bucket, self.name = bucket, name

    @property
    def generation(self):
        v = self.bucket._objs.get(self.name)
        return v[-1][0] if v else None

    def upload_from_string(self, data, *, if_generation_match=None):
        from .gcs_store import GcsPreconditionFailed
        cur = self.generation or 0
        if if_generation_match is not None and if_generation_match != cur:
            raise GcsPreconditionFailed(f"{self.name}: generation {cur} != {if_generation_match}")
        self.bucket._seq += 1000003                      # real GCS generations are large opaque integers, never counts
        self.bucket._objs.setdefault(self.name, []).append((self.bucket._seq, bytes(data)))

    def download_as_bytes(self, *, generation=None):
        v = self.bucket._objs.get(self.name)
        if not v:
            raise KeyError(self.name)
        if generation is None:
            return v[-1][1]
        for g, d in v:
            if g == generation:
                return d
        raise KeyError(f"{self.name}#{generation}")

    def exists(self):
        return self.name in self.bucket._objs


class FakeBucket:
    """Mimics the subset of google.cloud.storage.Bucket the adapter uses."""

    def __init__(self):
        self._objs: dict[str, list] = {}
        self._seq = 0
        self.deletes = 0

    def blob(self, name):
        return FakeBlob(self, name)

    def list_blobs(self, prefix=""):
        return [FakeBlob(self, n) for n in sorted(self._objs) if n.startswith(prefix)]

    def delete_blob(self, name):                          # exists only so a test can prove the adapter never calls it
        self.deletes += 1
