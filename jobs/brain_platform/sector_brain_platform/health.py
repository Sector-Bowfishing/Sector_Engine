"""Run health from counts (contract section 3)."""
from __future__ import annotations


def run_health(attempted: int, ok: int, failed: int, aborted: bool = False, partial: bool = False,
               publish_failed: bool = False) -> str:
    if aborted:
        return "FAILED"
    if attempted <= 0:
        return "UNKNOWN"
    if publish_failed:
        return "DEGRADED"
    unavailable = failed / attempted
    if unavailable > 0.25:
        return "DEGRADED"
    if unavailable >= 0.05 or partial:
        return "WARNING"
    return "HEALTHY"
