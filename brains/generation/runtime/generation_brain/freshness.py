"""How long a dam's published release picture counts as current, and when to read its sources again. Pure; no I/O.

Owner direction (Michael, 2026-11-22, Sector_Ops #51): refresh "when release schedules change", sooner when a release starts or stops; the
source-access rule caps every official source at one read per hour. So the cadence is chosen per dam, per run:

  TRANSITION  the operator's schedule changed since the last published state; or the status changed (a release started or stopped);
              or the schedule starts or stops generation within the next 120 min; or the measured release moved by >= 25 % and
              >= 500 cfs over the last 3 h                                                               -> read again in 60 min
  ACTIVE      water is moving (GENERATING / SPILLING / RELEASING) and none of the above              -> 120 min
  STEADY      the dam is OFF and nothing is scheduled to change soon                                  -> 180 min, but never later than
              60 min before the next scheduled start or stop
  UNKNOWN     nothing usable came back (source down or stale)                                         -> 120 min (back off, do not hammer)
  Schedule horizon: when the posted schedule ends within 12 h (the next day is not posted yet), the next read is at most 120 min away,
  so a new posting is picked up the same afternoon.
The 60 min floor is the access rule: no series is read more than once an hour, whatever the tier.

The published value then stays current for:
    freshUntil = min(reading + ceiling, max(reading + tierWindow, now + refreshLatency))
  ceiling         the source's own stale rule (lag + 3 x cadence): a reading is never presented as current once its source is overdue.
  refreshLatency  one hourly grant + one publish cycle + run time (150 min), counted from the run, so a correct value is never withdrawn
                  before its replacement can arrive (the Lake Brain rule, LakeLevelValidity).
  tierWindow      TRANSITION 60, ACTIVE 120, STEADY 240, UNKNOWN 0 (min).
  ceiling is per series: the earliest stale limit among the release series actually used (assess.measuredCurrentUntil).
A SCHEDULE_ONLY state is current until the end of the scheduled window that covers now, and never beyond now + 6 h; any status that rests
on the schedule hour (statusBasis SCHEDULE or MEASURED_AND_SCHEDULE) is capped at the end of that window. A DOWNSTREAM_ONLY state (USGS gauge,
dam status UNKNOWN) follows the gauge's own stale limit.
Thresholds are pre-set, not fitted; the pre-registered week-long schedule comparison (docs/brains/GENERATION_BRAIN_PLAN.md) tunes them."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import contract as C
from .contract import iso, parse_iso

FLOOR_MIN = 60
RECHECK_MIN = {C.TIER_TRANSITION: 60, C.TIER_ACTIVE: 120, C.TIER_STEADY: 180, C.TIER_UNKNOWN: 120}
WINDOW_MIN = {C.TIER_TRANSITION: 60, C.TIER_ACTIVE: 120, C.TIER_STEADY: 240, C.TIER_UNKNOWN: 0}
REFRESH_LATENCY_MIN = 150
SOON_MIN = 120
HORIZON_H = 12
SCHEDULE_ONLY_MAX_H = 6
MOVE_FRACTION, MOVE_CFS, MOVE_HOURS = 0.25, 500.0, 3
PLANNER_TOLERANCE_MIN = 10


def schedule_fingerprint(schedule: dict | None) -> str | None:
    if not schedule:
        return None
    return "|".join(f"{w['start']}>{w['end']}:{w.get('unitsOn')}:{w.get('unitsOnIsMinimum')}:{w.get('generationMw')}" for w in schedule["windows"])


def moved(history: list[dict], now: datetime) -> float | None:
    rows = [r for r in history if r.get("dischargeCfs") is not None]
    if len(rows) < 2:
        return None
    last = rows[-1]
    cut = parse_iso(last["at"]) - timedelta(hours=MOVE_HOURS)
    base = [r for r in rows if parse_iso(r["at"]) <= cut]
    if not base:
        return None
    b = base[-1]["dischargeCfs"]
    d = last["dischargeCfs"] - b
    return d if abs(d) >= MOVE_CFS and abs(d) >= MOVE_FRACTION * max(abs(b), 1.0) else None


def tier(a: dict, prev: dict | None, now: datetime) -> tuple[str, str]:
    rel, sched = a["release"], a["schedule"]
    if a["kind"] == C.UNAVAILABLE:
        return C.TIER_UNKNOWN, "no usable reading"
    prev_rel = (prev or {}).get("release") or {}
    if prev and (prev.get("provenance") or {}).get("scheduleFingerprint") != schedule_fingerprint(sched) and sched:
        return C.TIER_TRANSITION, "the operator's schedule changed since the last published state"
    if prev and prev_rel.get("status") not in (None, C.UNKNOWN) and rel["status"] != prev_rel.get("status"):
        return C.TIER_TRANSITION, f"release status changed {prev_rel.get('status')} -> {rel['status']}"
    for k, what in (("nextReleaseStartAt", "starts"), ("nextShutdownAt", "stops")):
        t = parse_iso((sched or {}).get(k))
        if t and timedelta(0) <= t - now <= timedelta(minutes=SOON_MIN):
            return C.TIER_TRANSITION, f"the schedule {what} generation at {iso(t)}"
    m = moved(a["history"], now)
    if m is not None:
        return C.TIER_TRANSITION, f"measured release moved {m:+.0f} cfs in {MOVE_HOURS} h"
    if rel["status"] in (C.GENERATING, C.SPILLING, C.RELEASING):
        return C.TIER_ACTIVE, f"{rel['status'].lower()}"
    if rel["status"] == C.OFF:
        return C.TIER_STEADY, "off, no scheduled change soon"
    return C.TIER_UNKNOWN, "status unknown"


def decide(a: dict, prev: dict | None, now: datetime) -> dict:
    t, why = tier(a, prev, now)
    recheck = RECHECK_MIN[t]
    sched = a["schedule"] or {}
    if t == C.TIER_STEADY:
        nxt = [parse_iso(sched.get(k)) for k in ("nextReleaseStartAt", "nextShutdownAt") if sched.get(k)]
        if nxt:
            recheck = min(recheck, max(FLOOR_MIN, int((min(nxt) - now).total_seconds() // 60) - 60))
    covers = parse_iso(sched.get("scheduleCoversUntil"))
    if covers is not None and covers - now <= timedelta(hours=HORIZON_H):
        recheck = min(recheck, 120)
        why += "; the posted schedule ends within 12 h (watching for the next posting)"
    recheck = max(FLOOR_MIN, recheck)
    floor = now + timedelta(minutes=REFRESH_LATENCY_MIN)
    rel = a["release"]
    if a["kind"] == C.OBSERVED and a.get("measuredCurrentUntil"):
        obs = parse_iso(rel["observedAt"])
        ceiling = parse_iso(a["measuredCurrentUntil"])               # the earliest stale limit among the series actually used
        fresh_until = min(ceiling, max(obs + timedelta(minutes=WINDOW_MIN[t]), floor))
    elif a["kind"] == C.SCHEDULE_ONLY:
        end = parse_iso((sched.get("now") or {}).get("end")) or now
        fresh_until = min(end, now + timedelta(hours=SCHEDULE_ONLY_MAX_H))
    elif a["kind"] == C.DOWNSTREAM_ONLY and a.get("gaugeCurrentUntil"):
        obs = parse_iso(a["tailwaterGauge"]["observedAt"])
        fresh_until = min(parse_iso(a["gaugeCurrentUntil"]), max(obs + timedelta(minutes=WINDOW_MIN[t]), floor))
    else:
        fresh_until = now
    if rel.get("statusBasis") in ("SCHEDULE", "MEASURED_AND_SCHEDULE"):
        # the status rests on the schedule hour: it cannot be presented past the end of that scheduled window
        end = parse_iso((sched.get("now") or {}).get("end"))
        if end is not None:
            fresh_until = min(fresh_until, end)
    next_check = now + timedelta(minutes=recheck)
    return {"tier": t, "reason": why, "freshUntil": iso(fresh_until), "nextCheckAt": iso(next_check), "recheckMinutes": recheck,
            "stale": fresh_until <= now, "model": C.STALENESS_MODEL}


def due(published: dict | None, now: datetime) -> bool:
    """Read the dam's sources this run? Yes when nothing is published, or its nextCheckAt is reached (minus the planner tolerance)."""
    if not published:
        return True
    nxt = parse_iso((published.get("freshness") or {}).get("nextCheckAt"))
    return nxt is None or now >= nxt - timedelta(minutes=PLANNER_TOLERANCE_MIN)
