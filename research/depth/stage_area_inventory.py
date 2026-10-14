"""Inventory of USACE CWMS Elev;Area (and Stage;Area) ratings, matched to Depth candidate lakes. Read-only GETs, cached outside git.
Output: docs/brains/depth/data/stage_area_inventory.json (small)."""
import json, os, re
from datum_pair_common import get_json, CWMS

OUT = os.path.join(os.path.dirname(__file__), "../../docs/brains/depth/data/stage_area_inventory.json")
CANDS = os.path.join(os.path.dirname(__file__), "../../jobs/depth-brain/depth_brain/data/candidates.json")


def specs(office):
    out, page = [], None
    for _ in range(60):
        params = {"office": office, "rating-id-mask": "*Elev;Area*", "page-size": 500}
        if page:
            params["page"] = page
        r = get_json(f"{CWMS}/ratings/spec", params, headers={"Accept": "application/json;version=2"}, retries=1)
        d = r.get("data") if isinstance(r, dict) else None
        if not d or "specs" not in d:
            break
        out += [s["rating-id"] for s in d["specs"]]
        page = d.get("next-page")
        if not page:
            break
    return out


def main():
    offs = get_json(f"{CWMS}/offices", {}, headers={"Accept": "application/json;version=2"})["data"]
    offs = [o["name"] for o in (offs if isinstance(offs, list) else offs.get("offices", []))]
    inv = {}
    for o in offs:
        s = specs(o)
        if s:
            inv[o] = s
            print(o, len(s), flush=True)
    json.dump({"schema": "depth-stage-area-inventory-v1", "ratings": inv}, open(OUT, "w"), indent=1)


main()
