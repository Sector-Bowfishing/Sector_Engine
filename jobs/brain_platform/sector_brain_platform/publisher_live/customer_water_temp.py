"""The Publisher's CUSTOMER-lane Water Temp copy, `customer/lakes/{k}/waterTemp` (Sector_Ops #53 spec §5). DRAFT, NOT WIRED.

Schema sector-customer-water-temp-v1: {schema, lakeId, status, valueF, kind, observedAt, freshUntil, runner, publishId}.
Source: the Water Temp Brain's published per-lake state (`lakes/{k}/states/waterTemp`) and its `staleAfterHours` (the registry write
in the same write set). Gates, all fail closed:

  0. switch      PUBLISHER_CUSTOMER_WATER_TEMP=1 (default off)
  1. readiness   the Water Temp Brain's status is BETA or higher
  2. publication the lake's state exists and its stored lakeId matches
  3. fresh       stale and evidenceStale are both False
  4. source      kind `measured` with a source observation time (lastObservationAt) -> AVAILABLE
  5. value       currentTempF is a finite number in degF
  6. not expired observedAt + staleAfterHours (the Brain's own rule) is not before now; that sum is the copy's freshUntil

GAP (owner decision): a `modeled` state carries no source observation time (lastObservationAt is null; the Brain's only time is its run
time, which the copy may never use). Modeled lakes therefore get no copy (reason NO_OBSERVATION_TIME) and stay on the old path, although
spec §4 allows `kind: modeled` -> ESTIMATE. Writing them needs the Water Temp Brain to publish the model's valid time.
"""
from __future__ import annotations

import datetime as dt

from ..keys import lake_key
from . import customer_copies as CC

SCHEMA = "sector-customer-water-temp-v1"
COPY = "waterTemp"
SLOT = "waterTemp"
BRAIN_KEY = "brains/water-temp"


def copy_path(lake_id: str) -> str:
    return f"customer/lakes/{lake_key(lake_id)}/waterTemp"


def stale_after_hours(updates: dict):
    """The Brain's published staleAfterHours, from its registry write (whole node or the child); None when absent."""
    u = {k.lstrip("/"): v for k, v in (updates or {}).items()}
    if CC._num(u.get(BRAIN_KEY + "/staleAfterHours")) is not None:
        return u[BRAIN_KEY + "/staleAfterHours"]
    node = u.get(BRAIN_KEY)
    return CC._num(node.get("staleAfterHours")) if isinstance(node, dict) else None


def copy_for(state, lake_id: str, *, readiness: str | None, stale_hours, runner: str, publish_id: str, now: dt.datetime) -> tuple[dict | None, str]:
    if not CC.ready(readiness):
        return None, "WATER_TEMP_NOT_BETA"
    if not isinstance(state, dict) or state.get("lakeId") != lake_id:
        return None, "NO_PUBLICATION"
    if state.get("stale") is not False or state.get("evidenceStale") is not False:
        return None, "STALE"
    if state.get("kind") == "modeled":
        return None, "NO_OBSERVATION_TIME"
    if state.get("kind") != "measured":
        return None, "NO_SOURCE"
    observed = CC.utc(state.get("lastObservationAt"))
    if observed is None:
        return None, "NO_OBSERVATION_TIME"
    value = CC._num(state.get("currentTempF"))
    if value is None or state.get("unit", "degF") != "degF":
        return None, "NO_VALUE"
    if CC._num(stale_hours) is None or stale_hours <= 0:
        return None, "STALE"
    until = observed + dt.timedelta(hours=stale_hours)
    if now > until:
        return None, "STALE"
    return {"schema": SCHEMA, "lakeId": lake_id, "status": "AVAILABLE", "valueF": value, "kind": "measured", "observedAt": CC._iso(observed),
            "freshUntil": CC._iso(until), "runner": CC.check_runner(runner), "publishId": publish_id}, "AVAILABLE"


def unknown_copy(lake_id: str, *, runner: str, publish_id: str) -> dict:
    return {"schema": SCHEMA, "lakeId": lake_id, "status": "UNKNOWN", "runner": CC.check_runner(runner), "publishId": publish_id}


def plan(updates: dict, previous: dict, *, readiness: str | None, runner: str, publish_id: str, now: dt.datetime, env) -> tuple[dict, dict]:
    states = CC.states_at(updates, SLOT)
    if not CC.enabled(COPY, env):
        return {}, {lid: CC.NOT_ENABLED for lid in states}
    hours = stale_after_hours(updates)
    return CC.plan_lakes(states, previous, path_for=copy_path,
                         copy_for=lambda lid: copy_for(states.get(lid), lid, readiness=readiness, stale_hours=hours, runner=runner,
                                                       publish_id=publish_id, now=now),
                         unknown_for=lambda lid: unknown_copy(lid, runner=runner, publish_id=publish_id))
