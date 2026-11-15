"""The Publisher's CUSTOMER-lane Water Temp copy, `customer/lakes/{k}/waterTemp` (Sector_Ops #53 spec §5). Wired by customer_lane.py after a verified publication, behind its switch (default off).

Schema sector-customer-water-temp-v1: {schema, lakeId, status, valueF, kind, observedAt, freshUntil, runner, publishId}.
Source: the Water Temp Brain's published per-lake state (`lakes/{k}/states/waterTemp`) and its `staleAfterHours` (the registry write
in the same write set). Gates, all fail closed:

  0. switch      PUBLISHER_CUSTOMER_WATER_TEMP=1 (default off; a stored copy is withdrawn with UNKNOWN once)
  1. readiness   the Water Temp Brain's status is BETA or higher
  2. publication the lake's state exists and its stored lakeId matches
  3. fresh       stale and evidenceStale are both False
  4. source      kind `measured` with a source observation time (lastObservationAt) -> AVAILABLE; kind `modeled` with its lake-local
                 day and zone -> ESTIMATE (see below)
  5. value       currentTempF is a finite number in degF
  6. not expired lastObservationAt is not more than 10 minutes in the future, and observedAt + staleAfterHours (the Brain's own rule) is not before now; that sum is the copy's freshUntil

Modeled lakes (owner approval, Sector_Ops #51, 2026-11-15, P4): the approved launch "Estimate" is copied as `status: ESTIMATE`,
`kind: modeled`, with no range (the schema has none). A modeled state has no source observation time and the copy may never use the
Brain's run time, so its time is the model's own valid time: the lake-local calendar day it was computed for (`lakeLocalDate` in
`lakeTimeZone`, the model is daily). observedAt = the start of that local day, freshUntil = the end of it; a day that is not the lake's
current local day (or a missing or unknown date or zone) gets no copy (STALE / NO_OBSERVATION_TIME).
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    return CC.stale_after_hours(updates, BRAIN_KEY)


def copy_for(state, lake_id: str, *, readiness: str | None, stale_hours, runner: str, publish_id: str, now: dt.datetime) -> tuple[dict | None, str]:
    if not lake_id:
        return None, "NO_PUBLICATION"
    if not CC.ready(readiness):
        return None, "WATER_TEMP_NOT_BETA"
    if not isinstance(state, dict) or state.get("lakeId") != lake_id:
        return None, "NO_PUBLICATION"
    if state.get("stale") is not False or state.get("evidenceStale") is not False:
        return None, "STALE"
    if state.get("kind") == "modeled":
        return _estimate(state, lake_id, runner=runner, publish_id=publish_id, now=now)
    if state.get("kind") != "measured":
        return None, "NO_SOURCE"
    observed = CC.utc(state.get("lastObservationAt"))
    if observed is None:
        return None, "NO_OBSERVATION_TIME"
    if CC.future(observed, now):
        return None, "STALE"
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


def _local_day(state):
    """(start, end) in UTC of the state's lake-local model day, or None when the date or zone is missing or invalid."""
    day, zone = state.get("lakeLocalDate"), state.get("lakeTimeZone")
    if not isinstance(day, str) or not isinstance(zone, str):
        return None
    try:
        tz = ZoneInfo(zone)
        d = dt.date.fromisoformat(day)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return None
    start = dt.datetime(d.year, d.month, d.day, tzinfo=tz)
    end = dt.datetime.combine(d + dt.timedelta(days=1), dt.time(0), tzinfo=tz)
    return start.astimezone(dt.timezone.utc), end.astimezone(dt.timezone.utc)


def _estimate(state, lake_id, *, runner, publish_id, now):
    """The approved modeled "Estimate" (P4): valid for its lake-local day only, never timed by the Brain's run."""
    span = _local_day(state)
    if span is None:
        return None, "NO_OBSERVATION_TIME"
    start, end = span
    if now < start or now >= end:
        return None, "STALE"
    value = CC._num(state.get("currentTempF"))
    if value is None or state.get("unit", "degF") != "degF":
        return None, "NO_VALUE"
    return {"schema": SCHEMA, "lakeId": lake_id, "status": "ESTIMATE", "valueF": value, "kind": "modeled", "observedAt": CC._iso(start),
            "freshUntil": CC._iso(end), "runner": CC.check_runner(runner), "publishId": publish_id}, "ESTIMATE"


def unknown_copy(lake_id: str, *, runner: str, publish_id: str) -> dict:
    return {"schema": SCHEMA, "lakeId": lake_id, "status": "UNKNOWN", "runner": CC.check_runner(runner), "publishId": publish_id}


def plan(updates: dict, previous: dict, *, readiness: str | None, runner: str, publish_id: str, now: dt.datetime, env) -> tuple[dict, dict]:
    states = CC.states_at(updates, SLOT)
    if not CC.enabled(COPY, env):
        return CC.withdraw(previous, lambda lid: unknown_copy(lid, runner=runner, publish_id=publish_id))
    hours = stale_after_hours(updates)
    return CC.plan_lakes(states, previous, path_for=copy_path,
                         copy_for=lambda lid: copy_for(states.get(lid), lid, readiness=readiness, stale_hours=hours, runner=runner,
                                                       publish_id=publish_id, now=now),
                         unknown_for=lambda lid: unknown_copy(lid, runner=runner, publish_id=publish_id))
