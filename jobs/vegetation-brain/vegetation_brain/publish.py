"""Vegetation Brain SHADOW publisher: fleet manifest (+ optional offline observations/context) -> Brain RTDB shape, DRY-RUN ONLY.

Write order mirrors the platform contract: per lake `states/vegetation` + snapshot -> `lakeFleet` rows -> registry/validation -> health.
Vegetation writes ONLY vegetation-owned paths (ownership enforced by the writer). `publish()` never raises. There is no live writer:
adopting one is a Michael decision (docs/brains/vegetation/VEGETATION_OPS_VISIBILITY_GAP.md)."""
from __future__ import annotations

import traceback
from collections import Counter
from datetime import datetime, timezone

from . import contract as C
from . import ops_summary
from .state import build_state, plan
from .writer import PLATFORM  # noqa: E402  (also puts the shared platform package on sys.path)

from sector_brain_platform import lake_key, key_collisions  # noqa: E402

NOT_VALIDATED = {
    "brainId": C.BRAIN_ID, "status": "NOT_VALIDATED", "modelVersion": C.MODEL_ID, "validationVersion": "vegetation-validation-none (shadow)",
    "note": "The observer is unit-tested; it is NOT validated against independent truth under the pre-registered gates "
            "(docs/brains/vegetation/VEGETATION_VALIDATION_PREREGISTRATION.md). No customer surface consumes it.",
    "separation": "MODEL/SCIENCE validation only. Lake readiness lives in /lakeFleet; runtime health in /health.",
}


def _health(errors: list, evaluated: int, unavailable: int) -> str:
    if errors and evaluated == 0:
        return "FAILED"
    if errors:
        return "DEGRADED"
    if evaluated and unavailable == evaluated:
        return "DEGRADED"
    return "HEALTHY" if evaluated else "UNKNOWN"


def publish(manifest: dict, writer, observations: dict | None = None, contexts: dict | None = None, validation: dict | None = None,
            now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    now_iso = C.iso(now)
    observations, contexts = observations or {}, contexts or {}
    rep: dict = {"ok": False, "errors": [], "writes": 0, "lakes": {}}
    try:
        cands = manifest["candidates"]
        coll = key_collisions([c["lakeId"] for c in cands])
        if coll:
            raise ValueError(f"lake key collision: {coll}")
        mv = manifest.get("manifestVersion", "unversioned")
        readiness: dict[str, str] = {}
        kinds = Counter()
        stale_lakes = evaluated = unavailable = observed = skipped = 0
        for cand in cands:
            lid = cand["lakeId"]
            k = lake_key(lid)
            obs = observations.get(lid)
            if obs is None and cand["readiness"] != "BLOCKED":
                readiness[lid] = "PROFILED"            # could be observed; nothing has been run: no state is written
                continue
            try:
                pl = plan(writer.get(f"lakes/{k}/states/{C.SLOT}"), cand, obs, contexts.get(lid), mv)
                state, meta = build_state(cand, obs, now, validation=validation, context=contexts.get(lid), manifest_version=mv)
                evaluated += 1
                readiness[lid] = meta["readiness"]
                kinds[meta["kind"]] += 1
                unavailable += meta["kind"] == "unavailable"
                stale_lakes += bool(meta["stale"])
                observed += obs is not None and meta["presence"] != "UNKNOWN"
                rep["lakes"][lid] = {**meta, "plan": pl["action"]}
                if pl["action"] == "SKIP":
                    skipped += 1
                    continue
                writer.patch({f"lakes/{k}/states/{C.SLOT}": state, f"snapshots/{k}/latest/{C.SNAPSHOT_FIELD}": state,
                              f"snapshots/{k}/latest/lakeId": lid, f"snapshots/{k}/latest/brainVersions/{C.BRAIN_ID}": C.BRAIN_VERSION})
                rep["writes"] += 1
            except Exception as e:
                readiness[lid] = "DEGRADED"
                unavailable += 1
                evaluated += 1
                stale_lakes += 1
                rep["errors"].append(f"lake {lid}: {e!r} {traceback.format_exc()[-300:]}")

        fleet = {}
        for lid, r in readiness.items():
            k = lake_key(lid)
            fleet[f"lakeFleet/{k}/lakeId"] = lid
            fleet[f"lakeFleet/{k}/readiness/{C.SLOT}"] = r
            fleet[f"lakeFleet/{k}/modelVersions/{C.SLOT}"] = C.MODEL_ID
            if lid in rep["lakes"]:
                m = rep["lakes"][lid]
                fleet[f"lakeFleet/{k}/slots/{C.SLOT}"] = {"readiness": r, "stale": bool(m["stale"]), "stateType": m["kind"], "kind": m["kind"],
                                                          "issueCount": 0 if r == "CALIBRATION" else 1, "lastUpdatedAt": now_iso}
        writer.patch(fleet)
        rep["writes"] += 1

        counts = dict(Counter(readiness.values()))
        health = _health(rep["errors"], evaluated, unavailable)
        reg = {
            "brainId": C.BRAIN_ID, "displayName": C.DISPLAY_NAME, "domain": C.DOMAIN, "question": C.QUESTION, "platform": PLATFORM,
            "version": C.BRAIN_VERSION, "schemaVersion": C.SCHEMA_VERSION, "enabled": True, "health": health, "status": "PROFILED",
            "supportedLakeCount": sum(1 for c in cands if c["readiness"] != "BLOCKED"), "readinessCounts": counts, "staleLakeCount": stale_lakes,
            "staleAfterHours": 72, "stalenessModel": C.STALENESS_MODEL, "dependsOn": list(C.DEPENDS_ON),
            "lastSuccessfulRun": now_iso if not rep["errors"] else None,
            "lastError": {"at": now_iso, "message": rep["errors"][0][:300]} if rep["errors"] else None,
            "schedule": {"cadence": "SHADOW: not scheduled, not deployed", "jobId": C.JOB_ID, "running": False},
            "models": {"active": None, "candidates": [{"modelId": C.MODEL_ID, "status": "SHADOW", "version": C.BRAIN_VERSION}]},
            "versions": [{"version": C.BRAIN_VERSION, "date": now_iso[:10], "note": "Surface-vegetation observer foundation; shadow/internal only", "status": "SHADOW"}],
            "validation": {"ref": f"/validation/{C.BRAIN_ID}", "status": "NOT_VALIDATED"}, "sourceIds": [],
            "readinessDefinitions": C.READINESS_DEFINITIONS, "updatedAt": now_iso, "publishMode": "shadow: internal only, not scheduled",
            "scoreNote": C.SCORE_NOTE,
        }
        try:
            reg.update(ops_summary.registry_extras(manifest, observed, {"evaluated": evaluated, "unavailable": unavailable}, validation))
        except Exception as e:
            rep["errors"].append(f"ops summary: {e!r}")
            reg["blockers"] = ["Ops summary unavailable this run"]
        writer.patch({f"brains/{C.BRAIN_ID}": reg, f"validation/{C.BRAIN_ID}": {**NOT_VALIDATED, "publishedAt": now_iso}})
        rep["writes"] += 1
        writer.patch({f"health/brains/{C.BRAIN_ID}": {"status": health, "lastRun": now_iso, "lastSuccess": reg["lastSuccessfulRun"],
                                                      "staleLakeCount": stale_lakes, "errorCount": len(rep["errors"]),
                                                      "latestError": rep["errors"][0][:300] if rep["errors"] else None,
                                                      "deployedVersion": None, "publishMode": reg["publishMode"]}})
        rep["writes"] += 1
        rep.update({"ok": not rep["errors"], "health": health, "readinessCounts": counts, "evaluated": evaluated, "observed": observed,
                    "unavailable": unavailable, "skippedUnchanged": skipped, "kinds": dict(kinds)})
    except Exception as e:
        rep["errors"].append(f"publish crashed: {e!r} {traceback.format_exc()[-400:]}")
    return rep
