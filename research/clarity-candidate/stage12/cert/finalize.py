"""Certification protocol sections 3-5: matched visits -> blind sample. A match = a row from the extractor with an item
and >= 5 valid pixels and no error; one row per site-day (best pass already chosen by the extractor: smallest |dt|,
then most valid pixels). Per lake <= 3 matched observations in seeded order (seed 20261002). Blind checks only (no
Secchi value exists here). Planning prior for class counts: Stage 11 corpus class shares. Writes blind_sample.csv
(ids, dates, items only), blind_checks.json, and the sample's sha256."""
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
        k = r["id"]; cur = best.get(k)
        key = (abs(int(float(r.get("dt_days") or 0))), -nv)
        if cur is None or key < cur[0]: best[k] = (key, r)
    return [v[1] for v in best.values()]
M = matched("out_nla22.csv") + matched("out_nla17.csv") + matched("out_syke.csv")
by = collections.defaultdict(list)
for r in sorted(M, key=lambda r: r["id"]): by[r["lake"]].append(r)
g = random.Random(20261002); keep = []
for lk in sorted(by):
    rs = by[lk][:]; g.shuffle(rs); keep += rs[:3]
keep.sort(key=lambda r: r["id"])
cols = ["id", "src", "lake", "state", "lat", "lon", "date", "item", "pass_date", "dt_days", "platform"]
with open("blind_sample.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(keep)
sha = hashlib.sha256(open("blind_sample.csv", "rb").read()).hexdigest()
us = [r for r in keep if r["src"].startswith("NLA")]
st = collections.Counter(r["state"] for r in us)
cool = [r for r in keep if int(r["date"][5:7]) in (10, 11, 12, 1, 2, 3, 4)]
prior = collections.Counter()
corpus = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if x["date"] <= "2025-12-31"]
for x in corpus:
    s = x["secchi"]; prior["clear" if s >= 6 else "normal" if s >= 3 else "stained" if s >= 2 else "limited"] += 1
    c, t = x.get("chl"), x.get("turb")
    if c is not None and c >= 15: prior["algae"] += 1
    if t is not None and t >= 8 and (c is None or c < 15): prior["sediment"] += 1
share = {k: v / len(corpus) for k, v in prior.items()}
MIN = {"clear": 40, "normal": 40, "stained": 60, "algae": 30, "sediment": 20, "limited": 25}
expected = {k: round(share.get(k, 0) * len(us), 1) for k in MIN}
chk = {"matched_observations": len(keep), "us_core": len(us), "syke": len(keep) - len(us), "lakes": len({r["lake"] for r in keep}),
       "us_states": len(st), "max_state_share_us": round(max(st.values()) / len(us), 3) if us else None,
       "cool_season_share": round(len(cool) / len(keep), 3) if keep else 0, "cool_season_lakes": len({r["lake"] for r in cool}),
       "expected_per_class_us_core (Stage 11 shares)": expected, "minima": MIN,
       "by_source": dict(collections.Counter(r["src"] for r in keep)), "months": dict(sorted(collections.Counter(r["date"][5:7] for r in keep).items()))}
chk["checks"] = {"observations>=400": chk["matched_observations"] >= 400, "lakes>=100": chk["lakes"] >= 100, "us_states>=20": chk["us_states"] >= 20,
                 "no_state_over_15pct": (chk["max_state_share_us"] or 1) <= 0.15, "cool_season>=15%_across>=20_lakes": chk["cool_season_share"] >= 0.15 and chk["cool_season_lakes"] >= 20,
                 "expected_class_counts_meet_minima": all(expected[k] >= MIN[k] for k in MIN)}
chk["READY"] = all(chk["checks"].values()); chk["sha256"] = sha
json.dump(chk, open("blind_checks.json", "w"), indent=1); print(json.dumps(chk, indent=1))
