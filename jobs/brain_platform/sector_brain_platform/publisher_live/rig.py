"""Test/proof rig: a LivePublisher wired to FAKE clients only (in-memory or fake-GCS object store, FakeRtdb), deterministic clock and ids.
Used by the platform tests and by the Brain Certification Kit's live-parity proofs. It contains no network, no credentials and no production adapter."""
from __future__ import annotations

import datetime as dt
import itertools
import uuid

from ..publisher import ArtifactWriter, MemoryObjectStore, PublishHistory, default_registry, publisher_view
from .authorization import BrainAuthorization, LiveAuthorization
from .fakes import FakeBucket, FakeRtdb
from .gcs_store import GcsObjectStore
from .publisher import LivePublisher

DEFAULT_CLOCK = dt.datetime(2026, 10, 15, 4, 0, tzinfo=dt.timezone.utc)


def _uuid(n: int) -> str:
    return str(uuid.UUID(int=n, version=4))


def make_store(kind="memory"):
    return MemoryObjectStore() if kind == "memory" else GcsObjectStore(FakeBucket())


class Rig:
    def __init__(self, brains=("wind",), store_kind="memory", tree=None, max_update_bytes=4 * 1024 * 1024, on_published=None, registry=None, clock=None, release_resolver=None):
        self.store = make_store(store_kind)
        self.history = PublishHistory(publisher_view(self.store))
        self.rtdb = FakeRtdb(tree)
        self.ids = itertools.count(1)
        self.signals = []
        self.clock = clock or DEFAULT_CLOCK
        self.auth = LiveAuthorization(*[BrainAuthorization(b, f"approval/test/{b}") for b in brains])
        self._resolver = release_resolver
        self.live = self._build(registry, max_update_bytes, on_published or self.signals.append)

    def _build(self, registry, max_update_bytes, on_published):
        return LivePublisher(registry or default_registry(), self.history, self.rtdb, self.auth, clock=lambda: self.clock,
                             id_factory=lambda: _uuid(next(self.ids) + 70000), max_update_bytes=max_update_bytes, on_published=on_published,
                             release_resolver=self._resolver)

    def with_limit(self, max_update_bytes):
        r = Rig.__new__(Rig)
        r.__dict__.update(self.__dict__)
        r.live = r._build(self.live.registry, max_update_bytes, self.signals.append)
        return r

    def ref(self, artifact, brain=None):
        return ArtifactWriter(self.store, brain or artifact["lineage"]["brainId"]).write(artifact)

    def reconcile(self, ref, approval="approval/baseline/test"):
        return self.live.acknowledge_baseline(ref, approval_ref=approval)

    def publish_first(self, artifact):
        ref = self.ref(artifact)
        self.reconcile(ref)
        return ref, self.live.publish(ref)
