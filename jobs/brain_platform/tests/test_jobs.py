"""The /jobs contract: Cloud Scheduler is authoritative for enabled/cron/nextScheduledAt; executions give runtime facts;
the manifest gives design facts; nothing secret is published; only the platform writer may write it."""
import datetime as dt

import pytest

from sector_brain_platform import (JOB_MANIFEST, OwnershipError, assert_owned, build_records, cron_runs_per_day, job_record,
                                   jobs_changed_paths, path_allowed)
from sector_brain_platform.jobs import CLASSIFICATIONS, EXECUTION_MODES, RUNTIME_STATUSES, TRIGGERS

NOW = dt.datetime(2026, 10, 13, 5, 0, tzinfo=dt.timezone.utc)
SCHED = {"name": "projects/p/locations/us-central1/jobs/wind-hourly", "schedule": "5 * * * *", "timeZone": "UTC", "state": "ENABLED",
         "scheduleTime": "2026-10-13T05:05:01Z", "lastAttemptTime": "2026-10-13T04:05:03Z",
         "httpTarget": {"oauthToken": {"serviceAccountEmail": "wind-hourly-job@p.iam.gserviceaccount.com"}, "uri": "https://run.googleapis.com/..."}}
RUNJOB = {"metadata": {"name": "wind-hourly", "labels": {"commit": "abc123"}},
          "spec": {"template": {"spec": {"taskCount": 1, "template": {"spec": {"timeoutSeconds": 900, "serviceAccountName": "wind-hourly-job@p",
                   "containers": [{"image": "us-central1-docker.pkg.dev/p/r/wind@sha256:1", "resources": {"limits": {"cpu": "1", "memory": "2Gi"}},
                                   "env": [{"name": "SECRET_THING", "value": "hunter2"}]}]}}}}}}
EXECS = [{"metadata": {"name": "wind-hourly-a", "creationTimestamp": "2026-10-13T04:05:03Z"},
          "status": {"startTime": "2026-10-13T04:05:15Z", "completionTime": "2026-10-13T04:08:22Z", "succeededCount": 1}},
         {"metadata": {"name": "wind-hourly-b", "creationTimestamp": "2026-10-13T03:05:03Z"},
          "status": {"startTime": "2026-10-13T03:05:30Z", "completionTime": "2026-10-13T03:09:37Z", "succeededCount": 1}},
         {"metadata": {"name": "wind-hourly-c", "creationTimestamp": "2026-10-13T02:05:03Z"},
          "status": {"startTime": "2026-10-13T02:05:30Z", "completionTime": "2026-10-13T02:07:00Z", "failedCount": 1,
                     "conditions": [{"type": "Completed", "status": "False", "message": "task failed: exit 1"}]}}]


def test_manifest_vocabularies_and_coverage():
    for jid, m in JOB_MANIFEST.items():
        assert m["classification"] in CLASSIFICATIONS, jid
        assert m["trigger"] in TRIGGERS, jid
        assert m.get("purpose"), jid
    for jid in ("sector-engine", "wind-hourly", "water-temp-tva-archive", "hydrology-hourly", "clarity-current-hourly", "lake-surface-daily",
                "lake-surface-dispatch", "clarity-candidate-shadow", "lake-brain", "water-temp-brain", "water-clarity-brain",
                "biological-brain", "sector-intelligence-brain", "brain-orchestrator", "wind-candidate-read"):
        assert jid in JOB_MANIFEST
    assert JOB_MANIFEST["sector-engine"]["classification"] == "PRODUCTION"
    assert JOB_MANIFEST["clarity-candidate-shadow"]["classification"] == "SHADOW"
    assert JOB_MANIFEST["hydrology-hourly"]["classification"] == JOB_MANIFEST["clarity-current-hourly"]["classification"] == "RESEARCH"
    assert JOB_MANIFEST["wind-hourly"]["classification"] == "INTERNAL" and "RESEARCH_CANDIDATE" in JOB_MANIFEST["wind-hourly"]["scienceStatus"]
    assert JOB_MANIFEST["water-clarity-brain"]["trigger"] == "manual"
    for jid in ("biological-brain", "sector-intelligence-brain", "lake-brain", "water-temp-brain"):
        assert JOB_MANIFEST[jid]["trigger"] == "orchestrator"


def test_scheduler_is_authoritative_and_runtime_from_executions():
    r = job_record("wind-hourly", JOB_MANIFEST["wind-hourly"], SCHED, RUNJOB, EXECS, NOW, "test")
    assert r["executionMode"] == "SCHEDULED" and r["enabled"] is True and r["cron"] == "5 * * * *" and r["timezone"] == "UTC"
    assert r["nextScheduledAt"] == "2026-10-13T05:05:01Z" and r["schedule"] == "5 * * * * UTC"
    assert r["runtimeStatus"] == "HEALTHY" and r["running"] is False
    assert r["lastStartedAt"] == "2026-10-13T04:05:15Z" and r["lastSuccessfulAt"] == "2026-10-13T04:08:22Z"
    assert r["lastFailedAt"] == "2026-10-13T02:07:00Z" and r["failureCount"] == 1 and r["lastError"] == "task failed: exit 1"
    assert r["durationMs"] == 187_000
    assert r["resources"] == {"cpu": 1.0, "memoryGi": 2.0, "tasks": 1, "parallelism": 1, "taskTimeoutS": 900}
    assert r["cost"]["expectedRunsPerDay"] == 24 and r["cost"]["expectedRunsBasis"] == "cron"
    assert r["cost"]["recentAverageRuntimeMs"] == (187_000 + 247_000) // 2
    assert r["cost"]["estimatedVcpuHoursPerDay"] == pytest.approx(24 * 217 / 3600, abs=0.01)
    assert "estimatedDollars" not in str(r) and "$" not in str(r["cost"])
    assert r["sourceVersion"] == "abc123" and r["contractVersion"] == "jobs-v1" and r["deploymentStatus"] == "DEPLOYED"


def test_nothing_secret_is_published():
    r = job_record("wind-hourly", JOB_MANIFEST["wind-hourly"], SCHED, RUNJOB, EXECS, NOW, "test")
    blob = str(r)
    for forbidden in ("hunter2", "SECRET_THING", "gserviceaccount", "sha256", "docker.pkg.dev", "gs://"):
        assert forbidden not in blob, forbidden
    for m in JOB_MANIFEST.values():
        assert "gs://" not in str(m) and "gserviceaccount" not in str(m)


def test_paused_scheduler_shows_as_disabled_and_paused():
    s = dict(SCHED, state="PAUSED", scheduleTime=None)
    r = job_record("hydrology-hourly", JOB_MANIFEST["hydrology-hourly"], s, RUNJOB, EXECS[:2], NOW, "test")
    assert r["executionMode"] == "DISABLED" and r["enabled"] is False and r["runtimeStatus"] == "PAUSED"
    assert "nextScheduledAt" not in r and r["cost"]["expectedRunsPerDay"] == 0 and r["cost"]["expectedRunsBasis"] == "paused"
    assert r["cron"] == "5 * * * *"                       # the schedule is still shown; it is just not enabled


def test_running_execution_and_not_deployed():
    running = [{"metadata": {"name": "x", "creationTimestamp": "2026-10-13T04:59:00Z"}, "status": {"startTime": "2026-10-13T04:59:10Z"}}]
    r = job_record("wind-hourly", JOB_MANIFEST["wind-hourly"], SCHED, RUNJOB, running, NOW, "test")
    assert r["running"] is True and r["runtimeStatus"] == "RUNNING"
    nd = job_record("water-clarity-brain", JOB_MANIFEST["water-clarity-brain"], None, None, None, NOW, "test",
                    brain_health={"status": "HEALTHY", "lastRun": "2026-10-12T06:52:07Z", "lastSuccess": "2026-10-12T06:52:07Z", "errorCount": 0})
    assert nd["deploymentStatus"] == "NOT_DEPLOYED" and nd["executionMode"] == "MANUAL" and nd["runtimeStatus"] == "HEALTHY"
    assert nd["lastSuccessfulAt"] == "2026-10-12T06:52:07Z"


def test_dispatcher_and_orchestrator_triggered_jobs_flag_a_live_legacy_cron():
    legacy = dict(SCHED, name=".../lake-surface-daily", schedule="0 3 * * *", timeZone="America/Chicago")
    r = job_record("lake-surface-daily", JOB_MANIFEST["lake-surface-daily"], legacy, RUNJOB, None, NOW, "test")
    assert r["executionMode"] == "EVENT_DRIVEN" and r["triggeredBy"] == "lake-surface-dispatch"
    assert r["legacyScheduler"]["state"] == "ENABLED" and any("still ENABLED" in w for w in r["warnings"])
    paused = job_record("lake-surface-daily", JOB_MANIFEST["lake-surface-daily"], dict(legacy, state="PAUSED"), RUNJOB, None, NOW, "test")
    assert "warnings" not in paused and paused["legacyScheduler"]["state"] == "PAUSED"
    lb = job_record("lake-brain", JOB_MANIFEST["lake-brain"], None, RUNJOB, EXECS[:1], NOW, "test")
    assert lb["executionMode"] == "EVENT_DRIVEN" and lb["cost"]["expectedRunsBasis"].startswith("estimate")


def test_build_records_covers_manifest_and_unmanifested_cloud_jobs():
    extra = {"metadata": {"name": "mystery-job"}, "spec": {"template": {"spec": {"taskCount": 1, "template": {"spec": {"containers": [{}]}}}}}}
    recs = build_records(scheduler_jobs=[SCHED], run_jobs=[RUNJOB, extra], executions={"wind-hourly": EXECS}, now=NOW, synced_by="test",
                         brain_health={"biological-state": {"status": "HEALTHY", "lastRun": "2026-10-13T03:56:36Z", "lastSuccess": "2026-10-13T03:56:36Z"}})
    assert set(JOB_MANIFEST) <= set(recs) and "mystery-job" in recs
    assert "unmanifested workload" in recs["mystery-job"]["warnings"]
    assert recs["biological-brain"]["lastSuccessfulAt"] == "2026-10-13T03:56:36Z" and recs["biological-brain"]["executionMode"] == "EVENT_DRIVEN"
    for r in recs.values():
        assert r["runtimeStatus"] in RUNTIME_STATUSES and r["executionMode"] in EXECUTION_MODES
    # a scheduler-triggered deployed job with no scheduler gets a warning
    recs2 = build_records(scheduler_jobs=[], run_jobs=[RUNJOB], executions={}, now=NOW, synced_by="test")
    assert any("no Cloud Scheduler job" in w for w in recs2["wind-hourly"]["warnings"])


def test_changed_paths_ignores_synced_at():
    a = {"wind-hourly": {"syncedAt": "t1", "enabled": True}, "x": {"syncedAt": "t1", "enabled": False}}
    b = {"wind-hourly": {"syncedAt": "t0", "enabled": True}, "x": {"syncedAt": "t0", "enabled": True}}
    assert list(jobs_changed_paths(a, b)) == ["jobs/x"]
    assert set(jobs_changed_paths(a, None)) == {"jobs/wind-hourly", "jobs/x"}


def test_cron_runs_per_day():
    assert cron_runs_per_day("5 * * * *") == 24 and cron_runs_per_day("0 3 * * *") == 1
    assert cron_runs_per_day("25 */3 * * *") == 8 and cron_runs_per_day("*/15 * * * *") == 96
    assert cron_runs_per_day("0 7 * * 1") is None and cron_runs_per_day(None) is None


def test_only_the_platform_writer_writes_jobs():
    assert path_allowed("brain-platform", "jobs/wind-hourly") and not path_allowed("wind", "jobs/wind-hourly")
    assert path_allowed("wind", "health/jobs/wind-hourly")
    with pytest.raises(OwnershipError):
        assert_owned({"jobs/lake-surface-daily": {}}, "water-clarity")


def test_every_control_manifest_job_has_an_owned_manifest_record():
    """Firebase remediation 2026-10-21 (audit E-9 / C-9): production /jobs/lake-brain-ledger-daily had no owner because the hand-made scheduler was
    missing from MANIFEST and was published as an unmanifested workload. Every job the control manifest knows must have a MANIFEST entry whose
    owner is the job's Brain (the platform for Brain-less jobs); /jobs stays written only by the platform."""
    import json, os
    import sector_brain_platform as P
    cm = json.load(open(os.path.join(os.path.dirname(P.__file__), "control_manifest.json"), encoding="utf-8"))["jobs"]
    for jid, j in cm.items():
        assert jid in JOB_MANIFEST, f"{jid}: in control_manifest.json but not in jobs.MANIFEST"
        assert JOB_MANIFEST[jid]["owner"] == (j.get("brainId") or "brain-platform"), jid


def test_the_ledger_scheduler_is_an_owned_scheduled_record_not_an_unmanifested_workload():
    sched = {"name": "projects/p/locations/us-central1/jobs/lake-brain-ledger-daily", "schedule": "0 12 * * *", "timeZone": "UTC", "state": "ENABLED",
             "scheduleTime": "2026-10-13T12:00:00Z"}
    r = build_records(scheduler_jobs=[sched], run_jobs=[], executions={}, now=NOW, synced_by="test")["lake-brain-ledger-daily"]
    assert r["owner"] == "lake-brain" and r["triggers"] == ["lake-brain"] and r["deploymentStatus"] == "DEPLOYED"
    assert r["executionMode"] == "SCHEDULED" and "unmanifested workload" not in (r.get("warnings") or [])
    gone = build_records(scheduler_jobs=[], run_jobs=[], executions={}, now=NOW, synced_by="test")["lake-brain-ledger-daily"]
    assert gone["deploymentStatus"] == "NOT_DEPLOYED"                     # no scheduler, nothing deployed
    assert not path_allowed("lake-brain", "jobs/lake-brain-ledger-daily")  # the owner field never grants write authority
