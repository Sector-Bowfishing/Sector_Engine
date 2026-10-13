#!/usr/bin/env python3
"""Pull a CWMS time series (CWMS Data API, unit=EN) in multi-year windows and reduce to daily values (gz csv date,value).
usage: cwms_pull.py OFFICE 'TSID' TZ [begin-year] [end-year] [mode]   mode: mean (default) | last (value at end-of-day / midnight)
Local-date convention: sub-daily series -> mean of values per local calendar day (TZ); '~1Day'/'1Day'/irregular '0' daily-stamped -> value stamped at
00:00-12:00 local belongs to the previous day (CWMS end-of-day stamps), otherwise to the stamp date."""
import sys, json, zoneinfo, collections
from common import *
BASE = "https://cwms-data.usace.army.mil/cwms-data"
OUT = f"{PLAN}/history/cwms"; os.makedirs(OUT, exist_ok=True)

def pull(office, tsid, tz, y0, y1, step_years=3, sleep=0.5):
    z = zoneinfo.ZoneInfo(tz); acc = collections.defaultdict(list); n = 0
    for ys in range(y0, y1 + 1, step_years):
        b = f"{ys}-01-01T00:00:00Z"; e = f"{min(ys + step_years - 1, y1)}-12-31T23:59:59Z"
        q = urllib.parse.urlencode({"name": tsid, "office": office, "begin": b, "end": e, "unit": "EN", "page-size": 100000})
        url = f"{BASE}/timeseries?{q}"
        while url:
            try:
                d = json.loads(get(url, accept="application/json;version=2", timeout=180, sleep=sleep))
            except urllib.error.HTTPError as ex:
                print("  http", ex.code, ys); break
            for t, v, *_ in d.get("values", []):
                if v is None: continue
                n += 1
                acc[t].append(v)
            nxt = d.get("next-page")
            url = f"{BASE}/timeseries?{q}&page={urllib.parse.quote(nxt)}" if nxt else None
    return acc, n

def daily(acc, tz, mode="mean", stamped_end_of_day=False):
    z = zoneinfo.ZoneInfo(tz); per = collections.defaultdict(list)
    for t, vs in acc.items():
        loc = dt.datetime.fromtimestamp(t / 1000, tz=dt.timezone.utc).astimezone(z)
        day = (loc - dt.timedelta(minutes=1)).date() if stamped_end_of_day else loc.date()
        per[day.isoformat()].append((t, vs[0]))
    out = {}
    for d, xs in per.items():
        xs.sort()
        out[d] = round(xs[-1][1] if mode == "last" else sum(v for _, v in xs) / len(xs), 3)
    return out

if __name__ == "__main__":
    office, tsid, tz = sys.argv[1:4]
    y0 = int(sys.argv[4]) if len(sys.argv) > 4 else 1960; y1 = int(sys.argv[5]) if len(sys.argv) > 5 else dt.date.today().year
    mode = sys.argv[6] if len(sys.argv) > 6 else "mean"
    acc, n = pull(office, tsid, tz, y0, y1)
    eod = ("1Day" in tsid) or (".0.0." in tsid)
    r = daily(acc, tz, mode, stamped_end_of_day=eod)
    tag = f"{office}_{tsid.replace('/', '_').replace(' ', '')}"
    write_daily(f"{OUT}/{tag}.csv.gz", r)
    ys = complete_years(r)
    print(tag, "raw", n, "days", len(r), min(r) if r else None, max(r) if r else None, "complete", len(ys), (ys[0], ys[-1]) if ys else "", "eod" if eod else "")
