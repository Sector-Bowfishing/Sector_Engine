"""The Publisher's CUSTOMER-lane generation (dam) binding, `customer/lakes/{k}/generationBinding` (Sector_Ops #53 spec §5). DRAFT, NOT WIRED.

Schema sector-customer-generation-binding-v1: {schema, lakeId, operatorId, damId, damName, cwmsOffice?, tvaCode?, updatedAt}.
Source: the Lake Brain's reviewed bindings contract (brains/lake/contracts/reviewed-lake-bindings-v1.json). Gates, all fail closed:

  0. switch      PUBLISHER_CUSTOMER_GENERATION_BINDING=1 (default off)
  1. readiness   the Lake Brain's status is BETA or higher
  2. contract    schema reviewed-lake-bindings-v1, owner lake-brain, and a review date (`reviewedAt`, else the date in `bindingVersion`)
  3. binding     the lake's reviewed record carries a `damBinding` {operatorId, damId, damName, cwmsOffice?, tvaCode?} with the three
                 required strings

GAP (documented in the PR): the Lake Brain does not publish dam bindings yet. reviewed-lake-bindings-v1 binds each lake to its POOL
level sources (`liveSourceIds`, e.g. a TVA pool gauge), not to the dam whose generation the tile shows, and has no dam id or name.
Nothing is derived from the pool ids (a pool gauge code is not a generation site code), so against today's contract every lake gets
no copy (reason NO_DAM_BINDING) and the Engine keeps its own TailwaterRegistry binding. `damBinding` is the proposed additive field.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re

from ..keys import lake_key
from . import customer_copies as CC

SCHEMA = "sector-customer-generation-binding-v1"
COPY = "generationBinding"
SOURCE_SCHEMA = "reviewed-lake-bindings-v1"
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
CONTRACT_FILE = os.path.join(REPO, "brains", "lake", "contracts", "reviewed-lake-bindings-v1.json")
OPTIONAL = ("cwmsOffice", "tvaCode")


def copy_path(lake_id: str) -> str:
    return f"customer/lakes/{lake_key(lake_id)}/generationBinding"


def load_contract(path: str = CONTRACT_FILE) -> dict:
    return json.load(open(path, encoding="utf-8"))


def reviewed_at(contract: dict):
    """The Brain's review time: `reviewedAt`, else the date in `bindingVersion` (bindings-YYYY-MM-DD.n). Never a run time."""
    t = CC._time(contract.get("reviewedAt"))
    if t is not None:
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    m = re.fullmatch(r"bindings-(\d{4}-\d{2}-\d{2})\.\d+", str(contract.get("bindingVersion", "")))
    return dt.datetime.fromisoformat(m.group(1)).replace(tzinfo=dt.timezone.utc) if m else None


def _records(contract: dict) -> dict:
    out = {}
    for r in contract.get("reviewed") or []:
        if isinstance(r, dict) and isinstance(r.get("lakeId"), str):
            out[r["lakeId"]] = r
    return out


def copy_for(record, lake_id: str, *, readiness: str | None, updated) -> tuple[dict | None, str]:
    if not CC.ready(readiness):
        return None, "LAKE_NOT_BETA"
    if not isinstance(record, dict) or record.get("lakeId") != lake_id:
        return None, "NO_PUBLICATION"
    if updated is None:
        return None, "NO_REVIEW_TIME"
    b = record.get("damBinding")
    if not isinstance(b, dict):
        return None, "NO_DAM_BINDING"
    if not all(isinstance(b.get(k), str) and b[k] for k in ("operatorId", "damId", "damName")):
        return None, "NO_VALUE"
    c = {"schema": SCHEMA, "lakeId": lake_id, "operatorId": b["operatorId"], "damId": b["damId"], "damName": b["damName"], "updatedAt": CC._iso(updated)}
    for k in OPTIONAL:
        if isinstance(b.get(k), str) and b[k]:
            c[k] = b[k]
    return c, "AVAILABLE"


def unknown_copy(lake_id: str, *, updated) -> dict:
    c = {"schema": SCHEMA, "lakeId": lake_id, "status": "UNKNOWN"}
    if updated is not None:
        c["updatedAt"] = CC._iso(updated)
    return c


def plan(contract: dict, previous: dict, *, readiness: str | None, env) -> tuple[dict, dict]:
    """-> ({copyPath: copy}, {lakeId: reason}) from the reviewed bindings contract. No clock is needed: a binding is reviewed configuration."""
    contract = contract if isinstance(contract, dict) else {}
    valid = contract.get("schema") == SOURCE_SCHEMA and contract.get("owner") == "lake-brain"
    records = _records(contract) if valid else {}
    if not CC.enabled(COPY, env):
        return {}, {lid: CC.NOT_ENABLED for lid in records}
    updated = reviewed_at(contract) if valid else None
    return CC.plan_lakes(records, previous, path_for=copy_path,
                         copy_for=lambda lid: copy_for(records.get(lid), lid, readiness=readiness, updated=updated),
                         unknown_for=lambda lid: unknown_copy(lid, updated=updated))
