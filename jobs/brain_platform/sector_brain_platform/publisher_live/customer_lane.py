"""The Publisher's CUSTOMER-lane wiring (design note docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md §6, §8; Sector_Ops #51 P1).

After a verified live publication of a Brain that owns a customer copy, the Publisher job plans that Brain's copy with the existing pure
planner (customer_lake_level / customer_clarity / customer_water_temp) and writes it in ONE separate update, guarded so it can only touch
`customer/lakes/{lakeKey}/{copy}` for that Brain's own copy. The copy is never part of the Brain's atomic publication: a copy failure is
reported and never undoes or retries the publication.

Switches (passed in as `env`; this package never reads the environment, test_publisher_live_boundary):
  lake-brain     -> level       PUBLISHER_CUSTOMER_LAKE_LEVEL
  water-clarity  -> clarity     PUBLISHER_CUSTOMER_CLARITY
  water-temp     -> waterTemp   PUBLISHER_CUSTOMER_WATER_TEMP
  "1" = on. Any other value = off: nothing new is computed and every stored copy of that kind is withdrawn once with status UNKNOWN.
  ABSENT = not configured: the lane does nothing at all for that Brain (no read, no write), which is the default and today's behaviour.

The gates are the planners' own (readiness BETA or higher, publication, freshness, source kind). Nothing here relaxes them. A modeled
Water Temp state is copied as `status: ESTIMATE` with no range, valid for its lake-local day (customer_water_temp; owner approval P4,
Sector_Ops #51, 2026-11-15).
"""
from __future__ import annotations

import datetime as dt
import re

from ..keys import lake_key
from . import customer_clarity as CL
from . import customer_copies as CC
from . import customer_lake_level as LV
from . import customer_water_temp as WT

#: brain id -> (copy name, switch). Only these Brains have a customer copy written by this lane.
LANE = {
    "lake-brain": ("level", "PUBLISHER_CUSTOMER_LAKE_LEVEL"),
    "water-clarity": (CL.COPY, CC.SWITCHES[CL.COPY]),
    "water-temp": (WT.COPY, CC.SWITCHES[WT.COPY]),
}
SCHEMA = "sector-customer-lane-pass-v1"
_KEY = re.compile(r"^customer/lakes/([^/]+)/([A-Za-z]+)$")


def copy_name(brain_id: str):
    e = LANE.get(brain_id)
    return e[0] if e else None


def configured(brain_id: str, env) -> bool:
    """True when the Brain owns a customer copy AND its switch is present in `env` (any value). Absent = the lane is not configured."""
    e = LANE.get(brain_id)
    return bool(e) and isinstance(env, dict) and e[1] in env


def switched_on(brain_id: str, env) -> bool:
    e = LANE.get(brain_id)
    return bool(e) and isinstance(env, dict) and env.get(e[1]) == "1"


def key_allowed(brain_id: str, key: str) -> bool:
    """Only `customer/lakes/{k}/{copy}` for the Brain's own copy, with a key that the lake-key rule produces from some id (no `/`, `.`, `#`, `$`, `[`, `]`)."""
    name = copy_name(brain_id)
    m = _KEY.match(str(key).lstrip("/"))
    return bool(name and m and m.group(2) == name and not any(c in m.group(1) for c in ".#$[]"))


def assert_keys(brain_id: str, writes: dict) -> None:
    bad = sorted(k for k in writes if not key_allowed(brain_id, k))
    if bad:
        raise PermissionError(f"customer-lane write for {brain_id!r} refused on {bad[:5]}")


def _u(updates: dict) -> dict:
    return {str(k).lstrip("/"): v for k, v in (updates or {}).items()}


def readiness_from(updates: dict, brain_id: str):
    """The Brain's readiness (its registry `status`) from the write set: the child or the whole registry node. None when absent."""
    u = _u(updates)
    key = f"brains/{brain_id}"
    if isinstance(u.get(key + "/status"), str):
        return u[key + "/status"]
    node = u.get(key)
    return node.get("status") if isinstance(node, dict) and isinstance(node.get("status"), str) else None


def previous_from(stored, brain_id: str) -> dict:
    """{copyPath: copy} for the Brain's copy kind, from the stored `customer/lakes` node ({lakeKey: {copyName: copy}})."""
    name = copy_name(brain_id)
    out = {}
    if isinstance(stored, dict):
        for k, node in stored.items():
            if isinstance(node, dict) and isinstance(node.get(name), dict):
                out[f"customer/lakes/{k}/{name}"] = node[name]
    return out


def plan(brain_id: str, updates: dict, previous: dict, *, readiness, runner: str, publish_id: str, source_release: str, now: dt.datetime,
         env, eligible=None) -> tuple[dict, dict]:
    """-> ({copyPath: copy}, {lakeId: reason}) for one verified publication of `brain_id`. Pure. Not configured -> ({}, {})."""
    if not configured(brain_id, env):
        return {}, {}
    name = copy_name(brain_id)
    if name == "level":
        if not switched_on(brain_id, env):
            return CC.withdraw(previous, lambda lid: LV.unknown_copy(lid, source_release=source_release, now=now))
        return LV.plan(updates, previous, readiness=readiness, eligible=LV.eligible_lake_ids() if eligible is None else eligible,
                       source_release=source_release, now=now)
    mod = CL if name == CL.COPY else WT
    return mod.plan(updates, previous, readiness=readiness, runner=runner, publish_id=publish_id, now=now, env=env)


def write_pass(brain_id: str, result_updates: dict, record: dict, *, rtdb, env, runner: str, now: dt.datetime, eligible=None) -> dict | None:
    """Plan and apply the Brain's copy after a verified publication. `rtdb` exposes get(path) and update(dict). Returns a small report, or
    None when the lane is not configured for this Brain (nothing read, nothing written). Raises on a refused key (never expected)."""
    if not configured(brain_id, env):
        return None
    record = record or {}
    readiness = readiness_from(result_updates, brain_id)
    if readiness is None:
        st = rtdb.get(f"brains/{brain_id}/status")
        readiness = st if isinstance(st, str) else None
    previous = previous_from(rtdb.get("customer/lakes"), brain_id)
    writes, reasons = plan(brain_id, result_updates, previous, readiness=readiness, runner=runner, publish_id=record.get("publishId") or "",
                           source_release=record.get("knowledgeRelease") or "NONE", now=now, env=env, eligible=eligible)
    assert_keys(brain_id, writes)
    if writes:
        rtdb.update(writes)
    statuses = {}
    for c in writes.values():
        s = c.get("status") if isinstance(c, dict) else None
        statuses[s] = statuses.get(s, 0) + 1
    return {"schema": SCHEMA, "copy": copy_name(brain_id), "switchedOn": switched_on(brain_id, env), "readiness": readiness,
            "written": len(writes), "statuses": dict(sorted((str(k), v) for k, v in statuses.items())),
            "reasons": dict(sorted(_count(reasons).items()))}


def _count(reasons: dict) -> dict:
    out = {}
    for r in (reasons or {}).values():
        out[str(r)] = out.get(str(r), 0) + 1
    return out


def lake_keys(writes: dict) -> list:
    return sorted({k.split("/")[2] for k in writes})


__all__ = ["LANE", "configured", "switched_on", "key_allowed", "plan", "write_pass", "previous_from", "readiness_from", "lake_key"]
