"""consumption-lineage-v1: ACTUAL reads recorded at the platform store, ownership-derived identity, deterministic merge, validation,
immutability of recorded lineage, and the end-to-end declared-vs-actual evaluation at consumption time (historical truth)."""
import copy
import datetime as dt
import json
import random

import pytest

from sector_brain_platform import ConsumptionRecorder, DryRunStore, consumption as CN, control_state as CS, dependency_health as DH, execution_health as EH, orchestration as O
from sector_brain_platform import brain_health as BH

NOW = dt.datetime(2026, 10, 16, 18, 20, tzinfo=dt.timezone.utc)
T = lambda h: (NOW - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")   # noqa: E731


def tree():
    return {"brains": {"alpha-upstream": {"version": "3", "lastSuccessfulRun": T(0.3), "freshness": {"generatedAt": T(0.4), "sourceObservationAt": T(0.6), "freshUntil": T(-2), "stale": False}},
                       "gamma": {"version": "g1"}, "me": {"version": "self"}},
            "health": {"brains": {"alpha-upstream": {"status": "HEALTHY"}}, "jobs": {"x": {"status": "HEALTHY"}}},
            "validation": {"alpha-upstream": {"status": "NOT_VALIDATED"}},
            "species": {"gar": {"name": "gar"}},
            "lakeFleet": {"G": {"slots": {"wind": {"s": 1}, "lake": {"s": 2}}, "modelVersions": {"wind": "w2"}}},
            "snapshots": {"G": {"latest": {"wind": {"provenance": {"generatedAt": T(0.5), "brainVersion": "wb"}, "freshness": {"stale": True}}, "lakeState": {"x": 1}, "brainVersions": {"wind": "w9"}}}},
            "lakes": {"G": {"speciesPresence": {"gar": True}, "states": {"waterTemp": {"freshness": {"generatedAt": T(6), "evidenceStale": True}}}}},
            "sources": {"noaa-nbm-v5": {"latestIssuedAt": T(1.3), "staleThresholdHours": 3}},
            "jobs": {"x": 1}, "control": {"y": 1}, "scores": {"z": 1}, "mystery": {"q": 1}}


def rec_and_store(brain="sector-intelligence"):
    r = ConsumptionRecorder(brain, clock=lambda: NOW)
    return r, DryRunStore(tree(), brain, recorder=r)


def test_contract_keys_are_the_single_merged_contract():
    assert CN.CONSUMED_KEYS == EH.CONSUMED_KEYS
    assert set(CN.PREFIX_TYPE.values()) == {"BRAIN", "ENVIRONMENTAL_SIGNAL", "PROVIDER_DATA", "PLATFORM_REGISTRY"}


def test_only_actual_reads_become_consumption_and_own_state_never_does():
    r, db = rec_and_store()
    db.get("brains/alpha-upstream"); db.get("brains/sector-intelligence"); db.get("brains/does-not-exist"); db.get("jobs"); db.get("control/y"); db.get("scores")
    ids = [e["dependencyId"] for e in db.consumed()]
    assert ids == ["brain:alpha-upstream"]                                     # read once, own node and absent node and platform nodes: no entry
    assert r.read_count == 6 and r.unclassified == []
    e = db.consumed()[0]
    assert e == {"dependencyId": "brain:alpha-upstream", "dependencyType": "BRAIN", "ref": "/brains/alpha-upstream", "stateVersion": "3", "generatedAt": T(0.4),
                 "evidenceObservedAt": T(0.6), "consumedAt": T(0), "freshnessStatus": "FRESH", "staleAfter": T(-2)}
    assert "lastSuccessfulRun" not in json.dumps(e)                            # process history never enters lineage
    empty = ConsumptionRecorder("x", clock=lambda: NOW)
    assert empty.entries() == [] and DryRunStore({}, "x").consumed() is None   # no recorder -> None (absence), recorder with no reads -> []


def test_identity_is_derived_from_the_ownership_contract_for_every_path_family():
    r, db = rec_and_store()
    for p in ("health/brains/alpha-upstream", "validation/alpha-upstream/status", "species", "lakeFleet/G", "snapshots/G/latest", "lakes/G/speciesPresence",
              "lakes/G/states/waterTemp", "sources/noaa-nbm-v5", "health/jobs/x", "mystery"):
        db.get(p)
    by = {e["dependencyId"]: e for e in db.consumed()}
    assert set(by) == {"brain:alpha-upstream", "brain:biological-state", "brain:wind", "brain:lake-brain", "brain:water-temp", "provider:noaa-nbm-v5"}
    assert by["brain:biological-state"]["ref"] == "/species"                   # the ownership contract says who owns /species; no table here
    assert by["brain:water-temp"]["freshnessStatus"] == "STALE" and by["brain:water-temp"]["generatedAt"] == T(6)
    assert by["brain:wind"]["freshnessStatus"] == "STALE" and by["brain:wind"]["stateVersion"] in ("w2", "wb", "w9")   # snapshot evidence stale; one deterministic version
    assert by["provider:noaa-nbm-v5"]["generatedAt"] == T(1.3) and by["provider:noaa-nbm-v5"]["staleAfter"] == T(1.3 - 3)   # the owner's own threshold applied
    assert r.unclassified == ["/mystery"]                                      # unknown root: reported, not guessed
    assert "health/jobs" not in json.dumps(db.consumed())
    # a Brain reading its own provider source is not consuming a dependency
    rw, dbw = rec_and_store("wind")
    dbw.get("sources/noaa-nbm-v5"); dbw.get("lakes/G/states/wind")
    assert dbw.consumed() == []
    shallow_r, shallow_db = rec_and_store()
    shallow_db.get("species", shallow=True)
    assert shallow_db.consumed()[0]["dependencyId"] == "brain:biological-state"


def test_merge_is_deterministic_and_read_order_independent():
    r, db = rec_and_store()
    paths = ["brains/alpha-upstream", "health/brains/alpha-upstream", "validation/alpha-upstream/status", "snapshots/G/latest", "lakeFleet/G", "lakes/G/states/waterTemp", "species"]
    for p in paths:
        db.get(p)
    base = db.consumed()
    for seed in range(5):
        rr = ConsumptionRecorder("sector-intelligence", clock=lambda: NOW)
        dd = DryRunStore(tree(), "sector-intelligence", recorder=rr)
        order = list(paths); random.Random(seed).shuffle(order)
        for p in order:
            dd.get(p)
        assert dd.consumed() == base
        shuffled = list(rr.reads); random.Random(seed + 7).shuffle(shuffled)
        assert CN.merge_reads(shuffled) == base
    assert [e["dependencyId"] for e in base] == sorted(e["dependencyId"] for e in base)
    assert json.dumps(base, sort_keys=True) == json.dumps(CN.finalize(copy.deepcopy(base)), sort_keys=True)
    # newest evidence / earliest staleAfter / worst freshness across reads of the same dependency
    m = CN.merge_reads([("brain:b", {"ref": "/b", "evidenceObservedAt": T(2), "staleAfter": T(-1), "freshnessStatus": "FRESH", "stateVersion": "1"}),
                        ("brain:b", {"ref": "/a", "evidenceObservedAt": T(1), "staleAfter": T(-3), "freshnessStatus": "STALE", "stateVersion": "2"})])
    assert m == [{"dependencyId": "brain:b", "dependencyType": "BRAIN", "ref": "/a", "evidenceObservedAt": T(1), "staleAfter": T(-1), "freshnessStatus": "STALE", "stateVersion": "2"}]   # newest evidence, EARLIEST staleAfter


@pytest.mark.parametrize("bad,needle", [
    ("nope", "must be a list"), ([1], "not an object"), ([{"dependencyId": "fish"}], "dependencyId"), ([{"dependencyId": "brain:Bad_Id"}], "dependencyId"),
    ([{"dependencyId": "brain:x", "dependencyType": "PROVIDER_DATA"}], "does not match"), ([{"dependencyId": "brain:x", "secret": 1}], "unknown keys"),
    ([{"dependencyId": "brain:x", "consumedAt": "yesterday"}], "ISO-8601"), ([{"dependencyId": "brain:x", "freshnessStatus": "OK"}], "freshnessStatus"),
    ([{"dependencyId": "brain:x"}, {"dependencyId": "brain:x"}], "duplicate"), ([{"dependencyId": "brain:x", "ref": ""}], "non-empty"),
])
def test_invalid_lineage_is_rejected_not_repaired(bad, needle):
    errs = CN.validate_consumed(bad)
    assert errs and needle in errs[0]
    with pytest.raises(ValueError):
        CN.finalize(bad)


def test_missing_fields_stay_absent_and_unknown_stays_unknown():
    e = CN.finalize([{"dependencyId": "signal:pressure-trend", "consumedAt": T(0)}])[0]
    assert e == {"dependencyId": "signal:pressure-trend", "dependencyType": "ENVIRONMENTAL_SIGNAL", "consumedAt": T(0)}
    d = {"dependencyId": "signal:pressure-trend", "dependencyType": "ENVIRONMENTAL_SIGNAL", "declaringBrain": "c", "target": "pressure-trend", "requirement": "OPTIONAL", "requirementDeclared": True}
    row = DH.evaluate_dependency(d, None, NOW, consumed=e)
    assert row["evaluationBasis"] == "RECORDED_CONSUMPTION" and row["freshnessStatus"] == "UNKNOWN" and row["dependencyStatus"] == "UNKNOWN"
    assert "ageHoursAtConsumption" not in row and "lineageRef" not in row


def test_recorded_consumption_is_immutable_in_the_execution_ledger():
    started = NOW - dt.timedelta(minutes=5)
    lineage = [{"dependencyId": "brain:alpha-upstream", "stateVersion": "3", "consumedAt": T(0.05)}]
    first = O.execution_record("e1", "me", "MANUAL", "asked", started, NOW, "SUCCEEDED", consumed=lineage)
    again = O.execution_record("e1", "me", "MANUAL", "asked", started, NOW, "SUCCEEDED")                         # re-observed, lineage not repeated
    assert CS.merge_execution(first, again)["consumed"] == EH.normalize_consumed(lineage)
    changed = O.execution_record("e1", "me", "MANUAL", "asked", started, NOW, "SUCCEEDED", consumed=[{"dependencyId": "brain:alpha-upstream", "stateVersion": "99"}])
    m = CS.merge_execution(first, changed)
    assert m["consumed"] == first["consumed"] and m["lineageConflict"] is True                                  # first recorded truth wins, loudly
    assert CS.merge_execution(None, changed) == changed and "lineageConflict" not in CS.merge_execution(first, first)
    m_ = O.load_manifest()
    ev = O.evaluate_world({"manifest": m_, "mode": "PRE_PRODUCTION", "now": NOW, "states": {}, "activity": O.effective_activity(m_), "running": {}, "out_fps": {}, "last_in_fps": {}}, None)
    st1 = CS.build_control_state(m_, "PRE_PRODUCTION", NOW, registries={}, health={}, scores={}, jobs={}, evaluation=ev,
                                 new_executions=[O.execution_record("w1", "wind", "SCHEDULE", "due", started, NOW, "SUCCEEDED", consumed=lineage)])
    st2 = CS.build_control_state(m_, "PRE_PRODUCTION", NOW + dt.timedelta(hours=1), registries={}, health={}, scores={}, jobs={}, evaluation=ev, prev=st1,
                                 new_executions=[O.execution_record("w1", "wind", "SCHEDULE", "due", started, NOW, "SUCCEEDED")])
    assert st2["executions"]["w1"]["consumed"] == st1["executions"]["w1"]["consumed"]


def test_historical_freshness_is_judged_as_consumed_and_never_rewritten_by_current_state():
    """Execution at 18:20 consumed an observation from 17:55 with the owner's staleAfter 18:10: STALE at consumption, 25 min old — and it stays so
    when the current state later becomes fresh. A fresh-at-consumption read stays FRESH even when the current state is stale now."""
    declared = [{"dependencyId": "brain:alpha-upstream", "dependencyType": "BRAIN", "declaringBrain": "me", "target": "alpha-upstream", "requirement": "REQUIRED", "requirementDeclared": True}]
    stale_then = [{"dependencyId": "brain:alpha-upstream", "evidenceObservedAt": "2026-10-16T17:55:00Z", "staleAfter": "2026-10-16T18:10:00Z", "consumedAt": "2026-10-16T18:20:00Z", "stateVersion": "3"}]
    fresh_then = [{"dependencyId": "brain:alpha-upstream", "evidenceObservedAt": "2026-10-16T18:15:00Z", "staleAfter": "2026-10-16T19:00:00Z", "consumedAt": "2026-10-16T18:20:00Z", "stateVersion": "4"}]
    later = NOW + dt.timedelta(hours=6)
    ex_stale = O.execution_record("e-stale", "me", "MANUAL", "asked", NOW - dt.timedelta(minutes=1), NOW, "SUCCEEDED", consumed=stale_then)
    ex_fresh = O.execution_record("e-fresh", "me", "MANUAL", "asked", NOW - dt.timedelta(minutes=1), NOW, "SUCCEEDED", consumed=fresh_then)
    now_fresh = {"brain:alpha-upstream": {"available": True, "freshnessStatus": "FRESH", "evidenceObservedAt": (later - dt.timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}}
    now_stale = {"brain:alpha-upstream": {"available": True, "freshnessStatus": "STALE", "evidenceObservedAt": T(40)}}
    h1 = BH.brain_health("me", declared=declared, declarations_known=True, executions=[ex_stale], observations=now_fresh, now=later)
    row = h1["dependencies"]["rows"][0]
    assert row["evaluationBasis"] == "RECORDED_CONSUMPTION" and row["freshnessStatus"] == "STALE" and row["ageHoursAtConsumption"] == 0.42
    assert row["consumedAt"] == "2026-10-16T18:20:00Z" and row["lineageRef"] == {"stateVersion": "3"} and h1["freshness"]["status"] == "STALE"
    assert h1["dependencies"]["declaredVsActual"] == {"consumptionRecorded": True, "declaredAndConsumed": ["brain:alpha-upstream"]}
    h2 = BH.brain_health("me", declared=declared, declarations_known=True, executions=[ex_fresh], observations=now_stale, now=later)
    assert h2["dependencies"]["rows"][0]["freshnessStatus"] == "FRESH" and h2["freshness"]["status"] == "FRESH"                       # fresh WHEN consumed
    h3 = BH.brain_health("me", declared=declared, declarations_known=True, executions=[O.execution_record("e0", "me", "MANUAL", "asked", NOW, NOW, "SUCCEEDED")], observations=now_stale, now=later)
    assert h3["dependencies"]["rows"][0]["evaluationBasis"] == "CURRENT_STATE" and h3["dependencies"]["declaredVsActual"]["consumptionRecorded"] is False
    assert json.dumps(h1, sort_keys=True) == json.dumps(BH.brain_health("me", declared=declared, declarations_known=True, executions=[ex_stale], observations=now_fresh, now=later), sort_keys=True)


def test_declared_vs_actual_from_a_real_recording():
    """A consumer declares A (required) and B (optional); its run actually read A and an undeclared C. Nothing from the declaration is copied."""
    r, db = rec_and_store("me")
    db.get("brains/alpha-upstream"); db.get("brains/gamma")
    consumed = db.consumed()
    assert [e["dependencyId"] for e in consumed] == ["brain:alpha-upstream", "brain:gamma"]
    declared = [{"dependencyId": "brain:alpha-upstream", "dependencyType": "BRAIN", "declaringBrain": "me", "target": "alpha-upstream", "requirement": "REQUIRED", "requirementDeclared": True},
                {"dependencyId": "brain:beta", "dependencyType": "BRAIN", "declaringBrain": "me", "target": "beta", "requirement": "OPTIONAL", "requirementDeclared": True}]
    ex = O.execution_record("e1", "me", "MANUAL", "asked", NOW - dt.timedelta(minutes=1), NOW, "SUCCEEDED", consumed=consumed)
    h = BH.brain_health("me", declared=declared, declarations_known=True, executions=[ex], observations={"brain:beta": None}, now=NOW)
    dva = h["dependencies"]["declaredVsActual"]
    assert dva == {"consumptionRecorded": True, "declaredAndConsumed": ["brain:alpha-upstream"], "declaredNotConsumed": ["brain:beta"], "consumedNotDeclared": ["brain:gamma"]}
    rows = {x["dependencyId"]: x for x in h["dependencies"]["rows"]}
    assert rows["brain:alpha-upstream"]["evaluationBasis"] == "RECORDED_CONSUMPTION" and rows["brain:alpha-upstream"]["dependencyStatus"] == "SATISFIED"
    assert rows["brain:beta"]["evaluationBasis"] == "CURRENT_STATE" and rows["brain:beta"]["dependencyStatus"] == "DEGRADED"    # declared, not read, and missing now


def test_old_execution_record_signature_and_lineage_free_executions_still_work():
    old = O.execution_record("x", "me", "SCHEDULE", "due", NOW - dt.timedelta(minutes=3), NOW, "SUCCEEDED")
    assert "consumed" not in old and EH.normalize_execution(old)["consumptionRecorded"] is False
    assert EH.execution_summary("me", [old], NOW)["processHealth"] == "HEALTHY"
    assert DH.reconcile_consumption([], EH.normalize_execution(old))["consumptionRecorded"] is False
