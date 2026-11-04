"""Automatic publishing by hand-off (Sector_Ops #46 Q3, #47 item 4), through the REAL orchestrate.main() cycle and the REAL brain-publisher pass.

The Orchestrator writes a create-only publication request for a CENTRAL Brain's sealed artifact and starts brain-publisher; the Publisher job publishes it; the next cycle reads the
Publisher's history and records PUBLISHED. Off by default; never while paused; never in a dry run; never twice. Every client is a fake (same stack as the e2e publication tests).
"""
import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "brain_platform", "tests"))
import orchestrate as OR                                                                     # noqa: E402
from test_central_scheduling import world                                                    # noqa: E402,F401  (fixture)
from test_orchestrator_publication_e2e import stack, quiet, cloud, rec_of                     # noqa: E402,F401  (fixture)
from publisher_fixtures import wind_artifact, uuid4                                          # noqa: E402
from sector_brain_platform import execution_control as EC, publication_requests as PR        # noqa: E402

_spec = importlib.util.spec_from_file_location("publish_job", os.path.join(HERE, "..", "..", "brain-publisher", "publish_job.py"))
PJ = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(PJ)

pytestmark = pytest.mark.live_manifest
CENTRAL = {"state": "CENTRAL", "approvalRef": "approval/test/wind", "orderReviewRef": "review/test"}


@pytest.fixture
def starts(monkeypatch):
    got = []
    monkeypatch.setattr(OR.gcp, "run_job", lambda tokens, job, args=None, task_count=None: got.append((job, args)) or {"metadata": {"name": f"{job}-e{len(got)}"}})
    return got


def requests(rig, brain="wind"):
    return sorted(rig.store.list(f"{PR.PREFIX}{brain}/"))


def publisher_pass(stack):
    control = EC.parse({"schema": EC.SCHEMA, "state": "ENABLED", "approvalRef": "approval/test/resume", "brains": {"wind": {"enabled": True}}})
    return PJ.run_pass(store=stack.rig.store, control=control, cutover_path=stack.paths["cut"], make_publisher=lambda b: stack.rig.live, live=True,
                       clock=lambda: stack.rig.clock)


def test_hand_off_is_off_by_default_even_for_a_central_brain(stack, starts):
    stack.rig.reconcile(stack.rig.ref(wind_artifact(n=1)))
    stack.cutover(wind=CENTRAL)
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv) == 0
    p = rec_of(stack.paths["ledger"])["publication"]
    assert p["outcome"] == "NOT_REQUESTED" and p["reason"] == "PUBLISHER_UNARMED"
    assert requests(stack.rig) == [] and starts == [] and stack.pub(db)["handoff"]["enabled"] is False


def test_central_artifact_is_handed_off_published_by_the_job_and_recorded_once(stack, starts):
    ref = stack.rig.ref(wind_artifact(n=1))
    stack.rig.reconcile(ref)
    stack.cutover(wind=CENTRAL)
    argv = stack.argv + ["--hand-off-publication"]
    db = stack.setup(quiet(), cloud())
    assert OR.main(argv) == 0
    r = rec_of(stack.paths["ledger"])
    assert r["publication"]["outcome"] == "PENDING" and r["publication"]["reason"] == "HANDED_TO_PUBLISHER_JOB" and r["publication"]["attempts"] == 1
    assert requests(stack.rig) == [PR.request_key("wind", ref.artifact_id)]
    assert starts == [("brain-publisher", None)]                                 # started once, no argument overrides
    h = stack.pub(db)["handoff"]
    assert h["pending"] == 1 and h["publisherStart"]["started"] is True and stack.rig.rtdb.updates == []     # the Orchestrator itself wrote no Brain key

    db = stack.setup(quiet(), {**cloud(), "brain-publisher": [{"metadata": {"name": "brain-publisher-e1"}, "status": {"startTime": "2026-10-15T03:00:00Z"}}]})
    assert OR.main(argv) == 0                                                    # Publisher still running: no second request, no second start
    assert requests(stack.rig) == [PR.request_key("wind", ref.artifact_id)] and len(starts) == 1
    assert stack.pub(db)["handoff"]["publisherStart"]["reason"] == "ALREADY_RUNNING"

    rep = publisher_pass(stack)                                                  # the Publisher job's pass
    assert rep["published"] == 1

    db = stack.setup(quiet(), cloud())
    assert OR.main(argv) == 0
    r = rec_of(stack.paths["ledger"])
    assert r["publication"]["outcome"] == "PUBLISHED" and r["publication"]["reason"] == "PUBLISHER_JOB:PUBLISHED" and r["publication"]["readback"]["source"] == "PUBLISHER_HISTORY"
    s = stack.pub(db)
    assert s["summary"]["brains"]["wind"]["published"] == 1 and s["summary"]["brains"]["wind"]["pending"] == 0
    assert s["handoff"]["publisherStart"]["reason"] == "NOTHING_PENDING" and len(starts) == 1
    assert publisher_pass(stack)["published"] == 0                               # decided: the job never publishes it again


def test_paused_control_hands_off_nothing_and_keeps_an_existing_request_pending(stack, starts):
    stack.rig.reconcile(stack.rig.ref(wind_artifact(n=1)))
    stack.cutover(wind=CENTRAL)
    argv = stack.argv + ["--hand-off-publication"]
    stack.setup(quiet(control=None), cloud())
    assert OR.main(argv) == 0
    assert rec_of(stack.paths["ledger"])["publication"]["reason"] == "EXECUTION_PAUSED" and requests(stack.rig) == [] and starts == []

    stack.setup(quiet(), cloud())
    assert OR.main(argv) == 0 and len(starts) == 1                              # enabled: handed off
    stack.setup(quiet(control=None), cloud())
    assert OR.main(argv) == 0                                                    # paused again
    p = rec_of(stack.paths["ledger"])["publication"]
    assert p["outcome"] == "PENDING" and p["heldReason"] == "EXECUTION_PAUSED" and len(starts) == 1


def test_dry_run_writes_no_request_and_starts_nothing(stack, starts):
    stack.rig.reconcile(stack.rig.ref(wind_artifact(n=1)))
    stack.cutover(wind=CENTRAL)
    stack.setup(quiet(), cloud())
    assert OR.main(stack.argv + ["--hand-off-publication", "--dry-run"]) == 0
    assert requests(stack.rig) == [] and starts == []


def test_a_brain_on_its_direct_writer_is_never_handed_off(stack, starts):
    stack.rig.reconcile(stack.rig.ref(wind_artifact(n=1)))
    stack.setup(quiet(), cloud())
    assert OR.main(stack.argv + ["--hand-off-publication"]) == 0
    assert rec_of(stack.paths["ledger"])["publication"]["reason"] == "DIRECT_WRITER_ACTIVE" and requests(stack.rig) == [] and starts == []


def test_a_failed_start_is_recorded_and_the_request_stays_pending(stack, monkeypatch):
    stack.rig.reconcile(stack.rig.ref(wind_artifact(n=1)))
    stack.cutover(wind=CENTRAL)

    def boom(*a, **k):
        raise OR.gcp.GcpError("404 job not found")
    monkeypatch.setattr(OR.gcp, "run_job", boom)
    db = stack.setup(quiet(), cloud())
    assert OR.main(stack.argv + ["--hand-off-publication"]) == 0                 # never breaks the cycle
    assert stack.pub(db)["handoff"]["publisherStart"]["reason"].startswith("START_FAILED")
    assert rec_of(stack.paths["ledger"])["publication"]["outcome"] == "PENDING" and len(requests(stack.rig)) == 1


def test_a_crash_between_request_and_ledger_does_not_make_a_second_request(stack):
    ref = stack.rig.ref(wind_artifact(n=1))
    import datetime as dt
    from sector_brain_platform.publisher.storage import orchestrator_view
    cut = {"wind": CENTRAL}
    a = PR.RequestHandoff(orchestrator_view(stack.rig.store), cut, "orchestrator-1", lambda: dt.datetime(2026, 11, 2, 1, tzinfo=dt.timezone.utc))
    b = PR.RequestHandoff(orchestrator_view(stack.rig.store), cut, "orchestrator-2", lambda: dt.datetime(2026, 11, 2, 2, tzinfo=dt.timezone.utc))
    assert a.submit(ref)["created"] is True and b.submit(ref)["created"] is False   # the later cycle finds the same request: no duplicate, no error
    other = PR.RequestHandoff(orchestrator_view(stack.rig.store), {"wind": {**CENTRAL, "approvalRef": "approval/other"}}, "o", lambda: dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc))
    with pytest.raises(ValueError):
        other.submit(ref)                                                        # a different request for the same artifact is never overwritten
    with pytest.raises(ValueError):
        PR.RequestHandoff(orchestrator_view(stack.rig.store), {}, "o", lambda: dt.datetime(2026, 11, 2, tzinfo=dt.timezone.utc)).submit(ref)   # not CENTRAL
    assert uuid4(2001) == ref.artifact_id
