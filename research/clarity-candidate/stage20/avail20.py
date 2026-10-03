"""Stage 20 section 8/9 (value-blind, hypothetical since S2C is not lifted): prior-pass availability with and without
S2C, all development events and the 2025-26 era (S2C operational from 2025-01-21), windows 5/10/15. A prior pass counts
when its frozen-path ACOLITE sample is valid (tier 1 or 2), exactly as Stage 19's NB. Writes avail20.json."""
import json, os, sys, glob, collections
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage20")
import lib20 as L20
P = {}
for f in glob.glob(f"{S}/stage17/scenes/res_nb/*.json") + glob.glob(f"{S}/stage18p/res_nb18/*.json") + glob.glob(f"{S}/stage19/res_nb19/*.json"):
    r = json.load(open(f))
    for c in r.get("crops", []):
        for k, p in (c.get("points") or {}).items(): P[k] = (p, r.get("l1c"))
dev = {r["id"]: r for r in json.load(open(f"{S}/stage16/analysis/dev16_rows.json"))}
corp = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
sel = json.load(open(f"{S}/stage19/neighbors19.json"))
NB = collections.defaultdict(list)
for cid, v in sel.items():
    for n in v:
        p = P.get(f"{cid}#{n['item']}")
        if not p or n.get("sun_elev") is None: continue
        if L20.pick(p[0].get("M0"), p[0].get("M3"))[0] is None: continue
        NB[cid].append({"age": n["age"], "platform": n["platform"], "baseline": (p[1] or "").split("_")[3] if p[1] else None})
out = {}
for era, fn in (("all", lambda d: True), ("2025-26", lambda d: d >= "2025-01-21")):
    ev = [cid for cid in dev if fn(corp[cid]["date"])]
    out[era] = {"events": len(ev)}
    for W in (5, 10, 15):
        a = [sum(1 for n in NB.get(c, []) if n["age"] <= W and n["platform"] != "sentinel-2c") for c in ev]
        b = [sum(1 for n in NB.get(c, []) if n["age"] <= W) for c in ev]
        out[era][str(W)] = {"zero_before": sum(x == 0 for x in a) / len(ev), "zero_after": sum(x == 0 for x in b) / len(ev),
                            "dist_before": {m: sum(min(3, x) == m for x in a) / len(ev) for m in range(4)}, "dist_after": {m: sum(min(3, x) == m for x in b) / len(ev) for m in range(4)},
                            "mean_before": sum(a) / len(ev), "mean_after": sum(b) / len(ev)}
out["s2c_prior_baselines"] = dict(collections.Counter(n["baseline"] for v in NB.values() for n in v if n["platform"] == "sentinel-2c"))
json.dump(out, open(f"{S}/stage20/avail20.json", "w"), indent=1)
for era, v in out.items():
    if era.startswith("s2c"): print(era, v); continue
    print(era, v["events"], {W: (round(x["zero_before"], 3), round(x["zero_after"], 3), round(x["mean_before"], 2), round(x["mean_after"], 2)) for W, x in v.items() if W != "events"})
