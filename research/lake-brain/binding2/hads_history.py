"""Daily history for NWPS-sourced lake gauges from the IEM HADS archive (NWS DCP raw data; HP/HG physical elements).
For each station in hads_probe.json with data, request calendar years from the first year with data to 2025 (what=txt, UTC), take the lake-level column that matches the NWPS
element (e.g. HPIRG*), average to a daily value per UTC date, and write history/hads_<ID>_<element>.csv.gz ('YYYY-MM-DD,value_ft'). 5-15 minute data; a day counts
when it has >= 4 observations. Politeness: sequential, >= 1 s between requests, resumes from existing files."""
import csv, gzip, io, json, os, collections, sys
from common2 import *

MINOBS = int(os.environ.get("MINOBS", "1"))
probe = json.load(open(f"{B2}/hads_probe.json"))
for sid, v in probe.items():
    if not v.get("firstYear"):
        continue
    el = v["element"]
    out = f"{B2}/history/hads_{sid}_{el}.csv.gz"
    if os.path.exists(out):
        continue
    daily = collections.defaultdict(list)
    first = max(2004, v["firstYear"] - 4) if v["firstYear"] > 2004 else 2004      # first sample year may be up to 4 years before the first hit
    for y in range(first, 2026):
        s, b = http_get(f"https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations={sid}&sts={y}-01-01T00:00Z&ets={y+1}-01-01T00:00Z&what=txt&delim=comma&tz=UTC", timeout=180, sleep=1.0, retries=2)
        if s != 200 or b.startswith("Error"):
            continue
        rd = csv.DictReader(io.StringIO(b))
        cols = [c for c in (rd.fieldnames or []) if c.startswith(el[:5])]
        if not cols:
            cols = [c for c in (rd.fieldnames or []) if c[:2] in ("HP", "HG")]
        # choose the column with the most numeric rows
        rows = list(rd)
        best = max(cols, key=lambda c: sum(1 for r in rows if r.get(c) not in (None, "", "M")), default=None)
        if not best:
            continue
        for r in rows:
            try:
                x = float(r[best])
            except Exception:
                continue
            if x < -900:
                continue
            daily[r["utc_valid"][:10]].append(x)
    series = {k: sum(v_) / len(v_) for k, v_ in daily.items() if len(v_) >= MINOBS}
    with gzip.open(out, "wt", newline="") as f:
        w = csv.writer(f)
        for k in sorted(series):
            w.writerow([k, round(series[k], 3)])
    print(sid, v["lakeId"], len(series), "days", flush=True)
