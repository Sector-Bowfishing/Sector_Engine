"""NWPS gauge metadata (usgsId, usaceId attribution, normalThreshold, flood stages) for every bound lake with provider=nwps."""
import json, sys, time
from common import *
rows = [r for r in bound() if r["provider"] == "nwps"]
out = {}
for r in rows:
    lid = r["station"]
    try:
        d = json.loads(get(f"https://api.water.noaa.gov/nwps/v1/gauges/{lid}", sleep=0.3))
    except Exception as e:
        out[lid] = {"error": str(e)}; continue
    out[lid] = {"lake": r["lakeId"], "usgsId": d.get("usgsId"), "name": d.get("name"), "description": d.get("description"),
                "rfc": (d.get("rfc") or {}).get("abbreviation"), "wfo": (d.get("wfo") or {}).get("abbreviation"),
                "pedts": d.get("pedts"), "normalThreshold": d.get("normalThreshold"),
                "flood": (d.get("flood") or {}).get("categories"), "attribution": [(a.get("abbrev"), a.get("text"), a.get("url")) for a in d.get("dataAttribution", [])],
                "obs": (d.get("status") or {}).get("observed"), "datums": d.get("datums")}
json.dump(out, open(f"{PLAN}/raw/nwps_meta.json", "w"), indent=1)
print(len(out))
