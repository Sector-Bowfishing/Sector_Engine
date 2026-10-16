"""Closeout decisions: artifact handoff by reference, ordering rule, /brains/{id} child ownership, private-namespace access model."""
import json

import pytest

from publisher_fixtures import LAKE_A, T0, iso, make, uuid4, wind_artifact, wind_state
from sector_brain_platform import DryRunStore
from sector_brain_platform.publisher import (ArtifactRef, ArtifactWriter, PublisherMode, Result, local_shadow_stack, output_fingerprint, sha256_ref)
from sector_brain_platform.publisher.storage import AccessDenied, ArtifactConflict, PreconditionFailed, artifact_key, brain_view, head_key, publisher_view
import itertools
import datetime as dt


def stack(**kw):
    ids = itertools.count(1)
    return local_shadow_stack(clock=lambda: T0 + dt.timedelta(hours=1), id_factory=lambda: uuid4(next(ids) + 50000), **kw)


def submit(st, art, **kw):
    ref = st.writer("wind").write(art, request_id=uuid4(900))
    return ref, st.publisher.evaluate_reference(ref, **kw)


def registry_artifact(n, muts, **kw):
    return wind_artifact(n=n, artifactSchema="wind-registry-v1", mutations=muts, **kw)


# ---- artifact handoff ----------------------------------------------------------------------------------------------------------------------
def test_reference_flow_loads_validates_and_stays_shadow_without_writing_artifacts():
    st = stack()
    ref, r = submit(st, wind_artifact(n=1))
    assert r.result is Result.SHADOW_READY and r.record["artifactId"] == ref.artifact_id and r.record["requestId"] == uuid4(900) and r.live_mutations == 0
    assert st.store.generation(artifact_key("wind", ref.artifact_id)) == 1                    # exactly the Brain's one write; the Publisher added none
    assert not [k for k in st.store.list("artifacts/") if "rejected-" in k]
    with pytest.raises(AccessDenied):
        st.history.put_artifact("wind", uuid4(1), wind_artifact())                           # the Publisher's storage view cannot create artifacts


def test_reference_flow_skip_and_change():
    st = stack()
    _, a = submit(st, wind_artifact(n=1))
    _, same = submit(st, wind_artifact(n=2, minutes=30))
    _, changed = submit(st, wind_artifact(n=3, speed=8.0, minutes=60))
    assert [x.result for x in (a, same, changed)] == [Result.SHADOW_READY, Result.SKIP, Result.SHADOW_READY]
    assert changed.record["previousPublishId"] == a.publish_id


def test_artifact_hash_mismatch_is_rejected_and_nothing_advances():
    st = stack()
    ref = st.writer("wind").write(wind_artifact(n=1))
    bad = ArtifactRef(ref.brain_id, ref.artifact_id, ref.location, sha256_ref(b"something else"), ref.execution_id, ref.expected_schema)
    r = st.publisher.evaluate_reference(bad)
    assert r.result is Result.REJECTED and r.codes == ["ARTIFACT_HASH_MISMATCH"] and r.plan is None and st.sink.submitted == []
    assert st.history.head("wind", "wind-lake-state-v1") is None and st.history.get_record("wind", r.publish_id)["result"] == "REJECTED"


def test_hash_is_over_the_exact_stored_bytes_not_a_canonical_re_encoding():
    st = stack()
    art = wind_artifact(n=1)
    raw_bytes = json.dumps(art, indent=2).encode()                                            # a Brain that writes pretty JSON
    key = artifact_key("wind", art["lineage"]["artifactId"])
    brain_view(st.store, "wind").put(key, raw_bytes, if_generation_match=0)
    ref = ArtifactRef("wind", art["lineage"]["artifactId"], key, sha256_ref(raw_bytes), art["lineage"]["executionId"], "wind-lake-state-v1")
    assert st.publisher.evaluate_reference(ref).result is Result.SHADOW_READY
    assert st.publisher.evaluate_reference(ArtifactRef(**{**ref.__dict__, "sha256": sha256_ref(json.dumps(art).encode())})).codes == ["ARTIFACT_HASH_MISMATCH"]


def test_missing_artifact_and_malformed_references():
    st = stack()
    ghost = ArtifactRef("wind", uuid4(77), f"artifacts/wind/{uuid4(77)}/artifact.json", sha256_ref(b"x"), uuid4(1), "wind-lake-state-v1")
    assert st.publisher.evaluate_reference(ghost).codes == ["ARTIFACT_NOT_FOUND"]
    for field, val, code in (("location", f"artifacts/wind/{uuid4(77)}/other.json", "ARTIFACT_REF_INVALID"), ("location", "../../etc/passwd", "NAMESPACE_VIOLATION"),
                             ("location", "/lakes/x/states/wind", "NAMESPACE_VIOLATION"), ("sha256", "abc", "ARTIFACT_REF_INVALID"),
                             ("artifact_id", "nope", "ARTIFACT_REF_INVALID"), ("execution_id", "nope", "ARTIFACT_REF_INVALID"),
                             ("expected_schema", "Bad Schema!", "ARTIFACT_REF_INVALID")):
        r = st.publisher.evaluate_reference(ArtifactRef(**{**ghost.__dict__, field: val}))
        assert r.is_rejection and r.codes == [code], (field, r.codes)


def test_a_brain_may_reference_only_its_own_artifact_namespace():
    st = stack()
    fish = wind_artifact(n=5, brainId="biological-state", artifactSchema="biological-species-profile-v1")
    fref = ArtifactWriter(st.store, "biological-state").write(fish)
    sneaky = ArtifactRef("wind", fref.artifact_id, fref.location, fref.sha256, fref.execution_id, fref.expected_schema)        # Wind pointing at a Fish artifact
    r = st.publisher.evaluate_reference(sneaky)
    assert r.result is Result.REJECTED and r.codes == ["NAMESPACE_VIOLATION"] and st.sink.submitted == []
    assert st.publisher.evaluate_reference(ArtifactRef("wind", fref.artifact_id, f"artifacts/biological-state/{fref.artifact_id}/../x", fref.sha256, fref.execution_id, "wind-lake-state-v1")).is_rejection


def test_binding_mismatches_between_request_and_artifact_are_rejected():
    st = stack()
    ref = st.writer("wind").write(wind_artifact(n=1))
    for field, val in (("execution_id", uuid4(4242)), ("expected_schema", "wind-registry-v1")):
        r = st.publisher.evaluate_reference(ArtifactRef(**{**ref.__dict__, field: val}))
        assert r.codes == ["ARTIFACT_BINDING_MISMATCH"], field


@pytest.mark.parametrize("mutate,code", [
    (lambda a: a["mutations"].append({"op": "SET", "path": "/speciesProfiles/common_carp", "value": {"a": 1}}), "CROSS_DOMAIN_PATH"),
    (lambda a: a["lineage"].update(lifecycle="PRODUCTION"), "LIFECYCLE_NOT_AUTHORIZED"),
    (lambda a: a["lineage"].update(outputFingerprint="sha256:" + "00" * 32), "FINGERPRINT_MISMATCH"),
    (lambda a: a["lineage"].pop("codeVersion"), "LINEAGE_INCOMPLETE"),
    (lambda a: a["lineage"].update(artifactSchema="nope-v1"), "UNKNOWN_SCHEMA"),
    (lambda a: a["mutations"][0].update(value=None), "NULL_VALUE"),
])
def test_artifact_retrieval_feeds_the_same_validation_path(mutate, code):
    st = stack()
    art = wind_artifact(n=1); mutate(art)
    ref = st.writer("wind").write(art)
    r = st.publisher.evaluate_reference(ref)
    assert r.codes == [code] and r.plan is None and st.sink.submitted == []


def test_rejected_reference_records_point_at_the_brains_artifact_and_write_nothing_to_artifacts():
    st = stack()
    art = wind_artifact(n=1, lifecycle="PRODUCTION")
    ref = st.writer("wind").write(art)
    before = st.store.list("artifacts/")
    r = st.publisher.evaluate_reference(ref)
    assert st.store.list("artifacts/") == before and r.record["artifactId"] == ref.artifact_id and st.history.get_record("wind", r.publish_id)


def test_dry_run_reference_flow_persists_nothing():
    st = stack(mode=PublisherMode.DRY_RUN)
    ref = st.writer("wind").write(wind_artifact(n=1))
    before = st.store.list("")
    r = st.publisher.evaluate_reference(ref)
    assert r.result is Result.SHADOW_READY and r.persisted is False and st.store.list("") == before and st.sink.submitted == []


# ---- private namespace access model ---------------------------------------------------------------------------------------------------------
def test_specialist_access_is_create_only_in_its_own_prefix():
    st = stack()
    w = brain_view(st.store, "wind")
    w.put("artifacts/wind/x/artifact.json", b"1", if_generation_match=0)
    with pytest.raises(PreconditionFailed):
        w.put("artifacts/wind/x/artifact.json", b"2", if_generation_match=0)                 # no overwrite
    for denied in ("artifacts/biological-state/x/artifact.json", "publishes/wind/x/record.json", "scores/wind/x.json", "exports/x.json", head_key("wind", "s")):
        with pytest.raises(AccessDenied):
            w.put(denied, b"x", if_generation_match=0)
    with pytest.raises(AccessDenied):
        w.put("artifacts/wind/y/artifact.json", b"x")                                          # un-guarded overwrite form is not a create
    with pytest.raises(AccessDenied):
        w.get("artifacts/biological-state/x/artifact.json")
    with pytest.raises(AccessDenied):
        w.list("artifacts/")
    assert not any(hasattr(w, n) for n in ("delete", "remove", "clear", "pop"))                # immutable history cannot be deleted through this interface


def test_artifact_writer_refuses_other_brains_and_conflicting_rewrites():
    st = stack()
    with pytest.raises(AccessDenied):
        st.writer("wind").write(wind_artifact(n=1, brainId="biological-state"))
    st.writer("wind").write(wind_artifact(n=1))
    st.writer("wind").write(wind_artifact(n=1))                                               # identical bytes: idempotent
    with pytest.raises(ArtifactConflict):
        st.writer("wind").write(wind_artifact(n=1, speed=1.0))


def test_publisher_access_reads_artifacts_and_creates_history_only():
    st = stack()
    p = publisher_view(st.store)
    ref = st.writer("wind").write(wind_artifact(n=1))
    assert p.get(ref.location) is not None
    p.put("publishes/wind/p1/record.json", b"{}", if_generation_match=0)
    for denied in ("artifacts/wind/z/artifact.json", "scores/wind/x.json", "exports/x.json"):
        with pytest.raises(AccessDenied):
            p.put(denied, b"x", if_generation_match=0)
    with pytest.raises(PreconditionFailed):
        p.put("publishes/wind/p1/record.json", b"{}", if_generation_match=0)                  # records are immutable
    assert not hasattr(p, "delete")


# ---- ARTIFACT_OLDER_THAN_BASELINE and the ordering rule -----------------------------------------------------------------------------------------
def test_older_artifact_is_rejected_with_a_diagnostic_naming_the_baseline():
    st = stack()
    _, a = submit(st, wind_artifact(n=1, minutes=60, speed=1.0))
    _, r = submit(st, wind_artifact(n=2, minutes=0, speed=2.0))
    assert r.result is Result.REJECTED and r.codes == ["ARTIFACT_OLDER_THAN_BASELINE"] and a.publish_id in r.violations[0]["detail"] and st.sink.submitted[-1][1]["publishId"] == a.publish_id
    assert st.history.head("wind", "wind-lake-state-v1")["publishId"] == a.publish_id


def test_equal_generated_at_with_different_content_is_ambiguous_and_rejected():
    st = stack()
    submit(st, wind_artifact(n=1, minutes=10, speed=1.0))
    _, r = submit(st, wind_artifact(n=2, minutes=10, speed=2.0))
    assert r.codes == ["ARTIFACT_OLDER_THAN_BASELINE"]


def test_sub_second_precision_orders_correctly():
    st = stack()
    a = wind_artifact(n=1, minutes=10, speed=1.0); a["lineage"]["generatedAt"] = "2026-10-15T03:10:00.100Z"
    b = wind_artifact(n=2, minutes=10, speed=2.0); b["lineage"]["generatedAt"] = "2026-10-15T03:10:00.200Z"
    for x in (a, b):
        x["lineage"]["outputFingerprint"] = output_fingerprint("wind", "wind-lake-state-v1", x["mutations"])
    assert submit(st, a)[1].result is Result.SHADOW_READY and submit(st, b)[1].result is Result.SHADOW_READY


def test_unequal_content_with_unestablishable_order_fails_closed():
    st = stack()
    _, a = submit(st, wind_artifact(n=1, minutes=10, speed=1.0))
    key = head_key("wind", "wind-lake-state-v1")
    ptr = json.loads(st.store.get(key)); ptr["generatedAt"] = "not a time"                    # a corrupted baseline pointer
    st.store.put(key, json.dumps(ptr).encode(), if_generation_match=1)
    _, r = submit(st, wind_artifact(n=2, minutes=20, speed=2.0))
    assert r.result is Result.REJECTED and r.codes == ["BASELINE_ORDER_UNKNOWN"]
    ptr.pop("generatedAt"); st.store.put(key, json.dumps(ptr).encode(), if_generation_match=2)
    assert submit(st, wind_artifact(n=3, minutes=30, speed=3.0))[1].codes == ["BASELINE_ORDER_UNKNOWN"]


def test_equal_content_skips_even_when_the_baseline_pointer_is_unreadable_for_ordering():
    st = stack()
    submit(st, wind_artifact(n=1, minutes=10))
    key = head_key("wind", "wind-lake-state-v1")
    ptr = json.loads(st.store.get(key)); ptr["generatedAt"] = "garbage"
    st.store.put(key, json.dumps(ptr).encode(), if_generation_match=1)
    assert submit(st, wind_artifact(n=2, minutes=20))[1].result is Result.SKIP                 # same fingerprint: nothing to order


def test_future_dated_artifact_is_rejected_so_it_cannot_block_later_honest_ones():
    st = stack()                                                                                   # publisher clock = T0 + 1h
    _, r = submit(st, wind_artifact(n=1, minutes=60 + 30))
    assert r.codes == ["ARTIFACT_FROM_FUTURE"] and st.history.head("wind", "wind-lake-state-v1") is None
    assert submit(st, wind_artifact(n=2, minutes=60 + 3))[1].result is Result.SHADOW_READY      # within the 5 min skew allowance


def test_ordering_is_per_scope():
    st = stack()
    submit(st, wind_artifact(n=1, minutes=40))
    other = wind_artifact(n=2, minutes=0, speed=2.0); other["scope"] = "other"
    assert submit(st, other)[1].result is Result.SHADOW_READY


# ---- /brains/{brainId} child ownership ----------------------------------------------------------------------------------------------------------
def test_whole_node_brains_replacement_is_rejected():
    pub = make()[0]
    for p in ("/brains/wind", "/brains"):
        r = pub.evaluate(registry_artifact(1, [{"op": "SET", "path": p, "value": {"brainId": "wind", "version": "x"}}]), producer="wind")
        assert r.result is Result.REJECTED and r.codes == ["BRAIN_NODE_REPLACEMENT"] and r.plan is None, p


def test_approved_wind_child_updates_are_accepted_one_per_registry_group():
    from sector_brain_platform.publisher.registry import WIND_REGISTRY_CHILDREN
    pub = make()[0]
    muts = [{"op": "SET", "path": f"/brains/wind/{c}", "value": {"v": 1}} for grp in WIND_REGISTRY_CHILDREN.values() for c in grp]
    r = pub.evaluate(registry_artifact(1, muts), producer="wind")
    assert r.result is Result.SHADOW_READY and set(WIND_REGISTRY_CHILDREN) == {"identity", "model", "status"}
    assert all(k.startswith("brains/wind/") for k in r.plan.updates) and "publication" not in {c for g in WIND_REGISTRY_CHILDREN.values() for c in g}


@pytest.mark.parametrize("path,code", [("/brains/wind/publication", "RESERVED_PATH"), ("/brains/wind/publication/publishId", "RESERVED_PATH"),
                                       ("/brains/wind/certification", "RESERVED_PATH"), ("/brains/wind/notAnApprovedChild", "PATH_NOT_AUTHORIZED"),
                                       ("/brains/wind/status/health", "PATH_NOT_AUTHORIZED"), ("/brains/biological-state/status", "CROSS_DOMAIN_PATH"),
                                       ("/brains/biological-state/publication", "RESERVED_PATH")])
def test_wind_cannot_supply_or_overwrite_publisher_owned_or_foreign_brain_children(path, code):
    pub = make()[0]
    muts = [{"op": "SET", "path": "/brains/wind/health", "value": "HEALTHY"}, {"op": "SET", "path": path, "value": {"x": 1}}]
    r = pub.evaluate(registry_artifact(1, muts), producer="wind")
    assert r.result is Result.REJECTED and code in r.codes and r.plan is None


def test_publisher_adds_its_own_publication_metadata_and_it_merges_without_touching_siblings():
    pub = make()[0]
    r = pub.evaluate(registry_artifact(1, [{"op": "SET", "path": "/brains/wind/health", "value": "HEALTHY"},
                                                    {"op": "SET", "path": "/brains/wind/status", "value": "CALIBRATION"}]), producer="wind")
    pub = r.plan.updates["brains/wind/publication"]
    assert pub["publisher"] == "orchestrator-publisher" and pub["publishId"] == r.publish_id and pub["outputFingerprint"] == r.record["outputFingerprint"]
    assert set(r.plan.updates) == {"brains/wind/health", "brains/wind/status", "brains/wind/publication"}      # child level only: nothing replaces /brains/wind
    live = DryRunStore({"brains": {"wind": {"health": "OLD", "certification": {"status": "IN_PROGRESS"}, "publication": {"publishId": "old"}, "unlisted": 7}}})
    live.update(r.plan.updates)                                                                  # test double only: proves merge semantics of the plan
    node = live.get("brains/wind")
    assert node["health"] == "HEALTHY" and node["status"] == "CALIBRATION" and node["certification"] == {"status": "IN_PROGRESS"} and node["unlisted"] == 7
    assert node["publication"]["publishId"] == r.publish_id


def test_atomic_patch_remains_deterministic_through_the_reference_flow():
    plans = []
    for _ in range(2):
        st = stack()
        art = wind_artifact(n=1); art["mutations"].reverse()
        art["lineage"]["outputFingerprint"] = output_fingerprint("wind", "wind-lake-state-v1", art["mutations"])
        plans.append(submit(st, art)[1].plan)
    assert plans[0].canonical() == plans[1].canonical() and plans[0].update_sha256 == plans[1].update_sha256


def test_shadow_reference_flow_has_no_live_capability():
    st = stack()
    r = submit(st, wind_artifact(n=1))[1]
    assert r.live_mutations == 0 and st.sink.live_mutations == 0 and r.record["live"] is False and r.record["status"] == "SHADOW" and "publishedAt" not in r.record
