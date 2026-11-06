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
  python3 orchestrate.py --health-only        evaluate and publish ONLY control/healthV1 (brain-health-v1); no /jobs write, no execution,
                                              no scores, no control/orchestratorV1 write, no legacy record (health-plane-publication-v1)
  python3 orchestrate.py ... --publish-engineering-status
                                              also publish control/engineeringStatusV1 (engineering-status-ops-v1) from the projection
                                              staged in this image; OFF by default (decision O-1). --emit-engineering-status FILE: review only

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
from sector_brain_platform import orchestration as O, control_state as CS, consumption as CN, publication_trigger as PT                          # noqa: E402
from sector_brain_platform import brain_operations as BOPS                                                            # noqa: E402
from sector_brain_platform import execution_control as EC                                                            # noqa: E402
from sector_brain_platform import engineering_status_publication as ESP                                                # noqa: E402
from sector_brain_platform import shadow_lane as SL                                                                   # noqa: E402
from sector_brain_platform import data_ownership as DO, publication_stage as PS, health_mirror as HM                                       # noqa: E402
from sector_brain_platform import runner_lease as RL                                                                  # noqa: E402
sys.path.insert(0, HERE)
import control_plane as CP                                                                                            # noqa: E402
import conditions_sources as CSP                                                                                    # noqa: E402

WRITER = "brain-platform"
JOB_NAME = "brain-orchestrator"
RTDB_URL = os.environ.get("BRAIN_RTDB_URL", "https://sector-brain.firebaseio.com")
PILOT_LAKES = ("Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC")
LOCK_MINUTES = 15                       # covers the gap between `:run` and the execution showing up in the API
PYTHON = sys.executable

def _fish_runtime_dir() -> str:
    """Fish Brain runtime: brains/fish/runtime in the repository; ../biological-brain in the staged orchestrator image (deploy-job.sh stages it there)."""
    repo = os.path.normpath(os.path.join(HERE, "..", "..", "brains", "fish", "runtime"))
    return repo if os.path.isdir(repo) else os.path.join(HERE, "..", "biological-brain")


def _intelligence_runtime_dir() -> str:
    """Sector Intelligence runtime: brains/sector-intelligence/runtime in the repository; ../sector-intelligence-brain in the staged orchestrator image."""
    repo = os.path.normpath(os.path.join(HERE, "..", "..", "brains", "sector-intelligence", "runtime"))
    return repo if os.path.isdir(repo) else os.path.join(HERE, "..", "sector-intelligence-brain")


# Executors: how each brain is started. Anything absent here is never started by the orchestrator.
EXECUTORS = {
    "lake-brain": {"kind": "cloud-run-job", "job": "lake-brain"},
    "water-temp": {"kind": "cloud-run-job", "job": "water-temp-brain"},
    "water-clarity": {"kind": "cloud-run-job", "job": "water-clarity-brain"},       # C1 publisher, pilot lakes baked into the job (internal operation 2026-10-22)
    # Central scheduling 2026-10-23 (Cortex 2.7.0 PL-15): Wind's own wind-hourly Cloud Scheduler is DEPRECATED (paused); the orchestrator starts the
    # same Cloud Run job (arguments baked in: `hourly --store ...`) when Wind is due. Its science and job are unchanged.
    "wind": {"kind": "cloud-run-job", "job": "wind-hourly"},
    "biological-state": {"kind": "in-process", "dir": _fish_runtime_dir(), "jobId": "biological-brain"},
    "sector-intelligence": None,                                                         # set below: in-process today; artifact job only behind SI_ARTIFACT_JOB
}


INTELLIGENCE_JOB = "sector-intelligence-brain"


def intelligence_executor(env=None) -> dict:
    """Sector Intelligence's executor (SECTOR_INTELLIGENCE_JOB_PLAN_V1 SI-A2). Default: in-process (`run.py --write`), exactly as before.
    SI_ARTIFACT_JOB=1: an artifact job (`run.py --artifact-dir/--artifact-bucket`, SI-A1) that is LEASE-ONLY. The Orchestrator grants the cycle to the
    runner-policy primary (Pulse) and never starts a Cloud Run job for it, because none is deployed (a deploy is a separate approval). With the cloud as
    primary it holds. Its `--plan` verdict is still asked in-process, so the decision inputs do not change. The in-process path is removed only at SI-A6.

    SI-P2 option (b), owner-approved 2026-11-05 (Sector_Ops #50): with SI_JOB_PLAN=1 as well (default off), the Orchestrator no longer runs Intelligence's
    `--plan` itself (planInProcess False): it leases the cycle on the schedule and dependency triggers alone, and the job's own `orch.plan`, computed from
    the same reads, decides PUBLISH or SKIP. A SKIP comes back as a SKIPPED runner record (runner.py skip), a normal cycle outcome. SI_JOB_PLAN without
    SI_ARTIFACT_JOB changes nothing: the in-process Brain keeps its plan."""
    env = os.environ if env is None else env
    if env.get("SI_ARTIFACT_JOB") == "1":
        return {"kind": "cloud-run-job", "job": INTELLIGENCE_JOB, "jobId": INTELLIGENCE_JOB, "dir": _intelligence_runtime_dir(),
                "artifactMode": True, "leaseOnly": True, "planInProcess": env.get("SI_JOB_PLAN") != "1"}
    return {"kind": "in-process", "dir": _intelligence_runtime_dir(), "jobId": INTELLIGENCE_JOB}


EXECUTORS["sector-intelligence"] = intelligence_executor()
NOT_STARTED_HERE: dict = {}                     # every Brain with an executor is started only by the orchestrator (PL-15)


def job_args(brain_id: str) -> list[str] | None:
    """Container-arg overrides for a brain's job. By default NONE: the jobs are deployed with their arguments baked in
    (jobs/lake-brain, jobs/water-temp-brain deploy scripts) so `roles/run.invoker` is enough — `jobs.run` with overrides
    needs `run.jobs.runWithOverrides` (run.developer). Set ORCHESTRATOR_OVERRIDE_ARGS=1 to pass scope overrides instead."""
    if os.environ.get("ORCHESTRATOR_OVERRIDE_ARGS") != "1":
        return None
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


def json_output(stdout: str) -> dict | None:
    """The JSON object a Brain's run.py prints (its summary / plan): the last line if it is JSON, else the first '{' to the end. None if unreadable."""
    s = (stdout or "").strip()
    if not s:
        return None
    try:
        v = json.loads(s.splitlines()[-1] if "\n" in s else s)
        return v if isinstance(v, dict) else None
    except ValueError:
        try:
            v = json.loads(s[s.index("{"):])
            return v if isinstance(v, dict) else None
        except ValueError:
            return None


def brain_plan(brain_id: str, timeout: int = 600) -> dict:
    """`run.py --plan` of an in-process brain → its plan() verdict (PUBLISH / SKIP + reasons). Failure = SKIP with the error, marked
    `planError` so the VERSION freshness verdict is UNKNOWN, never FRESH (operational_truth)."""
    ex = EXECUTORS[brain_id]
    try:
        out = subprocess.run([PYTHON, "run.py", "--plan"], cwd=ex["dir"], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"action": "SKIP", "planError": True, "reasons": [f"--plan timed out after {timeout}s"]}
    if out.returncode != 0:
        return {"action": "SKIP", "planError": True, "reasons": [f"--plan failed: {(out.stderr or out.stdout).strip()[-300:]}"]}
    return json_output(out.stdout) or {"action": "SKIP", "planError": True, "reasons": ["--plan output unreadable"]}


SCORER_TIMEOUT_SECONDS = 900


def run_scorer(cmd: list[str], timeout: int = SCORER_TIMEOUT_SECONDS) -> dict:
    """The scorer step, isolated (PL-02): a timeout or a failure is RECORDED in the cycle's scores block and the cycle goes on to publish the control
    plane and its own record; it never aborts the cycle. Success semantics are unchanged (published == exit code 0)."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"published": False, "timedOut": True, "tail": f"score_brains.py timed out after {timeout}s"}
    return {"published": out.returncode == 0, "tail": (out.stdout if out.returncode == 0 else (out.stderr or out.stdout)).strip()[-500:]}


def in_process_timeout(manifest: dict, brain_id: str) -> int:
    """The Brain's declared timeoutSeconds (control manifest), else the platform default; never longer than the orchestrator's own 30-min task."""
    t = (manifest["brains"].get(brain_id) or {}).get("timeoutSeconds") or (manifest.get("defaults") or {}).get("timeoutSeconds") or 1800
    return int(min(t, 1800))


def run_in_process(brain_id: str, timeout: int = 1800) -> dict:
    """`run.py --write`. The Brain's printed summary may carry `consumed` (consumption-lineage-v1: what its RTDB client ACTUALLY read, recorded by
    the platform ConsumptionRecorder). It is passed through when valid; an invalid list is reported, never repaired; absence stays absence."""
    ex = EXECUTORS[brain_id]
    t0 = time.time()
    out = subprocess.run([PYTHON, "run.py", "--write"], cwd=ex["dir"], capture_output=True, text=True, timeout=timeout)
    ok = out.returncode == 0
    res = {"brainId": brain_id, "how": "in-process", "ok": ok, "seconds": round(time.time() - t0, 1),
           "tail": (out.stdout if ok else (out.stderr or out.stdout)).strip()[-600:]}
    summary = json_output(out.stdout) if ok else None
    if summary is not None:
        if "consumed" in summary:
            errs = CN.validate_consumed(summary["consumed"])
            if errs:
                res["consumptionIssue"] = "; ".join(errs)[:300]
            else:
                res["consumed"] = CN.finalize(summary["consumed"])
        if summary.get("published") is False:
            res["skipped"] = True
    return res


def shadow_runtime_dir(brain_id: str) -> str:
    """Staged Brain runtime for the SHADOW lane: <image or repo>/brains/<dir>/runtime (deploy-job.sh stages Depth and Vegetation there)."""
    d = {"depth": "depth", "vegetation": "vegetation"}[brain_id]
    return os.path.normpath(os.path.join(HERE, "..", "..", "brains", d, "runtime"))


def run_shadow(brain_id: str, timeout: int = 900) -> dict:
    """Run the Brain's own runtime against its CANDIDATE release into its in-memory writer (shadow_run.py). Never writes Brain paths."""
    t0 = time.time()
    out = subprocess.run([PYTHON, os.path.join(HERE, "shadow_run.py"), brain_id], cwd=shadow_runtime_dir(brain_id), capture_output=True, text=True,
                         timeout=timeout)
    res = {"brainId": brain_id, "ok": out.returncode == 0, "exit": out.returncode, "seconds": round(time.time() - t0, 1)}
    if out.returncode == 0:
        res["output"] = json_output(out.stdout)
        res["ok"] = res["output"] is not None
    else:
        res["error"] = (out.stderr or out.stdout).strip()[-400:]
    return res


def shadow_lane_stage(manifest: dict, live, db, now: dt.datetime, write: bool, dry_run: bool, force: bool = False) -> list[dict]:
    """Internal SHADOW lane (control_manifest brains[*].shadowLane): due -> run -> summarise -> refuse on contract problems -> write
    /control/shadowLaneV1/{brainId}. One Brain's failure never stops the others or the cycle."""
    done = []
    for bid, b in sorted(manifest["brains"].items()):
        sl = b.get("shadowLane") or {}
        if not sl.get("enabled"):
            continue
        prev = live.get(SL.node(bid)) or {}
        if not (force or SL.due(prev, sl.get("cadenceHours", 24), now)):
            done.append({"brainId": bid, "shadow": "NOT_DUE", "lastRunAt": prev.get("runAt")})
            continue
        try:
            r = run_shadow(bid)
        except Exception as e:                                       # timeout etc.
            r = {"brainId": bid, "ok": False, "error": repr(e)[:300]}
        if not r.get("ok"):
            done.append({"brainId": bid, "shadow": "FAILED", "error": r.get("error")})
            if write and not dry_run:
                db.update({f"{SL.node(bid)}/lastFailure": {"at": iso(now), "error": str(r.get("error"))[:300]}})
            continue
        o = r["output"]
        doc = SL.summarize(bid, o["slot"], o["patches"], o["report"], o["release"], o["approvedPath"], iso(now),
                           os.environ.get("DEPLOYMENT_VERSION"), prev=prev)
        doc["inputs"] = o.get("inputs") or {}
        doc["seconds"] = r["seconds"]
        bad = SL.problems(doc)
        if bad:
            done.append({"brainId": bid, "shadow": "REFUSED", "problems": bad[:3]})
            continue
        if write or dry_run:
            db.update({SL.node(bid): doc})
        done.append({"brainId": bid, "shadow": "PUBLISHED" if write and not dry_run else "COMPUTED", "lakes": doc["lakeCount"],
                     "readinessCounts": doc["readinessCounts"], "approvedPath": doc["approvedPath"].get("status")})
    return done


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
            # the lock only bridges the gap until the started execution is visible; once that execution has
            # completed the real world says so and the lock is spent
            done = any((e.get("metadata") or {}).get("name") == (lock.get("execution") or "").rsplit("/", 1)[-1]
                       and (e.get("status") or {}).get("completionTime") for e in executions.get((ex or {}).get("job") or "") or [])
            if not done:
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


def score_cmd(env=None) -> list[str]:
    """The scorer invocation. WIND_MEASUREMENTS=on (set only at an approved deploy) attaches Wind's three measurements to
    /scores/wind (score_brains.py --wind-measurements: additive, no score.changed event). Anything else: OFF."""
    env = os.environ if env is None else env
    cmd = [PYTHON, os.path.join(HERE, "..", "brain-scores", "score_brains.py"), "--write", "--if-changed"]
    if env.get("WIND_MEASUREMENTS", "off") == "on":
        cmd.append("--wind-measurements")
    return cmd


def _runner_policy_or_none() -> dict | None:
    """The reviewed runner policy (runner-policy.json), or None when unreadable (the conditions-sources projection then says runner unknown)."""
    try:
        return RL.load_policy()
    except Exception:                                            # noqa: BLE001
        return None


def _fresh_lease_holder(a, brain_id: str, now: dt.datetime) -> str | None:
    """Holder of a Brain's unexpired runner lease (read-only), or None: no artifact store configured, no lease, an expired lease, or unreadable."""
    store = build_publication_store(a.artifact_store_dir, a.artifact_bucket)
    if store is None:
        return None
    lease, _ = RL.read(RL.orchestrator_view(store), brain_id)
    return (lease or {}).get("holder") if RL.fresh(lease, now) else None


def build_publication_store(directory: str | None, bucket: str | None = None):
    """The artifact store the publication stage uses: the private GCS bucket (PUBLICATION_ARTIFACT_BUCKET; the stage wraps it in the Orchestrator's least-privilege view and IAM
    enforces the same) or a local directory for review. None = not configured."""
    if bucket:
        from sector_brain_platform.object_bucket import GcsRestObjectStore
        return GcsRestObjectStore(bucket, TokenProvider())
    if not directory:
        return None
    from sector_brain_platform.publisher.storage import LocalDirObjectStore
    return LocalDirObjectStore(directory)


def build_shadow_publisher(store):
    from sector_brain_platform.publisher import ShadowPublisher, ShadowSink, PublishHistory, PublisherMode, default_registry, publisher_view
    from sector_brain_platform.publisher.storage import OverlayObjectStore
    # reads the real artifacts and history; its own records stay in memory (the Orchestrator may not write publishes/, and a shadow verdict is never a publication)
    return ShadowPublisher(default_registry(), PublishHistory(publisher_view(OverlayObjectStore(store))), ShadowSink(), mode=PublisherMode.SHADOW)


def build_live_publisher(store):
    """The LIVE Publisher. NEVER constructed by the scheduled cycle: arming needs the approved LiveAuthorization, a reconciled baseline, an RTDB client with the Publisher identity and the
    release resolver (docs/cortex/sessions/2026-10-28-orchestrator-cortex-3-1.md, gate G-ARM). Returns None so every Brain's run record says PUBLISHER_UNARMED / DIRECT_WRITER_ACTIVE."""
    return None


def runner_gate(a, brain_id: str, now: dt.datetime) -> tuple[bool, str]:
    """--runner-leases: may the cloud start this Brain? Unreadable store or policy = no (fail closed: a missing lease system never means a surprise cloud run)."""
    try:
        store = build_publication_store(a.artifact_store_dir, a.artifact_bucket)
        if store is None:
            return False, "NO_ARTIFACT_STORE"
        return RL.cloud_may_start(RL.orchestrator_view(store), RL.load_policy(), brain_id, now)
    except Exception as e:                                       # noqa: BLE001 - fail closed
        return False, f"LEASE_CHECK_FAILED:{type(e).__name__}"


def runner_primary_is_cloud(brain_id: str) -> bool:
    """Is the cloud this Brain's reviewed runner (runner-policy.json)? Unreadable policy = no (then the grant path fails closed and nothing starts)."""
    try:
        return RL.primary(RL.load_policy(), brain_id) == "cloud"
    except Exception:                                            # noqa: BLE001
        return False


def runner_grants_today(a, brain_id: str, now: dt.datetime) -> int:
    """Grants made today for this Brain: each counts as a run against the execution control's maxRunsPerDay (a grant is a run outside Cloud Run)."""
    try:
        store = build_publication_store(a.artifact_store_dir, a.artifact_bucket)
        return len(RL.grants_since(RL.orchestrator_view(store), brain_id, now.strftime("%Y-%m-%dT00:00:00Z"))) if store is not None else 0
    except Exception:                                            # noqa: BLE001 - unreadable: the grant itself then fails closed
        return 0


def regrant_cooldown_minutes(manifest: dict, brain_id: str) -> int:
    """A runner is granted a new cycle at most once per the Brain's staleness window (TIME Brains), else every 6 h, never more often than the lease TTL."""
    b = (manifest.get("brains") or {}).get(brain_id) or {}
    hours = (b.get("freshness") or {}).get("staleAfterHours") or b.get("staleAfterHours") or 6   # the control manifest keeps it under freshness
    return max(RL.DEFAULT_TTL_MINUTES, int(float(hours) * 60))


def grant_to_primary(a, brain_id: str, now: dt.datetime, cooldown_minutes: int = 360) -> tuple[bool, str, dict | None]:
    """--runner-leases, a Brain whose policy primary is not the cloud (Sector_Ops #51 C1): the Orchestrator grants that runner the lease for this cycle and starts
    nothing itself. A fresh lease of the same holder means its cycle is still in progress (not granted again). Unreadable store or policy = no grant (fail closed)."""
    try:
        store = build_publication_store(a.artifact_store_dir, a.artifact_bucket)
        if store is None:
            return False, "NO_ARTIFACT_STORE", None
        view, pol = RL.orchestrator_view(store), RL.load_policy()
        holder = RL.primary(pol, brain_id)
        cur, _ = RL.read(view, brain_id)
        if cur and cur.get("holder") == holder and RL.fresh(cur, now):
            return False, f"CYCLE_IN_PROGRESS:{holder}:{cur.get('cycleId')}", None
        last = (RL.grants_since(view, brain_id, iso(now - dt.timedelta(minutes=cooldown_minutes))) or [None])[-1]
        if last:                                                 # granted recently and not yet published: never a fresh cycle every hour
            return False, f"GRANTED_RECENTLY:{last['holder']}:{last['cycleId']} (cooldown {cooldown_minutes} min)", None
        if a.dry_run or a.no_execute:
            return False, f"WOULD_GRANT:{holder} (--dry-run/--no-execute)", None
        doc = RL.grant(view, pol, brain_id, holder, f"{brain_id}-{now:%Y%m%dT%H%MZ}", now)
        return True, f"GRANTED:{holder}:{doc['cycleId']}", doc
    except RL.LeaseBusy as e:
        return False, f"LEASE_BUSY:{e}", None
    except Exception as e:                                       # noqa: BLE001 - fail closed
        return False, f"GRANT_FAILED:{type(e).__name__}", None


class LocalCycleLock:
    """Local runner mode: no overlapping orchestrator cycles on this machine (PL-17), an exclusive non-blocking lock file instead of the Cloud Run execution list."""
    def __init__(self, path: str):
        self.path, self.fh = path, None

    def acquire(self) -> bool:
        import fcntl
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self.fh = open(self.path, "a+")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            self.fh.close()
            self.fh = None
            return False


PUBLISHER_JOB = "brain-publisher"
PUBLISHER_LOCAL = os.path.join(HERE, "..", "brain-publisher", "publish_job.py")


def run_publisher_locally(handoff: dict, *, auto_ok: bool, may_start: bool, bucket: str | None, live: bool, timeout: int = 900) -> dict:
    """Local Publisher mode (Sector_Ops #51 C1): the same Publisher pass as the brain-publisher job, as a subprocess of this cycle instead of a Cloud Run start.
    A dry run unless `live` (PUBLISHER_LOCAL_LIVE=on, its own approval); the pass re-checks the execution control and the cutover itself."""
    if not handoff.get("pending"):
        return {"started": False, "reason": "NOTHING_PENDING"}
    if not auto_ok:
        return {"started": False, "reason": "EXECUTION_PAUSED"}
    if not may_start:
        return {"started": False, "reason": "DRY_RUN_OR_NO_EXECUTE"}
    if not bucket:
        return {"started": False, "reason": "NO_ARTIFACT_BUCKET"}
    pub_token = os.environ.get("PUBLISHER_ACCESS_TOKEN")
    if not pub_token:                                            # the Publisher identity only: never the cycle's (orchestrator) token, never a gcloud fallback
        return {"started": False, "reason": "NO_PUBLISHER_TOKEN"}
    cmd = [PYTHON, PUBLISHER_LOCAL, "--artifact-bucket", bucket, "--max-artifacts", "4"] + (["--live"] if live else [])
    env = {k: v for k, v in os.environ.items() if k not in ("BRAIN_ACCESS_TOKEN", "PUBLISHER_ACCESS_TOKEN")}
    env["BRAIN_ACCESS_TOKEN"] = pub_token
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"started": True, "how": "local", "ok": False, "reason": "TIMED_OUT", "live": live}
    return {"started": True, "how": "local", "ok": r.returncode == 0, "exit": r.returncode, "live": live, "tail": (r.stdout + r.stderr)[-400:],
            "at": iso(dt.datetime.now(dt.timezone.utc))}


def start_publisher_if_needed(handoff: dict, executions: dict, tokens: TokenProvider, *, auto_ok: bool, may_start: bool) -> dict:
    """Hand-off mode: start the recurring Publisher job once when requests are pending. Never while automatic work is not permitted, never in a dry run / no-execute cycle, never
    while an execution of it is already running (single flight); the job re-checks the execution control and the cutover itself. No argument overrides: its deployed arguments decide
    whether it runs --live."""
    if not handoff.get("pending"):
        return {"started": False, "reason": "NOTHING_PENDING"}
    if not auto_ok:
        return {"started": False, "reason": "EXECUTION_PAUSED"}
    if not may_start:
        return {"started": False, "reason": "DRY_RUN_OR_NO_EXECUTE"}
    running = gcp.running_executions(executions.get(PUBLISHER_JOB) or [])
    if running:
        return {"started": False, "reason": "ALREADY_RUNNING", "execution": running[0]}
    try:
        op = gcp.run_job(tokens, PUBLISHER_JOB)
    except Exception as e:                                       # noqa: BLE001 - recorded; the requests stay pending for the next cycle
        return {"started": False, "reason": f"START_FAILED:{type(e).__name__}", "detail": str(e)[:200]}
    return {"started": True, "execution": (op.get("metadata") or {}).get("name"), "at": iso(dt.datetime.now(dt.timezone.utc))}


def gate_dispatch(todo: set, deferred: list) -> set:
    """Cortex M08 in the execution path: only recognised Brain identities run; an alias or unknown identity never runs; the legacy combined package is the ONLY dispatch of its two target
    Brains (a target Brain that the legacy package already covers is not also dispatched: no double dispatch, no duplicated scientific result)."""
    ok = set()
    for b in sorted(todo):
        r = DO.recognize(b)
        if r["kind"] in ("UNREGISTERED", "ALIAS"):
            deferred.append({"brainId": b, "why": f"{r.get('finding')}: {b!r} is not a Cortex target Brain or deployed package; not dispatched"})
        else:
            ok.add(b)
    covered = {t for b in ok if DO.recognize(b)["kind"] == "LEGACY_COMBINED" for t in DO.recognize(b)["targets"]}
    for b in sorted(ok & covered):
        deferred.append({"brainId": b, "why": "DOUBLE_DISPATCH_PREVENTED: the legacy combined package already covers this target Brain"})
    return ok - covered


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write nothing, start nothing")
    ap.add_argument("--no-execute", action="store_true", help="sync + plan + record, start nothing")
    ap.add_argument("--sync-jobs-only", action="store_true")
    ap.add_argument("--force-scores", action="store_true", help="publish scores/control even when nothing changed")
    ap.add_argument("--trigger", default="SCHEDULE", choices=("SCHEDULE", "MANUAL", "ADMIN"), help="why this cycle runs (recorded in the control state; default SCHEDULE)")
    ap.add_argument("--run-now", default=None, metavar="BRAIN", help="scoped manual run of one Brain (needs --scope); validated by orchestrator policy")
    ap.add_argument("--scope", default=None, help="scope for --run-now, e.g. guntersville, pilots")
    ap.add_argument("--requested-by", default="cli", help="who asked, recorded with the decision")
    ap.add_argument("--admin-reason", default=None, help="with --run-now: an explicit, separately authorized ADMIN run (allowed while the global execution "
                                                         "control is PAUSED; recorded in the execution ledger; never re-enables anything)")
    ap.add_argument("--control-only", action="store_true", help="evaluate and publish ONLY /control/orchestratorV1: no /jobs write, no execution, no score publication, no legacy record (a deliberate, side-effect-free evaluation)")
    ap.add_argument("--emit-control-state", default=None, metavar="FILE", help="write the computed control state JSON here (sample payloads, review)")
    ap.add_argument("--legacy-execution", action="store_true", help="old behaviour: start whatever the TIME/plan logic says, ignoring the PRE_PRODUCTION decision model")
    ap.add_argument("--emit-health-state", default=None, metavar="FILE", help="write the computed brain-health-v1 state (control/healthV1) JSON here (review, samples)")
    ap.add_argument("--publish-health", action="store_true", help="also publish control/healthV1 (brain-health-v1). OFF by default: enabling it is a recorded decision")
    ap.add_argument("--emit-engineering-status", default=None, metavar="FILE",
                    help="write the gated control/engineeringStatusV1 document (engineering-status-ops-v1) here; never writes the database")
    ap.add_argument("--publish-engineering-status", action="store_true",
                    help="also publish control/engineeringStatusV1 from the projection staged in THIS image. OFF by default: enabling it is decision O-1")
    ap.add_argument("--run-shadow-lane", action="store_true",
                    help="run the internal SHADOW lane for Brains with control_manifest shadowLane.enabled (candidate knowledge, in-memory, summary to "
                         "/control/shadowLaneV1/{id}; never authoritative or customer). OFF by default; enabled by the deployed job's arguments")
    ap.add_argument("--force-shadow-lane", action="store_true", help="with --run-shadow-lane: ignore the shadow cadence (ADMIN run)")
    ap.add_argument("--coordinate-publication", action="store_true",
                    help="PL-19 publication coordination: reconcile this cycle's and Cloud Run's executions with the sealed artifacts in the private store, record each run's publication outcome "
                         "(control/orchestrator.publication). OFF by default (also PUBLICATION_COORDINATION=on). Never arms the Publisher: a Brain is only handed to a live Publisher after an approved cutover")
    ap.add_argument("--hand-off-publication", action="store_true",
                    help="with --coordinate-publication (Sector_Ops #46 Q3): for each sealed artifact of a CENTRAL Brain write a create-only publication request and start brain-publisher "
                         "when requests are pending and automatic work is permitted. OFF by default (also PUBLICATION_HANDOFF=on); a dry run writes and starts nothing")
    ap.add_argument("--runner-leases", action="store_true",
                    help="Sector_Ops #50: honour runner leases (runner_lease.py, runner-policy.json): never start a Brain's Cloud Run job while another runner holds its lease, "
                         "or while its policy primary is not the cloud and failover is OFF; reconcile runner execution records in the publication stage. OFF by default "
                         "(also RUNNER_LEASES=on); needs the artifact store")
    ap.add_argument("--runner-mode", choices=("cloud", "local"), default=os.environ.get("RUNNER_MODE", "cloud"),
                    help="Sector_Ops #51 C1. cloud (default): unchanged. local: this cycle runs outside Cloud Run (a registered runner's machine) and makes NO Cloud Run or "
                         "Cloud Scheduler API call at all: /jobs is not synced, no Cloud Run job is started (a Brain whose policy primary is the cloud waits), the overlap "
                         "guard is a local lock file, and the Publisher pass runs as a local process. Implies --runner-leases")
    ap.add_argument("--local-lock", default=os.environ.get("RUNNER_LOCAL_LOCK"), help="local runner mode: the cycle lock file (default: next to the publication ledger)")
    ap.add_argument("--publisher-local-live", action="store_true",
                    help="local runner mode: run the local Publisher pass with --live (also PUBLISHER_LOCAL_LIVE=on; its own approval). Default: a dry run")
    ap.add_argument("--artifact-store-dir", default=os.environ.get("PUBLICATION_ARTIFACT_DIR"), help="directory holding the artifact store (local); the private bucket is a gated deployment resource")
    ap.add_argument("--artifact-bucket", default=os.environ.get("PUBLICATION_ARTIFACT_BUCKET"), help="private GCS bucket holding artifacts/, publishes/ and exports/orchestrator/ (the Orchestrator reads artifacts and writes only exports/orchestrator/)")
    ap.add_argument("--publication-ledger", default=os.environ.get("PUBLICATION_LEDGER"), help="JSON ledger file persisting run/publication records between cycles")
    ap.add_argument("--publication-cutover", default=os.environ.get("PUBLICATION_CUTOVER"), help=f"{PS.CUTOVER_SCHEMA} document naming Brains approved for CENTRAL publication; absent = every Brain on its direct writer")
    ap.add_argument("--emit-publication-state", default=None, metavar="FILE", help="write the publication stage result JSON here (review; Sector Ops reads control/orchestrator.publication)")
    ap.add_argument("--health-only", action="store_true", help="publish ONLY control/healthV1: implies --control-only and --publish-health, and additionally writes no control/orchestratorV1 "
                                                               "and asks no Brain for a plan (the exact write set is control/healthV1/* and nothing else)")
    a = ap.parse_args(argv)
    if a.health_only:
        a.control_only, a.publish_health = True, True
    a.coordinate_publication = (a.coordinate_publication or os.environ.get("PUBLICATION_COORDINATION") == "on") and not a.health_only
    a.hand_off_publication = (a.hand_off_publication or os.environ.get("PUBLICATION_HANDOFF") == "on") and a.coordinate_publication
    a.local_mode = a.runner_mode == "local"
    a.runner_leases = a.runner_leases or os.environ.get("RUNNER_LEASES") == "on" or a.local_mode
    a.publisher_local_live = a.publisher_local_live or os.environ.get("PUBLISHER_LOCAL_LIVE") == "on"
    if a.local_mode and not os.environ.get("BRAIN_ACCESS_TOKEN"):
        print("REFUSED: --runner-mode local needs BRAIN_ACCESS_TOKEN (a short-lived token of the intended identity); it never falls back to the gcloud login of "
              "whoever runs it", file=sys.stderr)
        return 2
    if a.local_mode:
        gcp.disable_cloud_calls("orchestrator local runner mode (--runner-mode local): no Cloud Run or Cloud Scheduler call")
    t0 = time.time()
    now = dt.datetime.now(dt.timezone.utc)
    if a.control_only:
        a.no_execute = True
    write = not a.dry_run
    tokens = TokenProvider()
    live = BrainRtdb(RTDB_URL, tokens, brain_id=WRITER)
    check_schema(live)
    db = live if write else _ReadThrough(live)
    # 0. the ONE authoritative execution switch (Cortex 2.7.0 PL-16): absent / unreadable / invalid => PAUSED (fail closed)
    try:
        ctl = EC.parse(live.get(EC.NODE))
    except Exception as e:                                       # unreadable is PAUSED, never "carry on"
        ctl = EC.parse(None)
        ctl["reason"] = f"execution control unreadable ({type(e).__name__}): fail closed (PAUSED)"
    auto_ok, auto_why = EC.automatic_allowed(ctl)
    admin = {"requestedBy": a.requested_by, "reason": a.admin_reason} if (a.run_now and a.admin_reason) else None
    print(f"execution control: {ctl['state']} ({ctl['reason']}); automatic work {'permitted' if auto_ok else 'NOT permitted'}"
          + (f"; ADMIN run of {a.run_now} by {a.requested_by}: {a.admin_reason}" if admin else ""), flush=True)

    # 1. /jobs
    if a.local_mode:                                             # nothing is read from or written about Cloud Run: /jobs keeps what the cloud last recorded
        records, executions, n_changed = {}, {}, 0
    else:
        records, executions, n_changed = sync_jobs(db, tokens, now, write and not a.control_only)
    print(f"jobs: {len(records)} records, {n_changed} changed", flush=True)
    if a.sync_jobs_only:
        return 0
    # no overlapping orchestrator cycles (PL-17): another running execution of this job owns the cycle; this one starts nothing
    me = os.environ.get("CLOUD_RUN_EXECUTION")
    others = [n for n in gcp.running_executions(executions.get(JOB_NAME) or []) if n != me] if me else []     # execution NAMES still running
    if a.local_mode:
        lock = LocalCycleLock(a.local_lock or os.path.join(os.path.dirname(os.path.abspath(a.publication_ledger or ".")), "orchestrator-cycle.lock"))
        if not lock.acquire():
            others = [f"local cycle lock {lock.path}"]
    if others:
        a.no_execute = True
        auto_ok, auto_why = False, f"another orchestrator cycle is running ({others[0]}): this cycle starts nothing"
        print(f"overlap guard: {auto_why}", flush=True)

    # 2. plan: the decision model (engine mode, active/parked, dependencies, material change) says what MAY run; the legacy TIME/plan logic only
    #    describes what is stale. Parked Brains are not even asked for a plan (a plan can cost provider/Engine calls).
    brains = live.get("brains") or {}
    health = live.get("health/brains") or {}
    state = live.get("control/orchestrator") or {}
    world = CP.load_world(live, now)
    activity = O.effective_activity(world["manifest"], world["overrides"])
    brain_plans = {b: brain_plan(b) for b, ex in EXECUTORS.items()
                   if (ex["kind"] == "in-process" or ex.get("planInProcess")) and b in brains and (a.legacy_execution or activity.get(b) == "ACTIVE") and not a.health_only and not a.local_mode
                   and (auto_ok and EC.brain_enabled(ctl, b) or (admin and a.run_now == b))}
    locks_now = state.get("locks") or {}
    run_now = (a.run_now, a.scope, a.requested_by) if a.run_now else None
    ctx, evaluation = CP.evaluate(world, now, {f"{b}|*": l for b, l in locks_now.items()}, brain_plans, run_now)
    allowed = set(evaluation["runs"])
    plan = orchestrate(with_single_flight(brains, executions, locks_now, now), health, now, brain_plans)
    for d in evaluation["decisions"]:
        if d["decision"] in ("RUN", "BLOCKED_DEPENDENCY", "BLOCKED_POLICY", "MANUAL_APPROVAL", "WAITING") and d["trigger"] != "SCHEDULE" or d["decision"] == "RUN":
            print(f"DECIDE {d['brainId']:20s} {d['trigger']:18s} {d['decision']:18s} {d['reason']}")
    for r in plan["runs"]:
        print(f"STALE {r['brainId']:20s} {'; '.join(r['reasons'])}" + (f" (after {r['after']})" if r.get("after") else "") + ("" if r["brainId"] in allowed or a.legacy_execution else "  -> not started: decision model says no"))
    for w in plan["waiting"]:
        print(f"WAIT {w['brainId']:20s} {'; '.join(w['reasons'])}")

    # 3. execute — only what the decision model allowed (RUN), in dependency waves; legacy TIME/plan logic only with --legacy-execution
    executed, deferred, locks, exec_records = [], [], {}, []
    started_async = set()
    starts = 0
    leases_granted = []                                          # --runner-leases: cycles granted to a runner outside Cloud Run this cycle (it starts nothing here)
    ledger = list(((world["prev"] or {}).get("executions") or {}).values())
    day = f"{now:%Y-%m-%d}"
    manifest = world["manifest"]
    todo = set(allowed) | ({r["brainId"] for r in plan["runs"]} if a.legacy_execution else set())
    todo = gate_dispatch(todo, deferred)
    for r in plan["runs"]:                       # stale by the legacy TIME/plan logic, but not allowed to run by the decision model: say why
        if r["brainId"] not in todo:
            why = next((d["reason"] for d in evaluation["decisions"] if d["brainId"] == r["brainId"] and d["trigger"] == "SCHEDULE"), "no RUN decision")
            deferred.append({"brainId": r["brainId"], "why": f"PRE_PRODUCTION decision model: {why}"})
    for d in evaluation["decisions"]:
        if d["brainId"] not in todo and d["decision"] in ("MANUAL_APPROVAL", "WAITING", "BLOCKED_DEPENDENCY") and d["trigger"] != "SCHEDULE":
            deferred.append({"brainId": d["brainId"], "why": f"{d['decision']}: {d['reason']}"})
    for wave in O.plan_waves(sorted(todo), manifest) if todo else []:
        for b in wave:
            dec = next((d for d in evaluation["decisions"] if d["brainId"] == b and d["decision"] == "RUN"), None)
            trigger = dec["trigger"] if dec else "SCHEDULE"
            why = dec["reason"] if dec else "legacy TIME/plan logic (--legacy-execution)"
            tgt = (manifest["brains"][b].get("executionTarget") or {})
            ex = EXECUTORS.get(b)
            if b in NOT_STARTED_HERE or not ex or not tgt.get("startedByOrchestrator", False):
                cmd = f"gcloud run jobs execute {tgt.get('job')} --region us-central1 --wait" if tgt.get("job") else "run locally from the Brain's branch"
                deferred.append({"brainId": b, "why": f"RUN allowed but not startable by the orchestrator ({NOT_STARTED_HERE.get(b, tgt.get('note') or 'legacy/manual target')}); manual: {cmd}"})
                continue
            if any(d["id"] in started_async for d in manifest["brains"][b].get("dependencies", [])):
                deferred.append({"brainId": b, "why": "an upstream was started this cycle; evaluated again next cycle"})
                continue
            # the execution control gate (PL-16, PL-17): global + per-Brain enablement, starts-per-cycle, runs-per-day, cost-per-day
            mine = [e for e in ledger + exec_records if e.get("brainId") == b and (e.get("startedAt") or "").startswith(day)
                    and e.get("status") in ("STARTED", "RUNNING", "SUCCEEDED", "SKIPPED", "FAILED", "DEGRADED")]
            runner_path = a.runner_leases and ex["kind"] == "cloud-run-job" and not runner_primary_is_cloud(b)
            granted_today = runner_grants_today(a, b, now) if runner_path else 0
            ok, gwhy = EC.gate(ctl, b, trigger, admin=admin if a.run_now == b else None, starts_this_cycle=starts, runs_today=len(mine) + granted_today,
                               cost_today=O.cost_rollup(mine, day).get("usd"))
            if not ok:
                deferred.append({"brainId": b, "why": f"execution control: {gwhy}"})
                print(f"HOLD {b:20s} {gwhy}", flush=True)
                continue
            if runner_path:
                gok, gwhy2, gdoc = grant_to_primary(a, b, now, regrant_cooldown_minutes(manifest, b))
                if gok:
                    starts += 1
                    leases_granted.append(gdoc)
                deferred.append({"brainId": b, "why": f"runner lease: {gwhy2}" + ("; the runner runs it, its execution is reconciled next cycles" if gok else "")})
                print(f"{'LEASE' if gok else 'HOLD '} {b:20s} runner lease: {gwhy2}", flush=True)
                continue
            if ex.get("leaseOnly"):                              # SI-A2 artifact job: no Cloud Run job is deployed, so only a runner lease may run it
                deferred.append({"brainId": b, "why": "artifact job (SI_ARTIFACT_JOB): lease-only and no runner lease was granted (needs --runner-leases and a "
                                                      "non-cloud runner-policy primary); no Cloud Run job is deployed for it"})
                print(f"HOLD {b:20s} artifact job: lease-only, not started", flush=True)
                continue
            if a.local_mode and ex["kind"] == "in-process":       # its `run.py --write` writes the database directly: never from a runner's machine
                deferred.append({"brainId": b, "why": "local runner mode: an in-process Brain writes the database directly and is never run from a local cycle "
                                                      "(it needs its own artifact job first; cutover plan SI-1)"})
                print(f"HOLD {b:20s} local runner mode: in-process writer, not run", flush=True)
                continue
            if a.local_mode and ex["kind"] == "cloud-run-job":
                deferred.append({"brainId": b, "why": "local runner mode: a Cloud Run job is never started from a local cycle (policy primary is the cloud)"})
                print(f"HOLD {b:20s} local runner mode: cloud primary, not started", flush=True)
                continue
            if a.runner_leases and ex["kind"] == "cloud-run-job":
                lok, lwhy = runner_gate(a, b, now)
                if not lok:
                    deferred.append({"brainId": b, "why": f"runner lease: {lwhy}"})
                    print(f"HOLD {b:20s} runner lease: {lwhy}", flush=True)
                    continue
            if a.dry_run or a.no_execute:
                deferred.append({"brainId": b, "why": "not executed (--dry-run/--no-execute)"})
                continue
            starts += 1
            started = dt.datetime.now(dt.timezone.utc)
            eid = f"{b}-{started:%Y%m%dT%H%M%SZ}"
            try:
                if ex["kind"] == "cloud-run-job":
                    res = start_job(b, tokens)
                    started_async.add(b)
                    eid = (res.get("execution") or eid).rsplit("/", 1)[-1]
                    locks[b] = {"execution": res.get("execution"), "startedAt": res["startedAt"], "lockedUntil": iso(now + dt.timedelta(minutes=LOCK_MINUTES))}
                else:
                    res = run_in_process(b, timeout=in_process_timeout(manifest, b))
            except Exception as e:                                   # one brain's failure never stops the cycle
                res = {"brainId": b, "ok": False, "error": repr(e)[:300]}
            ended = None if res.get("how") == "cloud-run-job" and res.get("ok") else dt.datetime.now(dt.timezone.utc)
            fc = None if res.get("ok") else O.classify_failure(res.get("error") or res.get("tail"))
            rec = O.execution_record(eid, b, trigger, why, started, ended, "STARTED" if ended is None else ("SUCCEEDED" if res.get("ok") else "FAILED"),
                                     scope=a.scope if a.run_now == b else None, input_fp=(dec or {}).get("inputFingerprint"),
                                     resources=manifest["brains"][b].get("resources"), failure_class=fc,
                                     # an in-process run executes THIS image's code; a Cloud Run job's version is read from its own `commit` label later
                                     code_version=os.environ.get("DEPLOYMENT_VERSION") if ex["kind"] == "in-process" else None,
                                     job_id=tgt.get("job") or ex.get("jobId"), consumed=res.get("consumed"))
            if res.get("consumptionIssue"):
                rec["consumptionIssue"] = res["consumptionIssue"]
            if admin and a.run_now == b:
                rec["admin"] = {"requestedBy": admin["requestedBy"], "reason": admin["reason"][:200]}           # auditable ADMIN run
            if res.get("skipped"):
                rec["status"], rec["statusDetail"] = "SKIPPED", "the Brain's own plan said SKIP (nothing published)"
            exec_records.append(rec)
            executed.append(res)
            print(f"{'✓' if res.get('ok') else '✗'} {b} [{trigger}] {res.get('execution') or res.get('tail', res.get('error', ''))[-200:]}", flush=True)

    # 4b. publication coordination (Cortex PL-19): what each Brain produced and what happened to it. Reads sealed artifacts and Cloud Run results; the Publisher is asked only after an
    #     approved cutover with a live Publisher supplied (none is, today), so nothing here writes a canonical Brain path. A failure here never breaks the cycle or the scores.
    publication = None
    if a.coordinate_publication:
        try:
            pstore = build_publication_store(a.artifact_store_dir, a.artifact_bucket)
            if pstore is None:
                publication = {"state": "UNAVAILABLE", "reason": "no artifact store configured (--artifact-store-dir / PUBLICATION_ARTIFACT_DIR)"}
            else:
                cloud_now = CP.executions_from_cloud_run(manifest, executions, records, now)
                seen_ids = {e["executionId"] for e in exec_records}
                terminal = [e for e in exec_records + [c for c in cloud_now if c["executionId"] not in seen_ids] if e.get("status") not in ("STARTED", "RUNNING")]
                if a.runner_leases:                                      # runs outside Cloud Run (a registered runner) are reconciled like Cloud Run ones
                    seen_ids |= {e["executionId"] for e in terminal}
                    kept, skipped = RL.reconcilable_executions(RL.orchestrator_view(pstore), set(EXECUTORS), since=iso(now - dt.timedelta(days=2)), exclude=seen_ids)
                    for e in skipped:                                    # fail closed: a run whose runner did not hold its cycle's lease is never published
                        print(f"SKIP {e['brainId']:20s} runner execution {e['executionId']}: {e['runner']} did not hold the lease for cycle {e['cycleId']}", flush=True)
                    terminal += kept
                publication = PS.run_stage(store=pstore, ledger_path=a.publication_ledger, executions=terminal, shadow=build_shadow_publisher(pstore),
                                           live=build_live_publisher(pstore), cutover_path=a.publication_cutover,
                                           paused_reason=None if auto_ok else "EXECUTION_PAUSED", dry_run=a.dry_run,
                                           handoff=a.hand_off_publication, run_id=f"orchestrator-{iso(now)}")
                publication["state"] = "COORDINATED"
                if publication["handoff"]["enabled"] and a.local_mode:
                    publication["handoff"]["publisherStart"] = run_publisher_locally(publication["handoff"], auto_ok=auto_ok, bucket=a.artifact_bucket,
                                                                                     may_start=write and not a.control_only and not a.no_execute, live=a.publisher_local_live)
                elif publication["handoff"]["enabled"]:
                    publication["handoff"]["publisherStart"] = start_publisher_if_needed(publication["handoff"], executions, tokens, auto_ok=auto_ok,
                                                                                         may_start=write and not a.control_only and not a.no_execute)
                # operational health of a CENTRAL Brain is the Orchestrator's, derived only from what the Publisher published (never written by the Publisher or the Brain)
                central_published = [b for b in publication["cutover"]["central"] if (publication["summary"]["brains"].get(b) or {}).get("published")]
                publication["healthMirror"] = HM.stage(db, central_published, write and not a.control_only)
                for r in exec_records:                                       # evidence replaces UNKNOWN; the scoring trigger below is unchanged
                    ch = (publication["outputChanged"].get(r["executionId"]) or {}).get("outputChanged")
                    if ch and r.get("outputChanged", "UNKNOWN") == "UNKNOWN":
                        r["outputChanged"] = ch
            print(f"publication: {publication['state']}" + (f" ({publication.get('reason')})" if publication.get("reason") else
                  f" collected {len(publication['reconcile']['collected'])}, missing {len(publication['reconcile']['missing'])}, failed runs {len(publication['reconcile']['failedRuns'])}, "
                  f"skipped runs {len(publication['reconcile']['skippedRuns'])}; "
                  f"Publisher {'ARMED' if publication['armed'] else 'unarmed'}; imported from Publisher history {len(publication['importedFromPublisherHistory']['imported'])}; "
                  f"central {publication['cutover']['central']}; per Brain " + json.dumps({b: {k: v[k] for k in ('runs', 'published', 'failed', 'notRequested', 'missingArtifacts')}
                                                                                               for b, v in publication['summary']['brains'].items()}, sort_keys=True)), flush=True)
            if a.emit_publication_state:
                json.dump(publication, open(a.emit_publication_state, "w"), indent=1, sort_keys=True)
        except Exception as e:                                       # the stage never breaks the cycle
            publication = {"state": "FAILED", "reason": repr(e)[:300]}
            print(f"publication: FAILED {e!r}", file=sys.stderr)

    # 4. scores / control — only after a state change
    seen = {b: PT.seen_token(brains.get(b)) for b in brains}      # S1: a COMPLETE Publisher publication (new artifactId) also counts as a Brain state change
    changed_brains = sorted(b for b in seen if seen[b] != (state.get("lastSeen") or {}).get(b))
    ran_in_process = [e["brainId"] for e in executed if e.get("how") == "in-process" and e.get("ok")]
    reason = ("brain state changed: " + ", ".join(changed_brains)) if changed_brains else \
             ("published this cycle: " + ", ".join(ran_in_process)) if ran_in_process else \
             (f"{n_changed} job record(s) changed" if n_changed else ("forced" if a.force_scores else None))
    scores = {"published": False, "why": reason or "nothing changed since the last cycle"}
    if reason and write and not a.control_only:
        scores.update(run_scorer(score_cmd()))
        print(f"scores: {'published' if scores['published'] else 'FAILED'} ({reason})", flush=True)
    else:
        print(f"scores: skipped ({scores['why']})")

    # 5. control plane: the compact read-only state Sector Ops renders (content-aware: unchanged sections are not rewritten)
    state_cp = None
    try:
        world2 = CP.load_world(live, dt.datetime.now(dt.timezone.utc)) if (executed and write) else world
        ctx2, ev2 = CP.evaluate(world2, now, {f"{b}|*": l for b, l in {**locks_now, **locks}.items()}, brain_plans, run_now)
        rq = CP.process_requests(live, world2, ctx2, write)
        cloud_execs = CP.executions_from_cloud_run(manifest, executions, records, now)
        for r in exec_records:                                   # downstream decisions of a Brain that just ran
            r["downstream"] = [{"brainId": d["brainId"], "decision": d["decision"]} for d in ev2["decisions"]
                               if d["trigger"] == "DEPENDENCY_CHANGED" and r["brainId"] in [c["id"] for c in manifest["brains"][d["brainId"]].get("dependencies", [])]]
        state_cp = CS.build_control_state(manifest, ctx2["mode"], now, registries=world2["registries"], health=world2["health"], scores=live.get("scores") or {},
                                          jobs=records, evaluation=ev2, prev=world["prev"], new_executions=exec_records + cloud_execs,
                                          locks={**locks_now, **locks}, trigger=a.trigger, duration_ms=int((time.time() - t0) * 1000),
                                          overrides=rq["overrides"], requests=rq["requests"], scheduler_states=CP.scheduler_states(tokens),
                                          plans=brain_plans, ctx=ctx2, overview_brains=world2.get("overviewBrains"))
        if a.emit_control_state:
            json.dump(state_cp, open(a.emit_control_state, "w"), indent=1, sort_keys=True)
        cp_paths = CS.changed_paths(state_cp, world["prev"])
        if a.health_only:
            print(f"control plane: evaluated in memory only (--health-only): {len(cp_paths)} section(s) would differ; control/orchestratorV1 NOT written")
        elif cp_paths and (write or a.dry_run):
            db.update(cp_paths)
        if not a.health_only:
            print(f"control plane: {len(cp_paths)} section(s) changed of {len(CS.SECTIONS)}; mode {state_cp['summary']['engineMode']}; "
                  f"active {state_cp['summary'].get('activeBrains')}; queued {state_cp['summary'].get('queued', [])}")
        # 5b. brain-health-v1 (control/healthV1): five health concepts side by side (G1 execution, G2 dependency + freshness). Computed only
        #     when asked for, published only with --publish-health (a recorded decision); it never changes what runs.
        if a.emit_health_state or a.publish_health:
            hw = CP.load_health_world(live)
            health_cp = CP.build_health_state(world2, state_cp, records, now, scheduler_states=CP.scheduler_states(tokens),
                                              sources=hw["sources"], source_health=hw["sourceHealth"], code_version=os.environ.get("DEPLOYMENT_VERSION"))
            if a.emit_health_state:
                json.dump(health_cp, open(a.emit_health_state, "w"), indent=1, sort_keys=True)
            if a.publish_health:
                h_paths = CP.BH.changed_paths(health_cp, live.get(CP.HEALTH_NODE) or {})
                if h_paths and (write or a.dry_run):
                    db.update(h_paths)                                   # ONE atomic multi-location PATCH: old snapshot or new snapshot, never half
                body = json.dumps(h_paths, separators=(",", ":"), sort_keys=True) if h_paths else ""
                print(f"health plane: {len(h_paths)} section(s) changed of {len(CP.BH.SECTIONS)}; aggregate {health_cp['summary'].get('aggregateCounts')}; "
                      f"paths {sorted(h_paths)}; bytes {len(body)}; contentFingerprint {health_cp['summary'].get('contentFingerprint')}; "
                      f"codeVersion {health_cp['summary'].get('codeVersion')}")
    except Exception as e:                                       # the control plane must never break the cycle or the score publication
        print(f"control plane: FAILED {e!r}", file=sys.stderr)

    # 5c. internal SHADOW lane (Brains without an APPROVED knowledge release): experimental, isolated, never authoritative or customer
    shadow = []
    if a.run_shadow_lane and a.local_mode:
        print("shadow lane: not run (local runner mode runs no Brain code in this process)")
    elif a.run_shadow_lane and not a.control_only and not auto_ok:
        print(f"shadow lane: not run ({auto_why})")
    elif a.run_shadow_lane and not a.control_only:
        try:
            shadow = shadow_lane_stage(manifest, live, db, now, write, a.dry_run, force=a.force_shadow_lane)
        except Exception as e:                                       # never breaks the cycle
            print(f"shadow lane: FAILED {e!r}", file=sys.stderr)
        for r in shadow:
            print(f"shadow lane: {r['brainId']} {r['shadow']} " + json.dumps({k: v for k, v in r.items() if k not in ('brainId', 'shadow')}, default=str))

    # 5d. engineering status for Sector Ops (engineering-status-ops-v1 at control/engineeringStatusV1). The document comes ONLY from the projection
    #     staged into this image at deploy time (the exact deployed commit); ESP.gate() publishes it or an explicit UNAVAILABLE with the reason.
    #     Computed only when asked for; written only with --publish-engineering-status (decision O-1). It never changes what runs.
    if a.emit_engineering_status or a.publish_engineering_status:
        try:
            dv = os.environ.get("DEPLOYMENT_VERSION")
            es_doc = ESP.gate(ESP.load_staged(HERE), deployed_commit=ESP.deployed_commit(dv), now_iso=iso(now), deployment_version=dv)
            if es_doc.get("state") == "AVAILABLE":
                # Cortex 2.6.0 four dimensions: live runtime readiness + internal operation from this cycle's evidence (control state, scheduler
                # states, shadow summaries). A leak or failure here publishes the static document instead; it never blocks the publication.
                try:
                    ov = BOPS.overlay(es_doc, manifest, (state_cp or {}).get("brains"), scheduler_states=CP.scheduler_states(tokens),
                                      shadow_docs=live.get(SL.NODE_ROOT) or {}, plans=brain_plans, now=now, control=ctl)
                    bad = ESP.leaks(ov)
                    if bad:
                        print(f"engineering status: live operations withheld (leak check: {bad[:3]})", file=sys.stderr)
                    else:
                        es_doc = ov
                        print(f"engineering status: operations {BOPS.counts(es_doc)}")
                except Exception as e:
                    print(f"engineering status: live operations FAILED {e!r} (static document published)", file=sys.stderr)
            if a.emit_engineering_status:
                json.dump(es_doc, open(a.emit_engineering_status, "w"), indent=1, sort_keys=True)
            if a.publish_engineering_status and not a.health_only and (write or a.dry_run):   # --health-only's write set stays control/healthV1 only
                db.update({ESP.NODE: es_doc})
            print(f"engineering status: {es_doc['state']}" + (f" ({es_doc['reason']})" if es_doc.get("reason") else
                  f" @ {es_doc['generatedFrom']['sourceCommit'][:12]}") + ("" if a.publish_engineering_status and not a.health_only else " (not published)"))
        except Exception as e:                                   # never breaks the cycle
            print(f"engineering status: FAILED {e!r}", file=sys.stderr)

    # 5e. conditions sources for Sector Ops (sector-conditions-sources-v1 at control/conditionsSourcesV1, Sector_Ops #53 spec §7). Only with env
    #     CONDITIONS_SOURCES_PROJECTION=1 (default OFF: nothing is probed, read or written); at most every 15 min; never with --health-only or
    #     --control-only (their write sets stay what they are). Probes the Engine's GET /conditions read-only; a failed probe never breaks the cycle.
    if CSP.enabled() and not a.health_only and not a.control_only:
        try:
            csp = CSP.stage(live, db, now, write=write, dry_run=a.dry_run, brains=brains, policy=_runner_policy_or_none(),
                            lease_holder=lambda b: _fresh_lease_holder(a, b, now))
            print(f"conditions sources: {json.dumps(csp, sort_keys=True)}", flush=True)
        except Exception as e:                                   # never breaks the cycle
            print(f"conditions sources: FAILED {e!r}", file=sys.stderr)

    # 6. record
    record = {"version": "orchestrator-v1", "lastRunAt": iso(now), "durationMs": int((time.time() - t0) * 1000),
              "mode": "dry-run" if a.dry_run else ("no-execute" if a.no_execute else "cycle"),
              "plan": plan, "brainPlans": brain_plans, "executed": executed, "deferred": deferred, "shadow": shadow,
              "locks": {**{b: l for b, l in (state.get("locks") or {}).items() if l.get("lockedUntil", "") > iso(now) and b not in locks}, **locks},
              "lastSeen": {**(state.get("lastSeen") or {}), **{b: v for b, v in seen.items() if v}} if write else state.get("lastSeen"),
              "jobsSynced": len(records), "jobsChanged": n_changed, "scores": scores, "executionControl": EC.summary(ctl)}
    if publication is not None:
        record["publication"] = {k: publication[k] for k in ("state", "reason", "armed", "cutover", "summary", "healthMirror", "handoff") if k in publication}
    if write and not a.control_only:
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
