import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import check_preproduction_schedules as C

POLICY = json.load(open(C.POLICY))


def job(name, state, cron="5 * * * *"):
    return {"name": f"projects/p/locations/l/jobs/{name}", "state": state, "schedule": cron}


def test_committed_policy_is_complete_and_matches_the_internal_activation():
    assert C.audit([], POLICY) == ([], [])
    assert set(POLICY["allowEnabled"]) == {"wind-hourly", "lake-brain-ledger-daily", "brain-orchestrator"}     # 2026-10-22 internal operation
    assert "2026-10-22" in POLICY["allowEnabled"]["brain-orchestrator"]["approvedAt"]


def test_freeze_end_state_passes():
    jobs = [job("wind-hourly", "ENABLED"), job("lake-brain-ledger-daily", "ENABLED", "0 12 * * *"), job("brain-orchestrator", "PAUSED"),
            job("water-temp-tva-archive", "PAUSED"), job("lake-surface-dispatch", "PAUSED"), job("sector-unrelated-prod", "ENABLED")]
    bad, ok = C.audit(jobs, POLICY)
    assert bad == [] and sorted(ok) == ["lake-brain-ledger-daily", "wind-hourly"]


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
def test_internal_activation_scheduler_state_has_no_drift():
    """The live board after internal activation: wind-hourly, lake-brain-ledger-daily and brain-orchestrator ENABLED; every other Brain scheduler
    PAUSED (cost freeze). Any other state is drift; the policy audit passes."""
    from sector_brain_platform import orchestration as O
    m = O.load_manifest()
    live = [job("wind-hourly", "ENABLED"), job("lake-brain-ledger-daily", "ENABLED", "0 12 * * *"), job("brain-orchestrator", "ENABLED", "50 * * * *"),
            job("water-temp-tva-archive", "PAUSED"), job("lake-surface-dispatch", "PAUSED"), job("lake-surface-daily", "PAUSED"), job("hydrology-hourly", "PAUSED"),
            job("clarity-current-hourly", "PAUSED"), job("clarity-candidate-shadow", "PAUSED")]
    assert C.drift(live, m) == []
    bad, ok = C.audit(live, POLICY)
    assert bad == [] and sorted(ok) == ["brain-orchestrator", "lake-brain-ledger-daily", "wind-hourly"]
    # pausing the orchestrator is the documented disable control, not drift
    assert not any("brain-orchestrator" in d for d in C.drift([j if not j["name"].endswith("brain-orchestrator") else job("brain-orchestrator", "PAUSED") for j in live], m))
