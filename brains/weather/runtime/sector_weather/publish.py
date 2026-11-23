"""Weather Brain run: plan -> fetch -> compute -> write set. The write set is ONE flat multi-path update over Weather-owned paths only
(the families registered for `weather` in sector_brain_platform.publisher.registry). `--dry-run` puts it into the platform's in-memory store
(ownership and key checks included) and dumps it to a file. `run.py --write` applies the SAME write set through writer.RtdbWriter, and only with
an APPROVED knowledge release AND WEATHER_WRITE_APPROVED=1; the Brain is registered DISABLED, so nothing starts it (WEATHER_BRAIN_PLAN.md §6)."""
from __future__ import annotations

import hashlib
import math
import re
import traceback
from datetime import datetime

from . import contract as C
from .client import POINTS_404_BLOCK_RUNS, POINTS_404_BLOCK_SPAN_HOURS, FetchError, Moved, OutOfCoverage, PointsUnavailable, in_us_area
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
    """The lake's NWS grid cell and its nearest stations (cached static metadata). {outOfCoverage: True} outside NWS coverage.
    Raises PointsUnavailable for a /points failure that is an outage, not out of coverage (client module docstring)."""
    return _resolve(lake, source, cache, now)[0]


def _resolve(lake: dict, source, cache, now: datetime, refresh: bool = False) -> tuple[dict, bool]:
    """(entry, from_cache). refresh=True skips the cache (revalidation after a 404/redirect on a URL the cache gave). A /points 404 inside the
    US area is an outage (PointsUnavailable, nothing cached) until it has persisted (PointCache.record_points_404); outside it, BLOCKED."""
    e = cache.get(lake, now) if cache and not refresh else None
    if e:
        return e, True
    try:
        pt = decode_point(source.point(lake["lat"], lake["lon"]))
        if pt is None:
            raise FetchError("points response without a grid")
        st = decode_stations(source.stations(pt.observation_stations))[: C.MAX_STATIONS]
        e = {"gridpoint": pt.gridpoint, "forecastGridData": pt.forecast_grid_data, "cachedAt": C.iso(now),
             "stations": [{"id": s["id"], "name": s["name"], "distanceMi": _miles(lake["lat"], lake["lon"], s["lat"], s["lon"])} for s in st]}
    except PointsUnavailable:
        raise
    except FetchError as err:                                    # 5xx / transport after the client's retries: an outage like a US 404
        raise PointsUnavailable(f"/points or stations unavailable for {lake['lat']},{lake['lon']}: {err}"[:200]) from None
    except OutOfCoverage:
        if not in_us_area(lake["lat"], lake["lon"]):
            e = {"outOfCoverage": True, "reason": "outside the US NWS area", "cachedAt": C.iso(now)}
        elif cache and cache.record_points_404(lake, now):
            e = {"outOfCoverage": True, "reason": f"/points 404 on {POINTS_404_BLOCK_RUNS}+ consecutive runs over "
                                                  f"{POINTS_404_BLOCK_SPAN_HOURS}+ h", "cachedAt": C.iso(now)}
        else:
            raise PointsUnavailable(f"/points 404 at {lake['lat']},{lake['lon']} inside the US NWS area: treated as an outage, retried next run")
    if cache:
        cache.put(lake, e)
    return e, False


_GRIDPOINT = re.compile(r"/gridpoints/([A-Z]{3})/(\d+),(\d+)")


def _store_redirect(lake: dict, pt: dict, location: str | None, cache) -> None:
    """A grid URL that redirects: remember the target, so the next run asks it directly (at most one redirect per lake per run)."""
    if not (cache and location):
        return
    m = _GRIDPOINT.search(location)
    cache.put(lake, {**{k: v for k, v in pt.items() if k != "revalidate"}, "forecastGridData": location,
                     **({"gridpoint": f"{m.group(1)}/{m.group(2)},{m.group(3)}"} if m else {})})


def _fetch_grid(source, url: str, pt: dict, grids: dict, errors: list, lake: dict | None = None, cache=None) -> None:
    if url in grids:
        return
    try:
        grids[url] = decode_grid(source.grid(url))
    except Moved as e:
        grids[url] = decode_grid(e.doc) if e.doc is not None else None
        if e.doc is None:
            errors.append(f"grid {pt['gridpoint']}: {e}"[:200])
        elif lake is not None:
            _store_redirect(lake, pt, e.location, cache)
    except (FetchError, OutOfCoverage) as e:
        grids[url] = None
        errors.append(f"grid {pt['gridpoint']}: {e}"[:200])


def _fresh_until(state: dict | None, now: datetime) -> bool:
    from .nws import parse_time
    t = parse_time(((state or {}).get("freshness") or {}).get("freshUntil"))
    return t is not None and now < t


DRY_RUN_MODE = "DRY_RUN (no live writer in this version)"
LIVE_MODE = "LIVE: direct platform write (internal CALIBRATION only; Publisher cutover NOT_STARTED)"


def run(directory: list[dict], source, cache, published: dict, now: datetime, lake_ids: list[str] | None = None,
        publish_mode: str = DRY_RUN_MODE) -> dict:
    """-> {updates, states, report}. `published` is lakeId -> the last published state (for the planner); never raises for one lake."""
    now = now.replace(microsecond=0)
    lakes = [l for l in directory if not lake_ids or l["id"] in lake_ids]
    grids, obs, stale_urls = {}, {}, set()
    states, ready, reasons, errors, kept = {}, {}, {}, [], set()

    def outage(lid: str, err: Exception) -> None:
        """/points unavailable (an outage): keep the last state while it is fresh (not rewritten), else no state this run."""
        errors.append(f"lake {lid}: {err}"[:200])
        if _fresh_until(published.get(lid), now):
            states[lid] = published[lid]
            kept.add(lid)
            ready[lid] = readiness(published[lid])
            reasons[lid] = ["points lookup failed (NWS outage); last state kept while fresh"]
        else:
            ready[lid] = "DEGRADED" if lid in published else "DISCOVERED"

    def revalidate(lake: dict, old: dict) -> tuple[dict, bool, bool]:
        """(entry, from_cache, ok): re-resolve /points once; on failure keep the old entry (and it stays in the cache)."""
        try:
            fresh, _ = _resolve(lake, source, cache, now, refresh=True)
            cache.stats["revalidated"] += 1
            if not fresh.get("outOfCoverage"):
                fresh = {**fresh, "revalidatedAt": C.iso(now)}
                cache.put(lake, fresh)
            return fresh, False, True
        except PointsUnavailable as err:
            errors.append(f"revalidate {lake['id']}: {err}"[:200])
            return old, True, False

    for lake in lakes:
        lid = lake["id"]
        try:
            why = due(published.get(lid), now)
            if not why:
                states[lid] = published[lid]
                ready[lid] = readiness(published[lid])
                reasons[lid] = ["not due"]
                continue
            grid_known_bad = tried = False
            try:
                pt, cached = _resolve(lake, source, cache, now)
            except PointsUnavailable as err:
                old = cache.fallback(lake) if cache else None
                if old is None:
                    outage(lid, err)
                    continue
                errors.append(f"lake {lid}: {err}; using the stored (expired) grid entry"[:200])
                pt, cached, tried = old, True, True               # the expired entry, as a failed revalidation keeps it; no retry this run
            if cached and not pt.get("outOfCoverage") and (pt.get("revalidate") or pt["forecastGridData"] in stale_urls):
                old_url, tried = pt["forecastGridData"], True
                pt, cached, ok = revalidate(lake, pt)
                grid_known_bad = not ok and old_url in stale_urls
            if pt.get("outOfCoverage"):
                ready[lid], reasons[lid] = "BLOCKED", [f"outside NWS coverage ({pt.get('reason', 'NWS /points 404')})"]
                continue
            url = pt["forecastGridData"]
            if grid_known_bad:
                grids.setdefault(url, None)
            if url not in grids:
                try:
                    grids[url] = decode_grid(source.grid(url))
                except (Moved, OutOfCoverage) as e:
                    if cached and not tried:                     # the cached resolution is stale: revalidate /points once, in this run
                        stale_urls.add(url)
                        pt, cached, ok = revalidate(lake, pt)
                        if not ok:                               # outage while revalidating: the old entry stays; no grid this run
                            grids[url] = None
                            errors.append(f"grid {pt['gridpoint']}: {e}"[:200])
                        elif pt.get("outOfCoverage"):
                            ready[lid], reasons[lid] = "BLOCKED", [f"outside NWS coverage ({pt.get('reason')})"]
                            continue
                        else:
                            url = pt["forecastGridData"]
                            _fetch_grid(source, url, pt, grids, errors, lake, cache)
                    elif isinstance(e, Moved) and e.doc is not None:
                        grids[url] = decode_grid(e.doc)          # the redirected body as before; the target is remembered
                        _store_redirect(lake, pt, e.location, cache)
                    else:
                        grids[url] = None
                        errors.append(f"grid {pt['gridpoint']}: {e}"[:200])
                except FetchError as e:
                    grids[url] = None
                    errors.append(f"grid {pt['gridpoint']}: {e}"[:200])
            sids = [s["id"] for s in pt["stations"]]
            for s in sids:
                if s not in obs:
                    try:
                        obs[s] = decode_observations(source.observations(s, now))
                    except Moved as e:                           # a moved station: use what NWS sent, re-resolve the stations next run
                        obs[s] = decode_observations(e.doc) if e.doc is not None else []
                        if e.doc is None:
                            errors.append(f"observations {s}: {e}"[:200])
                        if cached:
                            cache.mark_revalidate(lake, now)
                    except (FetchError, OutOfCoverage) as e:
                        obs[s] = []
                        errors.append(f"observations {s}: {e}"[:200])
                        if cached and isinstance(e, OutOfCoverage):
                            cache.mark_revalidate(lake, now)     # a cached station that answers 404: re-resolve next run (old entry kept)
            rd = assemble(sids, {s: obs[s] for s in sids}, grids[url], now)
            st = build_state(lake, rd, pt, now)
            states[lid], ready[lid], reasons[lid] = st, readiness(st), why
        except Exception as e:                                   # one lake never stops the run
            ready[lid] = "DEGRADED" if lid in published else "DISCOVERED"
            errors.append(f"lake {lid}: {e!r} {traceback.format_exc()[-200:]}")
    for l in directory:
        ready.setdefault(l["id"], "DISCOVERED")
    return {"states": states, "readiness": ready, "reasons": reasons, "errors": errors,
            "updates": write_set(directory, states, ready, errors, now,
                                 computed={k for k, v in reasons.items() if v != ["not due"] and k not in kept},
                                 publish_mode=publish_mode)}


def change_summary(states: dict) -> dict:
    lv = {lid: (s.get("weatherChange") or {}) for lid, s in states.items()}
    changing = sorted(f"{lid}:{w.get('signature')}" for lid, w in lv.items() if w.get("level") == "CHANGE")
    return {"changeLakeCount": sum(1 for w in lv.values() if w.get("level") == "CHANGE"),
            "watchLakeCount": sum(1 for w in lv.values() if w.get("level") == "WATCH"),
            "steadyLakeCount": sum(1 for w in lv.values() if w.get("level") == "STEADY"),
            "signature": hashlib.sha256("\n".join(changing).encode()).hexdigest()[:16]}


def write_set(directory, states, ready, errors, now, computed, publish_mode: str = DRY_RUN_MODE) -> dict:
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
        "weatherChange": change_summary(states), "publishMode": publish_mode, "updatedAt": now_iso,
    }
    for child, v in reg.items():
        u[f"brains/{C.BRAIN_ID}/{child}"] = v
    return u
