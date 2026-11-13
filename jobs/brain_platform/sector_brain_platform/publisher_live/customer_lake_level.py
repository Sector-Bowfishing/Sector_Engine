"""The Publisher's CUSTOMER-lane copy of Lake level and trend (design note docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md §3, §6; Sector_Ops #47 item 5). DRAFT.

The customer Engine reads only `/customer/lakes/{lakeKey}/level` (schema sector-customer-lake-level-v1), never Lake's INTERNAL state. This module is the Publisher-side writer:
from one Lake publication's write set it plans the copy updates, applying the Brain-side gates 1-4 of the design note. Pure: no clock (the caller passes `now`), no I/O.

  1. readiness   Lake (`/brains/lake-brain/status`) is BETA or higher
  2. validated   the lake is on the owner-approved list (customer_lake_level_eligible.json = the Engine's validatedLakeIds; a test keeps them equal)
  3. publication the lake's state exists, its stored lakeId matches (lake keys are lossy) and it is not stale
  4. source      an observed operator pool or lake gauge -> AVAILABLE; a labelled nearby-gauge proxy -> ESTIMATE, trend only (Cortex lake.md LC-06); anything else -> no copy

A lake that had a copy and stops passing gets `status: UNKNOWN` written over it (never a stale value left standing). Nothing else from the INTERNAL record is copied.

NOT WIRED: the LivePublisher does not call this yet. Wiring it into Lake's atomic apply needs Lake CENTRAL (cutover), the CUSTOMER-lane family declared in Cortex (CG-3.1-8)
and the owner's approval; until then nothing writes `/customer/`.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from ..enums import READINESS_LADDER
from ..keys import lake_key

SCHEMA = "sector-customer-lake-level-v1"
BRAIN_ID = "lake-brain"
ELIGIBLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "customer_lake_level_eligible.json")
OBSERVED_SOURCES = ("DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE")
PROXY_SOURCES = ("NEARBY_GAUGE_PROXY",)
TRENDS = ("STABLE", "RISING", "FALLING", "RISING_RAPIDLY", "FALLING_RAPIDLY")


def copy_path(lake_id: str) -> str:
    return f"customer/lakes/{lake_key(lake_id)}/level"


def eligible_lake_ids(path: str = ELIGIBLE_FILE) -> frozenset:
    return frozenset(json.load(open(path, encoding="utf-8"))["lakeIds"])


def _time(s):
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float("inf") else None


def ready(readiness: str | None) -> bool:
    return readiness in READINESS_LADDER and READINESS_LADDER.index(readiness) >= READINESS_LADDER.index("BETA")


def copy_for(state, lake_id: str, *, readiness: str | None, eligible, source_release: str, now: dt.datetime) -> tuple[dict | None, str]:
    """-> (copy, reason). copy is None when no copy may be written for this lake (reason says which gate)."""
    if not ready(readiness):
        return None, "LAKE_NOT_BETA"
    if lake_id not in eligible:
        return None, "NOT_VALIDATED_HERE"
    if not isinstance(state, dict) or state.get("lakeId") != lake_id:
        return None, "NO_PUBLICATION"
    fresh = state.get("freshness") or {}
    until, observed = _time(fresh.get("freshUntil")), _time(state.get("observationTime"))
    if fresh.get("stale") is not False or until is None or observed is None or now > until:
        return None, "STALE"
    trend = state.get("trendState")
    base = {"schema": SCHEMA, "lakeId": lake_id, "observationTime": _iso(observed), "sourceAgeHours": _num(state.get("sourceAgeHours")),
            "trend": trend if trend in TRENDS else "UNKNOWN", "freshUntil": _iso(until), "brainId": BRAIN_ID, "sourceRelease": source_release, "writtenAt": _iso(now)}
    cap, kind = state.get("sourceCapability"), state.get("kind")
    if cap in OBSERVED_SOURCES and kind == "OBSERVED":
        elev = _num(state.get("currentElevationFt"))
        if elev is None:
            return None, "NO_VALUE"
        c = {**base, "status": "AVAILABLE", "elevationFt": elev, "change24hFt": _num((state.get("change") or {}).get("h24"))}
        if isinstance(state.get("datum"), str) and state["datum"]:
            c["datum"] = state["datum"]
        return c, "AVAILABLE"
    if cap in PROXY_SOURCES and kind == "PROXY":
        if base["trend"] == "UNKNOWN":
            return None, "NO_TREND"
        return {**base, "status": "ESTIMATE"}, "ESTIMATE"                       # trend only: no elevation, datum or change in feet (LC-06)
    return None, "NO_SOURCE"


def unknown_copy(lake_id: str, *, source_release: str, now: dt.datetime) -> dict:
    return {"schema": SCHEMA, "lakeId": lake_id, "status": "UNKNOWN", "brainId": BRAIN_ID, "sourceRelease": source_release, "writtenAt": _iso(now)}


def lake_states(updates: dict) -> dict:
    """{lakeId: state} from one Lake write set (`lakes/{key}/states/lake`), keyed by the state's own lakeId."""
    out = {}
    for k, v in (updates or {}).items():
        if k.lstrip("/").startswith("lakes/") and k.endswith("/states/lake") and isinstance(v, dict) and isinstance(v.get("lakeId"), str):
            if lake_key(v["lakeId"]) == k.lstrip("/").split("/")[1]:
                out[v["lakeId"]] = v
    return out


def plan(updates: dict, previous: dict, *, readiness: str | None, eligible, source_release: str, now: dt.datetime) -> tuple[dict, dict]:
    """-> ({copyPath: copy}, {lakeId: reason}). `previous` = {copyPath: copy} as stored now. A lake that passes gets its copy; a lake that had a
    copy (status not UNKNOWN) and stops passing, including one taken off the eligible list, gets UNKNOWN over it; every other lake gets nothing."""
    states = lake_states(updates)
    had = {c["lakeId"] for c in (previous or {}).values() if isinstance(c, dict) and isinstance(c.get("lakeId"), str)}
    writes, reasons = {}, {}
    for lake_id in sorted(set(eligible) | set(states) | had):
        copy, why = copy_for(states.get(lake_id), lake_id, readiness=readiness, eligible=eligible, source_release=source_release, now=now)
        reasons[lake_id] = why
        path = copy_path(lake_id)
        if copy is not None:
            writes[path] = copy
        elif isinstance((previous or {}).get(path), dict) and previous[path].get("status") != "UNKNOWN":
            writes[path] = unknown_copy(lake_id, source_release=source_release, now=now)
    return writes, reasons
