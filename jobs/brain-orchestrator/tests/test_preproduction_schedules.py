import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import check_preproduction_schedules as C

POLICY = json.load(open(C.POLICY))


def job(name, state, cron="5 * * * *"):
    return {"name": f"projects/p/locations/l/jobs/{name}", "state": state, "schedule": cron}


def test_committed_policy_has_one_scheduling_authority():
    """Central scheduling 2026-10-23 (Cortex 2.7.0 PL-15): only brain-orchestrator may ever be ENABLED, and only under an ENABLED execution control;
    wind-hourly and lake-brain-ledger-daily are deprecated."""
    assert C.audit([], POLICY) == ([], [])
    assert set(POLICY["allowEnabled"]) == {"brain-orchestrator"}
    assert POLICY["allowEnabled"]["brain-orchestrator"]["requiresExecutionControl"] == "ENABLED"
    assert "NOT APPROVED" in POLICY["allowEnabled"]["brain-orchestrator"]["approvedAt"]
    assert set(POLICY["deprecatedSchedulers"]) == {"wind-hourly", "lake-brain-ledger-daily"}


def test_paused_end_state_passes():
    jobs = [job("wind-hourly", "PAUSED"), job("lake-brain-ledger-daily", "PAUSED", "0 12 * * *"), job("brain-orchestrator", "PAUSED"),
            job("water-temp-tva-archive", "PAUSED"), job("lake-surface-dispatch", "PAUSED"), job("sector-unrelated-prod", "ENABLED")]
    assert C.audit(jobs, POLICY, {"state": "PAUSED"}) == ([], [])


def test_deprecated_per_brain_schedulers_may_never_be_enabled():
    for name in ("wind-hourly", "lake-brain-ledger-daily"):
        bad, ok = C.audit([job(name, "ENABLED")], POLICY, {"state": "ENABLED"})
        assert any("DEPRECATED" in b and name in b for b in bad) and ok == []


def test_the_central_trigger_is_allowed_only_under_an_enabled_execution_control():
    on = [job("brain-orchestrator", "ENABLED", "50 * * * *")]
    assert any("execution control is PAUSED" in b for b in C.audit(on, POLICY, {"state": "PAUSED"})[0])
    assert any("NOT CHECKED" in b for b in C.audit(on, POLICY, None)[0])                       # unknown control = not allowed
    assert C.audit(on, POLICY, {"state": "ENABLED"}) == ([], ["brain-orchestrator"])


def test_a_reactivated_ungated_brain_job_is_a_violation():
    for name in ("water-temp-tva-archive", "lake-surface-dispatch", "hydrology-hourly", "lake-surface-daily", "clarity-current-hourly"):
        bad, _ = C.audit([job(name, "ENABLED")], POLICY)
        assert bad and name in bad[0]


def test_allowlist_entries_need_gate_cost_stop_and_date():
    pol = {"brainSchedulers": ["x"], "allowEnabled": {"x": {"gate": "g"}}}
    bad, _ = C.audit([], pol)
    assert bad and "lacks" in bad[0]


def test_drift_between_live_schedulers_and_the_execution_manifest():      # frozen pre-activation manifest (conftest)
    from sector_brain_platform import orchestration as O
    m = O.load_manifest()
    live = [job("wind-hourly", "ENABLED"), job("lake-brain-ledger-daily", "ENABLED"), job("brain-orchestrator", "PAUSED"), job("water-temp-tva-archive", "PAUSED"),
            job("lake-surface-dispatch", "PAUSED"), job("lake-surface-daily", "PAUSED"), job("hydrology-hourly", "PAUSED"), job("clarity-current-hourly", "PAUSED"),
            job("clarity-candidate-shadow", "PAUSED")]
    assert C.drift(live, m) == []                                              # the live freeze state IS the manifest
    live2 = [j if not j["name"].endswith("tva-archive") else job("water-temp-tva-archive", "ENABLED") for j in live]
    assert any("water-temp-tva-archive" in d and "ENABLED" in d for d in C.drift(live2, m))
    live3 = [j if not j["name"].endswith("wind-hourly") else job("wind-hourly", "PAUSED") for j in live]
    assert any("wind-hourly" in d and "evidence capture is not running" in d for d in C.drift(live3, m))
    assert any("UNMANAGED hidden-cron" in d for d in C.drift(live + [job("hidden-cron", "ENABLED")], m))


import pytest  # noqa: E402


@pytest.mark.live_manifest
def test_central_scheduling_live_board_has_no_drift():
    """The live board after the 2026-10-23 shutdown: every Brain scheduler PAUSED, deprecated ones included. No drift; the audit passes."""
    from sector_brain_platform import orchestration as O
    m = O.load_manifest()
    live = [job(n, "PAUSED") for n in ("wind-hourly", "lake-brain-ledger-daily", "brain-orchestrator", "water-temp-tva-archive", "lake-surface-dispatch",
                                       "lake-surface-daily", "hydrology-hourly", "clarity-current-hourly", "clarity-candidate-shadow")]
    assert C.drift(live, m) == []
    assert C.audit(live, POLICY, {"state": "PAUSED"}) == ([], [])
    # a deprecated scheduler that comes back ENABLED is drift as well as a policy violation
    assert any("wind-hourly" in d for d in C.drift([job("wind-hourly", "ENABLED")] + live[1:], m))
