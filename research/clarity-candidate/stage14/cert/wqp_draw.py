"""Stage 14 cert protocol sections 3-4 (value-blind): the eligible WQP pool, lakes, the seeded draw, and the STAC
prescreen. Reads the blind index (no secchi_m) and only the site/date columns of turbidity.csv. Writes wqp_pool.json,
wqp_draw.csv, in_wqp_c1.csv, in_wqp_legacy.csv, wqp_draw.json."""
import csv, json, math, random, collections, sys, datetime as dt, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
def rd(p): return list(csv.DictReader(open(f"{S}/{p}", encoding="utf-8", errors="ignore")))
# rule 2: Stage 5-13 development site ids
dev_ids = set()
for p in ("stage6/station_days.csv", "stage6/readouts.csv", "stage6/readouts_old.csv", "stage6/landsat_readouts.csv", "stage8/fresh_draw.csv", "stage8/fresh_readouts.csv",
          "stage8/val_in.csv", "stage8/val_out.csv", "stage11/corpus/e_draw.csv", "stage11/corpus/e_readouts.csv", "stage11/corpus/g_days.csv", "stage11/corpus/g_readouts.csv"):
    for r in rd(p): dev_ids.add(r["site"])
for l in open(f"{S}/stage7/national_sites.txt"):
    if l.strip(): dev_ids.add(l.strip())
for x in json.load(open(f"{S}/stage11/corpus/corpus.json")): dev_ids.add(x["site"])
# rule 5: Stage 5-13 development stations; rule 6: blind-sample sites
dev_xy = {(x["lat"], x["lon"]) for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
for p in ("stage6/readouts.csv", "stage6/landsat_readouts.csv", "stage8/fresh_readouts.csv", "stage8/val_out.csv", "stage11/corpus/e_readouts.csv", "stage11/corpus/g_readouts.csv"):
    for r in rd(p):
        if r.get("item") or r.get("n_valid"): dev_xy.add((float(r["lat"]), float(r["lon"])))
for j in json.load(open(f"{S}/stage11/ac/jobs_aeronet.json")): dev_xy.add((j["lat"], j["lon"]))
bl_xy = {(float(r["lat"]), float(r["lon"])) for p in ("stage12/cert/blind_sample.csv", "stage13/cert/blind_sample13.csv") for r in rd(p)}
# rule 7: Stage 1-4 site-days
q9_days = {(r["site_id"], r["date"]) for p in ("q9/national_sample.csv", "q9/targeted_sample.csv", "q9/targeted_capped.csv") for r in rd(p)}
q9_xy = {(float(r["lat"]), float(r["lon"])) for p in ("q9/national_sample.csv", "q9/targeted_sample.csv", "q9/targeted_capped.csv") for r in rd(p)}
def grid(pts):
    g = collections.defaultdict(list)
    for a, b in pts: g[(int(a / 0.05), int(b / 0.05))].append((a, b))
    return g
def km(a, b, c, d): return 6371 * math.hypot(math.radians(a - c), math.radians(b - d) * math.cos(math.radians(a)))
def near(g, la, lo, lim=5.0):
    ci, cj = int(la / 0.05), int(lo / 0.05)
    return any(km(la, lo, a, b) <= lim for di in range(-2, 3) for dj in range(-2, 3) for a, b in g.get((ci + di, cj + dj), []))
GD, GB, GQ = grid(dev_xy), grid(bl_xy), grid(q9_xy)
idx = rd("stage14/cert/wqp_blind_index.csv")
last = collections.defaultdict(str)
for r in idx: last[r["site_id"]] = max(last[r["site_id"]], r["date"])
site = {}
for r in idx: site.setdefault(r["site_id"], {"lat": float(r["lat"]), "lon": float(r["lon"]), "state": r["state"], "org": r["org"]})
B = (34.27, -86.42, 35.06, -85.60)
def ok_site(s):
    v = site[s]; la, lo = v["lat"], v["lon"]
    return (s not in dev_ids and last[s] < "2026-01-01" and not (B[0] <= la <= B[2] and B[1] <= lo <= B[3])
            and not near(GD, la, lo) and not near(GB, la, lo))
OK = {s for s in site if ok_site(s)}
days = sorted({(r["site_id"], r["date"]) for r in idx if r["site_id"] in OK and "2018-01-01" <= r["date"] <= "2025-12-31"
               and r.get("bottom_visible") != "true" and (r["site_id"], r["date"]) not in q9_days})
# lakes: single linkage within 5 km over eligible sites
sites = sorted({s for s, _ in days}); par = {s: s for s in sites}
def find(s):
    while par[s] != s: par[s] = par[par[s]]; s = par[s]
    return s
g = collections.defaultdict(list)
for s in sites: g[(int(site[s]["lat"] / 0.05), int(site[s]["lon"] / 0.05))].append(s)
for s in sites:
    la, lo = site[s]["lat"], site[s]["lon"]; ci, cj = int(la / 0.05), int(lo / 0.05)
    for di in range(-2, 3):
        for dj in range(-2, 3):
            for t in g.get((ci + di, cj + dj), []):
                if t != s and km(la, lo, site[t]["lat"], site[t]["lon"]) <= 5.0: par[find(s)] = find(t)
lake = {s: "W" + find(s) for s in sites}
strict = {s: not near(GQ, site[s]["lat"], site[s]["lon"]) for s in sites}
turb_days = set()
with open(f"{S}/q9/wqp/turbidity.csv", newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh): turb_days.add((r["site_id"], r["date"]))      # presence only; the value column is not used
cool = lambda d: int(d[5:7]) in (10, 11, 12, 1, 2, 3, 4)
pool = [{"site": s, "date": d, "turb": (s, d) in turb_days} for s, d in days]
json.dump({"site_days": len(pool), "sites": len(sites), "lakes": len(set(lake.values())), "states": len({site[s]["state"] for s in sites}),
           "cool_site_days": sum(cool(p["date"]) for p in pool), "with_same_day_turbidity": sum(p["turb"] for p in pool),
           "strict_subset_sites": sum(strict.values())}, open(f"{S}/stage14/cert/wqp_pool.json", "w"), indent=1)
rng = random.Random(20261015); rng.shuffle(pool); pool.sort(key=lambda p: 0 if p["turb"] else 1)
N = 7000; per_lake, per_sm, per_state, draw = collections.Counter(), set(), collections.Counter(), []
for p in pool:
    if len(draw) >= N: break
    s = p["site"]; sm = (s, p["date"][:7]); lk = lake[s]; st = site[s]["state"]
    if sm in per_sm or per_lake[lk] >= 6 or per_state[st] >= 0.15 * N: continue
    per_sm.add(sm); per_lake[lk] += 1; per_state[st] += 1
    draw.append({"id": f"WQP:{s}|{p['date']}", "lat": site[s]["lat"], "lon": site[s]["lon"], "date": p["date"], "set": "WQP", "src": "WQP", "lake": lk,
                 "state": st, "season": "cool" if cool(p["date"]) else "warm", "site": s, "org": site[s]["org"], "turb_present": p["turb"], "strict": strict[s]})
with open(f"{S}/stage14/cert/wqp_draw.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(draw[0])); w.writeheader(); w.writerows(draw)
print(json.load(open(f"{S}/stage14/cert/wqp_pool.json")), "draw", len(draw), "lakes", len({d["lake"] for d in draw}), "states", len(per_state),
      "cool", sum(d["season"] == "cool" for d in draw), "turb", sum(d["turb_present"] for d in draw), "top states", per_state.most_common(6))
if "--prescreen" not in sys.argv: sys.exit()
sys.argv = ["x"]; sys.path.insert(0, f"{S}/stage6")
import extract as E
def coll(d): return "sentinel-2-l2a" if d[:4] in ("2017", "2022") else "sentinel-2-c1-l2a"
def q(r):
    d0 = dt.date.fromisoformat(r["date"])
    body = {"collections": [coll(r["date"])], "intersects": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
            "datetime": f"{(d0 - dt.timedelta(days=1)).isoformat()}T00:00:00Z/{(d0 + dt.timedelta(days=1)).isoformat()}T23:59:59Z", "limit": 50}
    for i in range(3):
        try:
            fs = E.post(E.ES_SEARCH, body).get("features", [])
            return r, any((f["properties"].get("eo:cloud_cover") if f["properties"].get("eo:cloud_cover") is not None else 100) <= 60 for f in fs)
        except Exception: pass
    return r, False
keep = []
with cf.ThreadPoolExecutor(12) as ex:
    for n, (r, ok) in enumerate(ex.map(q, draw), 1):
        if ok: keep.append(r)
        if n % 1000 == 0: print("prescreen", n, len(keep), flush=True)
cols = list(draw[0].keys())
for tag, cond in (("c1", lambda r: coll(r["date"]) == "sentinel-2-c1-l2a"), ("legacy", lambda r: coll(r["date"]) == "sentinel-2-l2a")):
    with open(f"{S}/stage14/cert/in_wqp_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows([r for r in keep if cond(r)])
res = {"drawn": len(draw), "passed": len(keep), "cool_passed": sum(r["season"] == "cool" for r in keep), "by_collection": dict(collections.Counter(coll(r["date"]) for r in keep))}
json.dump(res, open(f"{S}/stage14/cert/wqp_draw.json", "w"), indent=1); print(res)
