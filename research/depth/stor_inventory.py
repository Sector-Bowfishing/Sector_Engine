"""Inventory of USACE CWMS Elev;Stor ratings (storage versus elevation) for lakes WITHOUT an Elev;Area rating in stage_area_curves.json. Read-only; output docs/brains/depth/data/stor_only_inventory.json"""
import json, os
from datum_pair_common import get_json, CWMS
HERE = os.path.dirname(os.path.abspath(__file__))
cur = json.load(open(f"{HERE}/../../jobs/depth-brain/depth_brain/data/stage_area_curves.json"))["lakes"]
cands = {c["lakeId"]: c for c in json.load(open(f"{HERE}/../../jobs/depth-brain/depth_brain/data/candidates.json"))["candidates"]}
offs = [o["name"] for o in (lambda d: d if isinstance(d, list) else d.get("offices", []))(get_json(f"{CWMS}/offices", {}, headers={"Accept": "application/json;version=2"})["data"])]
inv = {}
for o in offs:
    out, page = [], None
    for _ in range(30):
        p = {"office": o, "rating-id-mask": "*Elev;Stor*", "page-size": 500}
        if page: p["page"] = page
        r = get_json(f"{CWMS}/ratings/spec", p, headers={"Accept": "application/json;version=2"}, retries=1)
        d = (r or {}).get("data")
        if not d or "specs" not in d: break
        out += [s["rating-id"] for s in d["specs"]]
        page = d.get("next-page")
        if not page: break
    if out: inv[o] = out
norm = lambda x: "".join(ch for ch in x.lower() if ch.isalnum())
hits = {}
for lid, c in cands.items():
    if lid in cur or not c.get("cwmsOffice"):
        continue
    src = (c["reference"].get("source") or "")
    tokens = set()
    if c["levelSource"].get("provider") in ("cwms", "a2w") and c["levelSource"].get("series"):
        tokens.add(norm(c["levelSource"]["series"].split(".")[0].split("-")[0]))
    if src.startswith("CWMS "):
        tokens.add(norm(src[5:].split(".")[0].split(" Top")[0].split("-")[0]))
    for o, ids in inv.items():
        for i in ids:
            if norm(i.split(".Elev")[0].split("-")[0]) in tokens and tokens:
                hits.setdefault(lid, []).append((o, i))
print(sum(len(v) for v in inv.values()), "stor ratings;", len(hits), "candidate lakes without an area rating but with a storage rating")
for lid, v in sorted(hits.items()):
    print(lid, c["shiftPossible"] if (c := cands[lid]) else None, v[0][1])
json.dump({"schema": "depth-stor-only-inventory-v1", "lakes": {k: [list(x) for x in v] for k, v in hits.items()}}, open(f"{HERE}/../../docs/brains/depth/data/stor_only_inventory.json", "w"), indent=0)
