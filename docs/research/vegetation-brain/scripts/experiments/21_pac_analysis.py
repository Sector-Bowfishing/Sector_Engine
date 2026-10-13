"""Lake-level: S2 / Sector-grass summaries vs FWC sonar PAC (% area covered) and PVI (% volume infested), lake-years 2018-2023."""
import json, glob, numpy as np
from pathlib import Path
from scipy.stats import spearmanr, pearsonr
from sklearn.metrics import roc_auc_score
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parent.parent
R = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT/"out/pac/*.json")))]
R = [r for r in R if r["scenes"]]
METR = ["cell_grass_frac_lake", "px_ndvi_sector_ge30", "px_fai_gt005", "NDVI_q90", "NDVI_q99", "NDAVI_q90", "FAI_q90", "FAI_q99", "NIR_q90"]
rows = []
for r in R:
    m = r["meta"]; sc = sorted(r["scenes"], key=lambda s: abs(s["dt"]))
    # "shipped-like" single scene: closest scene that reads >= 50 % of non-grass clarity water, else the best-cov one
    good = [s for s in sc if s["cov"] >= 0.5]; one = good[0] if good else max(sc, key=lambda s: s["cov"])
    row = dict(lake=m["lake"], year=m["year"], PAC=m["PAC"], PVI=m["PVI"], km2=m["km2"], n_scenes=len(sc), cov_single=one["cov"], pass_ok=bool(good))
    for k in METR:
        row[k+"|single"] = one[k]
        v = [s[k] for s in sc if s[k] is not None]
        row[k+"|min2"] = min(v) if len(v) >= 2 else None       # persistence-style: both scenes must agree
        row[k+"|mean"] = float(np.mean(v)) if v else None
    rows.append(row)
json.dump(rows, open(ROOT/"out/pac_lakeyear_table.json", "w"), indent=1)
print(len(rows), "lake-years;", len({r["lake"] for r in rows}), "lakes; pass_ok", sum(r["pass_ok"] for r in rows))
res = {}
def corr(sel, name):
    out = {}
    for tgt in ("PAC", "PVI"):
        y = np.array([r[tgt] for r in sel], float)
        for k in METR:
            for v in ("single", "min2", "mean"):
                x = np.array([np.nan if r[f"{k}|{v}"] is None else r[f"{k}|{v}"] for r in sel], float); ok = np.isfinite(x)
                if ok.sum() < 10: continue
                out[f"{tgt}|{k}|{v}"] = dict(n=int(ok.sum()), rho=round(float(spearmanr(x[ok], y[ok])[0]), 3))
    res[name] = out
    return out
corr(rows, "all"); corr([r for r in rows if r["pass_ok"]], "pass_ok_only")
# detection of high-cover lake-years
def aucs(sel, name, pos, neg):
    out = {}
    for k in METR:
        for v in ("single", "min2"):
            xs = [(r[f"{k}|{v}"], 1) for r in sel if pos(r) and r[f"{k}|{v}"] is not None] + [(r[f"{k}|{v}"], 0) for r in sel if neg(r) and r[f"{k}|{v}"] is not None]
            y = np.array([a[1] for a in xs]); x = np.array([a[0] for a in xs])
            if y.sum() >= 5 and (1 - y).sum() >= 5: out[f"{k}|{v}"] = dict(n_pos=int(y.sum()), n_neg=int((1-y).sum()), auc=round(float(roc_auc_score(y, x)), 3))
    res[name] = out
aucs(rows, "AUC_PAC>=50_vs_PAC<20", lambda r: r["PAC"] >= 50, lambda r: r["PAC"] < 20)
aucs(rows, "AUC_PVI>=20_vs_PVI<5", lambda r: r["PVI"] >= 20, lambda r: r["PVI"] < 5)
aucs([r for r in rows if r["PAC"] >= 30], "AUC_topped(PVI/PAC>=0.5)_vs_PVI/PAC<0.25 (PAC>=30 only)", lambda r: r["PVI"] / r["PAC"] >= 0.5, lambda r: r["PVI"] / r["PAC"] < 0.25)
# binned by mean biovolume in covered area (PVI/PAC) and by PAC
def binned(key, edges, label):
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        sel = [r for r in rows if a <= key(r) < b]
        if not sel: continue
        g = [r["cell_grass_frac_lake|single"] for r in sel]; p = [r["px_ndvi_sector_ge30|single"] for r in sel]
        out.append(dict(bin=f"{a}-{b}", n=len(sel), median_cell_grass=round(float(np.median(g)), 4), p75=round(float(np.percentile(g, 75)), 4), median_px_ndvi30=round(float(np.median(p)), 4), median_PAC=float(np.median([r["PAC"] for r in sel])), median_PVI=float(np.median([r["PVI"] for r in sel]))))
    res[label] = out
binned(lambda r: r["PAC"], [0, 10, 20, 40, 60, 80, 101], "bins_by_PAC")
binned(lambda r: r["PVI"], [0, 2, 5, 10, 20, 40, 101], "bins_by_PVI")
binned(lambda r: (r["PVI"] / r["PAC"]) if r["PAC"] >= 30 else -1, [0, 0.15, 0.25, 0.4, 0.6, 1.01], "bins_by_meanBV_PVI_over_PAC_(PAC>=30)")
json.dump(res, open(ROOT/"out/metrics_pac.json", "w"), indent=1)
fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
x = np.array([r["PAC"] for r in rows]); y = np.array([r["cell_grass_frac_lake|single"] for r in rows]); c = np.array([r["PVI"] / max(1, r["PAC"]) for r in rows])
s = ax[0].scatter(x, y * 100, c=c, cmap="viridis", s=24); ax[0].set_xlabel("FWC sonar PAC (% lake area vegetated)"); ax[0].set_ylabel("Sector cell-grass, % of lake cells"); plt.colorbar(s, ax=ax[0], label="PVI/PAC (mean biovolume in veg)")
ax[0].set_title("Sector grass cells vs sonar PAC")
ax[1].scatter([r["PVI"] for r in rows], y * 100, c=c, cmap="viridis", s=24); ax[1].set_xlabel("FWC sonar PVI (% water volume occupied)"); ax[1].set_title("vs PVI")
ax[2].scatter([r["PAC"] for r in rows], [r["FAI_q99|single"] for r in rows], c=c, cmap="viridis", s=24); ax[2].set_xlabel("PAC"); ax[2].set_ylabel("FAI 99th pct (lake px)"); ax[2].set_title("FAI q99 vs PAC")
plt.tight_layout(); plt.savefig(ROOT/"out/figures/pac_lake_level.png", dpi=110)
for nm in ("all",):
    for k in ["PAC|cell_grass_frac_lake|single", "PAC|cell_grass_frac_lake|min2", "PAC|px_ndvi_sector_ge30|single", "PAC|NDVI_q99|single", "PAC|FAI_q99|single", "PAC|NDAVI_q90|single", "PVI|cell_grass_frac_lake|single", "PVI|px_ndvi_sector_ge30|single", "PVI|FAI_q99|single", "PVI|NDVI_q99|single"]:
        print(nm, k, res[nm].get(k))
for k, v in res.items():
    if k.startswith("AUC") or k.startswith("bins"): print(k, json.dumps(v)[:900])
