"""Sector Intelligence Brain (brainId `sector-intelligence`): registry, dependency and per-lake input publisher.

Sector Intelligence is the synthesis layer above the specialised brains. Today no normalized Intelligence
evaluation exists: customers get the Engine Conditions Score from GET /conditions, which fetches and computes
every signal itself and reads no Brain. This module publishes that reality, and nothing more:

  * /brains/sector-intelligence             registry: lifecycle, implementations, dependencies, blockers, versions
  * /health/brains/sector-intelligence      publisher runtime health, kept apart from dependency health
  * /validation/sector-intelligence         NOT_VALIDATED, with the software-test evidence that does exist
  * /lakes/{k}/states/intelligence          per lake: NOT_EVALUATED + which upstream brain states are published
  * /lakeFleet/{k}/slots/intelligence       fleet summary of the same

It never evaluates a lake, never writes the snapshot field `sectorIntelligence`, never writes a readiness it cannot
justify, and never marks a dependency CONNECTED unless an implementation actually reads that brain.
Pure functions only; run.py does the I/O.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re

import brain_platform as bp

BRAIN_ID = "sector-intelligence"
SLOT = "intelligence"
BRAIN_VERSION = "sector-intelligence-brain-0.1.0"
DISPLAY_NAME = "Sector Intelligence"
QUESTION = "What does everything Sector knows mean for the bowfisher?"

DEPENDENCY_ORDER = ["lake-brain", "water-temp", "water-clarity", "wind", "biological-state"]

# Engine-owned vocabularies (Ops shows any value verbatim and colours the ones it knows).
VOCABULARIES = {
    "connectionStatus": ["CONNECTED", "CONNECTED_DEGRADED", "AVAILABLE_NOT_CONSUMED", "NOT_CONNECTED"],
    "publishingStatus": ["PUBLISHING", "VERSION_DRIVEN", "STALE", "NOT_REGISTERED"],
    "evaluationStatus": ["EVALUATED", "NOT_EVALUATED"],
    "implementationLifecycle": ["PRODUCTION", "MERGED_UNRELEASED", "UNMERGED", "NOT_STARTED"],
    "inputStatus": ["PUBLISHED", "STALE", "NOT_PUBLISHED"],
}


class CatalogError(ValueError):
    pass


# ------------------------------------------------------------------ catalog
def load_catalog(raw: bytes) -> dict:
    cat = json.loads(raw)
    for key in ("catalogVersion", "codeLineage", "implementations", "activeImplementation", "dependencies", "validation"):
        if key not in cat:
            raise CatalogError(f"catalog missing {key!r}")
    ids = [m["modelId"] for m in cat["implementations"]]
    if cat["activeImplementation"] not in ids:
        raise CatalogError("activeImplementation is not an implementation")
    if set(cat["dependencies"]) != set(DEPENDENCY_ORDER):
        raise CatalogError(f"dependencies must be exactly {DEPENDENCY_ORDER}")
    for m in cat["implementations"]:
        unknown = set(m.get("readsBrains", [])) - set(DEPENDENCY_ORDER)
        if unknown:
            raise CatalogError(f"{m['modelId']} reads unknown brains {sorted(unknown)}")
    return cat


def catalog_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def consumers_of(cat: dict, brain_id: str) -> list[str]:
    """Implementations that actually read this brain (declared in catalog.readsBrains, reviewed)."""
    return [m["modelId"] for m in cat["implementations"] if brain_id in m.get("readsBrains", [])]


# ------------------------------------------------------------------ engine serving revision
def engine_serving(service: dict | None, lineage: dict, checked_at: dt.datetime) -> dict:
    """Cloud Run service document -> what serves customers now, and whether it is the declared code lineage."""
    out = {"service": lineage["service"], "codeLineageTag": lineage["tag"], "codeLineageCommit": lineage["commit"],
           "checkedAt": bp.iso(checked_at)}
    if not service:
        return out | {"status": "UNKNOWN", "lineageVerified": False, "reason": "Cloud Run service could not be read"}
    serving = [t for t in service.get("trafficStatuses", []) if (t.get("percent") or 0) > 0]
    serving.sort(key=lambda t: -(t.get("percent") or 0))
    image = ((service.get("template") or {}).get("containers") or [{}])[0].get("image", "")
    digest = image.split("@", 1)[1] if "@" in image else None
    if not serving:
        return out | {"status": "UNKNOWN", "lineageVerified": False, "reason": "no revision receives traffic"}
    top = serving[0]
    rev = top.get("revision") or (service.get("latestReadyRevision") or "").rsplit("/", 1)[-1]
    verified = digest is not None and digest == lineage.get("imageDigest")
    return out | {"status": "SERVING", "revision": rev, "trafficPercent": top.get("percent"),
                  "imageDigest": digest, "lineageVerified": verified,
                  **({} if verified else {"reason": "serving image differs from the declared code lineage; review catalog.json"})}


# ------------------------------------------------------------------ dependencies
PILOT_IMPLEMENTATION = "normalized-sector-intelligence"


def dependency_status(brain_id: str, decl: dict, registry: dict | None, health: dict | None,
                      validation_status: str | None, cat: dict, now: dt.datetime,
                      pilot_ran: bool = False, used_in_last_evaluation: bool = False, last_evaluation_at: str | None = None) -> dict:
    """One upstream brain, with 'exists', 'publishing', 'consumed' and 'used' kept separate.

    CONNECTED means an Intelligence implementation that actually ran consumes this brain. The customer
    path (the active implementation) and the pilot evaluation are reported separately so a pilot never
    reads as customer consumption."""
    consumers = consumers_of(cat, brain_id)
    active_reads = cat["activeImplementation"] in consumers
    pilot_reads = pilot_ran and PILOT_IMPLEMENTATION in consumers
    d = {"brainId": brain_id, "slot": decl["slot"], "displayName": decl["displayName"],
         "plannedRole": decl["plannedRole"], "plannedInputs": decl.get("plannedInputs", []),
         "customerPathToday": decl.get("customerPathToday"),
         "exists": registry is not None, "consumedBySectorIntelligence": active_reads or pilot_reads,
         "consumedByCustomerPath": active_reads, "consumedByPilotEvaluation": pilot_reads,
         "consumedBy": consumers, "usedInLastEvaluation": used_in_last_evaluation, "lastEvaluationAt": last_evaluation_at}
    if registry is None:
        d.update(publishingStatus="NOT_REGISTERED", connectionStatus="NOT_CONNECTED",
                 missingReason=f"/brains/{brain_id} is not registered; no publisher writes this brain yet")
        return _strip(d)

    last = registry.get("lastSuccessfulRun") or (health or {}).get("lastSuccess")
    age = bp.age_hours(last, now)
    stale_after = registry.get("staleAfterHours")
    if stale_after is None:
        publishing = "VERSION_DRIVEN"          # e.g. species knowledge: stale by version, never by age
    elif age is None or age > float(stale_after):
        publishing = "STALE"
    else:
        publishing = "PUBLISHING"
    hstat = (health or {}).get("status") or registry.get("health") or "UNKNOWN"
    degraded = []
    if publishing == "STALE":
        degraded.append(f"last successful run {age} h ago exceeds the brain's staleAfterHours {stale_after}"
                        if age is not None else "no successful run recorded")
    if hstat != "HEALTHY":
        degraded.append(f"brain health {hstat}")

    if active_reads or pilot_reads:
        connection = "CONNECTED_DEGRADED" if degraded else "CONNECTED"
    else:
        connection = "AVAILABLE_NOT_CONSUMED"
    d.update(publishingStatus=publishing, connectionStatus=connection, lifecycle=registry.get("status"),
             health=hstat, version=registry.get("version"), lastUpdatedAt=last, ageHours=age,
             staleAfterHours=stale_after, supportedLakeCount=registry.get("supportedLakeCount"),
             validationStatus=validation_status, deploymentVersion=registry.get("deploymentVersion"))
    if degraded:
        d["degradedReason"] = "; ".join(degraded)
    if not (active_reads or pilot_reads):
        d["notConsumedReason"] = "No Intelligence implementation has run that reads this brain yet"
    elif not active_reads:
        d["customerPathNote"] = "Consumed by the pilot evaluation only; the customer path does not read this brain"
    comps = _components(brain_id, registry)
    if comps:
        d["components"] = comps
    return _strip(d)


def _components(brain_id: str, registry: dict) -> dict | None:
    """Brain-published sub-capabilities that matter to Intelligence (read verbatim, never inferred)."""
    if brain_id == "biological-state":
        resp = registry.get("responsibilities") or {}
        return {k: {"status": v.get("status"), **({"note": v["note"]} if v.get("note") else {})}
                for k, v in resp.items() if isinstance(v, dict)} or None
    if brain_id == "water-clarity":
        out = {}
        if registry.get("activeModel"):
            out["activeModel"] = {"status": "SERVING", "modelIds": registry["activeModel"].get("modelIds")}
        cand = registry.get("candidateModel")
        if cand:
            out["candidateModel"] = {"status": cand.get("certificationStatus") or cand.get("lifecycle"),
                                     "modelId": cand.get("modelId"), "deploymentStatus": cand.get("deploymentStatus")}
        return out or None
    if brain_id in ("water-temp", "wind"):
        apm = registry.get("activeProductionModel")
        rc = registry.get("researchCandidate")
        out = {}
        if isinstance(apm, dict):
            out["activeProductionModel"] = {"status": apm.get("status") or "SERVING",
                                            "modelId": apm.get("modelId") or apm.get("modelVersion")}
        if isinstance(rc, dict):
            out["researchCandidate"] = {"status": rc.get("status"), "modelId": rc.get("modelId") or rc.get("name")}
        return {k: _strip(v) for k, v in out.items()} or None
    return None


def dependency_summary(deps: dict) -> dict:
    vals = list(deps.values())
    return {
        "total": len(vals),
        "required": sum(1 for d in vals if d["plannedRole"] == "REQUIRED"),
        "registered": sum(1 for d in vals if d["exists"]),
        "connected": sum(1 for d in vals if d["connectionStatus"] in ("CONNECTED", "CONNECTED_DEGRADED")),
        "availableNotConsumed": sum(1 for d in vals if d["connectionStatus"] == "AVAILABLE_NOT_CONSUMED"),
        "notConnected": sum(1 for d in vals if d["connectionStatus"] == "NOT_CONNECTED"),
        "stale": sum(1 for d in vals if d.get("publishingStatus") == "STALE"),
        "unhealthy": sum(1 for d in vals if d["exists"] and d.get("health") != "HEALTHY"),
        "degradedInputs": sum(1 for d in vals if d["connectionStatus"] == "CONNECTED_DEGRADED"),
    }


PILOT_RESOLVED_BLOCKERS = ("NO_NORMALIZED_EVALUATION", "NO_BRAIN_CONSUMED")


def derived_blockers(deps: dict, serving: dict) -> list[dict]:
    out = []
    for bid in DEPENDENCY_ORDER:
        d = deps[bid]
        if not d["exists"]:
            out.append({"id": f"DEPENDENCY_NOT_REGISTERED:{bid}", "severity": "warning", "brainId": bid,
                        "title": f"{d['displayName']} is not registered in the Brain RTDB"})
        elif d.get("publishingStatus") == "STALE":
            out.append({"id": f"DEPENDENCY_STALE:{bid}", "severity": "info", "brainId": bid,
                        "title": f"{d['displayName']} state is stale ({d.get('degradedReason')})"})
    if serving.get("status") == "SERVING" and not serving.get("lineageVerified"):
        out.append({"id": "ENGINE_LINEAGE_UNVERIFIED", "severity": "warning",
                    "title": "The serving Engine image differs from the declared code lineage; catalog.json needs review"})
    return out


# ------------------------------------------------------------------ per lake
def lake_inputs(fleet_row: dict | None, deps: dict, now: dt.datetime) -> dict:
    """Which upstream brain states are published for one lake, judged with each brain's own staleness rule.

    Keyed by slot. Brain id, brain version and 'consumed' are lake-independent and live on the registry's
    dependencies map; only lake-specific facts are stored here to keep the per-lake node small."""
    row = fleet_row or {}
    slots = row.get("slots") or {}
    readiness = row.get("readiness") or {}
    versions = row.get("modelVersions") or {}
    out = {}
    for bid in DEPENDENCY_ORDER:
        d = deps[bid]
        slot = d["slot"]
        if bid == "biological-state":
            # Species knowledge is lake-independent; per-lake Biological State is a separate, unstarted product.
            comps = d.get("components") or {}
            out[slot] = _strip({"status": "NOT_PUBLISHED",
                                "speciesKnowledge": (comps.get("speciesKnowledge") or {}).get("status"),
                                "biologicalState": (comps.get("biologicalState") or {}).get("status")})
            continue
        s = slots.get(slot) or {}
        r = readiness.get(slot) or s.get("readiness")
        last = s.get("lastUpdatedAt")
        if not s and not r:
            out[slot] = {"status": "NOT_PUBLISHED"}
            continue
        age = bp.age_hours(last, now)
        sa = d.get("staleAfterHours")
        stale = bool(s.get("stale")) or (sa is not None and (age is None or age > float(sa)))
        out[slot] = _strip({"status": "STALE" if stale else "PUBLISHED", "readiness": r,
                            "stateType": s.get("stateType"), "lastUpdatedAt": last,
                            "modelVersion": versions.get(slot)})
    return out


# The shared Brain Platform this brain publishes through (docs/brains/BRAIN_PLATFORM_CONTRACT.md §13; Engine Score reads it).
PLATFORM = {"implementation": "sector_brain_platform", "contract": "docs/brains/BRAIN_PLATFORM_CONTRACT.md v1.0", "conformant": True}


def lake_state(lake_id: str, inputs: dict, cat: dict, serving: dict, now: dt.datetime) -> dict:
    published = sum(1 for v in inputs.values() if v["status"] == "PUBLISHED")
    stale = sum(1 for v in inputs.values() if v["status"] == "STALE")
    return _strip({
        "lakeId": lake_id,
        "kind": "not_evaluated",                       # Brain Platform contract §3 state kind
        "evaluationStatus": "NOT_EVALUATED",
        "customerPath": {"implementation": cat["activeImplementation"], "engineRevision": serving.get("revision")},
        "inputs": inputs,
        "inputCounts": {"total": len(inputs), "published": published, "stale": stale,
                        "notPublished": len(inputs) - published - stale, "consumed": 0},
        "generatedAt": bp.iso(now),
        "provenance": {"brainId": BRAIN_ID, "brainVersion": BRAIN_VERSION, "processingVersion": serving.get("revision"),
                       "generatedAt": bp.iso(now), "qualityFlags": ["NO_EVALUATION"]},
    })


# ------------------------------------------------------------------ registry / health / validation
def versions_list(cat: dict, serving: dict, today: str) -> list[dict]:
    lin = cat["codeLineage"]
    rows = []
    for m in cat["implementations"]:
        mid = m["modelId"]
        if mid == "engine-conditions-score":
            rev = serving.get("revision")
            note = (f"Serving customers on {rev} ({'image matches' if serving.get('lineageVerified') else 'image NOT verified against'} {lin['tag']})"
                    if rev else f"Code lineage {lin['tag']}; serving revision unknown")
            rows.append({"version": f"{mid} @ {lin['tag']}", "status": "CURRENT", "lifecycle": m["lifecycle"], "note": note})
        elif mid == "ios-fishintel":
            mv = m.get("modelVersions", {})
            rows.append({"version": f"{mv.get('intelligence', mid)} (iOS FishIntel)", "date": "2026-09-28",
                         "status": m["lifecycle"], "lifecycle": m["lifecycle"], "note": "Merged to iOS Michael-Master; in no release"})
        elif mid == "phase5a-guardrails":
            rows.append({"version": mid, "date": "2026-10-09", "status": m["lifecycle"], "lifecycle": m["lifecycle"],
                         "note": "Branches only; not merged or deployed"})
        else:
            rows.append({"version": mid, "status": m["lifecycle"], "lifecycle": m["lifecycle"], "note": m.get("note")})
    rows.append({"version": BRAIN_VERSION, "date": today, "status": "METADATA_PUBLISHER", "lifecycle": "METADATA_PUBLISHER",
                 "note": "This publisher: registry, dependencies and per-lake input availability; evaluates nothing"})
    return [_strip(r) for r in rows]


def roster(cat: dict, serving: dict) -> list[dict]:
    out = []
    for m in cat["implementations"]:
        r = {k: m[k] for k in ("modelId", "lifecycle", "deploymentStatus", "certificationStatus", "servesCustomers",
                               "publishesLakeState", "coverage", "method", "runsIn") if k in m}
        if m.get("codeRef"):
            r["codeRef"] = dict(m["codeRef"])
            if m["modelId"] == cat["activeImplementation"] and serving.get("revision"):
                r["codeRef"]["deployedRevision"] = serving["revision"]
        out.append(r)
    return out


def fingerprint(cat_sha: str, serving: dict, deps: dict, inputs_fp: str | None = None) -> str:
    """What, if it changes, warrants a republish (used by orchestration.plan)."""
    dep_view = {k: [v["exists"], v.get("publishingStatus"), v.get("health"), v.get("version"), v.get("lifecycle"),
                    v["connectionStatus"]] for k, v in sorted(deps.items())}
    blob = json.dumps([BRAIN_VERSION, cat_sha, serving.get("revision"), serving.get("imageDigest"),
                       serving.get("lineageVerified"), dep_view, inputs_fp], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def build_updates(*, cat: dict, cat_sha: str, lakes: list[str], fleet: dict, upstream: dict, serving: dict,
                  now: dt.datetime, deployment: str, descriptor: dict, duration_ms: int, published: dict | None,
                  event_id: str, evaluations: dict | None = None, evaluation_errors: dict | None = None,
                  inputs_fp: str | None = None, fingerprint_value: str | None = None) -> dict:
    """upstream: {brainId: {"registry": dict|None, "health": dict|None, "validationStatus": str|None}}.
    evaluations: {lakeId: normalized evaluation (evaluation.evaluate)} for the pilot lakes that evaluated."""
    evaluations = evaluations or {}
    evaluation_errors = evaluation_errors or {}
    now_iso = bp.iso(now)
    slot_of = {bid: cat["dependencies"][bid]["slot"] for bid in DEPENDENCY_ORDER}
    used_slots = {slot for e in evaluations.values() for slot in (e.get("inputsUsed") or {})}
    deps = {bid: dependency_status(bid, cat["dependencies"][bid], upstream[bid]["registry"], upstream[bid]["health"],
                                   upstream[bid]["validationStatus"], cat, now, pilot_ran=bool(evaluations),
                                   used_in_last_evaluation=slot_of[bid] in used_slots,
                                   last_evaluation_at=now_iso if evaluations else None) for bid in DEPENDENCY_ORDER}
    summary = dependency_summary(deps)
    keys = bp.lake_keys(lakes)
    updates: dict = {}
    published_counts: dict[str, int] = {}
    snapshot_field = cat.get("snapshotField", "sectorIntelligence")
    for lid in lakes:
        k = keys[lid]
        updates[f"/lakeFleet/{k}/lakeId"] = lid
        ev = evaluations.get(lid)
        if ev is not None:
            updates[f"/lakes/{k}/states/{SLOT}"] = ev
            updates[f"/snapshots/{k}/latest/lakeId"] = lid
            updates[f"/snapshots/{k}/latest/{snapshot_field}"] = ev
            updates[f"/snapshots/{k}/latest/brainVersions/{BRAIN_ID}"] = BRAIN_VERSION
            updates[f"/lakeFleet/{k}/readiness/{SLOT}"] = "CALIBRATION"
            updates[f"/lakeFleet/{k}/modelVersions/{SLOT}"] = ev["evaluationVersion"]
            updates[f"/lakeFleet/{k}/slots/{SLOT}"] = {"readiness": "CALIBRATION", "stateType": "EVALUATED_PILOT", "kind": "evaluated",
                                                        "stale": False, "evidenceStale": bool(ev.get("degradedInputs")),
                                                        "issueCount": len(ev.get("degradedInputs") or []),
                                                        "inputsPublished": ev["synthesis"]["inputsFresh"],
                                                        "inputsConsumed": len(ev.get("inputsUsed") or {}),
                                                        "generatedAt": now_iso, "lastUpdatedAt": now_iso}
            continue
        inputs = lake_inputs(fleet.get(k), deps, now)
        st = lake_state(lid, inputs, cat, serving, now)
        updates[f"/lakes/{k}/states/{SLOT}"] = st
        n = st["inputCounts"]["published"]
        published_counts[f"{n} of {len(inputs)} published"] = published_counts.get(f"{n} of {len(inputs)} published", 0) + 1
        slot = {"stateType": "NOT_EVALUATED", "kind": "not_evaluated", "issueCount": 0, "stale": False,
                "inputsPublished": n, "inputsConsumed": 0, "lastUpdatedAt": now_iso}
        if lid in evaluation_errors:
            slot["lastErrorAt"], slot["lastError"] = now_iso, evaluation_errors[lid][:200]
        updates[f"/lakeFleet/{k}/slots/{SLOT}"] = slot

    # The stored fingerprint must be the one plan() compares against next time: main() computes it from the
    # dependency view BEFORE this run upgrades connections to CONNECTED (pilot_ran). Recomputing it here from the
    # upgraded view made every --plan say "changed" and republish hourly (orchestrator cycles, 2026-10-13).
    fp = fingerprint_value or fingerprint(cat_sha, serving, deps, inputs_fp)
    # The catalog's "no evaluation / no Brain consumed" blockers describe the inventory-only mode; once the pilot evaluated lakes from Brain states they
    # are false, and the true position is in statusReasons (PILOT_EVALUATION_ONLY, NOT_CONSUMED_BY_CUSTOMER_PATH).
    blockers = [b for b in cat.get("declaredBlockers", []) if not (evaluations and b.get("id") in PILOT_RESOLVED_BLOCKERS)] + derived_blockers(deps, serving)
    today = now.date().isoformat()
    lin = cat["codeLineage"]
    registry = _strip({
        "brainId": BRAIN_ID, "displayName": DISPLAY_NAME, "domain": "intelligence", "question": QUESTION,
        "platform": PLATFORM,
        "stalenessModel": "FINGERPRINT", "dependsOn": list(DEPENDENCY_ORDER),
        "schedule": {"cadence": "manual (fingerprint-driven; Orchestrator will own cadence)", "running": False},
        "version": BRAIN_VERSION, "schemaVersion": bp.SCHEMA_VERSION, "enabled": True, "health": "HEALTHY",
        "status": "CALIBRATION" if evaluations else "DISCOVERED",
        "statusBasis": (f"Pilot: normalized evaluations ({evaluations[next(iter(evaluations))]['evaluationVersion']}) for "
                        f"{len(evaluations)} lakes consume real specialist Brain states with provenance. No customer "
                        f"consumes them; customers get the Engine Conditions Score (PRODUCTION, NOT_VALIDATED)."
                        if evaluations else
                        "Registered and inventoried. No normalized Sector Intelligence evaluation exists and no "
                        "Intelligence implementation reads any Brain. Customers get the Engine Conditions Score "
                        "(PRODUCTION, NOT_VALIDATED)."),
        "statusReasons": (["PILOT_EVALUATION_ONLY", "NOT_CONSUMED_BY_CUSTOMER_PATH", "CUSTOMER_PATH_NOT_VALIDATED"]
                          if evaluations else ["NO_NORMALIZED_EVALUATION", "NO_BRAIN_CONSUMED", "CUSTOMER_PATH_NOT_VALIDATED"]),
        "supportedLakeCount": len(evaluations), "evaluatedLakeCount": len(evaluations), "directoryLakeCount": len(lakes),
        "evaluation": _strip({"version": evaluations[next(iter(evaluations))]["evaluationVersion"] if evaluations else None,
                              "pilotLakes": sorted(evaluations), "lastEvaluationAt": now_iso if evaluations else None,
                              "customerConsumes": False, "errors": evaluation_errors or None}) if (evaluations or evaluation_errors) else None,
        "lastSuccessfulRun": bp.iso(now), "updatedAt": bp.iso(now),
        "deploymentVersion": deployment, "publishMode": "manual",
        "catalogVersion": cat["catalogVersion"], "catalogSha256": cat_sha, "fingerprint": fp,
        "engineServing": serving,
        "activeModel": {"modelIds": [cat["activeImplementation"]], "servedBy": lin["service"],
                        "engineRevision": serving.get("revision"), "processingPathId": "engine-conditions"},
        "modelRoster": roster(cat, serving),
        "dependencies": deps, "dependencyOrder": DEPENDENCY_ORDER, "dependencySummary": summary,
        "blockers": blockers,
        "versions": versions_list(cat, serving, today),
        "breakdowns": {"normalizedEvaluation": _strip({"EVALUATED_PILOT": len(evaluations) or None, "NOT_EVALUATED": len(lakes) - len(evaluations)}),
                       "upstreamStatesPublished": published_counts},
        "vocabularies": VOCABULARIES,
        "inputContract": cat.get("inputContract"), "outputContract": cat.get("outputContract"),
        "knownLimitations": cat.get("knownLimitations"),
        "orchestration": descriptor,
    })
    stale_ids = [b for b, d in deps.items() if d.get("publishingStatus") == "STALE"]
    missing = [b for b, d in deps.items() if not d["exists"]]
    health = _strip({"status": "HEALTHY", "lastRun": bp.iso(now), "lastSuccess": bp.iso(now), "durationMs": duration_ms,
                     "errorCount": 0, "deployedVersion": deployment, "publishMode": "manual",
                     "engineRevision": serving.get("revision"), "lakesPublished": len(lakes),
                     "dependencyFailures": len(stale_ids) + summary["unhealthy"],
                     "staleInputs": stale_ids or None, "notRegisteredInputs": missing or None,
                     "evaluatedLakes": len(evaluations) or None, "evaluationErrors": evaluation_errors or None,
                     "note": "Publisher health only. Dependency freshness is reported per dependency; a pilot evaluation "
                             "that could not run is recorded under evaluationErrors, never invented."})
    v = cat["validation"]
    validation = _strip({"brainId": BRAIN_ID, "modelVersion": cat["activeImplementation"], "validationVersion": "none",
                         "status": v["status"], "statusNote": v.get("statusNote"), "softwareTests": v.get("softwareTests"),
                         "predictiveValidation": v.get("predictiveValidation"),
                         "unvalidatedActiveModels": [cat["activeImplementation"]], "updatedAt": bp.iso(now)})
    updates[f"/brains/{BRAIN_ID}"] = registry
    updates[f"/health/brains/{BRAIN_ID}"] = health
    updates[f"/validation/{BRAIN_ID}"] = validation

    prev_v = (published or {}).get("version")
    prev_cat = (published or {}).get("catalogVersion")
    prev_rev = ((published or {}).get("engineServing") or {}).get("revision")
    if not published or prev_v != BRAIN_VERSION or prev_cat != cat["catalogVersion"] or prev_rev != serving.get("revision"):
        if not published:
            title = f"Sector Intelligence registered ({BRAIN_VERSION}); customer path = {cat['activeImplementation']}"
        elif prev_rev != serving.get("revision"):
            title = f"Sector Intelligence: Engine serving revision {prev_rev} -> {serving.get('revision')}"
        else:
            title = f"Sector Intelligence metadata updated ({prev_v} / {prev_cat} -> {BRAIN_VERSION} / {cat['catalogVersion']})"
        updates[f"/activity/{event_id}"] = {"id": event_id, "at": bp.iso(now), "kind": "brain.registered" if not published else "brain.updated",
                                             "severity": "info", "brainId": BRAIN_ID, "title": title}
    return updates


# ------------------------------------------------------------------ helpers
def _strip(d):
    """Drop None values and empty containers: RTDB stores neither, and unknown must stay absent."""
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            v = _strip(v)
            if v is None or (isinstance(v, (dict, list)) and not v):
                continue
            out[k] = v
        return out
    if isinstance(d, list):
        return [_strip(x) for x in d if x is not None]
    return d


_BAD = re.compile(r"[.$#\[\]/]")


def check_keys(updates: dict) -> None:
    """RTDB forbids . $ # [ ] / in keys (paths may contain /)."""
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if _BAD.search(str(k)):
                    raise CatalogError(f"illegal RTDB key {k!r} at {path}")
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}/{i}")
    for p, v in updates.items():
        if any(_BAD.search(seg) for seg in p.strip("/").split("/")):
            raise CatalogError(f"illegal RTDB path {p!r}")
        walk(v, p)
