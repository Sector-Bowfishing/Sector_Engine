#!/usr/bin/env python3
"""Polite fetchers for the baselines thread (read-only, public APIs). Bulk output goes to
~/Desktop/Development/Sector_Research_Data/lake-brain/history/ (never Git).
usage: baseline_fetch.py cwms <office> <name> <outcsv> [begin] [end]
       baseline_fetch.py usgs-dv <site> <param> <outcsv> [begin] [end]
"""
import sys, json, time, urllib.request, urllib.parse, csv, datetime as dt

UA = "SectorResearch/1.0 (lake-brain baselines research)"
CWMS = "https://cwms-data.usace.army.mil/cwms-data"

def get(url, accept="application/json", timeout=120, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise last

def cwms_series(office, name, begin="1900-01-01T00:00:00Z", end=None, sleep=0.4):
    """Paged CWMS timeseries -> list of (epoch_ms, value, quality). Follows next-page."""
    end = end or dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    q = urllib.parse.urlencode({"name": name, "office": office, "begin": begin, "end": end, "page-size": 100000})
    url = f"{CWMS}/timeseries?{q}"
    rows, meta = [], None
    while url:
        d = json.loads(get(url, "application/json;version=2"))
        meta = meta or {k: d.get(k) for k in ("name", "units", "interval", "time-zone", "total")}
        rows += d.get("values", [])
        nxt = d.get("next-page")
        url = f"{CWMS}/timeseries?{q}&page={urllib.parse.quote(nxt)}" if nxt else None
        time.sleep(sleep)
    return meta, rows

def usgs_dv(site, param, begin="1900-01-01", end=None, stat="00003"):
    end = end or dt.date.today().isoformat()
    q = urllib.parse.urlencode({"format": "json", "sites": site, "parameterCd": param, "statCd": stat,
                                "startDT": begin, "endDT": end})
    d = json.loads(get(f"https://waterservices.usgs.gov/nwis/dv/?{q}", timeout=180))
    out = []
    for ts in d["value"]["timeSeries"]:
        for v in ts["values"][0]["value"]:
            out.append((v["dateTime"][:10], v["value"], ",".join(v.get("qualifiers", []))))
    return out

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "cwms":
        office, name, out = sys.argv[2:5]
        meta, rows = cwms_series(office, name, *(sys.argv[5:7]))
        with open(out, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["epoch_ms", "value", "quality"])
            w.writerows(rows)
        print(meta, len(rows))
    elif mode == "usgs-dv":
        site, param, out = sys.argv[2:5]
        rows = usgs_dv(site, param, *(sys.argv[5:7]))
        with open(out, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["date", "value", "qualifiers"]); w.writerows(rows)
        print(len(rows))
