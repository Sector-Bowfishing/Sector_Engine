"""Stage 16 protocol section 4 (value-blind): the fresh pool from the 2026-10-01 WQP pull. secchi_m is deleted on read;
turbidity.csv is read for site/date presence only. Exclusions: any site in an earlier development/certification file,
the Guntersville box, censored rows; dates 2026-01-01..2026-09-28; <= 1 site-day per site-month (seeded order, seed
20261001). Lakes = 5 km single linkage; strict flag = > 5 km from every development station and certification site.
Optional --prescreen: an item within +-1 day with eo:cloud_cover <= 20%. Writes fresh_events.csv, in_fresh_c1.csv."""
import csv, json, math, random, collections, sys, datetime as dt, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage16/fresh"; W = f"{D}/wqp"
F = json.load(open(f"{S}/stage14/cert/dev_footprint.json")); ids = set(F["site_ids"])
for p in ("wqp_draw.csv", "wqp_draw2.csv", "wqp_sample.csv"):
    for r in csv.DictReader(open(f"{S}/stage14/cert/{p}")): ids.add(r["site"])
xy = [(a, b) for a, b, t in F["coords"]] + [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(f"{S}/stage14/cert/wqp_sample.csv"))]
g = collections.defaultdict(list)
for a, b in xy: g[(int(a / 0.05), int(b / 0.05))].append((a, b))
km = lambda a, b, c, d: 6371 * math.hypot(math.radians(a - c), math.radians(b - d) * math.cos(math.radians(a)))
def near(la, lo): return any(km(la, lo, a, b) <= 5 for di in range(-2, 3) for dj in range(-2, 3) for a, b in g.get((int(la / 0.05) + di, int(lo / 0.05) + dj), []))
rows = []
with open(f"{W}/secchi.csv", newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        r.pop("secchi_m", None); rows.append(r)
with open(f"{D}/fresh_blind_index.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["site_id", "org", "lat", "lon", "date", "time", "bottom_visible", "state"], extrasaction="ignore"); w.writeheader(); w.writerows(rows)
B = (34.27, -86.42, 35.06, -85.60); why = collections.Counter(); el = {}
for r in rows:
    la, lo = float(r["lat"]), float(r["lon"])
    if not ("2026-01-01" <= r["date"] <= "2026-09-28"): why["date"] += 1; continue
    if r["site_id"] in ids: why["site in an earlier file"] += 1; continue
    if B[0] <= la <= B[2] and B[1] <= lo <= B[3]: why["Guntersville"] += 1; continue
    if r.get("bottom_visible") == "true": why["censored"] += 1; continue
    el.setdefault((r["site_id"], r["date"]), r)
turb = set()
with open(f"{W}/turbidity.csv", newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh): turb.add((r["site_id"], r["date"]))
site = {s: (float(r["lat"]), float(r["lon"]), r["state"], r["org"]) for (s, d), r in el.items()}
sites = sorted(site); par = {s: s for s in sites}
def find(s):
    while par[s] != s: par[s] = par[par[s]]; s = par[s]
    return s
gs = collections.defaultdict(list)
for s in sites: gs[(int(site[s][0] / 0.05), int(site[s][1] / 0.05))].append(s)
for s in sites:
    la, lo = site[s][:2]
    for di in range(-2, 3):
        for dj in range(-2, 3):
            for t in gs.get((int(la / 0.05) + di, int(lo / 0.05) + dj), []):
                if t != s and km(la, lo, site[t][0], site[t][1]) <= 5: par[find(s)] = find(t)
keys = sorted(el); random.Random(20261001).shuffle(keys); seen = set(); ev = []
for s, d in keys:
    if (s, d[:7]) in seen: continue
    seen.add((s, d[:7])); la, lo, st, org = site[s]
    ev.append({"id": f"FRESH:{s}|{d}", "lat": la, "lon": lo, "date": d, "set": "FRESH", "src": "WQP26", "lake": "F" + find(s), "state": st,
               "season": "cool" if int(d[5:7]) in (10, 11, 12, 1, 2, 3, 4) else "warm", "site": s, "org": org, "strict": not near(la, lo), "turb_present": (s, d) in turb})
cols = list(ev[0]) if ev else []
with open(f"{D}/fresh_events.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(ev)
info = {"rows_read": len(rows), "excluded": dict(why), "eligible_site_days": len(el), "events_after_site_month": len(ev), "sites": len(sites), "lakes": len({e["lake"] for e in ev}),
        "strict_events": sum(e["strict"] for e in ev), "states": dict(collections.Counter(e["state"] for e in ev).most_common()), "by_month": dict(sorted(collections.Counter(e["date"][:7] for e in ev).items()))}
print(json.dumps(info, indent=1)); json.dump(info, open(f"{D}/fresh_pool.json", "w"), indent=1)
if "--prescreen" not in sys.argv: sys.exit()
sys.argv = ["x"]; sys.path.insert(0, f"{S}/stage6")
import extract as E
def q(r):
    d0 = dt.date.fromisoformat(r["date"])
    body = {"collections": ["sentinel-2-c1-l2a"], "intersects": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
            "datetime": f"{(d0 - dt.timedelta(days=1)).isoformat()}T00:00:00Z/{(d0 + dt.timedelta(days=1)).isoformat()}T23:59:59Z", "limit": 50}
    for i in range(3):
        try:
            fs = E.post(E.ES_SEARCH, body).get("features", [])
            return r, any((f["properties"].get("eo:cloud_cover") if f["properties"].get("eo:cloud_cover") is not None else 100) <= 20 for f in fs)
        except Exception: pass
    return r, False
keep = []
with cf.ThreadPoolExecutor(8) as ex:
    for r, ok in ex.map(q, ev):
        if ok: keep.append(r)
with open(f"{D}/in_fresh_c1.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(keep)
print("prescreen passed", len(keep), "of", len(ev)); info["prescreen_passed"] = len(keep); json.dump(info, open(f"{D}/fresh_pool.json", "w"), indent=1)
