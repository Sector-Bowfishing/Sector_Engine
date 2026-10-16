"""Stage 3C Track C: ICESat-2 ATL13 (V007) granule inventory over all 54 Sector lakes (CMR search, no login)."""
import json, gzip, os, sys, urllib.request, urllib.parse
IOS = os.path.expanduser("~/Desktop/Development/iOS/sector-wind")
OUT = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/icesat2")


def lakes():
    out = []
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lakes.json")))
    for k, v in cfg["lakes"].items():
        out.append({"lake": k, "set": "development", "bbox": v["bbox"]})
    man = json.load(open(os.path.join(IOS, "docs/intelligence/wind/stage3a/national_fetch_manifest.json")))
    T = os.path.expanduser("~/Library/Caches/sector-wind/national-fetch/tables")
    for r in man["lakes"]:
        if r["status"] != "PASS":
            continue
        o = json.load(gzip.open(os.path.join(T, f"{r['slug']}.windfetch.json.gz")))
        la = [b["anchor"][0] for b in o["banks"]]; lo = [b["anchor"][1] for b in o["banks"]]
        out.append({"lake": r["slug"], "set": "directory", "bbox": [min(lo), min(la), max(lo), max(la)], "areaKm2": r["qa"]["areaKm2"]})
    return out


def granules(bbox, start="2018-10-13T00:00:00Z", end="2026-10-07T00:00:00Z"):
    n, page, dates = 0, 1, []
    while True:
        q = urllib.parse.urlencode({"short_name": "ATL13", "version": "007", "bounding_box": ",".join(map(str, bbox)),
                                    "temporal": f"{start},{end}", "page_size": 2000, "page_num": page})
        j = json.load(urllib.request.urlopen("https://cmr.earthdata.nasa.gov/search/granules.json?" + q, timeout=120))
        e = j["feed"]["entry"]; n += len(e); dates += [x["time_start"][:10] for x in e]
        if len(e) < 2000:
            break
        page += 1
    return n, (min(dates) if dates else None), (max(dates) if dates else None)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    res = []
    import time
    for L in lakes():
        for k in range(5):
            try:
                n, a, b = granules(L["bbox"]); break
            except Exception as e:
                print("retry", L["lake"], repr(e)[:80], flush=True); time.sleep(20 * (k + 1))
        else:
            n, a, b = None, None, None
        res.append({**L, "granules": n, "first": a, "last": b}); print(L["lake"], n, a, b, flush=True)
        json.dump(res, open(os.path.join(OUT, "atl13_inventory.json"), "w"), indent=1)
    json.dump(res, open(os.path.join(OUT, "atl13_inventory.json"), "w"), indent=1)
