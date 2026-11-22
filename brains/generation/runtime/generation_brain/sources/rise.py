"""Bureau of Reclamation RISE (data.usbr.gov/rise/api/result): a reservoir's release item (total release, cfs).

The binding names the release item id: {"itemId": "<id>", "unit": "cfs"} (found by research/tools probe_rise_release; never discovered at
run time). Only `resultType` observed is read (modeled results are refused). RISE writes 0.0 for a missing value in its elevation series
(Lake Brain finding), and a missing release cannot be told apart from a real zero there, so a 0.0 release is dropped as missing: a dam
with no release shows as UNKNOWN, never as OFF, from RISE alone. Daily items lag about 48 h, so their freshness window is long."""
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timedelta

from ..contract import iso, parse_iso
from . import Reading, failed, merge_observations

AGENCY = "Bureau of Reclamation (RISE)"
BASE = "https://data.usbr.gov/rise/api"


def url(item: str, after: datetime) -> str:
    q = {"itemId": item, "dateTime[after]": after.strftime("%Y-%m-%d"), "itemsPerPage": "2000"}
    return f"{BASE}/result?" + urllib.parse.urlencode(q)


def parse(body: bytes) -> list[dict] | None:
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    out = []
    for it in (obj.get("data") if isinstance(obj, dict) else None) or []:
        a = (it or {}).get("attributes") or {}
        at = parse_iso(a.get("dateTime"))
        v = a.get("result")
        if at is None or not isinstance(v, (int, float)) or v <= 0:
            continue
        kind = ((a.get("resultAttributes") or {}).get("resultType"))
        if kind is not None and kind != "observed":
            continue
        out.append({"at": iso(at), "dischargeCfs": float(v)})
    return merge_observations(out)


def read(binding: dict, fetcher, now: datetime) -> Reading:
    item = binding["itemId"]
    series = [f"rise:{item}"]
    r = fetcher.get("rise", url(item, now - timedelta(days=4)), accept="application/vnd.api+json")
    if not r.ok:
        return failed("rise", AGENCY, f"RISE item {item}: {r.error}", series)
    obs = parse(r.body)
    if obs is None:
        return failed("rise", AGENCY, f"RISE item {item}: unreadable response", series)
    if not obs:
        return failed("rise", AGENCY, f"RISE item {item}: no observed release values (0.0 placeholders dropped)", series)
    daily = binding.get("interval", "daily") == "daily"
    return Reading("rise", AGENCY, True, None, obs, [], series, cadence_min=1440 if daily else 60, lag_min=2880 if daily else 120)
