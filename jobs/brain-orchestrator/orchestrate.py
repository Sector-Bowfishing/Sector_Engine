#!/usr/bin/env python3
"""brain-orchestrator — the low-cost executor of docs/brains/ORCHESTRATOR_DESIGN.md (cost work 2026-10-13, Phase 15).

One hourly wake-up (Cloud Scheduler → this scale-to-zero Cloud Run job, 1 vCPU / 512 Mi, usually < 1 min):

  1. SYNC  /jobs/{jobId} from Cloud Scheduler + Cloud Run (the one canonical path; sector_brain_platform.jobs).
  2. PLAN  with sector_brain_platform.orchestrator.plan(): TIME brains (Lake, Water Temp) from their published
           staleAfterHours / lastSuccessfulRun; VERSION / FINGERPRINT brains (Biological, Intelligence) from their own
           `run.py --plan`. Single-flight from running Cloud Run executions + the lock this job wrote last time.
  3. RUN   only what the plan says: lake-brain / water-temp-brain as Cloud Run jobs (Jobs API `:run`, pilot lakes
           for Lake, fleet for Water Temp); biological-brain / sector-intelligence-brain in-process (`run.py --write`).
           Wind stays on its own cron; Water Clarity stays MANUAL — both are reported, never started here.
  4. SCORE publish /scores + /control (score_brains.py --write --if-changed) only when a Brain state changed since the
           last cycle, a job record changed, or something ran now.
  5. RECORD /control/orchestrator (plan, executed, lastSeen) as the platform writer.

  python3 orchestrate.py --dry-run            plan + report, write nothing, start nothing
  python3 orchestrate.py --sync-jobs-only     publish /jobs and stop
  python3 orchestrate.py --no-execute         sync + plan + record, but start no brain
  python3 orchestrate.py                      the hourly cycle

env: BRAIN_RTDB_URL, ORCHESTRATOR_SCOPE (pilots|fleet, Lake Brain; default pilots), WATER_TEMP_SCOPE (fleet|pilots; default
     fleet — a per-lake Water Temp run leaves the registry's fleet counts empty), LAKE_BRAIN_ARCHIVE (gs:// bucket name
     for the Lake Brain history; passed through as a job arg), ENGINE_URL (Intelligence reads GET /lakes).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
from sector_brain_platform import (BrainRtdb, DryRunStore, TokenProvider, build_records, check_schema, iso,            # noqa: E402
                                   jobs_changed_paths, orchestrate)
from sector_brain_platform import gcp                                                                                 # noqa: E402

WRITER = "brain-platform"
JOB_NAME = "brain-orchestrator"
RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")
PILOT_LAKES = ("Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC")
LOCK_MINUTES = 15                       # covers the gap between `:run` and the execution showing up in the API
PYTHON = sys.executable

# Executors: how each brain is started. Anything absent here is never started by the orchestrator.
EXECUTORS = {
    "lake-brain": {"kind": "cloud-run-job", "job": "lake-brain"},
    "water-temp": {"kind": "cloud-run-job", "job": "water-temp-brain"},
    "biological-state": {"kind": "in-process", "dir": os.path.join(HERE, "..", "biological-brain"), "jobId": "biological-brain"},
    "sector-intelligence": {"kind": "in-process", "dir": os.path.join(HERE, "..", "sector-intelligence-brain"), "jobId": "sector-intelligence-brain"},
}
NOT_STARTED_HERE = {"wind": "scheduler-owned (wind-hourly cron at :05)", "water-clarity": "MANUAL by decision (docs/brains/WATER_CLARITY_BRAIN_SCHEDULING.md)"}


def job_args(brain_id: str) -> list[str]:
    if brain_id == "lake-brain":
        args = ["--rtdb", RTDB_URL, "--scope", os.environ.get("ORCHESTRATOR_SCOPE", "pilots")]
        if os.environ.get("LAKE_BRAIN_ARCHIVE"):
            args += ["--archive", os.environ["LAKE_BRAIN_ARCHIVE"]]
        return args
    if brain_id == "water-temp":
        args = ["--rtdb", RTDB_URL]
        if os.environ.get("WATER_TEMP_SCOPE", "fleet") == "pilots":
            for lid in PILOT_LAKES:
                args += ["--lake", lid]
        return args
    return []


def brain_plan(brain_id: str, timeout: int = 600) -> dict:
    """`run.py --plan` of an in-process brain → its plan() verdict (PUBLISH / SKIP + reasons). Failure = SKIP with the error."""
    ex = EXECUTORS[brain_id]
    try:
        out = subprocess.run([PYTHON, "run.py", "--plan"], cwd=ex["dir"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"action": "SKIP", "reasons": [f"--plan timed out after {timeout}s"]}
    if out.returncode != 0:
        return {"action": "SKIP", "reasons": [f"--plan failed: {(out.stderr or out.stdout).strip()[-300:]}"]}
    try:
        return json.loads(out.stdout.strip().splitlines()[-1] if "\n" in out.stdout.strip() else out.stdout)
    except ValueError:
        try:
            return json.loads(out.stdout[out.stdout.index("{"):])
        except ValueError:
            return {"action": "SKIP", "reasons": ["--plan output unreadable"]}


def run_in_process(brain_id: str, timeout: int = 1800) -> dict:
    ex = EXECUTORS[brain_id]
    t0 = time.time()
    out = subprocess.run([PYTHON, "run.py", "--write"], cwd=ex["dir"], capture_output=True, text=True, timeout=timeout)
    ok = out.returncode == 0
    return {"brainId": brain_id, "how": "in-process", "ok": ok, "seconds": round(time.time() - t0, 1),
            "tail": (out.stdout if ok else (out.stderr or out.stdout)).strip()[-600:]}


def start_job(brain_id: str, tokens: TokenProvider) -> dict:
    ex = EXECUTORS[brain_id]
    op = gcp.run_job(tokens, ex["job"], args=job_args(brain_id))
    return {"brainId": brain_id, "how": "cloud-run-job", "job": ex["job"], "ok": True,
            "execution": (op.get("metadata") or {}).get("name"), "startedAt": iso(dt.datetime.now(dt.timezone.utc))}


def with_single_flight(brains: dict, executions: dict[str, list[dict]], locks: dict, now: dt.datetime) -> dict:
    """A copy of the registries with `schedule.running` / `schedule.lockedUntil` from the real world: a running
    Cloud Run execution of the brain's job, or the lock this orchestrator wrote when it started one."""
    out = {}
    for b, reg in brains.items():
        reg = dict(reg or {})
        sched = dict(reg.get("schedule") or {}) if isinstance(reg.get("schedule"), dict) else {}
        ex = EXECUTORS.get(b) or {}
        if ex.get("kind") == "cloud-run-job" and gcp.running_executions(executions.get(ex["job"]) or []):
            sched["running"] = True
        lock = (locks or {}).get(b) or {}
        if lock.get("lockedUntil") and lock["lockedUntil"] > iso(now):
            sched["lockedUntil"] = lock["lockedUntil"]
        reg["schedule"] = sched
        out[b] = reg
    return out


def sync_jobs(db, tokens: TokenProvider, now: dt.datetime, write: bool) -> tuple[dict, dict, int]:
    scheduler = gcp.list_scheduler_jobs(tokens)
    run_jobs = gcp.list_run_jobs(tokens)
    executions = {}
    for j in run_jobs:
        name = (j.get("metadata") or {}).get("name")
        if name:
            try:
                executions[name] = gcp.list_executions(tokens, name, limit=20)
            except gcp.GcpError as e:
                print(f"warning: executions of {name} unreadable: {e}", file=sys.stderr)
    services = {}
    for s in ("sector-engine", "wind-candidate-read"):
        try:
            svc = gcp.get_service(tokens, s)
            if svc:
                services[s] = svc
        except gcp.GcpError as e:
            print(f"warning: service {s} unreadable: {e}", file=sys.stderr)
    health = db.get("health/brains") or {}
    records = build_records(scheduler_jobs=scheduler, run_jobs=run_jobs, executions=executions, now=now, synced_by=JOB_NAME,
                            brain_health=health, services=services)
    changed = jobs_changed_paths(records, db.get("jobs") or {})
    if write and changed:
        db.update(changed)
    return records, executions, len(changed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write nothing, start nothing")
    ap.add_argument("--no-execute", action="store_true", help="sync + plan + record, start nothing")
    ap.add_argument("--sync-jobs-only", action="store_true")
    ap.add_argument("--force-scores", action="store_true", help="publish scores/control even when nothing changed")
    a = ap.parse_args(argv)
    t0 = time.time()
    now = dt.datetime.now(dt.timezone.utc)
    write = not a.dry_run
    tokens = TokenProvider()
    live = BrainRtdb(RTDB_URL, tokens, brain_id=WRITER)
    check_schema(live)
    db = live if write else _ReadThrough(live)

    # 1. /jobs
    records, executions, n_changed = sync_jobs(db, tokens, now, write)
    print(f"jobs: {len(records)} records, {n_changed} changed", flush=True)
    if a.sync_jobs_only:
        return 0

    # 2. plan
    brains = live.get("brains") or {}
    health = live.get("health/brains") or {}
    state = live.get("control/orchestrator") or {}
    brain_plans = {b: brain_plan(b) for b, ex in EXECUTORS.items() if ex["kind"] == "in-process" and b in brains}
    plan = orchestrate(with_single_flight(brains, executions, state.get("locks") or {}, now), health, now, brain_plans)
    for r in plan["runs"]:
        print(f"RUN  {r['brainId']:20s} {'; '.join(r['reasons'])}" + (f" (after {r['after']})" if r.get("after") else ""))
    for w in plan["waiting"]:
        print(f"WAIT {w['brainId']:20s} {'; '.join(w['reasons'])}")
    for s in plan["skipped"]:
        print(f"SKIP {s['brainId']:20s} {'; '.join(s['reasons'])}")

    # 3. execute
    executed, deferred, locks = [], [], {}
    started_async = set()
    for r in plan["runs"]:
        b = r["brainId"]
        if b in NOT_STARTED_HERE:
            deferred.append({"brainId": b, "why": NOT_STARTED_HERE[b]})
            continue
        ex = EXECUTORS.get(b)
        if not ex:
            deferred.append({"brainId": b, "why": "no executor"})
            continue
        if any(x in started_async for x in r.get("after") or []):
            deferred.append({"brainId": b, "why": f"upstream started this cycle ({[x for x in r['after'] if x in started_async]}); next wake-up"})
            continue
        if a.dry_run or a.no_execute:
            deferred.append({"brainId": b, "why": "not executed (--dry-run/--no-execute)"})
            continue
        try:
            if ex["kind"] == "cloud-run-job":
                res = start_job(b, tokens)
                started_async.add(b)
                locks[b] = {"execution": res.get("execution"), "startedAt": res["startedAt"],
                            "lockedUntil": iso(now + dt.timedelta(minutes=LOCK_MINUTES))}
            else:
                res = run_in_process(b)
        except Exception as e:                                   # one brain's failure never stops the cycle
            res = {"brainId": b, "ok": False, "error": repr(e)[:300]}
        executed.append(res)
        print(f"{'✓' if res.get('ok') else '✗'} {b}: {res.get('execution') or res.get('tail', res.get('error', ''))[-200:]}", flush=True)

    # 4. scores / control — only after a state change
    seen = {b: (brains.get(b) or {}).get("lastSuccessfulRun") for b in brains}
    changed_brains = sorted(b for b in seen if seen[b] != (state.get("lastSeen") or {}).get(b))
    ran_in_process = [e["brainId"] for e in executed if e.get("how") == "in-process" and e.get("ok")]
    reason = ("brain state changed: " + ", ".join(changed_brains)) if changed_brains else \
             ("published this cycle: " + ", ".join(ran_in_process)) if ran_in_process else \
             (f"{n_changed} job record(s) changed" if n_changed else ("forced" if a.force_scores else None))
    scores = {"published": False, "why": reason or "nothing changed since the last cycle"}
    if reason and write:
        cmd = [PYTHON, os.path.join(HERE, "..", "brain-scores", "score_brains.py"), "--write", "--if-changed"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        scores.update({"published": out.returncode == 0, "tail": (out.stdout if out.returncode == 0 else (out.stderr or out.stdout)).strip()[-500:]})
        print(f"scores: {'published' if out.returncode == 0 else 'FAILED'} ({reason})", flush=True)
    else:
        print(f"scores: skipped ({scores['why']})")

    # 5. record
    record = {"version": "orchestrator-v1", "lastRunAt": iso(now), "durationMs": int((time.time() - t0) * 1000),
              "mode": "dry-run" if a.dry_run else ("no-execute" if a.no_execute else "cycle"),
              "plan": plan, "brainPlans": brain_plans, "executed": executed, "deferred": deferred,
              "locks": {**{b: l for b, l in (state.get("locks") or {}).items() if l.get("lockedUntil", "") > iso(now) and b not in locks}, **locks},
              "lastSeen": {**(state.get("lastSeen") or {}), **{b: v for b, v in seen.items() if v}} if write else state.get("lastSeen"),
              "jobsSynced": len(records), "jobsChanged": n_changed, "scores": scores}
    if write:
        live.update({"control/orchestrator": record})
    print(json.dumps({k: record[k] for k in ("mode", "durationMs", "jobsChanged", "scores")}, indent=None))
    print(f"executed {len(executed)}, deferred {len(deferred)}, waiting {len(plan['waiting'])}, skipped {len(plan['skipped'])}")
    return 0 if all(e.get("ok") for e in executed) else 1


class _ReadThrough:
    """Dry run: GETs go to the live database, every update is kept in memory and printed."""

    def __init__(self, live):
        self.live, self.mem = live, DryRunStore(brain_id=WRITER)

    def get(self, path, shallow=False):
        return self.live.get(path, shallow)

    def update(self, updates):
        self.mem.update(updates)
        print(f"(dry run) would write {len(updates)} path(s): {sorted(updates)[:8]}{' …' if len(updates) > 8 else ''}")


if __name__ == "__main__":
    sys.exit(main())
