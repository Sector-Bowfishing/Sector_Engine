"""Map RISE catalog items -> locations via catalog-record (location.catalogRecords -> record.catalogItems)."""
import json
from common import *
H = {"Accept": "application/vnd.api+json"}
locs = json.load(open(f"{RAW}/rise/locations.json"))
items = json.load(open(f"{RAW}/rise/catalog_items_level.json"))
want = {str(i["attributes"]["_id"]) for i in items}
rec2loc = {}
for l in locs:
    for r in (l["relationships"].get("catalogRecords") or {}).get("data", []):
        rec2loc[r["id"].rsplit("/", 1)[1]] = l["attributes"]["_id"]
item2loc, done = {}, 0
for rid, lid in rec2loc.items():
    s, d = get_json(f"https://data.usbr.gov/rise/api/catalog-record/{rid}", H, sleep=0.15)
    if not d:
        continue
    for ci in d["data"]["relationships"]["catalogItems"]["data"]:
        i = ci["id"].rsplit("/", 1)[1]
        if i in want:
            item2loc[i] = lid
    done += 1
json.dump(item2loc, open(f"{RAW}/rise/item2loc.json", "w"))
print("records", done, "items mapped", len(item2loc), "of", len(want))
