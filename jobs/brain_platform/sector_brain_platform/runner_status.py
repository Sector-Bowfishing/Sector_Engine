"""Runner status for Sector Ops (sector-runner-status-v1): what a registered runner outside Cloud Run is doing, read from the cloud.

The registered runner ("pulse") writes one small, sanitized JSON object every few minutes to the private artifact store at `exports/runners/pulse/status.json`
(under the runner prefix it already writes: no new bucket root). The Orchestrator, which already reads `exports/runners/`, copies a
whitelisted view of it into its control state (`/control/orchestratorV1/runners`) so Sector Ops can render it without any GCS access.

Pure builders. Nothing here decides what runs: the view is display only. Missing or unreadable status is reported as such (never a zero),
and a status older than STALE_MINUTES is marked stale, so an offline runner is visible.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from .timeutil import iso, parse_time

SCHEMA = "sector-runner-status-v1"
KEY = "exports/runners/pulse/status.json"
STALE_MINUTES = 15
MAX_JOBS = 40

# Whitelists: only these fields ever leave this module (defence in depth on top of the runner-side sanitizer).
_TOP = ("pulseVersion", "pulseCommit", "engineRevision", "state", "paused", "startedAt", "uptimeSeconds")
_JOB = ("id", "enabled", "runPolicy", "leaseOnly", "leaseHeld", "running", "lastStartedAt", "lastFinishedAt", "lastResult", "lastExitCode",
        "nextEligibleAt")
_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_TEXT = re.compile(r"[A-Za-z0-9 ._:+-]{0,64}")


def _clean(v):
    """Scalars only: booleans, numbers, and short plain text (no slashes, so no paths or URLs can pass through)."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str) and _TEXT.fullmatch(v):
        return v
    return None


def build_view(raw: bytes | str | None, now: dt.datetime, stale_minutes: int = STALE_MINUTES) -> dict:
    """The runners section. `raw` is the status object's bytes (None = absent)."""
    if raw is None:
        return {"pulse": {"available": False, "stale": True, "reason": "NO_STATUS", "checkedAt": iso(now)}}
    try:
        doc = json.loads(raw)
    except (TypeError, ValueError):
        return {"pulse": {"available": False, "stale": True, "reason": "UNREADABLE", "checkedAt": iso(now)}}
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return {"pulse": {"available": False, "stale": True, "reason": "WRONG_SCHEMA", "checkedAt": iso(now)}}
    at = parse_time(doc.get("generatedAt"))
    age = round((now - at).total_seconds() / 60, 1) if at else None
    view = {k: _clean(doc.get(k)) for k in _TOP if _clean(doc.get(k)) is not None}
    jobs = {}
    for j in (doc.get("jobs") or [])[:MAX_JOBS]:
        if not isinstance(j, dict) or not _ID.fullmatch(str(j.get("id") or "")):
            continue
        jobs[j["id"]] = {k: _clean(j.get(k)) for k in _JOB if k != "id" and _clean(j.get(k)) is not None}
    view.update({"available": True, "generatedAt": iso(at) if at else None, "ageMinutes": age,
                 "stale": at is None or age is None or age > stale_minutes or age < -5,
                 "reason": None if (at and age is not None and -5 <= age <= stale_minutes) else ("NO_TIMESTAMP" if at is None else "STALE"),
                 "checkedAt": iso(now), "jobs": jobs})
    return {"pulse": {k: v for k, v in view.items() if v is not None}}


def read_view(store, now: dt.datetime) -> dict:
    """Read the status object through the Orchestrator's runner view. Any read error is reported in the view, never raised."""
    try:
        return build_view(store.get(KEY), now)
    except Exception as e:                                       # noqa: BLE001 - display only: an unreadable status is a state, not a failure
        return {"pulse": {"available": False, "stale": True, "reason": f"READ_FAILED {type(e).__name__}", "checkedAt": iso(now)}}
