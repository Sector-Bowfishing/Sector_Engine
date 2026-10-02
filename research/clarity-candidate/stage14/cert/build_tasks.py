"""Stage 14 cert (value-blind): ACOLITE tasks from a matched sample CSV (id, lat, lon, item, ...). Pass times come from
the extraction outputs; elevation from USGS EPQS (US) or Copernicus GLO-30 (elsewhere). Crops as in Stage 12.
  python build_tasks.py SAMPLE_CSV OUT_JSON EXTRACT_OUT_CSV [EXTRACT_OUT_CSV ...]"""
import csv, json, sys, math, urllib.request, time, collections, os, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
ECACHE = f"{S}/stage14/cert/elevations.json"
EL = json.load(open(ECACHE)) if os.path.exists(ECACHE) else {}
def epqs(lat, lon):
    for i in range(4):
        try:
            with urllib.request.urlopen(f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&wkid=4326&units=Meters&includeDate=false", timeout=30) as r:
                v = float(json.load(r).get("value")); return v if v > -100 else None
        except Exception: time.sleep(2 * (i + 1))
    return None
def glo30(lat, lon):
    import rasterio
    la, lo = math.floor(lat), math.floor(lon)
    t = f"Copernicus_DSM_COG_10_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM"
    try:
        with rasterio.open(f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{t}/{t}.tif") as ds:
            v = float(next(ds.sample([(lon, lat)]))[0]); return v if v > -100 else None
    except Exception: return None
def elev(lat, lon, us):
    k = f"{lat},{lon}"
    if k not in EL: EL[k] = epqs(lat, lon) if us else glo30(lat, lon)
    return EL[k]
smp = list(csv.DictReader(open(sys.argv[1])))
pt = {}
for p in sys.argv[3:]:
    for r in csv.DictReader(open(p)):
        if r.get("item") and r.get("pass_time"): pt[(r["id"], r["item"])] = r["pass_time"]
by = collections.defaultdict(list)
for r in smp: by[r["item"]].append(r)
T = []
for item, xs in sorted(by.items()):
    crops, left = [], list(xs)
    while left:
        c = left[0]; la, lo = float(c["lat"]), float(c["lon"])
        inside = [y for y in left if abs(float(y["lat"]) - la) < 0.07 and abs(float(y["lon"]) - lo) < 0.09]
        crops.append({"lat": la, "lon": lo, "us": c.get("src") != "SYKE", "points": [[float(y["lat"]), float(y["lon"]), y["id"]] for y in inside]})
        left = [y for y in left if y not in inside]
    T.append({"item": item, "pass_time": pt.get((xs[0]["id"], item)), "platform": xs[0].get("platform"), "crops": crops})
todo = [c for t in T for c in t["crops"] if f"{c['lat']},{c['lon']}" not in EL]
with cf.ThreadPoolExecutor(8) as ex: list(ex.map(lambda c: elev(c["lat"], c["lon"], c["us"]), todo))
for t in T:
    for c in t["crops"]: c["elev"] = EL.get(f"{c['lat']},{c['lon']}")
json.dump(EL, open(ECACHE, "w")); json.dump(T, open(sys.argv[2], "w"))
print(len(T), "items;", sum(len(t["crops"]) for t in T), "crops;", sum(1 for t in T for c in t["crops"] if c["elev"] is None), "crops without elevation;",
      sum(1 for t in T if not t["pass_time"]), "items without pass time")
