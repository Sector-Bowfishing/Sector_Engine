"""brain-health-v1 glue in the orchestrator: observations by dependency TYPE, cadence from the schedule (never from staleAfterHours), the
control/healthV1 node built from the published world, code-version lineage, and the opt-in publication flags. Nothing starts, no network."""
import datetime as dt
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import control_plane as CP        # noqa: E402
import orchestrate as OR          # noqa: E402
from sector_brain_platform import orchestration as O, control_state as CS, brain_health as BH, dependency_declarations as DD   # noqa: E402
from test_control_plane import FakeDb, tree, ago, NOW   # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def rows_for(bid):
    reg = DD.load_registered_brains(ROOT)
    if bid in reg:
        return DD.declared_dependencies(reg[bid])
    return DD.legacy_rows_from_execution_manifest(O.load_manifest(), reg)[bid]


def test_expected_cadence_comes_from_an_enabled_scheduler_cron_not_from_freshness():
    m = O.load_manifest()
    enabled = {b: 0 for b in m["brains"]}
    for bid, b in m["brains"].items():
        sch = b.get("schedule") or {}
        if sch.get("class") == "VALIDATION_EXCEPTION" and sch.get("cron"):
            assert CP.expected_interval_hours(b, {}, {sch["scheduler"]: "ENABLED"}) == pytest.approx(24 / __import__("sector_brain_platform").jobs.cron_runs_per_day(sch["cron"]))
            assert CP.expected_interval_hours(b, {}, {sch["scheduler"]: "PAUSED"}) is None           # paused scheduler: no cadence expectation
            assert CP.expected_interval_hours(b, {}, None) is None                                  # unknown scheduler state: unknown, not assumed
            enabled[bid] = 1
        elif sch.get("class") in ("MANUAL", "INPUT_DRIVEN", "PAUSED"):
            assert CP.expected_interval_hours(b, {}, {}) is None
    assert sum(enabled.values()) >= 1
    b = {"schedule": {"class": "MANUAL"}, "freshness": {"staleAfterHours": 1.5}}
    assert CP.expected_interval_hours(b, {}, {}) is None                                            # staleAfterHours is an evidence rule, never a cadence


def test_observations_are_built_by_dependency_type_and_carry_no_invented_freshness():
    rows = [{"dependencyId": "brain:x", "dependencyType": "BRAIN", "target": "x", "declaringBrain": "c"},
            {"dependencyId": "brain:y", "dependencyType": "BRAIN", "target": "y", "declaringBrain": "c"},
            {"dependencyId": "provider:p", "dependencyType": "PROVIDER_DATA", "target": "p", "declaringBrain": "c"},
            {"dependencyId": "provider:q", "dependencyType": "PROVIDER_DATA", "target": "q", "declaringBrain": "c"},
            {"dependencyId": "signal:pressure-trend", "dependencyType": "ENVIRONMENTAL_SIGNAL", "target": "pressure-trend", "declaringBrain": "c"},
            {"dependencyId": "signal:nope", "dependencyType": "ENVIRONMENTAL_SIGNAL", "target": "nope", "declaringBrain": "c"},
            {"dependencyId": "registry:lakes", "dependencyType": "PLATFORM_REGISTRY", "target": "lakes", "declaringBrain": "c"}]
    regs = {"x": {"lastSuccessfulRun": ago(1), "staleAfterHours": 3, "version": "7", "freshness": {"sourceObservationAt": ago(2), "stale": False}}}
    sources = {"p": {"latestObservationAt": ago(0.5), "staleThresholdHours": 2, "health": "HEALTHY"}}
    from sector_brain_platform import signals as SG
    obs = CP.observe_dependencies(rows, regs, sources, {"p": {"status": "HEALTHY"}}, SG.load())
    assert obs["brain:x"]["evidenceObservedAt"] == ago(2) and obs["brain:x"]["stale"] is False and obs["brain:x"]["stateVersion"] == "7" and obs["brain:x"]["lastSuccessfulRun"] == ago(1)
    assert obs["brain:y"] is None
    assert obs["provider:p"]["evidenceObservedAt"] == ago(0.5) and obs["provider:p"]["staleAfterHours"] == 2 and "HEALTHY" in obs["provider:p"]["reason"]
    assert obs["provider:q"] is None
    assert obs["signal:pressure-trend"]["available"] is False and "DECLARED only" in obs["signal:pressure-trend"]["reason"]
    assert obs["signal:nope"]["available"] is False
    assert obs["registry:lakes"]["available"] is None
    only_run = CP.observe_dependencies(rows[:1], {"x": {"lastSuccessfulRun": ago(1), "staleAfterHours": 3}}, {}, {}, None)["brain:x"]
    assert "evidenceObservedAt" not in only_run and "freshnessStatus" not in only_run                  # nothing invented from lastSuccessfulRun


def test_health_state_from_the_published_world(monkeypatch):
    t = tree()
    t["sources"] = {}
    db = FakeDb(t)
    world = CP.load_world(db, NOW)
    ctx, ev = CP.evaluate(world, NOW, {})
    exec_rec = O.execution_record("wind-hourly-abc", "wind", "SCHEDULE", "legacy scheduler fire", NOW - dt.timedelta(minutes=10), NOW - dt.timedelta(minutes=7),
                                  "SUCCEEDED", source="cloud-run", code_version="c0ffee", job_id="wind-hourly")
    cs = CS.build_control_state(world["manifest"], "PRE_PRODUCTION", NOW, registries=world["registries"], health=world["health"], scores={}, jobs={}, evaluation=ev,
                                new_executions=[exec_rec])
    jobs = {"wind-hourly": {"schedulerState": "ENABLED", "cron": "5 * * * *"}}
    st = CP.build_health_state(world, cs, jobs, NOW, scheduler_states={"wind-hourly": "ENABLED"}, sources=db.get("sources"), source_health={})
    assert set(st) == set(BH.SECTIONS) and st["summary"]["engineMode"] == "PRE_PRODUCTION"
    w = st["brains"]["wind"]
    assert w["process"]["processHealth"] == "HEALTHY" and w["process"]["codeVersions"] == ["c0ffee"] and w["process"]["cadence"]["status"] == "ON_CADENCE"
    assert w["process"]["cadence"]["expectedIntervalHours"] == 1.0
    assert w["dependencies"]["dependencyHealth"] in ("UNKNOWN", "UNSATISFIED")                           # Wind's providers publish no /sources in this world
    assert w["freshness"]["status"] in ("UNKNOWN", "UNAVAILABLE") and w["aggregate"]["status"] in ("FAILED", "UNKNOWN")
    assert w["dependencies"]["declaredVsActual"]["consumptionRecorded"] is False                       # the gap is stated, not papered over
    assert "domainValidation" in w and w["domainValidation"]["status"] == "UNKNOWN"
    bio = st["brains"]["biological-state"]
    assert bio["process"]["processHealth"] == "UNKNOWN" and bio["aggregate"]["status"] == "UNKNOWN"
    # Fish is a REGISTERED Brain (brains/fish/brain.json) that consumes no other Brain: zero declared rows, nothing legacy, freshness stays UNKNOWN
    assert bio["dependencies"]["declared"] == 0 and "rows" not in bio["dependencies"] and bio["dependencies"]["freshnessHealth"] == "UNKNOWN"
    assert st["dependencies"]["brains"]["biological-state"]["source"] == "brain.json" and not st["dependencies"]["brains"]["biological-state"].get("rows")
    assert st["dependencies"]["brains"]["sector-intelligence"].get("legacy") is True                          # a not-yet-migrated Brain is still legacy, labelled
    assert st["brains"]["depth"]["process"]["processHealth"] == "NOT_CONFIGURED"                       # executionTarget kind none
    assert st["dependencies"]["edges"] and all("signalId" in s for s in st["signals"].values())
    assert "wind" in st["dependencies"]["brains"] and st["dependencies"]["brains"]["wind"]["source"] == "brain.json"
    assert json.dumps(st, sort_keys=True) == json.dumps(CP.build_health_state(world, cs, jobs, NOW, scheduler_states={"wind-hourly": "ENABLED"}, sources={}, source_health={}), sort_keys=True)


def test_cloud_run_executions_carry_the_job_commit_label_as_code_version():
    m = O.load_manifest()
    execs = {"wind-hourly": [{"metadata": {"name": "wind-hourly-xyz"}, "status": {"startTime": ago(0.5), "completionTime": ago(0.45), "succeededCount": 1}}]}
    recs = CP.executions_from_cloud_run(m, execs, {"wind-hourly": {"cron": "5 * * * *", "timezone": "UTC", "sourceVersion": "abc123"}}, NOW)
    assert recs[0]["codeVersion"] == "abc123" and recs[0]["jobId"] == "wind-hourly" and recs[0]["status"] == "SUCCEEDED"
    recs2 = CP.executions_from_cloud_run(m, execs, {"wind-hourly": {"cron": "5 * * * *", "timezone": "UTC"}}, NOW)
    assert "codeVersion" not in recs2[0]                                                               # unknown stays absent


@pytest.fixture
def cycle(monkeypatch):
    calls = {"start": [], "inproc": []}

    def setup(t):
        db = FakeDb(t)
        monkeypatch.setattr(OR, "BrainRtdb", lambda *a, **k: db)
        monkeypatch.setattr(OR, "TokenProvider", lambda *a, **k: object())
        monkeypatch.setattr(OR, "check_schema", lambda d: None)
        monkeypatch.setattr(OR, "sync_jobs", lambda *a, **k: ({}, {}, 0))
        monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: {"action": "SKIP", "reasons": ["nothing to do"]})
        monkeypatch.setattr(OR, "start_job", lambda b, tokens: calls["start"].append(b))
        monkeypatch.setattr(OR, "run_in_process", lambda b, timeout=1800: calls["inproc"].append(b))
        monkeypatch.setattr(OR.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})())
        monkeypatch.setattr(CP, "scheduler_states", lambda tokens: {})
        return db
    return setup, calls


def test_health_plane_is_off_by_default_and_opt_in(cycle, tmp_path):
    setup, calls = cycle
    db = setup(tree())
    assert OR.main([]) == 0
    assert "healthV1" not in db.tree.get("control", {}) and "sources" not in db.tree                 # default cycle: no health reads, no health writes
    out = tmp_path / "health.json"
    assert OR.main(["--emit-health-state", str(out)]) == 0
    st = json.load(open(out))
    assert set(st) == set(BH.SECTIONS) and "healthV1" not in db.tree["control"]                    # emitted for review, still not published
    assert OR.main(["--publish-health"]) == 0
    hv = db.tree["control"]["healthV1"]
    assert set(hv) == set(BH.SECTIONS) and hv["summary"]["version"] == "brain-health-v1"
    assert calls["start"] == [] and calls["inproc"] == []                                           # the health plane never starts anything
    db.writes.clear()
    OR.main(["--publish-health"])
    assert [w for w in db.writes for p in w if p.startswith("control/healthV1")] == []              # content-aware: unchanged -> not rewritten


def test_health_plane_failure_never_breaks_the_cycle(cycle, monkeypatch):
    setup, calls = cycle
    db = setup(tree())
    monkeypatch.setattr(CP, "build_health_state", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert OR.main(["--publish-health"]) == 0 and "orchestrator" in db.tree["control"]


def test_health_only_writes_exactly_the_health_node_and_nothing_else(cycle, monkeypatch, tmp_path):
    """health-plane-publication-v1: the one controlled live publication must be provable as ONE atomic PATCH of control/healthV1/* — no /jobs, no
    execution, no scores, no control/orchestratorV1, no legacy record, no Brain --plan subprocess."""
    setup, calls = cycle
    db = setup(tree())
    plans = []
    monkeypatch.setattr(OR, "brain_plan", lambda b, timeout=600: plans.append(b) or {"action": "SKIP", "reasons": ["x"]})
    out = tmp_path / "h.json"
    assert OR.main(["--dry-run", "--health-only", "--emit-health-state", str(out)]) == 0
    assert db.writes == [] and "healthV1" not in db.tree.get("control", {}) and set(json.load(open(out))) == set(BH.SECTIONS)   # dry run: nothing written
    assert OR.main(["--health-only"]) == 0
    assert len(db.writes) == 1, db.writes                                                             # exactly one multi-location update ...
    assert set(db.writes[0]) == {f"control/healthV1/{s}" for s in BH.SECTIONS}                         # ... and it touches only the health node
    assert "orchestratorV1" not in db.tree["control"] and "orchestrator" not in db.tree["control"] and "jobs" not in db.tree.get("control", {})
    assert calls["start"] == [] and calls["inproc"] == [] and plans == []                                # nothing started, no plan asked
    hv = db.tree["control"]["healthV1"]
    assert hv["summary"]["contentFingerprint"] and hv["summary"]["source"]["controlState"] == CS.NODE
    db.writes.clear()
    assert OR.main(["--health-only"]) == 0
    assert db.writes == []                                                                            # unchanged world: no write at all
