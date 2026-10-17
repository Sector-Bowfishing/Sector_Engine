"""DECLARED dependencies, discovered from the one Brain-owned source: `brains/<dir>/brain.json` (`consumes[]`, `providers[]`).

Generic by construction. This module contains no Brain id, no signal id and no provider id: every relationship is READ from a
registered manifest or a platform registry, never written in code. Ops/Canvas consumes the discovered graph; it keeps no table.

Dependency types (closed): BRAIN (another Brain's published contract), ENVIRONMENTAL_SIGNAL (Signal Registry), PROVIDER_DATA
(providers/PROVIDERS.json), PLATFORM_REGISTRY (lakes / species / brains registry contract).

Two sources still exist for Brains that have not migrated to a brain.json (legacy): the platform-authored execution manifest
(`control_manifest.json`, Brain -> Brain only). They are reported as `legacy: true` and retire per Brain at migration; `drift()`
fails closed when the platform manifest claims an edge a REGISTERED Brain does not declare.
"""
from __future__ import annotations

import json
import os

DECLARATIONS_VERSION = "dependency-declarations-v1"
DEPENDENCY_TYPES = ("BRAIN", "ENVIRONMENTAL_SIGNAL", "PROVIDER_DATA", "PLATFORM_REGISTRY")
REQUIREMENT = ("REQUIRED", "OPTIONAL")
_KIND_TO_TYPE = {"brain": "BRAIN", "registry": "PLATFORM_REGISTRY", "signal": "ENVIRONMENTAL_SIGNAL"}
_PKG = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.normpath(os.path.join(_PKG, "..", "..", ".."))


class DeclarationError(ValueError):
    pass


def dependency_id(dep_type: str, target: str) -> str:
    prefix = {"BRAIN": "brain", "ENVIRONMENTAL_SIGNAL": "signal", "PROVIDER_DATA": "provider", "PLATFORM_REGISTRY": "registry"}[dep_type]
    return f"{prefix}:{target}"


def _policy(entry: dict) -> dict:
    out = {}
    req = entry.get("requirement")
    out["requirementDeclared"] = req is not None
    if req is not None:
        if req not in REQUIREMENT:
            raise DeclarationError(f"requirement {req!r} not in {REQUIREMENT}")
        out["requirement"] = req
    fr = entry.get("freshness")
    if fr is not None:
        if fr.get("maxAgeHours") is None or not fr.get("reason"):
            raise DeclarationError("freshness needs maxAgeHours and reason")
        out["freshnessPolicy"] = {"maxAgeHours": float(fr["maxAgeHours"]), "reason": fr["reason"]}
    return out


def declared_dependencies(brain: dict) -> list[dict]:
    """The declared dependency rows of one brain.json, in deterministic order. Raises on a malformed declaration."""
    bid = brain.get("brainId")
    if not bid:
        raise DeclarationError("brain.json without brainId")
    rows = []
    for i, c in enumerate(brain.get("consumes") or []):
        kind = c.get("kind")
        t = _KIND_TO_TYPE.get(kind)
        if t is None:
            raise DeclarationError(f"{bid}: consumes[{i}] kind {kind!r} unknown")
        target = c.get("brainId") if kind == "brain" else c.get("registry") if kind == "registry" else c.get("signalId")
        if not target:
            raise DeclarationError(f"{bid}: consumes[{i}] has no target id")
        row = {"dependencyId": dependency_id(t, target), "dependencyType": t, "declaringBrain": bid, "target": target,
               "declaredIn": f"brain.json#consumes[{i}]", **_policy(c)}
        for k in ("contractId", "minVersion"):
            if c.get(k) is not None:
                row[k] = c[k]
        rows.append(row)
    for i, p in enumerate(brain.get("providers") or []):
        pid = p.get("providerId")
        if not pid:
            raise DeclarationError(f"{bid}: providers[{i}] has no providerId")
        row = {"dependencyId": dependency_id("PROVIDER_DATA", pid), "dependencyType": "PROVIDER_DATA", "declaringBrain": bid, "target": pid,
               "declaredIn": f"brain.json#providers[{i}]", **_policy(p)}
        if p.get("domainInterpreter") is not None:
            row["domainInterpreter"] = bool(p["domainInterpreter"])
        rows.append(row)
    ids = [r["dependencyId"] for r in rows]
    dup = sorted({d for d in ids if ids.count(d) > 1})
    if dup:
        raise DeclarationError(f"{bid}: dependency declared twice: {dup}")
    return sorted(rows, key=lambda r: (r["dependencyType"], r["dependencyId"]))


def resolve(rows: list[dict], *, brains: dict | None, signals: dict | None, providers: dict | None) -> list[dict]:
    """Attach `resolved` / `resolutionIssue` to each row against the registries. A registry passed as None is 'not available'
    (issue reported, nothing assumed). `brains`: {brainId: brain.json}; `signals`: signals.load(); `providers`: {providerId: entry}."""
    out = []
    for r in rows:
        r = dict(r)
        t, target, bid = r["dependencyType"], r["target"], r["declaringBrain"]
        issue = None
        if t == "BRAIN":
            if brains is None:
                issue = "brain registry not available"
            elif target not in brains:
                issue = f"consumes unknown Brain {target!r}"
            elif target == bid:
                issue = "a Brain cannot depend on itself"
            elif r.get("contractId") and not any(p.get("contractId") == r["contractId"] for p in brains[target].get("publishes") or []):
                issue = f"contract {r['contractId']!r} is not published by {target!r}"
            else:
                auth = brains[target].get("authorizedConsumers")
                if auth is not None and bid not in auth:
                    issue = f"{bid!r} is not an authorizedConsumer of {target!r}"
        elif t == "ENVIRONMENTAL_SIGNAL":
            if signals is None:
                issue = "signal registry not available"
            elif target not in signals:
                issue = f"signal {target!r} is not defined in the Signal Registry"
            elif signals[target].get("status") == "RETIRED":
                issue = f"signal {target!r} is RETIRED"
        elif t == "PROVIDER_DATA":
            if providers is None:
                issue = "provider catalog not available"
            elif target not in providers:
                issue = f"provider {target!r} not registered in providers/PROVIDERS.json"
            elif bid not in (providers[target].get("authorizedConsumers") or []):
                issue = f"{bid!r} is not an authorizedConsumer of provider {target!r}"
        elif t == "PLATFORM_REGISTRY":
            if target not in ("lakes", "species", "brains"):
                issue = f"unknown platform registry {target!r}"
        r["resolved"] = issue is None
        if issue:
            r["resolutionIssue"] = issue
        out.append(r)
    return out


# ------------------------------------------------------------------------------------------------------------ loaders (repo layout)
def load_registered_brains(root: str | None = None) -> dict[str, dict]:
    """{brainId: brain.json} for every brains/<dir>/brain.json (template and dot dirs excluded). Missing brains/ -> {}."""
    base = os.path.join(root or DEFAULT_ROOT, "brains")
    out: dict[str, dict] = {}
    if not os.path.isdir(base):
        return out
    for d in sorted(os.listdir(base)):
        if d.startswith(("_", ".")):
            continue
        p = os.path.join(base, d, "brain.json")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                b = json.load(fh)
            if b.get("brainId"):
                out[b["brainId"]] = b
    return out


def load_providers(root: str | None = None) -> dict[str, dict] | None:
    p = os.path.join(root or DEFAULT_ROOT, "providers", "PROVIDERS.json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        cat = json.load(fh)
    return {x["providerId"]: x for x in cat.get("providers") or [] if isinstance(x, dict) and x.get("providerId")}


# ------------------------------------------------------------------------------------------------------------ legacy sources
def legacy_rows_from_execution_manifest(manifest: dict, registered: dict) -> dict[str, list[dict]]:
    """Brain -> Brain rows for Brains WITHOUT a brain.json, read from the platform execution manifest. Labelled legacy; they retire
    when the Brain registers (its brain.json then becomes the only source)."""
    out: dict[str, list[dict]] = {}
    for bid, b in sorted((manifest.get("brains") or {}).items()):
        if bid in registered:
            continue
        rows = []
        if "dependencies" not in b:
            out[bid] = []
            continue
        for i, d in enumerate(b.get("dependencies") or []):
            row = {"dependencyId": dependency_id("BRAIN", d["id"]), "dependencyType": "BRAIN", "declaringBrain": bid, "target": d["id"],
                   "declaredIn": f"control_manifest.json#brains.{bid}.dependencies[{i}]", "legacy": True,
                   "requirementDeclared": d.get("requirement") in REQUIREMENT}
            if d.get("requirement") in REQUIREMENT:
                row["requirement"] = d["requirement"]
            if d.get("maxAgeHours") is not None:
                row["freshnessPolicy"] = {"maxAgeHours": float(d["maxAgeHours"]), "reason": "platform execution manifest tolerance (provisional)" if d.get("provisional") else "platform execution manifest tolerance"}
            rows.append(row)
        out[bid] = sorted(rows, key=lambda r: r["dependencyId"])
    return out


def drift(registered: dict, manifest: dict | None, job_manifest: dict | None = None) -> list[str]:
    """Edges the PLATFORM claims for a REGISTERED Brain that the Brain itself does not declare. Fail closed: the platform must not
    invent relationships. `manifest`: control_manifest.json; `job_manifest`: jobs.MANIFEST ({jobId: {owner, brainDependencies}})."""
    out = []
    declared = {bid: {r["target"] for r in declared_dependencies(b) if r["dependencyType"] == "BRAIN"} for bid, b in registered.items()}
    for bid, b in ((manifest or {}).get("brains") or {}).items():
        if bid not in declared:
            continue
        for d in b.get("dependencies") or []:
            if d.get("id") not in declared[bid]:
                out.append(f"control_manifest.json: {bid} -> {d.get('id')} is not declared in brains/*/brain.json (consumes kind=brain)")
    for jid, m in (job_manifest or {}).items():
        owner = m.get("owner")
        if owner not in declared:
            continue
        for dep in m.get("brainDependencies") or []:
            if dep not in declared[owner]:
                out.append(f"jobs.MANIFEST[{jid}].brainDependencies: {owner} -> {dep} is not declared in brains/*/brain.json")
    return out


# ------------------------------------------------------------------------------------------------------------ read model
def dependency_graph(registered: dict, *, manifest: dict | None = None, signals: dict | None = None, providers: dict | None = None) -> dict:
    """The Engine-owned declared graph Ops/Canvas renders: {version, brains{id: {source, rows[]}}, edges[], warnings[]}.
    Registered Brains come from brain.json only; unregistered Brains known to the execution manifest are legacy rows."""
    brains_out, edges, warnings = {}, [], []
    for bid in sorted(registered):
        rows = resolve(declared_dependencies(registered[bid]), brains=registered, signals=signals, providers=providers)
        brains_out[bid] = {"source": "brain.json", "declarationsKnown": True, "rows": rows}
        warnings += [f"{bid}: {r['dependencyId']}: {r['resolutionIssue']}" for r in rows if not r["resolved"]]
    for bid, rows in legacy_rows_from_execution_manifest(manifest or {}, registered).items():
        known = "dependencies" in ((manifest or {}).get("brains") or {}).get(bid, {})
        brains_out[bid] = {"source": "control_manifest.json (legacy, platform-authored)", "declarationsKnown": known, "legacy": True, "rows": rows}
        if not known:
            warnings.append(f"{bid}: no dependency metadata declared anywhere (unknown, not 'none')")
    for bid, b in brains_out.items():
        for r in b["rows"]:
            e = {"from": r["dependencyId"], "to": bid, "dependencyType": r["dependencyType"]}
            if r.get("requirement"):
                e["requirement"] = r["requirement"]
            if r.get("legacy"):
                e["legacy"] = True
            edges.append(e)
    for w in drift(registered, manifest):
        warnings.append("DRIFT " + w)
    return {"version": DECLARATIONS_VERSION, "brains": brains_out, "edges": sorted(edges, key=lambda e: (e["to"], e["from"])), "warnings": warnings}
