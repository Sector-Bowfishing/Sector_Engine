"""Addendum 2 section 2: value-blind metadata prescreen. An event goes to the extractor only if a STAC search finds an
item within +-1 day with eo:cloud_cover <= 60% in the addendum B/B2 collection for its year. Events already extracted
in Stage 12 are reused, not re-extracted. Writes in_s13_{c1,legacy}.csv and prescreen.json."""
import csv, json, datetime as dt, concurrent.futures as cf, sys, collections
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.argv = ["x"]; sys.path.insert(0, f"{S}/stage6")
import extract as E
C = list(csv.DictReader(open("syke_all_candidates.csv")))
done = set()
for f in ("out_s17.csv", "out_s22.csv", "out_sc1.csv"):
    try: done |= {r["id"] for r in csv.DictReader(open(f"{S}/stage12/cert/{f}"))}
    except FileNotFoundError: pass
def coll(d): return "sentinel-2-l2a" if d[:4] in ("2017", "2022") else "sentinel-2-c1-l2a"
def q(r):
    d0 = dt.date.fromisoformat(r["date"])
    body = {"collections": [coll(r["date"])], "intersects": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]},
            "datetime": f"{(d0 - dt.timedelta(days=1)).isoformat()}T00:00:00Z/{(d0 + dt.timedelta(days=1)).isoformat()}T23:59:59Z", "limit": 50}
    for i in range(3):
        try:
            fs = E.post(E.ES_SEARCH, body).get("features", [])
            return r, any((f["properties"].get("eo:cloud_cover") if f["properties"].get("eo:cloud_cover") is not None else 100) <= 60 for f in fs)
        except Exception:
            pass
    return r, False
todo = [r for r in C if r["id"] not in done]
keep = []
with cf.ThreadPoolExecutor(12) as ex:
    for n, (r, ok) in enumerate(ex.map(q, todo), 1):
        if ok: keep.append(r)
        if n % 1000 == 0: print(n, len(todo), len(keep), flush=True)
cols = list(C[0].keys())
for tag, cond in (("c1", lambda r: coll(r["date"]) == "sentinel-2-c1-l2a"), ("legacy", lambda r: coll(r["date"]) == "sentinel-2-l2a")):
    with open(f"in_s13_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows([r for r in keep if cond(r)])
res = {"candidates": len(C), "already_extracted_stage12": len(C) - len(todo), "prescreened": len(todo), "passed": len(keep),
       "passed_cool": sum(r["season"] == "cool" for r in keep), "by_collection": dict(collections.Counter(coll(r["date"]) for r in keep))}
json.dump(res, open("prescreen.json", "w"), indent=1); print(res)
