"""The publication ledger survives worker restarts, lost Publisher answers and overlapping workers (Cortex 3.1 PL-19; Orchestrator scales to zero)."""
import datetime as dt
import json

import pytest

from live_rig import Rig
from publisher_fixtures import T0, make, wind_artifact
from sector_brain_platform.publication_coordination import PublicationCoordinator, StoreLedger
from sector_brain_platform.publisher.storage import LocalDirObjectStore, PreconditionFailed

CLOCK = {"t": T0 + dt.timedelta(hours=1)}


def coordinator(rig, store, live, cutover=("wind",)):
    shadow, _, _ = make(store=rig.store)
    return PublicationCoordinator(StoreLedger(store), rig.store, shadow=shadow, live=live, cutover=cutover, clock=lambda: CLOCK["t"])


def test_ledger_records_survive_a_restart_of_the_worker(tmp_path):
    rig = Rig(brains=("wind",))
    ref = rig.ref(wind_artifact(n=1))
    rig.reconcile(ref)
    disk = LocalDirObjectStore(tmp_path)                                    # the private bucket stand-in, persisted
    rec = coordinator(rig, disk, rig.live).process(ref)
    assert rec["publication"]["outcome"] == "PUBLISHED"
    fresh = StoreLedger(LocalDirObjectStore(tmp_path))                       # a brand new process reading the same storage
    assert fresh.get(rec["key"])["publication"]["outcome"] == "PUBLISHED" and len(fresh.records()) == 1
    calls = rig.rtdb.calls
    again = coordinator(rig, LocalDirObjectStore(tmp_path), rig.live).process(ref)           # the same run reported again after the restart
    assert again["publication"]["attempts"] == 1 and rig.rtdb.calls == calls


def test_a_lost_answer_after_a_successful_write_is_recovered_from_the_publisher_history_not_republished():
    rig = Rig(brains=("wind",))
    ref = rig.ref(wind_artifact(n=1))
    rig.reconcile(ref)
    disk = rig.store.__class__()                                             # ledger storage
    real = rig.live

    class LosesAnswer:
        history = real.history

        def publish(self, r):
            real.publish(r)                                                  # the write happened ...
            raise ConnectionError("response lost")                            # ... the answer did not arrive
    co = coordinator(rig, disk, LosesAnswer())
    rec = co.process(ref)
    assert rec["publication"]["outcome"] == "FAILED" and rec["publication"]["retryable"] is True
    n = len(rig.rtdb.updates)
    rec["publication"]["nextAttemptAfter"] = "2000-01-01T00:00:00Z"
    co.ledger.put(rec)
    rec = co.request_publication(rec["key"])
    p = rec["publication"]
    assert p["outcome"] == "PUBLISHED" and p["reason"] == "RECOVERED_FROM_PUBLISHER_HISTORY" and p["recovered"] is True and p["livePublishId"]
    assert len(rig.rtdb.updates) == n                                        # nothing was written a second time


def test_a_crash_between_the_request_and_the_answer_leaves_a_durable_in_flight_marker():
    rig = Rig(brains=("wind",))
    ref = rig.ref(wind_artifact(n=1))
    rig.reconcile(ref)
    disk = rig.store.__class__()

    class Crashes:
        def publish(self, r):
            raise KeyboardInterrupt("worker killed")
    co = coordinator(rig, disk, Crashes())
    with pytest.raises(KeyboardInterrupt):
        co.process(ref)
    rec = next(iter(StoreLedger(disk).records()))
    assert rec["publication"]["inFlight"] is True and rec["publication"]["attempts"] == 1 and rec["publication"]["outcome"] != "PUBLISHED"
    after = coordinator(rig, disk, rig.live).resume()                       # next worker continues it
    rec = next(iter(StoreLedger(disk).records()))
    assert rec["publication"]["outcome"] == "PUBLISHED" and rec["publication"]["inFlight"] is False and after["requested"] + after["retried"] == 1


def test_overlapping_workers_never_lose_a_record_or_write_twice():
    rig = Rig(brains=("wind",))
    a, b = rig.ref(wind_artifact(n=1)), rig.ref(wind_artifact(n=2, speed=8.0, minutes=30))
    rig.reconcile(a)
    disk = rig.store.__class__()
    w1, w2 = coordinator(rig, disk, rig.live), coordinator(rig, disk, rig.live)       # both loaded the (empty) ledger
    r1 = w1.process(a)                                                       # worker 1 commits
    r2 = w2.process(b)                                                       # worker 2 holds a stale generation: it must re-read and merge
    keys = {r["key"] for r in StoreLedger(disk).records()}
    assert keys == {r1["key"], r2["key"]}
    assert StoreLedger(disk).get(r1["key"])["publication"]["outcome"] == "PUBLISHED"


def test_conflicting_versions_of_one_record_keep_the_decided_one():
    rig = Rig(brains=("wind",))
    ref = rig.ref(wind_artifact(n=1))
    rig.reconcile(ref)
    disk = rig.store.__class__()
    w1, w2 = coordinator(rig, disk, rig.live), coordinator(rig, disk, None)
    w2.collect(ref)                                                          # stale view: only collected
    w1.process(ref)                                                          # decided PUBLISHED
    stale = w2.ledger.get(next(iter(w2.ledger.doc["records"])))
    w2.ledger.put(stale)                                                     # the stale writer commits late
    assert next(iter(StoreLedger(disk).records()))["publication"]["outcome"] == "PUBLISHED"


def test_the_orchestrator_view_can_write_only_its_own_prefix():
    from sector_brain_platform.publisher.storage import AccessDenied, MemoryObjectStore, orchestrator_view
    v = orchestrator_view(MemoryObjectStore())
    StoreLedger(v).put({"key": "k", "brainId": "wind", "runId": "r", "artifact": {"state": "MISSING"}, "publication": {"outcome": "NOT_REQUESTED", "attempts": 0}})
    for key in ("artifacts/wind/x/artifact.json", "publishes/wind/p/record.json", "publishes/wind/_heads/s/default.json", "scores/wind/x"):
        with pytest.raises(AccessDenied):
            v.put(key, b"{}", if_generation_match=0)
        with pytest.raises(AccessDenied):
            v.put(key, b"{}", if_generation_match=1)


def test_a_publication_made_by_any_path_is_imported_from_the_publisher_history_once():
    rig = Rig(brains=("wind",))
    ref, res = rig.publish_first(wind_artifact(n=1))                                  # published by a path that never touched the Orchestrator's ledger
    disk = rig.store.__class__()
    co = coordinator(rig, disk, None, cutover=())
    out = co.import_publisher_history(["wind", "lake-brain"])
    assert len(out["imported"]) == 1 and out["recordsSeen"] >= 1
    rec = next(iter(StoreLedger(disk).records("wind")))
    assert rec["publication"]["outcome"] == "PUBLISHED" and rec["publication"]["reason"] == "IMPORTED_FROM_PUBLISHER_HISTORY" and rec["publication"]["livePublishId"] == res.publish_id
    assert rec["writePath"] == "PUBLISHER" and rec["artifact"]["state"] == "COLLECTED" and rec["artifact"]["digest"] == ref.sha256
    assert co.import_publisher_history(["wind"])["imported"] == []                    # idempotent: never duplicated or changed
    assert co.summary()["brains"]["wind"]["published"] == 1
