"""History storage: versioned objects, immutability, head pointer, previous-publish linkage, rollback metadata (local/test implementations only)."""
import pytest

from publisher_fixtures import make, uuid4, wind_artifact
from sector_brain_platform.publisher import LocalDirObjectStore, MemoryObjectStore, PublishHistory, Result
from sector_brain_platform.publisher.storage import (ArtifactConflict, PREFIXES, PreconditionFailed, StorageError, artifact_key, check_key, head_key,
                                                      publish_key)


def test_object_store_keeps_every_generation_and_enforces_preconditions():
    s = MemoryObjectStore()
    assert s.put("publishes/wind/x.json", b"1", if_generation_match=0) == 1
    assert s.put("publishes/wind/x.json", b"2") == 2
    assert s.get("publishes/wind/x.json") == b"2" and s.get("publishes/wind/x.json", 1) == b"1" and s.get("publishes/wind/x.json", 3) is None
    with pytest.raises(PreconditionFailed):
        s.put("publishes/wind/x.json", b"3", if_generation_match=0)           # create-only is immutable
    with pytest.raises(PreconditionFailed):
        s.put("publishes/wind/x.json", b"3", if_generation_match=1)           # stale optimistic-concurrency token
    assert s.put("publishes/wind/x.json", b"3", if_generation_match=2) == 3


@pytest.mark.parametrize("key", ["other/x.json", "artifacts/../x", "artifacts//x", "/artifacts/x", "artifacts/a b", "artifacts/.hidden", "", None])
def test_keys_are_confined_to_the_four_approved_prefixes(key):
    with pytest.raises(StorageError):
        check_key(key)


def test_layout_matches_cert_3():
    assert PREFIXES == ("artifacts/", "publishes/", "scores/", "exports/")
    assert artifact_key("wind", "sha256:ab12") == "artifacts/wind/sha256-ab12.json"
    assert publish_key("wind", uuid4(1)).startswith("publishes/wind/") and head_key("wind", "wind-lake-state-v1") == "publishes/wind/_heads/wind-lake-state-v1/default.json"


def test_publisher_writes_only_artifacts_and_publishes_prefixes():
    pub, hist, _ = make()
    pub.evaluate(wind_artifact(n=1), producer="wind")
    pub.evaluate(wind_artifact(n=2, lifecycle="PRODUCTION", minutes=5), producer="wind")
    assert {k.split("/")[0] + "/" for k in hist.store.list("")} == {"artifacts/", "publishes/"}


def test_artifacts_are_immutable_and_idempotent():
    h = PublishHistory(MemoryObjectStore())
    a = wind_artifact()
    k = h.put_artifact("wind", uuid4(9), a)
    assert h.put_artifact("wind", uuid4(9), a) == k                              # same bytes: fine
    other = wind_artifact(speed=1.0)
    with pytest.raises(ArtifactConflict):
        h.put_artifact("wind", uuid4(9), other)
    assert h.get_artifact("wind", uuid4(9)) == a


def test_previous_publication_linkage_and_head_generations():
    pub, hist, _ = make()
    rs = [pub.evaluate(wind_artifact(n=i, speed=float(i), minutes=10 * i), producer="wind") for i in (1, 2, 3)]
    assert all(r.result is Result.SHADOW_READY for r in rs)
    assert [r.record.get("previousPublishId") for r in rs] == [None, rs[0].publish_id, rs[1].publish_id]
    assert hist.head("wind", "wind-lake-state-v1")["publishId"] == rs[2].publish_id
    assert [h["publishId"] for h in hist.head_history("wind", "wind-lake-state-v1")] == [r.publish_id for r in rs]     # versioning keeps every pointer


def test_rollback_metadata_identifies_the_previous_publish_and_artifact():
    pub, hist, _ = make()
    r1 = pub.evaluate(wind_artifact(n=1, speed=1.0), producer="wind")
    r2 = pub.evaluate(wind_artifact(n=2, speed=2.0, minutes=10), producer="wind")
    ref = hist.rollback_reference("wind", r2.publish_id)
    assert ref["restorePublishId"] == r1.publish_id and ref["artifactId"] == uuid4(2001) and ref["artifactStored"] is True
    assert ref["outputFingerprint"] == r1.record["outputFingerprint"] and ref["artifactKey"] == artifact_key("wind", uuid4(2001))
    assert hist.get_artifact("wind", ref["artifactId"])["lineage"]["outputFingerprint"] == r1.record["outputFingerprint"]     # the rollback source really exists
    assert hist.rollback_reference("wind", r1.publish_id) is None                # first publication: nothing earlier
    with pytest.raises(StorageError):
        hist.rollback_reference("wind", uuid4(404))


def test_concurrent_head_advance_is_detected():
    pub, hist, _ = make()
    r = pub.evaluate(wind_artifact(n=1), producer="wind")
    stale = dict(r.record, publishId=uuid4(9), headGeneration=0)                  # a second writer that planned against the empty head
    with pytest.raises(PreconditionFailed):
        hist.advance_head(stale)


def test_rejected_artifact_is_kept_with_its_rejection_record():
    pub, hist, _ = make()
    r = pub.evaluate(wind_artifact(lifecycle="PRODUCTION"), producer="wind")
    assert r.record["artifactStored"] is True and hist.get_artifact("wind", r.record["artifactId"]) is not None
    assert hist.get_record("wind", r.publish_id)["violations"][0]["code"] == "LIFECYCLE_NOT_AUTHORIZED"
    assert hist.head("wind", "wind-lake-state-v1") is None


def test_local_directory_store_persists_generations_and_reloads(tmp_path):
    store = LocalDirObjectStore(tmp_path)
    pub, hist, _ = make(store=store)
    r1 = pub.evaluate(wind_artifact(n=1), producer="wind")
    r2 = pub.evaluate(wind_artifact(n=2, speed=3.0, minutes=10), producer="wind")
    again = PublishHistory(LocalDirObjectStore(tmp_path))                          # a fresh process reading the same directory
    assert again.head("wind", "wind-lake-state-v1")["publishId"] == r2.publish_id
    assert [h["publishId"] for h in again.head_history("wind", "wind-lake-state-v1")] == [r1.publish_id, r2.publish_id]
    assert {p.suffix for p in tmp_path.rglob("*") if p.is_file()} <= {".g1", ".g2"}
    assert not any(".." in str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
