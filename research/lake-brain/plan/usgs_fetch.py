#!/usr/bin/env python3
"""Daily series from USGS NWIS legacy services (dv statistic or iv->daily mean), saved as gz csv (date,value) under plan/history/usgs/.
usage: usgs_fetch.py dv <site> <param> <stat> [begin] [end]  |  iv <site> <param> [begin] [end]"""
import sys, json, collections
from common import *
OUT = f"{PLAN}/history/usgs"; os.makedirs(OUT, exist_ok=True)

def dv(site, param, stat, begin="1900-01-01", end=None):
    end = end or dt.date.today().isoformat(); out = {}
    b = int(begin[:4]); e = int(end[:4])
    for y0 in range(max(b, 1900), e + 1, 15):
        s = begin if y0 == b else f"{y0}-01-01"; t = min(f"{y0 + 14}-12-31", end)
        q = urllib.parse.urlencode({"format": "json", "sites": site, "parameterCd": param, "statCd": stat, "startDT": s, "endDT": t})
        try:
            d = json.loads(get(f"https://waterservices.usgs.gov/nwis/dv/?{q}", timeout=180, sleep=0.6))
        except urllib.error.HTTPError:
            continue
        for ts in d["value"]["timeSeries"]:
            for v in ts["values"][0]["value"]:
                if v["value"] not in ("", None) and float(v["value"]) > -999990:
                    out[v["dateTime"][:10]] = float(v["value"])
    return out

def iv_daily(site, param, begin, end=None):
    end = end or dt.date.today().isoformat(); acc = collections.defaultdict(list)
    for y in range(int(begin[:4]), int(end[:4]) + 1):
        s = begin if y == int(begin[:4]) else f"{y}-01-01"; t = min(f"{y}-12-31", end)
        q = urllib.parse.urlencode({"format": "json", "sites": site, "parameterCd": param, "startDT": s, "endDT": t})
        try:
            d = json.loads(get(f"https://waterservices.usgs.gov/nwis/iv/?{q}", timeout=300, sleep=1.0))
        except Exception as e:
            print("iv err", y, e); continue
        for ts in d["value"]["timeSeries"]:
            for v in ts["values"][0]["value"]:
                if v["value"] not in ("", None) and float(v["value"]) > -999990:
                    acc[v["dateTime"][:10]].append(float(v["value"]))
    return {k: round(sum(v) / len(v), 3) for k, v in acc.items()}

if __name__ == "__main__":
    m = sys.argv[1]
    if m == "dv":
        site, param, stat = sys.argv[2:5]; r = dv(site, param, stat, *(sys.argv[5:7]))
        tag = f"{site}_{param}_{stat}_dv"
    else:
        site, param = sys.argv[2:4]; r = iv_daily(site, param, *(sys.argv[4:6]))
        tag = f"{site}_{param}_iv"
    write_daily(f"{OUT}/{tag}.csv.gz", r)
    ys = complete_years(r)
    print(tag, len(r), min(r) if r else None, max(r) if r else None, "complete years", len(ys), (ys[0], ys[-1]) if ys else "")
