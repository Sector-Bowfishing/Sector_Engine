"""Fetch the Reclamation RISE location list and catalog items (reservoir elevation / storage) -> raw/rise/. Read-only."""
import json, os
from common import *
os.makedirs(f"{RAW}/rise", exist_ok=True)
H = {"Accept": "application/vnd.api+json"}
BASE = "https://data.usbr.gov"


def all_pages(path, per=100):
    out, page = [], 1
    while True:
        s, d = get_json(f"{BASE}{path}{'&' if '?' in path else '?'}itemsPerPage={per}&page={page}", H, timeout=120)
        if d is None:
            print("fail", path, page, s)
            break
        out += d["data"]
        if not d["links"].get("next"):
            break
        page += 1
    return out


loc = all_pages("/rise/api/location")
json.dump(loc, open(f"{RAW}/rise/locations.json", "w"))
print("locations", len(loc), flush=True)
cat = all_pages("/rise/api/catalog-item")
keep = [c for c in cat if any(k in (c["attributes"].get("parameterName") or "").lower() for k in ("elevation", "storage", "stage", "level"))]
json.dump(keep, open(f"{RAW}/rise/catalog_items_level.json", "w"))
json.dump([{"id": c["attributes"]["_id"], "param": c["attributes"].get("parameterName")} for c in cat], open(f"{RAW}/rise/catalog_param_index.json", "w"))
print("catalog", len(cat), "kept", len(keep), flush=True)
