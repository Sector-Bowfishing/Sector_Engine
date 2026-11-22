"""USGS Water Data API (api.waterdata.usgs.gov/ogcapi/v1, collection `continuous`): measured discharge (00060, cfs) at a gauge below a dam.

A downstream gauge measures the river, not the dam's own release: the state labels it `tailwaterGauge` with the site and its distance, and
it is used for discharge only when no operator release series is bound. The binding names the site: {"site": "07049690", "parameter": "00060"}.
Rules (as the Lake Brain's v1 reader): several series for one site and parameter are refused rather than merged; a null value and the legacy
-999999 sentinel are dropped; a non-JSON body (an outage notice) is a failure, never data. WaterServices (shuts down 2027-02-22) is not used."""
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime

from ..contract import iso, parse_iso
from . import Reading, failed, merge_observations

AGENCY = "U.S. Geological Survey (Water Data API)"
BASE = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"
PROPS = "time_series_id,monitoring_location_id,parameter_code,time,value,unit_of_measure,approval_status,qualifier"


def url(site: str, parameter: str = "00060", window: str = "PT48H") -> str:
    q = {"f": "json", "monitoring_location_id": f"USGS-{site}", "parameter_code": parameter, "time": window, "limit": "10000",
         "properties": PROPS}
    return f"{BASE}/continuous/items?" + urllib.parse.urlencode(q)


def parse(body: bytes, site: str, parameter: str = "00060") -> tuple[list[dict] | None, str | None]:
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None, "not JSON"
    feats = obj.get("features") if isinstance(obj, dict) else None
    if feats is None:
        return None, "no features"
    series = set()
    out = []
    for f in feats:
        p = (f or {}).get("properties") or {}
        if p.get("monitoring_location_id") not in (None, f"USGS-{site}") or p.get("parameter_code") not in (None, parameter):
            return None, "response for another site or parameter"
        series.add(p.get("time_series_id"))
        unit = str(p.get("unit_of_measure") or "ft^3/s").lower()
        if unit not in ("ft^3/s", "ft3/s", "cfs"):
            return None, f"unexpected unit {p.get('unit_of_measure')!r}"
        at = parse_iso(p.get("time"))
        try:
            v = float(p.get("value"))
        except (TypeError, ValueError):
            continue
        if at is None or v <= -999990:
            continue
        out.append({"at": iso(at), "dischargeCfs": v})
    if len(series - {None}) > 1:
        return None, f"{len(series - {None})} series for one site and parameter (refused, never merged)"
    return merge_observations(out), None


def read(binding: dict, fetcher, now: datetime) -> Reading:
    site, param = binding["site"], binding.get("parameter", "00060")
    series = [f"usgs:{site}:{param}"]
    r = fetcher.get("usgs", url(site, param))
    if not r.ok:
        return failed("usgs", AGENCY, f"USGS {site}: {r.error}", series)
    obs, why = parse(r.body, site, param)
    if obs is None:
        return failed("usgs", AGENCY, f"USGS {site}: {why}", series)
    if not obs:
        return failed("usgs", AGENCY, f"USGS {site}: no readings in 48 h", series)
    return Reading("usgs", AGENCY, True, None, obs, [], series, cadence_min=60, lag_min=60)
