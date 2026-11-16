"""tools/ops/dev_rehearsal.py (Sector_Engine #198, owner approval B5): the X09/X13 rehearsal, proven here against FAKE clients only.

The real run is Michael's, against the non-production Brain database once a reviewed PR lists it. These tests prove the guard refuses everything
today, and that the rehearsal reports PASS on a correct database and FAIL when atomicity or rollback is broken."""
import datetime as dt
import itertools
import json
import os
import sys
import uuid

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))

import dev_rehearsal as DR                                                              # noqa: E402
from sector_brain_platform.publisher import MemoryObjectStore                          # noqa: E402
from sector_brain_platform.publisher_live.fakes import FakeBucket, FakeRtdb            # noqa: E402
from sector_brain_platform.publisher_live.gcs_store import GcsObjectStore              # noqa: E402
from sector_brain_platform.publisher_live.model import RtdbDefiniteFailure             # noqa: E402

FAKE_DEV = "https://sector-brain-rehearsal-fake.firebaseio.invalid"
T = dt.datetime(2026, 11, 16, 6, 0, tzinfo=dt.timezone.utc)


def _ids():
    n = itertools.count(1)
    return lambda: str(uuid.UUID(int=next(n) + 90000, version=4))


def _run(rtdb, store=None):
    return DR.rehearse(rtdb, store or MemoryObjectStore(), approval_ref="approval/test/rehearsal", clock=lambda: T, new_id=_ids())


def test_the_hard_coded_lists_are_empty_so_every_database_is_refused_today():
    assert DR.DEV_BRAIN_DATABASES == frozenset() and DR.DEV_BUCKETS == frozenset()
    for url in (FAKE_DEV, "https://sector-brain-dev.firebaseio.com", "https://anything.example"):
        with pytest.raises(DR.Refused):
            DR.guard_database(url)


@pytest.mark.parametrize("url", ["https://sector-brain.firebaseio.com", "https://sector-brain.firebaseio.com/",
                                 "https://sector-9393c-default-rtdb.firebaseio.com", "https://sector-dev-1f4d0.firebaseio.com"])
def test_production_and_app_databases_are_refused_even_when_listed(url):
    with pytest.raises(DR.Refused):
        DR.guard_database(url, allowed={url})


def test_the_cli_refuses_before_building_any_client(tmp_path):
    built = []
    rc = DR.main(["--database-url", FAKE_DEV, "--approval-ref", "x", "--out-dir", str(tmp_path)], make_clients=lambda *a: built.append(a))
    assert rc == 2 and built == [] and list(tmp_path.iterdir()) == []
    rc = DR.main(["--database-url", FAKE_DEV, "--approval-ref", "x", "--bucket", "some-bucket", "--out-dir", str(tmp_path)],
                 allowed_databases={FAKE_DEV}, make_clients=lambda *a: built.append(a))
    assert rc == 2 and built == []


@pytest.mark.parametrize("store", ["memory", "gcs"])
def test_x09_and_x13_pass_on_a_correct_database(store):
    rtdb = FakeRtdb()
    ev = _run(rtdb, MemoryObjectStore() if store == "memory" else GcsObjectStore(FakeBucket()))
    assert ev["checks"]["X13"]["status"] == "PASS", ev["checks"]["X13"]
    assert ev["checks"]["X09"]["status"] == "PASS", ev["checks"]["X09"]
    x09 = ev["checks"]["X09"]
    assert x09["beforeDigest"] == x09["afterFailureDigest"] and x09["nonAuthoritativeKeysLanded"] > 0
    assert ev["checks"]["X13"]["preCutoverDigest"] == ev["checks"]["X13"]["afterRollbackDigest"]
    assert [s["step"] for s in ev["steps"]] == ["seed.publishA", "X13.publishB", "X13.rollbackB", "X09.publishC.faulted",
                                                "X09.otherArtifactWhileInterrupted", "X09.resumeC"]
    written = {k.split("/")[0] + "/" + k.split("/")[1] for u in rtdb.updates for k in u}
    assert all(not p.startswith("lakes/") or p.startswith("lakes/rehearsal_lake_") for p in written)      # synthetic lakes only


def test_a_rerun_over_the_previous_rehearsal_state_still_passes():
    rtdb = FakeRtdb()
    _run(rtdb)
    ev = DR.rehearse(rtdb, MemoryObjectStore(), approval_ref="approval/test/rehearsal", clock=lambda: T, new_id=_ids_offset(5000))
    assert {c: v["status"] for c, v in ev["checks"].items()} == {"X09": "PASS", "X13": "PASS"}
    assert ev["priorPublicationArtifactId"] is not None


def _ids_offset(k):
    n = itertools.count(k)
    return lambda: str(uuid.UUID(int=next(n), version=4))


class DropsDeletes(FakeRtdb):
    """A broken database: ignores deletes inside a multi-location update."""

    def update(self, updates):
        return super().update({k: v for k, v in updates.items() if v is not None})


def test_x13_fails_when_the_database_does_not_remove_the_rolled_back_paths():
    ev = _run(DropsDeletes())
    assert ev["checks"]["X13"]["status"] == "FAIL"
    assert ev["checks"]["X13"]["assertions"]["extra_lake_removed"] is False


def test_x09_fails_when_the_failed_write_moved_the_marker(monkeypatch):
    class Leaky(DR.FaultOnUpdate):
        def update(self, updates):
            self.calls += 1
            if self.calls == self.fail_on:
                self.inner.update({DR.PUB + "/artifactId": "leaked"})        # a non-atomic database: part of the failed write landed
                raise RtdbDefiniteFailure("forced")
            return self.inner.update(updates)
    monkeypatch.setattr(DR, "FaultOnUpdate", Leaky)
    ev = _run(FakeRtdb())
    assert ev["checks"]["X09"]["status"] == "FAIL"
    assert ev["checks"]["X09"]["assertions"]["marker_still_previous"] is False


def test_the_cli_writes_evidence_with_no_values(tmp_path):
    rtdb = FakeRtdb()
    rc = DR.main(["--database-url", FAKE_DEV, "--approval-ref", "approval/test", "--out-dir", str(tmp_path)],
                 allowed_databases={FAKE_DEV}, make_clients=lambda url, bucket: (rtdb, MemoryObjectStore()))
    assert rc == 0
    (f,) = list(tmp_path.iterdir())
    ev = json.loads(f.read_text())
    assert ev["standard"] == "dev-rehearsal-v1" and ev["database"] == FAKE_DEV and ev["objectStore"] == "memory"
    assert {c: v["status"] for c, v in ev["checks"].items()} == {"X09": "PASS", "X13": "PASS"}
    assert "windMS" not in f.read_text()                                     # digests and key counts, never the data
