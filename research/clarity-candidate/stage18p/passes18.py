"""Stage 18 (physical-pass rebuild), part 1 (value-blind): canonical physical-pass identity, its validation, the Stage 17
contamination count, and the rebuilt neighbour selection.

Physical pass = (platform, UTC sensing date). A Sentinel-2 satellite images a given site at most once a day (one
descending daytime pass; consecutive orbits are ~2,800 km apart at the equator and overlap only beyond ~84 deg), so
every Earth Search item of one platform on one day over a site - overlapping MGRS tiles, datastrip twins, duplicate
representations - is one observation. Checked against the L1C datatake identity (platform + datatake sensing start) of
every item whose L1C is known, and against the spread of sensing times within each pass.

Rebuilt neighbours (Stage 17 section 2 with passes in place of items): candidate passes with a valid production-gated
Sen2Cor disk at the site (n_valid >= 5, no read error) within +-10 days, excluding the anchor's own pass; one
representative item per pass (most valid pixels, then lowest scene cloud, then item id); the 3 nearest passes by |dt|,
then the representative's scene cloud. Writes neighbors18.json, contamination18.json, validation18.json, tasks_nb18.json.
No Secchi value is read."""
import csv, json, collections, glob, os, sys, datetime as dt, random

S = __import__("os").environ["CLARITY_RESEARCH_ROOT"]
D = f"{S}/stage18p"
sys.path.insert(0, f"{S}/stage11/tools")
dev = {r["id"]: r for r in json.load(open(f"{S}/stage16/analysis/dev16_rows.json"))}
corp = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
sel17 = json.load(open(f"{S}/stage17/scenes/neighbors.json"))


def item_date(it):
    f = it.split("_"); return f[2][:8]


def pkey(platform, date8): return f"{platform}|{date8}"


def anchor_key(cid):
    a = corp[cid]; return pkey(a["platform"], item_date(a["item"]))


# ---------------- L1C datatake identity where known (every ACOLITE result written so far)
L1C = {}
for f in glob.glob(f"{S}/stage1[2-7]/**/res*/*.json", recursive=True):
    try: r = json.load(open(f))
    except Exception: continue
    if r.get("l1c") and r.get("item"): L1C[r["item"]] = r["l1c"]
datatake = lambda n: f"{n.split('_')[0]}|{n.split('_')[2]}"          # S2B|20210220T170329 (datatake sensing start)
plat = {"S2A": "sentinel-2a", "S2B": "sentinel-2b", "S2C": "sentinel-2c"}

# ---------------- every candidate read-out, by event
R = collections.defaultdict(list)
for r in csv.DictReader(open(f"{S}/stage11/temporal/neighbors_readouts.csv")):
    cid = f"{r['set']}:{r['id']}"
    if cid in dev and r.get("item"): R[cid].append(r)

# ---------------- validation A: pass key vs L1C datatake, on every pair of known items seen at the same site
agree = collections.Counter(); bad = []
for cid, rows in R.items():
    items = {r["item"]: r for r in rows}
    a = corp[cid]["item"]
    if a in L1C: items.setdefault(a, {"item": a, "platform": corp[cid]["platform"], "pass_date": f"{item_date(a)[:4]}-{item_date(a)[4:6]}-{item_date(a)[6:]}"})
    known = [(it, r) for it, r in items.items() if it in L1C]
    for i in range(len(known)):
        for j in range(i + 1, len(known)):
            (ia, ra), (ib, rb) = known[i], known[j]
            ka = pkey(ra["platform"], ra["pass_date"].replace("-", "")); kb = pkey(rb["platform"], rb["pass_date"].replace("-", ""))
            same_key, same_dt = ka == kb, datatake(L1C[ia]) == datatake(L1C[ib])
            agree[(same_key, same_dt)] += 1
            if same_key != same_dt and len(bad) < 20: bad.append({"event": cid, "a": ia, "b": ib, "l1c_a": L1C[ia], "l1c_b": L1C[ib]})

# ---------------- validation B: sensing-time spread inside a pass, and the gap between passes of one platform
def t(s):
    try: return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception: return None
spread, gaps = [], []
for cid, rows in R.items():
    g = collections.defaultdict(list)
    for r in rows:
        if t(r.get("pass_time") or ""): g[pkey(r["platform"], r["pass_date"].replace("-", ""))].append(t(r["pass_time"]))
    for k, ts in g.items(): spread.append((max(ts) - min(ts)).total_seconds())
    byp = collections.defaultdict(list)
    for k, ts in g.items(): byp[k.split("|")[0]].append(min(ts))
    for p, ts in byp.items():
        ts = sorted(ts); gaps += [(b - a).total_seconds() / 3600 for a, b in zip(ts, ts[1:])]

# ---------------- Stage 17 contamination
cont = {"neighbour_obs": 0, "anchor_pass": 0, "duplicate_neighbour": 0, "events_with_neighbours": 0, "events_anchor_dup": 0, "events_nb_dup": 0,
        "by_kind": collections.Counter()}
for cid, v in sel17.items():
    if cid not in dev or not v: continue
    cont["events_with_neighbours"] += 1; ak = anchor_key(cid); seen = set(); fa = fd = False
    a_tile = corp[cid]["item"].split("_")[1].lstrip("T")
    for n in v:
        cont["neighbour_obs"] += 1; k = pkey(n["platform"], n["pass_date"].replace("-", ""))
        tile = n["item"].split("_")[1].lstrip("T")
        if k == ak:
            cont["anchor_pass"] += 1; fa = True; cont["by_kind"]["anchor: same tile (datastrip twin or duplicate)" if tile == a_tile else "anchor: overlapping tile"] += 1
        elif k in seen:
            cont["duplicate_neighbour"] += 1; fd = True; cont["by_kind"]["neighbour: duplicate of another neighbour"] += 1
        seen.add(k)
    cont["events_anchor_dup"] += fa; cont["events_nb_dup"] += fd
cont["removed"] = cont["anchor_pass"] + cont["duplicate_neighbour"]; cont["by_kind"] = dict(cont["by_kind"])

# ---------------- rebuilt selection: up to 3 nearest independent passes
num = lambda x, d=None: float(x) if x not in (None, "") else d
NB18, members = {}, {}
for cid in dev:
    ak = anchor_key(cid); passes = collections.defaultdict(list)
    for r in R.get(cid, []):
        try: nv = int(float(r.get("n_valid") or 0)); d_ = int(float(r["dt_days"]))
        except ValueError: continue
        if r.get("error") or nv < 5 or r["item"] == corp[cid]["item"] or abs(d_) > 10: continue
        k = pkey(r["platform"], r["pass_date"].replace("-", ""))
        if k == ak: continue
        passes[k].append({"item": r["item"], "dt": d_, "n_valid": nv, "cloud": num(r.get("scene_cloud"), 100.0), "pass_time": r.get("pass_time"),
                          "platform": r.get("platform"), "sun_elev": num(r.get("sun_elev")), "pass_date": r.get("pass_date"), "tile": r.get("tile")})
    reps = []
    for k, its in passes.items():
        uniq = {i["item"]: i for i in its}.values()
        rep = sorted(uniq, key=lambda i: (-i["n_valid"], i["cloud"], i["item"]))[0]
        reps.append(dict(rep, pass_key=k, pass_items=sorted(i["item"] for i in uniq)))
    NB18[cid] = sorted(reps, key=lambda n: (abs(n["dt"]), n["cloud"], n["pass_key"]))[:3]

# which representatives still need the frozen ACOLITE path at this site
have = set()
for f in glob.glob(f"{S}/stage17/scenes/res_nb/*.json") + glob.glob(f"{D}/res_nb18/*.json"):
    r = json.load(open(f))
    for c in r.get("crops", []):
        for k, p in (c.get("points") or {}).items():
            if p: have.add(k)
need = collections.defaultdict(list); meta = {}
for cid, v in NB18.items():
    x = corp[cid]
    for n in v:
        k = f"{cid}#{n['item']}"
        if k not in have: need[n["item"]].append((x["lat"], x["lon"], k)); meta[n["item"]] = n
EL = {}
for p in (f"{S}/stage17/scenes/elevations17.json", f"{S}/stage14/cert/elevations.json", f"{S}/stage12/corpus/elevations.json"):
    if os.path.exists(p): EL.update(json.load(open(p)))
T = []
for item, ps in sorted(need.items()):
    crops, left = [], list(ps)
    while left:
        c = left[0]; inside = [p for p in left if abs(p[0] - c[0]) < 0.07 and abs(p[1] - c[1]) < 0.09]
        crops.append({"lat": c[0], "lon": c[1], "points": [list(p) for p in inside], "elev": EL.get(f"{c[0]},{c[1]}")}); left = [p for p in left if p not in inside]
    T.append({"item": item, "pass_time": meta[item]["pass_time"], "platform": meta[item]["platform"], "crops": crops})

# ---------------- manual-review sample (deterministic): duplicate groups of each kind, with their L1C names
rng = random.Random(18)
groups = {"anchor: overlapping tile": [], "anchor: same tile (datastrip twin or duplicate)": [], "neighbour: duplicate of another neighbour": []}
for cid, v in sel17.items():
    if cid not in dev: continue
    ak = anchor_key(cid); a_tile = corp[cid]["item"].split("_")[1].lstrip("T"); first = {}
    for n in v:
        k = pkey(n["platform"], n["pass_date"].replace("-", "")); tile = n["item"].split("_")[1].lstrip("T")
        if k == ak: groups["anchor: same tile (datastrip twin or duplicate)" if tile == a_tile else "anchor: overlapping tile"].append((cid, corp[cid]["item"], n["item"]))
        elif k in first: groups["neighbour: duplicate of another neighbour"].append((cid, first[k], n["item"]))
        else: first[k] = n["item"]
sample = []
import safe as SAFE
def l1c_of(it):
    return L1C.get(it) or (SAFE.l1c_for(it) if "T" in it.split("_")[2] else None)
for kind, gs in groups.items():
    for cid, a, b in rng.sample(gs, min(8, len(gs))):
        la, lb = l1c_of(a), l1c_of(b)
        sample.append({"kind": kind, "event": cid, "item_a": a, "item_b": b, "l1c_a": la, "l1c_b": lb,
                       "same_datatake": bool(la and lb and datatake(la) == datatake(lb)), "same_l1c": la == lb})

json.dump(NB18, open(f"{D}/neighbors18.json", "w")); json.dump(T, open(f"{D}/tasks_nb18.json", "w"))
json.dump(cont, open(f"{D}/contamination18.json", "w"), indent=1)
val = {"pairs_key_vs_datatake": {f"same_key={a} same_datatake={b}": n for (a, b), n in agree.items()}, "disagreements": bad,
       "within_pass_spread_s": {"n": len(spread), "max": max(spread) if spread else None, "p99": sorted(spread)[int(0.99 * len(spread))] if spread else None},
       "between_pass_gap_h_min": min(gaps) if gaps else None, "manual_sample": sample,
       "new_selection": {"events": sum(1 for v in NB18.values() if v), "neighbour_passes": sum(len(v) for v in NB18.values()),
                         "need_acolite_items": len(T), "need_acolite_points": sum(len(c["points"]) for t_ in T for c in t_["crops"])}}
json.dump(val, open(f"{D}/validation18.json", "w"), indent=1, default=str)
print(json.dumps({k: v for k, v in val.items() if k != "manual_sample"}, indent=1, default=str)); print(json.dumps(cont, indent=1))
