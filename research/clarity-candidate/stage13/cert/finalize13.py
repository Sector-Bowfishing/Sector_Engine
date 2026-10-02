"""Addendum 2/3: the expanded blind sample. Matches = Stage 12 NLA and SYKE outputs + Stage 13 SYKE outputs (same rule
as Stage 12 finalize: an item, >= 5 valid pixels, no error; best pass per event). Per lake <= 3, filled October-April
first, then the rest, in seeded order (seed 20261002). Stage 12 checks unchanged (US core carries the per-class check).
Writes blind_sample13.csv (ids, dates, items only), blind_checks13.json."""
import csv, json, random, hashlib, collections, os
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
def matched(path):
    if not os.path.exists(path): return []
    best = {}
    for r in csv.DictReader(open(path)):
        if r.get("error") or not r.get("item"): continue
        try: nv = int(float(r.get("n_valid") or 0))
        except ValueError: continue
        if nv < 5: continue
        key = (abs(int(float(r.get("dt_days") or 0))), -nv)
        if r["id"] not in best or key < best[r["id"]][0]: best[r["id"]] = (key, r)
    return [v[1] for v in best.values()]
C12 = f"{S}/stage12/cert"
M = {}
for p in (f"{C12}/out_nla22.csv", f"{C12}/out_nla17.csv", f"{C12}/out_s17.csv", f"{C12}/out_s22.csv", f"{C12}/out_sc1.csv", "out13_c1.csv", "out13_legacy.csv"):
    for r in matched(p): M.setdefault(r["id"], r)
cool = lambda r: int(r["date"][5:7]) in (10, 11, 12, 1, 2, 3, 4)
by = collections.defaultdict(list)
for r in sorted(M.values(), key=lambda r: r["id"]): by[r["lake"]].append(r)
g = random.Random(20261002); keep = []
for lk in sorted(by):
    rs = by[lk][:]; g.shuffle(rs); rs.sort(key=lambda r: 0 if cool(r) else 1); keep += rs[:3]
keep.sort(key=lambda r: r["id"])
cols = ["id", "src", "lake", "state", "lat", "lon", "date", "item", "pass_date", "dt_days", "platform"]
with open("blind_sample13.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(keep)
sha = hashlib.sha256(open("blind_sample13.csv", "rb").read()).hexdigest()
us = [r for r in keep if r["src"].startswith("NLA")]; st = collections.Counter(r["state"] for r in us); cl = [r for r in keep if cool(r)]
corpus = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if x["date"] <= "2025-12-31"]; pr = collections.Counter()
for x in corpus:
    s = x["secchi"]; pr["clear" if s >= 6 else "normal" if s >= 3 else "stained" if s >= 2 else "limited"] += 1
    c, t = x.get("chl"), x.get("turb")
    if c is not None and c >= 15: pr["algae"] += 1
    if t is not None and t >= 8 and (c is None or c < 15): pr["sediment"] += 1
MIN = {"clear": 40, "normal": 40, "stained": 60, "algae": 30, "sediment": 20, "limited": 25}
exp = {k: round(pr[k] / len(corpus) * len(us), 1) for k in MIN}
chk = {"matched_observations": len(keep), "us_core": len(us), "syke": len(keep) - len(us), "lakes": len({r["lake"] for r in keep}), "us_states": len(st),
       "max_state_share_us": round(max(st.values()) / len(us), 3), "cool_season_share": round(len(cl) / len(keep), 3), "cool_season_lakes": len({r["lake"] for r in cl}),
       "expected_per_class_us_core": exp, "minima": MIN, "by_source": dict(collections.Counter(r["src"] for r in keep)),
       "months": dict(sorted(collections.Counter(r["date"][5:7] for r in keep).items())), "sha256": sha,
       "matched_before_cap": len(M), "syke_lakes": len({r["lake"] for r in keep if r["src"] == "SYKE"})}
chk["checks"] = {"observations>=400": chk["matched_observations"] >= 400, "lakes>=100": chk["lakes"] >= 100, "us_states>=20": chk["us_states"] >= 20,
                 "no_state_over_15pct": chk["max_state_share_us"] <= 0.15, "cool_season>=15%_across>=20_lakes": chk["cool_season_share"] >= 0.15 and chk["cool_season_lakes"] >= 20,
                 "expected_class_counts_meet_minima": all(exp[k] >= MIN[k] for k in MIN)}
chk["READY"] = all(chk["checks"].values())
json.dump(chk, open("blind_checks13.json", "w"), indent=1); print(json.dumps(chk, indent=1))
