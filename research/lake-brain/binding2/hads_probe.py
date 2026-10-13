"""NWPS lake gauges as DIRECT_LAKE_GAUGE: how much history exists in the IEM HADS archive (NWS DCP raw data)?
For every wave-1 bound lake whose chosen series is an NWPS gauge (core + flagged + stage) test one 3-day window per year (Jan 1-3) 2003..2025 and record
the first year with data and the physical-element column. Output binding2/hads_probe.json."""
import csv, json, io, datetime as dt
from common2 import *

ver = [r for r in csv.DictReader(open(f"{BIND}/verified.csv")) if r["provider"] == "nwps"]
out = {}
for r in ver:
    sid = r["station"]; el = r["series"]
    res = {}
    for y in (2004, 2008, 2012, 2016, 2019, 2022):
        s, b = http_get(f"https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations={sid}&sts={y}-01-01T00:00Z&ets={y}-01-04T00:00Z&what=txt&delim=comma&tz=UTC", timeout=60, sleep=0.3, retries=2)
        if s != 200 or b.startswith("Error"):
            res[y] = 0; continue
        rows = list(csv.DictReader(io.StringIO(b)))
        cols = [c for c in (rows[0].keys() if rows else []) if c.startswith(el[:5]) or c.startswith("HP") or c.startswith("HG")]
        res[y] = dict(n=len(rows), cols=cols)
    yrs = [y for y, v in res.items() if v and v["n"]]
    out[sid] = dict(lakeId=r["lakeId"], element=el, status=r["bindingStatus"], firstYear=min(yrs) if yrs else None, yearsWithData=yrs, cols=sorted({c for v in res.values() if v for c in v["cols"]}))
    print(sid, r["lakeId"], "first", out[sid]["firstYear"], len(yrs), out[sid]["cols"], flush=True)
    json.dump(out, open(f"{B2}/hads_probe.json", "w"), indent=1)
