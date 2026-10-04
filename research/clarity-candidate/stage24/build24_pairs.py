"""Stage 24 part A (metadata only): NEW nominal N0513 S2C -> S2A pairs (same relative orbit and MGRS tile, S2A 48 +- 1 h after
S2C, S2C sun >= 25, both <= 40% tile cloud, S2C baseline >= 05.13, 2026-08-01 .. 2026-10-04), one per (site, S2C physical pass),
lowest combined cloud, EXCLUDING every S2C/S2A item pair already in Stage 23 T2N. Sites: all Stage 20 sites (L: and G:, any
latitude) + one water point per Shadow pilot lake. Writes pairs24_meta.json (T24N)."""
import json, os, sys, datetime as dt, collections, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage6"); import extract as E6
T = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
REGION = {"Northeast": "ME NH VT MA RI CT NY NJ PA", "Southeast": "MD DE VA WV NC SC GA FL AL MS TN KY AR LA",
          "Midwest": "OH IN IL MI WI MN IA MO", "Plains": "ND SD NE KS OK TX", "West": "MT ID WY CO UT NV AZ NM CA OR WA", "Alaska": "AK"}
ST2R = {s: r for r, ss in REGION.items() for s in ss.split()}
sites = [dict(s, region=ST2R.get(s["site"].split("|")[-1], "Global/coastal")) for s in json.load(open(f"{S}/stage20/sites20.json"))]
PL = json.load(open("/Users/mcather/Desktop/Development/Sector_Engine-candidate/jobs/clarity-candidate/pilot_lakes.json"))["lakes"]
for l in PL:
    p = l["points"][0]; sites.append({"site": f"P:{l['slug']}", "lat": p["lat"], "lon": p["lon"], "region": "Pilot"})
old = {(p["c"], p["o"]) for p in json.load(open(f"{S}/stage23/pairs23_meta.json"))["pairs"] if p["kind"] == "T2N"}
prop = lambda i, k: i["properties"].get(k)
orbit = lambda i: (prop(i, "s2:product_uri") or "_____").split("_")[4]
def one(s):
    f = None
    for _ in range(3):
        try:
            f = E6.post(E6.ES_SEARCH, {"collections": ["sentinel-2-c1-l2a"], "intersects": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                                       "datetime": "2026-08-01T00:00:00Z/2026-10-04T23:59:59Z", "limit": 100, "query": {"eo:cloud_cover": {"lte": 40}}}).get("features", []); break
        except Exception: f = None
    f = f or []
    C = [i for i in f if prop(i, "platform") == "sentinel-2c" and (prop(i, "s2:processing_baseline") or "0") >= "05.13" and (prop(i, "view:sun_elevation") or 0) >= 25]
    A_ = [i for i in f if prop(i, "platform") == "sentinel-2a"]; best = {}
    for c in C:
        for o in A_:
            if orbit(o) != orbit(c) or prop(o, "grid:code") != prop(c, "grid:code") or (c["id"], o["id"]) in old: continue
            if abs((T(prop(o, "datetime")) - T(prop(c, "datetime"))).total_seconds() / 3600 - 48) > 1: continue
            k = f"{prop(c, 'platform')}|{prop(c, 'datetime')[:10]}|{orbit(c)}"; key = (prop(c, "eo:cloud_cover") + prop(o, "eo:cloud_cover"), c["id"], o["id"])
            if k not in best or key < best[k][0]:
                best[k] = (key, {"kind": "T24N", "site": s["site"], "region": s["region"], "lat": s["lat"], "lon": s["lon"], "c": c["id"], "o": o["id"],
                                 "c_time": prop(c, "datetime"), "o_time": prop(o, "datetime"), "c_orbit": orbit(c), "o_orbit": orbit(o), "tile": prop(c, "grid:code"),
                                 "c_cloud": prop(c, "eo:cloud_cover"), "o_cloud": prop(o, "eo:cloud_cover"), "c_baseline": prop(c, "s2:processing_baseline"),
                                 "o_baseline": prop(o, "s2:processing_baseline"), "c_sun_elev": prop(c, "view:sun_elevation"), "c_pass": k})
    return [v[1] for v in best.values()]
P = []
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(one, sites): P += r
json.dump({"sites": len(sites), "pairs": P}, open(f"{S}/stage24/pairs24_meta.json", "w"), indent=0)
print("T24N", len(P), "lakes", len({p["site"] for p in P}), "regions", dict(collections.Counter(p["region"] for p in P)),
      "cloud<=20 both", sum(1 for p in P if p["c_cloud"] <= 20 and p["o_cloud"] <= 20), "months", dict(collections.Counter(p["c_time"][:7] for p in P)))
