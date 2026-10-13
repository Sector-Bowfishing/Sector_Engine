#!/usr/bin/env python3
"""Lake Brain storage / API / runtime cost model for 5, 196 and 621 lakes. Re-derives every number in
docs/brains/LAKE_BRAIN_STORAGE_LIFECYCLE_AND_COST.md. MEASURED inputs are from 2026-10-13 (listings, Cloud Run executions, logs);
ESTIMATE inputs are labelled. Prices: Cloud Billing Catalog API (cloudbilling.googleapis.com), SKUs effective 2026-10-13, USD.
usage: cost_model.py [--json]"""
import json, sys

GIB = 2 ** 30
PRICE = dict(
    storage_gib_month=0.02,       # SKU "Standard Storage US Regional" (us-central1), first 5 GiB-month free; free tier ignored below
    class_a=0.005 / 1000,         # SKU "Regional Standard Class A Operations": $0.000005 each, first 5,000/month free (ignored)
    class_b=0.0004 / 1000,        # SKU "Regional Standard Class B Operations": $0.0000004 each, first 50,000/month free (ignored)
    run_job_cpu_s=0.000018,       # SKU "Jobs CPU in us-central1" per vCPU-second
    run_job_mem_gib_s=0.000002,   # SKU "Jobs Memory in us-central1" per GiB-second
)
M = dict(  # MEASURED 2026-10-13
    baseline_bytes_sufficient=118_000,      # 114,360 .. 122,517 (v2 artifacts, SUFFICIENT history)
    baseline_bytes_insufficient=50_000,     # 49,518 .. 50,906 (v1, history too short)
    history_bytes_tva=260_000,              # 256,578 .. 266,028 (7,140..7,410 rows, ~36 B/row)
    history_bytes_hartwell=1_680_028,       # 23,662 rows
    ledger_bytes_per_record=6_620 / 5,      # 5 records in the first ledger object
    registry_bytes_per_lake=9_108_590 / 590,  # lakes/ prefix: 1,180 objects for 590 lake dirs
    registry_index_bytes_per_lake=224_666 / 590,
    run_wall_s=[70.3, 148.0, 108.4, 82.5, 71.0],   # Cloud Run execution start..completion, 5 executions in time order (05:33..18:52 UTC), 5 pilot lakes
    run_inprocess_s=[4.452, 38.300, 34.572, 14.804, 5.034],  # "5 lakes in N ms" from the job log, same 5 executions, same order
    cpu=1.0, mem_gib=1.0, task_timeout_s=900, concurrency=3,
)
E = dict(  # ESTIMATES (labelled in the doc)
    fleet_history_bytes=400_000,   # average history file per lake (TVA 0.26 MB measured; Hartwell 1.68 MB; fleet unknown)
    runs_per_day=6,                # 5 executions observed 05:33..18:52 UTC with the hourly orchestrator (about every 4 h)
    pointer_bytes=700,
    baseline_retention_days=90, baseline_recompute_days=7, history_noncurrent_days=30, soft_delete_days=7,
)

def gb(b): return b / GIB
def usd_month(b): return gb(b) * PRICE["storage_gib_month"]

def storage_rows(n, runs=E["runs_per_day"]):
    bl = M["baseline_bytes_sufficient"]; hist = E["fleet_history_bytes"]
    per_year = {}
    # baselines
    old_objs = 365 * n; new_objs = round(365 / E["baseline_recompute_days"]) * n
    per_year["baselines_old_objects"] = old_objs; per_year["baselines_old_bytes"] = old_objs * bl
    per_year["baselines_new_nolifecycle_objects"] = new_objs; per_year["baselines_new_nolifecycle_bytes"] = new_objs * bl + new_objs * E["pointer_bytes"]
    stand = n * (E["baseline_retention_days"] // E["baseline_recompute_days"] + 1)
    per_year["baselines_new_lifecycle_standing_objects"] = stand + n
    per_year["baselines_new_lifecycle_standing_bytes"] = stand * bl + n * E["pointer_bytes"] * 2
    # history: live + noncurrent copies (one rewrite per lake per day)
    per_year["history_live_bytes"] = n * hist
    per_year["history_noncurrent_nolifecycle_objects"] = 365 * n
    per_year["history_noncurrent_nolifecycle_bytes"] = 365 * n * hist
    cap = E["history_noncurrent_days"] + E["soft_delete_days"]
    per_year["history_noncurrent_lifecycle_standing_objects"] = cap * n
    per_year["history_noncurrent_lifecycle_standing_bytes"] = cap * n * hist
    # predictions ledger: one object per run, one record per lake per run (upper bound: every lake published every run)
    per_year["predictions_objects"] = 365 * runs
    per_year["predictions_bytes"] = 365 * runs * n * M["ledger_bytes_per_record"]
    # registry (gs://sector-lake-registry): no versioning; growth only by new lakes / republish (7-day soft delete is transient)
    per_year["registry_live_bytes"] = n * (M["registry_bytes_per_lake"] + M["registry_index_bytes_per_lake"])
    return per_year

def ops_per_year(n, runs=E["runs_per_day"]):
    R = 365 * runs
    a_old = n * 365 * 2 + R                           # history PUT + baseline PUT per lake per day, + ledger
    b_old = R * (2 * n + 3) + n * 365                 # history GET + baseline exists-GET per lake per run, presence/ledger per run
    a_new = n * 365 + n * 52 * 2 + R                  # history PUT daily, baseline object+pointer weekly, ledger
    b_new = R * (3 * n + 3) + n * 52                  # pointer GET + object GET + history GET per lake per run, + weekly exists check
    return dict(class_a_old=a_old, class_b_old=b_old, class_a_new=a_new, class_b_new=b_new,
                usd_old=a_old * PRICE["class_a"] + b_old * PRICE["class_b"], usd_new=a_new * PRICE["class_a"] + b_new * PRICE["class_b"])

def runtime(n, runs=E["runs_per_day"]):
    startup = [w - p for w, p in zip(M["run_wall_s"], M["run_inprocess_s"])]   # wall minus in-process work: 65.9 .. 109.7 s
    batch_s = [p / 2 for p in M["run_inprocess_s"]]               # 5 lakes at concurrency 3 = 2 batches
    lo_batch, hi_batch = min(batch_s), max(batch_s)
    batches = -(-n // M["concurrency"])
    lo = min(startup) + batches * lo_batch; hi = max(startup) + batches * hi_batch
    unit = M["cpu"] * PRICE["run_job_cpu_s"] + M["mem_gib"] * PRICE["run_job_mem_gib_s"]
    return dict(batches=batches, wall_lo_s=lo, wall_hi_s=hi, exceeds_timeout_hi=hi > M["task_timeout_s"], exceeds_timeout_lo=lo > M["task_timeout_s"],
                usd_run_lo=lo * unit, usd_run_hi=hi * unit, usd_year_lo=lo * unit * runs * 365, usd_year_hi=hi * unit * runs * 365,
                startup_s=(min(startup), max(startup)))

def main():
    out = {}
    for n in (5, 196, 621):
        s = storage_rows(n)
        out[n] = dict(storage=s, ops=ops_per_year(n), runtime=runtime(n), ops_12_per_day=ops_per_year(n, 12), runtime_12=runtime(n, 12))
    measured_runs = dict(avg_wall_s=sum(M["run_wall_s"]) / 5, unit_usd_per_s=PRICE["run_job_cpu_s"] + PRICE["run_job_mem_gib_s"])
    measured_runs["usd_per_run_5_lakes"] = measured_runs["avg_wall_s"] * measured_runs["unit_usd_per_s"]
    measured_runs["usd_year_5_lakes_6_runs_day"] = measured_runs["usd_per_run_5_lakes"] * E["runs_per_day"] * 365
    out["measured"] = measured_runs
    if "--json" in sys.argv: print(json.dumps(out, indent=1, default=str)); return out
    print("price basis:", PRICE)
    for n in (5, 196, 621):
        s = out[n]["storage"]
        print(f"\n== {n} lakes")
        for k, v in s.items():
            if k.endswith("bytes"): print(f"  {k:55s} {v/1e6:12.1f} MB  ${usd_month(v):9.4f}/month at that size")
            else: print(f"  {k:55s} {v:12,.0f}")
        print("  ops/yr:", {k: round(v, 3) if isinstance(v, float) else v for k, v in out[n]["ops"].items()})
        print("  runtime (6 runs/day):", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out[n]["runtime"].items()})
    print("\nmeasured pilot run cost:", out["measured"])
    return out

if __name__ == "__main__":
    main()
