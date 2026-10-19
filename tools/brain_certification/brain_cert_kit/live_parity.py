"""LIVE-PARITY proofs (PRODUCTION CUTOVER CERTIFICATION, offline portion) — deliberately NOT part of the 19 structural proofs.

Structural certification asks "is this Brain correctly shaped and shadow-compatible?". These proofs ask "could the LIVE Publisher publish this Brain's real artifact
correctly?", using the Brain's own artifact factories against FAKE clients only (fake RTDB, in-memory/fake-GCS store). They prove the repository half of
PRODUCTION_EXIT_GATE_V1; the LIVE half (real database readback, real write-denial under rules and IAM) can only happen at an approved cutover.

    from brain_cert_kit.live_parity import make_live_parity_tests
    globals().update(make_live_parity_tests(SPEC))          # in brains/<dir>/tests/test_<brain>_live_parity.py
"""
from __future__ import annotations

import copy
import datetime as dt

import pytest

from .env import Env, GEN

LATER = ("2026-10-12T07:30:00Z", "2026-10-12T08:30:00Z", "2026-10-12T09:30:00Z", "2026-10-12T10:30:00Z")
CLOCK = dt.datetime(2026, 10, 15, 4, 0, tzinfo=dt.timezone.utc)
PARITY_TESTS = (
    "test_live_parity_artifact_publishes_with_correct_identity_and_metadata",
    "test_live_parity_identity_schema_and_lifecycle_are_enforced",
    "test_live_parity_plan_stays_inside_the_brains_families_and_protected_paths_are_rejected",
    "test_live_parity_fingerprint_is_deterministic_and_unchanged_artifacts_skip",
    "test_live_parity_changed_artifact_publishes_with_readback_and_score_signal",
    "test_live_parity_unrelated_brains_and_platform_paths_are_untouched",
    "test_live_parity_health_and_score_ownership_are_preserved",
    "test_live_parity_oversize_plan_is_manifest_last_and_failure_keeps_the_previous_release",
    "test_live_parity_rollback_restores_the_previous_state_exactly",
    "test_live_parity_legacy_writer_reentry_is_detected_and_reserved_children_survive",
)


def make_live_parity_tests(spec) -> dict:
    spec.validate()
    from sector_brain_platform import publication_trigger as PT
    from sector_brain_platform.publisher_live import LiveResult
    from sector_brain_platform.publisher_live.rig import Rig
    from sector_brain_platform.publisher_live import security_model as SM
    from sector_brain_platform.publisher.storage import AccessDenied

    bid = spec.brain_id
    pub_key = f"brains/{bid}/publication"
    out: dict = {}

    def rig(**kw):
        return Rig(brains=(bid,), clock=CLOCK, **kw)

    def art(n, minutes=0, changed=False):
        t = LATER[minutes - 1] if minutes else GEN
        return spec.changed_artifact_factory(n, t) if changed else spec.artifact_factory(n, t, None, False)

    def strip(tree):
        t = copy.deepcopy(tree)
        t.get("brains", {}).get(bid, {}).pop("publication", None)
        return t

    def first(r):
        ref, res = r.publish_first(art(1))
        assert res.result is LiveResult.PUBLISHED, (res.result, res.codes, res.detail)
        return ref, res

    def case(fn):
        out[fn.__name__] = fn
        return fn

    @case
    def test_live_parity_artifact_publishes_with_correct_identity_and_metadata():
        r = rig()
        ref, res = first(r)
        pub = r.rtdb.get(pub_key)
        assert pub["brainId"] == bid and pub["artifactId"] == ref.artifact_id and pub["status"] == "COMPLETE" and pub["live"] is True and pub["mode"] == "LIVE"
        assert pub["outputFingerprint"] == res.record["outputFingerprint"] and pub["lifecycle"] == spec.lifecycle and "SHADOW" not in str(pub)
        assert r.rtdb.calls == 1, "the whole plan, including the publication record, is ONE atomic update"
        assert pub_key in r.rtdb.updates[0]

    @case
    def test_live_parity_identity_schema_and_lifecycle_are_enforced():
        env = Env(spec)
        r = rig()
        r.reconcile(r.ref(art(1)))
        other = env.other_registered_brains()
        assert other
        wrong_brain = env.sealed([{"op": "SET", "path": f"/brains/{bid}/version", "value": "x"}], brain_id=other[0], bundle_id=env.bundle_id_of(other[0]))
        # an artifact whose lineage names another Brain cannot even be written into this Brain's artifact prefix
        with pytest.raises(AccessDenied):
            r.ref(wrong_brain, brain=bid)
        prod = env.sealed([{"op": "SET", "path": f"/brains/{bid}/version", "value": "x"}], lifecycle="PRODUCTION")
        bad = r.live.publish(r.ref(prod))
        assert bad.result in (LiveResult.REJECTED, LiveResult.FAILED_VALIDATION) and r.rtdb.calls == 0
        unknown = env.sealed([{"op": "SET", "path": f"/brains/{bid}/version", "value": "x"}], schema="not-a-registered-schema-v1")
        bad2 = r.live.publish(r.ref(unknown))
        assert bad2.result in (LiveResult.REJECTED, LiveResult.FAILED_VALIDATION) and r.rtdb.calls == 0

    @case
    def test_live_parity_plan_stays_inside_the_brains_families_and_protected_paths_are_rejected():
        env = Env(spec)
        r = rig()
        first(r)
        keys = r.rtdb.write_keys()
        assert keys and all(k.startswith(spec.plan_root_prefixes) or k == pub_key for k in keys), [k for k in keys if not k.startswith(spec.plan_root_prefixes)]
        assert all(SM.publisher_key_allowed(bid, k) for k in keys)
        calls = r.rtdb.calls
        protected = [(f"/scores/{bid}", None), ("/control/healthV1/x", None), ("/jobs/x", None), ("/engine/score", None), (f"/brains/{bid}/publication", None),
                     (f"/brains/{bid}/certification", None), (f"/brains/{bid}", None)] + [(x.path, x.code) for x in spec.extra_rejections]
        for path, code in protected:
            res = r.live.publish(r.ref(env.sealed([{"op": "SET", "path": path, "value": {"a": 1}}])))
            assert res.result in (LiveResult.REJECTED, LiveResult.FAILED_VALIDATION), (path, res.result)
            if code:
                assert code in res.codes, (path, code, res.codes)
        assert r.rtdb.calls == calls, "a rejected artifact performs no live write"

    @case
    def test_live_parity_fingerprint_is_deterministic_and_unchanged_artifacts_skip():
        a, b = art(1), art(2, 1)
        assert a["lineage"]["outputFingerprint"] == b["lineage"]["outputFingerprint"] != spec.changed_artifact_factory(3, LATER[1])["lineage"]["outputFingerprint"]
        r = rig()
        first(r)
        calls, tree = r.rtdb.calls, r.rtdb.snapshot()
        res = r.live.publish(r.ref(b))
        assert res.result is LiveResult.SKIP and r.rtdb.calls == calls and r.rtdb.snapshot() == tree and res.score_signal is None and len(r.signals) == 1

    @case
    def test_live_parity_changed_artifact_publishes_with_readback_and_score_signal():
        r = rig(tree={"brains": {"some-other-brain": {"lastSuccessfulRun": "t", "publication": {"artifactId": "keep", "status": "COMPLETE"}}}})
        first(r)
        seen = {b: PT.seen_token(n) for b, n in r.rtdb.get("brains").items()}
        ref = r.ref(art(3, 2, changed=True))
        res = r.live.publish(ref)
        assert res.result is LiveResult.PUBLISHED and r.rtdb.get(pub_key)["artifactId"] == ref.artifact_id
        assert res.score_signal["brainId"] == bid and res.score_signal["artifactId"] == ref.artifact_id
        assert PT.changed_brains(r.rtdb.get("brains"), seen) == [bid]
        # authoritative readback: every planned key now holds the artifact's value
        from sector_brain_platform.publisher_live import apply as AP
        assert AP.readback(r.rtdb, {k: v for k, v in res.updates.items()}) == []

    @case
    def test_live_parity_unrelated_brains_and_platform_paths_are_untouched():
        tree = {"scores": {bid: {"score": 1.0}}, "control": {"c": 1}, "engine": {"score": 7}, "jobs": {"j": {"x": 1}}, "health": {"jobs": {"j": {"s": 1}}},
                "brains": {"unrelated": {"status": "KEEP"}}, "lakes": {"unrelated_lake": {"states": {"zzz": {"v": 1}}}}}
        r = rig(tree=copy.deepcopy(tree))
        first(r)
        r.live.publish(r.ref(art(3, 2, changed=True)))
        for root in ("scores", "control", "engine", "jobs"):
            assert r.rtdb.get(root) == tree[root]
        assert r.rtdb.get("health/jobs") == tree["health"]["jobs"] and r.rtdb.get("brains/unrelated") == tree["brains"]["unrelated"]
        assert r.rtdb.get("lakes/unrelated_lake") == tree["lakes"]["unrelated_lake"]

    @case
    def test_live_parity_health_and_score_ownership_are_preserved():
        r = rig()
        first(r)
        keys = r.rtdb.write_keys()
        assert not [k for k in keys if k.startswith(("health/jobs", "health/engine", "health/rtdb", "scores", "control", "engine", "jobs"))]
        assert not [k for k in keys if k.startswith(f"health/brains/{bid}/") and k.split("/")[-1] in SM.TARGET_ORCHESTRATOR_HEALTH_FIELDS], "process health belongs to the Orchestrator"
        assert not [k for k in keys if k == f"brains/{bid}/score"]
        assert r.rtdb.get("scores") is None, "the Publisher never creates or changes a score"

    @case
    def test_live_parity_oversize_plan_is_manifest_last_and_failure_keeps_the_previous_release():
        r = rig()
        first(r)
        prev = r.rtdb.get(pub_key)["artifactId"]
        ref = r.ref(art(3, 2, changed=True))
        size = len(str(r.live.dry_run(ref).updates))
        small = r.with_limit(max(200, size // 6))
        assert small.live.dry_run(ref).mode == "CHUNKED"
        small.rtdb.inject("definite", nth=3)
        res = small.live.publish(ref)
        assert res.result is LiveResult.APPLY_FAILED
        pub = r.rtdb.get(pub_key)
        assert pub["artifactId"] == prev and pub["status"] == "COMPLETE", "previous release stays authoritative until the marker lands"
        done = small.live.publish(ref)
        assert done.result is LiveResult.PUBLISHED and done.mode == "CHUNKED"
        assert list(r.rtdb.updates[-1]) == [pub_key] and r.rtdb.get(pub_key)["artifactId"] == ref.artifact_id

    @case
    def test_live_parity_rollback_restores_the_previous_state_exactly():
        r = rig()
        first(r)
        before = strip(r.rtdb.snapshot())
        res = r.live.publish(r.ref(art(3, 2, changed=True)))
        assert res.result is LiveResult.PUBLISHED and strip(r.rtdb.snapshot()) != before
        rb = r.live.rollback(bid, res.publish_id, approval_ref="approval/rollback/test", reason="parity rehearsal")
        assert rb.result is LiveResult.ROLLED_BACK
        assert strip(r.rtdb.snapshot()) == before, "rollback is the exact inverse of the publication (new paths removed, old values restored)"
        assert r.rtdb.get(pub_key)["rollback"]["fromPublishId"] == res.publish_id
        assert r.live.publish(r.ref(art(4, 3, changed=True))).result is LiveResult.PUBLISHED

    @case
    def test_live_parity_legacy_writer_reentry_is_detected_and_reserved_children_survive():
        r = rig(tree={"brains": {bid: {"certification": {"standard": "brain-certification-v1", "status": "PARTIAL"}}}})
        first(r)
        r.live.publish(r.ref(art(3, 2, changed=True)))
        assert r.rtdb.get(f"brains/{bid}/certification") == {"standard": "brain-certification-v1", "status": "PARTIAL"}, "child-level writes never erase a reserved child"
        keys = r.rtdb.write_keys()
        assert f"brains/{bid}" not in keys and f"health/brains/{bid}" not in keys, "the Publisher never replaces a whole Brain node"
        # a legacy WHOLE-NODE write (what the old writers do) erases the Publisher-owned publication record...
        r.rtdb.update({f"brains/{bid}": {"version": "legacy", "status": "X"}})
        assert r.rtdb.get(pub_key) is None
        calls = r.rtdb.calls
        res = r.live.publish(r.ref(art(4, 3)))            # content differs from the published head (back to the base state), so this is a real change
        # ...and the Publisher notices and refuses to build on a state it did not write (fail closed)
        assert res.result is LiveResult.PRECONDITION_FAILED and r.rtdb.calls == calls

    assert tuple(out) == PARITY_TESTS, tuple(out)
    return out
