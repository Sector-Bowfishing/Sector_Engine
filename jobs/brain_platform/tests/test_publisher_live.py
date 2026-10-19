"""Publisher LIVE V1: the live apply path against FAKE clients only. No production service, credential or network is touched."""
import copy
import json

import pytest

from gatep_fixtures import bundle, lake_section, registry_section, source_section
from live_rig import Rig
from publisher_fixtures import LAKE_A, LAKE_B
from sector_brain_platform import publication_trigger as PT
from sector_brain_platform.publisher_live import locks as LK
from sector_brain_platform.publisher_live.model import LiveResult, NoRollbackTarget

PUB = "brains/wind/publication"
STORES = ["memory", "gcs"]


def changed(n, minutes, speed):
    return bundle(n=n, minutes=minutes, sections=[lake_section(speed=speed), registry_section(), source_section()])


def same_content_new_run(n, minutes):
    return bundle(n=n, minutes=minutes)


@pytest.mark.parametrize("kind", STORES)
def test_nothing_is_enabled_by_default_and_a_denied_brain_writes_nothing(kind):
    r = Rig(brains=(), store_kind=kind)
    ref = r.ref(bundle())
    out = r.live.publish(ref)
    assert out.result is LiveResult.NOT_AUTHORIZED and r.rtdb.calls == 0 and r.rtdb.reads == []
    r2 = Rig(brains=("biological-state",))                       # authorised for a different Brain: still nothing for wind
    assert r2.live.publish(r2.ref(bundle())).result is LiveResult.NOT_AUTHORIZED and r2.rtdb.calls == 0


def test_first_live_publish_requires_a_deliberate_reconciled_baseline():
    r = Rig()
    ref = r.ref(bundle())
    out = r.live.publish(ref)
    assert out.result is LiveResult.BASELINE_UNRECONCILED and r.rtdb.calls == 0
    with pytest.raises(ValueError):
        from sector_brain_platform.publisher_live import baseline as BL
        BL.acknowledge(r.store, "wind", "wind-lake-state-v1", "lake-live", diff={"diffSha256": "x", "differing": [], "missingLive": [], "unplannedLive": []}, approval_ref=" ", now="t")
    diff = r.live.baseline_diff(ref)
    assert diff["missingLive"] and r.rtdb.calls == 0           # GET only
    r.reconcile(ref)
    assert r.live.publish(ref).result is LiveResult.PUBLISHED


@pytest.mark.parametrize("kind", STORES)
def test_publish_is_one_atomic_update_with_the_publication_record_and_matches_dry_run(kind):
    r = Rig(store_kind=kind)
    ref = r.ref(bundle())
    r.reconcile(ref)
    dry = r.live.dry_run(ref)
    assert dry.result is LiveResult.PUBLISHED and r.rtdb.calls == 0 and not r.store.list("publishes/wind/_locks/")
    out = r.live.publish(ref)
    assert out.result is LiveResult.PUBLISHED and out.mode == "SINGLE" and r.rtdb.calls == 1
    applied = dict(r.rtdb.updates[0])
    shown = dict(dry.updates)
    for d in (applied, shown):
        d[PUB] = {k: v for k, v in d[PUB].items() if k != "publishId"}                      # the only per-attempt difference: the attempt's own id
    assert applied == shown                                                                  # dry-run / live parity: the same data keys, values and publication record
    pub = r.rtdb.get(PUB)
    assert pub["status"] == "COMPLETE" and pub["live"] is True and pub["mode"] == "LIVE" and pub["artifactId"] == ref.artifact_id
    assert pub["outputFingerprint"] == out.record["outputFingerprint"] and "SHADOW" not in json.dumps(pub)
    assert out.score_signal == {"brainId": "wind", "artifactId": ref.artifact_id, "publishId": out.publish_id, "reason": "PUBLICATION_COMPLETE"}
    assert r.signals == [out.score_signal]
    for sec in ("wind-lake-state-v1", "wind-registry-v1", "wind-source-registry-v1"):
        assert r.history.head("wind", sec, next(s["scope"] for s in out.record["sections"] if s["artifactSchema"] == sec))["live"] is True


def test_unchanged_artifact_skips_with_no_live_write_and_no_score_signal():
    r = Rig()
    r.publish_first(bundle(n=1))
    before, tree = r.rtdb.calls, r.rtdb.snapshot()
    out = r.live.publish(r.ref(same_content_new_run(2, 30)))
    assert out.result is LiveResult.SKIP and r.rtdb.calls == before and r.rtdb.snapshot() == tree
    assert out.score_signal is None and len(r.signals) == 1
    assert PT.seen_token(r.rtdb.get("brains/wind")) == PT.seen_token(tree["brains"]["wind"])


def test_changed_artifact_publishes_moves_the_publication_marker_and_only_that_brains_score_token():
    other = {"brains": {"water-clarity": {"lastSuccessfulRun": "t0", "publication": {"artifactId": "keep", "status": "COMPLETE"}}}, "scores": {"wind": {"score": 3.3}}, "control": {"x": 1}}
    r = Rig(tree=other)
    r.publish_first(bundle(n=1))
    seen = {b: PT.seen_token(n) for b, n in r.rtdb.get("brains").items()}
    out = r.live.publish(r.ref(changed(2, 30, 9.0)))
    assert out.result is LiveResult.PUBLISHED and r.rtdb.get(PUB)["artifactId"] == out.record["artifactId"]
    assert PT.changed_brains(r.rtdb.get("brains"), seen) == ["wind"]                           # nobody else's score is triggered
    assert r.rtdb.get("scores") == other["scores"] and r.rtdb.get("control") == other["control"]
    assert r.rtdb.get("brains/water-clarity") == other["brains"]["water-clarity"]


def test_unrelated_paths_are_never_in_the_write_set_and_platform_paths_are_never_touched():
    tree = {"scores": {"wind": 1}, "control": {"a": 1}, "engine": {"score": 7}, "jobs": {"wind-hourly": {"x": 1}}, "health": {"jobs": {"wind-hourly": {"s": 1}}, "engine": {"x": 1}},
            "species": {"s1": {"a": 1}}, "lakes": {"other_lake": {"states": {"wind": {"windMS": 1}}}}}
    r = Rig(tree=tree)
    r.publish_first(bundle())
    keys = r.rtdb.write_keys()
    assert keys and all(k.split("/")[0] in ("lakes", "lakeFleet", "brains", "validation", "health", "sources", "snapshots", "activity") for k in keys)
    assert not [k for k in keys if k.split("/")[0] in ("scores", "control", "engine", "jobs", "species") or k.startswith(("health/jobs", "health/engine"))]
    for root in ("scores", "control", "engine", "jobs", "species"):
        assert r.rtdb.get(root) == tree[root]
    assert r.rtdb.get("lakes/other_lake") == tree["lakes"]["other_lake"]


@pytest.mark.parametrize("path,code", [("/scores/wind", None), ("/control/healthV1/x", None), ("/jobs/wind-hourly", None), ("/engine/score", None),
                                       ("/brains/wind/publication", None), ("/brains/water-clarity/status", None), ("/health/jobs/wind-hourly", None)])
def test_artifacts_targeting_protected_or_foreign_paths_are_rejected_before_any_live_io(path, code):
    r = Rig()
    art = bundle(sections=[lake_section(), registry_section(), source_section(extra=[{"op": "SET", "path": path, "value": {"a": 1}}])])
    ref = r.ref(art)
    r.reconcile(r.ref(bundle(n=5)))
    out = r.live.publish(ref)
    assert out.result in (LiveResult.REJECTED, LiveResult.FAILED_VALIDATION) and r.rtdb.calls == 0 and r.rtdb.get(PUB) is None


def test_a_definite_apply_failure_leaves_the_previous_release_authoritative_and_a_retry_succeeds():
    r = Rig()
    r.publish_first(bundle(n=1))
    a1 = r.rtdb.get(PUB)["artifactId"]
    ref2 = r.ref(changed(2, 30, 8.0))
    r.rtdb.inject("definite")
    out = r.live.publish(ref2)
    assert out.result is LiveResult.APPLY_FAILED and r.rtdb.get(PUB)["artifactId"] == a1
    assert len(r.signals) == 1 and not LK.quarantined(r.store, "wind")
    assert r.history.head("wind", "wind-lake-state-v1", "lake-live")["artifactId"] == a1
    assert r.live.publish(ref2).result is LiveResult.PUBLISHED and r.rtdb.get(PUB)["artifactId"] == ref2.artifact_id


def test_a_lost_response_after_commit_is_verified_by_readback_not_assumed():
    r = Rig()
    r.publish_first(bundle(n=1))
    r.rtdb.inject("ambiguous_after")
    out = r.live.publish(r.ref(changed(2, 30, 8.0)))
    assert out.result is LiveResult.PUBLISHED and r.rtdb.get(PUB)["artifactId"] == out.record["artifactId"]
    r2 = Rig()
    r2.publish_first(bundle(n=1))
    r2.rtdb.inject("ambiguous_before")                           # the request never landed
    out2 = r2.live.publish(r2.ref(changed(2, 30, 8.0)))
    assert out2.result is LiveResult.APPLY_FAILED and r2.rtdb.get(PUB)["artifactId"] != out2.record["artifactId"]


def test_idempotent_recovery_when_a_verified_apply_was_not_followed_by_a_head_advance():
    r = Rig()
    r.publish_first(bundle(n=1))
    ref2 = r.ref(changed(2, 30, 8.0))
    real = r.history.advance_head
    r.history.advance_head = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("process died"))
    with pytest.raises(RuntimeError):
        r.live.publish(ref2)
    r.history.advance_head = real
    assert not (r.store.get(LK.lock_key("wind")) and json.loads(r.store.get(LK.lock_key("wind")))["state"] == "HELD")
    calls = r.rtdb.calls
    out = r.live.publish(ref2)
    assert out.result is LiveResult.RECOVERED and r.rtdb.calls == calls                         # finalised without a second live write
    assert r.history.head("wind", "wind-lake-state-v1", "lake-live")["artifactId"] == ref2.artifact_id
    assert r.live.publish(ref2).result is LiveResult.SKIP


def test_a_readback_mismatch_quarantines_the_brain_and_rollback_is_the_way_out():
    r = Rig()
    r.publish_first(bundle(n=1))
    first = r.rtdb.get(PUB)
    good_tree = r.rtdb.snapshot()
    r.rtdb.corrupt_after_apply = lambda t: t["lakes"][LAKE_A]["states"]["wind"].update(windMS=99)
    out = r.live.publish(r.ref(changed(2, 30, 8.0)))
    assert out.result is LiveResult.READBACK_MISMATCH and LK.quarantined(r.store, "wind") and out.mismatched
    assert len(r.signals) == 1                                                       # a mismatching publication never signals the scorer
    r.rtdb.corrupt_after_apply = None
    assert r.live.publish(r.ref(changed(3, 40, 7.0))).result is LiveResult.QUARANTINED
    rb = r.live.rollback("wind", out.publish_id, approval_ref="approval/rb/2", reason="readback mismatch")
    assert rb.result is LiveResult.ROLLED_BACK and not LK.quarantined(r.store, "wind")
    assert r.rtdb.get(PUB)["artifactId"] == first["artifactId"] and r.rtdb.get(f"lakes/{LAKE_A}/states/wind") == good_tree["lakes"][LAKE_A]["states"]["wind"]
    assert r.live.publish(r.ref(changed(4, 60, 7.0))).result is LiveResult.PUBLISHED


def test_precondition_live_state_changed_by_someone_else_refuses_the_publish():
    r = Rig()
    r.publish_first(bundle(n=1))
    r.rtdb.update({PUB + "/artifactId": "legacy-writer-wrote-here"})
    calls = r.rtdb.calls
    out = r.live.publish(r.ref(changed(2, 30, 8.0)))
    assert out.result is LiveResult.PRECONDITION_FAILED and r.rtdb.calls == calls


def test_concurrent_publish_is_serialised_by_the_apply_lock():
    r = Rig()
    ref, _ = r.publish_first(bundle(n=1))
    LK.acquire(r.store, "wind", "someone-else", "t")
    out = r.live.publish(r.ref(changed(2, 30, 8.0)))
    assert out.result is LiveResult.LOCK_BUSY
    LK.break_lock(r.store, "wind", "operator verified live state", "t")
    assert r.live.publish(r.ref(changed(2, 30, 8.0))).result is LiveResult.PUBLISHED
    with pytest.raises(ValueError):
        LK.break_lock(r.store, "wind", " ", "t")


def big_changed(n, minutes, speed):
    return bundle(n=n, minutes=minutes, sections=[lake_section(speed=speed, lakes=tuple(f"synthetic_lake_{i:03d}" for i in range(40))), registry_section(), source_section()])


def test_oversize_plans_are_applied_manifest_last_and_a_mid_failure_keeps_the_previous_release_authoritative():
    r = Rig()
    r.publish_first(big_changed(1, 0, 4.0))
    a1 = r.rtdb.get(PUB)["artifactId"]
    small = r.with_limit(2500)
    ref2 = r.ref(big_changed(2, 30, 8.0))
    small.rtdb.inject("definite", nth=3)                         # call1 = pending marker, call2 = chunk 1, call3 = chunk 2 fails
    out = small.live.publish(ref2)
    assert out.result is LiveResult.APPLY_FAILED
    pub = r.rtdb.get(PUB)
    assert pub["artifactId"] == a1 and pub["status"] == "COMPLETE" and pub["pending"]["artifactId"] == ref2.artifact_id     # previous release still authoritative
    assert r.history.head("wind", "wind-lake-state-v1", "lake-live")["artifactId"] == a1
    assert small.live.publish(r.ref(big_changed(3, 40, 6.0))).result is LiveResult.PRECONDITION_FAILED                    # a DIFFERENT artifact cannot jump the interrupted one
    done = small.live.publish(ref2)                              # same artifact resumes (idempotent)
    assert done.result is LiveResult.PUBLISHED and done.mode == "CHUNKED" and done.calls >= 4
    pub = r.rtdb.get(PUB)
    assert pub["artifactId"] == ref2.artifact_id and "pending" not in pub
    assert list(r.rtdb.updates[-1]) == [PUB]                     # the publication marker is the LAST write and travels alone


def test_rollback_restores_the_previous_publication_removes_new_paths_and_retriggers_scoring():
    r = Rig()
    r.publish_first(bundle(n=1))
    first = r.rtdb.get(PUB)
    third_lake = lake_section(speed=8.0, lakes=(LAKE_A, LAKE_B, "synthetic_extra_lake"))
    out = r.live.publish(r.ref(bundle(n=2, minutes=30, sections=[third_lake, registry_section(), source_section()])))
    assert out.result is LiveResult.PUBLISHED and r.rtdb.get("lakes/synthetic_extra_lake/states/wind") is not None
    token_b = PT.seen_token(r.rtdb.get("brains/wind"))
    with pytest.raises(ValueError):
        r.live.rollback("wind", out.publish_id, approval_ref="", reason="x")
    rb = r.live.rollback("wind", out.publish_id, approval_ref="approval/rollback/1", reason="bad release")
    assert rb.result is LiveResult.ROLLED_BACK
    assert r.rtdb.get("lakes/synthetic_extra_lake/states/wind") is None and r.rtdb.get("lakes/synthetic_extra_lake") is None            # inverse operation for new paths
    assert r.rtdb.get(f"lakes/{LAKE_A}/states/wind")["windMS"] == 4.2
    pub = r.rtdb.get(PUB)
    assert pub["artifactId"] == first["artifactId"] and pub["status"] == "COMPLETE" and pub["rollback"]["fromPublishId"] == out.publish_id
    assert PT.seen_token(r.rtdb.get("brains/wind")) != token_b and r.signals[-1]["artifactId"] == first["artifactId"]
    assert r.history.head("wind", "wind-lake-state-v1", "lake-live")["artifactId"] == first["artifactId"]
    assert r.live.publish(r.ref(changed(3, 60, 5.0))).result is LiveResult.PUBLISHED          # a newer artifact still publishes after a rollback


def test_the_first_live_publication_has_no_artifact_to_roll_back_to():
    r = Rig()
    _, out = r.publish_first(bundle(n=1))
    with pytest.raises(NoRollbackTarget):
        r.live.rollback("wind", out.publish_id, approval_ref="approval/rb", reason="pre-cutover state is restored from the private RTDB export, not from an artifact")


def test_rejected_and_failed_attempts_never_trigger_scoring_or_move_heads():
    r = Rig()
    r.publish_first(bundle(n=1))
    n_signals, head = len(r.signals), r.history.head("wind", "wind-lake-state-v1", "lake-live")
    bad = bundle(n=2, minutes=30, lifecycle="PRODUCTION")
    out = r.live.publish(r.ref(bad))
    assert out.result in (LiveResult.REJECTED, LiveResult.FAILED_VALIDATION) and len(r.signals) == n_signals
    assert r.history.head("wind", "wind-lake-state-v1", "lake-live") == head
    older = r.live.publish(r.ref(bundle(n=3, minutes=-30, sections=[lake_section(speed=1.0), registry_section(), source_section()])))
    assert older.result is LiveResult.REJECTED and "ARTIFACT_OLDER_THAN_BASELINE" in older.codes


def test_the_gcs_adapter_has_the_object_store_contract_and_no_delete():
    from sector_brain_platform.publisher.storage import PreconditionFailed
    from sector_brain_platform.publisher_live.fakes import FakeBucket
    from sector_brain_platform.publisher_live.gcs_store import GcsObjectStore
    b = FakeBucket()
    s = GcsObjectStore(b)
    assert s.generation("publishes/x/a.json") == 0 and s.get("publishes/x/a.json") is None
    g1 = s.put("publishes/x/a.json", b"1", if_generation_match=0)
    with pytest.raises(PreconditionFailed):
        s.put("publishes/x/a.json", b"2", if_generation_match=0)                     # create-only
    g2 = s.put("publishes/x/a.json", b"2", if_generation_match=g1)
    with pytest.raises(PreconditionFailed):
        s.put("publishes/x/a.json", b"3", if_generation_match=g1)                    # stale generation
    assert s.get("publishes/x/a.json") == b"2" and s.get("publishes/x/a.json", g1) == b"1" and g2 != g1       # history stays readable
    assert not hasattr(s, "delete") and b.deletes == 0
    assert s.list("publishes/x/") == ["publishes/x/a.json"]
    with pytest.raises(PermissionError):
        GcsObjectStore.from_bucket_name("any-bucket")                                 # not armed


def test_release_resolver_verifies_hash_and_release_identity_and_fails_closed():
    import hashlib
    from sector_brain_platform.publisher_live.release_resolver import ManifestReleaseResolver
    body = json.dumps({"researchVersion": "2026-10-17.1", "files": []}).encode()
    sha = "sha256:" + hashlib.sha256(body).hexdigest()
    ok = ManifestReleaseResolver(lambda ref: {"gs://private/releases/2026-10-17.1/manifest.json": body}.get(ref))
    ref = "gs://private/releases/2026-10-17.1/manifest.json"
    assert ok("2026-10-17.1", ref, sha)
    assert not ok("2026-10-14.4", ref, sha)                                  # manifest names a different release
    assert not ok("2026-10-17.1", ref, "sha256:" + "0" * 64)                 # hash mismatch
    assert not ok("2026-10-17.1", "gs://private/missing", sha)               # unreadable
    assert not ManifestReleaseResolver(lambda r: (_ for _ in ()).throw(OSError("denied")))("2026-10-17.1", ref, sha)
    assert not ManifestReleaseResolver(lambda r: b"not json")("x", ref, "sha256:" + hashlib.sha256(b"not json").hexdigest())
    assert not ManifestReleaseResolver(lambda r: b'{"files": []}')("x", ref, "sha256:" + hashlib.sha256(b'{"files": []}').hexdigest())     # no release identity at all
