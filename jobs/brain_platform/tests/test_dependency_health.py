"""G2 dependency + freshness health (dependency-health-v1): fresh / stale / expired / missing / unknown, required vs optional, multiple
dependency types, owner authority vs consumer rule, recorded vs current consumption, lastSuccessfulRun != freshness, unknown != zero."""
import datetime as dt
import json

import pytest

from sector_brain_platform import dependency_health as DH
from sector_brain_platform.publisher.model import FRESHNESS_STATUSES

NOW = dt.datetime(2026, 10, 16, 12, 0, tzinfo=dt.timezone.utc)


def iso(h_ago):
    return (NOW - dt.timedelta(hours=h_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def dep(did, t="BRAIN", req="REQUIRED", **kw):
    d = {"dependencyId": did, "dependencyType": t, "declaringBrain": "alpha", "target": did.split(":", 1)[1], "requirementDeclared": req is not None}
    if req:
        d["requirement"] = req
    d.update(kw)
    return d


def test_freshness_vocabulary_is_the_publisher_vocabulary():
    assert DH.FRESHNESS_STATUS == FRESHNESS_STATUSES == ("FRESH", "STALE", "EXPIRED", "UNAVAILABLE", "UNKNOWN")
    assert set(DH.DEPENDENCY_STATUS) == {"SATISFIED", "DEGRADED", "UNSATISFIED", "UNKNOWN"}


def test_fresh_required_dependency_from_owner_verdict():
    r = DH.evaluate_dependency(dep("brain:beta"), {"available": True, "freshnessStatus": "FRESH", "evidenceObservedAt": iso(1), "generatedAt": iso(0.5),
                                                   "publishedAt": iso(0.4), "stateVersion": "v7", "ref": "/brains/beta"}, NOW)
    assert r["availability"] == "AVAILABLE" and r["freshnessStatus"] == "FRESH" and r["freshnessAuthority"] == "OWNER_VERDICT"
    assert r["dependencyStatus"] == "SATISFIED" and r["ageHoursAtConsumption"] == 1.0 and r["ageBasis"] == "EVIDENCE_OBSERVED"
    assert r["lineageRef"] == {"ref": "/brains/beta", "stateVersion": "v7"} and r["evaluationBasis"] == "CURRENT_STATE"
    assert r["evidenceObservedAt"] == iso(1) and r["generatedAt"] == iso(0.5) and r["publishedAt"] == iso(0.4)


def test_stale_required_and_stale_optional_dependency():
    stale = {"available": True, "freshnessStatus": "STALE", "evidenceObservedAt": iso(30)}
    req = DH.evaluate_dependency(dep("brain:beta"), stale, NOW)
    assert req["freshnessStatus"] == "STALE" and req["dependencyStatus"] == "DEGRADED"
    opt = DH.evaluate_dependency(dep("brain:beta", req="OPTIONAL"), stale, NOW)
    assert opt["freshnessStatus"] == "STALE" and opt["dependencyStatus"] == "DEGRADED" and opt["requirement"] == "OPTIONAL"
    agg = DH.aggregate([req, DH.evaluate_dependency(dep("brain:gamma", req="OPTIONAL"), stale, NOW)])
    assert agg["dependencyHealth"] == "DEGRADED" and agg["freshnessHealth"] == "STALE"
    only_optional_stale = DH.aggregate([opt])
    assert only_optional_stale["freshnessHealth"] == "UNKNOWN" and only_optional_stale["dependencyHealth"] == "DEGRADED"   # optional never bounds freshness: not assessable


def test_missing_dependency():
    r = DH.evaluate_dependency(dep("brain:beta"), None, NOW)
    assert r["availability"] == "MISSING" and r["freshnessStatus"] == "UNAVAILABLE" and r["dependencyStatus"] == "UNSATISFIED"
    o = DH.evaluate_dependency(dep("brain:beta", req="OPTIONAL"), {"available": False, "reason": "node absent"}, NOW)
    assert o["dependencyStatus"] == "DEGRADED" and "node absent" in o["reasons"]
    agg = DH.aggregate([r])
    assert agg["dependencyHealth"] == "UNSATISFIED" and agg["freshnessHealth"] == "UNAVAILABLE"


def test_expired_dependency_and_owner_rules():
    r = DH.evaluate_dependency(dep("brain:beta"), {"available": True, "generatedAt": iso(10), "staleAfter": iso(6), "expiresAt": iso(2)}, NOW)
    assert r["freshnessStatus"] == "EXPIRED" and r["freshnessAuthority"] == "OWNER_RULE" and r["dependencyStatus"] == "UNSATISFIED"
    s = DH.evaluate_dependency(dep("brain:beta"), {"available": True, "generatedAt": iso(10), "staleAfter": iso(6), "expiresAt": iso(-2)}, NOW)
    assert s["freshnessStatus"] == "STALE" and s["dependencyStatus"] == "DEGRADED"
    f = DH.evaluate_dependency(dep("brain:beta"), {"available": True, "generatedAt": iso(1), "staleAfterHours": 3}, NOW)
    assert f["freshnessStatus"] == "FRESH" and f["ageBasis"] == "GENERATED" and f["staleAfterHours"] == 3
    env = DH.evaluate_dependency(dep("brain:beta"), {"available": True, "generatedAt": iso(1), "stale": False, "evidenceStale": True}, NOW)
    assert env["freshnessStatus"] == "STALE" and env["freshnessAuthority"] == "OWNER_VERDICT"            # evidenceStale is the owner's own rule


def test_last_successful_run_is_never_evidence_freshness():
    r = DH.evaluate_dependency(dep("brain:beta"), {"available": True, "lastSuccessfulRun": iso(0.1), "staleAfterHours": 3}, NOW)
    assert r["freshnessStatus"] == "UNKNOWN" and r["dependencyStatus"] == "UNKNOWN" and "ageHoursAtConsumption" not in r
    assert any("process history, not evidence freshness" in x for x in r["reasons"])
    agg = DH.aggregate([r])
    assert agg["freshnessHealth"] == "UNKNOWN" and agg["dependencyHealth"] == "UNKNOWN"                   # never promoted to FRESH


def test_unknown_is_a_value_not_zero_and_not_fresh():
    u = DH.evaluate_dependency(dep("signal:x", "ENVIRONMENTAL_SIGNAL"), {"available": None, "reason": "not observed by the Engine"}, NOW)
    assert u["availability"] == "UNKNOWN" and u["freshnessStatus"] == "UNKNOWN" and u["dependencyStatus"] == "UNKNOWN"
    assert "ageHoursAtConsumption" not in u and "staleAfterHours" not in u
    mixed = DH.aggregate([u, DH.evaluate_dependency(dep("brain:beta"), {"available": True, "freshnessStatus": "FRESH", "generatedAt": iso(1)}, NOW)])
    assert mixed["freshnessHealth"] == "UNKNOWN" and mixed["dependencyHealth"] == "UNKNOWN"              # one unknown required input: not FRESH
    assert mixed["counts"]["byFreshness"] == {"FRESH": 1, "UNKNOWN": 1}
    unknown_decls = DH.aggregate([], declarations_known=False)
    assert unknown_decls["dependencyHealth"] == "UNKNOWN" and unknown_decls["freshnessHealth"] == "UNKNOWN"
    none_decls = DH.aggregate([], declarations_known=True)
    assert none_decls["dependencyHealth"] == "SATISFIED" and none_decls["freshnessHealth"] == "UNKNOWN"      # vacuous requirement, never vacuous freshness


def test_undeclared_requirement_is_treated_as_required_and_said_so():
    r = DH.evaluate_dependency(dep("provider:p", "PROVIDER_DATA", req=None), None, NOW)
    assert r["requirement"] == "REQUIRED" and r["dependencyStatus"] == "UNSATISFIED"
    assert any("not declared" in x for x in r["reasons"])


def test_consumer_rule_only_stricter_and_documented():
    pol = {"maxAgeHours": 2, "reason": "same-day evidence needed"}
    r = DH.evaluate_dependency(dep("brain:beta", freshnessPolicy=pol), {"available": True, "freshnessStatus": "FRESH", "evidenceObservedAt": iso(5)}, NOW)
    assert r["freshnessStatus"] == "STALE" and r["ownerFreshnessStatus"] == "FRESH" and r["freshnessAuthority"] == "CONSUMER_RULE"
    assert any("consumer rule" in x and "same-day" in x for x in r["reasons"]) and r["consumerMaxAgeHours"] == 2
    looser = DH.evaluate_dependency(dep("brain:beta", freshnessPolicy={"maxAgeHours": 48, "reason": "x"}), {"available": True, "freshnessStatus": "STALE", "evidenceObservedAt": iso(5)}, NOW)
    assert looser["freshnessStatus"] == "STALE" and looser["freshnessAuthority"] == "OWNER_VERDICT"        # a consumer can never loosen the owner's STALE
    no_age = DH.evaluate_dependency(dep("brain:beta", freshnessPolicy=pol), {"available": True, "freshnessStatus": "FRESH"}, NOW)
    assert no_age["freshnessStatus"] == "FRESH" and any("cannot be applied" in x for x in no_age["reasons"])


def test_multiple_dependency_types_in_one_evaluation():
    rows = [dep("brain:beta"), dep("signal:pressure-trend", "ENVIRONMENTAL_SIGNAL", req="OPTIONAL"), dep("provider:nbm", "PROVIDER_DATA"), dep("registry:lakes", "PLATFORM_REGISTRY")]
    obs = {"brain:beta": {"available": True, "freshnessStatus": "FRESH", "generatedAt": iso(1)},
           "signal:pressure-trend": {"available": False, "reason": "signal DECLARED only (no producer)"},
           "provider:nbm": {"available": True, "evidenceObservedAt": iso(2), "staleAfterHours": 3},
           "registry:lakes": {"available": True, "freshnessStatus": "FRESH", "reason": "version-based registry contract"}}
    out = DH.evaluate_all(rows, obs, NOW)
    assert [r["dependencyId"] for r in out] == ["brain:beta", "provider:nbm", "registry:lakes", "signal:pressure-trend"]      # deterministic order
    by = {r["dependencyId"]: r for r in out}
    assert by["signal:pressure-trend"]["dependencyStatus"] == "DEGRADED" and by["provider:nbm"]["dependencyStatus"] == "SATISFIED"
    agg = DH.aggregate(out)
    assert agg["dependencyHealth"] == "DEGRADED" and agg["freshnessHealth"] == "FRESH" and agg["counts"]["byType"] == {"BRAIN": 1, "ENVIRONMENTAL_SIGNAL": 1, "PLATFORM_REGISTRY": 1, "PROVIDER_DATA": 1}
    missing_key = DH.evaluate_all([dep("brain:zeta")], {}, NOW)[0]
    assert missing_key["availability"] == "UNKNOWN"                                               # not observed != missing


def test_declared_vs_actual_recorded_consumption():
    rows = [dep("brain:beta"), dep("brain:gamma", req="OPTIONAL")]
    execution = {"executionId": "e1", "consumptionRecorded": True,
                 "consumed": [{"dependencyId": "brain:beta", "stateVersion": "v3", "generatedAt": iso(5), "consumedAt": iso(4)},
                              {"dependencyId": "brain:omega", "stateVersion": "1"}]}
    out = DH.evaluate_all(rows, {"brain:beta": {"available": True, "freshnessStatus": "FRESH", "generatedAt": iso(0.1)}}, NOW, execution)
    beta = next(r for r in out if r["dependencyId"] == "brain:beta")
    assert beta["evaluationBasis"] == "RECORDED_CONSUMPTION" and beta["consumedAt"] == iso(4) and beta["ageHoursAtConsumption"] == 1.0
    assert beta["lineageRef"] == {"stateVersion": "v3"} and beta["freshnessStatus"] == "UNKNOWN"      # consumed state carried no verdict/rule: unknown at consumption
    gamma = next(r for r in out if r["dependencyId"] == "brain:gamma")
    assert gamma["evaluationBasis"] == "CURRENT_STATE" and gamma["availability"] == "UNKNOWN"
    recon = DH.reconcile_consumption(rows, execution)
    assert recon == {"consumptionRecorded": True, "declaredAndConsumed": ["brain:beta"], "declaredNotConsumed": ["brain:gamma"], "consumedNotDeclared": ["brain:omega"]}
    none = DH.reconcile_consumption(rows, {"executionId": "e0", "consumptionRecorded": False})
    assert none["consumptionRecorded"] is False and none["declaredNotConsumed"] == []                  # nothing inferred when nothing recorded


def test_output_is_deterministic_json():
    rows = [dep("brain:beta"), dep("provider:nbm", "PROVIDER_DATA", req="OPTIONAL")]
    obs = {"brain:beta": {"available": True, "freshnessStatus": "STALE", "generatedAt": iso(9)}, "provider:nbm": None}
    a = json.dumps(DH.evaluate_all(rows, obs, NOW), sort_keys=True)
    b = json.dumps(DH.evaluate_all(list(reversed(rows)), dict(reversed(list(obs.items()))), NOW), sort_keys=True)
    assert a == b
