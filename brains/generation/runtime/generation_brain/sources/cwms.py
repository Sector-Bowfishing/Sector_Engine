"""USACE CWMS Data API (cwms-data.usace.army.mil/cwms-data/timeseries): measured release series of one project.

A binding names the exact time-series ids (never discovered at run time; discovery is research/tools probe_cwms_release):
  {"office": "SWL", "discharge": "<total outflow tsid>", "turbine"?: tsid, "spill"?: tsid, "generation"?: tsid (MW), "tailwater"?: tsid}
Each series is asked in English units (`unit=EN`) for the last 48 h. A response that still answers in SI is converted (cms -> cfs, m -> ft);
any other unit is refused for that series. Null values are dropped (CWMS marks missing values with a null value), never zero-filled.
Forecast or modeled versions are refused by the binding review, and a series id that looks like one is refused here too."""
from __future__ import annotations

import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from ..contract import iso
from . import FT3_PER_M3, FT_PER_M, Reading, failed, merge_observations

AGENCY = "U.S. Army Corps of Engineers (CWMS)"
BASE = "https://cwms-data.usace.army.mil/cwms-data"
FIELDS = {"discharge": "dischargeCfs", "turbine": "turbineCfs", "spill": "spillCfs", "generation": "generationMw", "tailwater": "tailwaterFt"}
_MODELED = re.compile(r"(?i)(forecast|fcst|-F[FX]$|-P[FX]$|modeled|for comparison|smoothed)")
UNITS = {"dischargeCfs": {"cfs": 1.0, "cms": FT3_PER_M3}, "turbineCfs": {"cfs": 1.0, "cms": FT3_PER_M3}, "spillCfs": {"cfs": 1.0, "cms": FT3_PER_M3},
         "generationMw": {"mw": 1.0}, "tailwaterFt": {"ft": 1.0, "m": FT_PER_M}}


def url(office: str, name: str, begin: datetime, end: datetime) -> str:
    q = {"office": office, "name": name, "unit": "EN", "begin": iso(begin), "end": iso(end), "page-size": "5000"}
    return f"{BASE}/timeseries?" + urllib.parse.urlencode(q)


def interval_minutes(tsid: str) -> int:
    parts = tsid.split(".")
    iv = parts[3] if len(parts) > 3 else ""
    m = re.match(r"^~?(\d+)(Minute|Minutes|Hour|Hours|Day|Days)$", iv)
    if not m:
        return 60
    n, u = int(m.group(1)), m.group(2)
    return n * (1 if u.startswith("Minute") else 60 if u.startswith("Hour") else 1440)


def parse(body: bytes, field: str) -> tuple[list[dict] | None, str | None]:
    try:
        raw = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return None, "unreadable JSON"
    if not isinstance(raw, dict):
        return None, "unexpected response shape"
    unit = str(raw.get("units") or "").strip().lower()
    k = UNITS[field].get(unit)
    if k is None:
        return None, f"unexpected unit {raw.get('units')!r} for {field}"
    out = []
    for row in raw.get("values") or []:
        if not isinstance(row, list) or len(row) < 2 or not isinstance(row[0], (int, float)) or not isinstance(row[1], (int, float)):
            continue
        at = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc)
        out.append({"at": iso(at), field: round(float(row[1]) * k, 3)})
    return out, None


def read(binding: dict, fetcher, now: datetime) -> Reading:
    office = binding["office"]
    begin, end = now - timedelta(hours=48), now + timedelta(hours=1)
    obs, errors, series, cadence = [], [], [], []
    for role, field in FIELDS.items():
        tsid = binding.get(role)
        if not tsid:
            continue
        series.append(f"cwms:{office}:{tsid}")
        if _MODELED.search(tsid):
            errors.append(f"{tsid}: a forecast or modeled version is never read as a measurement")
            continue
        r = fetcher.get("cwms", url(office, tsid, begin, end), accept="application/json;version=2")
        if not r.ok:
            errors.append(f"{tsid}: {r.error}")
            continue
        rows, why = parse(r.body, field)
        if rows is None:
            errors.append(f"{tsid}: {why}")
            continue
        obs += rows
        cadence.append(interval_minutes(tsid))
    if not obs:
        return failed("cwms", AGENCY, "; ".join(errors) or f"CWMS {office}: no release series in the binding", series)
    c = max(60, min(cadence) if cadence else 60)
    return Reading("cwms", AGENCY, True, "; ".join(errors) or None, merge_observations(obs), [], series, cadence_min=c, lag_min=max(120, c))
