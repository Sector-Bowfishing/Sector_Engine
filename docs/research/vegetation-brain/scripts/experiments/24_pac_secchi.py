"""Stratify lake-level S2-vs-sonar agreement by Secchi (WQP) and check lake-clustering robustness."""
import json, numpy as np, datetime as dt
from pathlib import Path
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
ROOT = Path(__file__).resolve().parent.parent
T = json.load(open(ROOT/"out/pac_lakeyear_table.json")); meta = {(o["lake"], o["year"]): o for o in json.load(open(ROOT/"data/pac_lakeyears.json"))}
S = json.load(open(ROOT/"out/secchi_pac.json"))
for r in T:
    m = [o for o in json.load(open(ROOT/"data/pac_lakeyears.json")) if o["lake"] == r["lake"] and o["year"] == r["year"]][0]; r["lake_id"] = m["lake_id"]
    v = [(dt.date.fromisoformat(d), x) for d, x in S.get(m["lake_id"], [])]
    yr = [x for d, x in v if d.year == r["year"] and 5 <= d.month <= 10]; pm = [x for d, x in v if abs(d.year - r["year"]) <= 1 and 5 <= d.month <= 10]
    r["secchi"] = float(np.median(yr)) if len(yr) >= 2 else (float(np.median(pm)) if len(pm) >= 3 else None); r["secchi_src"] = "year" if len(yr) >= 2 else ("pm1yr" if len(pm) >= 3 else None)
json.dump(T, open(ROOT/"out/pac_lakeyear_table.json", "w"), indent=1)
res = {}
have = [r for r in T if r["secchi"] is not None]
print("lake-years with Secchi", len(have), "of", len(T), "; lakes", len({r["lake"] for r in have}))
def rho(sel, tgt, k="cell_grass_frac_lake|single"):
    x = np.array([r[k] for r in sel], float); y = np.array([r[tgt] for r in sel], float)
    return (round(float(spearmanr(x, y)[0]), 2), len(sel)) if len(sel) >= 8 else (None, len(sel))
strata = [("<0.5 m", 0, 0.5), ("0.5-1 m", 0.5, 1.0), ("1-2 m", 1.0, 2.0), (">=2 m", 2.0, 99)]
res["strata"] = {}
for nm, a, b in strata:
    sel = [r for r in have if a <= r["secchi"] < b]
    pos = [r for r in sel if r["PVI"] >= 15]; neg = [r for r in sel if r["PVI"] < 5]
    au = None
    if len(pos) >= 4 and len(neg) >= 4:
        au = round(float(roc_auc_score([1]*len(pos) + [0]*len(neg), [r["px_ndvi_sector_ge30|single"] for r in pos + neg])), 3)
    res["strata"][nm] = dict(n=len(sel), lakes=len({r["lake"] for r in sel}), rho_PVI_cellgrass=rho(sel, "PVI"), rho_PAC_cellgrass=rho(sel, "PAC"), rho_PVI_px30=rho(sel, "PVI", "px_ndvi_sector_ge30|single"),
        n_pvi_ge15=len(pos), n_pvi_lt5=len(neg), auc_px30_PVIge15_vs_lt5=au, median_cell_grass=round(float(np.median([r["cell_grass_frac_lake|single"] for r in sel])), 4) if sel else None, median_PVI=float(np.median([r["PVI"] for r in sel])) if sel else None)
    print(nm, res["strata"][nm])
sec = np.array([r["secchi"] for r in have]); resid = {}
for tgt in ("PAC", "PVI"):
    resid[tgt] = round(float(spearmanr(sec, [r[tgt] for r in have])[0]), 2)
res["secchi_vs_sonar_rho"] = resid
# per-lake means (cluster robustness)
lk = {}
for r in T: lk.setdefault(r["lake"], []).append(r)
means = [dict(lake=k, PAC=np.mean([r["PAC"] for r in v]), PVI=np.mean([r["PVI"] for r in v]), cg=np.mean([r["cell_grass_frac_lake|single"] for r in v]), px=np.mean([r["px_ndvi_sector_ge30|single"] for r in v])) for k, v in lk.items()]
res["per_lake_mean_rho"] = {t: {m: round(float(spearmanr([x[t] for x in means], [x[m] for x in means])[0]), 3) for m in ("cg", "px")} for t in ("PAC", "PVI")}; res["n_lakes"] = len(means)
# residual: partial association of grass fraction with PVI controlling for nothing; test whether Secchi explains misses among high-PVI
hi = [r for r in have if r["PVI"] >= 15]
res["high_PVI_lakeyears"] = dict(n=len(hi), rho_secchi_vs_cellgrass=(round(float(spearmanr([r["secchi"] for r in hi], [r["cell_grass_frac_lake|single"] for r in hi])[0]), 2) if len(hi) >= 8 else None),
        rows=[(r["lake"], r["year"], r["PVI"], r["PAC"], round(r["secchi"], 2), round(r["cell_grass_frac_lake|single"], 3)) for r in sorted(hi, key=lambda r: -r["PVI"])])
json.dump(res, open(ROOT/"out/metrics_pac_secchi.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "strata"}, indent=0)[:2500])
