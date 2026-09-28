"""Candidate Sentinel-2 passes over a lake (Clarity Fusion Stages 2-3B).

Earth Search STAC, collection sentinel-2-c1-l2a, the lake outline's bbox,
queried in 60-day windows (limit 200, retried); a pass is a (date, platform)
with its tiles' cloud cover; a candidate has a tile at or under 40% cloud.

usage: geo/bin/python pass_candidates.py <lake geojson> <start YYYY-MM-DD> <end> <out.json>
"""
import sys, json, time, collections, datetime as dt, urllib.request
from shapely.geometry import shape
from shapely.ops import unary_union

lake_p, start, end, out = sys.argv[1:5]
lake = unary_union([shape(f["geometry"]) for f in json.load(open(lake_p))["features"]])
bbox = list(lake.bounds)
url = "https://earth-search.aws.element84.com/v1/search"
got = collections.defaultdict(list)
s = dt.date.fromisoformat(start); e = dt.date.fromisoformat(end)
while s < e:
    t = min(s + dt.timedelta(days=60), e)
    body = {"collections": ["sentinel-2-c1-l2a"], "bbox": bbox, "datetime": f"{s}T00:00:00Z/{t}T00:00:00Z", "limit": 200}
    d = None
    for i in range(5):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=120)); break
        except Exception:
            time.sleep(5 * (i + 1))
    for f in (d or {}).get("features", []):
        got[(f["properties"]["datetime"][:10], f["properties"].get("platform"))].append(f["properties"].get("eo:cloud_cover") or 0)
    s = t
passes = sorted(((k, min(v), len(v)) for k, v in got.items()))
cand = [{"date": k[0], "platform": k[1], "minCloud": c, "tiles": n} for k, c, n in passes if c <= 40]
json.dump(cand, open(out, "w"), indent=0)
print(len(passes), "passes;", len(cand), "with a tile <= 40% cloud")
