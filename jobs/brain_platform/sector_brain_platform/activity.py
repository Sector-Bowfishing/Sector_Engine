"""Activity events (contract section 7)."""
from __future__ import annotations

import datetime as dt
import re

from .enums import ACTIVITY_KIND, SEVERITY
from .timeutil import iso, parse_time

EVENT_ID = re.compile(r"^[0-9]{13}-[a-z0-9-]+-[0-9]{3}$")
KEEP_PER_BRAIN = 80
MAX_AGE_DAYS = 30


def event_id(at: dt.datetime | int, brain_id: str, n: int) -> str:
    """{ms13}-{brainId}-{nnn}: lexical order == time order across brains."""
    ms = at if isinstance(at, int) else int(at.timestamp() * 1000)
    return f"{ms:013d}-{brain_id}-{n:03d}"


def event(at: dt.datetime, brain_id: str, n: int, kind: str, title: str, severity: str,
          lake_id: str | None = None) -> dict:
    if kind not in ACTIVITY_KIND:
        raise ValueError(f"not an activity kind: {kind!r}")
    if severity not in SEVERITY:
        raise ValueError(f"not a severity: {severity!r}")
    e = {"id": event_id(at, brain_id, n), "at": iso(at), "kind": kind, "title": title, "brainId": brain_id, "severity": severity}
    if lake_id:
        e["lakeId"] = lake_id
    return e


def prune_activity(activity: dict | None, brain_id: str, now: dt.datetime,
                   keep: int = KEEP_PER_BRAIN, max_age_days: int = MAX_AGE_DAYS) -> dict:
    """Multi-path deletes for THIS brain's old events only, decided by the `at` field, never by key.

    Events whose `at` is missing or unparseable are kept (unknown stays unknown). Other brains' events
    and brain-less legacy events are never touched — a global sweep is the Orchestrator's job.
    """
    mine = [(k, e) for k, e in (activity or {}).items() if isinstance(e, dict) and e.get("brainId") == brain_id]
    cutoff = now - dt.timedelta(days=max_age_days)
    drop = {k for k, e in mine if (t := parse_time(e.get("at"))) is not None and t < cutoff}
    dated = sorted(((k, t) for k, e in mine if (t := parse_time(e.get("at"))) is not None), key=lambda kt: kt[1])
    if len(dated) > keep:
        drop |= {k for k, _ in dated[: len(dated) - keep]}
    return {f"activity/{k}": None for k in sorted(drop)}
