import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import check_preproduction_schedules as C

POLICY = json.load(open(C.POLICY))


def job(name, state, cron="5 * * * *"):
    return {"name": f"projects/p/locations/l/jobs/{name}", "state": state, "schedule": cron}


def test_committed_policy_is_complete_and_matches_the_freeze():
    assert C.audit([], POLICY) == ([], [])
    assert set(POLICY["allowEnabled"]) == {"wind-hourly", "lake-brain-ledger-daily"}


def test_freeze_end_state_passes():
    jobs = [job("wind-hourly", "ENABLED"), job("lake-brain-ledger-daily", "ENABLED", "0 12 * * *"), job("brain-orchestrator", "PAUSED"),
            job("water-temp-tva-archive", "PAUSED"), job("lake-surface-dispatch", "PAUSED"), job("sector-unrelated-prod", "ENABLED")]
    bad, ok = C.audit(jobs, POLICY)
    assert bad == [] and sorted(ok) == ["lake-brain-ledger-daily", "wind-hourly"]


def test_a_reactivated_ungated_brain_job_is_a_violation():
    for name in ("brain-orchestrator", "water-temp-tva-archive", "lake-surface-dispatch", "hydrology-hourly"):
        bad, _ = C.audit([job(name, "ENABLED")], POLICY)
        assert bad and name in bad[0]


def test_allowlist_entries_need_gate_cost_stop_and_date():
    pol = {"brainSchedulers": ["x"], "allowEnabled": {"x": {"gate": "g"}}}
    bad, _ = C.audit([], pol)
    assert bad and "lacks" in bad[0]


def test_drift_between_live_schedulers_and_the_execution_manifest():
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
