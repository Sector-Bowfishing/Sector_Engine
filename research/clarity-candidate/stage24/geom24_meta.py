"""Stage 24 (metadata only): scene geometry for every development anchor, every Stage 19 prior pass, and every Stage 23
FL23/T2N scene, from the Element 84 STAC items (the live-available scene metadata): sun elevation/azimuth, mean view
incidence/azimuth, relative orbit, acquisition time, platform, tile, baseline. Writes geom24_items.json."""
import json, os, sys, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage6"); import extract as E6
ids = set()
for x in json.load(open(f"{S}/stage11/corpus/corpus.json")): ids.add(x["item"])
for v in json.load(open(f"{S}/stage19/neighbors19.json")).values():
    for n in v: ids.add(n["item"]); ids.update(n.get("pass_items") or [])
for p in json.load(open(f"{S}/stage23/pairs23_meta.json"))["pairs"]: ids.add(p["c"]); ids.add(p["o"])
ids = sorted(ids); print("items", len(ids), flush=True)
def get(chunk):
    for _ in range(4):
        try: return E6.post(E6.ES_SEARCH, {"collections": ["sentinel-2-c1-l2a"], "ids": chunk, "limit": 100}).get("features", [])
        except Exception: pass
    return []
out = {}
with cf.ThreadPoolExecutor(6) as ex:
    for feats in ex.map(get, [ids[i:i + 100] for i in range(0, len(ids), 100)]):
        for f in feats:
            p = f["properties"]
            out[f["id"]] = {"platform": p.get("platform"), "datetime": p.get("datetime"), "sun_elev": p.get("view:sun_elevation"), "sun_az": p.get("view:sun_azimuth"),
                            "view_inc": p.get("view:incidence_angle"), "view_az": p.get("view:azimuth"), "rel_orbit": (p.get("s2:product_uri") or "_____").split("_")[4],
                            "tile": p.get("grid:code"), "baseline": p.get("s2:processing_baseline"), "cloud": p.get("eo:cloud_cover")}
json.dump(out, open(f"{S}/stage24/geom24_items.json", "w"))
print("found", len(out), "missing", len(set(ids) - set(out)), "no view_az", sum(1 for v in out.values() if v["view_az"] is None))
