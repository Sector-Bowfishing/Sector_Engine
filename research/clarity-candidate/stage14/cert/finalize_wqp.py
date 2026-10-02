"""Stage 14 cert protocol sections 4-5 (value-blind): the final part B (WQP) sample and the blind checks on the whole
certification set. Match rule as Stage 12/13 finalize (an item, >= 5 valid pixels, no error; best pass = smallest |dt|,
then most valid pixels). Per lake <= 3, October-April first, then seeded order (seed 20261015); <= 15% per state;
<= 900. Writes wqp_sample.csv (ids, dates, items only) and blind_checks14.json."""
import csv, json, random, hashlib, collections, os
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage14/cert"
def matched(path):
    best = {}
    for r in csv.DictReader(open(path)):
        if r.get("error") or not r.get("item"): continue
        try: nv = int(float(r.get("n_valid") or 0))
        except ValueError: continue
        if nv < 5 or not r.get("rho_red_v") or not r.get("rho_rededge1_v"): continue
        key = (abs(int(float(r.get("dt_days") or 0))), -nv)
        if r["id"] not in best or key < best[r["id"]][0]: best[r["id"]] = (key, r)
    return [v[1] for v in best.values()]
M = {}
for p in (f"{D}/out_wqp_c1.csv", f"{D}/out_wqp_legacy.csv"):
    for r in matched(p): M.setdefault(r["id"], r)
draw = {r["id"]: r for p in ("wqp_draw.csv", "wqp_draw2.csv") for r in csv.DictReader(open(f"{D}/{p}"))}      # addendum A2: both draws
for k, r in M.items():
    for f in ("site", "org", "strict", "turb_present"): r[f] = draw[k][f]
cool = lambda r: int(r["date"][5:7]) in (10, 11, 12, 1, 2, 3, 4)
by = collections.defaultdict(list)
for r in sorted(M.values(), key=lambda r: r["id"]): by[r["lake"]].append(r)
g = random.Random(20261015); capped = []
for lk in sorted(by):
    rs = by[lk][:]; g.shuffle(rs); rs.sort(key=lambda r: 0 if cool(r) else 1); capped += rs[:3]
g.shuffle(capped)
N = min(900, len(capped)); cap = int(0.15 * N); st = collections.Counter(); keep = []
for r in capped:
    if len(keep) >= N: break
    if st[r["state"]] >= cap: continue
    st[r["state"]] += 1; keep.append(r)
keep.sort(key=lambda r: r["id"])
cols = ["id", "src", "lake", "state", "lat", "lon", "date", "item", "pass_date", "pass_time", "dt_days", "platform", "season", "site", "org", "strict", "turb_present"]
with open(f"{D}/wqp_sample.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(keep)
sha = hashlib.sha256(open(f"{D}/wqp_sample.csv", "rb").read()).hexdigest()
# blind checks on the whole set (protocol section 5 = Stage 12 checks)
b13 = list(csv.DictReader(open(f"{S}/stage13/cert/blind_sample13.csv")))
nla = [r for r in b13 if r["src"].startswith("NLA")]; syke = [r for r in b13 if r["src"] == "SYKE"]
us = nla + keep; allr = us + syke
stc = collections.Counter(r["state"] for r in us)
corpus = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if x["date"] <= "2025-12-31"]; pr = collections.Counter()
for x in corpus:
    s = x["secchi"]; pr["clear" if s >= 6 else "normal" if s >= 3 else "stained" if s >= 2 else "limited"] += 1
    c, t = x.get("chl"), x.get("turb")
    if c is not None and c >= 15: pr["algae"] += 1
    if t is not None and t >= 8 and (c is None or c < 15): pr["sediment"] += 1
MIN = {"clear": 40, "normal": 40, "stained": 60, "algae": 30, "sediment": 20, "limited": 25}
exp = {k: round(pr[k] / len(corpus) * len(us), 1) for k in MIN}
lakes = {r["lake"] for r in allr}; cl = [r for r in allr if cool(r)]
chk = {"wqp_matched_before_caps": len(M), "wqp_after_lake_cap": len(capped), "wqp_final": len(keep), "wqp_sha256": sha,
       "observations": len(allr), "us_core": len(us), "nla": len(nla), "wqp": len(keep), "syke": len(syke), "lakes": len(lakes), "us_states": len(stc),
       "max_state_share_us": round(max(stc.values()) / len(us), 3), "cool_share": round(len(cl) / len(allr), 3), "cool_lakes": len({r["lake"] for r in cl}),
       "us_cool_share": round(sum(1 for r in us if cool(r)) / len(us), 3), "wqp_strict_subset": sum(1 for r in keep if r["strict"] == "True"),
       "wqp_with_turbidity_record": sum(1 for r in keep if r["turb_present"] == "True"), "expected_per_class_us_core": exp, "minima": MIN,
       "wqp_states": dict(collections.Counter(r["state"] for r in keep).most_common()), "wqp_platforms": dict(collections.Counter(r["platform"] for r in keep))}
chk["checks"] = {"observations>=400": chk["observations"] >= 400, "lakes>=100": chk["lakes"] >= 100, "us_states>=20": chk["us_states"] >= 20,
                 "no_state_over_15pct": chk["max_state_share_us"] <= 0.15, "cool>=15%_across>=20_lakes": chk["cool_share"] >= 0.15 and chk["cool_lakes"] >= 20,
                 "expected_class_counts_meet_minima": all(exp[k] >= MIN[k] for k in MIN)}
chk["READY"] = all(chk["checks"].values())
json.dump(chk, open(f"{D}/blind_checks14.json", "w"), indent=1); print(json.dumps(chk, indent=1))
F = json.load(open(f"{S}/stage14/FREEZE_STAGE14.json")); F["files"]["stage14/cert/wqp_sample.csv"] = sha
F["files"]["stage14/cert/finalize_wqp.py"] = hashlib.sha256(open(f"{D}/finalize_wqp.py", "rb").read()).hexdigest()
json.dump(F, open(f"{S}/stage14/FREEZE_STAGE14.json", "w"), indent=1)
