"""Stage 21 part 1 (value-blind): choose the real-nominal tandem tiles and split them.
From the Stage 20 nominal tandem pairs (tandem20_readouts.json), keep the S2C tile-dates with at least one site whose
production-gated Sen2Cor disk is valid on both satellites (n_valid >= 5: a validity count, no reflectance value). Pick 150
tile-dates round-robin across datatakes (date + relative orbit), datatakes and tiles each in md5 order. Every tandem site
on a chosen tile-date is sampled. For each tile-date: the S2A L1C on Google Cloud (SAFE.l1c_for, the 2024 N0511 product
the reprocessed collection reuses) and the S2C nominal reprocessed L1C from Earth Search sentinel-2-l1c (s3://sentinel-s2-l1c,
requester pays). Split by datatake, whole units, balanced by site count (lib20.split rule, salt "stage21").
Writes select21.json. No reflectance and no Secchi value is read."""
import json, os, sys, hashlib, collections, urllib.request, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage20"]
import safe as SAFE
N = 150
R = json.load(open(f"{S}/stage20/tandem20_readouts.json"))
valid = lambda r: isinstance(r.get("a"), dict) and isinstance(r.get("c"), dict) and (r["a"].get("n_valid") or 0) >= 5 and (r["c"].get("n_valid") or 0) >= 5
by_td = collections.defaultdict(list)
for r in R: by_td[(r["tile"], r["date"])].append(r)
eligible = {k: v for k, v in by_td.items() if any(valid(r) for r in v)}
dk = lambda v: f"{v[0]['date'].replace('-', '')}|{(v[0].get('s2c_product') or v[0].get('s2a_product')).split('_')[4]}"
by_dt = collections.defaultdict(list)
for k, v in eligible.items(): by_dt[dk(v)].append(k)
h = lambda s: hashlib.md5(f"stage21|{s}".encode()).hexdigest()
queues = [sorted(by_dt[d], key=lambda k: h(f"{k[0]}|{k[1]}")) for d in sorted(by_dt, key=h)]
pick = []
while len(pick) < N and any(queues):
    for q in queues:
        if q and len(pick) < N: pick.append(q.pop(0))


def es_l1c(tile, date):
    t = tile.replace("MGRS-", "")
    body = {"collections": ["sentinel-2-l1c"], "query": {"grid:code": {"eq": tile}, "platform": {"eq": "sentinel-2c"}},
            "datetime": f"{date}T00:00:00Z/{date}T23:59:59Z", "limit": 10}
    req = urllib.request.Request("https://earth-search.aws.element84.com/v1/search", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    for i in range(4):
        try:
            f = json.load(urllib.request.urlopen(req, timeout=60))["features"]; break
        except Exception:
            f = None
    if not f: return None
    f = sorted(f, key=lambda i: i["properties"].get("s2:product_uri", ""))[-1]          # newest generation
    return {"id": f["id"], "product": f["properties"].get("s2:product_uri", "").replace(".SAFE", ""), "baseline": f["properties"].get("s2:processing_baseline"),
            "assets": {k: v["href"] for k, v in f["assets"].items()}}


out = []
def one(k):
    v = by_td[k]; c = es_l1c(v[0]["tile"], v[0]["date"]); a = SAFE.l1c_for(v[0]["s2a"])
    return {"tile": v[0]["tile"], "date": v[0]["date"], "datatake": dk(v), "s2a_item": v[0]["s2a"], "s2c_item": v[0]["s2c"], "s2a_l1c": a, "s2c": c,
            "sites": [{"site": r["site"], "lat": r["lat"], "lon": r["lon"], "s2a": r["s2a"], "s2c": r["s2c"], "sen2cor_valid": valid(r)} for r in v]}
with cf.ThreadPoolExecutor(8) as ex:
    out = list(ex.map(one, pick))
cnt = collections.Counter()
for t in out: cnt[t["datatake"]] += len(t["sites"])
d, ho, nd, nh = set(), set(), 0, 0
for k in sorted(cnt, key=h):
    if nd <= nh: d.add(k); nd += cnt[k]
    else: ho.add(k); nh += cnt[k]
for t in out: t["split"] = "D" if t["datatake"] in d else "H"; t["seen_in_stage20_tandem"] = t["date"] >= "2024-12-12"
json.dump(out, open(f"{S}/stage21/select21.json", "w"), indent=1)
ok = [t for t in out if t["s2a_l1c"] and t["s2c"]]
print("tile-dates", len(out), "| with both L1C", len(ok), "| datatakes", len({t["datatake"] for t in out}), "| sites", sum(len(t["sites"]) for t in out))
print("split D/H tiles", collections.Counter(t["split"] for t in ok), "sites", {s: sum(len(t["sites"]) for t in ok if t["split"] == s) for s in "DH"},
      "datatakes", {s: len({t["datatake"] for t in ok if t["split"] == s}) for s in "DH"})
print("S2C baselines", collections.Counter((t["s2c"] or {}).get("baseline") for t in out), "generation", collections.Counter(((t["s2c"] or {}).get("product") or "")[-15:-11] for t in out))
print("missing S2A", sum(1 for t in out if not t["s2a_l1c"]), "missing S2C", sum(1 for t in out if not t["s2c"]))
