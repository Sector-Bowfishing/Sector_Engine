#!/usr/bin/env python3
"""Hartwell effective-depth validation: independent re-derivation from the cached CWMS daily pool series. Research only.

Inputs  (read only):
  ~/Desktop/Development/Sector_Research_Data/lake-brain/history/lakebrain_gcs/Lake_Hartwell_SC.csv   (CWMS SAS Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS, date label = CWMS stamp - 1 day)
  ~/Desktop/Development/Sector_Research_Data/lake-brain/history/cwms/hartwell_daily.csv              (same series, raw CWMS epoch stamps; cross-check)
  ~/Desktop/Development/Sector_Research_Data/lake-brain/history/cwms/hartwell_gc_daily.csv            (Elev-GC, operator guide / top of conservation, 2000+)
  ~/Desktop/Development/Sector_Research_Data/depth-brain/adoption/hartwell/stor_p1.json              (CWMS storage daily, fetched for this task)
Outputs: ~/Desktop/Development/Sector_Engine-depth-adoption/docs/brains/depth/data/hartwell_effective_depth_results.json
Run: venv python with -I (tables are printed; the json carries the numbers quoted in DEPTH_HARTWELL_EFFECTIVE_DEPTH.md).
"""
import json, os, sys, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
H = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/history")
AD = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/adoption/hartwell")
OUT = os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption/docs/brains/depth/data"); os.makedirs(OUT, exist_ok=True)
FP = 660.0
rng = np.random.default_rng(20261013)

# ---------------------------------------------------------------- load
lb = pd.read_csv(f"{H}/lakebrain_gcs/Lake_Hartwell_SC.csv", parse_dates=["date"]).set_index("date")["elevationFt"].astype(float)
raw = pd.read_csv(f"{H}/cwms/hartwell_daily.csv"); raw["date"] = pd.to_datetime(raw.epoch_ms, unit="ms")
rawq = raw[raw.value.notna()]
print("raw non-null", len(rawq), "quality codes of non-null values:", rawq.quality.value_counts().to_dict())
raw_s = rawq.set_index("date")["value"]; raw_s.index = raw_s.index - pd.Timedelta(days=1)
j = pd.concat([lb, raw_s], axis=1, keys=["lb", "raw"], sort=True).dropna()
print("LB vs raw (after the one-day label shift): overlap", len(j), "max |diff|", float((j.lb - j.raw).abs().max()))
gc = pd.read_csv(f"{H}/cwms/hartwell_gc_daily.csv"); gc["date"] = pd.to_datetime(gc.epoch_ms, unit="ms") - pd.Timedelta(days=1)
gc = gc[gc.value.notna()].set_index("date")["value"]
print("pool series", lb.index.min().date(), lb.index.max().date(), "n", len(lb), "calendar days", (lb.index.max() - lb.index.min()).days + 1,
      "gaps", (lb.index.max() - lb.index.min()).days + 1 - len(lb), " min", lb.min(), "max", lb.max())
gaps = lb.index.to_series().diff().dt.days; print("largest gap (days) between consecutive observations:", int(gaps.max()))
print("guide (Elev-GC) ", gc.index.min().date(), gc.index.max().date(), len(gc), "values", sorted(gc.round(2).unique())[:12], "...")

res = {"series": dict(source="CWMS SAS Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS", first=str(lb.index.min().date()), last=str(lb.index.max().date()), n=int(len(lb)),
                      missing_days_in_span=int((lb.index.max() - lb.index.min()).days + 1 - len(lb)), min=float(lb.min()), max=float(lb.max()),
                      lb_vs_raw_max_abs_diff=float((j.lb - j.raw).abs().max()), vertical_datum_cwms="NGVD29 (CWMS locations/Hartwell?office=SAS, fetched 2026-10-13)")}

# ---------------------------------------------------------------- core functions
QS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
CLASSES = [("dry_le0", -np.inf, 0.0), ("0_1ft", 0.0, 1.0), ("1_3ft", 1.0, 3.0), ("3_6ft", 3.0, 6.0), ("ge6ft", 6.0, np.inf)]


def class_fracs(eff):
    out = {}
    for n, lo, hi in CLASSES:
        if n == "dry_le0": out[n] = float((eff <= 0).mean())
        elif n == "ge6ft": out[n] = float((eff >= 6).mean())
        else: out[n] = float(((eff > lo) & (eff < hi)).mean()) if n == "0_1ft" else float(((eff >= lo) & (eff < hi)).mean())
    out["lt1ft_incl_dry"] = float((eff < 1).mean())
    return out


def stats(shift, d0s=(2, 4, 6)):
    r = dict(n=int(len(shift)), shift_q={f"p{int(q*100):02d}": float(shift.quantile(q)) for q in QS}, shift_min=float(shift.min()), shift_max=float(shift.max()),
             frac_shift_le_m4=float((shift <= -4).mean()), frac_shift_le_m2=float((shift <= -2).mean()), frac_shift_lt_m1=float((shift < -1).mean()),
             frac_shift_le_m6=float((shift <= -6).mean()), frac_shift_ge_0=float((shift >= 0).mean()))
    r["flats"] = {str(d): class_fracs(d + shift) for d in d0s}
    return r


def year_block_boot(shift, fn_keys, B=2000):
    """resample whole calendar years with replacement; returns {key: (lo5, hi95)} of the metric"""
    yrs = sorted(set(shift.index.year)); groups = {y: shift[shift.index.year == y].values for y in yrs}
    outs = {k: [] for k in fn_keys}
    for _ in range(B):
        pick = rng.choice(yrs, size=len(yrs), replace=True)
        s = pd.Series(np.concatenate([groups[y] for y in pick]))
        for k, f in fn_keys.items(): outs[k].append(f(s))
    return {k: (float(np.percentile(v, 5)), float(np.percentile(v, 95))) for k, v in outs.items()}


KEYS = {"p05": lambda s: s.quantile(.05), "p50": lambda s: s.quantile(.50), "p95": lambda s: s.quantile(.95),
        "le_m4": lambda s: (s <= -4).mean(), "le_m2": lambda s: (s <= -2).mean(), "lt_m1": lambda s: (s < -1).mean(), "le_m6": lambda s: (s <= -6).mean(),
        "f2_lt1": lambda s: (2 + s < 1).mean(), "f2_dry": lambda s: (2 + s <= 0).mean(), "f4_lt1": lambda s: (4 + s < 1).mean(), "f4_dry": lambda s: (4 + s <= 0).mean(),
        "f6_lt1": lambda s: (6 + s < 1).mean(), "f6_dry": lambda s: (6 + s <= 0).mean(),
        "f2_1_3": lambda s: ((2 + s >= 1) & (2 + s < 3)).mean(), "f4_1_3": lambda s: ((4 + s >= 1) & (4 + s < 3)).mean(), "f6_1_3": lambda s: ((6 + s >= 1) & (6 + s < 3)).mean(),
        "f2_3_6": lambda s: ((2 + s >= 3) & (2 + s < 6)).mean(), "f4_3_6": lambda s: ((4 + s >= 3) & (4 + s < 6)).mean(), "f6_3_6": lambda s: ((6 + s >= 3) & (6 + s < 6)).mean(),
        "f2_ge6": lambda s: (2 + s >= 6).mean(), "f4_ge6": lambda s: (4 + s >= 6).mean(), "f6_ge6": lambda s: (6 + s >= 6).mean()}

# ---------------------------------------------------------------- periods
shift_all = lb - FP
PER = {"2016-01-01..2026-10-06 (research window)": ("2016-01-01", None), "2016..2025 (10 full years)": ("2016-01-01", "2025-12-31"),
       "2006-01-01..2026-10-06 (20 y)": ("2006-01-01", None), "1990-01-01..2026-10-06": ("1990-01-01", None), "1962..2026 full record": (None, None),
       "2000-01-01..2015-12-31 (pre-window)": ("2000-01-01", "2015-12-31")}
res["periods"] = {}
for nm, (a, b) in PER.items():
    s = shift_all[a:b] if (a or b) else shift_all
    st = stats(s); st["boot90_year_blocks"] = year_block_boot(s, KEYS, B=1000 if len(s) > 8000 else 2000)
    res["periods"][nm] = st
    q = st["shift_q"]
    print(f"\n== {nm}: n={st['n']}  shift p05/p50/p95 = {q['p05']:.2f}/{q['p50']:.2f}/{q['p95']:.2f}  min {st['shift_min']:.2f} max {st['shift_max']:.2f}")
    print(f"   frac shift<=-4: {st['frac_shift_le_m4']:.3f}  <=-2: {st['frac_shift_le_m2']:.3f}  <-1: {st['frac_shift_lt_m1']:.3f}  <=-6: {st['frac_shift_le_m6']:.3f}  >=0: {st['frac_shift_ge_0']:.3f}")
    bb = st["boot90_year_blocks"]; print(f"   year-block 90% CI: shift<=-4 {bb['le_m4'][0]:.3f}-{bb['le_m4'][1]:.3f}; <=-2 {bb['le_m2'][0]:.3f}-{bb['le_m2'][1]:.3f}; p05 {bb['p05'][0]:.2f}..{bb['p05'][1]:.2f}; p50 {bb['p50'][0]:.2f}..{bb['p50'][1]:.2f}; p95 {bb['p95'][0]:.2f}..{bb['p95'][1]:.2f}")

# ---------------------------------------------------------------- reference sensitivity (what if 'full pool' is not 660)
s16 = shift_all["2016-01-01":]
sens = {}
for ref in (656.0, 658.0, 660.0, 662.0):
    s = lb["2016-01-01":] - ref
    sens[str(ref)] = {"frac_4ft_dry": float((4 + s <= 0).mean()), "frac_4ft_lt1": float((4 + s < 1).mean()), "p50": float(s.median())}
res["reference_sensitivity_2016on"] = sens
print("\nreference-pool sensitivity (2016+) fraction 4-ft flat dry:", {k: round(v["frac_4ft_dry"], 3) for k, v in sens.items()})
# guide-relative
g = pd.concat([lb, gc], axis=1, keys=["lvl", "gc"], sort=True).dropna()
g = g[g.index >= "2016-01-01"]; sg = g.lvl - g.gc
res["vs_operator_guide_2016on"] = dict(n=int(len(g)), q={f"p{int(q*100):02d}": float(sg.quantile(q)) for q in QS}, frac_below_guide_4=float((sg <= -4).mean()), frac_below_guide_2=float((sg <= -2).mean()),
                                       frac_4ft_flat_dry_vs_guide=float((4 + sg <= 0).mean()), guide_values=sorted(map(float, gc.round(2).unique()))[:8])
print("vs guide (2016+): n", len(g), "p05/p50/p95", sg.quantile(.05).round(2), sg.quantile(.5).round(2), sg.quantile(.95).round(2), " frac<=-4:", round(float((sg <= -4).mean()), 3), " frac<=-2:", round(float((sg <= -2).mean()), 3))

# ---------------------------------------------------------------- seasonality (2016+ and 1990+)
for lab, a in (("2016on", "2016-01-01"), ("1990on", "1990-01-01")):
    s = shift_all[a:]
    mo = s.groupby(s.index.month).agg(p10=lambda x: x.quantile(.1), p50="median", p90=lambda x: x.quantile(.9), mn="min", mx="max")
    mo["frac_le_m4"] = s.groupby(s.index.month).apply(lambda x: (x <= -4).mean())
    mo["frac_le_m2"] = s.groupby(s.index.month).apply(lambda x: (x <= -2).mean())
    res[f"monthly_{lab}"] = {int(m): {k: round(float(v), 3) for k, v in r.items()} for m, r in mo.iterrows()}
    print(f"\nmonthly shift ({lab})\n", mo.round(2).to_string())
# annual-cycle amplitude: mean of monthly medians, max-min
mm = shift_all["1990-01-01":].groupby(shift_all["1990-01-01":].index.month).median()
res["annual_cycle_1990on"] = dict(monthly_median_range_ft=float(mm.max() - mm.min()), month_max=int(mm.idxmax()), month_min=int(mm.idxmin()))
print("monthly-median range", mm.max() - mm.min(), "max month", mm.idxmax(), "min month", mm.idxmin())

# ---------------------------------------------------------------- per-year table (drought years)
yt = []
for y in range(1990, 2027):
    s = shift_all[str(y)]
    if len(s) < 300 and y != 2026: continue
    mi = s.idxmin()
    yt.append(dict(year=y, n=int(len(s)), min_level=float(lb[mi]), min_date=str(mi.date()), p50_shift=float(s.median()), p05_shift=float(s.quantile(.05)), days_le_m4=int((s <= -4).sum()), frac_le_m4=float((s <= -4).mean()),
                   days_le_m8=int((s <= -8).sum()), frac_le_m2=float((s <= -2).mean()), swing_p99_p01=float(s.quantile(.99) - s.quantile(.01))))
ydf = pd.DataFrame(yt); res["per_year"] = yt
print("\nper-year\n", ydf.round(2).to_string(index=False))

# ---------------------------------------------------------------- consecutive-run analysis of a 4-ft flat being dry (>= N days)
def runs(mask):
    r, c = [], 0
    for v in mask.values:
        if v: c += 1
        elif c: r.append(c); c = 0
    if c: r.append(c)
    return r
rr = runs(shift_all["2016-01-01":] <= -4)
res["dry4_runs_2016on"] = dict(n_runs=len(rr), median_len=float(np.median(rr)) if rr else 0, max_len=int(max(rr)) if rr else 0, share_of_dry_days_in_runs_ge_30d=float(sum(x for x in rr if x >= 30) / max(sum(rr), 1)))
print("\nruns of shift<=-4 (2016+):", res["dry4_runs_2016on"])

# ---------------------------------------------------------------- area per foot: storage-derived (independent) vs CWMS levels vs 3DEP proxy
st = json.load(open(f"{AD}/stor_p1.json"))
sdf = pd.DataFrame(st["values"], columns=["ms", "stor_acft", "q"]); sdf["date"] = pd.to_datetime(sdf.ms, unit="ms"); sdf = sdf[sdf.stor_acft.notna()].set_index("date")["stor_acft"]
rr_ = raw_s.copy(); rr_.index = rr_.index + pd.Timedelta(days=1)   # back to the raw CWMS stamps so stor and elev pair exactly
pair = pd.concat([rr_, sdf], axis=1, keys=["z", "S"], sort=True).dropna()
print("\nstorage/elevation pairs:", len(pair), pair.index.min().date(), pair.index.max().date())
res["storage"] = dict(n_pairs=int(len(pair)), first=str(pair.index.min().date()), last=str(pair.index.max().date()))
# is the stage-storage mapping time-invariant?  bin by 0.5 ft and compare eras
bins = np.arange(646, 666.5, 1.0)
era = {"1962-1989": pair[:"1989-12-31"], "1990-2009": pair["1990":"2009"], "2010-2026": pair["2010":]}
tab = {}
for e, d in era.items():
    b = pd.cut(d.z, bins); tab[e] = d.groupby(b, observed=True).S.median()
cmp_ = pd.DataFrame(tab); print("\nmedian storage (ac-ft) by 1-ft pool bin and era (checks whether the stage-storage mapping changed):\n", cmp_.round(0).to_string())
cmp_["d_2010_vs_1962"] = cmp_["2010-2026"] - cmp_["1962-1989"]; res["storage_era_compare_1ft_bins"] = {str(k): {c: (None if pd.isna(v) else float(v)) for c, v in r.items()} for k, r in cmp_.iterrows()}

def area_curve(d, z0, z1, win=1.5):
    """A(z)=dS/dz by local linear fit of S on z within +-win ft windows (ac-ft per ft = acres)"""
    out = []
    for zc in np.arange(z0, z1 + 0.01, 1.0):
        m = d[(d.z >= zc - win) & (d.z <= zc + win)]
        if len(m) < 40 or np.ptp(m.z) < 1.0: out.append((zc, np.nan, len(m))); continue
        b = np.polyfit(m.z, m.S, 1)[0]; out.append((zc, float(b), len(m)))
    return pd.DataFrame(out, columns=["z", "acres", "n"])
for e in ("1990-2009", "2010-2026"):
    ac = area_curve(era[e], 648, 664); print(f"\nA(z)=dS/dz local fit, era {e}:\n", ac.round(0).to_string(index=False)); res[f"A_of_z_{e}"] = ac.replace({np.nan: None}).to_dict("records")
rec = pair["2010":]
# S(z) quadratic over 647-665 ft  =>  A(z)=dS/dz (surface area, acres), dA/dz = 2*q2[0] (acres gained per foot of pool rise; this is the 'acres per foot' number)
m = rec[(rec.z >= 647) & (rec.z <= 665)]
q2 = np.polyfit(m.z, m.S, 2)
def area_at(z): return 2 * q2[0] * z + q2[1]
dAdz = 2 * q2[0]
resid = m.S - np.polyval(q2, m.z)
res["area_per_ft"] = dict(fit="quadratic S(z) on 2010-2026 pairs, 647-665 ft", n=int(len(m)), A_at_650=float(area_at(650)), A_at_655=float(area_at(655)), A_at_660=float(area_at(660)), A_at_661_98=float(area_at(661.98)),
                          dAdz_ac_per_ft=float(dAdz), rel_per_ft_at_660=float(dAdz / area_at(660)), rel_per_ft_at_661_98=float(dAdz / area_at(661.98)), resid_sd_acft=float(resid.std()),
                          hypso_truth_json=dict(dA_dz_ac_per_ft=961.8, rel_per_ft=0.016645, z_ref=661.98, A_ref_ac=57782.7, fit_range=[646.99, 664.85], r2=0.99945),
                          proxy_3dep_ac_per_ft=1001.56, proxy_3dep_rel_per_ft=0.0179)
# slope of the era tables (A(660)-A(650))/10
for e in ("1990-2009", "2010-2026"):
    ac = pd.DataFrame(res[f"A_of_z_{e}"]).set_index("z").acres
    res["area_per_ft"][f"table_slope_650_to_660_{e}"] = float((ac[660.0] - ac[650.0]) / 10.0)
    res["area_per_ft"][f"table_slope_654_to_660_{e}"] = float((ac[660.0] - ac[654.0]) / 6.0)
a665 = 248476984.33536 / 4046.8564224; a625 = 111895580.07936 / 4046.8564224
res["area_per_ft"]["cwms_area_levels_ac"] = dict(top_of_flood_665ft=a665, top_of_inactive_625ft=a625, mean_ac_per_ft_625_to_665=(a665 - a625) / 40.0)
# max relative difference between eras in the stage-storage mapping (1-ft bins 647-665)
cc = cmp_.loc[:, ["1962-1989", "1990-2009", "2010-2026"]].dropna()
cc = cc[[iv.left >= 647 for iv in cc.index]]
res["storage_mapping_max_rel_diff_between_eras"] = float(((cc.max(axis=1) - cc.min(axis=1)) / cc.mean(axis=1)).max())
print("max relative era difference in median storage per 1-ft bin (647-665):", res["storage_mapping_max_rel_diff_between_eras"])
print(f"\nrecomputed (2010+ pairs, 647-665 ft quadratic): A(650)={area_at(650):.0f} A(655)={area_at(655):.0f} A(660)={area_at(660):.0f} A(661.98)={area_at(661.98):.0f} ac; dA/dz={dAdz:.0f} ac/ft; rel/ft={dAdz/area_at(660):.4f} (at 660) {dAdz/area_at(661.98):.4f} (at 661.98)")
print("table slopes:", {k: round(v) for k, v in res["area_per_ft"].items() if k.startswith("table_slope")})
print(f"CWMS area levels: {a665:.0f} ac at 665.0 ft (Top of Flood), {a625:.0f} ac at 625.0 ft (Top of Inactive): mean {(a665-a625)/40:.0f} ac/ft over 625-665")
res["area_at_pool_levels_ac_quad"] = {str(z): float(area_at(z)) for z in (665, 660, 656, 650, 648)}
res["frac_surface_lost_vs_660"] = {str(z): float(1 - area_at(z) / area_at(660)) for z in (656, 650, 648)}
print("quad surface area (ac) at 665/660/656/650/648:", [round(area_at(z)) for z in (665, 660, 656, 650, 648)], " fraction of 660-ft surface lost at 656/650/648:", [round(1 - area_at(z) / area_at(660), 3) for z in (656, 650, 648)])
print("(fit supported only for 647-665 ft; deeper drawdowns extrapolate)")

json.dump(res, open(f"{OUT}/hartwell_effective_depth_results.json", "w"), indent=1, default=float)
print("\nwrote", f"{OUT}/hartwell_effective_depth_results.json")
