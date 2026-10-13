"""Fetch CWMS Data API catalogs (locations + level-ish timeseries) for every district office. Read-only."""
import json, os, sys, urllib.parse
from common import *

OFFICES = "LRC LRE LRB LRH LRL LRN LRP MVK MVM MVN MVP MVR MVS NAB NAE NAN NAO NAP NWK NWO NWP NWS NWW POA POH SAC SAJ SAM SAS SAW SPA SPK SPL SPN SWF SWG SWL SWT NWDP NWDM NWD NWDB MVD LRD SWD SPD SAD NAD POD HQ".split()
H = {"Accept": "application/json;version=2"}
BASE = "https://cwms-data.usace.army.mil/cwms-data"
TS_RE = r".*\.(Elev|Stor|Stage|Flow-Res Out)(-[^.]*)?\..*"
os.makedirs(f"{RAW}/cwms", exist_ok=True)


def paged(path, params):
    out, page = [], None
    for _ in range(40):
        p = dict(params)
        if page:
            p["page"] = page
        s, d = get_json(f"{BASE}/{path}?" + urllib.parse.urlencode(p), H, timeout=120)
        if d is None:
            return out, s
        out += d.get("entries", [])
        page = d.get("next-page")
        if not page:
            break
    return out, 200


for off in OFFICES:
    ts_f, loc_f = f"{RAW}/cwms/ts_{off}.json", f"{RAW}/cwms/loc_{off}.json"
    if not os.path.exists(ts_f):
        ts, st = paged("catalog/TIMESERIES", {"office": off, "like": TS_RE, "page-size": 1000})
        json.dump({"status": st, "entries": ts}, open(ts_f, "w"))
        print(off, "ts", st, len(ts), flush=True)
    if not os.path.exists(loc_f):
        loc, st = paged("catalog/LOCATIONS", {"office": off, "page-size": 1000})
        json.dump({"status": st, "entries": loc}, open(loc_f, "w"))
        print(off, "loc", st, len(loc), flush=True)
