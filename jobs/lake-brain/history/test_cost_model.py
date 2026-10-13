import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cost_model as cm


def test_five_lake_runtime_matches_the_measured_executions():
    r = cm.runtime(5)
    assert round(r["wall_lo_s"], 1) == 70.3 and round(r["wall_hi_s"], 1) == 148.0
    avg = sum(cm.M["run_wall_s"]) / 5
    assert round(avg, 1) == 96.0
    assert abs(avg * 2e-05 - 0.00192) < 1e-5            # 1 vCPU + 1 GiB at the catalog rates


def test_scaling_is_linear_and_lifecycle_beats_no_lifecycle():
    for n in (5, 196, 621):
        s = cm.storage_rows(n)
        assert s["baselines_new_lifecycle_standing_bytes"] < s["baselines_new_nolifecycle_bytes"] < s["baselines_old_bytes"]
        assert s["history_noncurrent_lifecycle_standing_bytes"] < s["history_noncurrent_nolifecycle_bytes"]
    a, b = cm.storage_rows(196), cm.storage_rows(621)
    assert abs(b["history_live_bytes"] / a["history_live_bytes"] - 621 / 196) < 1e-9


def test_fleet_runs_exceed_the_task_timeout_without_sharding():
    assert cm.runtime(621)["exceeds_timeout_hi"] is True and cm.runtime(5)["exceeds_timeout_hi"] is False


def test_baseline_object_count_drops_seven_fold():
    s = cm.storage_rows(621)
    assert s["baselines_old_objects"] / s["baselines_new_nolifecycle_objects"] > 7
