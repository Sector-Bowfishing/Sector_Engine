"""Orchestrator publication coordination (Cortex 3.1 PL-19 / FD-15), against FAKE clients only: no production database, bucket, credential or service is touched."""
import datetime as dt
import json

import pytest

from live_rig import Rig
from publisher_fixtures import T0, make, wind_artifact
from sector_brain_platform import data_ownership as DO
from sector_brain_platform.publication_coordination import PublicationCoordinator, PublicationLedger
from sector_brain_platform.publisher.canonical import sha256_ref
from sector_brain_platform.publisher.refs import ArtifactRef, artifact_location
from sector_brain_platform.publisher_live.model import LiveResult
from sector_brain_platform.publisher_live.publisher import LivePublishResult

CLOCK = {"t": T0 + dt.timedelta(hours=1)}


def clock():
    return CLOCK["t"]


def stack(brains=("wind",), cutover=(), armed=True, path=None):
    r = Rig(brains=brains)
    shadow, _, _ = make(store=r.store)
    ledger = PublicationLedger(path)
    co = PublicationCoordinator(ledger, r.store, shadow=shadow, live=r.live if armed else None, cutover=cutover, clock=clock)
    return r, co, ledger


def write(r, n=1, **kw):
    ref = r.ref(wind_artifact(n=n, **kw))
    return ref


def test_pre_cutover_a_passing_shadow_is_not_a_publication_and_nothing_is_written():
    r, co, _ = stack(cutover=())
    ref = write(r)
    rec = co.process(ref)
    assert rec["artifact"]["state"] == "COLLECTED" and rec["artifact"]["digest"] == ref.sha256 and rec["artifact"]["schema"] == "wind-lake-state-v1"
    assert rec["shadow"]["checked"] and rec["shadow"]["result"] == "SHADOW_READY" and rec["shadow"]["live"] is False
    assert rec["writePath"] == "DIRECT_WRITE_PRE_CUTOVER"
    assert rec["publication"]["outcome"] == "NOT_REQUESTED" and rec["publication"]["reason"] == "DIRECT_WRITER_ACTIVE" and rec["publication"]["requested"] is False
    assert r.rtdb.updates == [] and r.rtdb.calls == 0                        # no RTDB write of any kind
    assert co.summary()["brains"]["wind"]["published"] == 0 and co.summary()["brains"]["wind"]["directWriter"] is True


def test_an_unarmed_publisher_is_never_asked_even_after_cutover_is_declared():
    r, co, _ = stack(cutover=("wind",), armed=False)
    rec = co.process(write(r))
    assert rec["publication"]["outcome"] == "NOT_REQUESTED" and rec["publication"]["reason"] == "PUBLISHER_UNARMED"
    assert r.rtdb.updates == []


def test_armed_publisher_publishes_once_records_readback_and_a_retry_never_duplicates():
    r, co, ledger = stack(cutover=("wind",))
    ref = write(r)
    r.reconcile(ref)                                                         # baseline acknowledged (Publisher precondition)
    rec = co.process(ref)
    p = rec["publication"]
    assert p["outcome"] == "PUBLISHED" and p["reason"] == "PUBLISHED" and p["readback"]["verified"] is True and p["livePublishId"] and p["attempts"] == 1
    assert rec["writePath"] == "PUBLISHER"
    calls = r.rtdb.calls
    again = co.process(ref)                                                  # the same artifact reported again
    assert again["publication"]["attempts"] == 1 and r.rtdb.calls == calls and len(ledger.records()) == 1
    assert co.resume() == {"shadowed": 0, "requested": 0, "retried": 0} and r.rtdb.calls == calls


def test_same_content_in_a_new_run_is_skipped_not_republished():
    r, co, _ = stack(cutover=("wind",))
    a = write(r, n=1)
    r.reconcile(a)
    co.process(a)
    calls = r.rtdb.calls
    b = write(r, n=2, minutes=5)                                             # new run, new artifact id, identical scientific content
    rec = co.process(b)
    assert rec["publication"]["outcome"] == "SKIPPED" and r.rtdb.calls == calls and rec["publication"]["readback"] is None


def test_a_brain_without_live_authorization_is_rejected_by_the_publisher_and_recorded():
    r, co, _ = stack(brains=(), cutover=("wind",))
    rec = co.process(write(r))
    assert rec["publication"]["outcome"] == "REJECTED" and rec["publication"]["reason"] == "NOT_AUTHORIZED" and rec["publication"]["retryable"] is False
    assert r.rtdb.updates == []


class Scripted:
    """A stand-in live publisher that returns scripted results (for failure, backoff and ambiguity paths)."""

    def __init__(self, *results):
        self.results, self.calls = list(results), 0

    def publish(self, ref):
        self.calls += 1
        x = self.results.pop(0)
        if isinstance(x, Exception):
            raise x
        return LivePublishResult(x, record={"publishId": f"p{self.calls}"}, codes=["C"], detail="d", mismatched=["/x"] if x == LiveResult.READBACK_MISMATCH else [])


def scripted_stack(*results, **kw):
    r = Rig(brains=("wind",))
    shadow, _, _ = make(store=r.store)
    sc = Scripted(*results)
    co = PublicationCoordinator(PublicationLedger(), r.store, shadow=shadow, live=sc, cutover=("wind",), clock=clock, **kw)
    return r, co, sc


def test_retryable_failure_backs_off_then_succeeds_without_a_duplicate():
    CLOCK["t"] = T0 + dt.timedelta(hours=1)
    r, co, sc = scripted_stack(LiveResult.APPLY_FAILED, LiveResult.RECOVERED)
    ref = write(r)
    rec = co.process(ref)
    assert rec["publication"]["outcome"] == "FAILED" and rec["publication"]["retryable"] is True and rec["publication"]["nextAttemptAfter"]
    co.request_publication(rec["key"])                                       # too early: backoff
    assert sc.calls == 1
    CLOCK["t"] += dt.timedelta(minutes=6)
    rec = co.request_publication(rec["key"])
    assert rec["publication"]["outcome"] == "PUBLISHED" and rec["publication"]["recovered"] is True and rec["publication"]["attempts"] == 2 and sc.calls == 2
    co.request_publication(rec["key"])
    assert sc.calls == 2                                                     # final: never submitted again


def test_retries_are_bounded_and_ambiguous_exceptions_are_failures_not_publications():
    CLOCK["t"] = T0 + dt.timedelta(hours=1)
    r, co, sc = scripted_stack(RuntimeError("boom"), LiveResult.LOCK_BUSY, LiveResult.APPLY_FAILED, LiveResult.PUBLISHED)
    rec = co.process(write(r))
    for _ in range(4):
        CLOCK["t"] += dt.timedelta(hours=1)
        rec = co.request_publication(rec["key"])
    p = rec["publication"]
    assert p["outcome"] == "FAILED" and p["reason"] == "RETRIES_EXHAUSTED" and p["retryable"] is False and p["attempts"] == 3 and sc.calls == 3


@pytest.mark.parametrize("result,outcome,retryable", [(LiveResult.READBACK_MISMATCH, "FAILED", False), (LiveResult.QUARANTINED, "FAILED", False), (LiveResult.BASELINE_UNRECONCILED, "FAILED", False),
                                                       (LiveResult.REJECTED, "REJECTED", False), (LiveResult.FAILED_VALIDATION, "REJECTED", False), (LiveResult.SKIP, "SKIPPED", False)])
def test_every_live_result_maps_to_one_outcome(result, outcome, retryable):
    CLOCK["t"] = T0 + dt.timedelta(hours=1)
    r, co, _ = scripted_stack(result)
    rec = co.process(write(r))
    assert rec["publication"]["outcome"] == outcome and bool(rec["publication"].get("retryable")) is retryable and rec["publication"]["reason"] == result.value
    if result == LiveResult.READBACK_MISMATCH:
        assert rec["publication"]["readback"] == {"verified": False, "mismatched": ["/x"]}


def test_a_failed_shadow_means_the_publisher_is_not_asked():
    r, co, sc = scripted_stack(LiveResult.PUBLISHED)
    bad = wind_artifact(n=1, mutations=[{"op": "SET", "path": "/lakes/Probe/states/lake", "value": {"x": 1}}])        # a wind artifact writing the Lake slot: ownership violation
    ref = r.ref(bad)
    rec = co.process(ref)
    assert rec["shadow"]["result"] in ("REJECTED", "FAILED_VALIDATION", "ERROR") and rec["publication"]["outcome"] == "NOT_REQUESTED" and rec["publication"]["reason"].startswith("SHADOW_") and sc.calls == 0


def test_tampered_or_mismatching_artifacts_are_invalid_never_published():
    r, co, sc = scripted_stack(LiveResult.PUBLISHED)
    ref = write(r)
    bad = ArtifactRef(ref.brain_id, ref.artifact_id, ref.location, "sha256:" + "0" * 64, ref.execution_id, ref.expected_schema)
    rec = co.process(bad)
    assert rec["artifact"]["state"] == "INVALID" and "DIGEST_MISMATCH" in rec["artifact"]["problems"] and sc.calls == 0
    wrong = ArtifactRef(ref.brain_id, ref.artifact_id, ref.location, ref.sha256, ref.execution_id, "wind-other-v1")
    assert co.collect(wrong)["artifact"]["state"] == "INVALID"


def ex(run_id, status="SUCCEEDED", brain="wind", start=T0, mins=10):
    return {"executionId": run_id, "brainId": brain, "status": status, "startedAt": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "endedAt": (start + dt.timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def test_cloud_run_reconcile_collects_by_execution_id_flags_missing_and_failed_runs():
    r, co, _ = scripted_stack()
    ref = write(r, n=1)
    lin = json.loads(r.store.get(ref.location))["lineage"]
    out = co.reconcile([ex(lin["executionId"]), ex("11111111-1111-4111-8111-111111111111"), ex("22222222-2222-4222-8222-222222222222", "FAILED"), ex("33333333-3333-4333-8333-333333333333", "RUNNING")])
    assert len(out["collected"]) == 1 and [m["runId"] for m in out["missing"]] == ["11111111-1111-4111-8111-111111111111"] and len(out["failedRuns"]) == 1
    s = co.summary()["brains"]["wind"]
    assert s["missingArtifacts"] == 1 and s["published"] == 0 and any(p["reason"] == "ARTIFACT_MISSING" for p in s["problems"])
    assert co.reconcile([ex(lin["executionId"])])["alreadyKnown"] == 1                           # reconciling twice changes nothing


def test_cloud_run_reconcile_falls_back_to_the_execution_window_and_labels_it():
    r, co, _ = scripted_stack()
    ref = write(r, n=1, minutes=3, executionId="44444444-4444-4444-8444-444444444444")                # generated inside the window, different execution id
    out = co.reconcile([ex("cloudrun-exec-1", start=T0)])
    assert len(out["collected"]) == 1 and co.ledger.get(out["collected"][0])["matchBasis"] == "TIME_WINDOW"


def test_an_interrupted_coordinator_resumes_from_the_persisted_ledger_and_publishes_exactly_once(tmp_path):
    path = str(tmp_path / "ledger.json")
    r, co, _ = stack(cutover=("wind",), path=path)
    ref = write(r)
    r.reconcile(ref)
    co.collect(ref)                                                          # ... the process dies here, before shadow and request
    r2 = PublicationCoordinator(PublicationLedger(path), r.store, shadow=make(store=r.store)[0], live=r.live, cutover=("wind",), clock=clock)
    assert r2.resume() == {"shadowed": 1, "requested": 1, "retried": 0}
    rec = r2.ledger.records()[0]
    assert rec["publication"]["outcome"] == "PUBLISHED"
    calls = r.rtdb.calls
    r3 = PublicationCoordinator(PublicationLedger(path), r.store, shadow=None, live=r.live, cutover=("wind",), clock=clock)
    assert r3.resume() == {"shadowed": 0, "requested": 0, "retried": 0} and r.rtdb.calls == calls


def test_the_combined_biological_state_package_maps_to_both_target_brains_and_stays_frozen():
    r = Rig(brains=("wind",))
    co = PublicationCoordinator(PublicationLedger(), r.store, clock=clock)
    rec = co.report_missing("biological-state", "55555555-5555-4555-8555-555555555555", "SUCCEEDED", "none")
    assert rec["targetBrains"] == ["fish-knowledge", "fish-behavior"] and DO.recognize("biological-state")["kind"] == "LEGACY_COMBINED"
    assert rec["artifact"]["state"] == "MISSING" and rec["publication"]["outcome"] == "NOT_REQUESTED"


def test_the_coordinator_has_no_database_client_and_never_writes_brain_intelligence():
    import ast
    import inspect
    from sector_brain_platform import publication_coordination as PC
    tree = ast.parse(inspect.getsource(PC))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.split(".")[-1] in ("rtdb", "gcp", "publisher_live") or m.startswith(("urllib", "requests", "http")) for m in imported)          # no database, cloud or network client is imported
    params = inspect.signature(PC.PublicationCoordinator.__init__).parameters
    assert "rtdb" not in params and "db" not in params                                                                                       # and none can be injected
