"""Orchestrator planning core: dependency order, dedupe, single-flight, conditional refresh, retries, failure isolation, targeting."""
import datetime as dt

import pytest

from sector_brain_platform import descriptor_gaps, orchestrate

NOW = dt.datetime(2026, 10, 12, 12, 0, tzinfo=dt.timezone.utc)
ISO = lambda h: (NOW - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731


def regs():
    return {
        "lake-brain": {"stalenessModel": "TIME", "staleAfterHours": 3, "lastSuccessfulRun": ISO(5), "schedule": {"cadence": "manual"}, "dependsOn": []},
        "water-temp": {"stalenessModel": "TIME", "staleAfterHours": 6, "lastSuccessfulRun": ISO(1), "schedule": {"cadence": "manual"}, "dependsOn": []},
        "water-clarity": {"stalenessModel": "TIME", "staleAfterHours": 26, "lastSuccessfulRun": ISO(2), "schedule": {}, "dependsOn": []},
        "wind": {"stalenessModel": "TIME", "staleAfterHours": 1.5, "lastSuccessfulRun": ISO(0.5), "schedule": {"cadence": "5 * * * *", "running": True}, "dependsOn": []},
        "biological-state": {"stalenessModel": "VERSION", "lastSuccessfulRun": ISO(400), "schedule": {"cadence": "manual"}, "dependsOn": []},
        "sector-intelligence": {"stalenessModel": "FINGERPRINT", "lastSuccessfulRun": ISO(1), "schedule": {"cadence": "manual"},
                                "dependsOn": ["lake-brain", "water-temp", "water-clarity", "wind", "biological-state"]},
    }


def test_plan_orders_runs_after_dependencies_and_only_runs_what_needs_it():
    p = orchestrate(regs(), {}, NOW, brain_plans={"sector-intelligence": {"action": "PUBLISH", "reasons": ["upstream changed"]},
                                                  "biological-state": {"action": "SKIP", "reasons": ["version unchanged"]}})
    assert p["order"][-1] == "sector-intelligence"
    ran = [r["brainId"] for r in p["runs"]]
    assert ran == ["lake-brain", "sector-intelligence"], ran            # lake stale (5 h > 3); intel's own plan says publish
    intel = p["runs"][1]
    assert intel["after"] == ["lake-brain"] and intel["priority"] == 2
    assert "brain plan: upstream changed" in intel["reasons"]
    assert [w["brainId"] for w in p["waiting"]] == ["wind"]              # single-flight: already running
    skipped = {s["brainId"]: s["reasons"] for s in p["skipped"]}
    assert "water-temp" in skipped and "biological-state" in skipped
    assert skipped["biological-state"] == ["brain plan: nothing to do"]   # VERSION brain never runs by age


def test_version_brain_runs_only_on_its_own_verdict_and_never_run_is_run():
    r = regs(); r["biological-state"].pop("lastSuccessfulRun")
    p = orchestrate(r, {}, NOW)
    assert "biological-state" not in [x["brainId"] for x in p["runs"]]
    r["water-temp"].pop("lastSuccessfulRun")
    p = orchestrate(r, {}, NOW)
    wt = next(x for x in p["runs"] if x["brainId"] == "water-temp")
    assert wt["reasons"] == ["never run"]


def test_retry_backoff_and_exhaustion():
    r = regs()
    h = {"lake-brain": {"status": "FAILED", "errorCount": 1, "lastRun": ISO(0.02)}}
    p = orchestrate(r, h, NOW)
    w = next(x for x in p["waiting"] if x["brainId"] == "lake-brain")
    assert "retry backoff: 5 min" in w["reasons"][0] and w["nextAttemptAt"]
    h["lake-brain"]["lastRun"] = ISO(1)
    p = orchestrate(r, h, NOW)
    run = next(x for x in p["runs"] if x["brainId"] == "lake-brain")
    assert run["reasons"][0] == "retry after failure #1"
    h["lake-brain"]["errorCount"] = 4
    p = orchestrate(r, h, NOW)
    s = next(x for x in p["skipped"] if x["brainId"] == "lake-brain")
    assert "retries exhausted" in s["reasons"][0]


def test_failure_isolation_runs_downstream_flagged_not_blocked():
    r = regs()
    h = {"lake-brain": {"status": "FAILED", "errorCount": 5}}
    p = orchestrate(r, h, NOW, brain_plans={"sector-intelligence": {"action": "PUBLISH", "reasons": ["upstream changed"]}})
    intel = next(x for x in p["runs"] if x["brainId"] == "sector-intelligence")
    assert intel["degradedUpstream"] == ["lake-brain"] and intel["after"] == []
    assert any("degraded inputs: lake-brain" in x for x in intel["reasons"])


def test_lock_dedupe_targets_and_cycles():
    r = regs(); r["water-temp"]["schedule"] = {"lockedUntil": (NOW + dt.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    r["water-temp"]["lastSuccessfulRun"] = ISO(100)
    p = orchestrate(r, {}, NOW, targets=["Guntersville|AL"])
    assert next(x for x in p["waiting"] if x["brainId"] == "water-temp")["reasons"][0].startswith("locked until")
    assert all(x["lakes"] == ["Guntersville|AL"] for x in p["runs"]) and p["targets"] == ["Guntersville|AL"]
    assert len({x["brainId"] for x in p["runs"]}) == len(p["runs"])
    r["lake-brain"]["dependsOn"] = ["sector-intelligence"]
    with pytest.raises(ValueError):
        orchestrate(r, {}, NOW)


def test_descriptor_gaps_name_what_is_missing():
    gaps = descriptor_gaps({"wind": {"staleAfterHours": 1.5, "lastSuccessfulRun": ISO(1)},
                            "biological-state": {"stalenessModel": "VERSION", "schedule": {}, "dependsOn": [], "lastSuccessfulRun": ISO(1), "orchestration": {"components": {}}}})
    assert gaps == {"wind": ["schedule", "stalenessModel", "dependsOn", "descriptor"]}
