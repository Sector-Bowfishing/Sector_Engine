"""Gate verdicts, pooled bootstrap, observability tables, peak-timing vs note 03. Writes out/summary.json and out/tables.md"""
import json, numpy as np, pandas as pd
from common import *
from s4_analysis import cdist, MIN_YEARS, MIN_EVAL
RNG = np.random.default_rng(7)
A = json.load(open(H/"out/analysis.json"))["lakes"]; ROWS = pd.read_pickle(H/"out/loyo_rows.pkl")
SIG_MIN = 0.05      # analyst-set (NOT prereg): lake climatology max belt share < 5 % => no measurable surface signal
EXPERT = {  # note 03 table rows -> expected peak window (doy) / centre(s)
 "SE reservoir": dict(row="Southeast reservoir (D Jul-Sep)", win=[(182, 273)]),
 "Florida": dict(row="Deep South / Gulf (D Jun-Sep)", win=[(152, 273)]),
 "Pacific NW": dict(row="Pacific NW (D Jul-Aug)", win=[(182, 243)]),
 "Upper Midwest/river pool": dict(row="Midwest (M-D May CLP; M-D Aug)", win=[(121, 151), (213, 243)]),
 "Northern ice-affected": dict(row="Great Lakes/upper Midwest (D Aug, M-D Jul)", win=[(182, 243)]),
}
def lake_stats(rows):
    r = [x for x in rows if x["clim"] is not None]
    return len(r), sum(x["clim"] == x["obs"] for x in r), sum(x["cal"] == x["obs"] for x in r), sum(cdist(x["clim"], x["obs"]) <= 1 for x in r), sum(cdist(x["cal"], x["obs"]) <= 1 for x in r)
def pooled(lakes, key="belt_share", which="clim"):
    n = ex = exc = w = wc = 0
    for lk in lakes:
        a, b, c, d, e = lake_stats(ROWS[(lk, key)]); n += a; ex += b; exc += c; w += d; wc += e
    return dict(n=n, clim=ex/max(n, 1), cal=exc/max(n, 1), w1=w/max(n, 1), w1_cal=wc/max(n, 1))
def boot(lakes, key="belt_share", B=2000):
    out = []
    for _ in range(B):
        s = RNG.choice(lakes, len(lakes)); p = pooled(list(s), key); out.append((p["clim"], p["cal"], p["clim"]-p["cal"], p["w1"]))
    o = np.array(out); return {k: [float(np.percentile(o[:, i], 2.5)), float(np.percentile(o[:, i], 97.5))] for i, k in enumerate(["clim", "cal", "diff", "w1"])}
S = dict(lakes={}, classes={})
for lk, cls, lab in LAKES:
    L = A[lk]; i = L["loyo"]["belt_share"]; v = dict(label=lab, cls=cls)
    hi = L["clim_amp"][1] if "clim_amp" in L else 0
    v["clim_max_belt"] = hi
    if "clim_vs_obs" not in i: v["verdict"] = "NOT_TESTABLE"; v["reason"] = i.get("verdict_reason", "no evaluable scenes")
    elif hi < SIG_MIN: v["verdict"] = "NOT_TESTABLE"; v["reason"] = f"no measurable surface signal (climatology max belt share {hi:.3f} < {SIG_MIN})"
    elif i["n_eval"] < MIN_EVAL or len(i["testable_years"]) < MIN_YEARS: v["verdict"] = "NOT_TESTABLE"; v["reason"] = f"n_eval={i['n_eval']} years={len(i['testable_years'])}"
    else:
        ex, cal, w1 = i["clim_vs_obs"]["exact"], i["cal_vs_obs"]["exact"], i["clim_vs_obs"]["w1"]
        v["verdict"] = "PASS" if (ex >= cal+0.10 and w1 >= 0.85) else "FAIL"
        v["reason"] = f"exact {ex:.2f} vs calendar {cal:.2f} ({(ex-cal)*100:+.0f} pts; need >= +10), within-one {w1:.2f} (need >= 0.85)"
    v.update(n_eval=i.get("n_eval"), years=len(i["testable_years"]))
    S["lakes"][lk] = v
testable = [lk for lk, v in S["lakes"].items() if v["verdict"] in ("PASS", "FAIL")]
allk = [lk for lk, _, _ in LAKES]
S["pooled_testable"] = dict(lakes=testable, **pooled(testable), ci=boot(testable))
S["pooled_all8"] = dict(lakes=allk, **pooled(allk), ci=boot(allk))
for key in ("lake_share", "belt_share_gdd", "belt_share_modern"):
    ks = [lk for lk in testable if (lk, key) in ROWS and ROWS[(lk, key)]]
    S[f"pooled_testable_{key}"] = dict(lakes=ks, **pooled(ks, key), ci=boot(ks, key)) if ks else None
# class level
for cls in sorted({c for _, c, _ in LAKES}):
    ks = [lk for lk, c, _ in LAKES if c == cls]; kt = [k for k in ks if k in testable]
    d = dict(lakes=ks, testable=kt)
    if kt:
        p = pooled(kt); d.update(p); d["ci"] = boot(kt) if len(kt) > 1 else None
        d["verdict"] = "PASS" if (p["clim"] >= p["cal"]+0.10 and p["w1"] >= 0.85) else "FAIL"
        d["lakes_pass"] = [k for k in kt if S["lakes"][k]["verdict"] == "PASS"]
    else: d["verdict"] = "NOT_TESTABLE"
    S["classes"][cls] = d
# persistence vs clim by age (pooled over testable lakes)
age_bins = {"<=14d": (0, 14), "15-30d": (15, 30), "31-60d": (31, 60), ">60d": (61, 1e9)}
pa = {}
for nm, (lo, hi_) in age_bins.items():
    rows = [r for lk in testable for r in ROWS[(lk, "belt_share")] if r["pers"] is not None and r["age"] is not None and lo <= r["age"] <= hi_]
    pa[nm] = dict(n=len(rows), pers=float(np.mean([r["pers"] == r["obs"] for r in rows])) if rows else None, clim=float(np.mean([r["clim"] == r["obs"] for r in rows])) if rows else None,
                  cal=float(np.mean([r["cal"] == r["obs"] for r in rows])) if rows else None, pers_w1=float(np.mean([cdist(r["pers"], r["obs"]) <= 1 for r in rows])) if rows else None,
                  clim_w1=float(np.mean([cdist(r["clim"], r["obs"]) <= 1 for r in rows])) if rows else None)
S["persistence_by_age"] = pa
cm = [r for lk in testable for r in ROWS[(lk, "belt_share")] if r["pers"] is not None]
S["common_pooled"] = dict(n=len(cm), pers=float(np.mean([r["pers"] == r["obs"] for r in cm])), clim=float(np.mean([r["clim"] == r["obs"] for r in cm])), cal=float(np.mean([r["cal"] == r["obs"] for r in cm])),
                          pers_w1=float(np.mean([cdist(r["pers"], r["obs"]) <= 1 for r in cm])))
# observed state distribution
S["obs_dist"] = {lk: pd.Series([r["obs"] for r in ROWS[(lk, "belt_share")]]).value_counts().to_dict() for lk in allk}
# majority-class sanity baseline (in-sample, i.e. generous to the baseline)
mj = {}
for lk in allk:
    r = ROWS[(lk, "belt_share")]
    if r: vc = pd.Series([x["obs"] for x in r]).value_counts(); mj[lk] = dict(label=vc.index[0], exact=float(vc.iloc[0]/len(r)), n=len(r))
S["majority"] = mj
S["majority_pooled_testable"] = float(sum(mj[k]["exact"]*mj[k]["n"] for k in testable)/sum(mj[k]["n"] for k in testable))
# peak timing vs expert
pk = {}
for lk, cls, lab in LAKES:
    L = A[lk]
    if "clim_peak_doy" not in L: continue
    ex = EXPERT.get(cls); d = dict(label=lab, cls=cls, clim_peak_doy=L["clim_peak_doy"], peak_window=L["peak_window_doy"], by_year=L["peak_doy_by_year"], n_years=len(L["peak_doy_by_year"]), signal=L["clim_amp"][1] >= SIG_MIN)
    if L["peak_doy_by_year"]:
        d["by_year_median"] = float(np.median(L["peak_doy_by_year"])); d["by_year_iqr"] = [float(np.percentile(L["peak_doy_by_year"], 25)), float(np.percentile(L["peak_doy_by_year"], 75))]
    if ex:
        d["expert_row"] = ex["row"]; d["expert_win"] = ex["win"]
        d["in_expert_win_clim"] = any(a <= L["clim_peak_doy"] <= b for a, b in ex["win"])
        d["in_expert_win_years"] = float(np.mean([any(a <= y <= b for a, b in ex["win"]) for y in L["peak_doy_by_year"]])) if L["peak_doy_by_year"] else None
        c = [(a+b)/2 for a, b in ex["win"]]; d["offset_days_vs_expert_centre"] = float(min((L["clim_peak_doy"]-x for x in c), key=abs))
    pk[lk] = d
S["peak"] = pk
json.dump(S, open(H/"out/summary.json", "w"), indent=1, default=float)
# ---------- markdown tables ----------
md = []
md.append("| Lake | Class | n eval | years | clim exact | calendar exact | delta pts | clim within-1 | persistence exact (common n) | verdict |\n|---|---|---|---|---|---|---|---|---|---|")
for lk, cls, lab in LAKES:
    i = A[lk]["loyo"]["belt_share"]; v = S["lakes"][lk]
    if "clim_vs_obs" in i: md.append(f"| {lab} | {cls} | {i['n_eval']} | {len(i['testable_years'])} | {i['clim_vs_obs']['exact']:.2f} | {i['cal_vs_obs']['exact']:.2f} | {(i['clim_vs_obs']['exact']-i['cal_vs_obs']['exact'])*100:+.0f} | {i['clim_vs_obs']['w1']:.2f} | {i['common_pers']['exact']:.2f} ({i['common_n']}) | **{v['verdict']}** |")
    else: md.append(f"| {lab} | {cls} | - | - | - | - | - | - | - | **{v['verdict']}** |")
open(H/"out/table_gate.md", "w").write("\n".join(md))
md = ["| Month | " + " | ".join(l for _, _, l in LAKES) + " |", "|---|" + "---|"*len(LAKES)]
for m in range(1, 13):
    md.append(f"| {m} | " + " | ".join(f"{pd.DataFrame(A[lk]['monthly']).set_index('month').loc[m,'acc_est']/max(pd.DataFrame(A[lk]['monthly']).set_index('month').loc[m,'tot'],1)*100:.0f}% / {pd.DataFrame(A[lk]['monthly']).set_index('month').loc[m,'acc_per_year_est']:.1f}" for lk, _, _ in LAKES) + " |")
open(H/"out/table_usable.md", "w").write("\n".join(md))
md = ["| Month | " + " | ".join(l for _, _, l in LAKES) + " |", "|---|" + "---|"*len(LAKES)]
for m in range(1, 13):
    md.append(f"| {m} | " + " | ".join(f"{A[lk]['age_imp'][str(m)]['med']:.0f} / {A[lk]['age_imp'][str(m)]['p90']:.0f} / {A[lk]['age_imp'][str(m)]['gt30']*100:.0f}%" for lk, _, _ in LAKES) + " |")
open(H/"out/table_age.md", "w").write("\n".join(md))
md = ["| Lake | STAC dates | read (clear>=25%) | accepted of read | fallback | refused | cloud (<25% clear) | ice/snow | no data | not read (subsample) | bin d |\n|---|---|---|---|---|---|---|---|---|---|---|"]
for lk, cls, lab in LAKES:
    s = A[lk]["status"]; n = A[lk]["n_dates"]; g = lambda k: s.get(k, 0)
    rd = g('ACCEPTED')+g('FALLBACK')+g('REFUSED')
    md.append(f"| {lab} | {n} | {rd} | {g('ACCEPTED')} ({g('ACCEPTED')/rd*100:.0f}%) | {g('FALLBACK')} ({g('FALLBACK')/rd*100:.0f}%) | {g('REFUSED')} ({g('REFUSED')/rd*100:.0f}%) | {g('CLOUD')} ({g('CLOUD')/n*100:.0f}% of dates) | {g('ICE')} | {g('NODATA')+g('ERR')} | {g('SKIPPED_SUBSAMPLE')} | {A[lk]['bin']} |")
open(H/"out/table_status.md", "w").write("\n".join(md))
print(json.dumps({k: S[k] for k in ("pooled_testable", "pooled_all8", "common_pooled", "persistence_by_age")}, indent=1, default=float))
for lk, v in S["lakes"].items(): print(lk, v["verdict"], v["reason"])
for c, d in S["classes"].items(): print(c, d["verdict"], {k: d.get(k) for k in ("testable", "clim", "cal", "w1", "ci")})
