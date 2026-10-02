"""Addendum C: USGS 3DEP elevation (EPQS) at the first station of every corpus crop and at the AERONET-OC Erie site.
Writes corpus/elevations.json {"lat,lon": metres or null}."""
import json, sys, urllib.request, concurrent.futures as cf, time
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.argv = ["x"]; exec(open(f"{S}/stage12/corpus/run_corpus.py").read().split("if __name__")[0])
pts = {f"{c['lat']},{c['lon']}" for t in tasks() for c in t["crops"]}
for j in json.load(open(f"{S}/stage11/ac/jobs_aeronet.json")): pts.add(f"{j['lat']},{j['lon']}")
def q(k):
    lat, lon = k.split(",")
    for i in range(4):
        try:
            with urllib.request.urlopen(f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&wkid=4326&units=Meters&includeDate=false", timeout=30) as r:
                v = json.load(r).get("value"); v = float(v)
                return k, (v if v > -100 else None)
        except Exception:
            time.sleep(2 * (i + 1))
    return k, None
with cf.ThreadPoolExecutor(8) as ex: E = dict(ex.map(q, sorted(pts)))
json.dump(E, open(f"{S}/stage12/corpus/elevations.json", "w"))
v = [x for x in E.values() if x is not None]
print(len(E), "points;", len(v), "with elevation; max", max(v), "; >1000 m:", sum(1 for x in v if x > 1000))
