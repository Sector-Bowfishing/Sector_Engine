"""Stage 17 section 2 (value-blind): the <= 3 nearest valid neighbouring passes (Stage 11 production-gated readouts;
|dt| then scene cloud) within +-10 days of every development event, excluding the anchor item. Grouped by item into
ACOLITE tasks (crops as Stage 12/14); elevation from USGS EPQS (cached). Writes neighbors.json, tasks_nb.json."""
import csv, json, collections, sys, os, urllib.request, time, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage17/scenes"
dev = {r["id"]: r for r in json.load(open(f"{S}/stage15/analysis/dev15_rows.json"))}
corp = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
nb = collections.defaultdict(list)
for r in csv.DictReader(open(f"{S}/stage11/temporal/neighbors_readouts.csv")):
    cid = f"{r['set']}:{r['id']}"
    if cid not in dev: continue
    try: nv = int(float(r.get("n_valid") or 0)); dt = int(float(r["dt_days"]))
    except ValueError: continue
    if r.get("error") or nv < 5 or not r.get("item") or r["item"] == corp[cid]["item"] or abs(dt) > 10: continue
    nb[cid].append({"item": r["item"], "dt": dt, "cloud": float(r.get("scene_cloud") or 100), "pass_time": r.get("pass_time"), "platform": r.get("platform"),
                    "sun_elev": float(r["sun_elev"]) if r.get("sun_elev") else None, "pass_date": r.get("pass_date")})
sel = {}
for cid, v in nb.items():
    seen, keep = set(), []
    for n in sorted(v, key=lambda n: (abs(n["dt"]), n["cloud"])):
        if n["item"] in seen: continue
        seen.add(n["item"]); keep.append(n)
        if len(keep) == 3: break
    sel[cid] = keep
json.dump(sel, open(f"{D}/neighbors.json", "w"))
pts = collections.defaultdict(list); meta = {}
for cid, v in sel.items():
    x = corp[cid]
    for n in v:
        pts[n["item"]].append((x["lat"], x["lon"], f"{cid}#{n['item']}")); meta[n["item"]] = n
EL = json.load(open(f"{S}/stage14/cert/elevations.json")) if os.path.exists(f"{S}/stage14/cert/elevations.json") else {}
EL.update(json.load(open(f"{S}/stage12/corpus/elevations.json")))
def epqs(la, lo):
    for i in range(4):
        try:
            with urllib.request.urlopen(f"https://epqs.nationalmap.gov/v1/json?x={lo}&y={la}&wkid=4326&units=Meters&includeDate=false", timeout=30) as r:
                v = float(json.load(r).get("value")); return v if v > -100 else None
        except Exception: time.sleep(2 * (i + 1))
    return None
T = []
for item, ps in sorted(pts.items()):
    crops, left = [], list(ps)
    while left:
        c = left[0]; inside = [p for p in left if abs(p[0] - c[0]) < 0.07 and abs(p[1] - c[1]) < 0.09]
        crops.append({"lat": c[0], "lon": c[1], "points": [list(p) for p in inside]}); left = [p for p in left if p not in inside]
    T.append({"item": item, "pass_time": meta[item]["pass_time"], "platform": meta[item]["platform"], "crops": crops})
need = sorted({(c["lat"], c["lon"]) for t in T for c in t["crops"] if f"{c['lat']},{c['lon']}" not in EL})
with cf.ThreadPoolExecutor(8) as ex:
    for (la, lo), v in zip(need, ex.map(lambda p: epqs(*p), need)): EL[f"{la},{lo}"] = v
for t in T:
    for c in t["crops"]: c["elev"] = EL.get(f"{c['lat']},{c['lon']}")
json.dump(EL, open(f"{D}/elevations17.json", "w")); json.dump(T, open(f"{D}/tasks_nb.json", "w"))
print("events with neighbours", sum(1 for v in sel.values() if v), "neighbour scenes", sum(len(v) for v in sel.values()), "items", len(T), "crops", sum(len(t["crops"]) for t in T),
      "no elevation", sum(1 for t in T for c in t["crops"] if c["elev"] is None), "platforms", collections.Counter(t["platform"] for t in T))
