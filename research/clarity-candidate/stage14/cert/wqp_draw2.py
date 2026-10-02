"""Addendum A2 (value-blind): re-prescreen the not-yet-extracted first-draw events at eo:cloud_cover <= 20%, and draw
7,000 more site-days in the frozen seeded order (continuing past the first draw), prescreened the same way.
Writes in_wqp_a2_{c1,legacy}.csv, wqp_draw2.csv, wqp_draw2.json."""
import csv, json, sys, collections, datetime as dt, concurrent.futures as cf, runpy, random
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
C = f"{S}/stage14/cert"
src = open(f"{C}/wqp_draw.py").read().split("rng = random.Random(20261015)")[0]
ns = {}; exec(src, ns)                                   # rebuilds the identical pool, lakes and helpers (value-blind)
pool, lake, site, cool, strict = ns["pool"], ns["lake"], ns["site"], ns["cool"], ns["strict"]
rng = random.Random(20261015); rng.shuffle(pool); pool.sort(key=lambda p: 0 if p["turb"] else 1)
first = {r["id"] for r in csv.DictReader(open(f"{C}/wqp_draw.csv"))}
N = 7000; per_lake, per_sm, per_state, d1, d2 = collections.Counter(), set(), collections.Counter(), [], []
for p in pool:                                           # replay draw 1 exactly, then continue for draw 2
    s = p["site"]; sm = (s, p["date"][:7]); lk = lake[s]; st = site[s]["state"]; rid = f"WQP:{s}|{p['date']}"
    if len(d1) < N:
        if sm in per_sm or per_lake[lk] >= 6 or per_state[st] >= 0.15 * N: continue
        per_sm.add(sm); per_lake[lk] += 1; per_state[st] += 1; d1.append(rid)
        if len(d1) == N: per_state = collections.Counter()
        continue
    if len(d2) >= N: break
    if sm in per_sm or per_lake[lk] >= 6 or per_state[st] >= 0.15 * N: continue
    per_sm.add(sm); per_lake[lk] += 1; per_state[st] += 1
    d2.append({"id": rid, "lat": site[s]["lat"], "lon": site[s]["lon"], "date": p["date"], "set": "WQP", "src": "WQP", "lake": lk, "state": st,
               "season": "cool" if cool(p["date"]) else "warm", "site": s, "org": site[s]["org"], "turb_present": p["turb"], "strict": strict[s]})
assert set(d1) == first, "draw 1 replay mismatch"
with open(f"{C}/wqp_draw2.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(d2[0])); w.writeheader(); w.writerows(d2)
done = set()
for t in ("c1", "legacy"):
    done |= {r["id"] for r in csv.DictReader(open(f"{C}/out_wqp_{t}.csv"))}
rest = [r for t in ("c1", "legacy") for r in csv.DictReader(open(f"{C}/in_wqp_{t}.csv")) if r["id"] not in done]
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
            return r, any((f["properties"].get("eo:cloud_cover") if f["properties"].get("eo:cloud_cover") is not None else 100) <= 20 for f in fs)
        except Exception: pass
    return r, False
keep = []
cand = rest + [{k: str(v) for k, v in r.items()} for r in d2]
with cf.ThreadPoolExecutor(12) as ex:
    for n, (r, ok) in enumerate(ex.map(q, cand), 1):
        if ok: keep.append(r)
        if n % 2000 == 0: print("prescreen", n, len(keep), flush=True)
cols = list(d2[0].keys())
for tag, cond in (("c1", lambda r: coll(r["date"]) == "sentinel-2-c1-l2a"), ("legacy", lambda r: coll(r["date"]) == "sentinel-2-l2a")):
    with open(f"{C}/in_wqp_a2_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows([r for r in keep if cond(r)])
res = {"draw1_not_yet_extracted": len(rest), "draw2": len(d2), "draw2_cool": sum(1 for r in d2 if r["season"] == "cool"), "passed_20pct": len(keep),
       "passed_from_draw1": sum(1 for r in keep if r["id"] in first), "passed_from_draw2": sum(1 for r in keep if r["id"] not in first),
       "by_collection": dict(collections.Counter(coll(r["date"]) for r in keep)), "draw2_states": dict(per_state.most_common(8))}
json.dump(res, open(f"{C}/wqp_draw2.json", "w"), indent=1); print(res)
