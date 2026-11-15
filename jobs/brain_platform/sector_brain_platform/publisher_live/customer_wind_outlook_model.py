"""The Publisher's CUSTOMER-lane Wind outlook-model decision, `customer/wind/outlookModel` (Sector_Ops #53 spec §5). DRAFT, NOT WIRED.

Schema sector-customer-wind-outlook-model-v1: {schema, tonight: "best_match", nights2to7: "ncep_nbm_conus", decidedBy, evidence, updatedAt}.
It replaces the Engine env SECTOR_WIND_FORECAST_MODEL (#125) with a Brain-owned decision. Gates, all fail closed:

  0. switch      PUBLISHER_CUSTOMER_WIND_MODEL=1 (default off; a stored decision is withdrawn with UNKNOWN once)
  1. readiness   the Wind Brain's status is BETA or higher
  2. publication the Wind registry write (`brains/wind/activeProductionModel`) carries an `outlookModel` block
                 {tonight, nights2to7, decidedBy, evidence, decidedAt}
  3. values      tonight is `best_match` (WS-5: all of tonight stays best_match) and nights2to7 is a known model id
  4. fresh       decidedAt (the Brain's decision time; never a run time) is no more than 14 days before now and not more than 10 minutes after it

GAP (documented in the PR): the Wind Brain does not publish an outlook-model decision yet. Its activeProductionModel describes the
served model (Open-Meteo Best Match) and has no `outlookModel` block, so today the writer writes nothing (NO_PUBLICATION). The block is
the proposed additive field, written by the Wind Brain when the owner records the decision.
"""
from __future__ import annotations

import datetime as dt

from . import customer_copies as CC

SCHEMA = "sector-customer-wind-outlook-model-v1"
COPY = "windOutlookModel"
PATH = "customer/wind/outlookModel"
TONIGHT = "best_match"
MODELS = ("best_match", "ncep_nbm_conus")
MAX_AGE = dt.timedelta(days=14)
SOURCE_KEY = "brains/wind/activeProductionModel"


def decision(updates: dict):
    u = {k.lstrip("/"): v for k, v in (updates or {}).items()}
    apm = u.get(SOURCE_KEY)
    if apm is None and isinstance(u.get("brains/wind"), dict):
        apm = u["brains/wind"].get("activeProductionModel")
    return apm.get("outlookModel") if isinstance(apm, dict) else None


def copy_for(block, *, readiness: str | None, now: dt.datetime) -> tuple[dict | None, str]:
    if not CC.ready(readiness):
        return None, "WIND_NOT_BETA"
    if not isinstance(block, dict):
        return None, "NO_PUBLICATION"
    if block.get("tonight") != TONIGHT or block.get("nights2to7") not in MODELS:
        return None, "NO_VALUE"
    if not (isinstance(block.get("decidedBy"), str) and block["decidedBy"]) or not isinstance(block.get("evidence"), str):
        return None, "NO_VALUE"
    decided = CC.utc(block.get("decidedAt"))
    if decided is None or now > decided + MAX_AGE or CC.future(decided, now):
        return None, "STALE"
    return {"schema": SCHEMA, "tonight": TONIGHT, "nights2to7": block["nights2to7"], "decidedBy": block["decidedBy"], "evidence": block["evidence"],
            "updatedAt": CC._iso(decided)}, "AVAILABLE"


def unknown_copy() -> dict:
    return {"schema": SCHEMA, "status": "UNKNOWN"}


def plan(updates: dict, previous, *, readiness: str | None, now: dt.datetime, env) -> tuple[dict, str]:
    """-> ({PATH: copy} or {}, reason). `previous` = the copy stored at PATH now (or None). A decision that stops passing gets UNKNOWN once."""
    if not CC.enabled(COPY, env):
        if isinstance(previous, dict) and previous and previous.get("status") != "UNKNOWN":
            return {PATH: unknown_copy()}, CC.NOT_ENABLED
        return {}, CC.NOT_ENABLED
    copy, why = copy_for(decision(updates), readiness=readiness, now=now)
    if copy is not None:
        return {PATH: copy}, why
    if isinstance(previous, dict) and previous and previous.get("status") != "UNKNOWN":
        return {PATH: unknown_copy()}, why
    return {}, why
