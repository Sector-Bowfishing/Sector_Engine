"""The Ops control plane (docs/brains/OPS_CONTROL_PLANE_CONTRACT.md): everything Sector Ops needs to show
"which Brain is strong, weak, stale, blocked, what is active, what is a candidate, what to work on next" —
computed by Engine from published Brain facts, published by the platform writer under /control.

Ops renders this; it never computes scores, readiness, health roll-ups or stale classifications.
Pure functions; unknown stays absent.
"""
from __future__ import annotations

import datetime as dt

from .enums import READINESS_LADDER
from .keys import BRAINS
from .timeutil import age_hours, iso

CONTROL_VERSION = "control-plane-v1"
UPSTREAM = ("lake-brain", "water-temp", "water-clarity", "wind", "biological-state")
ALL_BRAINS = UPSTREAM + ("sector-intelligence",)
# SHADOW brains are visible in the control plane but take no part in any roll-up: not in worst-health, conformance counts,
# dependency completeness, the work-next list, per-lake stale/issue roll-ups, or the Engine score (scoring.py never sees them).
SHADOW_BRAINS = ("depth",)
SHADOW_SLOTS = ("depth",)


def _strip(d):
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            v = _strip(v)
            if v is None or v == {} or v == []:
                continue
            out[k] = v
        return out
    if isinstance(d, list):
        return [_strip(x) for x in d if x is not None]
    return d


def _count(records, key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in records:
        if isinstance(r, dict) and r.get(key):
            out[str(r[key])] = out.get(str(r[key]), 0) + 1
    return out


def brain_stale(registry: dict | None, health: dict | None, now: dt.datetime) -> tuple[bool | None, str | None]:
    """The Engine's TIME rule for a brain as a whole: last successful run older than its staleAfterHours.
    VERSION/FINGERPRINT brains are never stale by age. None = unknown (never run / no rule)."""
    if not registry:
        return None, "not registered"
    model = registry.get("stalenessModel")
    sa = registry.get("staleAfterHours")
    if model in ("VERSION", "FINGERPRINT") or (model is None and sa is None):
        return False, None
    last = registry.get("lastSuccessfulRun") or (health or {}).get("lastSuccess")
    age = age_hours(last, now)
    if age is None:
        return None, "no successful run recorded"
    if sa is None:
        return False, None
    return (age > float(sa)), (f"last successful run {age} h ago > {sa} h" if age > float(sa) else None)


def _active_model(reg: dict) -> dict | None:
    models = reg.get("models") or {}
    if isinstance(models, dict) and models.get("active"):
        return models["active"]
    am = reg.get("activeModel")
    if isinstance(am, dict):
        return _strip({"modelIds": am.get("modelIds"), "modelId": am.get("modelId"), "servedBy": am.get("servedBy")})
    for v in reg.get("versions") or []:
        if isinstance(v, dict) and v.get("status") == "CURRENT":
            return {"modelId": v.get("version"), "status": "PRODUCTION"}
    return None


def _candidate_model(reg: dict) -> dict | None:
    cm = reg.get("candidateModel")
    if isinstance(cm, dict) and cm:
        return _strip({"modelId": cm.get("modelId"), "status": cm.get("status") or cm.get("certificationStatus"),
                       "deploymentStatus": cm.get("deploymentStatus"), "researchScore": cm.get("researchScore")})
    rc = reg.get("researchCandidate")
    if isinstance(rc, dict) and rc:
        return _strip({"modelId": rc.get("modelId") or rc.get("candidate"), "status": rc.get("status"), "promoted": rc.get("promoted")})
    models = reg.get("models") or {}
    if isinstance(models, dict) and models.get("candidates"):
        c = models["candidates"][0]
        return _strip({"modelId": c.get("modelId"), "status": c.get("status")}) if isinstance(c, dict) else None
    return None


def brain_summary(brain_id: str, reg: dict | None, health: dict | None, validation: dict | None, score: dict | None,
                  jobs: dict | None, now: dt.datetime) -> dict:
    slot, _, display = BRAINS[brain_id]
    if not reg:
        return {"brainId": brain_id, "slot": slot, "displayName": display, "status": "NOT_REGISTERED", "health": "UNKNOWN", "stale": None}
    stale, why = brain_stale(reg, health, now)
    counts = reg.get("readinessCounts") or {}
    # `jobs` is /jobs (jobs-v1): a brain is scheduled when a job it owns runs on a schedule or by the orchestrator/dispatcher.
    owned = [j for j in (jobs or {}).values() if isinstance(j, dict) and (j.get("owner") == brain_id or j.get("brainId") == brain_id)]
    shadow = brain_id in SHADOW_BRAINS
    scheduled = any(j.get("executionMode") in ("SCHEDULED", "EVENT_DRIVEN") and j.get("brainPublishInJob") for j in owned) or \
        (not shadow and bool((reg.get("schedule") or {}).get("jobId")))        # a shadow Brain is scheduled only by a real owned job
    execution = sorted({(j.get("executionMode") or "UNKNOWN") for j in owned if j.get("brainPublishInJob")}) or None
    blockers = []
    for b in reg.get("blockers") or []:
        blockers.append(b if isinstance(b, str) else (b.get("why") or b.get("id") or str(b)))
    for b in (score or {}).get("scoreBlockers") or []:
        blockers.append((b.get("gate") or b.get("dimension") or "score") + ": " + str(b.get("why")))
    deps = reg.get("dependsOn") or (list((reg.get("dependencies") or {}).keys()) if brain_id == "sector-intelligence" else None)
    dep_status = {k: (v or {}).get("connectionStatus") for k, v in (reg.get("dependencies") or {}).items()} if brain_id == "sector-intelligence" else None
    shadow_fields = {}
    if shadow:
        # Explicit semantics: NO official score. RTDB cannot store null, so `officialScore` is simply absent and `scoreStatus` says why.
        shadow_fields = {"shadow": True, "scoreStatus": (score or {}).get("scoreStatus") or reg.get("scoreStatus") or ("ESTABLISHED" if (score or {}).get("value") is not None else "NOT_ESTABLISHED"),
                         "research": reg.get("research"), "fleet": reg.get("fleet"), "lakeDependency": reg.get("lakeDependency"),
                         "orchestration": reg.get("orchestration"), "fieldValidation": reg.get("fieldValidation"),
                         "primaryBlocker": reg.get("primaryBlocker"), "statusBasis": reg.get("statusBasis"), "contractVersion": reg.get("contractVersion"),
                         "breakdowns": reg.get("breakdowns"), "scope": reg.get("scope"),
                         "lifecycle": reg.get("lifecycle"), "claims": reg.get("claims"), "execution": reg.get("execution")}
    return _strip({**shadow_fields,
        "brainId": brain_id, "slot": slot, "displayName": reg.get("displayName") or display,
        "status": reg.get("status"), "health": (health or {}).get("status") or reg.get("health"),
        "healthAt": (health or {}).get("lastRun"), "lastSuccessfulRun": reg.get("lastSuccessfulRun"),
        "lastError": reg.get("lastError"), "stale": stale, "staleReason": why,
        "staleAfterHours": reg.get("staleAfterHours"), "stalenessModel": reg.get("stalenessModel"),
        "scheduled": scheduled, "executionModes": execution, "version": reg.get("version"),
        "score": _strip({k: (score or {}).get(k) for k in ("value", "scale", "basis", "scoreVersion", "completenessPct", "scoreUpdatedAt")}) or None,
        "nextOpportunity": (score or {}).get("nextScoreOpportunity"),
        "coverage": _strip({"directory": reg.get("directoryLakeCount"), "supported": reg.get("supportedLakeCount"),
                            "evaluated": reg.get("evaluatedLakeCount"), "stale": reg.get("staleLakeCount"),
                            "readinessCounts": counts,
                            "onLadder": sum(n for r, n in counts.items() if r in READINESS_LADDER) or None}),
        "activeModel": _active_model(reg), "candidateModel": _candidate_model(reg),
        "validation": _strip({"status": (validation or {}).get("status"), "ref": f"/validation/{brain_id}" if validation else None,
                              "modelVersion": (validation or {}).get("modelVersion")}),
        "blockers": blockers, "dependsOn": deps, "dependencyStatus": dep_status,
        "platform": _strip({"conformant": (reg.get("platform") or {}).get("conformant"),
                            "implementation": (reg.get("platform") or {}).get("implementation")}) or None,
    })


def fleet_rollup(lake_key: str, row: dict | None, now: dt.datetime) -> dict | None:
    """The Orchestrator-owned per-lake rollup (contract §5), published by Engine under /control/fleet."""
    if not row:
        return None
    slots = row.get("slots") or {}
    stamps, stale_any, evidence_any, issues, published = [], False, False, 0, 0
    for name, s in slots.items():
        if not isinstance(s, dict):
            continue
        published += 1
        if name in SHADOW_SLOTS:
            continue
        for k in ("generatedAt", "lastUpdatedAt"):
            if s.get(k):
                stamps.append(s[k])
        stale_any = stale_any or bool(s.get("stale"))
        evidence_any = evidence_any or bool(s.get("evidenceStale"))
        issues += int(s.get("issueCount") or 0)
    return _strip({"lakeId": row.get("lakeId"), "lastUpdatedAt": max(stamps) if stamps else None, "stale": stale_any if slots else None,
                   "evidenceStale": evidence_any if slots else None, "issueCount": issues if slots else None,
                   "slotsPublished": published, "readiness": row.get("readiness"), "riverSystem": row.get("riverSystem"),
                   "rolledUpAt": iso(now)})


def fleet_summary(fleet: dict, now: dt.datetime, directory_count: int | None = None) -> dict:
    """The compact fleet summary Ops reads instead of all /lakeFleet rows: counts per slot and readiness, stale /
    evidence-stale / issue totals, newest update. Published inside /control/overview.fleet (Phase 3, cost work 2026-10-13)."""
    readiness_by_slot: dict[str, dict[str, int]] = {}
    stale_slots: dict[str, int] = {}
    published_by_slot: dict[str, int] = {}
    evaluated = stale_lakes = evidence_stale_lakes = issues = with_slots = 0
    newest = None
    for row in fleet.values():
        row = row or {}
        for slot, r in (row.get("readiness") or {}).items():
            readiness_by_slot.setdefault(slot, {})
            readiness_by_slot[slot][r] = readiness_by_slot[slot].get(r, 0) + 1
        slots = row.get("slots") or {}
        any_stale = any_ev = False
        for slot, s in slots.items():
            if not isinstance(s, dict):
                continue
            published_by_slot[slot] = published_by_slot.get(slot, 0) + 1
            if slot in SHADOW_SLOTS:
                continue                                                  # visible, but a shadow slot never makes a lake stale or adds issues
            if s.get("stale"):
                stale_slots[slot] = stale_slots.get(slot, 0) + 1
                any_stale = True
            if s.get("evidenceStale"):
                any_ev = True
            issues += int(s.get("issueCount") or 0)
            for k in ("generatedAt", "lastUpdatedAt"):
                if s.get(k) and (newest is None or s[k] > newest):
                    newest = s[k]
            if slot == "intelligence" and s.get("kind") == "evaluated":
                evaluated += 1
        if slots:
            with_slots += 1
        stale_lakes += any_stale
        evidence_stale_lakes += any_ev
    return _strip({"lakes": len(fleet), "directoryLakes": directory_count, "withSlots": with_slots, "evaluatedByIntelligence": evaluated,
                   "staleLakes": stale_lakes, "evidenceStaleLakes": evidence_stale_lakes, "issueCount": issues,
                   "staleSlots": stale_slots, "publishedBySlot": published_by_slot, "readinessBySlot": readiness_by_slot,
                   "newestUpdateAt": newest, "summarizedAt": iso(now),
                   "note": "compact summary of /lakeFleet; per-lake detail stays in /control/fleet/{k}"})


def overview(*, brains: dict, health: dict, validation: dict, scores: dict, engine: dict | None, fleet: dict, sources: dict,
             health_sources: dict, jobs: dict, now: dt.datetime) -> dict:
    """The one node Ops reads for the command center."""
    summaries = {b: brain_summary(b, brains.get(b), health.get(b), validation.get(b), scores.get(b), jobs, now) for b in ALL_BRAINS}
    shadow = {b: brain_summary(b, brains.get(b), health.get(b), validation.get(b), None, jobs, now) for b in SHADOW_BRAINS if brains.get(b)}   # never scored
    fs = fleet_summary(fleet, now, (brains.get("lake-brain") or {}).get("directoryLakeCount"))
    src = {}
    for sid, rec in (sources or {}).items():
        rec = rec or {}
        hs = (health_sources or {}).get(sid) or {}
        thr = rec.get("staleThresholdHours")
        age = age_hours(rec.get("latestObservationAt") or rec.get("lastFetchAt"), now)
        src[sid] = _strip({"owner": rec.get("ownerBrainId"), "health": hs.get("status") or rec.get("health"),
                           "lastFetchAt": rec.get("lastFetchAt"), "latestObservationAt": rec.get("latestObservationAt"),
                           "stale": (age > float(thr)) if (thr is not None and age is not None) else None,
                           "failures24h": hs.get("failures24h", rec.get("failures24h"))})
    intel = brains.get("sector-intelligence") or {}
    deps = intel.get("dependencies") or {}
    consumed = [b for b in UPSTREAM if (deps.get(b) or {}).get("connectionStatus") in ("CONNECTED", "CONNECTED_DEGRADED")]
    eng = None
    if engine:
        eng = _strip({"score": engine.get("engineScore"), "scoreVersion": engine.get("engineScoreVersion"), "scale": engine.get("scale"),
                      "uncapped": engine.get("uncapped"), "completenessPct": engine.get("completenessPct"),
                      "breakdown": {k: {"value": v.get("value"), "status": v.get("status"), "weight": v.get("weight")} for k, v in (engine.get("dimensions") or {}).items()},
                      "blockers": engine.get("blockers"), "strongestArea": engine.get("strongestArea"), "weakestArea": engine.get("weakestArea"),
                      "updatedAt": engine.get("updatedAt")})
    worst = None
    order = ["FAILED", "DEGRADED", "WARNING", "UNKNOWN", "NOT_CONFIGURED", "HEALTHY"]
    hs_all = [summaries[b].get("health") for b in ALL_BRAINS]
    for h in order:
        if h in hs_all:
            worst = h
            break
    return _strip({
        "schemaVersion": 1, "version": CONTROL_VERSION, "updatedAt": iso(now),
        "engine": _strip({**(eng or {}), "serving": _strip({"revision": (intel.get("engineServing") or {}).get("revision"),
                                                          "lineageVerified": (intel.get("engineServing") or {}).get("lineageVerified")}),
                          "dependencyCompleteness": {"consumed": len(consumed), "total": len(UPSTREAM), "consumedByCustomerPath": 0,
                                                     "byBrain": {b: (deps.get(b) or {}).get("connectionStatus") for b in UPSTREAM}},
                          "worstBrainHealth": worst, "brainsConformant": sum(1 for b in ALL_BRAINS if (summaries[b].get("platform") or {}).get("conformant"))}),
        "brains": {**summaries, **shadow},
        "shadowBrains": sorted(shadow) or None,
        "fleet": fs,
        "jobs": _strip({"total": len(jobs or {}),
                        "byClassification": _count((jobs or {}).values(), "classification"),
                        "byExecutionMode": _count((jobs or {}).values(), "executionMode"),
                        "byRuntimeStatus": _count((jobs or {}).values(), "runtimeStatus"),
                        "warnings": sorted(f"{jid}: {w}" for jid, j in (jobs or {}).items() if isinstance(j, dict) for w in (j.get("warnings") or []))[:20],
                        "syncedAt": max((j.get("syncedAt") for j in (jobs or {}).values() if isinstance(j, dict) and j.get("syncedAt")), default=None)}),
        "sources": src,
        "workNext": [{"brainId": b, "score": summaries[b].get("score", {}).get("value") if summaries[b].get("score") else None,
                      "why": summaries[b].get("nextOpportunity")}
                     for b in sorted(ALL_BRAINS, key=lambda b: ((summaries[b].get("score") or {}).get("value") is None, (summaries[b].get("score") or {}).get("value", 99)))
                     if summaries[b].get("nextOpportunity")][:6],
    })
