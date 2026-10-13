"""The standard failure write path (contract section 10)."""
from __future__ import annotations

import datetime as dt

from .activity import event
from .timeutil import iso


def failure_writes(brain_id: str, message: str, now: dt.datetime, started: dt.datetime | None = None,
                   error_count: int = 1, job_id: str | None = None) -> dict:
    """One unit: health leaves, registry health + lastError, and a run.failed event."""
    at = iso(now)
    ev = event(now, brain_id, 0, "run.failed", f"{brain_id} run failed: {message[:160]}", "critical")
    out = {
        f"health/brains/{brain_id}/status": "FAILED",
        f"health/brains/{brain_id}/lastRun": at,
        f"health/brains/{brain_id}/latestError": message[:500],
        f"health/brains/{brain_id}/errorCount": error_count,
        f"brains/{brain_id}/health": "FAILED",
        f"brains/{brain_id}/lastError": {"at": at, "message": message[:500]},
        f"activity/{ev['id']}": ev,
    }
    if started is not None:
        out[f"health/brains/{brain_id}/durationMs"] = int((now - started).total_seconds() * 1000)
    if job_id:
        out[f"health/jobs/{job_id}/status"] = "FAILED"
        out[f"health/jobs/{job_id}/lastRun"] = at
        out[f"health/jobs/{job_id}/latestError"] = message[:500]
        out[f"health/jobs/{job_id}/running"] = False
    return out
