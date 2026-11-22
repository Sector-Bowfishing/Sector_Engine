"""Combine one dam's source readings into its release picture. Pure: no clock, no I/O.

Precedence for the measured release (first provider with a current value wins; the others stay in `sources` for comparison):
  1. the operator's own release: TVA AverageHourlyDischarge, CWMS project outflow (with turbine / spill / generation where bound);
     a measured outflow > 0 while the operator's schedule has units running this hour is GENERATING (statusBasis MEASURED_AND_SCHEDULE);
  2. Reclamation RISE release item;
  3. a USGS discharge gauge below the dam (labelled `downstreamGauge`: it measures the river, not the dam).
The schedule comes from the operator only: TVA (unit counts as stated) or SWPA (megawatts; no unit count).

Status rules (never a default): measured turbine flow > 0 or generation MW > 0 -> GENERATING; measured spill > 0 -> SPILLING (and `spilling`
true when also generating); only a total outflow > 0 -> RELEASING; a measured 0 -> OFF. With no current measurement, the operator schedule
for this hour decides (GENERATING / OFF, statusBasis SCHEDULE). With neither, UNKNOWN."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import contract as C
from .contract import iso, parse_iso

PRIORITY = ("tva", "cwms", "rise", "usgs")
SCHEDULE_PRIORITY = ("tva", "swpa")
TREND_HOURS = 12


def ceiling_min(reading) -> int:
    """A reading counts as current until its source is overdue: lag + 3 x cadence (the Lake Brain stale rule)."""
    return reading.lag_min + 3 * reading.cadence_min


def _latest(rows: list[dict], key: str, not_after: datetime) -> dict | None:
    best = None
    for r in rows:
        at = parse_iso(r["at"])
        if r.get(key) is None or at is None or at > not_after:
            continue
        if best is None or at > parse_iso(best["at"]):
            best = r
    return best


def _trend(rows: list[dict], key: str, last: dict) -> float | None:
    t_last = parse_iso(last["at"])
    cut = t_last - timedelta(hours=TREND_HOURS)
    base = [r for r in rows if r.get(key) is not None and parse_iso(r["at"]) <= cut]
    if not base:
        return None
    b = max(base, key=lambda r: r["at"])
    return round(last[key] - b[key], 1)


def window_at(schedule: list[dict], t: datetime) -> dict | None:
    return next((w for w in schedule if parse_iso(w["start"]) <= t < parse_iso(w["end"])), None)


def _running(w: dict | None) -> bool | None:
    if w is None:
        return None
    if w.get("unitsOn") is not None:
        return w["unitsOn"] > 0
    if w.get("generationMw") is not None:
        return w["generationMw"] > 0
    return None


def transitions(schedule: list[dict], now: datetime) -> dict:
    """The next scheduled start and stop of generation after now, from the operator's schedule."""
    cur = _running(window_at(schedule, now))
    start = stop = None
    prev = cur
    for w in schedule:
        if parse_iso(w["end"]) <= now or parse_iso(w["start"]) < now:
            continue
        run = _running(w)
        if run is None:
            continue
        if run and prev is not True and start is None:
            start = w["start"]
        if not run and prev is not False and stop is None:
            stop = w["start"]
        prev = run
    ends = [parse_iso(w["end"]) for w in schedule]
    return {"nextReleaseStartAt": start, "nextShutdownAt": stop, "scheduleCoversUntil": iso(max(ends)) if ends else None}


def assess(readings: list, now: datetime) -> dict:
    by = {r.provider: r for r in readings if r.ok}
    measured, measured_by = None, None
    for p in PRIORITY:
        r = by.get(p)
        if not r:
            continue
        row = _latest(r.observations, "dischargeCfs", now) or _latest(r.observations, "turbineCfs", now) \
            or _latest(r.observations, "generationMw", now)
        if row and now - parse_iso(row["at"]) <= timedelta(minutes=ceiling_min(r)):
            measured, measured_by = row, r
            break
    sched_by = next((by[p] for p in SCHEDULE_PRIORITY if p in by and by[p].schedule), None)
    schedule = sched_by.schedule if sched_by else []
    now_w = window_at(schedule, now)

    gaps = []
    release = {"status": C.UNKNOWN, "statusBasis": None, "generating": None, "spilling": None, "dischargeCfs": None, "turbineCfs": None,
               "spillCfs": None, "generationMw": None, "trend12hCfs": None, "observedAt": None, "source": None, "downstreamGauge": False}
    if measured:
        g = (measured.get("turbineCfs") or 0) > 0 or (measured.get("generationMw") or 0) > 0
        s = (measured.get("spillCfs") or 0) > 0
        q = measured.get("dischargeCfs")
        if g:
            status = C.GENERATING
        elif s:
            status = C.SPILLING
        elif q is not None and q > 0:
            status = C.RELEASING
        elif q == 0 or (measured.get("turbineCfs") == 0 and measured.get("spillCfs") in (0, None)):
            status = C.OFF
        else:
            status = C.UNKNOWN
        release.update({"status": status, "statusBasis": "MEASURED", "dischargeCfs": q, "turbineCfs": measured.get("turbineCfs"),
                        "spillCfs": measured.get("spillCfs"), "generationMw": measured.get("generationMw"), "observedAt": measured["at"],
                        "source": measured_by.provider, "downstreamGauge": measured_by.provider == "usgs",
                        "generating": True if g else (False if measured.get("turbineCfs") == 0 or measured.get("generationMw") == 0 else None),
                        "spilling": True if s else (False if measured.get("spillCfs") == 0 else None)})
        if status == C.RELEASING and _running(now_w) is not None:
            # TVA's observed rows carry the release, not the units; the operator's schedule for this hour says whether units are running.
            release["generating"] = _running(now_w)
            if _running(now_w):
                release.update({"status": C.GENERATING, "statusBasis": "MEASURED_AND_SCHEDULE"})
        if q is not None:
            release["trend12hCfs"] = _trend(measured_by.observations, "dischargeCfs", measured)
        if measured_by.provider == "usgs":
            gaps.append("discharge is a USGS gauge below the dam (the river, not the dam's own release)")
    elif _running(now_w) is not None:
        release.update({"status": C.GENERATING if _running(now_w) else C.OFF, "statusBasis": "SCHEDULE", "source": sched_by.provider,
                        "generating": _running(now_w)})
        gaps.append("no current measured release: status is the operator's schedule for this hour")
    else:
        gaps.append("no current measured release and no operator schedule for this hour")

    tw_row = None
    for p in ("tva", "cwms"):
        r = by.get(p)
        row = _latest(r.observations, "tailwaterFt", now) if r else None
        if row and now - parse_iso(row["at"]) <= timedelta(minutes=ceiling_min(r)):
            tw_row = (row, p)
            break
    sched_block = None
    if schedule:
        sched_block = {"publishedBy": sched_by.agency, "provider": sched_by.provider, "windows": schedule,
                       "now": ({k: now_w.get(k) for k in ("start", "end", "unitsOn", "unitsOnIsMinimum", "generationMw")} if now_w else None),
                       "unitsStated": sched_by.provider == "tva", **transitions(schedule, now)}
        if sched_by.provider == "swpa":
            gaps.append("SWPA publishes megawatts, not unit counts: units on are not stated")
    hist_src = measured_by or next((by[p] for p in PRIORITY if p in by and by[p].observations), None)
    history = [{k: r.get(k) for k in ("at", "dischargeCfs", "turbineCfs", "spillCfs", "generationMw", "tailwaterFt") if r.get(k) is not None}
               for r in (hist_src.observations if hist_src else []) if now - parse_iso(r["at"]) <= timedelta(hours=48) and parse_iso(r["at"]) <= now]
    if measured:
        kind = C.OBSERVED
    elif sched_block and now_w:
        kind = C.SCHEDULE_ONLY
    else:
        kind = C.UNAVAILABLE
    return {"kind": kind, "release": release, "schedule": sched_block,
            "tailwater": {"elevationFt": tw_row[0]["tailwaterFt"], "observedAt": tw_row[0]["at"], "source": tw_row[1]} if tw_row else None,
            "history": history, "gaps": gaps, "measuredReading": measured_by}
