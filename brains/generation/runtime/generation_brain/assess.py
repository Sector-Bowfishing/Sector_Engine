"""Combine one dam's source readings into its release picture. Pure: no clock, no I/O.

Measured release (the first operator provider with at least one CURRENT release series wins; the others stay in `sources`):
  1. the operator's own release: TVA AverageHourlyDischarge; CWMS project outflow, turbine, spill and generation (MW) series;
  2. Reclamation RISE release item.
Within a provider every release series is judged on its OWN freshness (lag + 3 x its own cadence): a stale daily outflow never hides a fresh
hourly turbine or generation series, and a stale series contributes nothing. Of the current values, only those of the newest reading period are
shown together (same_period); an older one is named in `gaps`, never mixed in. `observedAt` is the newest value used and `observedAtByField`
gives each value's own time. The dam's `history` holds the dam's own data only; a USGS gauge keeps its river flow in `tailwaterGauge.history`.
`generatingBasis` says whether `generating` was measured or taken from the operator's schedule hour.
A USGS gauge below the dam measures the river, not the dam: it is published as `tailwaterGauge` {site, distanceMiles, dischargeCfs, ...}
and never sets the dam's release status (kind DOWNSTREAM_ONLY, status UNKNOWN). It is read only when no operator release series is bound.
The schedule comes from the operator only: TVA (unit counts as stated) or SWPA (megawatts; no unit count).

Status rules (never a default): measured turbine flow > 0 or generation MW > 0 -> GENERATING; measured spill > 0 -> SPILLING (and `spilling`
true when also generating); only a total outflow > 0 -> RELEASING, or GENERATING when the operator's schedule has units running this hour
(statusBasis MEASURED_AND_SCHEDULE); a measured 0 -> OFF. With no current measurement, the operator schedule for this hour decides
(GENERATING / OFF, statusBasis SCHEDULE). With neither, UNKNOWN."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import contract as C
from .contract import iso, parse_iso

PRIORITY = ("tva", "cwms", "rise")
SCHEDULE_PRIORITY = ("tva", "swpa")
RELEASE_KEYS = ("dischargeCfs", "turbineCfs", "spillCfs", "generationMw")
TREND_HOURS = 12


def _latest(rows: list[dict], key: str, not_after: datetime) -> dict | None:
    best = None
    for r in rows:
        at = parse_iso(r["at"])
        if r.get(key) is None or at is None or at > not_after:
            continue
        if best is None or at > parse_iso(best["at"]):
            best = r
    return best


def current(reading, key: str, now: datetime) -> dict | None:
    """The newest value of one series if it is still current under that series' own stale rule, else None."""
    row = _latest(reading.observations, key, now)
    if row and now - parse_iso(row["at"]) <= timedelta(minutes=reading.ceiling_min(key)):
        return row
    return None


def same_period(reading, rows: dict) -> tuple[dict, dict]:
    """Split current series values into those of the newest reading period and older ones. A value counts as the same period when it is no
    older than the newest value minus the newest series' cadence; e.g. a daily outflow from 30 h ago is never shown beside a 30-min turbine
    flow. Returns (used, older)."""
    newest_key = max(rows, key=lambda k: rows[k]["at"])
    newest = parse_iso(rows[newest_key]["at"])
    window = timedelta(minutes=reading.timing(newest_key)[0])
    used = {k: v for k, v in rows.items() if newest - parse_iso(v["at"]) <= window}
    return used, {k: v for k, v in rows.items() if k not in used}


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
    measured, measured_by, used, older = None, None, {}, {}
    for p in PRIORITY:
        r = by.get(p)
        if not r:
            continue
        rows = {k: current(r, k, now) for k in RELEASE_KEYS}
        rows = {k: v for k, v in rows.items() if v is not None}
        if rows:
            measured_by = r
            used, older = same_period(r, rows)
            measured = {k: v[k] for k, v in used.items()}
            break
    sched_by = next((by[p] for p in SCHEDULE_PRIORITY if p in by and by[p].schedule), None)
    schedule = sched_by.schedule if sched_by else []
    now_w = window_at(schedule, now)

    gaps = []
    release = {"status": C.UNKNOWN, "statusBasis": None, "generating": None, "spilling": None, "dischargeCfs": None, "turbineCfs": None,
               "spillCfs": None, "generationMw": None, "trend12hCfs": None, "observedAt": None, "observedAtByField": {}, "source": None,
               "generatingBasis": None}
    measured_until = None
    if measured:
        turb, mw, spill, q = (measured.get(k) for k in ("turbineCfs", "generationMw", "spillCfs", "dischargeCfs"))
        g = (turb or 0) > 0 or (mw or 0) > 0
        s = (spill or 0) > 0
        if g:
            status = C.GENERATING
        elif s:
            status = C.SPILLING
        elif q is not None and q > 0:
            status = C.RELEASING
        elif q == 0 or (turb == 0 and spill in (0, None)) or (mw == 0 and spill in (0, None) and q is None and turb is None):
            status = C.OFF
        else:
            status = C.UNKNOWN
        release.update({"status": status, "statusBasis": "MEASURED", "dischargeCfs": q, "turbineCfs": turb, "spillCfs": spill, "generationMw": mw,
                        "observedAt": max(v["at"] for v in used.values()), "observedAtByField": {k: v["at"] for k, v in sorted(used.items())},
                        "source": measured_by.provider,
                        "generating": True if g else (False if turb == 0 or mw == 0 else None),
                        "generatingBasis": "MEASURED" if (g or turb == 0 or mw == 0) else None,
                        "spilling": True if s else (False if spill == 0 else None)})
        if status == C.RELEASING and _running(now_w) is not None:
            # TVA's observed rows carry the release, not the units; the operator's schedule for this hour says whether units are running.
            release["generating"], release["generatingBasis"] = _running(now_w), "SCHEDULE"
            if _running(now_w):
                release.update({"status": C.GENERATING, "statusBasis": "MEASURED_AND_SCHEDULE"})
        for k, v in sorted(older.items()):
            gaps.append(f"{k} not shown: its latest value ({v['at']}) is from an earlier period than the newest release reading "
                        f"({release['observedAt']}); one release picture never mixes readings of different ages")
        if q is not None:
            release["trend12hCfs"] = _trend(measured_by.observations, "dischargeCfs", used["dischargeCfs"])
        measured_until = iso(min(parse_iso(v["at"]) + timedelta(minutes=measured_by.ceiling_min(k)) for k, v in used.items()))
    elif _running(now_w) is not None:
        release.update({"status": C.GENERATING if _running(now_w) else C.OFF, "statusBasis": "SCHEDULE", "source": sched_by.provider,
                        "generating": _running(now_w), "generatingBasis": "SCHEDULE"})
        gaps.append("no current measured release: status is the operator's schedule for this hour")
    else:
        gaps.append("no current measured release and no operator schedule for this hour")

    gauge, gauge_until = None, None
    u = by.get("usgs")
    if u is not None:
        row = current(u, "dischargeCfs", now)
        if row:
            gauge = {"site": u.meta.get("site"), "distanceMiles": u.meta.get("distanceMiles"), "dischargeCfs": row["dischargeCfs"],
                     "trend12hCfs": _trend(u.observations, "dischargeCfs", row), "observedAt": row["at"], "agency": u.agency,
                     "history": [{"at": o["at"], "dischargeCfs": o["dischargeCfs"]} for o in u.observations
                                 if o.get("dischargeCfs") is not None and timedelta(0) <= now - parse_iso(o["at"]) <= timedelta(hours=48)]}
            gauge_until = iso(parse_iso(row["at"]) + timedelta(minutes=u.ceiling_min("dischargeCfs")))
            gaps.append("a USGS gauge below the dam measures the river, not the dam's release: the dam's status stays UNKNOWN")

    tw_row = None
    for p in ("tva", "cwms"):
        r = by.get(p)
        row = current(r, "tailwaterFt", now) if r else None
        if row:
            tw_row = (row, p)
            break
    sched_block = None
    if schedule:
        sched_block = {"publishedBy": sched_by.agency, "provider": sched_by.provider, "windows": schedule,
                       "now": ({k: now_w.get(k) for k in ("start", "end", "unitsOn", "unitsOnIsMinimum", "generationMw")} if now_w else None),
                       "unitsStated": sched_by.provider == "tva", **transitions(schedule, now)}
        if sched_by.provider == "swpa":
            gaps.append("SWPA publishes megawatts, not unit counts: units on are not stated")
    hist_src = measured_by or next((by[p] for p in PRIORITY if p in by and by[p].observations), None)     # the dam's own data only
    history = [{k: r.get(k) for k in ("at", "dischargeCfs", "turbineCfs", "spillCfs", "generationMw", "tailwaterFt") if r.get(k) is not None}
               for r in (hist_src.observations if hist_src else []) if now - parse_iso(r["at"]) <= timedelta(hours=48) and parse_iso(r["at"]) <= now]
    if measured:
        kind = C.OBSERVED
    elif sched_block and now_w:
        kind = C.SCHEDULE_ONLY
    elif gauge:
        kind = C.DOWNSTREAM_ONLY
    else:
        kind = C.UNAVAILABLE
    return {"kind": kind, "release": release, "schedule": sched_block, "tailwaterGauge": gauge,
            "tailwater": {"elevationFt": tw_row[0]["tailwaterFt"], "observedAt": tw_row[0]["at"], "source": tw_row[1]} if tw_row else None,
            "history": history, "gaps": gaps, "measuredReading": measured_by, "measuredCurrentUntil": measured_until,
            "gaugeCurrentUntil": gauge_until}
