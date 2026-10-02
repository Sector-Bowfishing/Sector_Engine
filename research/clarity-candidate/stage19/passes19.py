"""Stage 19, part 1 (value-blind): the strictly causal prior-pass selection (PREREGISTRATION_STAGE19.md section 2).

For every development event: physical passes (platform, UTC sensing date) sensed strictly BEFORE the anchor, never the
anchor's own pass, with a valid production-gated Sen2Cor disk (n_valid >= 5); one representative item per pass (most
valid pixels, lowest scene cloud, item id); the 3 most recent within 15 days (age = anchor date - pass date, days; then
scene cloud, then pass key). Read-outs: Stage 11 (observation +-10 d) and stage19/readouts19.csv (observation -17..-11 d,
same frozen extractor). Writes neighbors19.json, tasks_nb19.json, passes19.json. No Secchi value is read."""
import csv, json, collections, glob, os, datetime as dt

S = __import__("os").environ["CLARITY_RESEARCH_ROOT"]
D = f"{S}/stage19"
dev = {r["id"]: r for r in json.load(open(f"{S}/stage16/analysis/dev16_rows.json"))}
corp = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
LOOK = 15


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


rows = collections.defaultdict(dict)                       # cid -> item -> read-out (truth-relative dt)
for r in csv.DictReader(open(f"{S}/stage11/temporal/neighbors_readouts.csv")):
    cid = f"{r['set']}:{r['id']}"
    if cid in dev and r.get("item"): rows[cid][r["item"]] = dict(r)
for r in csv.DictReader(open(f"{D}/readouts19.csv")):
    cid = f"{r['set']}:{r['id']}"
    if cid not in dev or not r.get("item") or r.get("error"): continue
    r = dict(r); truth = dt.date.fromisoformat(r["truth_date"]); r["dt_days"] = str((dt.date.fromisoformat(r["pass_date"]) - truth).days)
    rows[cid].setdefault(r["item"], r)

NB, stats = {}, collections.Counter()
for cid in dev:
    a_item = corp[cid]["item"]; a = rows[cid].get(a_item)
    assert a is not None, cid
    a_key = f"{a['platform']}|{a['pass_date'].replace('-', '')}"; a_t = ts(a["pass_time"]); a_day = dt.date.fromisoformat(a["pass_date"])
    passes = collections.defaultdict(list)
    for it, r in rows[cid].items():
        if it == a_item or r.get("error") or not r.get("pass_time"): continue
        try: nv = int(float(r.get("n_valid") or 0))
        except ValueError: continue
        k = f"{r['platform']}|{r['pass_date'].replace('-', '')}"
        if nv < 5 or k == a_key or ts(r["pass_time"]) >= a_t: continue
        age = (a_day - dt.date.fromisoformat(r["pass_date"])).days
        if age > LOOK: continue
        passes[k].append({"item": it, "dt": int(r["dt_days"]), "age": age, "n_valid": nv, "cloud": float(r.get("scene_cloud") or 100), "pass_time": r["pass_time"],
                          "platform": r["platform"], "sun_elev": float(r["sun_elev"]) if r.get("sun_elev") else None, "pass_date": r["pass_date"], "pass_key": k})
    reps = []
    for k, its in passes.items():
        rep = sorted(its, key=lambda i: (-i["n_valid"], i["cloud"], i["item"]))[0]
        reps.append(dict(rep, pass_items=sorted(i["item"] for i in its)))
    sel = sorted(reps, key=lambda n: (n["age"], n["cloud"], n["pass_key"]))[:3]
    keys = [a_key] + [n["pass_key"] for n in sel]
    assert len(keys) == len(set(keys)) and all(ts(n["pass_time"]) < a_t for n in sel), cid      # independent and strictly past
    NB[cid] = sel
    for W in (3, 5, 7, 10, 15): stats[(W, min(3, sum(1 for n in sel if n["age"] <= W)))] += 1

have = set()
for f in glob.glob(f"{S}/stage17/scenes/res_nb/*.json") + glob.glob(f"{S}/stage18p/res_nb18/*.json") + glob.glob(f"{D}/res_nb19/*.json"):
    for c in json.load(open(f)).get("crops", []):
        for k, p in (c.get("points") or {}).items():
            if p: have.add(k)
need = collections.defaultdict(list); meta = {}
for cid, v in NB.items():
    x = corp[cid]
    for n in v:
        k = f"{cid}#{n['item']}"
        if k not in have: need[n["item"]].append((x["lat"], x["lon"], k)); meta[n["item"]] = n
EL = {}
for p in (f"{S}/stage17/scenes/elevations17.json", f"{S}/stage14/cert/elevations.json", f"{S}/stage12/corpus/elevations.json"):
    if os.path.exists(p): EL.update(json.load(open(p)))
import urllib.request, time
def epqs(la, lo):                                 # as stage17/scenes/build_neighbors.py
    for i in range(4):
        try:
            with urllib.request.urlopen(f"https://epqs.nationalmap.gov/v1/json?x={lo}&y={la}&wkid=4326&units=Meters&includeDate=false", timeout=30) as r:
                v = float(json.load(r).get("value")); return v if v > -100 else None
        except Exception: time.sleep(2 * (i + 1))
    return None
if os.path.exists(f"{D}/elevations19.json"): EL.update(json.load(open(f"{D}/elevations19.json")))
for item, ps in need.items():
    c = ps[0]
    if f"{c[0]},{c[1]}" not in EL: EL[f"{c[0]},{c[1]}"] = epqs(c[0], c[1])
json.dump({k: v for k, v in EL.items()}, open(f"{D}/elevations19.json", "w"))
T = []
for item, ps in sorted(need.items()):
    crops, left = [], list(ps)
    while left:
        c = left[0]; inside = [p for p in left if abs(p[0] - c[0]) < 0.07 and abs(p[1] - c[1]) < 0.09]
        crops.append({"lat": c[0], "lon": c[1], "points": [list(p) for p in inside], "elev": EL.get(f"{c[0]},{c[1]}")}); left = [p for p in left if p not in inside]
    T.append({"item": item, "pass_time": meta[item]["pass_time"], "platform": meta[item]["platform"], "crops": crops})
json.dump(NB, open(f"{D}/neighbors19.json", "w")); json.dump(T, open(f"{D}/tasks_nb19.json", "w"))
out = {"candidate_prior_passes_by_window": {W: {n: stats[(W, n)] for n in range(4)} for W in (3, 5, 7, 10, 15)},
       "need_acolite_items": len(T), "need_acolite_points": sum(len(c["points"]) for t in T for c in t["crops"]), "no_crop_elevation": sum(1 for t in T for c in t["crops"] if c["elev"] is None)}
json.dump(out, open(f"{D}/passes19.json", "w"), indent=1); print(json.dumps(out, indent=1))
