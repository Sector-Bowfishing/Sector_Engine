"""Depth Brain SHADOW publisher: manifest + Lake Brain states -> Brain RTDB shape (dry-run by default).

Write order mirrors the platform contract: per lake `states/depth` + snapshot (one atomic update) -> `lakeFleet` rows
-> registry/validation -> health -> activity. Depth writes ONLY depth-owned paths (ownership is enforced by the writer).
`publish()` never raises. NOTHING here is deployed or scheduled; a live write needs explicit operator intent."""
from __future__ import annotations

import traceback
from collections import Counter
from datetime import datetime, timezone

from sector_brain_platform import event_id as _event_id, lake_key, key_collisions, prune_activity as _prune_own

from . import contract as C
from . import ops_summary
from .state import build_state, plan
from .writer import PLATFORM

NOT_VALIDATED = {
    "brainId": C.BRAIN_ID, "status": "NOT_VALIDATED", "modelVersion": C.MODEL_ID,
    "validationVersion": "depth-validation-none (shadow)",
    "note": "The shift arithmetic is unit-tested. Effective depth is NOT field-validated; no bowfishing field truth exists yet "
            "(preregistered plan in brains/depth/research). Research validation of the underlying evidence lives in the Depth research workspace.",
    "separation": "MODEL/SCIENCE validation only. Lake readiness lives in /lakeFleet and profiles; runtime health in /health.",
}


def _health(errors: list, evaluated: int, unavailable: int) -> str:
    if errors and evaluated == 0:
        return "FAILED"
    if errors:
        return "DEGRADED"
    if evaluated and unavailable == evaluated:
        return "DEGRADED"
    return "HEALTHY" if evaluated else "UNKNOWN"


def publish(manifest: dict, lake_states: dict, writer, now: datetime | None = None, mode: str = "shadow", scope: str = "pilots",
            release: dict | None = None) -> dict:
    """scope="pilots" (default, the only scope a live write is approved for): per-lake nodes and fleet rows ONLY for lakes with a Lake Brain state
    (or a reviewed pilot). scope="fleet" additionally writes PROFILED/BLOCKED readiness for every candidate - analysis/dry-run only."""
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    now_iso = C.iso(now)
    if scope not in ("pilots", "fleet"):
        raise ValueError(f"unknown scope {scope!r}")
    rep: dict = {"ok": False, "errors": [], "writes": 0, "lakes": {}, "scope": scope}
    try:
        cands = manifest["candidates"]
        coll = key_collisions([c["lakeId"] for c in cands])
        if coll:
            raise ValueError(f"lake key collision: {coll}")
        mv = manifest.get("manifestVersion", "unversioned")
        last = writer.get(f"brains/{C.BRAIN_ID}") or {}
        readiness: dict[str, str] = {}
        kinds = Counter()
        stale_lakes = evaluated = unavailable = skipped = 0
        for rec in cands:
            lid = rec.get("lakeId")
            if not lid:
                rep["errors"].append(f"candidate without lakeId skipped: {str(rec)[:80]}")
                continue
            k = lake_key(lid)
            ls = lake_states.get(lid)
            if ls is None and rec.get("rollout") != "PILOT_VERIFIED":
                readiness[lid] = "PROFILED" if rec.get("shiftPossible") else "BLOCKED"
                continue
            try:
                pub = writer.get(f"lakes/{k}/states/{C.SLOT}")
                pl = plan(pub, rec, ls, mv)
                state, meta = build_state(rec, ls, now, manifest_version=mv)
                evaluated += 1
                readiness[lid] = meta["readiness"]
                kinds[meta["kind"]] += 1
                unavailable += meta["kind"] == "unavailable"
                stale_lakes += bool(meta["stale"])
                rep["lakes"][lid] = {**meta, "plan": pl["action"]}
                if pl["action"] == "SKIP":
                    skipped += 1
                    continue
                writer.patch({f"lakes/{k}/states/{C.SLOT}": state, f"snapshots/{k}/latest/{C.SNAPSHOT_FIELD}": state,
                              f"snapshots/{k}/latest/lakeId": lid, f"snapshots/{k}/latest/brainVersions/{C.BRAIN_ID}": C.BRAIN_VERSION})
                rep["writes"] += 1
            except Exception as e:      # one lake never stops the run
                readiness[lid] = "DEGRADED"
                unavailable += 1
                evaluated += 1
                stale_lakes += 1
                rep["errors"].append(f"lake {lid}: {e!r} {traceback.format_exc()[-300:]}")

        written = {lid: r for lid, r in readiness.items() if lid in rep["lakes"]} if scope == "pilots" else dict(readiness)
        fleet = {}
        for lid, r in written.items():
            k = lake_key(lid)
            fleet[f"lakeFleet/{k}/lakeId"] = lid
            fleet[f"lakeFleet/{k}/readiness/{C.SLOT}"] = r
            if lid in rep["lakes"]:
                m = rep["lakes"][lid]
                fleet[f"lakeFleet/{k}/modelVersions/{C.SLOT}"] = C.MODEL_ID
                fleet[f"lakeFleet/{k}/slots/{C.SLOT}"] = {"readiness": r, "stale": bool(m["stale"]), "stateType": m["kind"], "kind": m["kind"],
                                                           "issueCount": 0 if r == "CALIBRATION" else 1, "lastUpdatedAt": now_iso}
        writer.patch(fleet)
        rep["writes"] += 1

        counts = dict(Counter(written.values()))
        health = _health(rep["errors"], evaluated, unavailable)
        reg = {
            "brainId": C.BRAIN_ID, "displayName": C.DISPLAY_NAME, "domain": C.DOMAIN, "question": C.QUESTION, "platform": PLATFORM,
            "version": C.BRAIN_VERSION, "schemaVersion": C.SCHEMA_VERSION, "enabled": True, "health": health, "status": "PROFILED",
            "supportedLakeCount": sum(1 for lid, m in rep["lakes"].items() if m["kind"] == "observed"), "readinessCounts": counts, "staleLakeCount": stale_lakes,
            "staleAfterHours": None, "stalenessModel": C.STALENESS_MODEL, "dependsOn": list(C.DEPENDS_ON),
            "lastSuccessfulRun": now_iso if not rep["errors"] else last.get("lastSuccessfulRun"),
            "lastError": {"at": now_iso, "message": rep["errors"][0][:300]} if rep["errors"] else None,
            "schedule": {"cadence": "SHADOW: not scheduled, not deployed (FINGERPRINT-triggered once the orchestrator is approved)", "running": False},
            "shadow": True, "scope": scope,
            "models": {"active": None, "candidates": [{"modelId": C.MODEL_ID, "status": "SHADOW", "version": C.BRAIN_VERSION}]},
            "versions": [{"version": C.BRAIN_VERSION, "date": now_iso[:10], "note": "Effective-depth shift foundation; shadow/internal only", "status": "SHADOW"}],
            "validation": {"ref": f"/validation/{C.BRAIN_ID}", "status": "NOT_VALIDATED"},
            "sourceIds": [],
            "descriptor": {"components": {"effectiveDepthShift": {
                "status": "SHADOW", "inputs": ["lake-brain states/lake (currentElevationFt, datum, sourceCapability)", "engine-directory fullPoolFt/poolBasis/poolConfidence",
                                                "audited datum table", "candidate manifest " + mv],
                "staleness": "fingerprint of the Lake Brain observation + reference + manifest + Depth version",
                "recomputeWhen": ["Lake Brain publishes a new observation", "manifest or Depth version changes"]}}},
            "readinessDefinitions": C.READINESS_DEFINITIONS, "stateKinds": C.KINDS, "updatedAt": now_iso,
            "publishMode": ("shadow: internal only, not scheduled" if mode == "shadow" else mode),
            "scoreNote": C.SCORE_NOTE,
        }
        try:
            reg.update(ops_summary.registry_extras(manifest, sum(1 for lid in lake_states if lid in readiness), {"evaluated": evaluated, "unavailable": unavailable},
                                                    release=release))
        except Exception as e:      # the Ops summary must never block the registry write
            rep["errors"].append(f"ops summary: {e!r}")
            reg["blockers"] = ["Ops summary unavailable this run"]
        writer.patch({f"brains/{C.BRAIN_ID}": reg, f"validation/{C.BRAIN_ID}": {**NOT_VALIDATED, "publishedAt": now_iso}})
        rep["writes"] += 1
        writer.patch({f"health/brains/{C.BRAIN_ID}": {"status": health, "lastRun": now_iso, "lastSuccess": reg["lastSuccessfulRun"],
                                                      "staleLakeCount": stale_lakes, "errorCount": len(rep["errors"]),
                                                      "latestError": rep["errors"][0][:300] if rep["errors"] else None,
                                                      "deployedVersion": None, "publishMode": reg["publishMode"]}})
        rep["writes"] += 1

        events = []
        if last.get("version") != C.BRAIN_VERSION:
            events.append(("brain.version" if last.get("version") else "brain.registered", "info",
                           f"Depth Brain {C.BRAIN_VERSION} (shadow) evaluated {evaluated} lakes", None))
        if rep["errors"] and not last.get("lastError"):
            events.append(("run.failed", "critical", f"Depth run error: {rep['errors'][0][:120]}", None))
        if events:
            writer.patch({f"activity/{_event_id(now, C.BRAIN_ID, i)}": {"id": _event_id(now, C.BRAIN_ID, i), "at": now_iso, "kind": kind, "title": t,
                                                                         "brainId": C.BRAIN_ID, "severity": sev, **({"lakeId": lid} if lid else {})}
                          for i, (kind, sev, t, lid) in enumerate(events)})
            dels = _prune_own(writer.get("activity") or {}, C.BRAIN_ID, now)
            if dels:
                writer.patch(dels)
        rep.update({"ok": not rep["errors"], "health": health, "readinessCounts": counts, "evaluated": evaluated, "skippedUnchanged": skipped,
                    "unavailable": unavailable, "events": len(events), "kinds": dict(kinds)})
    except Exception as e:
        rep["errors"].append(f"publish crashed: {e!r} {traceback.format_exc()[-400:]}")
    return rep
