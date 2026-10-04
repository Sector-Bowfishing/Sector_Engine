"""Stage 21 (value-blind): FRESH current-era pairs F25/F26 (PREREGISTRATION_STAGE21.md section 2) — the stage20/build20.py
ops rules (S2C vs S2A/S2B 1-2 days apart, both <= 20% cloud; 2025 Apr-Oct, 2026 Apr-Sep; per site the closest pair, then
lowest cloud) at sites NOT used by Stage 20's operational pairs for that year, next sites in the same md5 order, 80 per
year. Writes stage21/ops21_pairs.json and stage21/tasks21_ops_ref.json (S2A/B side) + tasks21_ops_c.json (S2C side)."""
import json, os, sys, hashlib, datetime as dt, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage6", f"{S}/stage20"]
import safe as SAFE, extract as E6
src = open(f"{S}/stage20/build20.py").read()
ns = {"__name__": "b20"}; exec(src.split('if sys.argv[1] == "prelim":')[0], ns)          # sites, elev, crops, finish helpers
sites, crops = ns["sites"], ns["crops"]
used = {(p["year"], p["site"]) for p in json.load(open(f"{S}/stage20/ops20_pairs.json"))}
N = 80; rank = lambda s, y: hashlib.md5(f"{s}|{y}".encode()).hexdigest()
meta, TR, TC = [], [], []
for year, rng in ((2025, ("2025-04-01", "2025-10-31")), (2026, ("2026-04-01", "2026-09-30"))):
    order = [s for s in sorted(sites, key=lambda s: rank(s, year)) if (year, s) not in used]
    def find(sname):
        s = sites[sname]
        try:
            f = E6.post(E6.ES_SEARCH, {"collections": ["sentinel-2-c1-l2a"], "intersects": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                                       "datetime": f"{rng[0]}T00:00:00Z/{rng[1]}T23:59:59Z", "limit": 300, "query": {"eo:cloud_cover": {"lte": 20}}}).get("features", [])
        except Exception: return sname, None
        C = [i for i in f if i["properties"]["platform"] == "sentinel-2c"]; AB = [i for i in f if i["properties"]["platform"] in ("sentinel-2a", "sentinel-2b")]
        day = lambda i: dt.date.fromisoformat(i["properties"]["datetime"][:10]); best = None
        for c in C:
            for o in AB:
                gap = abs((day(c) - day(o)).days)
                if 1 <= gap <= 2:
                    k = (gap, c["properties"]["eo:cloud_cover"] + o["properties"]["eo:cloud_cover"], c["id"], o["id"])
                    if best is None or k < best[0]: best = (k, c, o, gap)
        return sname, best
    got = []
    with cf.ThreadPoolExecutor(8) as ex:
        for sname, best in ex.map(find, order[: N * 3]):
            if best and len(got) < N: got.append((sname, best))
    for sname, (k, c, o, gap) in got:
        lc, lo = SAFE.l1c_for(c["id"]), SAFE.l1c_for(o["id"])
        if not (lc and lo): continue
        s = sites[sname]; key = f"{sname}|{o['id']}|{c['id']}"; cr = crops([(s["lat"], s["lon"], key)])
        TR.append({"run": f"O{year}_{lo}_{sname}", "l1c": lo, "crops": cr}); TC.append({"run": f"S{year}_{lc}_{sname}", "l1c": lc, "crops": cr})
        meta.append({"year": year, "site": sname, "s2c": c["id"], "other": o["id"], "gap_days": gap, "l1c_c": lc, "l1c_o": lo})
    print(year, len(got), "pairs", flush=True)
json.dump(meta, open(f"{S}/stage21/ops21_pairs.json", "w"))
for T, name in ((TR, "ref"), (TC, "c")):
    jobs = [c for t in T for c in t["crops"]]
    with cf.ThreadPoolExecutor(8) as ex:
        for c, v in zip(jobs, ex.map(lambda c: ns["elev"](c["lat"], c["lon"], not str(c["points"][0][2]).startswith("G:")), jobs)): c["elev"] = v
    json.dump(T, open(f"{S}/stage21/tasks21_ops_{name}.json", "w"))
json.dump(ns["EL"], open(ns["EP"], "w"))
print("F25/F26", len(meta), "pairs; ref runs", len(TR), "S2C runs", len(TC), "| overlap with Stage 20 sites:", sum(1 for m in meta if (m["year"], m["site"]) in used))
