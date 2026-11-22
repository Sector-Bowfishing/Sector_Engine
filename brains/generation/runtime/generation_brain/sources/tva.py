"""TVA REST API (www.tva.com/RestApi): the operator's unit schedule and its hourly observed release.

  /generation-releases/{LocationID}     rows {Day "MM/DD/YYYY", Time "5 PM - 6 PM EDT", Generators "2" | "2 or more"}: TVA's own unit plan
  /observed-data-48-hours/{LocationID}  rows {Day, Time (hour ENDING, "11 PM CDT", "Midnight CDT"), TailwaterElevation, AverageHourlyDischarge, ...}

Traps handled (each has a test):
  * JSON only with `Accept: application/json`; without it TVA answers 200 with an HTML explorer page, which is refused here.
  * Observed rows are hour-ENDING: "Midnight" is 00:00 of the NEXT day (Lake Brain and the TVA archive read it the same way; the old
    Engine/iOS parser put it 24 h early).
  * Schedule windows: "1 AM - Midnight" and "11 PM - Midnight" end at 24:00 of the window's day.
  * Times carry their own zone (EDT/EST/CDT/CST; it varies by dam). The fixed offset of the stated abbreviation is used, never the device's.
  * Numbers are comma-grouped strings ("32,614"); blank is missing. A zero discharge is kept as published.
  * Units "N or more" are published as a floor: unitsOn = N, unitsOnIsMinimum = true.
ReservoirElevation is in the same rows; it is Lake Brain's domain and is not read."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from ..contract import iso
from . import Reading, failed, merge_observations

AGENCY = "Tennessee Valley Authority"
BASE = "https://www.tva.com/RestApi"
OFFSETS = {"EDT": -4, "EST": -5, "CDT": -5, "CST": -6}
_HOUR = re.compile(r"^(\d{1,2})\s*(AM|PM)$", re.I)


def zone(text: str) -> timezone | None:
    t = (text or "").strip().upper()
    for abbr, h in OFFSETS.items():
        if t.endswith(abbr):
            return timezone(timedelta(hours=h), abbr)
    return None


def strip_zone(text: str) -> str:
    t = (text or "").strip()
    for abbr in OFFSETS:
        if t.upper().endswith(abbr):
            return t[: -len(abbr)].strip()
    return t


def hour(token: str) -> int | None:
    """"Midnight" -> 0, "Noon" -> 12, "5 AM" -> 5, "3 PM" -> 15."""
    t = (token or "").strip().upper()
    if t == "MIDNIGHT":
        return 0
    if t == "NOON":
        return 12
    m = _HOUR.match(t)
    if not m:
        return None
    n = int(m.group(1))
    if not 1 <= n <= 12:
        return None
    return (n % 12) + (12 if m.group(2).upper() == "PM" else 0)


def day(text: str) -> datetime | None:
    try:
        return datetime.strptime((text or "").strip(), "%m/%d/%Y")
    except ValueError:
        return None


def number(v) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.replace(",", "").strip()
        try:
            return float(s) if s else None
        except ValueError:
            return None
    return None


def parse_window(row: dict) -> dict | None:
    tz, d = zone(row.get("Time", "")), day(row.get("Day", ""))
    gen = str(row.get("Generators", "")).strip()
    m = re.match(r"^(\d+)", gen)
    if tz is None or d is None or not m:
        return None
    parts = strip_zone(row["Time"]).split("-")
    if len(parts) != 2:
        return None
    sh, eh = hour(parts[0]), hour(parts[1])
    if sh is None or eh is None:
        return None
    if eh <= sh:
        eh += 24                                   # "1 AM - Midnight", "Midnight - Midnight" end on the next day
    base = d.replace(tzinfo=tz)
    return {"start": iso(base + timedelta(hours=sh)), "end": iso(base + timedelta(hours=eh)), "unitsOn": int(m.group(1)),
            "unitsOnIsMinimum": "or more" in gen.lower(), "statedBy": "operator"}


def observed_time(row: dict) -> datetime | None:
    tz, d = zone(row.get("Time", "")), day(row.get("Day", ""))
    if tz is None or d is None:
        return None
    t = strip_zone(row["Time"]).upper()
    h = 24 if t == "MIDNIGHT" else hour(t)          # hour-ENDING: Midnight closes the day
    if h is None:
        return None
    return d.replace(tzinfo=tz) + timedelta(hours=h)


def _rows(body: bytes) -> list | None:
    try:
        rows = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None                                # the HTML explorer page, or anything else that is not JSON
    return rows if isinstance(rows, list) else None


def parse_schedule(body: bytes) -> list[dict] | None:
    rows = _rows(body)
    if rows is None:
        return None
    out = [w for w in (parse_window(r) for r in rows if isinstance(r, dict)) if w]
    return sorted(out, key=lambda w: w["start"])


def parse_observed(body: bytes) -> list[dict] | None:
    rows = _rows(body)
    if rows is None:
        return None
    obs = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        at = observed_time(r)
        if at is None:
            continue
        q, tw = number(r.get("AverageHourlyDischarge")), number(r.get("TailwaterElevation"))
        if q is None and tw is None:
            continue
        obs.append({"at": iso(at), "dischargeCfs": q, "tailwaterFt": tw if (tw or 0) > 0 else None})
    return merge_observations(obs)


def unparsed(endpoint: str, loc: str, body: bytes | None, ok) -> list[str]:
    """Rows TVA sent that could not be read (an unknown time or generator format): never silently dropped. All rows failing is an error
    for that endpoint (the schedule or the release is then absent, and the state says why); some failing is named too."""
    rows = _rows(body) if body is not None else None
    if not rows:
        return []
    bad = sum(1 for r in rows if not (isinstance(r, dict) and ok(r)))
    if bad == len(rows):
        return [f"{endpoint}/{loc}: none of {len(rows)} rows could be parsed (format changed?)"]
    return [f"{endpoint}/{loc}: {bad} of {len(rows)} rows could not be parsed"] if bad else []


def read(binding: dict, fetcher, now: datetime) -> Reading:
    loc = binding["locationId"]
    sched = fetcher.get("tva", f"{BASE}/generation-releases/{loc}")
    obs = fetcher.get("tva", f"{BASE}/observed-data-48-hours/{loc}")
    series = [f"tva:{loc}:generation-releases", f"tva:{loc}:observed-data-48-hours"]
    if not sched.ok and not obs.ok:
        return failed("tva", AGENCY, f"TVA {loc}: {sched.error or obs.error}", series)
    windows = parse_schedule(sched.body) if sched.ok else None
    observations = parse_observed(obs.body) if obs.ok else None
    errors = []
    if windows is None:
        errors.append(f"generation-releases/{loc}: {sched.error or 'not JSON (send Accept: application/json)'}")
    if observations is None:
        errors.append(f"observed-data-48-hours/{loc}: {obs.error or 'not JSON (send Accept: application/json)'}")
    errors += unparsed("generation-releases", loc, sched.body if sched.ok and windows is not None else None, lambda r: parse_window(r) is not None)
    errors += unparsed("observed-data-48-hours", loc, obs.body if obs.ok and observations is not None else None, lambda r: observed_time(r) is not None)
    if not windows and not observations:
        return failed("tva", AGENCY, "; ".join(errors) or f"TVA {loc}: no rows", series)
    return Reading("tva", AGENCY, True, "; ".join(errors) or None, observations or [], windows or [], series, cadence_min=60, lag_min=60)
