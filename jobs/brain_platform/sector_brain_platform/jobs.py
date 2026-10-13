"""The Engine-owned `/jobs/{jobId}` contract (jobs-v1) — what Sector Ops shows on Jobs & Schedules.

ENGINE OWNS TRUTH. One canonical sync path builds every record here from
  * the static manifest below (owner, purpose, classification, data flow, policies — facts about the
    *design* of each workload, reviewed in code), and
  * the live cloud state (Cloud Scheduler is authoritative for enabled / cron / timezone / nextScheduledAt;
    Cloud Run Jobs for resources, executions, last start / completion / success / failure, duration).

Pure: `build_records()` takes already-fetched API responses; `sector_brain_platform.gcp` fetches them and
`jobs/brain-orchestrator` publishes as the platform writer. No brain writes `/jobs` (ownership: platform-only).
Never published here: tokens, service-account identities, env var values, private bucket paths, secrets.
"""
from __future__ import annotations

import datetime as dt

from .timeutil import iso, parse_time

JOBS_CONTRACT_VERSION = "jobs-v1"
CLASSIFICATIONS = ("PRODUCTION", "INTERNAL", "RESEARCH", "SHADOW")
EXECUTION_MODES = ("SCHEDULED", "MANUAL", "EVENT_DRIVEN", "DISABLED")
RUNTIME_STATUSES = ("HEALTHY", "RUNNING", "WARNING", "FAILED", "STALE", "DISABLED", "PAUSED", "UNKNOWN")
TRIGGERS = ("scheduler", "orchestrator", "dispatcher", "manual", "request")
RECENT_EXECUTIONS = 20          # sample for average runtime / failure count

# ---------------------------------------------------------------------------------------------- manifest
# Design facts per workload. `trigger` says who starts it: scheduler (Cloud Scheduler → this job),
# orchestrator (brain-orchestrator decides), dispatcher (another job triggers it when there is work),
# manual (a person), request (a serving service / function). `expectedRunsPerDay` is only given where no
# cron can derive it (an estimate, labelled as such in the record).
MANIFEST: dict[str, dict] = {
    "sector-engine": {
        "displayName": "Sector Engine (customer API)", "owner": "sector-engine", "kind": "Cloud Run service",
        "classification": "PRODUCTION", "environment": "cloud-run-service", "trigger": "request",
        "purpose": "Customer-facing /conditions, /lakes, /health; the only customer path.",
        "inputs": ["open-meteo-forecast", "usgs-nwis", "tva-restapi", "usace-cwms-pool"],
        "outputs": ["GET /conditions", "GET /lakes", "GET /health"], "brainPublishInJob": False,
        "freshnessPolicy": "request-time computation; serving revision = tagged main (docs/production/PRODUCTION_LINEAGE.md)",
        "retryPolicy": "n/a (request path)",
    },
    "conditions": {"displayName": "Cloud Function: conditions", "owner": "sector-engine", "kind": "Cloud Function",
                   "classification": "PRODUCTION", "environment": "cloud-function", "trigger": "request",
                   "purpose": "Customer app endpoint (scale-to-zero).", "brainPublishInJob": False},
    "appstorenotifications": {"displayName": "Cloud Function: appstorenotifications", "owner": "sector-engine", "kind": "Cloud Function",
                              "classification": "PRODUCTION", "environment": "cloud-function", "trigger": "request",
                              "purpose": "App Store server notifications (scale-to-zero).", "brainPublishInJob": False},
    "adminlistusers": {"displayName": "Cloud Function: adminlistusers", "owner": "sector-engine", "kind": "Cloud Function",
                       "classification": "PRODUCTION", "environment": "cloud-function", "trigger": "request",
                       "purpose": "Admin user listing (scale-to-zero).", "brainPublishInJob": False},
    "tournamentpage": {"displayName": "Cloud Function: tournamentpage", "owner": "sector-engine", "kind": "Cloud Function",
                       "classification": "PRODUCTION", "environment": "cloud-function", "trigger": "request",
                       "purpose": "Tournament page (scale-to-zero).", "brainPublishInJob": False},
    "playnotifications": {"displayName": "Cloud Function: playnotifications", "owner": "sector-engine", "kind": "Cloud Function",
                          "classification": "PRODUCTION", "environment": "cloud-function", "trigger": "request",
                          "purpose": "Play notifications (scale-to-zero).", "brainPublishInJob": False},
    "wind-candidate-read": {
        "displayName": "Wind candidate read service", "owner": "wind", "kind": "Cloud Run service",
        "classification": "INTERNAL", "environment": "cloud-run-service", "trigger": "request",
        "purpose": "Serves the candidate wind bundles to the master inspector (3 UIDs, 4 lakes). Scale-to-zero. Not customer-facing.",
        "inputs": ["archive:wind-candidate (private)"], "outputs": ["latest/<lake>.json.gz (authenticated)"], "brainPublishInJob": False,
    },
    "wind-hourly": {
        "displayName": "Wind hourly (NBM / RTMA-RU / METAR archive + Wind Brain publish)", "owner": "wind", "kind": "Cloud Run job",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "scheduler",
        "purpose": "Archive the newest NBM cycle (catch-up of missed cycles), RTMA-RU quarter-hours and METAR, then publish the Wind Brain slot. "
                   "Primary internal wind pipeline; the candidate SCIENCE is RESEARCH_CANDIDATE — production wind stays Open-Meteo in-process.",
        "scienceStatus": "RESEARCH_CANDIDATE (not the production wind source)",
        "inputs": ["noaa-nbm-v5", "noaa-rtma-ru", "iem-metar-wind"],
        "outputs": ["archive:wind-candidate (private)", "/brains/wind", "/lakeFleet/{k}/slots/wind", "/lakes/{k}/states/wind", "/snapshots/{k}/latest/wind"],
        "brainDependencies": [], "statePaths": ["/brains/wind", "/health/brains/wind", "/health/jobs/wind-hourly", "/lakes/{k}/states/wind"],
        "brainPublishInJob": True,
        "retryPolicy": "Cloud Run task retries 1; Cloud Scheduler retry 5 s → 1 h (5 doublings)",
        "freshnessPolicy": "NBM cycle hourly (newest complete cycle; early exit when already archived), RTMA-RU 15 min catch-up 3 h, METAR daily refresh; Wind Brain staleAfterHours 1.5",
    },
    "water-temp-tva-archive": {
        "displayName": "Water Temp TVA archive (hourly)", "owner": "water-temp", "kind": "Cloud Run job",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "scheduler",
        "purpose": "Archive TVA observed-data-48-hours (water temperature, flow, elevation) every hour: the feed retains ~24 h, so an hourly cadence is required to keep a continuous record.",
        "inputs": ["tva-restapi (observed-data-48-hours)"], "outputs": ["archive:water-temp-tva (GCS)"],
        "brainDependencies": [], "consumers": ["water-temp", "lake-brain"], "brainPublishInJob": False,
        "retryPolicy": "Cloud Run task retries 1; Cloud Scheduler retry", "freshnessPolicy": "hourly; the source window is 48 h with ~24 h retention",
    },
    "hydrology-hourly": {
        "displayName": "Hydrology hourly (MRMS catchment rain, Guntersville)", "owner": "water-clarity", "kind": "Cloud Run job",
        "classification": "RESEARCH", "environment": "cloud-run-job", "trigger": "scheduler",
        "purpose": "MRMS Pass-2 catchment rainfall for the Clarity Stage 3–5 research path (one lake). No customer path reads it (iOS does not call /clarity/state).",
        "inputs": ["noaa-mrms", "usgs-nwis"], "outputs": ["archive:lake-surface/hydrology"], "brainDependencies": [], "brainPublishInJob": False,
        "retryPolicy": "Cloud Run task retries 1", "freshnessPolicy": "paused 2026-10-13 (cost decision); resume when the Clarity research path needs it",
    },
    "clarity-current-hourly": {
        "displayName": "Clarity current hourly (research precompute)", "owner": "water-clarity", "kind": "Cloud Run job",
        "classification": "RESEARCH", "environment": "cloud-run-job", "trigger": "scheduler",
        "purpose": "Clarity Stage 5 current-clarity precompute from the feat/clarity-algal-warning lineage (not on main). Read only by research server code and research iOS worktrees.",
        "inputs": ["archive:lake-surface/hydrology", "archive:lake-surface/clarity"], "outputs": ["archive:lake-surface/clarity/current"],
        "brainDependencies": [], "brainPublishInJob": False, "sourceLineage": "feat/clarity-algal-warning @ 03937913 (explicit exception; jobs/lake-surface/LINEAGE.md)",
        "retryPolicy": "Cloud Run task retries 1", "freshnessPolicy": "paused 2026-10-13 (cost decision)",
    },
    "lake-surface-dispatch": {
        "displayName": "Lake surface dispatch (daily Sentinel-2 discovery)", "owner": "water-clarity", "kind": "Cloud Run job",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "scheduler",
        "purpose": "Cheap single-task discovery: for every lake, ask STAC for the newest Sentinel-2 pass and compare with the published latest.json; "
                   "trigger lake-surface-daily only for the lakes with a newer pass. Never runs the heavy pipeline itself.",
        "inputs": ["sentinel-2-l2a (STAC metadata only)", "archive:lake-surface/clarity (latest.json)"], "outputs": ["archive:lake-surface/dispatch", "Cloud Run Jobs API: lake-surface-daily:run (overrides --lakes)"],
        "brainDependencies": [], "triggers": ["lake-surface-daily"], "brainPublishInJob": False,
        "retryPolicy": "Cloud Run task retries 1", "freshnessPolicy": "daily 03:00 America/Chicago; Sentinel-2 revisit 2–3 days so most days dispatch a subset",
    },
    "lake-surface-daily": {
        "displayName": "Lake surface daily (Sentinel-2 clarity rasters)", "owner": "water-clarity", "kind": "Cloud Run job",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "dispatcher", "triggeredBy": "lake-surface-dispatch",
        "purpose": "Heavy Sentinel-2 L2A clarity rasters per lake. Feeds the Water Clarity Brain (latest.json); no customer path reads it (production reads arms/latest.json, which nothing writes).",
        "inputs": ["sentinel-2-l2a"], "outputs": ["archive:lake-surface/clarity"], "brainDependencies": [], "consumers": ["water-clarity"], "brainPublishInJob": False,
        "sourceLineage": "feat/clarity-algal-warning @ 03937913 (explicit exception; jobs/lake-surface/LINEAGE.md) — not redeployed by this change",
        "retryPolicy": "Cloud Run task retries 1; 8 parallel tasks", "freshnessPolicy": "only when the dispatcher finds a newer pass (LOOKBACK_DAYS 14)",
    },
    "clarity-candidate-shadow": {
        "displayName": "Clarity candidate shadow (private research)", "owner": "water-clarity", "kind": "Cloud Run job",
        "classification": "SHADOW", "environment": "cloud-run-job", "trigger": "scheduler",
        "purpose": "Private candidate shadow run. Paused; stays paused (no promotion, no exposure).",
        "inputs": ["sentinel-2-l1c (private)"], "outputs": ["archive:clarity-candidate (private)"], "brainDependencies": [], "brainPublishInJob": False,
        "retryPolicy": "Cloud Run task retries 1", "freshnessPolicy": "paused",
    },
    "lake-brain": {
        "displayName": "Lake Brain (pilot: 5 lakes)", "owner": "lake-brain", "kind": "Cloud Run job",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "orchestrator", "expectedRunsPerDay": 8,
        "purpose": "Lake level / trend / baseline state for the 5 pilot lakes from the operator feeds; the brain's own plan() skips current lakes. Started by brain-orchestrator when due or stale (staleAfterHours 3), never by a blind cron.",
        "inputs": ["tva-restapi", "usace-cwms-pool", "usgs-nwis-lake-elevation", "archive:water-temp-tva (read-only)", "archive:lake-brain (history, baselines, presence — private)"],
        "outputs": ["/brains/lake-brain", "/lakes/{k}/brain", "/lakes/{k}/states/lake", "/lakeFleet/{k}/slots/lake", "/snapshots/{k}/latest/lakeState", "/lakes/{k}/speciesPresence"],
        "brainDependencies": [], "statePaths": ["/brains/lake-brain", "/health/brains/lake-brain", "/lakes/{k}/states/lake"], "brainPublishInJob": True,
        "retryPolicy": "orchestrator backoff 5 / 15 / 45 min after a FAILED run, then needs attention", "freshnessPolicy": "TIME: staleAfterHours 3; per-state nextCheckAt from the binding cadence",
    },
    "water-temp-brain": {
        "displayName": "Water Temperature Brain", "owner": "water-temp", "kind": "Cloud Run job",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "orchestrator", "expectedRunsPerDay": 4,
        "purpose": "Runs the production water-temperature path and publishes the Water Temp slot. Started by brain-orchestrator only when the 6-h freshness rule requires it; no every-3-h cron.",
        "inputs": ["usgs-nwis-00010", "usace-cwms-water-temp", "open-meteo-forecast", "archive:water-temp-tva (read-only)"],
        "outputs": ["/brains/water-temp", "/lakes/{k}/states/waterTemp", "/lakeFleet/{k}/slots/waterTemp", "/snapshots/{k}/latest/waterTemperature"],
        "brainDependencies": [], "statePaths": ["/brains/water-temp", "/health/brains/water-temp", "/lakes/{k}/states/waterTemp"], "brainPublishInJob": True,
        "retryPolicy": "orchestrator backoff 5 / 15 / 45 min after a FAILED run", "freshnessPolicy": "TIME: staleAfterHours 6",
    },
    "water-clarity-brain": {
        "displayName": "Water Clarity Brain", "owner": "water-clarity", "kind": "Cloud Run job",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "manual",
        "purpose": "Publishes the clarity slot from /conditions and the lake-surface latest.json. MANUAL by decision (docs/brains/WATER_CLARITY_BRAIN_SCHEDULING.md): a daily cron would re-read 621 lakes with no new satellite pass.",
        "inputs": ["GET /conditions (sector-engine)", "archive:lake-surface/clarity (latest.json)"],
        "outputs": ["/brains/water-clarity", "/lakes/{k}/states/waterClarity", "/lakeFleet/{k}/slots/waterClarity", "/snapshots/{k}/latest/waterClarity"],
        "brainDependencies": [], "statePaths": ["/brains/water-clarity", "/health/brains/water-clarity"], "brainPublishInJob": True,
        "retryPolicy": "manual", "freshnessPolicy": "TIME: staleAfterHours 26 (documented follow-up: dispatcher-driven publish after a satellite update)",
    },
    "biological-brain": {
        "displayName": "Biological Brain (species knowledge)", "owner": "biological-state", "kind": "in-process (brain-orchestrator)",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "orchestrator", "expectedRunsPerDay": 0,
        "purpose": "Version-driven: publishes only when the private research bundle's researchVersion / manifest changes (its own plan()). No cron.",
        "inputs": ["bundle:biology (private)"], "outputs": ["/species/{id}", "/brains/biological-state"], "brainDependencies": [],
        "statePaths": ["/brains/biological-state", "/health/brains/biological-state", "/species"], "brainPublishInJob": True,
        "retryPolicy": "orchestrator backoff", "freshnessPolicy": "VERSION (never by age)",
    },
    "sector-intelligence-brain": {
        "displayName": "Sector Intelligence (pilot evaluation)", "owner": "sector-intelligence", "kind": "in-process (brain-orchestrator)",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "orchestrator", "expectedRunsPerDay": 2,
        "purpose": "Fingerprint-driven: re-evaluates the 5 pilot lakes only when an upstream Brain state, the serving revision or the catalog changed. No cron; no customer consumption.",
        "inputs": ["/brains/*", "/health/brains/*", "/snapshots/{pilot}/latest", "/species", "/lakes/{pilot}/speciesPresence", "GET /lakes"],
        "outputs": ["/brains/sector-intelligence", "/lakes/{k}/states/intelligence", "/lakeFleet/{k}/slots/intelligence"],
        "brainDependencies": ["lake-brain", "water-temp", "water-clarity", "wind", "biological-state"],
        "statePaths": ["/brains/sector-intelligence", "/health/brains/sector-intelligence"], "brainPublishInJob": True,
        "retryPolicy": "orchestrator backoff", "freshnessPolicy": "FINGERPRINT; registry refresh after 24 h",
    },
    "brain-scores": {
        "displayName": "Brain scores + control plane publish", "owner": "brain-platform", "kind": "in-process (brain-orchestrator)",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "orchestrator", "expectedRunsPerDay": 24,
        "purpose": "Recomputes /scores, /control/overview, /control/fleet and /control/beta from published facts; writes only what changed.",
        "inputs": ["/brains", "/health", "/validation", "/lakeFleet", "/sources", "/jobs"], "outputs": ["/scores/*", "/control/*"], "brainDependencies": [],
        "brainPublishInJob": False, "retryPolicy": "next orchestrator cycle", "freshnessPolicy": "after any Brain state change; otherwise only when a stale/health classification flips",
    },
    "brain-orchestrator": {
        "displayName": "Brain Orchestrator (hourly wake-up)", "owner": "brain-platform", "kind": "Cloud Run job",
        "classification": "INTERNAL", "environment": "cloud-run-job", "trigger": "scheduler",
        "purpose": "Syncs /jobs from Cloud Scheduler + Cloud Run, plans which Brains are due (time / version / fingerprint), starts lake-brain / water-temp-brain when due, runs Biological / Intelligence in-process when their plan() says PUBLISH, then publishes scores and control.",
        "inputs": ["Cloud Scheduler (read)", "Cloud Run Jobs (read + run)", "/brains", "/health"], "outputs": ["/jobs/*", "/control/orchestrator", "/scores/*", "/control/*"],
        "brainDependencies": [], "triggers": ["lake-brain", "water-temp-brain"], "brainPublishInJob": False,
        "retryPolicy": "Cloud Run task retries 0 (the next hourly wake-up retries)", "freshnessPolicy": "hourly wake-up; cheap when nothing is due",
    },
}


# ---------------------------------------------------------------------------------------------- helpers
def cron_runs_per_day(cron: str | None) -> float | None:
    """Expected runs per day for the simple crons in use; None when it cannot be read."""
    if not cron:
        return None
    p = cron.split()
    if len(p) != 5:
        return None
    minute, hour, dom, mon, dow = p
    if dom != "*" or mon != "*" or dow != "*":
        return None
    def count(field: str, span: int) -> int | None:
        if field == "*":
            return span
        if field.startswith("*/") and field[2:].isdigit() and int(field[2:]) > 0:
            return len(range(0, span, int(field[2:])))
        if all(x.isdigit() for x in field.split(",")):
            return len(set(field.split(",")))
        return None
    m, h = count(minute, 60), count(hour, 24)
    return None if m is None or h is None else float(m * h)


def _res(run_job: dict | None) -> dict | None:
    if not run_job:
        return None
    try:
        spec = run_job["spec"]["template"]["spec"]
        t = spec["template"]["spec"]
        lim = (t["containers"][0].get("resources") or {}).get("limits") or {}
    except (KeyError, IndexError, TypeError):
        return None
    cpu = lim.get("cpu")
    mem = lim.get("memory")
    out = {"cpu": float(cpu[:-1]) / 1000 if isinstance(cpu, str) and cpu.endswith("m") else (float(cpu) if cpu else None),
           "memoryGi": (float(mem[:-2]) / 1024 if mem.endswith("Mi") else float(mem[:-2])) if isinstance(mem, str) and mem[-2:] in ("Gi", "Mi") else None,
           "tasks": spec.get("taskCount"), "parallelism": spec.get("parallelism") or spec.get("taskCount"),
           "taskTimeoutS": int(t["timeoutSeconds"]) if str(t.get("timeoutSeconds", "")).isdigit() else None}
    return {k: v for k, v in out.items() if v is not None}


def _exec_facts(executions: list[dict] | None) -> dict:
    """lastStartedAt / lastCompletedAt / lastSuccessfulAt / lastFailedAt / durationMs / running / failureCount / avg runtime
    from a list of Cloud Run executions (newest first or not; sorted here)."""
    out: dict = {}
    if not executions:
        return out
    def created(e):
        return (e.get("metadata") or {}).get("creationTimestamp") or e.get("createTime") or ""
    ex = sorted(executions, key=created, reverse=True)[:RECENT_EXECUTIONS]
    durs, fails, ok = [], 0, None
    for e in ex:
        st = e.get("status") or e
        s, c = st.get("startTime"), st.get("completionTime")
        failed = bool(st.get("failedCount")) or bool(st.get("cancelledCount"))
        succeeded = bool(st.get("succeededCount")) and not failed and c
        if s and c:
            d = (parse_time(c) - parse_time(s)).total_seconds() * 1000
            if succeeded:
                durs.append(d)
        if failed:
            fails += 1
            if "lastFailedAt" not in out:
                out["lastFailedAt"] = c or s
                cond = next((x for x in (st.get("conditions") or []) if x.get("type") == "Completed" and x.get("status") == "False"), None)
                if cond and cond.get("message"):
                    out["lastError"], out["lastErrorAt"] = str(cond["message"])[:300], c or s
        if succeeded and ok is None:
            ok = e
    newest = ex[0]
    st0 = newest.get("status") or newest
    out["lastStartedAt"] = st0.get("startTime") or created(newest) or None
    out["lastCompletedAt"] = st0.get("completionTime")
    out["running"] = not st0.get("completionTime")
    if ok is not None:
        oks = ok.get("status") or ok
        out["lastSuccessfulAt"] = oks.get("completionTime")
        s, c = parse_time(oks.get("startTime")), parse_time(oks.get("completionTime"))
        if s and c:
            out["durationMs"] = int((c - s).total_seconds() * 1000)
    out["failureCount"] = fails
    out["recentRuns"] = len(ex)
    if durs:
        out["recentAverageRuntimeMs"] = int(sum(durs) / len(durs))
    return out


def _runtime_status(sched_state: str | None, ex: dict, deployed: bool, trigger: str) -> str:
    if not deployed and trigger != "request":
        return "UNKNOWN"
    if ex.get("running"):
        return "RUNNING"
    if sched_state == "PAUSED" and trigger == "scheduler":
        return "PAUSED"
    if ex.get("lastCompletedAt") and ex.get("lastFailedAt") and ex["lastFailedAt"] >= (ex.get("lastSuccessfulAt") or ""):
        return "FAILED"
    if ex.get("lastSuccessfulAt"):
        return "HEALTHY"
    return "UNKNOWN"


def job_record(job_id: str, manifest: dict, scheduler: dict | None, run_job: dict | None, executions: list[dict] | None,
               now: dt.datetime, synced_by: str, brain_health: dict | None = None, service: dict | None = None) -> dict:
    """One `/jobs/{jobId}` record. `scheduler`: the Cloud Scheduler job named `job_id` (or None); `run_job`: the Cloud Run
    job (v1 API shape, or None when not deployed); `executions`: its recent executions; `brain_health`: /health/brains/{owner}
    for in-process brains (their last run is their publish); `service`: Cloud Run service (v1) for request-driven services."""
    trigger = manifest.get("trigger") or "manual"
    deployed = run_job is not None or service is not None or manifest.get("kind", "").startswith("in-process") or manifest.get("kind") == "Cloud Function"
    ex = _exec_facts(executions)
    rec: dict = {
        "contractVersion": JOBS_CONTRACT_VERSION, "syncedAt": iso(now), "syncedBy": synced_by,
        "jobId": job_id, "displayName": manifest.get("displayName", job_id), "owner": manifest.get("owner"),
        "purpose": manifest.get("purpose"), "environment": manifest.get("environment"), "classification": manifest.get("classification"),
        "kind": manifest.get("kind"), "trigger": trigger,
        "inputs": manifest.get("inputs"), "outputs": manifest.get("outputs"), "brainDependencies": manifest.get("brainDependencies"),
        "statePaths": manifest.get("statePaths"), "brainPublishInJob": manifest.get("brainPublishInJob"),
        "retryPolicy": manifest.get("retryPolicy"), "freshnessPolicy": manifest.get("freshnessPolicy"),
        "deploymentStatus": "DEPLOYED" if deployed else "NOT_DEPLOYED",
    }
    for k in ("scienceStatus", "sourceLineage", "triggeredBy", "triggers", "consumers"):
        if manifest.get(k) is not None:
            rec[k] = manifest[k]
    warnings: list[str] = []
    # ── schedule: Cloud Scheduler is authoritative ──
    sched_state = (scheduler or {}).get("state")
    cron = (scheduler or {}).get("schedule")
    tz = (scheduler or {}).get("timeZone")
    if trigger == "scheduler":
        if scheduler is None:
            rec.update({"executionMode": "MANUAL", "enabled": None, "schedule": None})
            if deployed:
                warnings.append("no Cloud Scheduler job of this name: the job only runs when started by hand")
        else:
            enabled = sched_state == "ENABLED"
            rec.update({"executionMode": "SCHEDULED" if enabled else "DISABLED", "enabled": enabled, "cron": cron, "timezone": tz,
                        "schedule": f"{cron} {tz}" if cron else None, "schedulerState": sched_state,
                        "nextScheduledAt": (scheduler or {}).get("scheduleTime") if enabled else None,
                        "lastScheduledAttemptAt": (scheduler or {}).get("lastAttemptTime")})
    elif trigger in ("orchestrator", "dispatcher"):
        rec.update({"executionMode": "EVENT_DRIVEN", "enabled": True, "schedule": f"on demand ({trigger}: {manifest.get('triggeredBy') or 'brain-orchestrator'})"})
        if scheduler is not None:
            rec["legacyScheduler"] = {"state": sched_state, "cron": cron, "timezone": tz}
            if sched_state == "ENABLED":
                warnings.append(f"legacy Cloud Scheduler job still ENABLED ({cron} {tz}) although the job is {trigger}-triggered")
    elif trigger == "request":
        rec.update({"executionMode": "EVENT_DRIVEN", "enabled": True, "schedule": "on request"})
    else:
        rec.update({"executionMode": "MANUAL", "enabled": None, "schedule": "manual"})
        if scheduler is not None and sched_state == "ENABLED":
            warnings.append(f"a Cloud Scheduler job exists and is ENABLED ({cron} {tz}) for a MANUAL job")
    # ── runtime: Cloud Run executions ──
    rec.update({k: ex.get(k) for k in ("running", "lastStartedAt", "lastCompletedAt", "lastSuccessfulAt", "lastFailedAt", "durationMs",
                                       "failureCount", "lastError", "lastErrorAt")})
    if brain_health and not executions:                   # in-process brains: the publish is the run
        rec.update({"lastStartedAt": brain_health.get("lastRun"), "lastCompletedAt": brain_health.get("lastRun"),
                    "lastSuccessfulAt": brain_health.get("lastSuccess"), "durationMs": brain_health.get("durationMs"),
                    "failureCount": brain_health.get("errorCount"), "lastError": brain_health.get("latestError"), "running": False})
        rec["runtimeStatus"] = brain_health.get("status") or "UNKNOWN"
    else:
        rec["runtimeStatus"] = _runtime_status(sched_state, ex, deployed, trigger)
    if service is not None:
        st = service.get("status") or {}
        live = [t for t in st.get("traffic") or [] if t.get("percent") == 100]
        rec["revision"] = live[0].get("revisionName") if live else st.get("latestReadyRevisionName")
        rec["runtimeStatus"] = "HEALTHY" if st.get("conditions") and all(c.get("status") == "True" for c in st["conditions"]) else "WARNING"
        rec["running"] = None
    if run_job is not None:
        labels = (run_job.get("metadata") or {}).get("labels") or {}
        if labels.get("commit"):
            rec["sourceVersion"] = labels["commit"]
        res = _res(run_job)
        if res:
            rec["resources"] = res
    # ── cost metadata (no dollars) ──
    runs = cron_runs_per_day(cron) if (trigger == "scheduler" and sched_state == "ENABLED") else None
    basis = "cron"
    if runs is None and manifest.get("expectedRunsPerDay") is not None and trigger in ("orchestrator", "dispatcher"):
        runs, basis = float(manifest["expectedRunsPerDay"]), "estimate (orchestrator-conditional)"
    if trigger == "scheduler" and sched_state == "PAUSED":
        runs, basis = 0.0, "paused"
    cost = {"expectedRunsPerDay": runs, "expectedRunsBasis": basis if runs is not None else None,
            "recentAverageRuntimeMs": ex.get("recentAverageRuntimeMs"), "recentRuns": ex.get("recentRuns"),
            "resourceProfile": rec.get("resources")}
    res = rec.get("resources") or {}
    if runs is not None and ex.get("recentAverageRuntimeMs") and res.get("cpu") and res.get("memoryGi"):
        hours = runs * ex["recentAverageRuntimeMs"] / 3_600_000 * (res.get("tasks") or 1)
        cost["estimatedVcpuHoursPerDay"] = round(hours * res["cpu"], 3)
        cost["estimatedGibHoursPerDay"] = round(hours * res["memoryGi"], 3)
    cost["note"] = "runs/day × average successful runtime × resources; task-parallel jobs multiply by tasks; not a dollar figure"
    rec["cost"] = {k: v for k, v in cost.items() if v is not None}
    if warnings:
        rec["warnings"] = warnings
    return {k: v for k, v in rec.items() if v is not None}


def build_records(*, scheduler_jobs: list[dict], run_jobs: list[dict], executions: dict[str, list[dict]], now: dt.datetime,
                  synced_by: str, brain_health: dict | None = None, services: dict[str, dict] | None = None,
                  manifest: dict | None = None) -> dict[str, dict]:
    """Every `/jobs/{jobId}` record: one per manifest entry, plus a minimal record for any deployed Cloud Run job or
    Scheduler job the manifest does not know (so Ops sees it instead of it being invisible)."""
    manifest = manifest or MANIFEST
    sched = {s["name"].rsplit("/", 1)[-1]: s for s in scheduler_jobs or []}
    runj = {(j.get("metadata") or {}).get("name") or j.get("name", "").rsplit("/", 1)[-1]: j for j in run_jobs or []}
    out = {}
    health = brain_health or {}
    for jid, m in manifest.items():
        bh = health.get(m.get("owner")) if m.get("kind", "").startswith("in-process") or jid == "water-clarity-brain" else None
        out[jid] = job_record(jid, m, sched.get(jid), runj.get(jid), (executions or {}).get(jid), now, synced_by,
                              brain_health=bh, service=(services or {}).get(jid))
    for jid in sorted(set(sched) | set(runj)):
        if jid in out:
            continue
        m = {"displayName": jid, "kind": "Cloud Run job" if jid in runj else "Cloud Scheduler job", "trigger": "scheduler" if jid in sched else "manual",
             "purpose": "not in the Engine job manifest (sector_brain_platform.jobs.MANIFEST) — classify it", "classification": None}
        out[jid] = job_record(jid, m, sched.get(jid), runj.get(jid), (executions or {}).get(jid), now, synced_by)
        out[jid]["warnings"] = (out[jid].get("warnings") or []) + ["unmanifested workload"]
    return out


def changed_paths(new: dict[str, dict], old: dict[str, dict] | None, ignore: tuple[str, ...] = ("syncedAt",)) -> dict[str, dict]:
    """Only the records whose content (minus volatile fields) differs from what is published."""
    old = old or {}
    def strip(r):
        return {k: v for k, v in (r or {}).items() if k not in ignore}
    return {f"jobs/{jid}": rec for jid, rec in new.items() if strip(rec) != strip(old.get(jid))}
