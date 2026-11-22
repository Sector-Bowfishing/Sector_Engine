"""How long a lake's weather state counts as current, and when to look again. Pure. The Lake Brain's adaptive-freshness shape (#216,
LakeLevelValidity.swift), with the tier taken from the weather-change signal instead of the lake level:

    freshUntil  = min(observedAt + CEILING, max(observedAt + tierWindow, now + REFRESH_LATENCY))
    nextCheckAt = CHANGE / WATCH: now + RECHECK (every hourly grant)
                  STEADY:         max(now + RECHECK, min(now + STEADY_RECHECK_MAX, freshUntil - REFRESH_LATENCY))

The tier window is counted from the OBSERVATION, the latency floor from the RUN (so a correct value is never withdrawn before the next
grant's replacement can land), and the ceiling bounds both: a reading more than 4 h old is never current, however steady the weather.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import contract as C


def decide(level: str, observed_at: datetime | None, now: datetime) -> dict:
    tier = level if level in C.TIER_WINDOW_MIN else "WATCH"
    if observed_at is None:
        # No observation at all: nothing is current; look again at the next grant.
        return {"tier": tier, "freshUntil": C.iso(now), "nextCheckAt": C.iso(now + timedelta(minutes=C.RECHECK_MIN)), "stale": True,
                "observedAt": None, "reason": f"{tier}: no observation; nothing is presented as current"}
    m = lambda x: timedelta(minutes=x)
    ceiling = observed_at + m(C.CEILING_MIN)
    wanted = observed_at + m(C.TIER_WINDOW_MIN[tier])
    floor = now + m(C.REFRESH_LATENCY_MIN)
    fresh_until = min(ceiling, max(wanted, floor))
    if tier == "STEADY":
        nxt = max(now + m(C.RECHECK_MIN), min(now + m(C.STEADY_RECHECK_MAX_MIN), fresh_until - m(C.REFRESH_LATENCY_MIN)))
    else:
        nxt = now + m(C.RECHECK_MIN)
    bound = " (the 4 h ceiling)" if fresh_until == ceiling else (" (held to the refresh latency)" if fresh_until == floor and floor > wanted else "")
    minutes = int(round((fresh_until - observed_at).total_seconds() / 60))
    return {"tier": tier, "freshUntil": C.iso(fresh_until), "nextCheckAt": C.iso(nxt), "stale": fresh_until <= now, "observedAt": C.iso(observed_at),
            "reason": f"{tier}: current for {minutes} min after the observation{bound}"}


def due(published: dict | None, now: datetime, brain_version: str = C.BRAIN_VERSION) -> list[str]:
    """Why this lake must be recomputed now ([] = not due). The LakeBrainPlanner rule set."""
    if not published:
        return ["nothing published yet"]
    reasons = []
    if published.get("brainVersion") != brain_version:
        reasons.append(f"brain version {published.get('brainVersion')} -> {brain_version}")
    if published.get("thresholdsVersion") != C.THRESHOLDS_VERSION:
        reasons.append(f"thresholds {published.get('thresholdsVersion')} -> {C.THRESHOLDS_VERSION}")
    f = published.get("freshness") or {}
    from .nws import parse_time
    nxt, gen = parse_time(f.get("nextCheckAt")), parse_time(published.get("generatedAt"))
    if f.get("stale"):
        reasons.append("published state is stale")
    if nxt is None or now >= nxt - timedelta(minutes=C.PLANNER_TOLERANCE_MIN):
        reasons.append(f"nextCheckAt {f.get('nextCheckAt')} reached")
    if gen is None or (now - gen).total_seconds() > C.STALE_AFTER_HOURS * 3600:
        reasons.append(f"published state older than {C.STALE_AFTER_HOURS:g} h")
    return reasons
