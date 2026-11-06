"""Shared pieces of the conditions-consolidation CUSTOMER-lane copy writers (Sector_Ops #53, spec §5). DRAFT, NOT WIRED.

The four new copies (clarity, waterTemp, generationBinding, wind outlookModel) follow the Lake level copy exactly
(customer_lake_level.py; design note docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md): a pure planner per copy that
applies the Brain-side gates and returns {copyPath: copy}; a copy that stops passing gets `status: UNKNOWN` written over it once.
In addition each copy sits behind its own Publisher env switch (spec §5), default OFF: with the switch off the planner computes
nothing and writes nothing. Pure: no clock (the caller passes `now`), no I/O, and no environment read: the live package never reads the environment
(test_publisher_live_boundary), so whoever wires a planner passes its environment mapping in as `env` and the switch is evaluated on that.
"""
from __future__ import annotations

from collections.abc import Mapping

from .customer_lake_level import _iso, _num, _time, ready  # noqa: F401  (re-exported: one definition of each)

#: spec §5 switch for each copy; "1" turns it on, anything else (or absent) is off.
SWITCHES = {
    "clarity": "PUBLISHER_CUSTOMER_CLARITY",
    "waterTemp": "PUBLISHER_CUSTOMER_WATER_TEMP",
    "generationBinding": "PUBLISHER_CUSTOMER_GENERATION_BINDING",
    "windOutlookModel": "PUBLISHER_CUSTOMER_WIND_MODEL",
}
RUNNERS = ("pulse", "cloud", "engine")              # spec §4 `runner`
NOT_ENABLED = "NOT_ENABLED"


def enabled(copy_name: str, env) -> bool:
    """True only when the passed environment mapping sets the copy's switch to exactly "1". No mapping (None) is off."""
    return isinstance(env, Mapping) and env.get(SWITCHES[copy_name]) == "1"


def utc(s):
    """An ISO 8601 time WITH a zone, else None (a zoneless time cannot be compared and is never guessed)."""
    t = _time(s)
    return t if t is not None and t.tzinfo is not None else None


def check_runner(runner: str) -> str:
    if runner not in RUNNERS:
        raise ValueError(f"runner must be one of {RUNNERS}: {runner!r}")
    return runner


def plan_lakes(candidates, previous: dict, *, path_for, copy_for, unknown_for) -> tuple[dict, dict]:
    """The level copy's write rule, per lake: a lake that passes gets its copy; a lake that had a copy (status not UNKNOWN) and stops
    passing gets UNKNOWN over it; every other lake gets nothing. `candidates` = lake ids to consider (from the write set)."""
    had = {c["lakeId"] for c in (previous or {}).values() if isinstance(c, dict) and isinstance(c.get("lakeId"), str)}
    writes, reasons = {}, {}
    for lake_id in sorted(set(candidates) | had):
        copy, why = copy_for(lake_id)
        reasons[lake_id] = why
        path = path_for(lake_id)
        if copy is not None:
            writes[path] = copy
        elif isinstance((previous or {}).get(path), dict) and previous[path].get("status") != "UNKNOWN":
            writes[path] = unknown_for(lake_id)
    return writes, reasons


def states_at(updates: dict, slot: str) -> dict:
    """{lakeId: state} from one write set's `lakes/{key}/states/{slot}` entries, keyed by the state's own lakeId (keys are lossy)."""
    from ..keys import lake_key
    out = {}
    for k, v in (updates or {}).items():
        p = k.lstrip("/")
        if p.startswith("lakes/") and p.endswith(f"/states/{slot}") and isinstance(v, dict) and isinstance(v.get("lakeId"), str):
            if lake_key(v["lakeId"]) == p.split("/")[1]:
                out[v["lakeId"]] = v
    return out
