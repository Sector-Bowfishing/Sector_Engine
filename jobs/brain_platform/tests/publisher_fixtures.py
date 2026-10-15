"""Sanitised fixtures for Publisher V1 tests: synthetic lake keys, synthetic ids, no real data, no credentials."""
import copy
import datetime as dt
import itertools

from sector_brain_platform.publisher.artifact import section_fingerprint
from sector_brain_platform.publisher import (LocalDirObjectStore, MemoryObjectStore, PublishHistory, PublisherMode, ShadowPublisher, ShadowSink,
                                             default_registry, output_fingerprint)

T0 = dt.datetime(2026, 10, 15, 3, 0, tzinfo=dt.timezone.utc)
SHA = "sha256:" + "ab" * 32
LAKE_A, LAKE_B = "test_lake_alpha", "test_lake_beta"


def uuid4(n: int) -> str:
    return f"{n:08x}-0000-4000-8000-{n:012x}"


def iso(t) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def rebuild(art: dict) -> dict:
    """Recompute and set the declared outputFingerprint (what an honest Brain does)."""
    lin = art["lineage"]
    spec = default_registry().spec(lin["artifactSchema"])
    lin["outputFingerprint"] = section_fingerprint(spec, lin["brainId"], art["mutations"]) if spec else output_fingerprint(lin["brainId"], lin["artifactSchema"], art["mutations"])
    return art


def wind_state(speed=4.2):
    return {"kind": "modeled", "windMS": speed, "texture": "RIPPLED", "generatedAt": "2026-10-15T03:00:00Z", "note": "synthetic"}


def wind_artifact(n=1, speed=4.2, minutes=0, mutations=None, **lineage_over):
    t = T0 + dt.timedelta(minutes=minutes)
    muts = mutations if mutations is not None else [
        {"op": "SET", "path": f"/lakes/{LAKE_A}/states/wind", "value": wind_state(speed)},
        {"op": "SET", "path": f"/lakes/{LAKE_A}/profiles/wind", "value": {"profile": "synthetic", "version": 1}},
        {"op": "SET", "path": f"/lakeFleet/{LAKE_A}/slots/wind", "value": {"readiness": "CALIBRATION", "stale": False}},
        {"op": "SET", "path": f"/lakes/{LAKE_B}/states/wind", "value": wind_state(speed + 1)},
    ]
    lin = {"schema": "brain-lineage-v1", "brainId": "wind", "artifactSchema": "wind-lake-state-v1", "knowledgeRelease": "NONE", "manifestRef": "NONE",
           "manifestSha256": "NONE", "codeVersion": "deadbeef", "executionId": uuid4(1000 + n), "inputFingerprint": SHA, "outputFingerprint": SHA,
           "artifactId": uuid4(2000 + n), "generatedAt": iso(t), "lifecycle": "CALIBRATION", "reviewStatus": "UNREVIEWED", "validationStatus": "NOT_VALIDATED"}
    lin.update(lineage_over)
    art = {"envelope": "publish-artifact-v1", "lineage": lin, "mutations": copy.deepcopy(muts),
           "freshness": {"evidenceObservedAt": iso(t), "freshnessStatus": "FRESH", "staleAfter": iso(t + dt.timedelta(hours=3)), "expiresAt": iso(t + dt.timedelta(hours=12))}}
    return rebuild(art) if "outputFingerprint" not in lineage_over else art


def make(mode=PublisherMode.SHADOW, store=None, registry=None, **kw):
    """-> (publisher, history, sink) with deterministic ids and clock."""
    ids = itertools.count(1)
    hist = PublishHistory(store or MemoryObjectStore())
    sink = ShadowSink()
    pub = ShadowPublisher(registry or default_registry(), hist, sink, mode=mode, clock=lambda: T0 + dt.timedelta(hours=1),
                          id_factory=lambda: uuid4(next(ids) + 50000), **kw)
    return pub, hist, sink
