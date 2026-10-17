"""brain-health-v1 — the Engine-owned health READ MODEL Ops/Canvas consumes (published under `control/healthV1/*`).

Five health concepts, kept distinct and published side by side (never collapsed into one boolean):
  process          did the job execute (execution_health.py, G1)
  dependencies     were the declared dependencies available / satisfied (dependency_health.py, G2)
  freshness        was the evidence behind the REQUIRED dependencies current (dependency_health.py, G2)
  domainValidation does the Brain trust its scientific result (passed through verbatim from the Brain; never computed here)
  publish          did the Publisher accept / publish the artifact (passed through; UNKNOWN until the Publisher is wired)
plus an OPERATIONAL aggregate (process + dependencies + freshness + publish) for presentation. Domain validation is shown beside the
aggregate and never folded into it: scientific trust is not operational health. UNKNOWN components stay listed as unknown.

Pure builders. Ops renders; it computes none of this. No Brain id appears in this module: relationships come from
dependency_declarations (brain.json), the Signal Registry and runtime lineage.
"""
from __future__ import annotations

import datetime as dt

from . import dependency_declarations as DD, dependency_health as DH, execution_health as EH, signals as SG
from .model_v1 import VALIDATION_STATUS
from .timeutil import iso

HEALTH_MODEL_VERSION = "brain-health-v1"
NODE = "control/healthV1"
SECTIONS = ("summary", "brains", "dependencies", "signals")
COMPONENTS = ("process", "dependencies", "freshness", "publish")             # the operational aggregate's inputs
DOMAIN_VALIDATION = VALIDATION_STATUS + ("UNKNOWN",)                         # model v1 words, passed through
# Publisher publication-record words (publisher.model.RECORD_STATUS values, tested equal; the platform never imports the Publisher) + PUBLISHED (future) + NOT_APPLICABLE
PUBLISH_STATUS = ("REJECTED", "SHADOW", "SKIPPED_UNCHANGED", "PUBLISHED", "NOT_APPLICABLE", "UNKNOWN")
AGGREGATE = ("HEALTHY", "WARNING", "DEGRADED", "FAILED", "UNKNOWN")
VOLATILE = ("evaluatedAt", "asOf", "lastSuccessAgeHours", "ageHoursAtConsumption")   # move every evaluation; the verdict words carry the decision
_SEV = {"HEALTHY": 0, "WARNING": 1, "DEGRADED": 2, "FAILED": 3}
_PROCESS = {"HEALTHY": "HEALTHY", "WARNING": "WARNING", "DEGRADED": "DEGRADED", "FAILED": "FAILED"}
_DEPS = {"SATISFIED": "HEALTHY", "DEGRADED": "DEGRADED", "UNSATISFIED": "FAILED"}
_FRESH = {"FRESH": "HEALTHY", "STALE": "DEGRADED", "UNAVAILABLE": "DEGRADED", "EXPIRED": "FAILED"}
_PUBLISH = {"PUBLISHED": "HEALTHY", "SHADOW": "HEALTHY", "SKIPPED_UNCHANGED": "HEALTHY", "NOT_APPLICABLE": "HEALTHY", "REJECTED": "FAILED"}


def _strip(o):
    if isinstance(o, dict):
        return {k: v2 for k, v in o.items() if (v2 := _strip(v)) not in (None, {}, [])}
    if isinstance(o, list):
        return [x for x in (_strip(v) for v in o) if x not in (None, {}, [])]
    return o


def _key(s: str) -> str:
    import re
    return re.sub(r"[.$#\[\]/\x00-\x1f\x7f|]", "_", str(s))


def domain_validation(registry: dict | None, validation: dict | None = None) -> dict:
    """Pass-through of the Brain's own validation verdict (registry `validationStatus` or /validation/{id}.status); UNKNOWN otherwise."""
    for src, obj in (("registry.validationStatus", registry), ("validation.status", validation)):
        v = (obj or {}).get("validationStatus") if src.startswith("registry") else (obj or {}).get("status")
        if v in VALIDATION_STATUS:
            return {"status": v, "source": src}
        if v is not None:
            return {"status": "UNKNOWN", "source": src, "reason": f"value {v!r} is not in the validation vocabulary"}
    return {"status": "UNKNOWN", "source": "none", "reason": "the Brain publishes no validation verdict"}


def publish_health(publication: dict | None) -> dict:
    """Pass-through of the newest Publisher publication record for the Brain ({status, publishedAt?, executionId?}); UNKNOWN when none."""
    if not publication:
        return {"status": "UNKNOWN", "reason": "no Publisher publication record (Publisher not wired for this Brain)"}
    st = publication.get("status")
    if st not in PUBLISH_STATUS:
        return {"status": "UNKNOWN", "reason": f"publication status {st!r} not in the vocabulary"}
    out = {"status": st}
    for k in ("publishedAt", "executionId", "artifactId", "codeVersion"):
        if publication.get(k) is not None:
            out[k] = publication[k]
    return out


def aggregate(process: str, deps: str, fresh: str, publish: str, cadence_status: str | None = None) -> dict:
    """Operational aggregate = worst KNOWN component, with one floor: an UNKNOWN process makes the aggregate UNKNOWN (nothing is
    operationally healthy while nobody knows whether it ran). Unknown components are always listed; never silently green or red.
    NOT_CONFIGURED process = no runtime: excluded (listed as notConfigured). Domain validation is deliberately not an input."""
    known, unknown = {}, []
    for name, word, table in (("process", process, _PROCESS), ("dependencies", deps, _DEPS), ("freshness", fresh, _FRESH), ("publish", publish, _PUBLISH)):
        if word in table:
            known[name] = table[word]
        else:
            unknown.append(name)
    if cadence_status == "OVERDUE" and known.get("process") == "HEALTHY":
        known["process"] = "WARNING"
    out = {"inputs": {"process": process, "dependencies": deps, "freshness": fresh, "publish": publish}}
    if not known:
        out.update(status="UNKNOWN", reason="no component is known")
    elif process == "UNKNOWN":
        out.update(status="UNKNOWN", reason="process health unknown: an execution outcome is the floor of operational health")
    else:
        worst = max(known.items(), key=lambda kv: _SEV[kv[1]])
        out.update(status=worst[1], worstComponent=worst[0])
    if unknown:
        out["unknownComponents"] = unknown
    if process == "NOT_CONFIGURED":
        out["notConfigured"] = True
    return out


def brain_health(brain_id: str, *, declared: list[dict], declarations_known: bool, executions: list[dict] | None, observations: dict,
                 now: dt.datetime, expected_interval_hours: float | None = None, brain_health_record: dict | None = None,
                 registry: dict | None = None, validation: dict | None = None, publication: dict | None = None,
                 runtime_configured: bool = True, code_version: str | None = None) -> dict:
    """The full record for one Brain. Dependencies are judged at the last execution's RECORDED consumption when it exists (declared vs
    actual), otherwise against the current observations (and the record says so)."""
    ex = EH.execution_summary(brain_id, executions, now, expected_interval_hours=expected_interval_hours, brain_health=brain_health_record,
                              runtime_configured=runtime_configured, code_version=code_version)
    last = None
    if executions:
        norm = sorted((EH.normalize_execution(e) for e in executions if isinstance(e, dict)), key=lambda e: (e.get("startedAt") or "", e.get("executionId") or ""), reverse=True)
        last = norm[0] if norm else None
    rows = DH.evaluate_all(declared, observations, now, last) if declarations_known else []
    dep = DH.aggregate(rows, declarations_known)
    recon = DH.reconcile_consumption(declared, last)
    dv = domain_validation(registry, validation)
    pub = publish_health(publication)
    agg = aggregate(ex["processHealth"], dep["dependencyHealth"], dep["freshnessHealth"], pub["status"], ex["cadence"]["status"])
    return _strip({
        "healthModel": HEALTH_MODEL_VERSION, "brainId": brain_id, "asOf": iso(now),
        "process": ex,
        "dependencies": {**dep, "rows": rows, "declaredVsActual": recon,
                         "basis": "RECORDED_CONSUMPTION" if recon["consumptionRecorded"] else "CURRENT_STATE"},
        "freshness": {"status": dep["freshnessHealth"], "basis": dep.get("freshnessBasis"),
                      "note": "evidence freshness of the REQUIRED dependencies; independent of process.lastSuccessfulAt"},
        "domainValidation": dv, "publish": pub, "aggregate": agg,
    })


def health_state(brains: dict[str, dict], graph: dict, signals_registry: dict | None, now: dt.datetime, *, engine_mode: str | None = None) -> dict:
    """The whole `control/healthV1` node: summary, brains/{id}, dependencies (the declared graph), signals (definitions)."""
    counts: dict[str, int] = {}
    for b in brains.values():
        s = b["aggregate"]["status"]
        counts[s] = counts.get(s, 0) + 1
    summary = {"version": HEALTH_MODEL_VERSION, "asOf": iso(now), "engineMode": engine_mode, "brainCount": len(brains),
               "aggregateCounts": dict(sorted(counts.items())),
               "unknownDeclarations": sorted(bid for bid, g in graph["brains"].items() if not g.get("declarationsKnown")),
               "graphWarnings": graph.get("warnings") or [],
               "note": "five health concepts published separately per Brain: process, dependencies, freshness, domainValidation, publish; "
                       "aggregate is operational only (domain validation is never folded in); UNKNOWN is a value, render it as a dash"}
    state = {"summary": summary, "brains": {_key(b): v for b, v in sorted(brains.items())},
             "dependencies": {"version": graph["version"], "brains": {_key(b): g for b, g in sorted(graph["brains"].items())},
                              "edges": graph["edges"], "warnings": graph.get("warnings") or []},
             "signals": SG.summary(signals_registry) if signals_registry is not None else {"note": "signal registry not available at runtime"}}
    return _strip(state)


def _stable(v):
    if isinstance(v, dict):
        return {k: _stable(x) for k, x in v.items() if k not in VOLATILE}
    if isinstance(v, list):
        return [_stable(x) for x in v]
    return v


def changed_paths(state: dict, published: dict | None) -> dict:
    """RTDB multi-path update of the sections whose content changed (evaluation timestamps ignored), plus the summary whenever anything did."""
    published = published or {}
    out = {f"{NODE}/{s}": state[s] for s in SECTIONS if s in state and _stable(state[s]) != _stable(published.get(s))}
    for s in SECTIONS:
        if s not in state and s in published:
            out[f"{NODE}/{s}"] = None
    if out and "summary" in state:
        out[f"{NODE}/summary"] = state["summary"]
    return out
