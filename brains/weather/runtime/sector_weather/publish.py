"""Weather Brain run: plan -> fetch -> compute -> write set. The write set is ONE flat multi-path update over Weather-owned paths only
(the families registered for `weather` in sector_brain_platform.publisher.registry). This version has NO live writer: the write set goes into
the platform's in-memory DryRunStore (ownership and key checks included) and is dumped to a file. Live publication is a separate owner step
(WEATHER_BRAIN_PLAN.md §6)."""
from __future__ import annotations

import hashlib
import math
import traceback
from datetime import datetime

from . import contract as C
from .client import FetchError, OutOfCoverage
from .freshness import due
from .nws import decode_grid, decode_observations, decode_point, decode_stations
from .reading import assemble
from .state import build_state, readiness

REGISTRY_CHILDREN = {
    "identity": ("brainId", "displayName", "domain", "question", "platform"),
    "model": ("version", "schemaVersion", "stalenessModel", "dependsOn", "descriptor", "readinessDefinitions", "stateKinds", "thresholds",
              "thresholdsVersion", "sourceIds"),
    "status": ("schedule", "enabled", "health", "status", "supportedLakeCount", "directoryLakeCount", "readinessCounts", "staleLakeCount",
               "staleAfterHours", "lastSuccessfulRun", "lastRunOutcome", "lastError", "weatherChange", "publishMode", "updatedAt"),
}


def _miles(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return round(3958.8 * 2 * math.asin(math.sqrt(a)), 1)


def resolve_point(lake: dict, source, cache, now: datetime) -> dict:
    """The lake's NWS grid cell and its nearest stations (cached static metadata). {outOfCoverage: True} outside NWS coverage."""
    e = cache.get(lake["id"], now) if cache else None
    if e:
        return e
    try:
        pt = decode_point(source.point(lake["lat"], lake["lon"]))
        if pt is None:
            raise FetchError("points response without a grid")
        st = decode_stations(source.stations(pt.observation_stations))[: C.MAX_STATIONS]
        e = {"gridpoint": pt.gridpoint, "forecastGridData": pt.forecast_grid_data, "cachedAt": C.iso(now),
             "stations": [{"id": s["id"], "name": s["name"], "distanceMi": _miles(lake["lat"], lake["lon"], s["lat"], s["lon"])} for s in st]}
    except OutOfCoverage:
        e = {"outOfCoverage": True, "cachedAt": C.iso(now)}
    if cache:
        cache.put(lake["id"], e)
    return e


def run(directory: list[dict], source, cache, published: dict, now: datetime, lake_ids: list[str] | None = None) -> dict:
    """-> {updates, states, report}. `published` is lakeId -> the last published state (for the planner); never raises for one lake."""
    now = now.replace(microsecond=0)
    lakes = [l for l in directory if not lake_ids or l["id"] in lake_ids]
    grids, obs = {}, {}
    states, ready, reasons, errors = {}, {}, {}, []
    for lake in lakes:
        lid = lake["id"]
        try:
            why = due(published.get(lid), now)
            if not why:
                states[lid] = published[lid]
                ready[lid] = readiness(published[lid])
                reasons[lid] = ["not due"]
                continue
            pt = resolve_point(lake, source, cache, now)
            if pt.get("outOfCoverage"):
                ready[lid], reasons[lid] = "BLOCKED", ["outside NWS coverage"]
                continue
            url = pt["forecastGridData"]
            if url not in grids:
                try:
                    grids[url] = decode_grid(source.grid(url))
                except (FetchError, OutOfCoverage) as e:
                    grids[url] = None
                    errors.append(f"grid {pt['gridpoint']}: {e}"[:200])
            sids = [s["id"] for s in pt["stations"]]
            for s in sids:
                if s not in obs:
                    try:
                        obs[s] = decode_observations(source.observations(s, now))
                    except (FetchError, OutOfCoverage) as e:
                        obs[s] = []
                        errors.append(f"observations {s}: {e}"[:200])
            rd = assemble(sids, {s: obs[s] for s in sids}, grids[url], now)
            st = build_state(lake, rd, pt, now)
            states[lid], ready[lid], reasons[lid] = st, readiness(st), why
        except Exception as e:                                   # one lake never stops the run
            ready[lid] = "DEGRADED" if lid in published else "DISCOVERED"
            errors.append(f"lake {lid}: {e!r} {traceback.format_exc()[-200:]}")
    for l in directory:
        ready.setdefault(l["id"], "DISCOVERED")
    return {"states": states, "readiness": ready, "reasons": reasons, "errors": errors,
            "updates": write_set(directory, states, ready, errors, now, computed={k for k, v in reasons.items() if v != ["not due"]})}


def change_summary(states: dict) -> dict:
    lv = {lid: (s.get("weatherChange") or {}) for lid, s in states.items()}
    changing = sorted(f"{lid}:{w.get('signature')}" for lid, w in lv.items() if w.get("level") == "CHANGE")
    return {"changeLakeCount": sum(1 for w in lv.values() if w.get("level") == "CHANGE"),
            "watchLakeCount": sum(1 for w in lv.values() if w.get("level") == "WATCH"),
            "steadyLakeCount": sum(1 for w in lv.values() if w.get("level") == "STEADY"),
            "signature": hashlib.sha256("\n".join(changing).encode()).hexdigest()[:16]}


def write_set(directory, states, ready, errors, now, computed) -> dict:
    now_iso = C.iso(now)
    u = {}
    for lid, st in states.items():
        if lid not in computed:
            continue
        k = C.lake_key(lid)
        u[f"lakes/{k}/states/{C.SLOT}"] = st
        u[f"lakeFleet/{k}/slots/{C.SLOT}"] = {"readiness": ready[lid], "kind": st["kind"], "stale": st["freshness"]["stale"],
                                               "changeLevel": st["weatherChange"]["level"], "tier": st["freshness"]["tier"],
                                               "freshUntil": st["freshness"]["freshUntil"], "lastUpdatedAt": now_iso}
        u[f"lakeFleet/{k}/readiness/{C.SLOT}"] = ready[lid]
        u[f"lakeFleet/{k}/modelVersions/{C.SLOT}"] = C.BRAIN_VERSION
    for lid, r in ready.items():
        if r == "BLOCKED":
            u[f"lakeFleet/{C.lake_key(lid)}/readiness/{C.SLOT}"] = r
    counts = {}
    for r in ready.values():
        counts[r] = counts.get(r, 0) + 1
    stale = sum(1 for s in states.values() if s["freshness"]["stale"])
    # A lake counts as computed only when its state carries at least one value (kind != "unavailable"): a lake whose every observation and
    # grid fetch failed has a state of nulls, and a run made only of those is FAILED, not PARTIAL (review of #234).
    computed_n = sum(1 for lid, st in states.items() if lid in computed and st.get("kind") != "unavailable")
    outcome = "FAILED" if errors and not computed_n else ("PARTIAL" if errors else "SUCCESS")
    health = "FAILED" if outcome == "FAILED" else ("WARNING" if errors or stale else "HEALTHY")
    reg = {
        "brainId": C.BRAIN_ID, "displayName": C.DISPLAY_NAME, "domain": C.DOMAIN, "question": C.QUESTION,
        "platform": {"implementation": "sector_brain_platform", "contract": "BRAIN_PLATFORM_CONTRACT.md v1.0", "conformant": True},
        "version": C.BRAIN_VERSION, "schemaVersion": C.SCHEMA_VERSION, "stalenessModel": "TIME", "dependsOn": [],
        "descriptor": {"components": {"weatherState": {"status": "CALIBRATION (internal; customer publication off)",
                                                       "inputs": ["NWS station observations (ASOS/AWOS)", "NWS forecast grid (NBM-based NDFD)"],
                                                       "staleness": f"per lake: freshness.freshUntil (adaptive, ceiling {C.CEILING_MIN} min after the observation)",
                                                       "recomputeWhen": ["nextCheckAt reached", "state stale", "brain or thresholds version changed"]}}},
        "readinessDefinitions": C.READINESS_DEFINITIONS, "stateKinds": C.STATE_KINDS, "thresholds": dict(C.THRESHOLDS),
        "thresholdsVersion": C.THRESHOLDS_VERSION, "sourceIds": list(C.SOURCE_IDS),
        "schedule": {"authority": "brain-orchestrator", "dueAfterHours": C.DUE_AFTER_HOURS, "running": False},
        "enabled": False, "health": health, "status": "CALIBRATION",
        "supportedLakeCount": sum(1 for r in ready.values() if r in ("CALIBRATION", "DEGRADED")), "directoryLakeCount": len(directory),
        "readinessCounts": counts, "staleLakeCount": stale, "staleAfterHours": C.STALE_AFTER_HOURS,
        # A run that computed at least one lake is a successful run, even if some station or grid fetch failed (PARTIAL is said explicitly in
        # lastRunOutcome). A FAILED run does not write lastSuccessfulRun at all, so the previous value stays (never written null).
        **({"lastSuccessfulRun": now_iso} if outcome != "FAILED" else {}),
        "lastRunOutcome": {"status": outcome, "at": now_iso, "computedLakeCount": computed_n, "errorCount": len(errors)},
        "lastError": {"at": now_iso, "message": errors[0][:300]} if errors else None,
        "weatherChange": change_summary(states), "publishMode": "DRY_RUN (no live writer in this version)", "updatedAt": now_iso,
    }
    for child, v in reg.items():
        u[f"brains/{C.BRAIN_ID}/{child}"] = v
    return u
