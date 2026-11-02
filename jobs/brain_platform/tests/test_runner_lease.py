"""Runner leases (Sector_Ops #50): the Orchestrator grants, the holder renews, failover is OFF unless the reviewed policy turns it on. Fakes only."""
import datetime as dt
import json

import pytest

from sector_brain_platform import runner_lease as RL
from sector_brain_platform.publisher.storage import AccessDenied, MemoryObjectStore

T0 = dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.timezone.utc)
CLOUD_PRIMARY = {"schema": "sector-runner-policy-v1", "defaultPrimary": "cloud", "primary": {}, "failover": {"enabled": False, "brains": []}}
PULSE_PRIMARY = {**CLOUD_PRIMARY, "primary": {"water-clarity": "pulse"}}
PULSE_FAILOVER = {**PULSE_PRIMARY, "failover": {"enabled": True, "brains": ["water-clarity"], "approvalRef": "owner/test"}}


def m(n):
    return T0 + dt.timedelta(minutes=n)


@pytest.fixture
def s():
    return MemoryObjectStore()


def test_committed_policy_keeps_the_status_quo_and_failover_off():
    p = RL.load_policy()
    assert p["defaultPrimary"] == "cloud" and p["primary"] == {} and p["failover"]["enabled"] is False
    assert all(RL.primary(p, b) == "cloud" and not RL.failover_enabled(p, b) for b in ("water-clarity", "wind", "lake-brain"))


def test_only_the_policy_primary_gets_a_first_lease(s):
    o = RL.orchestrator_view(s)
    with pytest.raises(RL.LeaseBusy):
        RL.grant(o, PULSE_PRIMARY, "water-clarity", "cloud", "c1", T0)            # cloud is not primary and failover is off
    g = RL.grant(o, PULSE_PRIMARY, "water-clarity", "pulse", "c1", T0)
    assert g["holder"] == "pulse" and g["leaseUntil"] == "2026-11-02T12:20:00Z" and g["grantedBy"] == "orchestrator"


def test_a_fresh_lease_is_never_taken_and_an_expired_one_moves_only_with_failover(s):
    o = RL.orchestrator_view(s)
    RL.grant(o, PULSE_PRIMARY, "water-clarity", "pulse", "c1", T0)
    with pytest.raises(RL.LeaseBusy):
        RL.grant(o, PULSE_FAILOVER, "water-clarity", "cloud", "c2", m(5))        # fresh: not even with failover
    with pytest.raises(RL.LeaseBusy, match="failover to cloud is OFF"):
        RL.grant(o, PULSE_PRIMARY, "water-clarity", "cloud", "c2", m(30))        # expired, failover off: the Brain waits
    assert RL.grant(o, PULSE_FAILOVER, "water-clarity", "cloud", "c2", m(30))["holder"] == "cloud"
    assert RL.grant(o, PULSE_FAILOVER, "water-clarity", "pulse", "c3", m(60))["holder"] == "pulse"   # back to the primary once cloud's lease ends


def test_only_the_holder_renews_and_never_after_expiry(s):
    o, pulse, cloud = RL.orchestrator_view(s), RL.runner_view(s, "pulse"), RL.runner_view(s, "cloud")
    RL.grant(o, PULSE_PRIMARY, "water-clarity", "pulse", "c1", T0)
    assert RL.renew(pulse, "water-clarity", "pulse", m(5))["leaseUntil"] == "2026-11-02T12:25:00Z"
    with pytest.raises(RL.LeaseLost):
        RL.renew(cloud, "water-clarity", "cloud", m(6))
    with pytest.raises(RL.LeaseLost, match="expired"):
        RL.renew(pulse, "water-clarity", "pulse", m(60))
    assert RL.may_run(pulse, "water-clarity", "pulse", m(60)) == (False, "LEASE_EXPIRED")
    assert RL.may_run(pulse, "water-clarity", "pulse", m(10)) == (True, "LEASE_HELD")
    assert RL.may_run(pulse, "wind", "pulse", m(10)) == (False, "NO_LEASE")


def test_a_concurrent_change_loses_the_compare_and_swap(s):
    o, pulse = RL.orchestrator_view(s), RL.runner_view(s, "pulse")
    RL.grant(o, PULSE_PRIMARY, "water-clarity", "pulse", "c1", T0)
    real_put = s.put

    def racing_put(key, data, *, if_generation_match=None):
        real_put(key, data, if_generation_match=None)                              # someone else writes first
        return real_put(key, data, if_generation_match=if_generation_match)
    s.put = racing_put
    with pytest.raises(RL.LeaseLost, match="concurrently"):
        RL.renew(pulse, "water-clarity", "pulse", m(5))


def test_cloud_start_gate(s):
    o = RL.orchestrator_view(s)
    assert RL.cloud_may_start(o, CLOUD_PRIMARY, "water-clarity", T0) == (True, "CLOUD_PRIMARY")
    assert RL.cloud_may_start(o, PULSE_PRIMARY, "water-clarity", T0) == (False, "PRIMARY_PULSE_FAILOVER_OFF")
    RL.grant(o, PULSE_FAILOVER, "water-clarity", "pulse", "c1", T0)
    assert RL.cloud_may_start(o, PULSE_FAILOVER, "water-clarity", m(5)) == (False, "HELD_BY_PULSE")
    assert RL.cloud_may_start(o, PULSE_FAILOVER, "water-clarity", m(30)) == (True, "FAILOVER_PRIMARY_EXPIRED")
    assert RL.cloud_may_start(o, PULSE_PRIMARY, "water-clarity", m(30)) == (False, "PRIMARY_PULSE_FAILOVER_OFF")


def test_views_keep_each_side_in_its_lane(s):
    pulse = RL.runner_view(s, "pulse")
    with pytest.raises(AccessDenied):
        pulse.put(RL.execution_key("cloud", "water-clarity", "e1"), b"{}", if_generation_match=0)    # not its own execution records
    with pytest.raises(AccessDenied):
        pulse.put("artifacts/water-clarity/x/artifact.json", b"{}", if_generation_match=0)            # artifacts go through ArtifactWriter on the raw store
    with pytest.raises(AccessDenied):
        RL.orchestrator_view(s).put(RL.execution_key("pulse", "water-clarity", "e1"), b"{}", if_generation_match=0)
    with pytest.raises(ValueError):
        RL.runner_view(s, "laptop")


def test_execution_records_are_create_only_and_reconcilable(s):
    pulse = RL.runner_view(s, "pulse")
    kw = dict(status="SUCCEEDED", started_at="2026-11-02T12:00:00Z", ended_at="2026-11-02T12:01:00Z", artifact={"artifactId": "a1"}, cycle_id="c1", engine_commit="abc")
    k = RL.record_execution(pulse, "pulse", "water-clarity", "e1", **kw)
    assert RL.record_execution(pulse, "pulse", "water-clarity", "e1", **kw) == k                 # identical: idempotent
    with pytest.raises(ValueError):
        RL.record_execution(pulse, "pulse", "water-clarity", "e1", **{**kw, "status": "FAILED"})
    ex = RL.runner_executions(RL.orchestrator_view(s), {"water-clarity"})
    assert ex == [{"executionId": "e1", "brainId": "water-clarity", "status": "SUCCEEDED", "startedAt": "2026-11-02T12:00:00Z",
                   "endedAt": "2026-11-02T12:01:00Z", "runner": "pulse", "cycleId": "c1"}]
    assert RL.runner_executions(RL.orchestrator_view(s), {"wind"}) == []
    assert RL.held_for_cycle([{"holder": "pulse", "cycleId": "c1"}], "pulse", "c1") and not RL.held_for_cycle([{"holder": "cloud", "cycleId": "c1"}], "pulse", "c1")
