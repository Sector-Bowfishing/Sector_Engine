"""Declared dependency discovery from brain.json (the one Brain-owned source), the Signal Registry, resolution against the registries,
legacy sources labelled as such, drift fail-closed, and the read model Ops consumes. Real repo + synthetic manifests."""
import copy
import json
import os

import pytest

from sector_brain_platform import dependency_declarations as DD, signals as SG, orchestration as O, JOB_MANIFEST

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def brain(bid, consumes=(), providers=(), publishes=(), authorized=None):
    b = {"brainId": bid, "consumes": list(consumes), "providers": list(providers), "publishes": list(publishes)}
    if authorized is not None:
        b["authorizedConsumers"] = authorized
    return b


def test_signal_registry_defines_signals_and_never_consumers():
    reg = SG.load()
    assert reg and all(s["status"] == "DECLARED" and "producer" not in s for s in reg.values())
    assert "consumers" not in json.dumps(list(reg.values()))                                              # consumers live in brain.json, never here
    assert SG.availability(reg, next(iter(reg))) == ("UNAVAILABLE", f"signal {next(iter(reg))!r} is DECLARED only (no producer registered)")
    assert SG.availability(reg, "no-such-signal")[0] == "UNAVAILABLE" and SG.availability(None, "x")[0] == "UNKNOWN"
    assert SG.validate_registry({"schemaVersion": "1.0.0", "signals": [{"signalId": "a", "status": "AVAILABLE"}]}) == ["a: AVAILABLE needs a producer"]
    assert SG.validate_registry({"schemaVersion": "1.0.0", "signals": [{"signalId": "a", "status": "DECLARED", "producer": {"kind": "brain", "id": "x"}}]})
    assert SG.validate_registry({"schemaVersion": "1.0.0", "signals": [{"signalId": "a", "status": "DECLARED"}, {"signalId": "a", "status": "DECLARED"}]}) == ["a: duplicate signalId"]
    assert SG.load("/nonexistent/signals.json") == {}
    with pytest.raises(SG.SignalRegistryError):
        SG.load(os.path.join(ROOT, "contracts", "conformance", "health.json"))
    s = SG.summary(reg)
    assert set(s) == set(reg) and all("description" not in v for v in s.values())


def test_wind_declares_its_own_dependencies_and_they_resolve():
    reg = DD.load_registered_brains(ROOT)
    assert "wind" in reg
    rows = DD.declared_dependencies(reg["wind"])
    types = {r["dependencyId"]: r["dependencyType"] for r in rows}
    assert types["registry:lakes"] == "PLATFORM_REGISTRY" and all(v == "PROVIDER_DATA" for k, v in types.items() if k.startswith("provider:"))
    assert next(r for r in rows if r["dependencyId"] == "registry:lakes")["requirement"] == "REQUIRED"
    assert all(not r["requirementDeclared"] for r in rows if r["dependencyType"] == "PROVIDER_DATA")       # undeclared stays undeclared
    res = DD.resolve(rows, brains=reg, signals=SG.load(), providers=DD.load_providers(ROOT))
    assert all(r["resolved"] for r in res), [r.get("resolutionIssue") for r in res]
    assert not [r for r in rows if r["dependencyType"] == "BRAIN"]                                         # Wind depends on no Brain, by its own declaration


def test_all_four_dependency_types_are_discovered_from_a_manifest():
    b = brain("alpha", consumes=[{"kind": "brain", "brainId": "beta", "contractId": "beta.state", "minVersion": "1.0.0", "requirement": "REQUIRED",
                                  "freshness": {"maxAgeHours": 6, "reason": "r"}},
                                 {"kind": "registry", "registry": "lakes", "contractId": "registry.lakes", "minVersion": "1.0.0"},
                                 {"kind": "signal", "signalId": "pressure-trend", "requirement": "OPTIONAL"}],
              providers=[{"providerId": "noaa-nbm-v5", "domainInterpreter": True}])
    rows = DD.declared_dependencies(b)
    assert [r["dependencyId"] for r in rows] == ["brain:beta", "signal:pressure-trend", "registry:lakes", "provider:noaa-nbm-v5"]
    assert {r["dependencyType"] for r in rows} == set(DD.DEPENDENCY_TYPES)
    beta = rows[0]
    assert beta["freshnessPolicy"] == {"maxAgeHours": 6.0, "reason": "r"} and beta["contractId"] == "beta.state" and beta["declaredIn"] == "brain.json#consumes[0]"
    assert rows[3]["domainInterpreter"] is True and rows[3]["declaredIn"] == "brain.json#providers[0]"
    with pytest.raises(DD.DeclarationError):
        DD.declared_dependencies(brain("a", consumes=[{"kind": "brain", "brainId": "x", "contractId": "c", "minVersion": "1.0.0"}] * 2))
    with pytest.raises(DD.DeclarationError):
        DD.declared_dependencies(brain("a", consumes=[{"kind": "brain", "brainId": "x", "requirement": "MAYBE"}]))
    with pytest.raises(DD.DeclarationError):
        DD.declared_dependencies(brain("a", consumes=[{"kind": "brain", "brainId": "x", "freshness": {"maxAgeHours": 2}}]))


def test_resolution_against_registries_fails_closed():
    beta = brain("beta", publishes=[{"contractId": "beta.state"}], authorized=["alpha"])
    alpha = brain("alpha", consumes=[{"kind": "brain", "brainId": "beta", "contractId": "beta.state", "minVersion": "1.0.0"},
                                     {"kind": "brain", "brainId": "ghost", "contractId": "g", "minVersion": "1.0.0"},
                                     {"kind": "signal", "signalId": "unicorn-index"},
                                     {"kind": "signal", "signalId": "pressure-trend"}],
                  providers=[{"providerId": "noaa-nbm-v5"}, {"providerId": "nobody"}])
    res = {r["dependencyId"]: r for r in DD.resolve(DD.declared_dependencies(alpha), brains={"alpha": alpha, "beta": beta}, signals=SG.load(), providers=DD.load_providers(ROOT))}
    assert res["brain:beta"]["resolved"] and res["signal:pressure-trend"]["resolved"]
    assert "unknown Brain" in res["brain:ghost"]["resolutionIssue"] and "not defined in the Signal Registry" in res["signal:unicorn-index"]["resolutionIssue"]
    assert "not registered" in res["provider:nobody"]["resolutionIssue"] and "authorizedConsumer" in res["provider:noaa-nbm-v5"]["resolutionIssue"]
    gamma = brain("gamma", consumes=[{"kind": "brain", "brainId": "beta", "contractId": "beta.state", "minVersion": "1.0.0"}])
    r = DD.resolve(DD.declared_dependencies(gamma), brains={"gamma": gamma, "beta": beta}, signals={}, providers={})[0]
    assert "authorizedConsumer" in r["resolutionIssue"]
    r = DD.resolve(DD.declared_dependencies(gamma), brains=None, signals=None, providers=None)[0]
    assert r["resolutionIssue"] == "brain registry not available"                                            # unavailable registry is an issue, not a pass


def test_legacy_manifest_rows_only_for_unregistered_brains_and_drift_fails_closed():
    m = O.load_manifest()
    reg = DD.load_registered_brains(ROOT)
    legacy = DD.legacy_rows_from_execution_manifest(m, reg)
    assert "wind" not in legacy and set(legacy) == set(m["brains"]) - set(reg)
    assert all(r["legacy"] and r["declaredIn"].startswith("control_manifest.json") for rows in legacy.values() for r in rows)
    assert DD.drift(reg, m, JOB_MANIFEST) == []                                                                # today: the platform claims nothing Wind does not declare
    m2 = copy.deepcopy(m); m2["brains"]["wind"]["dependencies"] = [{"id": "lake-brain", "requirement": "OPTIONAL", "onStale": "DEPENDENCY_STALE"}]
    d = DD.drift(reg, m2)
    assert d and "wind -> lake-brain" in d[0]
    jm = {"wind-hourly": {"owner": "wind", "brainDependencies": ["water-temp"]}}
    assert any("jobs.MANIFEST" in x and "wind -> water-temp" in x for x in DD.drift(reg, m, jm))


def test_dependency_graph_read_model_is_engine_owned_and_deterministic():
    reg = DD.load_registered_brains(ROOT)
    g = DD.dependency_graph(reg, manifest=O.load_manifest(), signals=SG.load(), providers=DD.load_providers(ROOT))
    assert g["version"] == DD.DECLARATIONS_VERSION and g["warnings"] == []
    assert g["brains"]["wind"]["source"] == "brain.json" and g["brains"]["wind"]["declarationsKnown"] is True
    registered = {"wind", "biological-state", "water-clarity",   # Wind (Phase 2), Fish and Water Clarity (Structural Certification V1) declare in brains/*/brain.json,
                  "sector-intelligence", "lake-brain", "water-temp"}   # as do Sector Intelligence, Lake and Water Temperature (Cortex architecture completion)
    others = [b for b in g["brains"] if b not in registered]
    assert others and all(g["brains"][b]["legacy"] for b in others)
    assert g["brains"]["biological-state"]["source"] == "brain.json" and g["brains"]["biological-state"]["declarationsKnown"] is True and g["brains"]["biological-state"]["rows"] == []
    assert g["brains"]["water-clarity"]["source"] == "brain.json" and g["brains"]["water-clarity"]["declarationsKnown"] is True
    assert all(e["to"] != "wind" for e in g["edges"] if e["dependencyType"] == "BRAIN")
    assert g["edges"] == sorted(g["edges"], key=lambda e: (e["to"], e["from"]))
    assert json.dumps(g, sort_keys=True) == json.dumps(DD.dependency_graph(reg, manifest=O.load_manifest(), signals=SG.load(), providers=DD.load_providers(ROOT)), sort_keys=True)
    m = {"engineMode": "PRE_PRODUCTION", "brains": {"nometa": {"displayName": "x"}}, "jobs": {}}
    g2 = DD.dependency_graph({}, manifest=m)
    assert g2["brains"]["nometa"]["declarationsKnown"] is False and any("unknown, not 'none'" in w for w in g2["warnings"])


def test_jobs_manifest_brain_dependencies_are_legacy_and_consistent_with_declarations():
    """OLD: jobs.MANIFEST[jid].brainDependencies (hand-maintained). NEW: brain.json consumes[kind=brain]. For every REGISTERED Brain the two must agree
    until the field is removed (removal gate: docs/brains/platform/ORCHESTRATOR_HEALTH_V1.md)."""
    reg = DD.load_registered_brains(ROOT)
    for jid, m in JOB_MANIFEST.items():
        if m.get("owner") in reg and m.get("brainDependencies") is not None:
            declared = sorted(r["target"] for r in DD.declared_dependencies(reg[m["owner"]]) if r["dependencyType"] == "BRAIN")
            assert sorted(m["brainDependencies"]) == declared, jid
