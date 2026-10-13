"""The shared conformance suite (docs/brains/conformance/*.json) run against the Python platform."""
import datetime as dt
import json
import os
import re

import pytest

from sector_brain_platform import (
    BrainRtdb, BrainRtdbError, DryRunStore, IllegalKey, OwnershipError, ACTIVITY_KIND, BRAIN_STATUS, BRAINS, HEALTH,
    MODEL_LIFECYCLE, READINESS, READINESS_LADDER, SEVERITY, STALENESS_MODEL, STATE_KIND, VERSION_STATUS,
    assert_owned, backoff_seconds, check_keys, check_update, check_schema, event_id, failure_writes, freshness, is_promotion,
    key_collisions, lake_key, lake_keys, normalize_model_lifecycle, normalize_state_kind, parse_time, path_allowed,
    prune_activity, run_health, should_retry, slot_for, snapshot_field_for, source_owner,
)

FIX = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "brains", "conformance")


def fixture(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


# ---------------------------------------------------------------- keys
def test_lake_keys():
    fx = fixture("lake_keys.json")
    for c in fx["cases"]:
        assert lake_key(c["lakeId"]) == c["key"], c
    for c in fx["collisions"]:
        assert bool(key_collisions(c["ids"])) == c["collides"], c
        if c["collides"]:
            with pytest.raises(ValueError):
                lake_keys(c["ids"])
        else:
            assert lake_keys(c["ids"])
    for k in fx["illegal_keys"]:
        with pytest.raises(IllegalKey):
            check_keys({k: 1})
    for k in fx["legal_keys"]:
        check_keys({k: 1})
    check_update({"lakes/Guntersville_AL/states/waterTemp": {"kind": "measured"}})   # multi-path keys are paths
    with pytest.raises(IllegalKey):
        check_update({"lakes/Gunters.ville/states": 1})
    with pytest.raises(IllegalKey):
        check_update({"lakes/x": {"bad.key": 1}})


# ---------------------------------------------------------------- events
def test_event_ids():
    fx = fixture("event_ids.json")
    pat = re.compile(fx["pattern"])
    for c in fx["cases"]:
        assert event_id(c["atMs"], c["brainId"], c["n"]) == c["id"], c
        assert pat.match(c["id"])
    assert sorted(fx["ordering"]["ids"]) == fx["ordering"]["sorted"]
    assert event_id(dt.datetime(2026, 10, 12, 4, 20, tzinfo=dt.timezone.utc), "wind", 1) == f"{1791778800000:013d}-wind-001"


def test_pruning():
    fx = fixture("pruning.json")
    now = parse_time(fx["now"])
    for c in fx["cases"]:
        dels = prune_activity(c["activity"], c["brainId"], now, keep=c.get("keep", fx["keep"]), max_age_days=fx["maxAgeDays"])
        assert sorted(k.split("/", 1)[1] for k in dels) == sorted(c["expectDeleted"]), c["name"]
        assert all(v is None for v in dels.values())


# ---------------------------------------------------------------- transport
def test_retry_policy():
    fx = fixture("retry_policy.json")
    for d in fx["decisions"]:
        if d["status"] == 200:
            continue
        assert should_retry(d["status"]) == d["retry"], d
    assert [backoff_seconds(i) for i in range(fx["attempts"] - 1)] == fx["backoffSeconds"]
    for u in fx["refusedUrls"]:
        with pytest.raises(ValueError):
            BrainRtdb(u, transport=lambda *a: (200, "null"))
    for u in fx["acceptedUrls"]:
        BrainRtdb(u, tokens=_Tok(), transport=lambda *a: (200, "null"))


class _Tok:
    def token(self):
        return "t"


def test_rtdb_retries_5xx_not_4xx():
    calls = []
    def t500(method, url, body):
        calls.append(method); return (503, "down")
    slept = []
    db = BrainRtdb(tokens=_Tok(), transport=t500, sleep=slept.append)
    with pytest.raises(BrainRtdbError):
        db.get("schemaVersion")
    assert len(calls) == 4 and slept == [1.5, 3.0, 6.0]
    calls.clear(); slept.clear()
    db = BrainRtdb(tokens=_Tok(), transport=lambda m, u, b: (403, "no"), sleep=slept.append)
    with pytest.raises(BrainRtdbError):
        db.get("x")
    assert slept == []


def test_schema_gate():
    assert check_schema(DryRunStore({"schemaVersion": 1})) == 1
    assert check_schema(DryRunStore({})) is None
    with pytest.raises(BrainRtdbError):
        check_schema(DryRunStore({"schemaVersion": 2}))


def test_update_rejects_nan_illegal_keys_and_foreign_paths():
    s = DryRunStore(brain_id="water-temp")
    with pytest.raises(ValueError):
        s.update({"brains/water-temp/x": float("nan")})
    with pytest.raises(IllegalKey):
        s.update({"brains/water-temp/bad.key": 1})
    with pytest.raises(OwnershipError):
        s.update({"brains/water-temp/x": 1, "lakeFleet/Guntersville_AL/lastUpdatedAt": "now"})
    assert s.patches == []                                 # refused whole
    s.update({"brains/water-temp/x": 1, "lakeFleet/Guntersville_AL/lakeId": "Guntersville|AL"})
    assert s.get("lakeFleet/Guntersville_AL/lakeId") == "Guntersville|AL"
    assert s.get("lakeFleet", shallow=True) == {"Guntersville_AL": True}
    s.delete("brains/water-temp/x")
    assert s.get("brains/water-temp/x") is None


# ---------------------------------------------------------------- health / freshness
def test_health():
    for c in fixture("health.json")["cases"]:
        assert run_health(c["attempted"], c["ok"], c["failed"], c["aborted"], c["partial"], c["publishFailed"]) == c["health"], c


def test_freshness():
    for c in fixture("freshness.json")["cases"]:
        f = freshness(c["generatedAt"], parse_time(c["now"]), c["staleAfterHours"], c["stalenessModel"],
                      evidence_stale=c["evidenceStale"], evidence_reasons=[c.get("evidenceReason", "")])
        e = c["expect"]
        assert f["stale"] == e["stale"], c
        assert f.get("freshUntil") == e["freshUntil"], c
        assert len(f.get("staleReasons", [])) == e["staleReasonsCount"], c
        assert f["evidenceStale"] == c["evidenceStale"]
        assert f["generatedAt"] == c["generatedAt"]
    with pytest.raises(ValueError):
        freshness("2026-10-12T00:00:00Z", parse_time("2026-10-12T01:00:00Z"), 1, "AGE")


# ---------------------------------------------------------------- ownership / vocabularies
def test_ownership():
    fx = fixture("ownership.json")
    for c in fx["cases"]:
        assert path_allowed(c["brainId"], c["path"]) == c["allowed"], c
    for sid, owner in fx["sourceOwners"].items():
        assert source_owner(sid) == owner
    with pytest.raises(OwnershipError):
        assert_owned({"schemaVersion": 2}, "wind")


def test_vocabularies():
    fx = fixture("vocabularies.json")
    assert list(HEALTH) == fx["health"] and list(READINESS) == fx["readiness"] and list(READINESS_LADDER) == fx["readinessLadder"]
    assert list(BRAIN_STATUS) == fx["brainStatus"] and list(MODEL_LIFECYCLE) == fx["modelLifecycle"]
    assert list(VERSION_STATUS) == fx["versionStatus"] and list(STATE_KIND) == fx["stateKind"]
    assert list(STALENESS_MODEL) == fx["stalenessModel"] and list(SEVERITY) == fx["severity"]
    assert list(ACTIVITY_KIND) == fx["activityKind"]
    for bid, b in fx["brains"].items():
        assert slot_for(bid) == b["slot"] and snapshot_field_for(bid) == b["snapshotField"] and BRAINS[bid][2] == b["displayName"]
    for p in fx["promotions"]:
        assert is_promotion(p["from"], p["to"]) == p["promoted"], p
    for old, new in fx["legacyMappings"]["modelLifecycle"].items():
        assert normalize_model_lifecycle(old) == new
    for old, new in fx["legacyMappings"]["stateKind"].items():
        assert normalize_state_kind(old) == new
    with pytest.raises(ValueError):
        normalize_state_kind("stateType")


def test_failure_writes_are_owned_and_complete():
    now = dt.datetime(2026, 10, 12, 12, 0, tzinfo=dt.timezone.utc)
    w = failure_writes("water-clarity", "boom", now, started=now - dt.timedelta(seconds=5), job_id="water-clarity-brain")
    assert_owned(w, "water-clarity")
    assert w["health/brains/water-clarity/status"] == "FAILED" and w["brains/water-clarity/health"] == "FAILED"
    assert w["health/brains/water-clarity/durationMs"] == 5000
    ev = [v for k, v in w.items() if k.startswith("activity/")][0]
    assert ev["kind"] == "run.failed" and ev["severity"] == "critical" and ev["brainId"] == "water-clarity"
