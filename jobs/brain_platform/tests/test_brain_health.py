"""brain-health-v1: five health concepts side by side, operational aggregate, declared vs actual, the control/healthV1 node, content-aware
publication, RTDB safety, and the conformance fixture that mirrors the vocabularies for Ops."""
import datetime as dt
import json
import os
import re

from sector_brain_platform import brain_health as BH, dependency_declarations as DD, dependency_health as DH, execution_health as EH, signals as SG, orchestration as O
from sector_brain_platform.model_v1 import VALIDATION_STATUS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
NOW = dt.datetime(2026, 10, 16, 12, 0, tzinfo=dt.timezone.utc)


def iso(h_ago):
    return (NOW - dt.timedelta(hours=h_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def dep(did, t="BRAIN", req="REQUIRED"):
    return {"dependencyId": did, "dependencyType": t, "declaringBrain": "alpha", "target": did.split(":", 1)[1], "requirement": req, "requirementDeclared": True}


def ex(eid, status, started_h, ended_h, **kw):
    r = {"executionId": eid, "brainId": "alpha", "trigger": "SCHEDULE", "reason": "due", "startedAt": iso(started_h), "endedAt": iso(ended_h), "status": status, "source": "orchestrator"}
    r.update(kw)
    return r


def test_five_concepts_stay_distinct_and_lastsuccess_is_not_freshness():
    h = BH.brain_health("alpha", declared=[dep("brain:beta")], declarations_known=True,
                        executions=[ex("e1", "SUCCEEDED", 0.2, 0.1, codeVersion="c9")],
                        observations={"brain:beta": {"available": True, "freshnessStatus": "STALE", "evidenceObservedAt": iso(40)}},
                        now=NOW, expected_interval_hours=6, registry={"validationStatus": "NOT_VALIDATED"}, publication={"status": "SHADOW", "publishedAt": iso(0.1)})
    assert h["process"]["processHealth"] == "HEALTHY" and h["process"]["lastSuccessfulAt"] == iso(0.1)       # the job just ran fine
    assert h["freshness"]["status"] == "STALE" and h["dependencies"]["dependencyHealth"] == "DEGRADED"      # ...but the evidence it consumed is stale
    assert h["domainValidation"] == {"status": "NOT_VALIDATED", "source": "registry.validationStatus"}
    assert h["publish"]["status"] == "SHADOW"
    assert h["aggregate"]["status"] == "DEGRADED" and h["aggregate"]["worstComponent"] in ("dependencies", "freshness")
    assert "domainValidation" not in h["aggregate"]["inputs"]                                                  # scientific trust is never folded in
    assert h["dependencies"]["basis"] == "CURRENT_STATE" and h["dependencies"]["declaredVsActual"]["consumptionRecorded"] is False


def test_unknown_components_are_listed_and_never_green():
    h = BH.brain_health("alpha", declared=[dep("brain:beta")], declarations_known=True, executions=[], observations={}, now=NOW)
    assert h["aggregate"]["status"] == "UNKNOWN" and set(h["aggregate"]["unknownComponents"]) == {"process", "dependencies", "freshness", "publish"}
    assert h["domainValidation"]["status"] == "UNKNOWN" and h["publish"]["status"] == "UNKNOWN"
    partial = BH.brain_health("alpha", declared=[], declarations_known=True, executions=[ex("e1", "FAILED", 1, 0.9)], observations={}, now=NOW)
    assert partial["aggregate"]["status"] == "FAILED" and partial["aggregate"]["worstComponent"] == "process" and partial["aggregate"]["unknownComponents"] == ["freshness", "publish"]
    nc = BH.brain_health("alpha", declared=[], declarations_known=True, executions=[], observations={}, now=NOW, runtime_configured=False)
    assert nc["process"]["processHealth"] == "NOT_CONFIGURED" and nc["aggregate"]["notConfigured"] is True and nc["aggregate"]["status"] == "HEALTHY"
    assert BH.aggregate("UNKNOWN", "SATISFIED", "FRESH", "SHADOW")["status"] == "UNKNOWN"                   # unknown process is the floor
    assert BH.aggregate("HEALTHY", "SATISFIED", "FRESH", "REJECTED")["status"] == "FAILED"
    assert BH.aggregate("HEALTHY", "SATISFIED", "FRESH", "UNKNOWN", "OVERDUE")["status"] == "WARNING"
    assert BH.aggregate("HEALTHY", "SATISFIED", "EXPIRED", "SHADOW")["status"] == "FAILED"


def test_declared_vs_actual_consumption_drives_the_dependency_verdict():
    exec_with_lineage = ex("e2", "SUCCEEDED", 1, 0.9, consumed=[{"dependencyId": "brain:beta", "stateVersion": "v4", "generatedAt": iso(2), "consumedAt": iso(1),
                                                                 "evidenceObservedAt": iso(2.5), "staleAfter": iso(0.5)}])
    h = BH.brain_health("alpha", declared=[dep("brain:beta"), dep("brain:gamma", req="OPTIONAL")], declarations_known=True, executions=[exec_with_lineage],
                        observations={"brain:beta": {"available": True, "freshnessStatus": "STALE"}, "brain:gamma": None}, now=NOW)
    assert h["dependencies"]["basis"] == "RECORDED_CONSUMPTION"
    beta = next(r for r in h["dependencies"]["rows"] if r["dependencyId"] == "brain:beta")
    assert beta["evaluationBasis"] == "RECORDED_CONSUMPTION" and beta["freshnessStatus"] == "FRESH" and beta["lineageRef"] == {"stateVersion": "v4"}   # fresh WHEN consumed, even if stale now
    assert h["dependencies"]["declaredVsActual"] == {"consumptionRecorded": True, "declaredAndConsumed": ["brain:beta"], "declaredNotConsumed": ["brain:gamma"]}   # empty lists are stripped (RTDB drops them)
    assert h["freshness"]["status"] == "FRESH" and h["dependencies"]["dependencyHealth"] == "DEGRADED"       # gamma (optional) missing now


def test_domain_validation_and_publish_are_pass_through_only():
    assert BH.domain_validation({"validationStatus": "VALIDATED"})["status"] == "VALIDATED"
    assert BH.domain_validation(None, {"status": "CALIBRATION"})["source"] == "validation.status"
    assert BH.domain_validation({"validationStatus": "great"})["status"] == "UNKNOWN"
    assert BH.DOMAIN_VALIDATION == VALIDATION_STATUS + ("UNKNOWN",)
    assert BH.publish_health({"status": "REJECTED", "executionId": "e1"}) == {"status": "REJECTED", "executionId": "e1"}
    assert BH.publish_health({"status": "LIVE"})["status"] == "UNKNOWN"
    assert set(BH.PUBLISH_STATUS) >= {"SHADOW", "SKIPPED_UNCHANGED", "REJECTED", "PUBLISHED", "NOT_APPLICABLE", "UNKNOWN"}


def test_health_state_node_on_the_real_repo_is_honest_rtdb_safe_and_content_aware():
    reg = DD.load_registered_brains(ROOT)
    m = O.load_manifest()
    g = DD.dependency_graph(reg, manifest=m, signals=SG.load(), providers=DD.load_providers(ROOT))
    brains = {}
    for bid, gb in g["brains"].items():
        brains[bid] = BH.brain_health(bid, declared=gb["rows"], declarations_known=gb["declarationsKnown"], executions=[], observations={}, now=NOW,
                                      registry={"lastSuccessfulRun": iso(0.5)})
    st = BH.health_state(brains, g, SG.load(), NOW, engine_mode=m["engineMode"])
    assert set(st) == set(BH.SECTIONS)
    assert all(b["aggregate"]["status"] == "UNKNOWN" for b in st["brains"].values())                       # no observation, no verdict: nothing invented
    assert all("ageHoursAtConsumption" not in json.dumps(b["dependencies"]) for b in st["brains"].values())
    assert st["summary"]["aggregateCounts"] == {"UNKNOWN": len(brains)} and st["summary"]["engineMode"] == "PRE_PRODUCTION"
    assert set(st["signals"]) == set(SG.load()) and st["dependencies"]["edges"]
    text = json.dumps(st)
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k; yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    assert not [k for k in keys(st) if re.search(r"[.$#\[\]/]", k)], "illegal RTDB key"
    assert not re.search(r"secret|token|apikey|password|gs://|@", text, re.I) and BH._strip(st) == st
    first = BH.changed_paths(st, None)
    assert set(first) == {f"{BH.NODE}/{s}" for s in BH.SECTIONS}
    later = BH.health_state(brains, g, SG.load(), NOW + dt.timedelta(hours=1), engine_mode=m["engineMode"])
    assert BH.changed_paths(later, st) == {}                                                                  # only timestamps moved: nothing rewritten
    brains2 = dict(brains); brains2["wind"] = BH.brain_health("wind", declared=g["brains"]["wind"]["rows"], declarations_known=True, executions=[ex("w1", "FAILED", 1, 0.9)],
                                                              observations={}, now=NOW)
    paths = BH.changed_paths(BH.health_state(brains2, g, SG.load(), NOW), st)
    assert set(paths) == {f"{BH.NODE}/brains", f"{BH.NODE}/summary"}


def test_vocabularies_match_the_publisher_without_importing_it():
    """The platform package must not import the Publisher (test_publisher_boundary); the words must still be the same words."""
    from sector_brain_platform.publisher.model import FRESHNESS_STATUSES, RECORD_STATUS
    from sector_brain_platform.enums import FRESHNESS_STATUS
    assert FRESHNESS_STATUS == FRESHNESS_STATUSES == DH.FRESHNESS_STATUS
    assert set(RECORD_STATUS.values()) <= set(BH.PUBLISH_STATUS)
    import ast
    for mod in (BH, DH, EH, DD, SG):
        tree = ast.parse(open(mod.__file__).read())
        assert not [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and "publisher" in (n.module or "")], mod.__name__


def test_conformance_fixture_mirrors_the_code_vocabularies():
    fx = json.load(open(os.path.join(ROOT, "contracts", "conformance", "health_v1.json")))
    assert fx["version"] == BH.HEALTH_MODEL_VERSION and fx["path"] == BH.NODE and tuple(fx["sections"]) == BH.SECTIONS
    for key, val in (("executionStatus", EH.EXECUTION_STATUS), ("processHealth", EH.PROCESS_HEALTH), ("cadenceStatus", EH.CADENCE_STATUS),
                     ("freshnessStatus", DH.FRESHNESS_STATUS), ("availability", DH.AVAILABILITY), ("dependencyStatus", DH.DEPENDENCY_STATUS),
                     ("freshnessAuthority", DH.FRESHNESS_AUTHORITY), ("evaluationBasis", DH.EVALUATION_BASIS), ("dependencyTypes", DD.DEPENDENCY_TYPES),
                     ("requirement", DD.REQUIREMENT), ("aggregate", BH.AGGREGATE), ("components", BH.COMPONENTS), ("publishStatus", BH.PUBLISH_STATUS),
                     ("domainValidation", BH.DOMAIN_VALIDATION), ("signalStatus", SG.SIGNAL_STATUS), ("consumedKeys", EH.CONSUMED_KEYS)):
        assert tuple(fx["vocabularies"][key]) == tuple(val), key
    assert fx["legacyExecutionStatus"] == EH.LEGACY_EXECUTION_STATUS and fx["cadenceGrace"] == EH.CADENCE_GRACE
    for c in fx["cases"]["executionStatus"]:
        assert EH.normalize_status(c["in"]) == c["out"], c
    for c in fx["cases"]["cadence"]:
        got = EH.cadence(c["lastSuccessAt"], dt.datetime.fromisoformat(c["now"].replace("Z", "+00:00")), c["expectedIntervalHours"])
        assert got["status"] == c["status"], c
    for c in fx["cases"]["dependency"]:
        d = dep(c["dependencyId"], c.get("dependencyType", "BRAIN"), c.get("requirement", "REQUIRED"))
        if c.get("requirement") is None and "requirement" in c:
            d.pop("requirement"); d["requirementDeclared"] = False
        got = DH.evaluate_dependency(d, c["observed"], dt.datetime.fromisoformat(c["now"].replace("Z", "+00:00")))
        assert (got["availability"], got["freshnessStatus"], got["dependencyStatus"]) == (c["availability"], c["freshnessStatus"], c["dependencyStatus"]), c
    for c in fx["cases"]["aggregate"]:
        assert BH.aggregate(c["process"], c["dependencies"], c["freshness"], c["publish"], c.get("cadence"))["status"] == c["status"], c
