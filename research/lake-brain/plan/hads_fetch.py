#!/usr/bin/env python3
"""Resumable, rate-limit-aware pull of the IEM HADS archive pool-elevation stream (HPIR*) for NWS location ids.
usage: hads_fetch.py LID[,LID...] [--from 2011] [--to 2026]
Per station it walks years newest -> oldest and stops after 2 consecutive years with no HP values (the archive starts ~2011).
Output: <PLAN>/history/hads/<LID>_<year>.csv.gz (utc_valid,value,col). One request at a time, SLEEP s between requests; HTTP 429 -> back off."""
import sys, io, csv, gzip, time, os, datetime as dt
from common import *
SLEEP = float(os.environ.get("HADS_SLEEP", "7"))
OUT = f"{PLAN}/history/hads"; os.makedirs(OUT, exist_ok=True)

def fetch_year(lid, y, y2=None):
    y2 = y2 or y
    a = f"{y}-01-01T00:00Z"; b = f"{y2 + 1}-01-01T00:00Z" if y2 < dt.date.today().year else dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    url = f"https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations={lid}&sts={a}&ets={b}&what=txt&delim=comma"
    wait = 60
    for attempt in range(8):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  429 for {lid} {y}; sleeping {wait}s", flush=True); time.sleep(wait); wait = min(wait * 2, 600); continue
            if e.code in (404, 400): return ""
            time.sleep(10)
        except Exception as e:
            print("  err", e, flush=True); time.sleep(20)
    raise RuntimeError("giving up " + lid + str(y))

def chunks(y0, y1, size=3):
    out = []; e = y1
    while e >= y0:
        s0 = max(y0, e - size + 1); out.append((s0, e)); e = s0 - 1
    return out

def one(lid, y0, y1):
    empty = 0; total = 0
    for a, b in chunks(y0, y1):
        p = f"{OUT}/{lid}_{a}-{b}.csv.gz"
        if os.path.exists(p):
            n = sum(1 for _ in gzip.open(p, "rt")) - 1
        elif all(os.path.exists(f"{OUT}/{lid}_{y}.csv.gz") for y in range(a, b + 1)):
            n = 1  # per-year files from the first version of this script
        else:
            txt = fetch_year(lid, a, b); time.sleep(SLEEP)
            rows = []
            if txt and not txt.startswith(("Error", "Too many")):
                rd = csv.DictReader(io.StringIO(txt))
                cols = [c for c in (rd.fieldnames or []) if c.startswith("HPIR")]
                for r in rd:
                    for c in cols:
                        v = r.get(c)
                        if v not in ("", None):
                            rows.append((r["utc_valid"], v, c)); break
            with gzip.open(p, "wt") as f:
                f.write("utc_valid,value,col\n")
                for r in rows: f.write(",".join(r) + "\n")
            n = len(rows)
        total += n
        print(f"{lid} {a}-{b} {n}", flush=True)
        empty = empty + 1 if n == 0 else 0
        if empty >= 1: break
    return total
if __name__ == "__main__":
    lids = sys.argv[1].split(",")
    y0 = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 2011
    y1 = int(sys.argv[sys.argv.index("--to") + 1]) if "--to" in sys.argv else dt.date.today().year
    for l in lids: print("==", l, one(l, y0, y1), flush=True)
