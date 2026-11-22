"""Generation Brain publisher: dam catalog + source readings -> Brain RTDB shape (dry-run by default).

Per lake that is due (freshness.due): read its bound sources (http.Fetcher, access-gated, at most once per URL per run), build the state,
write `states/generation` + snapshot (one atomic update) -> `lakeFleet` rows -> registry / validation -> health -> activity. Generation writes
ONLY generation-owned paths (ownership is enforced by the writer). `publish()` never raises. NOTHING here is deployed or scheduled; a live
write needs an APPROVED knowledge release and explicit operator intent (run.py)."""
from __future__ import annotations

import traceback
from collections import Counter
from datetime import datetime, timezone

from sector_brain_platform import event_id as _event_id, key_collisions, lake_key, prune_activity as _prune_own

from . import contract as C
from . import ops_summary
from .freshness import due
from .state import build_state, plan, read_sources, readiness_of
from .writer import PLATFORM

NOT_VALIDATED = {
    "brainId": C.BRAIN_ID, "status": "NOT_VALIDATED", "modelVersion": C.MODEL_ID,
    "validationVersion": "generation-validation-none (calibration)",
    "note": "Parsers and assembly rules are unit-tested on recorded and hand-built fixtures. The published release picture has not yet been "
            "compared with the operators' published schedules over the pre-registered week (Generation Brain plan, section 5).",
    "separation": "MODEL/SCIENCE validation only. Lake readiness lives in /lakeFleet; runtime health in /health.",
}


def _health(errors: list, evaluated: int, unavailable: int) -> str:
    if errors and evaluated == 0:
        return "FAILED"
    if errors or (evaluated and unavailable == evaluated):
        return "DEGRADED"
    return "HEALTHY" if evaluated else "UNKNOWN"


def publish(catalog: dict, access: dict, fetcher, writer, now: datetime | None = None, scope: str = "bound", release: dict | None = None,
            mode: str = "calibration") -> dict:
    """scope="bound" (default): per-lake nodes and fleet rows ONLY for lakes with a bound, allowed source. scope="fleet" also writes the
    readiness (NOT_BOUND / ACCESS_BLOCKED) of every dam lake - analysis and dry runs only."""
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    now_iso = C.iso(now)
    if scope not in ("bound", "fleet"):
        raise ValueError(f"unknown scope {scope!r}")
    rep: dict = {"ok": False, "errors": [], "writes": 0, "lakes": {}, "scope": scope}
    try:
        dams = catalog["dams"]
        coll = key_collisions([d["lakeId"] for d in dams])
        if coll:
            raise ValueError(f"lake key collision: {coll}")
        last = writer.get(f"brains/{C.BRAIN_ID}") or {}
        readiness: dict[str, str] = {}
        kinds, statuses, tiers = Counter(), Counter(), Counter()
        evaluated = unavailable = not_due = changed = stale = 0
        for rec in dams:
            lid = rec["lakeId"]
            r = readiness_of(rec, access)
            readiness[lid] = r
            if r != "CALIBRATION":
                continue
            k = lake_key(lid)
            try:
                pub = writer.get(f"lakes/{k}/states/{C.SLOT}")
                if not due(pub, now):
                    not_due += 1
                    rep["lakes"][lid] = {"plan": "NOT_DUE", "nextCheckAt": ((pub or {}).get("freshness") or {}).get("nextCheckAt"),
                                         "kind": (pub or {}).get("kind"), "status": ((pub or {}).get("release") or {}).get("status"),
                                         "tier": ((pub or {}).get("freshness") or {}).get("tier"), "stale": False}
                    continue
                readings = read_sources(rec, access, fetcher, now)
                state, meta = build_state(rec, readings, pub, now, catalog.get("catalogVersion", "unversioned"), release)
                pl = plan(pub, meta["inputFingerprint"])
                evaluated += 1
                changed += bool(pl["changed"])
                readiness[lid] = meta["readiness"]
                kinds[meta["kind"]] += 1
                statuses[meta["status"]] += 1
                tiers[meta["tier"]] += 1
                unavailable += meta["kind"] == C.UNAVAILABLE
                stale += bool(meta["stale"])
                rep["lakes"][lid] = {**meta, "plan": pl["action"], "changed": pl["changed"]}
                writer.patch({f"lakes/{k}/states/{C.SLOT}": state, f"snapshots/{k}/latest/{C.SNAPSHOT_FIELD}": state,
                              f"snapshots/{k}/latest/lakeId": lid, f"snapshots/{k}/latest/brainVersions/{C.BRAIN_ID}": C.BRAIN_VERSION})
                rep["writes"] += 1
            except Exception as e:      # one lake never stops the run
                readiness[lid] = "DEGRADED"
                evaluated += 1
                unavailable += 1
                stale += 1
                rep["errors"].append(f"lake {lid}: {e!r} {traceback.format_exc()[-300:]}")

        written = {lid: r for lid, r in readiness.items() if lid in rep["lakes"]} if scope == "bound" else dict(readiness)
        fleet = {}
        for lid, r in written.items():
            k = lake_key(lid)
            fleet[f"lakeFleet/{k}/lakeId"] = lid
            fleet[f"lakeFleet/{k}/readiness/{C.SLOT}"] = r
            m = rep["lakes"].get(lid)
            if m and m.get("plan") == "PUBLISH":
                fleet[f"lakeFleet/{k}/modelVersions/{C.SLOT}"] = C.MODEL_ID
                fleet[f"lakeFleet/{k}/slots/{C.SLOT}"] = {"readiness": r, "stale": bool(m["stale"]), "stateType": m["kind"], "kind": m["kind"],
                                                           "status": m["status"], "tier": m["tier"], "issueCount": len(m.get("errors") or []),
                                                           "lastUpdatedAt": now_iso}
        if fleet:
            writer.patch(fleet)
            rep["writes"] += 1

        counts = dict(Counter(written.values()))
        health = _health(rep["errors"], evaluated, unavailable)
        reg = {
            "brainId": C.BRAIN_ID, "displayName": C.DISPLAY_NAME, "domain": C.DOMAIN, "question": C.QUESTION, "platform": PLATFORM,
            "version": C.BRAIN_VERSION, "schemaVersion": C.SCHEMA_VERSION, "contractVersion": C.STATE_SCHEMA,
            "enabled": False,                       # registered DISABLED: orchestration.status DISABLED (ops_summary)
            "health": health,
            "status": "CALIBRATION", "lifecycle": C.LIFECYCLE,
            "supportedLakeCount": sum(1 for m in rep["lakes"].values() if m.get("kind") in (C.OBSERVED, C.SCHEDULE_ONLY)),
            "readinessCounts": counts, "staleLakeCount": stale, "staleAfterHours": None, "stalenessModel": C.STALENESS_MODEL,
            "dependsOn": list(C.DEPENDS_ON),
            "lastSuccessfulRun": now_iso if not rep["errors"] else last.get("lastSuccessfulRun"),
            "lastError": {"at": now_iso, "message": rep["errors"][0][:300]} if rep["errors"] else None,
            "schedule": {"cadence": "adaptive per dam (TRANSITION 60 / ACTIVE 120 / STEADY 180 min; never more than hourly); not scheduled, not deployed",
                         "running": False},
            "scope": scope, "validation": {"ref": f"/validation/{C.BRAIN_ID}", "status": "NOT_VALIDATED"},
            "versions": [{"version": C.BRAIN_VERSION, "date": now_iso[:10], "note": "Dam release and generation assembly; calibration only", "status": "CALIBRATION"}],
            "readinessDefinitions": C.READINESS_DEFINITIONS, "stateKinds": C.KINDS, "updatedAt": now_iso,
            "publishMode": "calibration: internal only, not scheduled" if mode == "calibration" else mode,
            "scoreNote": C.SCORE_NOTE, "scoreStatus": "NOT_ESTABLISHED",
        }
        try:
            reg.update(ops_summary.registry_extras(catalog, access, {"evaluated": evaluated, "unavailable": unavailable, "notDue": not_due,
                                                                      "changed": changed, "kinds": dict(kinds), "statuses": dict(statuses),
                                                                      "tiers": dict(tiers)}, release=release))
        except Exception as e:      # the Ops summary must never block the registry write
            rep["errors"].append(f"ops summary: {e!r}")
            reg["blockers"] = ["Ops summary unavailable this run"]
        writer.patch({f"brains/{C.BRAIN_ID}": reg, f"validation/{C.BRAIN_ID}": {**NOT_VALIDATED, "publishedAt": now_iso}})
        rep["writes"] += 1
        writer.patch({f"health/brains/{C.BRAIN_ID}": {"status": health, "staleLakeCount": stale}})
        rep["writes"] += 1

        events = []
        if last.get("version") != C.BRAIN_VERSION:
            events.append(("brain.version" if last.get("version") else "brain.registered", "info",
                           f"Generation Brain {C.BRAIN_VERSION} (calibration) evaluated {evaluated} lakes", None))
        if rep["errors"] and not last.get("lastError"):
            events.append(("run.failed", "critical", f"Generation run error: {rep['errors'][0][:120]}", None))
        for lid, m in rep["lakes"].items():
            if m.get("plan") == "PUBLISH" and m.get("tier") == C.TIER_TRANSITION and m.get("changed"):
                events.append(("release.transition", "info", f"{lid}: release picture changed ({m['status']})", lid))
        if events:
            writer.patch({f"activity/{_event_id(now, C.BRAIN_ID, i)}": {"id": _event_id(now, C.BRAIN_ID, i), "at": now_iso, "kind": kind, "title": t,
                                                                         "brainId": C.BRAIN_ID, "severity": sev, **({"lakeId": lid} if lid else {})}
                          for i, (kind, sev, t, lid) in enumerate(events)})
            dels = _prune_own(writer.get("activity") or {}, C.BRAIN_ID, now)
            if dels:
                writer.patch(dels)
        rep.update({"ok": not rep["errors"], "health": health, "readinessCounts": counts, "evaluated": evaluated, "notDue": not_due,
                    "changed": changed, "unavailable": unavailable, "events": len(events), "kinds": dict(kinds), "statuses": dict(statuses),
                    "tiers": dict(tiers), "requests": len(fetcher.requests)})
    except Exception as e:
        rep["errors"].append(f"publish crashed: {e!r} {traceback.format_exc()[-400:]}")
    return rep
