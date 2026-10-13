"""Shared helpers for the datum-pairing research scripts (read-only HTTP GETs against public USACE / USGS APIs, cached on disk).
Cache root (outside git): ~/Desktop/Development/Sector_Research_Data/depth-brain/datum2/"""
import hashlib, json, os, time
import requests

ROOT = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum2")
CACHE = os.path.join(ROOT, "http_cache"); os.makedirs(CACHE, exist_ok=True)
CWMS = "https://cwms-data.usace.army.mil/cwms-data"
A2W = "https://water.usace.army.mil/cda/reporting"
S = requests.Session(); S.headers["User-Agent"] = "sector-depth-brain-research/1.0 (read-only)"


def get_json(url, params=None, headers=None, retries=2, cache=True):
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True, default=str)).encode()).hexdigest()
    p = os.path.join(CACHE, key + ".json")
    if cache and os.path.exists(p):
        return json.load(open(p))
    last = None
    for i in range(retries + 1):
        try:
            r = S.get(url, params=params, headers=headers, timeout=60)
            if r.status_code == 200:
                d = r.json(); json.dump({"_url": r.url, "_fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "data": d}, open(p, "w"))
                return {"_url": r.url, "data": d}
            last = {"_url": r.url, "error": f"HTTP {r.status_code}", "body": r.text[:200]}
            if r.status_code in (400, 404): break
        except Exception as e:
            last = {"_url": url, "error": repr(e)[:200]}
        time.sleep(1.5)
    return last


def cwms(path, **params):
    return get_json(f"{CWMS}/{path}", params, headers={"Accept": "application/json;version=2"})


def a2w(path):
    return get_json(f"{A2W}/{path}")


# ---- series helpers -------------------------------------------------------------------------------------------------------
import numpy as np
import pandas as pd

USGS = "https://waterservices.usgs.gov/nwis"


def cwms_series(office, tsid, begin, end, unit="ft"):
    """All pages of a CWMS time series -> (pd.Series indexed by UTC timestamp, meta dict with vertical-datum-info, url list)."""
    vals, meta, urls, page = [], {}, [], None
    for _ in range(60):
        params = {"office": office, "name": tsid, "begin": begin, "end": end, "unit": unit, "page-size": 20000}
        if page:
            params["page"] = page
        r = cwms("timeseries", **params)
        d = r.get("data") if isinstance(r, dict) else None
        if not d or "values" not in d:
            return None, {"error": (r or {}).get("error", "no data")}, urls
        urls.append(r.get("_url"))
        meta = {k: d.get(k) for k in ("vertical-datum-info", "units", "interval", "time-zone", "name", "office-id")}
        vals += [(v[0], v[1], v[2] if len(v) > 2 else None) for v in d["values"] if v[1] is not None]
        page = d.get("next-page")
        if not page:
            break
    if not vals:
        return pd.Series(dtype=float), meta, urls
    s = pd.Series([v[1] for v in vals], index=pd.to_datetime([v[0] for v in vals], unit="ms", utc=True)).sort_index()
    return s[~s.index.duplicated()], meta, urls


def usgs_series(site, param, begin, end, kind="iv"):
    """USGS NWIS iv or dv -> pd.Series indexed by UTC (dv: local-day label at 12:00 local converted to UTC is NOT done; dv index is the local calendar date as naive Timestamp)."""
    out, urls = [], []
    b = pd.Timestamp(begin); e = pd.Timestamp(end)
    step = pd.Timedelta(days=100 if kind == "iv" else 3000)
    cur = b
    while cur < e:
        nxt = min(cur + step, e)
        params = {"format": "json", "sites": site, "parameterCd": param, "startDT": cur.strftime("%Y-%m-%d"), "endDT": nxt.strftime("%Y-%m-%d")}
        if kind == "dv":
            params["statCd"] = "00003"
        r = get_json(f"{USGS}/{kind}/", params)
        d = r.get("data") if isinstance(r, dict) else None
        if d is None:
            return None, {"error": (r or {}).get("error")}, urls
        urls.append(r.get("_url"))
        for ts in d["value"]["timeSeries"]:
            for blk in ts["values"]:
                for v in blk["value"]:
                    if v["value"] not in ("", None) and float(v["value"]) > -999:
                        out.append((v["dateTime"], float(v["value"])))
        cur = nxt
    if not out:
        return pd.Series(dtype=float), {}, urls
    idx = pd.to_datetime([o[0] for o in out], utc=(kind == "iv"), format="ISO8601")
    s = pd.Series([o[1] for o in out], index=idx).sort_index()
    return s[~s.index.duplicated()], {}, urls


def offset_stats(diff):
    """diff: pd.Series of (usgs - cwms) or similar. Returns the stats dict used in the proposals; stability = per-quarter means."""
    d = diff.dropna()
    if len(d) == 0:
        return {"n": 0}
    q = d.groupby(d.index.to_period("Q")).agg(["mean", "count"])
    q = q[q["count"] >= 10]
    h = len(d) // 2
    return {"n": int(len(d)), "meanFt": round(float(d.mean()), 3), "sdFt": round(float(d.std(ddof=1)), 3) if len(d) > 1 else None, "minFt": round(float(d.min()), 3),
            "maxFt": round(float(d.max()), 3), "medianFt": round(float(d.median()), 3), "window": f"{d.index.min().date()}..{d.index.max().date()}",
            "firstHalfMeanFt": round(float(d.iloc[:h].mean()), 3) if h else None, "secondHalfMeanFt": round(float(d.iloc[h:].mean()), 3) if h else None,
            "quarterMeanRangeFt": [round(float(q["mean"].min()), 3), round(float(q["mean"].max()), 3)] if len(q) else None, "nQuarters": int(len(q))}
