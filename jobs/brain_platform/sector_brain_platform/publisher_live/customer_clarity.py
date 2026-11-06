"""The Publisher's CUSTOMER-lane Water Clarity copy, `customer/lakes/{k}/clarity` (Sector_Ops #53 spec §5). DRAFT, NOT WIRED.

Schema sector-customer-clarity-v1: {schema, lakeId, status, centralFt, lowFt, highFt, confidence, observedAt, freshUntil, runner, publishId}.
Source: the Water Clarity Brain's published per-lake state (`lakes/{k}/states/waterClarity` in its write set). Gates, all fail closed:

  0. switch      PUBLISHER_CUSTOMER_CLARITY=1 (default off: nothing computed; a stored copy is withdrawn with UNKNOWN once)
  1. readiness   the Water Clarity Brain's status is BETA or higher (same rule as the level copy)
  2. publication the lake's state exists and its stored lakeId matches
  3. fresh       freshness.stale is False, evidenceStale is not True, evaluationTime and freshUntil parse with a zone, evaluationTime is
                 not more than 10 minutes in the future, and now <= min(freshUntil, evaluationTime + the Brain's staleAfterHours). The second
                 bound stops a new run re-publishing an old evaluation from looking fresh (freshUntil is run time + staleAfterHours)
  4. source      kind observed + basis OBSERVATION -> AVAILABLE; kind modeled + basis MODEL -> ESTIMATE; anything else
                 (FALLBACK neutral, unavailable) -> no copy
  5. value       clarityFt is a finite number

Values are copied from the state unchanged: centralFt = clarityFt, lowFt/highFt (only when the Brain published them),
confidence = engine.confidenceLabel. observedAt is the state's `evaluationTime` (the time of the Engine evaluation the estimate
restates; clarity-publication-v1 freshness.inputGeneratedAt), never the Brain's run time.
"""
from __future__ import annotations

import datetime as dt

from ..keys import lake_key
from . import customer_copies as CC

SCHEMA = "sector-customer-clarity-v1"
COPY = "clarity"
SLOT = "waterClarity"
CONFIDENCE = ("low", "medium", "high")
BRAIN_KEY = "brains/water-clarity"


def copy_path(lake_id: str) -> str:
    return f"customer/lakes/{lake_key(lake_id)}/clarity"


def copy_for(state, lake_id: str, *, readiness: str | None, stale_hours, runner: str, publish_id: str, now: dt.datetime) -> tuple[dict | None, str]:
    if not lake_id:
        return None, "NO_PUBLICATION"
    if not CC.ready(readiness):
        return None, "CLARITY_NOT_BETA"
    if not isinstance(state, dict) or state.get("lakeId") != lake_id:
        return None, "NO_PUBLICATION"
    fresh = state.get("freshness") or {}
    until, observed = CC.utc(fresh.get("freshUntil")), CC.utc(state.get("evaluationTime"))
    if fresh.get("stale") is not False or fresh.get("evidenceStale") is True or until is None or observed is None or CC.future(observed, now):
        return None, "STALE"
    if CC._num(stale_hours) is None or stale_hours <= 0:
        return None, "STALE"
    until = min(until, observed + dt.timedelta(hours=stale_hours))                  # never fresher than the evaluation it restates
    if now > until:
        return None, "STALE"
    kind, basis = state.get("kind"), state.get("basis")
    if kind == "observed" and basis == "OBSERVATION":
        status = "AVAILABLE"
    elif kind == "modeled" and basis == "MODEL":
        status = "ESTIMATE"
    else:
        return None, "NO_SOURCE"
    central = CC._num(state.get("clarityFt"))
    if central is None:
        return None, "NO_VALUE"
    c = {"schema": SCHEMA, "lakeId": lake_id, "status": status, "centralFt": central, "observedAt": CC._iso(observed), "freshUntil": CC._iso(until),
         "runner": CC.check_runner(runner), "publishId": publish_id}
    for k in ("lowFt", "highFt"):
        if CC._num(state.get(k)) is not None:
            c[k] = state[k]
    conf = (state.get("engine") or {}).get("confidenceLabel")
    if conf in CONFIDENCE:
        c["confidence"] = conf
    return c, status


def unknown_copy(lake_id: str, *, runner: str, publish_id: str) -> dict:
    return {"schema": SCHEMA, "lakeId": lake_id, "status": "UNKNOWN", "runner": CC.check_runner(runner), "publishId": publish_id}


def plan(updates: dict, previous: dict, *, readiness: str | None, runner: str, publish_id: str, now: dt.datetime, env) -> tuple[dict, dict]:
    """-> ({copyPath: copy}, {lakeId: reason}). `previous` = {copyPath: copy} as stored now."""
    states = CC.states_at(updates, SLOT)
    if not CC.enabled(COPY, env):
        return CC.withdraw(previous, lambda lid: unknown_copy(lid, runner=runner, publish_id=publish_id))
    hours = CC.stale_after_hours(updates, BRAIN_KEY)
    return CC.plan_lakes(states, previous, path_for=copy_path,
                         copy_for=lambda lid: copy_for(states.get(lid), lid, readiness=readiness, stale_hours=hours, runner=runner,
                                                       publish_id=publish_id, now=now),
                         unknown_for=lambda lid: unknown_copy(lid, runner=runner, publish_id=publish_id))
