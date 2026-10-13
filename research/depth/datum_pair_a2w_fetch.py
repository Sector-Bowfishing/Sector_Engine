#!/usr/bin/env python3
"""Step 1 of the datum pairing: for every DATUM_UNKNOWN lake whose live level is an Access2Water / CWMS series, fetch the A2W location
record (timeseries list with latest values) and the CWMS location record(s) (vertical-datum) of the level series.
Read-only GETs. Output: <cache>/a2w_series.json  (lake -> chosen level tsid + all Elev candidates + location datums)
Run: venv python -I research/depth/datum_pair_a2w_fetch.py"""
import csv, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datum_pair_common import *

REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption")
CAND = json.load(open(f"{REPO}/jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]
BIND = {r["lake_id"]: r for r in csv.DictReader(open(os.path.expanduser("~/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/verified_bindings_v2.csv")))}
A2WLOC = {}
for f in os.listdir(os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/binding/raw/a2w")):
    if f.startswith("locations_"):
        for l in json.load(open(os.path.expanduser(f"~/Desktop/Development/Sector_Research_Data/lake-brain/binding/raw/a2w/{f}"))):
            A2WLOC[(l["provider"], l["code"])] = l


def main():
    out = {}
    for c in CAND:
        if "DATUM_UNKNOWN" not in c["blockedReasons"]:
            continue
        prov = c["levelSource"]["provider"]
        if prov not in ("a2w", "cwms", "cwms-saw", "cwms-nwdp"):
            continue
        lid = c["lakeId"]; b = BIND[lid]
        rec = {"provider": prov, "station": b["station"], "series": b["series_or_param"]}
        if prov == "a2w":
            office, code = b["station"].split(":", 1)
            loc = A2WLOC.get((office, code))
            rec["a2wLocation"] = {"office": office, "code": code, "slug": loc and loc["slug"], "vertical_datum": loc and loc["vertical_datum"], "kind": loc and loc["kind"]}
            if loc:
                r = a2w(f"providers/{office.lower()}/locations/{loc['slug']}")
                recs = r.get("data") or []
                rec["a2wUrl"] = r.get("_url")
                ts = []
                for x in recs:
                    for t in (x.get("timeseries") or []):
                        if t.get("base_parameter") == "Elev":
                            ts.append({k: t.get(k) for k in ("tsid", "label", "parameter", "unit", "latest_time", "latest_value", "sort_order")})
                rec["a2wElevSeries"] = ts
        out[lid] = rec
    json.dump(out, open(f"{ROOT}/a2w_series.json", "w"), indent=1)
    print(len(out), "lakes")


if __name__ == "__main__":
    main()
